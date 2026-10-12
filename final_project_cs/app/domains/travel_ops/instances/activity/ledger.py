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

from datetime import datetime
from typing import Any

from app.domains.travel_ops.components.places.place_hours import read_by_rule

from .verdicts import HolidayLookup, holidays_needed, hours_verdict

SOURCE = "activity.ac_place"

_PLACE_SQL = (
    "SELECT a.content_id, a.name_ko, a.usetime_text, a.restdate_text, a.hours_week, a.hours_read FROM places p "
    "JOIN activity.ac_place a ON a.content_id = COALESCE(p.source_content_id, p.attributes->>'source_content_id') "
    "WHERE p.tenant_id = %s AND p.place_id = %s LIMIT 1"
)
_ROW = ("content_id", "name_ko", "usetime_text", "restdate_text", "hours_week", "hours_read")


def place_row(conn, tenant_id: str, place_id: str | None) -> dict[str, Any] | None:
    """코어 장소 하나 → 원장 행(`_ROW` 칸). 연결이 없으면 `None`."""
    if place_id is None:
        return None
    with conn.cursor() as cur:
        cur.execute(_PLACE_SQL, (tenant_id, str(place_id)))
        row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(_ROW, row))


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
    row = place_row(conn, tenant_id, place_id)
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
    return {**verdict, "content_id": row["content_id"], "name": row["name_ko"]}
