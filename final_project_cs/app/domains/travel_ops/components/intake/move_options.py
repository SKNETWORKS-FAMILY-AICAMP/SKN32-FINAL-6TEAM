# -*- coding: utf-8 -*-
"""이동수단 고르기 — 구간 하나의 **수단별 후보**(읽기) · **고른 수단 반영**(쓰기). `[2026-10-07 사용자 결정 — 이동 세션 착수]`

계약은 `wiki/records/plans/2026-10-05_이동수단_선택_서버계약안.md` 그대로다.

읽기(`options`): 그 구간을 지하철 · 버스 · 택시 · 걸음 **수단마다 한 번씩** 이동 계산기로 계산한다(`modes=[수단]`). 못 만든 수단(그 구간에 노선이 없거나 걸을 거리가 아님)은 줄이 없고,
  시간 안에 못 끝낸 수단은 `fits: null` + 이유다 — 지어낸 값이 없다. 네 수단을 **동시에** 돌리고 수단마다 상한을 둔다(가장 느린 것이 전체 시간).
쓰기(`choose`): 고른 수단으로 그 구간을 **다시 계산해 닿는지 확인한 뒤에만** 받는다 — 화면이 보낸 `fits` 를 믿지 않는다. 저장은 고객의 값(`moves[{from}~{to}].mode` 값 줄)으로
  새 판(revision+1)에 남는다 — 장소·시간 고치기와 같은 방식이라 앞 판의 근거를 지우지 않는다. `recommended` 는 되돌리기(값을 비운다).
  고른 값이 있는 구간은 앞뒤 일정이 바뀌어도 같은 방식으로 다시 시도한다(`review.build`): 닿으면 유지(`kept`) · 안 닿으면 추천으로 복귀(`dropped` + 이유).
경로 후보 `[2026-10-23 사용자 지시 — 먼저 3개 · 목록을 내리면 더]`: 검사(`moves[].routes`)가 구간마다 경로 후보 앞의 3개를 이미 싣는다(같은 계산 · 지연 없음).
  `routes` 읽기는 그 뒤를 준다 — 후보 상한을 넓힌 계산기(`wide`)로 그 구간을 한 번 더 세고, 검사가 이미 보인 후보는 빼고 `offset` · `limit` 만큼.
  `choose_route` 쓰기는 고른 경로를 그 구간에서 다시 세어 닿을 때만 받는다(`moves[{from}~{to}].route` 값 줄 · 고른 수단 값은 비운다).
"""
from __future__ import annotations

from app.core.team_availability import TeamUnavailable

import json
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime
from typing import Any, Callable
from uuid import UUID

from . import review as review_module
from .moves import ROUTES_FIRST, Leg, leg_between
from .review import MOVE_LABEL, MOVE_MODES, _dt, _hm, mode_fits, why_not

#: 「더 보기」 한 번에 주는 경로 후보 수(기본) · 최대 — 화면이 `limit` 로 고른다
ROUTES_PAGE = 5
ROUTES_PAGE_MAX = 20
#: 넓게 찾기 계산 하나의 기다림 상한(초) — 넓게 찾기는 보통 계산보다 0.3~0.6초 더 걸렸다(2026-10-23 이 PC 실측, 기록 문서). 넘으면 「확인 못 함」

#: 수단 하나의 계산에 기다리는 시간 상한(초) — 못 닿는 구간은 3~11초 걸린다(2026-10-03 실측). 넘으면 그 줄만 「확인 못 함」. ★우리가 고른 값(실서버 재서 다시 정한다 `[미실측]`)
OPTION_TIMEOUT_S = 14.0
ROUTES_TIMEOUT_S = 14.0
SLOW_TEXT = "계산이 오래 걸려 확인하지 못했어요"


class NotAvailable(LookupError):
    """이 구간은 수단 후보를 계산할 대상이 아니다(이동 계산기가 꺼짐 · 구간이 없음 · 장소·시각을 모름) — 화면은 고르기 박스를 두지 않는다(404 `not_available`)."""


class ModeNotFit(ValueError):
    """고른 수단이 안 닿는다 · 계산하지 못했다 · 알 수 없는 수단 — 422 `mode_not_fit`. `why` 는 서버가 완성한 문장."""

    def __init__(self, why: str) -> None:
        super().__init__(why)
        self.why = why


