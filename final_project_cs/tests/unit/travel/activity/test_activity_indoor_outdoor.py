# -*- coding: utf-8 -*-
"""성립 판정의 실내외 — `[2026-10-09]` team 통합 ⑤(사용자 결정: develop 기준 + 관광공사 분류).

- 장소에 적힌 값 → 관광공사 분류(`read.place_class` — develop 규칙 `weather_from_class`) 순으로 정한다. 장소명 짐작은 없다.
- 그래도 모르면 모름(`None`)으로 공유 점검에 넘긴다. 전에는 `bool(None)` 이 「실내」가 되어 날씨를 아예 안 봤다.
- 모르는데 날씨 사건만 걸리면 바꾸라고 단정하지 않고 먼저 묻는다(감시 경로 `pending.needs_consent` 와 같은 기준).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.core.contracts import NextAction
from app.domains.travel_ops.instances.activity import ActivityTeam

from ..helpers import FakeTools, pack, task

ALLOWED = ActivityTeam.manifest.allowed_tools
KST = timezone(timedelta(hours=9))
TUESDAY = datetime(2026, 11, 10, 14, 0, tzinfo=KST)
WEEK = {day: {"open": "09:00", "close": "18:00"} for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
CLEAR = {"verdict": "clear", "disruptions": [], "advisories": [], "checks": [], "failed_categories": [],
         "not_connected": [], "indoor_unknown": False}
RAIN = {"category": "forecast", "kind": "강수확률 80%"}
ROAD = {"category": "road_control", "kind": "도로 통제"}
CLASS_OUTDOOR = {"content_id": "126508", "lcls1": "NA", "lcls2": "NA01", "weather_sensitive": True}


def _hours(week=WEEK):
    return {"known": True, "attributes": {"hours_week": week}, "source": "tour_api", "why_unknown": None,
            "conditions": [], "usetime_text": None, "restdate_text": None}


def _disrupted(*events, indoor_unknown=True):
    return {**CLEAR, "verdict": "disrupted", "disruptions": list(events), "indoor_unknown": indoor_unknown}


def _run(*, sensitive=None, place_class=None, report=CLEAR, week=WEEK):
    values = {"read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": TUESDAY,
                               "party_size": 2, "capacity": 4},
              "read.policy": [],
              "read.place": {"place_id": "p1", "name": "북한산", "weather_sensitive": sensitive,
                             "latitude": 37.66, "longitude": 126.98},
              "read.place_class": place_class, "read.disruptions": report, "read.place_hours": _hours(week),
              "read.place_candidates": None}
    tools = FakeTools(values)
    result = asyncio.run(ActivityTeam(tools).execute(
        task("activity", "activity.check_feasible", pack("activity", scope=["activity"]), ALLOWED)))
    return result, dict(tools.calls), [name for name, _ in tools.calls]


def test_the_class_tool_is_declared():
    assert "read.place_class" in ALLOWED


def test_a_known_value_on_the_place_is_used_and_the_class_is_not_read():
    result, arguments, called = _run(sensitive=False)

    assert arguments["read.disruptions"]["weather_sensitive"] is False
    assert "read.place_class" not in called
    assert result.decisions[0]["indoor"] == {"value": False, "source": "place"}


def test_an_unknown_place_takes_the_tour_class():
    result, arguments, _ = _run(place_class=CLASS_OUTDOOR)

    assert arguments["read.disruptions"]["weather_sensitive"] is True
    indoor = result.decisions[0]["indoor"]
    assert indoor["source"] == "class" and indoor["value"] is True and indoor["lcls1"] == "NA"
    assert any("관광공사 분류로 정한 값" in w for w in result.warnings)
    assert "read.place_class" in [e.source_id for e in result.evidence]


def test_an_unknown_class_stays_unknown_instead_of_becoming_indoor():
    """★전에는 `bool(None)` 이라 「실내」로 넘어가 날씨를 안 봤다."""
    result, arguments, _ = _run(place_class={**CLASS_OUTDOOR, "weather_sensitive": None})

    assert arguments["read.disruptions"]["weather_sensitive"] is None
    assert result.decisions[0]["indoor"] == {"value": None, "source": None}


def test_unknown_indoor_with_only_weather_asks_first_instead_of_proposing():
    result, _, _ = _run(report=_disrupted(RAIN))
    decision = result.decisions[0]

    assert result.next_action is NextAction.RESPOND and not result.action_proposals
    assert decision["status"] == "needs_confirmation" and decision["feasible"] is None
    assert decision["reason"] == "indoor_unknown_weather"
    assert "실내인지 확인하지 못해" in result.answer and "바꿔야 합니다" not in result.answer


def test_a_closed_day_still_wins_over_asking_about_weather():
    result, _, _ = _run(report=_disrupted(RAIN), week={**WEEK, "tue": "closed"})

    assert result.decisions[0]["reason"] == "closed_weekday"
    assert result.next_action is NextAction.WAIT_FOR_APPROVAL


def test_known_outdoor_with_weather_still_proposes_a_change():
    result, _, _ = _run(sensitive=True, report=_disrupted(RAIN, indoor_unknown=False))

    assert result.decisions[0]["reason"] == "disrupted"
    assert result.next_action is NextAction.WAIT_FOR_APPROVAL


def test_unknown_indoor_with_a_non_weather_event_still_proposes_a_change():
    """도로 통제는 실내외와 상관없다."""
    result, _, _ = _run(report=_disrupted(RAIN, ROAD))

    assert result.decisions[0]["reason"] == "disrupted"
