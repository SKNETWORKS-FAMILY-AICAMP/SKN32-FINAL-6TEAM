# -*- coding: utf-8 -*-
"""활동 장소가 **그 시각에 열었나** — 활동 원장(`activity.ac_place`)을 읽어 판정한다. `[2026-10-12]`

요식 팀의 `dining.ledger.state` 와 같은 모양이다. 코어가 끼움 자리(`team_hooks/activity_verdicts`, 코어 작업)에 이 함수를
꽂으면 계획 검증 · 감시가 고객 문의(`team._check_feasible`)와 **같은 판정**을 쓴다(activity.md D2-2).

    원장   운영시간 원문 · 휴무 원문 — 바뀌지 않는 사실(`scripts/activity/load_places.py` 가 CSV 에서 적재)
    판정   `verdicts.hours_verdict` — 방문 시각마다 계산한다(「둘째 주 월요일 휴무」는 날짜마다 답이 다르다)

★재난은 여기서 보지 않는다. 재난문자는 실시간 사실이라 원장에 없다 — 코어가 모은 문자를 `verdicts.disaster_verdict` 에 넘긴다.
★요일표는 **미리 펴 둔 것**(`ac_place.hours_week` — `scripts/activity/read_hours.py`, 규칙 · sLLM 한 번)을 읽는다.
  아직 안 펴 둔 행은 그 자리에서 규칙으로만 편다(`place_hours.read_by_rule`). 모델을 부르지 않는다 — 감시가 장소마다 부르는 함수라서다.
  못 편 운영시간은 「모름」이다. 휴무 원문은 그래도 휴무 규칙(`closure_rules`)이 읽는다.
★모르면 모른다: 원장에 없는 장소는 `None`. 「열었다」로 바꾸지 않는다.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

from app.domains.travel_ops.components.places.place_hours import read_by_rule

from . import web_info
from .db_search import web_info_store
from .verdicts import HolidayLookup, holidays_needed, hours_verdict

SOURCE = "activity.ac_place"
_log = logging.getLogger(__name__)

_PLACE_SQL = (
    "SELECT a.content_id, a.name_ko, a.usetime_text, a.restdate_text, a.hours_week, a.hours_read FROM places p "
    "JOIN activity.ac_place a ON a.content_id = COALESCE(p.source_content_id, p.attributes->>'source_content_id') "
    "WHERE p.tenant_id = %s AND p.place_id = %s LIMIT 1"
)
_ROW = ("content_id", "name_ko", "usetime_text", "restdate_text", "hours_week", "hours_read")


#: 웹 값이 채울 수 있는 원장 칸 — 운영시간 · 휴무만 판정에 쓴다(나머지 칸은 판정과 상관없다)
_WEB_COLUMNS = {"business_hours": "usetime_text", "closed_days": "restdate_text"}


def _web_entries(conn, key: str | None) -> dict[str, web_info.Entry]:
    """그 장소의 웹 정보 줄들(`activity.ac_place_web_info`). 표가 없거나 읽지 못하면 빈 dict — 원장만으로 판정하던 때와 같다."""
    if not key:
        return {}
    try:
        with conn.transaction(), conn.cursor() as cur:          # 세이브포인트 — 실패한 읽기가 부르는 쪽 트랜잭션을 막지 않게
            return web_info_store.read_entries(cur, [key]).get(key, {})
    except Exception as exc:  # noqa: BLE001 — 읽지 못한 웹 값은 없는 것으로 둔다(「열었다」로 바꾸지 않는다). 종류만 남긴다
        _log.warning("web_info_lookup_failed %s", type(exc).__name__)
        return {}


def _merge_web(conn, row: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """원장 행의 **비어 있는** 운영시간 · 휴무 칸을 웹 값(만료 전)으로 채운다. `[2026-10-19 사용자 결정]` 원장 값이 있으면 그대로다.

    채운 칸은 `web_info` 에 출처(URL · 인용 · 확인 시각)를 싣는다 — 고객 안내가 「웹에서 확인한 값」이라고 말할 수 있게.
    웹 값으로 채웠으면 미리 편 요일표(`hours_week`)는 그 원문이 아니라서 쓰지 않는다 — 규칙이 새 원문으로 다시 편다(`hours_from_row`).
    """
    entries = _web_entries(conn, web_info.place_key(row.get("content_id"), row.get("name_ko")))
    if not entries:
        return row
    now = now or datetime.now(timezone.utc)
    merged, used = dict(row), {}
    for field, column in _WEB_COLUMNS.items():
        value, source = web_info.effective(field, row.get(column), entries.get(field), now)
        if source == "web":
            entry = entries[field]
            merged[column] = value
            used[field] = {"value": value, "url": entry.url, "quote": entry.quote,
                           "checked": entry.expires_at.isoformat() if entry.expires_at else None}
    if used:
        merged["web_info"] = used
        merged["hours_week"], merged["hours_read"] = None, None
    return merged


def _off_ledger_row(conn, tenant_id: str, place_id: str) -> dict[str, Any] | None:
    """원장에 없는 장소(카카오로 실존만 확인해 일정에 들어온 곳) — 코어 장소 이름으로 웹 정보 줄을 찾아 행을 만든다. 웹 값이 없으면 `None`(모름)."""
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM places WHERE tenant_id = %s AND place_id = %s LIMIT 1", (tenant_id, str(place_id)))
        found = cur.fetchone()
    name = found[0] if found else None
    if not name:
        return None
    row = {"content_id": None, "name_ko": name, "usetime_text": None, "restdate_text": None, "hours_week": None, "hours_read": None}
    merged = _merge_web(conn, row)
    return merged if merged.get("web_info") else None


def place_row(conn, tenant_id: str, place_id: str | None) -> dict[str, Any] | None:
    """코어 장소 하나 → 원장 행(`_ROW` 칸). 연결이 없으면 `None`. `[2026-10-19]` 비어 있는 운영시간 · 휴무는 웹 값으로 채운다(`_merge_web`).
    원장에 없는 장소는 웹 정보 줄이 있을 때만 행을 만든다(`_off_ledger_row`)."""
    if place_id is None:
        return None
    with conn.cursor() as cur:
        cur.execute(_PLACE_SQL, (tenant_id, str(place_id)))
        row = cur.fetchone()
    if row is None:
        return _off_ledger_row(conn, tenant_id, str(place_id))
    return _merge_web(conn, dict(zip(_ROW, row)))


def hours_from_row(row: dict[str, Any]) -> dict[str, Any]:
    """원장 행 → `hours_verdict` 가 받는 모양(`read.place_hours` 와 같은 칸). 미리 편 요일표가 먼저, 없으면 규칙."""
    usetime, restdate = row.get("usetime_text"), row.get("restdate_text")
    week = row.get("hours_week") or {}
    if not week and row.get("hours_read") is None:      # 아직 안 펴 둔 행 — 규칙으로만
        ruled = read_by_rule(usetime, restdate)
        week = ruled.week if ruled is not None else {}
    why = None if week else ("원문이 비어 있다" if not (usetime or restdate) else "펴지 못한 운영시간 원문")
    return {"known": bool(week), "attributes": {"hours_week": week} if week else {}, "source": SOURCE,
            "hours_read": row.get("hours_read") if row.get("hours_week") else None,     # 모델이 읽었나(notices) — 저장된 표를 쓸 때만
            "why_unknown": why, "usetime_text": usetime, "restdate_text": restdate}


def indoor(conn, tenant_id: str, place_id: str | None) -> dict[str, Any] | None:
    """한 곳의 실내외 — 저장된 값(`activity.ac_indoor`, 우선순위 가장 높은 줄). `[2026-10-12]` D-CS-015 개정 2.

    반환 `{"outdoor": bool, "decided_by": "operator|customer|llm|class", "notice": str | None, "content_id"}` · 모르면 `None`.
    `notice` 는 모델이 정한 값일 때만 고객 답에 붙일 안내(`notices.INDOOR_AUTO`). 코어가 끼움 자리로 부른다(협의 메모 요청 3)."""
    from . import indoor_store
    from .notices import INDOOR_AUTO

    row = place_row(conn, tenant_id, place_id)
    if row is None or not row.get("content_id"):                # 원장 밖 장소(웹 정보만 있는 곳)는 실내외 줄이 없다
        return None
    found = indoor_store.read(conn, row["content_id"])
    if found is None:
        return None
    return {"outdoor": found["outdoor"], "decided_by": found["decided_by"], "content_id": row["content_id"],
            "notice": INDOOR_AUTO if found["decided_by"] == "llm" else None}


def state(conn, tenant_id: str, place_id: str | None, at: datetime | None, until: datetime | None = None, *,
          holiday: HolidayLookup | None = None) -> dict[str, Any] | None:
    """한 곳 · 한 시각의 휴무 · 운영시간 판정. 원장에 없거나 시각을 모르면 `None`(모름).

    `holiday` 는 날짜 → `read.holiday` 모양 · None. 부르는 쪽(코어)이 공휴일 소스를 넘긴다 — 휴무 원문이 공휴일 조건일 때만,
    필요한 날짜(`holidays_needed`)만 묻는다. 안 넘기면 공휴일 조건은 「모름」으로 남는다.
    `until` 은 일정이 끝나는 시각 — 주면 끝날 때까지 운영시간 안인지 본다(자정을 넘기면 밖). 안 주면 도착 순간만.
    반환은 `hours_verdict` 의 칸에 `content_id` · `name` 을 더한 것.
    """
    if not isinstance(at, datetime):
        return None
    from . import live_store

    return _with_live_status(_state_of_row(place_row(conn, tenant_id, place_id), at, until, holiday), at,
                             _in_savepoint(conn, lambda day: live_store.lookup(conn, tenant_id, place_id, day)))


def content_row(conn, content_id: str | None) -> dict[str, Any] | None:
    """관광공사 번호 → 원장 행(`_ROW` 칸). 없으면 `None`. `[2026-10-13 코어 연결]`"""
    if not content_id:
        return None
    with conn.cursor() as cur:
        cur.execute("SELECT " + ", ".join(_ROW) + " FROM activity.ac_place WHERE content_id = %s LIMIT 1",
                    (str(content_id),))
        row = cur.fetchone()
    return _merge_web(conn, dict(zip(_ROW, row))) if row is not None else None


def state_by_content(conn, content_id: str | None, at: datetime | None, until: datetime | None = None, *,
                     holiday: HolidayLookup | None = None) -> dict[str, Any] | None:
    """`state` 와 같은 판정을 관광공사 번호로 — 코어 장소 행을 만들기 전(확인 화면 단계)에 쓴다. `[2026-10-13 코어 연결]`

    ★코어가 확인 화면에서 읽은 장소는 관광공사 번호만 있고 장소 행(`places`)이 없을 때가 많다. 그때 `state` 는 원장을 못 찾는다."""
    if not isinstance(at, datetime):
        return None
    # ★`[2026-10-15]` ST4F-573 — 이 길(확인 화면이 장소 행 없이 번호만 가진 때)에도 `live_status` 칸을 싣는다. 전에는 `state` 에만 있어
    #   확인 화면이 `core_id` 없이 부르면 칸이 비어 있었다. 저장소는 같고 키만 관광공사 번호다(`live_store.read`).
    from . import live_store

    return _with_live_status(_state_of_row(content_row(conn, content_id), at, until, holiday), at,
                             _in_savepoint(conn, lambda day: live_store.read(conn, content_id, day)))


def _in_savepoint(conn, read: Callable[[Any], dict[str, Any] | None]) -> Callable[[Any], dict[str, Any] | None]:
    """실시간 운영 상태 읽기를 **세이브포인트 안에서** 한다. `[2026-10-16]`

    ★`_live_status` 는 읽기 실패를 잡아 「모름」으로 싣는다. 그런데 PostgreSQL 은 실패한 문장 뒤 트랜잭션 전체를 막아서(aborted),
      예외만 잡으면 **같은 연결의 다음 쿼리가 모두** `InFailedSqlTransaction` 으로 깨졌다 — 로컬 DB 에 마이그레이션 304
      (`activity.ac_live_status`)가 빠져 있을 때 확인 화면이 원장에 있는 장소마다 이렇게 멈췄다(2026-10-16 확인).
      세이브포인트로 감싸면 실패한 읽기만 되돌리고 부르는 쪽의 트랜잭션은 살아 있다. 예외는 그대로 올려 `_live_status` 가 기록한다."""
    def guarded(day: Any) -> dict[str, Any] | None:
        with conn.transaction():
            return read(day)

    return guarded


def _state_of_row(row: dict[str, Any] | None, at: datetime, until: datetime | None,
                  holiday: HolidayLookup | None) -> dict[str, Any] | None:
    if row is None:
        return None
    hours = hours_from_row(row)
    facts: dict[Any, Any] = {}
    if holiday is not None:
        for day in holidays_needed(hours["restdate_text"], at):
            facts[day] = holiday(day)
            if facts[day] is None:
                break      # ★같은 소스가 또 모른다고 할 것이다(team._hours_check 와 같다)
    verdict = hours_verdict(hours, at, until=until if isinstance(until, datetime) else None, holiday=facts.get)
    out = {**verdict, "content_id": row["content_id"], "name": row["name_ko"]}
    if row.get("web_info"):
        out["web_info"] = row["web_info"]            # 어느 칸을 웹 값으로 채웠나(출처 · 인용) — 고객 안내가 쓴다
    return out


def _with_live_status(out: dict[str, Any] | None, at: datetime,
                      read: Callable[[Any], dict[str, Any] | None]) -> dict[str, Any] | None:
    """저장된 실시간 운영 상태를 `live_status` 칸으로 싣는다. 원장에 없어 판정이 `None` 이면 그대로 `None`."""
    if out is None:
        return None
    live = _live_status(at, read)
    if live is not None:
        out["live_status"] = live
        # ★`llm` 일 때만 판정에 반영한다 — 인용이 있는 「닫혔다」만 저장돼 있다(`live_store.record`). 「열었다」는 풀어 주지 않는다.
        #   `shadow` 에서는 판정을 그대로 두고 칸만 싣는다(코어 회신 9번 — 정확도를 재기 전에는 고객 결과를 바꾸지 않는다).
        if live.get("applied") and live.get("value") == "closed" and out.get("closed") is not True:
            quote = next((c.get("quote") for c in live.get("citations") or [] if c.get("quote")), None)
            out.update({"closed": True, "closure_reason": "live_status", "quote": quote})
    return out


def _live_status(at: datetime, read: Callable[[Any], dict[str, Any] | None]) -> dict[str, Any] | None:
    """저장된 실시간 운영 상태(`activity.ac_live_status`) — 별도 칸. `[2026-10-14]` 코어 회신(10-13) 「확인 화면 · 감시도 보게」.

    ★`rule`(꺼짐)이면 `None` — 칸이 없다. 켜져 있는데 못 읽으면 숨기지 않고 `unknown`(+ 이유)으로 싣는다(조용한 대체 금지).
    ★줄이 없으면 `unchecked`(아직 안 봤다) — 「열었다」가 아니다. 값은 `open` · `closed` · `unknown` · `unchecked`.
    """
    from .judge.modes import kind_mode
    from .judge.requests import KST
    from .judge.types import LIVE_STATUS
    from . import live_store

    mode = kind_mode(LIVE_STATUS)
    if mode == "rule":
        return None
    day = at.astimezone(KST).date() if at.tzinfo else at.date()
    try:
        stored = read(day)
    except Exception as exc:  # noqa: BLE001 — 읽지 못한 것을 「열었다」로 보지 않는다. 종류만 남기고 모름
        _log.warning("live_status_ledger_lookup_failed %s", type(exc).__name__)
        return {"value": "unknown", "mode": mode, "applied": False, "why": f"lookup_failed:{type(exc).__name__}",
                "visit_date": day.isoformat()}
    if stored is None or stored.get("value") not in live_store.VALUES:
        return {"value": "unchecked", "mode": mode, "applied": False, "visit_date": day.isoformat()}
    checked = stored.get("checked_at")
    citations = [{"url": c.get("url"), "quote": c.get("quote"), "published_at": c.get("published_at")}
                 for c in stored.get("citations") or [] if isinstance(c, dict)]
    return {"value": stored["value"], "mode": mode, "applied": mode == "llm", "visit_date": day.isoformat(),
            "checked_at": checked.isoformat() if hasattr(checked, "isoformat") else checked, "citations": citations}
