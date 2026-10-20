# -*- coding: utf-8 -*-
"""장소 정보 채우기 파이프라인 — 장소 이름 → 활동 원장 → (없으면) 카카오 실존 확인 → 웹 검색 → 주소를 좌표로 → 저장. `[2026-10-19 사용자 결정]`

    장소 이름(고객이 쓴 말)
      ├─ 활동 원장에 있다 ─────────────→ **비어 있는 칸만** 웹 검색(이미 채워진 칸은 패스)
      └─ 없다 → 카카오로 **실존만** 확인 ─→ 있으면 웹 검색(주소 · 운영시간 · 휴무 · 예약 …) → 주소를 브이월드로 좌표
    웹 값 · 좌표는 별도 표(`activity.ac_place_web_info`, 마이그레이션 307)에 출처 · 인용 · 만료와 함께 둔다.
    읽을 때 원장 값이 먼저, 비었을 때만 웹 값이다(`web_info.effective` · `ledger._merge_web`).

★**카카오가 준 값은 쓰지도 저장하지도 않는다** — 「있다/없다/못 물어봤다」만 쓴다(`place_lookup.lookup_place`). 웹 검색에는 **고객이 쓴 이름**만 보낸다.
★모르면 모른다 — 못 물어본 것(`unknown` · 웹 오류 · 시간 초과 · 예산 초과)을 「없다」로 읽지 않고 상태로 돌려준다. 웹 값은 **검증을 통과한 것만** 저장한다(`web_info.validate`).
★고객 응답을 기다리게 하지 않는다 — 웹 검색은 한 번에 15~40초 · 간혹 429 다. 일정 등록 때 **백그라운드로** 부르는 것이 전제다(부르는 쪽 몫).
★소개글 · 체험 안내는 다루지 않는다(남의 글 — 저장 안 함).
★이 파일은 IO 를 `PlaceIO`(DB) · `llm` · `geocoder` 로 받는다 — 시험은 가짜를 넣는다(실제 OpenAI · 카카오 · 브이월드 호출 없음).
"""
from __future__ import annotations

import logging
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from . import web_info
from .db_search import web_info_store
from .geocode import OK as GEO_OK
from .judge.llm import file_instructions, web_slots
from .judge.modes import BUDGET_METER_WEB, _run
from .place_aliases import key_of
from .place_lookup import lookup_place

_log = logging.getLogger("acop.activity.place_enrichment")

#: 결과 `status`
ENRICHED = "enriched"                  # 채웠다(저장함)
COMPLETE = "complete"                  # 채울 칸이 없다(원장 · 웹 값이 이미 있다)
NO_INFO = "no_info"                    # 웹 검색을 했지만 검증을 통과한 값이 없다
NOT_FOUND = "not_found"                # 원장에도 카카오에도 없다 — 웹 검색하지 않는다
AMBIGUOUS = "ambiguous"                # 원장에 같은 이름이 여럿 — 고르지 않는다(고객이 고른다)
UNKNOWN = "unknown"                    # 카카오를 못 물어봤다 — 「없다」가 아니다
BUDGET = "budget_exhausted"
BUSY = "busy"                          # 웹 검색 동시 호출 자리가 없다
WEB_TIMEOUT = "web_timeout"
WEB_ERROR = "web_error"
TABLE_MISSING = "table_missing"        # 마이그레이션 307 전 — 저장하지 못했다
WEB_OFF = "web_off"                    # 웹 검색이 꺼져 있다(`activity_judge_web_search`) — 검색한 출처가 없다. 「못 찾음」 표시를 남기지 않는다

_LEDGER_COLUMNS = tuple(dict.fromkeys(web_info.LEDGER_COLUMN.values()))


class PlaceIO:
    """DB 입출력 — 원장 찾기 · 원장 행 · 웹 정보 표. 시험은 같은 모양의 가짜를 넣는다."""

    def __init__(self, connection_factory: Callable[[], Any], tenant_id: str, kakao: Any | None) -> None:
        self._connect, self._tenant, self._kakao = connection_factory, tenant_id, kakao

    def lookup(self, name: str) -> dict[str, Any]:
        """`place_lookup.lookup_place` — 원장 먼저 → 없으면 카카오로 실존만."""
        return lookup_place(self._connect, self._tenant, name, self._kakao)

    def ledger_row(self, content_id: str) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT " + ", ".join(_LEDGER_COLUMNS) + " FROM activity.ac_place WHERE content_id = %s LIMIT 1", (content_id,))
            row = cur.fetchone()
        return dict(zip(_LEDGER_COLUMNS, row)) if row is not None else None

    def web_entries(self, place_key: str) -> dict[str, web_info.Entry]:
        with self._connect() as conn, conn.cursor() as cur:
            return web_info_store.read_entries(cur, [place_key]).get(place_key, {})

    def save(self, place_key: str, entries: list[web_info.Entry], *, model: str | None, now: datetime) -> bool:
        with self._connect() as conn, conn.transaction(), conn.cursor() as cur:
            return web_info_store.save_entries(cur, place_key, entries, model=model, now=now)


def _guardrail(name: str) -> Any:
    from app.core.settings import get_guardrails

    return get_guardrails().get(f"travel.activity_judge.{name}")