def _find(found: dict[str, Any], from_id: str, to_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    move = next((m for m in found.get("moves") or [] if m.get("from") == from_id and m.get("to") == to_id), None)
    items = {it.get("id"): it for it in found.get("items") or []}
    a, b = items.get(from_id), items.get(to_id)
    if move is None or a is None or b is None:
        raise NotAvailable("구간이 없다")
    return move, a, b


def _inputs(a: dict[str, Any], b: dict[str, Any], move: dict[str, Any]):
    """(출발 장소, 도착 장소, 앞 일정 끝, 다음 일정 시작, 다음 일정 시각 글자) — `review.build` 가 이동을 계산할 때와 같은 값."""
    if move.get("status") == "waiting" or not a.get("place") or not b.get("place"):
        raise NotAvailable("장소가 정해지지 않았다")
    a_end, b_start = _dt(a.get("date"), a.get("ends_at") or a.get("starts_at")), _dt(b.get("date"), b.get("starts_at"))
    if a_end is None or b_start is None or a.get("date") != b.get("date"):
        raise NotAvailable("시각을 모른다")
    try:
        pa = {"key": a["id"], "name": a["place"]["name"], "lat": float(a["place"]["latitude"]), "lon": float(a["place"]["longitude"])}
        pb = {"key": b["id"], "name": b["place"]["name"], "lat": float(b["place"]["latitude"]), "lon": float(b["place"]["longitude"])}
    except (KeyError, TypeError, ValueError):
        raise NotAvailable("좌표를 모른다") from None
    return pa, pb, a_end, b_start, str(b.get("starts_at") or "")


def _row(mode: str, leg: Leg, b_hhmm: str) -> dict[str, Any]:
    fits = mode_fits(leg)
    label = leg.mode_label
    estimate_grade = mode in ("taxi", "walk") or "선로 길이 추정" in str(leg.route) or not leg.verified
    row: dict[str, Any] = {
        "mode": mode, "label": label, "minutes": leg.minutes, "km": leg.km,
        "fare_krw": 0 if mode == "walk" else leg.fare_krw, "fare_is_floor": False,
        "fare_is_estimate": mode == "taxi",
        "depart": _hm(leg.depart), "arrive": _hm(leg.arrive), "slack_min": leg.slack_min, "fits": fits,
        "basis": "timetable" if mode in ("subway", "bus") else "estimate", "grade": "추정" if estimate_grade else "확정"}
    if not fits:
        row["why_not"] = why_not(MOVE_LABEL.get(mode, mode), leg, b_hhmm)
    return row


def _one(mode: str, engine: Any, pa: dict[str, Any], pb: dict[str, Any], a_end: datetime, b_start: datetime, b_hhmm: str):
    """수단 하나 → 줄(dict) · None(못 만든 수단) · 오류면 예외."""
    if engine is None:
        return None
    leg = leg_between(engine, pa, pb, a_end, b_start)
    if leg.basis == "estimate":
        # 계산기가 이 수단으로는 후보를 못 냈다 — 오류(예외를 삼킨 어림)면 「계산 못 함」, 아니면 그 수단은 이 구간에 없다
        if str(leg.why or "").startswith("이동 계산기 오류"):
            raise RuntimeError(leg.why)
        return None
    if leg.mode != mode:
        return None
    return _row(mode, leg, b_hhmm)


def options(found: dict[str, Any], from_id: str, to_id: str, *,
            engine_for_mode: Callable[[str], Any] | None = None, timeout_s: float = OPTION_TIMEOUT_S,
            only: str | None = None, party_size: int | None = None) -> dict[str, Any]:
    """구간 `from_id`~`to_id` 의 수단별 후보. `found` = 그 판의 저장된 검사. 줄 순서는 지하철 · 버스 · 택시 · 걸음 고정."""
    move, a, b = _find(found, from_id, to_id)
    pa, pb, a_end, b_start, b_hhmm = _inputs(a, b, move)
    modes = (only,) if only else MOVE_MODES
    if engine_for_mode is None:
        engine_for_mode = _default_factory(party_size, found.get("taxi_pricing"))
    if engine_for_mode is None:
        raise NotAvailable("이동 계산기가 꺼져 있다")
    engines = {m: engine_for_mode(m) for m in modes}
    if all(e is None for e in engines.values()):
        raise NotAvailable("이동 계산기가 꺼져 있다")
    pool = ThreadPoolExecutor(max_workers=len(modes), thread_name_prefix="move-options")
    futures = {m: pool.submit(_one, m, engines[m], pa, pb, a_end, b_start, b_hhmm) for m in modes}
    wait(list(futures.values()), timeout=timeout_s)
    pool.shutdown(wait=False)                               # 못 끝낸 계산은 뒤에서 끝나게 둔다(끊을 수 없다) — 이 응답은 기다리지 않는다
    rows: list[dict[str, Any]] = []
    for m in modes:
        f = futures[m]
        if not f.done():
            rows.append({"mode": m, "label": MOVE_LABEL.get(m, m), "fits": None, "why_not": SLOW_TEXT})
            continue
        try:
            row = f.result()
        except TeamUnavailable:
            raise
        except Exception:                                   # noqa: BLE001 — 한 수단의 오류가 다른 수단을 막지 않는다
            rows.append({"mode": m, "label": MOVE_LABEL.get(m, m), "fits": None, "why_not": SLOW_TEXT})
            continue
        if row is not None:
            rows.append(row)
    current = move.get("mode")
    return {"revision": found.get("revision"), "from": from_id, "to": to_id, "current_mode": current,
            "recommended_mode": move.get("recommended_mode") or current, "options": rows}


def _wide_engine(party_size: int | None, pricing=None) -> Any:
    """후보 상한을 넓힌 기본 계산기(`review.default_engine(wide=True)`). 이동 팀이 없으면 None."""
    from .review import default_engine
    from .taxi_pricing import constraints, default
    selected = constraints(pricing)
    if pricing == default():
        selected = {}
    return default_engine(party_size, constraints=selected, wide=True) if selected else default_engine(party_size, wide=True)


def _route_leg(found: dict[str, Any], from_id: str, to_id: str, engine: Any, *, prefer: str | None = None,
               timeout_s: float = ROUTES_TIMEOUT_S) -> tuple[dict[str, Any], Leg | None]:
    """(구간 검사 줄, 넓게 센 구간 또는 None = 시간 안에 못 셈). 아침 구간(숙소 → 그날 첫 일정)은 검사와 같은 아침 시각부터 센다."""
    move, a, b = _find(found, from_id, to_id)
    pa, pb, a_end, b_start, _ = _inputs(a, b, move)
    if move.get("from_stay"):
        from .review import STAY_MORNING_FROM
        a_end = _dt(b.get("date"), STAY_MORNING_FROM) or a_end
    if engine is None:
        raise NotAvailable("이동 계산기가 꺼져 있다")
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="move-routes")
    future = pool.submit(leg_between, engine, pa, pb, a_end, b_start, prefer=prefer)
    wait([future], timeout=timeout_s)
    pool.shutdown(wait=False)
    if not future.done():
        return move, None
    leg = future.result()                                   # TeamUnavailable · 계산 오류는 위로(어림값은 Leg 로 온다)
    return move, leg


