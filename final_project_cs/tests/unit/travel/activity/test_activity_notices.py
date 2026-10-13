# -*- coding: utf-8 -*-
"""모델이 읽은 요일표로 판정했을 때만 고객 답에 안내가 붙는가 — D-CS-015 개정 2 「고객 안내」. `[2026-10-12]`"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.domains.travel_ops.instances.activity import ActivityTeam
from app.domains.travel_ops.instances.activity.notices import HOURS_AUTO_READ, hours_read_by_model, with_notice
from app.domains.travel_ops.instances.activity.verdicts import hours_verdict

from ..helpers import FakeTools, pack, task
from ._disaster import disaster_from

ALLOWED = ActivityTeam.manifest.allowed_tools
KST = timezone(timedelta(hours=9))
WEDNESDAY = datetime(2026, 11, 11, 14, 0, tzinfo=KST)
TUESDAY = datetime(2026, 11, 10, 14, 0, tzinfo=KST)
CLEAR = {"verdict": "clear", "disruptions": [], "advisories": [], "checks": [], "failed_categories": [],
         "not_connected": []}
WEEK = {d: {"open": "09:00", "close": "18:00"} for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
LLM_READ = {"method": "llm", "quotes": ["하절기 09:00~18:00"], "read_at": "2026-10-12T03:00:00+09:00"}
RULE_READ = {"method": "rule", "quotes": ["09:00~18:00"], "read_at": "2026-10-12T03:00:00+09:00"}


def _hours(week, read, restdate=None):
    return {"known": True, "attributes": {"hours_week": week, "hours_read": read}, "source": "tour_api",
            "why_unknown": None, "conditions": [], "usetime_text": "하절기 09:00~18:00 …", "restdate_text": restdate}


def _answer(hours, at=WEDNESDAY):
    values = {"read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": at, "party_size": 2, "capacity": 4},
              "read.policy": [], "read.disruptions": CLEAR, "read.disaster": disaster_from(CLEAR),
              "read.place": {"place_id": "p1", "name": "경복궁", "weather_sensitive": False, "latitude": 37.5796,
                             "longitude": 126.9770, "source_content_id": None},
              "read.place_hours": hours, "read.place_candidates": None}
    result = asyncio.run(ActivityTeam(FakeTools(values)).execute(
        task("activity", "activity.check_feasible", pack("activity", scope=["activity"]), ALLOWED)))
    return result.answer or ""


def test_the_flag_reads_both_ledger_rows_and_core_hours():
    assert hours_read_by_model({"hours_read": LLM_READ}) is True
    assert hours_read_by_model({"attributes": {"hours_read": LLM_READ}}) is True
    assert hours_read_by_model({"attributes": {"hours_read": RULE_READ}}) is False
    assert hours_read_by_model(None) is False


def test_a_model_read_week_adds_the_notice_when_open():
    assert HOURS_AUTO_READ in _answer(_hours(WEEK, LLM_READ))


def test_a_rule_read_week_adds_nothing():
    assert HOURS_AUTO_READ not in _answer(_hours(WEEK, RULE_READ))


def test_a_model_read_week_that_closes_the_day_also_says_so():
    assert HOURS_AUTO_READ in _answer(_hours({**WEEK, "tue": "closed"}, LLM_READ), at=TUESDAY)


def test_a_closure_decided_by_the_text_rule_does_not_add_the_notice():
    """휴무를 원문 규칙(「매주 화요일」)이 정했으면 요일표를 안 쓴 것이다 — 모델이 읽었어도 붙이지 않는다."""
    verdict = hours_verdict(_hours({**WEEK, "tue": "closed"}, LLM_READ, restdate="매주 화요일"), TUESDAY)
    assert verdict["closed"] is True and verdict["auto_read"] is False


def test_with_notice_joins_or_keeps_one():
    assert with_notice("문장.", "안내.") == "문장. 안내."
    assert with_notice(None, "안내.") == "안내." and with_notice("문장.", None) == "문장."
