# -*- coding: utf-8 -*-
"""접수에서 문제 난 일정의 **대안을 미리 준비해** 둔다 — 확인 화면의 「바꾸기」가 계산 없이 뜨게. `[2026-10-19 사용자 지시]`

사용자: 「계획서 접수에서 문제 난 일정은 에이전트가 대안을 보내오잖아 — 그거 받아서 반영하면 되잖아」 ·
「접수 뒤 검증을 넘어갈 때 대안 3개를 완성본으로 다 뽑아 저장 — 바꾸기를 누르면 계산 · 로딩 없이 그대로」.

    접수 읽기 · 검사 끝(확인 화면)  →  뒤에서 문제 난 일정마다 `GET …/candidates` 와 같은 계산을 끝까지(팀 대안 → 두 구간 이동 → 판정 → 이유 문장)
                                     →  `intake_alternatives`(061)에 일정 줄마다 한 행
    「바꾸기」                       →  저장분이 지금 판에 맞으면 그대로(`serve`) · 앞뒤 일정만 바뀌었으면 이동 구간만 다시 잰다
                                     ·  저장분이 없으면(고객이 바꾼 일정 등) 실시간 진행이 어림으로 먼저 보이고 끝난 줄부터 바꾼다(`stream`)
    새 판(고치기 · 되돌리기 · 자동 추천 적용) →  뒤에서 낡은 줄만 다시 준비한다(`prepare_later`)

★카카오 값은 저장하지 않는다(약관 — `kakao_local.py`). 풀이나 최종 후보에 카카오에서 온 곳이 있으면 그 일정은 저장하지 않는다(「바꾸기」 때 계산).
★후보마다 앞 · 뒤 두 구간을 재는 일은 작업자 묶음(`WORKERS`)에서 병렬로 한다 — 이동 계산기 모양(`engine(pa, pb, b_start, not_before)`)은 그대로 부르기만 한다.
★어떤 실패도 확인 화면을 막지 않는다 — 저장하지 못하면 「바꾸기」가 예전처럼 계산한다.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FutureTimeout
from contextvars import copy_context
from datetime import datetime
from typing import Any, Callable

from . import candidates as cand
from .review import KST, _Budgeted

log = logging.getLogger(__name__)

#: 후보 구간을 병렬로 재는 작업자 수 · 한 접수 안에서 일정을 병렬로 준비하는 수. ★우리가 고른 값(측정 전)
WORKERS = 4
#: 후보 구간 계산의 **벽시계 마감**(초) — 실시간 「바꾸기」는 옛 계산과 같은 상한(`ENGINE_BUDGET_S` 12초)에서 끊고 남은 구간은 어림으로 둔다.
#: 미리 준비(뒤에서 · 고객은 기다리지 않는다)는 더 길게 줘서 끝까지 잰다. ★우리가 고른 값 — 2026-10-19 로컬 실측: 마감 없이 후보마다 12초씩 주면
#: 실시간 길의 마지막 실측이 중앙값 37.8초(옛 길 12.6초)였다
LIVE_DEADLINE_S = cand.ENGINE_BUDGET_S
PREPARE_DEADLINE_S = 90.0
#: 미리 준비할 때 문제로 보는 검사 줄
PROBLEM_ROWS = ("place", "hours", "closed", "time")
PROBLEM_STATES = ("picked_nearest", "unresolved", "needs_choice")

_running: set[str] = set()
_running_lock = threading.Lock()
#: 지금 준비 중인 일정(접수 · 원본 · 줄) → 끝나면 결과가 서는 Future. ★`[2026-10-19 사용자 지시]` 준비가 끝나기 전에 「바꾸기」를 누르면
#:  같은 계산을 다시 돌리지 않고 어림 카드를 먼저 보인 뒤 이 결과를 기다려 이어 받는다(`stream` · `serve`)
_preparing: dict[tuple[str, str, int], Future] = {}
#: 준비 결과를 기다리는 최대 시간(초) — 넘으면 그 자리에서 계산한다
WAIT_PREPARE_S = 120.0
_pool = ThreadPoolExecutor(max_workers=WORKERS * 2, thread_name_prefix="intake-alternatives")


# ── 어느 일정 · 서명 ───────────────────────────────────────────────
def needs_alternatives(item: dict[str, Any]) -> bool:
    """미리 준비할 일정 — 빼지 않았고 고정 · 예약이 아니며, 장소가 모호 · 못 찾음 · 이름 없음이거나 검사 줄에 확인 필요(bad · warn)가 있다.
    예약한 곳 이름을 묻는 줄(`needs_name`)은 후보를 권하지 않으므로 뺀다."""
    if item.get("removed") or item.get("locked") or item.get("booked") is True:
        return False
    if cand.is_risk_item(item):
        return False                                       # 위험 날짜 일정 — 「바꾸기」 때 안전 대안 경로가 그때의 확인으로 낸다(미리 저장하지 않는다)
    state = item.get("place_state")
    if state == "needs_name" or state == "none":
        return False
    if state in PROBLEM_STATES:
        return True
    return any(r.get("row") in PROBLEM_ROWS and r.get("result") in ("bad", "warn") for r in item.get("rows") or [])


def settled_target(item: dict[str, Any]) -> bool:
    """`[2026-10-20 사용자 지시]` 문제없이 **확정된 일정**도 대안을 미리 뽑는다(`travel.candidates.prepare_scope: all`) — 계획서는 「대안 추천을 다 해서 넣는다」.
    활동 · 식사 중 장소가 정해진 것만. 빼지 않았고 고정 · 예약이 아니다. ★숙소는 문제가 있을 때만(숙소 팀 바깥 검색 한도를 아낀다 — 「숙소 모드」)."""
    if item.get("removed") or item.get("locked") or item.get("booked") is True or cand.is_risk_item(item):
        return False
    if item.get("kind") not in ("activity", "dining") or _lodging(item):
        return False
    return item.get("place_state") in ("found", "customer") and bool(item.get("place"))


def prepare_scope() -> str:
    """`problems`(문제 난 일정만 — 옛 동작) · `all`(확정 일정까지). 설정을 못 읽으면 `problems`."""
    from app.core.settings import get_guardrails

    try:
        value = get_guardrails().get("travel.candidates.prepare_scope")
    except Exception:                                         # noqa: BLE001
        return "problems"
    return value if value in ("problems", "all") else "problems"


def _place_sig(place: dict[str, Any] | None) -> list[Any]:
    if not place:
        return [None]
    return [place.get("name"), round(float(place["latitude"]), 5) if place.get("latitude") is not None else None,
            round(float(place["longitude"]), 5) if place.get("longitude") is not None else None]


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:24]


def signatures(review: dict[str, Any], item: dict[str, Any]) -> tuple[str, str, str]:
    """(그 일정 · 앞 일정 · 뒤 일정)의 서명. 그 일정은 장소 · 날짜 · 시각 · 종류 · 장소 상태 · 지역, 앞뒤는 장소와 시각(이동 구간을 정하는 값)."""
    prev, nxt = cand.neighbours(review["items"], item)
    own = _sha([_place_sig(item.get("place")), item.get("date"), item.get("end_date"), item.get("starts_at"), item.get("ends_at"),
                item.get("kind"), item.get("place_state"), (item.get("parts") or {}).get("area"), item.get("title")])

    def side(x: dict[str, Any] | None) -> str:
        return _sha(None if x is None else [x.get("id"), _place_sig(x.get("place")), x.get("date"), x.get("starts_at"), x.get("ends_at")])

    return own, side(prev), side(nxt)


# ── 저장 ───────────────────────────────────────────────────────────
def _has_kakao(places: list[dict[str, Any]]) -> bool:
    return any((p or {}).get("source") == "kakao" for p in places)


def save(conn, *, tenant_id: str, intake_id: Any, item: dict[str, Any], revision: int, sigs: tuple[str, str, str],
         body: dict[str, Any], pool: list[dict[str, Any]], notes: list[str], elapsed_ms: int) -> bool:
    """한 일정의 완성본을 저장한다. 카카오 값이 섞였으면 저장하지 않고 False."""
    if _has_kakao(pool) or _has_kakao([c["place"] for c in body.get("candidates") or []]):
        return False
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "INSERT INTO intake_alternatives (tenant_id, intake_id, source_id, item_index, revision, item_sig, before_sig, after_sig, body, pool, notes, elapsed_ms, computed_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now()) ON CONFLICT (intake_id, source_id, item_index) DO UPDATE SET "
            "revision=EXCLUDED.revision, item_sig=EXCLUDED.item_sig, before_sig=EXCLUDED.before_sig, after_sig=EXCLUDED.after_sig, "
            "body=EXCLUDED.body, pool=EXCLUDED.pool, notes=EXCLUDED.notes, elapsed_ms=EXCLUDED.elapsed_ms, computed_at=now()",
            (tenant_id, intake_id, item["source_id"], int(item["index"]), int(revision), *sigs,
             json.dumps(body, ensure_ascii=False, default=str), json.dumps(pool, ensure_ascii=False, default=str),
             json.dumps(list(notes), ensure_ascii=False), int(elapsed_ms)))
    return True


def load(conn, tenant_id: str, intake_id: Any, item: dict[str, Any]) -> dict[str, Any] | None:
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT revision, item_sig, before_sig, after_sig, body, pool, notes, computed_at, elapsed_ms FROM intake_alternatives "
                        "WHERE tenant_id=%s AND intake_id=%s AND source_id=%s AND item_index=%s",
                        (tenant_id, intake_id, item["source_id"], int(item["index"])))
            row = cur.fetchone()
    except Exception as exc:                                  # noqa: BLE001 — 표가 없는 DB(061 전)면 저장분이 없는 것이다
        if type(exc).__name__ != "UndefinedTable":
            raise
        conn.rollback()
        return None
    if row is None:
        return None
    keys = ("revision", "item_sig", "before_sig", "after_sig", "body", "pool", "notes", "computed_at", "elapsed_ms")
    return dict(zip(keys, row))


def usable(row: dict[str, Any] | None, review: dict[str, Any], item: dict[str, Any]) -> tuple[str, list[str]]:
    """저장분을 지금 판에 쓸 수 있나 — (`fresh` 그대로 · `legs` 이동 구간만 낡음 · `none` 못 씀, 낡은 쪽 [`before` · `after`])."""
    if row is None:
        return "none", []
    own, before, after = signatures(review, item)
    if row["item_sig"] != own:
        return "none", []
    sides = [name for name, now, then in (("before", before, row["before_sig"]), ("after", after, row["after_sig"])) if now != then]
    return ("legs" if sides else "fresh"), sides


def _lodging(item: dict[str, Any]) -> bool:
    return item.get("kind") == "lodging" or cand._is_stay_line(item)


def reuse_row(row: dict[str, Any] | None, state: str, item: dict[str, Any]) -> dict[str, Any] | None:
    """다시 판정할 때 쓸 저장분 — 앞뒤 일정만 바뀌었거나(`legs`), **숙소**는 고객이 바꾼 뒤에도 저장해 둔 풀을 쓴다
    (`[2026-10-19 사용자 지시]` 바깥 숙소 비교는 접수 1건에서 문제 난 숙소 항목마다 1회만 — 「바꾸기」 · 다시 열기에서 다시 부르지 않는다)."""
    if row is None:
        return None
    if state == "legs" or (state == "none" and _lodging(item) and row.get("pool")):
        return row
    return None


def _meta(row: dict[str, Any], stale: list[str]) -> dict[str, Any]:
    at = row["computed_at"]
    return {"revision": row["revision"], "computed_at": at.isoformat() if hasattr(at, "isoformat") else str(at), "stale": stale}


# ── 계산 ───────────────────────────────────────────────────────────
class _Deadline:
    """이동 계산기 앞에 **벽시계 마감**을 건다 — 마감이 지나면 부르지 않고 못 채웠다고 답한다(그 구간은 어림값). 한 번의 호출은 중간에 끊지 못한다."""

    def __init__(self, engine: Callable[..., Any], deadline: float) -> None:
        self._engine, self._deadline = engine, deadline

    def __call__(self, a: dict[str, Any], b: dict[str, Any], arrive: Any, not_before: Any = None):
        if time.monotonic() >= self._deadline:
            return None, {"code": "budget", "reason": "이동 계산에 시간이 오래 걸려 어림값으로 냈어요"}
        return self._engine(a, b, arrive, not_before)


def judge_parallel(connect: Callable[[], Any], tenant_id: str, gathered: cand.Gathered, *,
                   on_done: Callable[[int, dict[str, Any], dict[str, Any]], None] | None = None,
                   engine_factory: Callable[[], Any] | None = None,
                   deadline_s: float | None = None) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """풀의 후보마다 앞 · 뒤 두 구간을 이동 계산기로 재 판정한다 — 후보끼리 병렬(`WORKERS`), 후보마다 자기 연결 · 자기 시간 상한(`ENGINE_BUDGET_S`).
    `on_done(풀 순번, 장소, 판정)` 는 끝나는 대로 불린다(실시간 진행이 그 줄을 바꾼다). 돌려주는 것은 풀과 같은 순서."""
    make = engine_factory or (lambda: cand.default_engine(None))      # 부를 때 찾는다(시험이 `candidates.default_engine` 을 갈아 끼운다)
    results: list[dict[str, Any] | None] = [None] * len(gathered.pool)
    until = time.monotonic() + (deadline_s if deadline_s is not None else PREPARE_DEADLINE_S)

    def one(index: int, place: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        engine = make()
        budget = _Budgeted(_Deadline(engine, until), cand.ENGINE_BUDGET_S) if engine is not None else None
        with connect() as conn:
            return index, cand.assess(conn, tenant_id, gathered.item, place, gathered.prev, gathered.nxt, budget)

    if not gathered.pool:
        return []
    with ThreadPoolExecutor(max_workers=min(WORKERS, len(gathered.pool)), thread_name_prefix="candidate-legs") as workers:
        # 작업자마다 지금 문맥을 복사해 넘긴다 — 조립이 꽂은 팀 · 계산기 자리(`service_bindings`)가 문맥에 있다
        futures = [workers.submit(copy_context().run, one, i, place) for i, (place, _cheap) in enumerate(gathered.pool)]
        for future in as_completed(futures):
            try:
                index, judged = future.result()
            except Exception:                                 # noqa: BLE001 — 그 후보는 싼 판정(어림)으로 남긴다
                log.warning("candidate leg judge failed", exc_info=True)
                continue
            results[index] = judged
            if on_done is not None:
                try:
                    on_done(index, gathered.pool[index][0], judged)
                except Exception:                             # noqa: BLE001 — 알리기 실패가 계산을 멈추지 않는다
                    log.debug("candidate partial emit failed", exc_info=True)
    return [(place, results[i] if results[i] is not None else cheap) for i, (place, cheap) in enumerate(gathered.pool)]


def _without_current(row: dict[str, Any], item: dict[str, Any]) -> list[dict[str, Any]]:
    """저장해 둔 풀에서 지금 장소(고객이 고른 곳)를 뺀다."""
    here = item.get("place")
    mine = _key({**here, "kind": None})[:3] if here else None
    return [p for p in row["pool"] or [] if mine is None or _key(p)[:3] != mine]


def judge_in_turn(connect: Callable[[], Any], tenant_id: str, gathered: cand.Gathered, *, first: list[int],
                  on_done: Callable[[int, dict[str, Any], dict[str, Any]], None] | None = None) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """고객이 기다리는 실시간 「바꾸기」 — 후보를 **차례로** 재되(보이는 카드 `first` 먼저) 계산기 시간을 모두 합쳐 `ENGINE_BUDGET_S`(12초)에서 끊는다(옛 길과 같다).
    끝난 후보마다 `on_done`. 상한 뒤의 후보는 싼 판정(어림)으로 남는다.
    ☆2026-10-19 로컬 실측: 병렬(작업자 4)로 재면 한 번 호출이 서로 CPU 를 나눠 써 느려져 마지막 실측이 33~38초였다(옛 길 12.6초). 그래서 실시간 길은 차례로 잰다."""
    engine = cand.default_engine(None)
    budget = _Budgeted(engine, cand.ENGINE_BUDGET_S) if engine is not None else None
    results: list[dict[str, Any] | None] = [None] * len(gathered.pool)
    order = [i for i in first if 0 <= i < len(gathered.pool)] + [i for i in range(len(gathered.pool)) if i not in first]
    with connect() as conn:
        for index in order:
            if budget is not None and budget.exhausted:
                break
            place = gathered.pool[index][0]
            try:
                judged = cand.assess(conn, tenant_id, gathered.item, place, gathered.prev, gathered.nxt, budget)
            except Exception:                                 # noqa: BLE001 — 그 후보는 싼 판정(어림)으로 남긴다
                log.warning("candidate leg judge failed", exc_info=True)
                continue
            results[index] = judged
            if on_done is not None:
                try:
                    on_done(index, place, judged)
                except Exception:                             # noqa: BLE001
                    log.debug("candidate partial emit failed", exc_info=True)
    return [(place, results[i] if results[i] is not None else cheap) for i, (place, cheap) in enumerate(gathered.pool)]


def _public_pool(gathered: cand.Gathered) -> list[dict[str, Any]]:
    return [place for place, _cheap in gathered.pool]


def compute(connect: Callable[[], Any], *, tenant_id: str, review: dict[str, Any], item: dict[str, Any], kakao: Any = None,
            chat: Any = None, row: dict[str, Any] | None = None, reason_wait: float | None = None,
            now: datetime | None = None, deadline_s: float | None = None) -> tuple[dict[str, Any], cand.Gathered]:
    """한 일정의 완성본 — 저장분의 풀(`row`)이 있으면 다시 모으지 않고 판정만, 없으면 모으고(팀 · 목록 · 지도 · 숙소 팀) 판정한다."""
    with connect() as conn:
        if row is not None:
            gathered = cand.regather(conn, tenant_id=tenant_id, review=review, item=item, places=_without_current(row, item),
                                     notes=list(row["notes"] or []))
        else:
            gathered = cand.gather(conn, tenant_id=tenant_id, review=review, item=item, kakao=kakao, now=now or datetime.now(KST),
                                   lodging_team=True)
    if deadline_s is not None and deadline_s <= LIVE_DEADLINE_S:
        judged = judge_in_turn(connect, tenant_id, gathered, first=list(range(cand.LIMIT)))      # 고객이 기다린다 — 차례로 · 12초 상한
    else:
        judged = judge_parallel(connect, tenant_id, gathered, deadline_s=deadline_s)
    with connect() as conn:
        body = cand.finish(conn, tenant_id=tenant_id, gathered=gathered, judged=judged, chat=chat, reason_wait=reason_wait)
    return body, gathered


def needs_kakao(item: dict[str, Any], gathered: cand.Gathered) -> bool:
    """이 일정의 후보가 **카카오 지도**에 기대는가 — 같은 이름의 다른 지점(이름 모호 · 못 찾음)이거나, 이름 없는 줄 · 숙소인데 팀이 답하지 않았고
    우리 목록만으로는 모자랐다(`gather` 가 카카오로 채우는 경우). 그런 일정은 미리 준비하지 않는다(카카오 값은 저장하지 않는다 — 「바꾸기」 때 계산)."""
    if item.get("place_state") in ("picked_nearest", "unresolved"):
        return True
    filling = item.get("place_state") == "needs_choice" or _lodging(item)
    return filling and "team_ranked" not in gathered.notes and len(gathered.pool) < cand.LIMIT + cand.POOL_EXTRA


def prepare_one(connect: Callable[[], Any], *, tenant_id: str, intake_id: Any, review: dict[str, Any], item: dict[str, Any],
                kakao: Any = None, chat: Any = None) -> str:
    """한 일정을 준비해 저장한다 — `fresh`(이미 맞음) · `saved` · `kakao`(카카오 값에 기대 저장 안 함) · `failed`.
    ★미리 준비는 **카카오를 부르지 않는다**(`kakao` 는 받지만 쓰지 않는다) — 저장할 수 없는 값을 미리 받아 무료 한도만 쓰지 않게."""
    started = time.monotonic()
    key = _item_key(intake_id, item)
    mine: Future = Future()
    with _running_lock:
        if key in _preparing:
            return "busy"                                     # 같은 일정을 다른 준비가 하고 있다
        _preparing[key] = mine
    try:
        return _prepare_one(connect, tenant_id=tenant_id, intake_id=intake_id, review=review, item=item, chat=chat, started=started)
    finally:
        with _running_lock:
            _preparing.pop(key, None)
        mine.set_result(True)


def _item_key(intake_id: Any, item: dict[str, Any]) -> tuple[str, str, int]:
    return str(intake_id), str(item["source_id"]), int(item["index"])


def wait_preparing(intake_id: Any, item: dict[str, Any], timeout: float = WAIT_PREPARE_S) -> bool:
    """이 일정을 지금 준비 중이면 끝날 때까지 기다린다 — 기다렸으면 True(끝났거나 시간이 다 됐다), 준비 중이 아니면 False."""
    with _running_lock:
        future = _preparing.get(_item_key(intake_id, item))
    if future is None:
        return False
    try:
        future.result(timeout=timeout)
    except FutureTimeout:
        log.warning("waited %.0fs for the prepared alternatives — computing here", timeout)
    return True


def is_preparing(intake_id: Any, item: dict[str, Any]) -> bool:
    with _running_lock:
        return _item_key(intake_id, item) in _preparing


def _prepare_one(connect: Callable[[], Any], *, tenant_id: str, intake_id: Any, review: dict[str, Any], item: dict[str, Any],
                 chat: Any, started: float) -> str:
    try:
        with connect() as conn:
            row = load(conn, tenant_id, intake_id, item)
        state, _sides = usable(row, review, item)
        if state == "fresh":
            return "fresh"
        reused = reuse_row(row, state, item)
        if reused is None:
            with connect() as conn:
                peek = cand.gather(conn, tenant_id=tenant_id, review=review, item=item, kakao=None, now=datetime.now(KST), lodging_team=True)
            if needs_kakao(item, peek):
                return "kakao"
            judged = judge_parallel(connect, tenant_id, peek)
            with connect() as conn:
                body = cand.finish(conn, tenant_id=tenant_id, gathered=peek, judged=judged, chat=chat)
            gathered = peek
        else:
            body, gathered = compute(connect, tenant_id=tenant_id, review=review, item=item, chat=chat, row=reused)
        with connect() as conn:
            ok = save(conn, tenant_id=tenant_id, intake_id=intake_id, item=item, revision=int(review["revision"]),
                      sigs=signatures(review, item), body=body, pool=_public_pool(gathered), notes=gathered.notes,
                      elapsed_ms=int((time.monotonic() - started) * 1000))
        return "saved" if ok else "kakao"
    except Exception:                                         # noqa: BLE001 — 준비 실패는 「바꾸기」가 계산하면 된다
        log.warning("intake alternatives prepare failed intake=%s item=%s", intake_id, item.get("id"), exc_info=True)
        return "failed"


def _current(conn, tenant_id: str, intake_id: Any) -> dict[str, Any] | None:
    from .pipeline import current_review

    with conn.cursor() as cur:
        cur.execute("SELECT customer_id FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s AND status='review'", (tenant_id, intake_id))
        row = cur.fetchone()
    if row is None:
        return None
    _state, found = current_review(conn, tenant_id=tenant_id, customer_id=row[0], intake_id=intake_id)
    return found


def prepare(connect: Callable[[], Any], *, tenant_id: str, intake_id: Any, kakao: Any = None, chat: Any = None) -> dict[str, Any]:
    """지금 판에서 문제 난 일정 · 저장분이 있는 일정 중 **낡은 것만** 준비한다(일정끼리 병렬). 센 값과 걸린 시간을 돌려준다.
    ★같은 접수를 두 번 겹쳐 돌리지 않는다 — 돌고 있으면 `busy`."""
    key = f"{tenant_id}:{intake_id}"
    with _running_lock:
        if key in _running:
            return {"busy": True}
        _running.add(key)
    started = time.monotonic()
    counts: dict[str, int] = {}
    try:
        with connect() as conn:
            review = _current(conn, tenant_id, intake_id)
            if review is None:
                return {"skipped": "not_in_review"}
            with conn.cursor() as cur:
                cur.execute("SELECT source_id::text, item_index FROM intake_alternatives WHERE tenant_id=%s AND intake_id=%s",
                            (tenant_id, intake_id))
                kept = {(s, int(i)) for s, i in cur.fetchall()}
        problems = [x for x in review["items"] if not cand.is_risk_item(x)
                    and (needs_alternatives(x) or (str(x["source_id"]), int(x["index"])) in kept)]
        # ★`[2026-10-20 사용자 지시]` 확정 일정의 대안도 처음에 뽑는다(`prepare_scope: all`) — 문제 난 일정을 먼저 맡기고 그 뒤에.
        #   확정 일정의 이유 문장은 틀 문장(모델 호출 없음 — x600 서버 모델을 채팅과 나눠 쓴다). 「바꾸기」 때 저장된 모델 문장이 있으면 그것
        picked = {id(x) for x in problems}
        settled = [x for x in review["items"] if id(x) not in picked and settled_target(x)] if prepare_scope() == "all" else []
        targets = problems + settled
        with ThreadPoolExecutor(max_workers=max(1, min(WORKERS, len(targets) or 1)), thread_name_prefix="prepare-items") as workers:
            jobs = [workers.submit(copy_context().run, prepare_one, connect, tenant_id=tenant_id, intake_id=intake_id, review=review,
                                   item=x, kakao=kakao, chat=chat if id(x) in picked else None) for x in targets]
            for job in jobs:
                state = job.result()
                counts[state] = counts.get(state, 0) + 1
        return {"revision": review["revision"], "items": len(targets), **counts, "seconds": round(time.monotonic() - started, 2)}
    except Exception:                                         # noqa: BLE001
        log.warning("intake alternatives prepare failed intake=%s", intake_id, exc_info=True)
        return {"failed": True}
    finally:
        with _running_lock:
            _running.discard(key)


def prepare_later(connect: Callable[[], Any], tenant_id: str, intake_id: Any, *, kakao: Any = None, chat: Any = None) -> None:
    """응답 뒤 뒤에서 준비한다(고객을 기다리게 하지 않는다)."""
    _pool.submit(copy_context().run, prepare, connect, tenant_id=tenant_id, intake_id=intake_id, kakao=kakao, chat=chat)


# ── 「바꾸기」 ────────────────────────────────────────────────────
def serve(connect: Callable[[], Any], conn, *, tenant_id: str, intake_id: Any, review: dict[str, Any], item: dict[str, Any],
          chat: Any = None) -> dict[str, Any] | None:
    """JSON 「바꾸기」 — 저장분이 맞으면 그대로, 앞뒤 일정만 바뀌었으면 이동 구간만 다시 재(병렬) 저장하고 돌려준다. 못 쓰면 None(부르는 쪽이 계산)."""
    if cand.is_risk_item(item):
        return None                                         # 위험 날짜 일정 — 부르는 쪽이 `candidates.alternatives`(안전 대안 경로가 먼저)로 간다
    row = load(conn, tenant_id, intake_id, item)
    state, sides = usable(row, review, item)
    if state != "fresh" and wait_preparing(intake_id, item):
        with connect() as other:                               # 준비 중이었다 — 끝난 결과를 받는다(같은 계산을 다시 돌리지 않는다)
            row = load(other, tenant_id, intake_id, item)
        state, sides = usable(row, review, item)
    reused = reuse_row(row, state, item)
    if state == "fresh":
        return {**row["body"], "prepared": _meta(row, [])}
    if reused is None:
        return None
    started = time.monotonic()
    body, gathered = compute(connect, tenant_id=tenant_id, review=review, item=item, chat=chat, row=reused, deadline_s=LIVE_DEADLINE_S)
    with connect() as other:
        save(other, tenant_id=tenant_id, intake_id=intake_id, item=item, revision=int(review["revision"]), sigs=signatures(review, item),
             body=body, pool=_public_pool(gathered), notes=gathered.notes, elapsed_ms=int((time.monotonic() - started) * 1000))
        fresh = load(other, tenant_id, intake_id, item)
    return {**body, "prepared": _meta(fresh or row, sides if state == "legs" else ["item"])}


def _pending(candidate: dict[str, Any], gathered: cand.Gathered, sides: list[str] | None, chat: Any) -> dict[str, bool]:
    from app.core.settings import get_guardrails

    legs = sides if sides is not None else ["before", "after"]
    model = chat is not None and bool(get_guardrails().get("travel.candidate_reason.enabled"))
    return {"before": "before" in legs and bool(gathered.prev and gathered.prev.get("place")),
            "after": "after" in legs and bool(gathered.nxt and gathered.nxt.get("place")),
            "reason": model and candidate.get("reason_by") == "template"}


def _key(place: dict[str, Any]) -> tuple:
    return (place.get("name"), round(float(place.get("latitude") or 0), 5), round(float(place.get("longitude") or 0), 5), place.get("kind"))


def stream(connect: Callable[[], Any], *, tenant_id: str, intake_id: Any, review: dict[str, Any], item: dict[str, Any],
           kakao: Any = None, chat: Any = None, emit: Callable[[str, dict[str, Any]], None]) -> dict[str, Any]:
    """실시간 진행 「바꾸기」 — 저장분이 맞으면 곧바로 결과. 아니면 `candidates`(직선 어림 · 줄마다 `pending`)를 먼저 `emit` 하고,
    구간 계산이 끝날 때마다 `candidate`, 이유 문장이 저장되면 `candidate`(이유)를 보낸 뒤 최종 결과(다시 고른 셋)를 돌려준다. 끝난 결과는 저장한다."""
    started = time.monotonic()
    if cand.is_risk_item(item):
        # ★`[faabcd92]` 위험 날짜 일정은 안전 대안 경로(`risks.alternatives`)가 먼저다 — 어림 카드 · 미리 준비 없이 그 결과를 그대로 낸다
        with connect() as conn:
            return {"revision": review["revision"], "prepared": None,
                    **cand.alternatives(conn, tenant_id=tenant_id, review=review, item=item, kakao=kakao, chat=chat)}
    with connect() as conn:
        row = load(conn, tenant_id, intake_id, item)
        state, sides = usable(row, review, item)
        if state == "fresh":
            return {"revision": review["revision"], **row["body"], "prepared": _meta(row, [])}
    if is_preparing(intake_id, item):
        # ★`[2026-10-19 사용자 지시]` 접수 뒤 준비가 아직 끝나지 않았다 — 어림 카드(바깥 호출 없이 · 모든 줄 「계산 중」)를 먼저 보이고
        #   **같은 계산을 다시 돌리지 않고** 준비 결과를 기다려 이어 받는다. 준비가 저장하지 못했으면(카카오 · 실패) 아래 길로 계산한다
        with connect() as conn:
            preview = cand.gather(conn, tenant_id=tenant_id, review=review, item=item, kakao=None, now=datetime.now(KST), lodging_team=False)
            shown = cand.finish(conn, tenant_id=tenant_id, gathered=preview, judged=list(preview.pool), chat=None)
        for c in shown["candidates"]:
            c["pending"] = {**_pending(c, preview, None, chat), "reason": chat is not None}
        emit("candidates", {"revision": review["revision"], **shown, "prepared": None, "waiting": "prepare"})
        wait_preparing(intake_id, item)
        with connect() as conn:
            row = load(conn, tenant_id, intake_id, item)
            state, sides = usable(row, review, item)
            if state == "fresh":
                return {"revision": review["revision"], **row["body"], "prepared": _meta(row, [])}
    with connect() as conn:
        reused = reuse_row(row, state, item)
        if reused is not None:
            gathered = cand.regather(conn, tenant_id=tenant_id, review=review, item=item, places=_without_current(reused, item),
                                     notes=list(reused["notes"] or []))
        else:
            gathered = cand.gather(conn, tenant_id=tenant_id, review=review, item=item, kakao=kakao, now=datetime.now(KST), lodging_team=True)
        first = cand.finish(conn, tenant_id=tenant_id, gathered=gathered, judged=list(gathered.pool), chat=chat, reason_wait=0)
    stale = sides if state == "legs" else None
    shown = {_key(c["place"]): c["rank"] for c in first["candidates"]}
    kept = {_key(c["place"]): c for c in (row or {}).get("body", {}).get("candidates") or []} if state == "legs" else {}
    for c in first["candidates"]:
        c["pending"] = _pending(c, gathered, stale, chat)
        before = kept.get(_key(c["place"]))
        for side in ("before", "after"):
            # 앞뒤 일정만 바뀐 일정 — 바뀌지 않은 쪽 구간은 저장해 둔 실제 값을 그대로 보인다(「계산 중」은 바뀐 쪽만)
            if before and stale is not None and side not in stale and (before.get("legs") or {}).get(side):
                c.setdefault("legs", {})[side] = before["legs"][side]
                c["slack"] = {**(c.get("slack") or {}), side: (before.get("slack") or {}).get(side)}
    emit("candidates", {"revision": review["revision"], **first, "prepared": None})

    def done(_index: int, place: dict[str, Any], judged: dict[str, Any]) -> None:
        rank = shown.get(_key(cand._public(place)))
        if rank is None:
            return
        emit("candidate", {"rank": rank, "rows": judged["rows"], "fits": judged["fits"], "status": judged["status"],
                           "slack": judged["slack"], "estimated": judged["estimated"], "legs": judged.get("legs"),
                           "pending": {"before": False, "after": False}})

    first_keys = set(shown)
    first_index = [i for i, (place, _c) in enumerate(gathered.pool) if _key(cand._public(place)) in first_keys]
    judged = judge_in_turn(connect, tenant_id, gathered, first=first_index, on_done=done)
    with connect() as conn:
        final = cand.finish(conn, tenant_id=tenant_id, gathered=gathered, judged=judged, chat=chat, reason_wait=0)
    _wait_reasons(final, gathered, chat, tenant_id, emit, shown)
    body = {"revision": review["revision"], **final, "prepared": None}
    try:
        with connect() as conn:
            save(conn, tenant_id=tenant_id, intake_id=intake_id, item=item, revision=int(review["revision"]),
                 sigs=signatures(review, item), body=final, pool=_public_pool(gathered), notes=gathered.notes,
                 elapsed_ms=int((time.monotonic() - started) * 1000))
    except Exception:                                         # noqa: BLE001 — 저장 실패는 다음 「바꾸기」가 다시 계산하면 된다
        log.warning("intake alternatives store after stream failed", exc_info=True)
    return body


def _wait_reasons(final: dict[str, Any], gathered: cand.Gathered, chat: Any, tenant_id: str,
                  emit: Callable[[str, dict[str, Any]], None], shown: dict[tuple, int]) -> None:
    """틀 문장으로 나간 후보의 모델 문장이 저장되기를 `budget_seconds` 까지 기다리며, 저장되면 그 줄을 바꾸게 알린다(최종 결과에도 싣는다)."""
    from app.core.settings import get_guardrails
    from app.infrastructure.db.session import get_connection

    from . import reasons

    if chat is None or not get_guardrails().get("travel.candidate_reason.enabled"):
        return
    original = (gathered.current or {}).get("name")
    waiting = {id(c): (c, reasons.key_of(reasons.facts_for(c, original))) for c in final["candidates"][: int(reasons._cfg("visible"))]
               if c.get("reason_by") == "template" and len(reasons.facts_for(c, original)) > 1}
    deadline = time.monotonic() + float(reasons._cfg("budget_seconds"))
    while waiting and time.monotonic() < deadline:
        time.sleep(0.3)
        with get_connection() as conn:
            for ident, (c, sha) in list(waiting.items()):
                sentence = reasons._stored(conn, tenant_id, sha)
                if sentence is None:
                    continue
                c["reason"], c["reason_by"] = sentence, "model"
                rank = shown.get(_key(c["place"]))
                if rank is not None:
                    emit("candidate", {"rank": rank, "reason": sentence, "reason_by": "model", "pending": {"reason": False}})
                del waiting[ident]


# ── 등록 ───────────────────────────────────────────────────────────
#: 등록 때 일정 항목에 남기는 대안 수(채팅 「바꿔 줘」가 쓴다)
REGISTERED = 3


def with_alternates(conn, *, tenant_id: str, intake_id: Any, body: dict[str, Any], review: dict[str, Any] | None) -> dict[str, Any]:
    """`[2026-10-19 사용자 지시]` 등록 몸통의 일정 항목에 **미리 준비한 대안**을 남긴다 — `detail.alternates`(+ `other_options`).
    채팅 「바꿔 줘」(`trip_desk.swap_alternate`)가 그것을 그대로 쓴다. 저장분이 지금 판의 그 일정에 맞을 때만(`usable` 이 `none` 이 아님),
    판정이 `bad` 인 후보는 뺀다. 장소는 ①우리 장소 행(`ref: place:<id>` — 요식 원장 식당 등)은 그 행을 가리키고 ②관광공사 · 숙소 비교 값은
    몸통의 `places[]` 에 그 여행 전용 장소로 더한다(`place_key` — 등록이 장소 행 번호로 바꾼다). 원래 몸통은 바꾸지 않는다."""
    from copy import deepcopy

    from .assemble import _place_in

    if not review:
        return body
    out = deepcopy(body)
    by_key = {(str(x["source_id"]), int(x["index"])): x for x in review.get("items") or []}
    places = out.setdefault("places", [])
    for entry in out.get("items") or []:
        if entry.get("kind") == "mobility":
            continue          # ☆이동 항목은 출발 일정의 접수 표시(`detail.intake`)를 그대로 물려받는다(`registered_moves`) — 2026-10-20 x600 실서버에서 이동에 장소 대안이 붙었다
        ref = ((entry.get("detail") or {}).get("intake") or {})
        item = by_key.get((str(ref.get("source_id")), int(ref.get("index", -1))))
        if item is None:
            continue
        row = load(conn, tenant_id, intake_id, item)
        state, _sides = usable(row, review, item)
        if row is None:
            continue
        options = [c for c in row["body"].get("candidates") or [] if c.get("status") != "bad"]
        if state == "none":
            # 고객이 저장된 대안 중 하나를 골라 바꾼 일정 — 고른 곳을 뺀 **나머지 대안**이 그 자리의 「다른 안」이다(같은 시각 · 같은 자리)
            here = item.get("place")
            picked = [c for c in options if here and _key(c["place"])[:3] == _key({**here, "kind": None})[:3]]
            if not picked:
                continue
            options = [c for c in options if c not in picked]
        records = []
        for n, c in enumerate(options[:REGISTERED], start=1):
            place = c["place"]
            record: dict[str, Any] = {"name": place["name"], "starts_at": entry["starts_at"], "ends_at": entry.get("ends_at"),
                                      "walk_min": None, "option": None, "option_label": None}
            linked = str(place.get("ref") or "")
            if linked.startswith("place:"):
                record["place_id"] = record["key"] = linked[6:]
            else:
                key = f"alt-{entry['seq']}-{n}"
                kind = "activity" if place.get("kind") != "dining" else "dining"
                places.append(_place_in(key, {**place, "source": place.get("source") if place.get("source") in ("tour_api", "dining_ledger") else "customer_pick",
                                              "origin": place.get("source")}, kind))
                record["place_key"] = record["key"] = key
            if c.get("reason"):
                record["reason"] = c["reason"]
            warnings = [r["text"] for r in c.get("rows") or [] if r.get("result") == "warn" and r.get("text")]
            if warnings:
                record["warnings"] = warnings
            records.append(record)
        if records:
            entry["detail"] = {**(entry.get("detail") or {}), "alternates": records, "other_options": [r["name"] for r in records],
                               "alternates_from": "intake"}
    return out


def bind_alternate_places(detail: dict[str, Any], ids: dict[str, Any]) -> dict[str, Any]:
    """등록(`trip_api._insert`) — 대안의 `place_key` 를 넣은 장소 행 번호(`place_id`)로 바꾼다. 행을 못 넣은 대안은 뺀다."""
    alternates = detail.get("alternates")
    if not alternates or not any("place_key" in a for a in alternates):
        return detail
    bound = []
    for a in alternates:
        if "place_key" not in a:
            bound.append(a)
            continue
        place_id = ids.get(a["place_key"])
        if place_id is None:
            continue
        rest = {k: v for k, v in a.items() if k != "place_key"}
        bound.append({**rest, "place_id": str(place_id), "key": str(place_id)})
    return {**detail, "alternates": bound, "other_options": [a["name"] for a in bound]}


__all__ = ["bind_alternate_places", "needs_alternatives", "prepare", "prepare_later", "serve", "signatures", "stream", "usable",
           "with_alternates"]