def routes(found: dict[str, Any], from_id: str, to_id: str, *, offset: int = ROUTES_FIRST, limit: int = ROUTES_PAGE,
           engine: Any = None, party_size: int | None = None, timeout_s: float = ROUTES_TIMEOUT_S) -> dict[str, Any]:
    """구간의 경로 후보 **다음 쪽** — 검사가 이미 보인 후보(`moves[].routes`) 다음부터. 줄 모양은 검사의 `routes[]` 와 같다.
    `offset` = 화면이 이미 보인 후보 수(검사의 3개 + 앞서 받은 것), `limit` = 이번에 받을 수. 다음이 없으면 `has_more: false`."""
    if engine is None:
        engine = _wide_engine(party_size, found.get("taxi_pricing"))
    move, leg = _route_leg(found, from_id, to_id, engine, timeout_s=timeout_s)
    shown = [r for r in move.get("routes") or [] if isinstance(r, dict)]
    head = {"revision": found.get("revision"), "from": from_id, "to": to_id, "route_key": move.get("route_key")}
    if leg is None:
        return {**head, "routes": [], "offset": offset, "next_offset": offset, "has_more": True, "total": None, "why": SLOW_TEXT}
    if leg.basis != "timetable":
        return {**head, "routes": [], "offset": offset, "next_offset": offset, "has_more": False, "total": len(shown),
                "why": "이 구간은 시간표로 경로를 찾지 못했어요"}
    seen = {r.get("key") for r in shown}
    rest = shown + [dict(r) for r in leg.routes if r.get("key") not in seen]
    offset = max(int(offset), 0)
    limit = min(max(int(limit), 1), ROUTES_PAGE_MAX)
    page = rest[offset:offset + limit]
    return {**head, "routes": page, "offset": offset, "next_offset": offset + len(page),
            "has_more": offset + len(page) < len(rest), "total": len(rest)}


