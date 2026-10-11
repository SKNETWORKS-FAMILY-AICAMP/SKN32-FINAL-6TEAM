# -*- coding: utf-8 -*-
"""활동 성립 판정의 휴무 · 운영시간 — `[2026-10-09]` role-activity 판의 정기휴무 규칙을 develop 설계 위로 옮겼다.

데이터는 DB 에 읽어 둔 값(`read.place_hours` — 새벽 작업 `catalog_hours`)만 본다. 요일 칸은 develop 표준 함수
(`place_hours.hours_on` · `fits`)가, 요일표가 펴지 못하는 휴무(매월 n번째 주 · 공휴일 조건)는 휴무 원문을
휴무 규칙(`closure_rules.read_closure`)이 읽는다. 휴무 · 운영시간 밖이면 공유 점검의 이상과 같은 변경 제안 길로 간다.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.core.contracts import NextAction
from app.domains.travel_ops.instances.activity import ActivityTeam
from app.domains.travel_ops.instances.activity import failure_codes as fc

from ..helpers import FakeTools, pack, task

ALLOWED = ActivityTeam.manifest.allowed_tools
KST = timezone(timedelta(hours=9))
#: 2026-11-10 화요일 14:00 — 11월의 둘째 화요일
SECOND_TUESDAY = datetime(2026, 11, 10, 14, 0, tzinfo=KST)
CLEAR = {"verdict": "clear", "disruptions": [], "advisories": [], "checks": [], "failed_categories": [],
         "not_connected": []}
OPEN_WEEK = {day: {"open": "09:00", "close": "18:00", "last_entry": "17:00"}
             for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}


def _hours(week=OPEN_WEEK, restdate=None, known=True):
    return {"known": known, "attributes": {"hours_week": week} if week else {}, "source": "tour_api",
            "why_unknown": None if known else "관광공사 운영시간을 아직 읽지 못했어요", "conditions": [],
            "usetime_text": "09:00~18:00", "restdate_text": restdate}


def _run(hours, *, starts_at=SECOND_TUESDAY, holiday=None):
    values = {"read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": starts_at,
                               "party_size": 2, "capacity": 4},
              "read.policy": [],
              "read.place": {"place_id": "p1", "weather_sensitive": False, "latitude": 37.5, "longitude": 127.0},
              "read.disruptions": CLEAR,
              "read.place_hours": hours,
              "read.holiday": holiday}
    tools = FakeTools(values)
    context = pack("activity", scope=["activity"])
    result = asyncio.run(ActivityTeam(tools).execute(task("activity", "activity.check_feasible", context, ALLOWED)))
    return result, [name for name, _ in tools.calls]


def test_the_tools_are_declared():
    assert "read.place_hours" in ALLOWED and "read.holiday" in ALLOWED


def test_a_weekly_closed_day_from_the_week_table_is_a_change_proposal():
    week = {**OPEN_WEEK, "tue": "closed"}
    result, _ = _run(_hours(week))
    decision = result.decisions[0]
    assert result.next_action is NextAction.WAIT_FOR_APPROVAL
    assert decision["feasible"] is False and decision["reason"] == "closed_weekday"
    assert decision["hours"]["failure_code"] == fc.CLOSED_WEEKDAY
    assert "정기휴무일이라" in result.answer


def test_an_nth_week_closure_the_week_table_cannot_hold_is_read_from_the_text():
    """★요일표는 「매월 둘째 주」를 펴지 못한다(화요일 칸은 열림) — 원문을 휴무 규칙이 읽어 막는다."""
    result, _ = _run(_hours(restdate="매월 둘째 주 화요일 휴무"))
    decision = result.decisions[0]
    assert decision["feasible"] is False and decision["reason"] == "closed_weekday"
    assert "「" in result.answer and "둘째" in result.answer


def test_a_holiday_exception_in_the_text_wins_over_the_week_table():
    """「매주 화요일 휴무, 단 공휴일이면 개방」 — 공휴일 화요일은 열린다. 그날 시간은 요일표가 모르므로 모름으로 남긴다."""
    week = {**OPEN_WEEK, "tue": "closed"}
    result, calls = _run(_hours(week, restdate="매주 화요일 휴무. 단 공휴일과 겹치면 개방"),
                         holiday={"is_holiday": True, "holiday_name": "임시공휴일"})
    decision = result.decisions[0]
    assert "read.holiday" in calls
    assert decision["feasible"] is True and decision["hours"]["closed"] is False
    assert decision["hours"]["within_hours"] is None


def test_outside_the_opening_hours_is_a_change_proposal():
    late = SECOND_TUESDAY.replace(hour=19)
    result, _ = _run(_hours(), starts_at=late)
    decision = result.decisions[0]
    assert decision["feasible"] is False and decision["reason"] == "outside_hours"
    assert decision["hours"]["failure_code"] == fc.OUTSIDE_HOURS


def test_within_hours_is_feasible_and_says_so():
    result, _ = _run(_hours())
    decision = result.decisions[0]
    assert decision["feasible"] is True and decision["hours"]["within_hours"] is True
    assert "운영시간 · 휴무를 확인하지 못해" not in result.answer


def test_unknown_hours_are_not_read_as_open():
    """★모르면 모른다 — 성립을 단정하지 않고 안내 문구와 경고로 남긴다."""
    for hours in (None, _hours(week=None, known=False)):
        result, _ = _run(hours)
        decision = result.decisions[0]
        assert decision["feasible"] is True
        assert "운영시간 · 휴무를 확인하지 못해" in result.answer
        assert any("운영시간 · 휴무를 확인하지 못했다" in w for w in result.warnings)


def test_empty_operating_info_asks_the_customer_instead_of_answering_feasible():
    """★`[2026-10-11]` 운영 정보가 **비어 있으면**(원문도 요일표도 없다) 「성립」으로 답하지 않고 그대로 진행할지 묻는다
    (수정본 UC-A3 `4a` · 부록 A #3). 원문은 있는데 못 읽는 것(`5b`)은 위 시험처럼 단서 + 유지다."""
    empty = {**_hours(week=None, known=False), "usetime_text": None, "restdate_text": None}
    result, calls = _run(empty)
    decision = result.decisions[0]
    assert result.outcome == "waiting" and result.next_action is NextAction.WAIT_FOR_INPUT
    assert result.required_input_schema["properties"]["proceed"]["enum"] == ["keep", "change"]
    assert decision["feasible"] is None and decision["reason"] == "hours_unknown"
    assert decision["failure_code"] == fc.HOURS_UNKNOWN and decision["hours"]["empty"] is True
    assert "성립합니다" not in result.answer
    assert "read.disruptions" in calls          # ★재난 확인을 먼저 한다(4a 는 3단계 뒤)


def test_no_holiday_lookup_when_the_text_has_no_holiday_condition():
    _, calls = _run(_hours(restdate="매주 월요일 휴무"))
    assert "read.holiday" not in calls