def _ask_web(llm: Any, name: str, address: str | None, wanted: list[str], *, run_id: Any, instructions: str | None,
             timeout: float, wait: float, concurrent: int, now: datetime) -> tuple[str, Any]:
    """웹 검색 한 번 — `(상태, 호출 결과)`. 상태는 `ok` 또는 실패 사유(`busy` · `web_timeout` · `web_error`)."""
    slots = web_slots(concurrent)
    if not slots.acquire(True, wait):
        return BUSY, None
    try:
        call = _run(llm.judge(web_info.PROMPT_KEY, web_info.payload(name, wanted, address=address, today=now.date()),
                              schema=web_info.schema(wanted), schema_name="activity_place_info", web_search=None,
                              instructions=instructions, run_id=run_id), timeout=timeout)
    except FuturesTimeout:
        return WEB_TIMEOUT, None
    except Exception as exc:  # noqa: BLE001 — 429 · 키 없음 · 프롬프트 미등록 — 종류만 남긴다
        _log.warning("place_info_web_failed %s", type(exc).__name__)
        return WEB_ERROR, type(exc).__name__
    finally:
        slots.release()
    return "ok", call


def enrich_place(name: str, io: PlaceIO, llm: Any, geocoder: Any, *, run_id: Any = None, now: datetime | None = None,
                 budget: Callable[[str], bool] | None = None, fields: tuple[str, ...] = web_info.FIELDS,
                 instructions: str | None = None, timeout: float | None = None, wait: float | None = None,
                 concurrent: int | None = None, max_age_days: int | None = None) -> dict[str, Any]:
    """장소 하나를 채운다. 항상 `status` 가 있는 dict — 위 상수 중 하나. 부르는 쪽(백그라운드)이 상태를 기록한다."""
    now = now or datetime.now(timezone.utc)
    name = (name or "").strip()
    if not key_of(name):
        return {"status": NOT_FOUND, "reason": "empty_name"}

    found = io.lookup(name)
    state = found.get("status")
    if state == "ambiguous":
        return {"status": AMBIGUOUS, "candidates": found.get("candidates")}
    if state == "unknown":
        return {"status": UNKNOWN, "reason": found.get("reason")}
    if state not in ("found", "exists_unregistered"):
        return {"status": NOT_FOUND}                                      # 원장에도 카카오에도 없다 — 웹 검색하지 않는다

    content_id = str(found["content_id"]) if state == "found" else None
    key = web_info.place_key(content_id, name)
    ledger = io.ledger_row(content_id) if content_id else None
    existing = io.web_entries(key)
    wanted = web_info.missing_fields(ledger, existing, now, wanted=fields)
    base = {"place_key": key, "in_ledger": content_id is not None}
    if not wanted:
        return {**base, "status": COMPLETE}

    if budget is not None and not budget(BUDGET_METER_WEB):
        return {**base, "status": BUDGET, "wanted": wanted}
    state, call = _ask_web(llm, name, (ledger or {}).get("addr1"), wanted, run_id=run_id,
                           instructions=instructions if instructions is not None else file_instructions(web_info.KIND),
                           timeout=timeout if timeout is not None else float(_guardrail("web_answer_timeout_seconds")),
                           wait=wait if wait is not None else float(_guardrail("web_wait_seconds")),
                           concurrent=concurrent if concurrent is not None else int(_guardrail("web_max_concurrent")), now=now)
    if state != "ok":
        return {**base, "status": state, "wanted": wanted, **({"error": call} if isinstance(call, str) else {})}

    sources = getattr(call, "sources", None) or []
    if not sources:
        # ★웹 검색이 꺼져 있거나 아무 페이지도 열지 않았다 — 「값을 못 찾았다」가 아니라 「검색하지 못했다」다. 표시를 남기면 7일 동안 다시 안 묻는다
        return {**base, "status": WEB_OFF, "wanted": wanted}
    entries, dropped = web_info.validate(
        getattr(call, "output", None), wanted=wanted, sources=sources, now=now,
        max_age_days=max_age_days if max_age_days is not None else int(_guardrail("citation_max_age_days")))
    coords = None
    geocode_status = None
    if content_id is None:
        entries.append(web_info.Entry("name", name, "customer", None, None, None, now + timedelta(days=web_info.TTL_DAYS["name"])))
        address = next((e.value for e in entries if e.field == "address"), None)
        if address:
            spot = geocoder.geocode(address)                              # 주소 → 좌표(브이월드). 카카오 좌표는 쓰지 않는다
            geocode_status = spot.status
            if spot.status == GEO_OK:
                coords = {"latitude": spot.latitude, "longitude": spot.longitude}
                entries.append(web_info.Entry("lat_lng", f"{spot.latitude},{spot.longitude}", "vworld", None, None, None,
                                              now + timedelta(days=web_info.TTL_DAYS["lat_lng"])))
    facts = [e for e in entries if e.field != "name"]
    # ★검색했는데 값을 못 얻은 칸은 「못 찾음」 표시를 남긴다 — 같은 칸을 매번 다시 검색해 돈이 나가지 않게(짧은 만료)
    markers = web_info.not_found_markers(wanted, [e.field for e in entries], now)
    to_save = [*(entries if facts else []), *markers]
    result = {**base, "wanted": wanted, "filled": [e.field for e in facts], "dropped": dropped, "not_found": [m.field for m in markers],
              "coords": coords, "geocode": geocode_status, "model": getattr(call, "model", None)}
    if to_save and not io.save(key, to_save, model=getattr(call, "model", None), now=now):
        return {**result, "status": TABLE_MISSING}
    return {**result, "status": ENRICHED if facts else NO_INFO}              # 검증을 통과한 값이 없으면 이름만 저장하지 않는다