def _default_factory(party_size: int | None, pricing=None) -> Callable[[str], Any] | None:
    """기본 계산기 팩토리. 이동 팀이 없으면 None."""
    from .review import default_engine
    from .taxi_pricing import constraints, default
    selected = constraints(pricing)
    if pricing == default():
        selected = {}  # 같은 일반호출 기본값은 옛 수단 계산기 시그니처도 유지한다.
    if (default_engine(party_size, constraints=selected) if selected else default_engine(party_size)) is None:
        return None
    if selected:
        return lambda mode: default_engine(party_size, [mode], constraints=selected)
    return lambda mode: default_engine(party_size, [mode])


def party_size_of(conn, *, tenant_id: str, intake_id: UUID, revision: int) -> int | None:
    """그 판의 일행 수(`trip.party_size` 값 줄) — 검사를 만들 때와 같은 일행으로 계산하려고 읽는다. 모르면 None."""
    from . import pipeline
    from .assemble import collect

    got = collect(sources=pipeline._sources(conn, tenant_id, intake_id),
                  claims=pipeline.effective(pipeline._claims(conn, tenant_id, intake_id, revision)))
    try:
        value = (got.trip.get("party_size") or {}).get("value")
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def read_routes(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID, revision: int | None, from_id: str, to_id: str,
                offset: int = ROUTES_FIRST, limit: int = ROUTES_PAGE, engine: Any = None) -> dict[str, Any]:
    """경로 후보 더 보기 입구 — 남의 접수 `LookupError` · 낡은 판 `IntakeConflict` · 구간 없음 `NotAvailable`."""
    from . import pipeline

    _, found = pipeline.current_review(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=revision)
    party = party_size_of(conn, tenant_id=tenant_id, intake_id=intake_id, revision=found["revision"])
    return routes(found, from_id, to_id, offset=offset, limit=limit, engine=engine, party_size=party)


def choose_route(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID, revision: int, from_id: str, to_id: str,
                 key: str, engine: Any = None) -> dict[str, Any]:
    """고른 경로를 반영한다 → `{"revision": 새 판, "review": 검사 전체(public)}`. `key` = 경로 열쇠(`routes[].key`) · `"recommended"` = 되돌리기.
    그 구간을 넓게 다시 세어 **그 경로가 있고 다음 일정 안에 닿을 때만** 받는다(화면이 보낸 값을 믿지 않는다) — 안 닿으면 `ModeNotFit`(422).
    저장은 `moves[{from}~{to}].route` 와 함께 고른 수단 값(`.mode`)을 비운다 — 경로가 수단을 정한다."""
    from . import pipeline

    if not isinstance(key, str) or not key.strip():
        raise ModeNotFit("알 수 없는 경로예요")
    _, found = pipeline.current_review(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=revision)
    _find(found, from_id, to_id)
    pair = f"moves[{from_id}~{to_id}]"
    if key == "recommended":
        fields = [(f"{pair}.route", None)]
    else:
        if engine is None:
            party = party_size_of(conn, tenant_id=tenant_id, intake_id=intake_id, revision=found["revision"])
            engine = _wide_engine(party, found.get("taxi_pricing"))
        _, leg = _route_leg(found, from_id, to_id, engine, prefer=key)
        if leg is None:
            raise ModeNotFit(SLOW_TEXT)
        if leg.route_key != key:
            raise ModeNotFit("고른 경로를 지금 시각으로는 찾지 못했어요 · 목록을 다시 불러와 주세요")
        if not mode_fits(leg):
            b = next((it for it in found.get("items") or [] if it.get("id") == to_id), {})
            raise ModeNotFit(why_not("고른 경로", leg, str(b.get("starts_at") or "")))
        fields = [(f"{pair}.route", key), (f"{pair}.mode", None)]
    new = _store(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=revision, fields=fields)
    _, found2 = pipeline.current_review(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=new)
    return {"revision": new, "review": review_module.public(found2, tenant_id=tenant_id)}


def read(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID, revision: int | None, from_id: str, to_id: str,
         engine_for_mode: Callable[[str], Any] | None = None) -> dict[str, Any]:
    """읽기 입구 — 남의 접수 `LookupError` · 낡은 판 `IntakeConflict` · 구간 없음 `NotAvailable`."""
    from . import pipeline

    _, found = pipeline.current_review(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=revision)
    party = party_size_of(conn, tenant_id=tenant_id, intake_id=intake_id, revision=found["revision"])
    return options(found, from_id, to_id, engine_for_mode=engine_for_mode, party_size=party)


def choose(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID, revision: int, from_id: str, to_id: str,
           mode: str, engine_for_mode: Callable[[str], Any] | None = None) -> dict[str, Any]:
    """고른 수단을 반영한다 → `{"revision": 새 판, "review": 검사 전체(public)}`.
    남의 접수 `LookupError` · 구간 없음 `NotAvailable` · 낡은 판 `IntakeConflict` · 안 닿는 수단 `ModeNotFit`."""
    from . import pipeline

    if mode != "recommended" and mode not in MOVE_MODES:
        raise ModeNotFit("알 수 없는 수단이에요")
    _, found = pipeline.current_review(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=revision)
    _find(found, from_id, to_id)                               # 없는 구간이면 NotAvailable
    if mode != "recommended":
        party = party_size_of(conn, tenant_id=tenant_id, intake_id=intake_id, revision=found["revision"])
        got = options(found, from_id, to_id, engine_for_mode=engine_for_mode, only=mode, party_size=party)
        row = next((r for r in got["options"] if r["mode"] == mode), None)
        if row is None:
            raise ModeNotFit(f"{review_module.ro(MOVE_LABEL.get(mode, mode))}는 이 구간을 갈 수 없어요")
        if row.get("fits") is not True:
            raise ModeNotFit(str(row.get("why_not") or "닿지 않는 수단이에요"))
    # `[2026-10-23]` 수단을 새로 고르면(되돌리기 포함) 앞서 고른 경로는 비운다 — 경로가 수단보다 앞서므로 남기면 고른 수단이 안 먹는다
    new = _store(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=revision,
                 fields=[(f"moves[{from_id}~{to_id}].mode", None if mode == "recommended" else mode),
                         *([(f"moves[{from_id}~{to_id}].route", None)] if _has_route(found, from_id, to_id) else [])])
    _, found2 = pipeline.current_review(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=new)
    return {"revision": new, "review": review_module.public(found2, tenant_id=tenant_id)}


def _has_route(found: dict[str, Any], from_id: str, to_id: str) -> bool:
    move = next((m for m in found.get("moves") or [] if m.get("from") == from_id and m.get("to") == to_id), None)
    return bool(move and move.get("route_choice"))


def _store(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID, revision: int, field: str | None = None, value: Any = None,
           fields: list[tuple[str, Any]] | None = None) -> int:
    """고객의 값 줄(하나 · `fields` 면 여럿)을 얹은 **새 판**을 만든다(`pipeline.edit` 와 같은 방식 — 앞 판을 그대로 옮기고 고친 값을 뒤에 얹는다). 새 판의 검사도 바로 계산한다."""
    from . import pipeline

    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT status, revision FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s AND customer_id=%s FOR UPDATE",
                    (tenant_id, intake_id, customer_id))
        row = cur.fetchone()
        if row is None:
            raise LookupError("intake")
        status, current = row
        if status != "review":
            raise pipeline.IntakeConflict("intake_not_editable", f"지금은 고칠 수 없습니다(상태 {status})", status=status)
        if revision != current:
            raise pipeline.IntakeConflict("stale_revision", "그 사이 다른 화면에서 고쳤습니다 — 새로 불러와 주세요", current_revision=current)
        new = current + 1
        cur.execute("INSERT INTO intake_claims (intake_id, tenant_id, revision, source_id, field, value_json, method, "
                    "evidence, needs_review, note, created_at) SELECT intake_id, tenant_id, %s, source_id, field, "
                    "value_json, method, evidence, needs_review, note, created_at FROM intake_claims "
                    "WHERE tenant_id=%s AND intake_id=%s AND revision=%s", (new, tenant_id, intake_id, current))
        for name, val in (fields if fields is not None else [(field, value)]):
            cur.execute("INSERT INTO intake_claims (intake_id, tenant_id, revision, source_id, field, value_json, method, "
                        "evidence, needs_review, note, created_at) VALUES (%s,%s,%s,NULL,%s,%s,'customer',%s,false,NULL, clock_timestamp())",
                        (intake_id, tenant_id, new, name, json.dumps(val, ensure_ascii=False),
                         json.dumps({"via": "move_options"}, ensure_ascii=False)))
        cur.execute("UPDATE trip_intakes SET revision=%s, updated_at=now() WHERE tenant_id=%s AND intake_id=%s",
                    (new, tenant_id, intake_id))
    pipeline._review_of(conn, tenant_id, intake_id, new, pipeline._sources(conn, tenant_id, intake_id),
                        pipeline.effective(pipeline._claims(conn, tenant_id, intake_id, new)), force=True)
    return new


__all__ = ["ModeNotFit", "NotAvailable", "OPTION_TIMEOUT_S", "ROUTES_PAGE", "choose", "choose_route", "options", "party_size_of", "read",
           "read_routes", "routes"]
