# -*- coding: utf-8 -*-
"""Activity 가 **성립 점검**(`read.disruptions`)을 어떻게 쓰는지.

★★예보 수치로 「불가」를 만들지 않는다. 강수확률이 얼마부터 취소·순연인지는
  운영 규정이 정할 일이고, 가드레일 수치는 **우리가 고른 주의 문구 기준**이다.
  「불가」(일정 변경)는 **사건**(특보 등, 점검의 `disruptions`)에서만 나온다.

★2026-09-14 — 예보·특보를 따로 부르던 것을 점검 한 번으로 바꿨다. Activity 는
  `max_steps=6` 인데 예보·특보만으로 5 를 쓰고 있었다(실측).
"""
from __future__ import annotations

import pytest

from app.core.contracts import NextAction
from app.modules.travel_ops.activity import ActivityTeam

from .helpers import FakeTools, in_hours, pack, task

ALLOWED = ActivityTeam.manifest.allowed_tools


def _task(capability: str = "activity.check_feasible"):
    context = pack("activity", scope=["activity", "weather"])
    return task("activity", capability, context, ALLOWED)


def _forecast(**overrides):
    base = {"matched_hour": "2026-09-10T14:00", "precipitation_probability": 10,
            "wind_speed_kmh": 5.0, "temperature_c": 21.0, "kind": "forecast",
            "source": "open_meteo", "confirmed_at": "2026-09-09T12:00:00+00:00"}
    base.update(overrides)
    return base


def _report(forecast=None, *, verdict="clear", failed=()):
    checks = []
    if forecast is not None:
        checks.append({"category": "forecast", "status": "ok", "value": forecast})
    return {"verdict": verdict, "disruptions": [], "advisories": [], "checks": checks,
            "failed_categories": list(failed), "not_connected": ["air_quality"]}


def _values(*, report=None, weather_sensitive=True, party=2, capacity=4):
    return {
        "read.booking": {"booking_id": "b1", "place_id": "p1",
                         "starts_at": in_hours(30), "party_size": party,
                         "capacity": capacity},
        "read.policy": [{"cancel_deadline_hours": 24}],
        "read.place": {"place_id": "p1", "weather_sensitive": weather_sensitive,
                       "latitude": 37.5, "longitude": 127.0},
        "read.disruptions": report,
    }


@pytest.mark.asyncio
async def test_a_bad_forecast_still_does_not_produce_a_refusal():
    """★강수확률 90% 여도 판정은 「성립」이고, 기준 미확인을 **말한다.**"""
    result = await ActivityTeam(FakeTools(_values(
        report=_report(_forecast(precipitation_probability=90))))).execute(_task())

    assert result.outcome == "completed"
    assert result.next_action is NextAction.RESPOND
    assert result.decisions[0]["feasible"] is True
    assert "90%" in result.answer
    assert any("주의 기준" in warning for warning in result.warnings)
    assert "판정하지 않았습니다" in result.answer
    assert "불가" not in result.answer and "취소해야" not in result.answer


@pytest.mark.asyncio
async def test_a_calm_forecast_adds_no_advisory():
    result = await ActivityTeam(FakeTools(_values(report=_report(_forecast())))).execute(_task())
    assert result.decisions[0]["feasible"] is True
    assert not [w for w in result.warnings if "주의 기준" in w]
    assert "강수확률 10%" in result.answer


@pytest.mark.asyncio
async def test_the_answer_says_it_is_a_forecast_not_an_observation():
    """★v10 §4-D — 예보를 현장 확인처럼 전하지 않는다."""
    result = await ActivityTeam(FakeTools(_values(report=_report(_forecast())))).execute(_task())
    assert "예보" in result.answer
    assert "현장 확인이 아닙니다" in result.answer


@pytest.mark.asyncio
async def test_the_forecast_hour_source_and_unconnected_checks_are_recorded():
    result = await ActivityTeam(FakeTools(_values(report=_report(_forecast())))).execute(_task())
    weather = result.decisions[0]["weather"]
    assert weather["matched_hour"] == "2026-09-10T14:00"
    assert weather["source"] == "open_meteo"
    assert weather["confirmed_at"]
    # ★아직 못 붙인 소스를 숨기지 않는다
    assert result.decisions[0]["not_connected"] == ["air_quality"]


@pytest.mark.asyncio
async def test_a_failed_check_is_fatal_instead_of_guessing():
    """★결정 15 — 대체까지 못 가져오면 치명. 성립이라고 답하지 않는다."""
    result = await ActivityTeam(FakeTools(_values(
        report=_report(verdict="fatal", failed=["forecast"])))).execute(_task())
    assert result.outcome == "escalated"
    assert result.failure_code == "fatal_source_failure"
    assert any("forecast" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_no_report_at_all_is_fatal_too():
    """★점검 도구 자체가 답을 못 하면(소스 묶음 미주입 등) 성립이라고 하지 않는다."""
    result = await ActivityTeam(FakeTools(_values(report=None))).execute(_task())
    assert result.outcome == "escalated"
    assert result.failure_code == "fatal_source_failure"


@pytest.mark.asyncio
async def test_the_check_is_one_call_carrying_coordinates_time_and_sensitivity():
    """★Team 은 점검을 **한 번** 부른다. 좌표·시각·날씨 민감도를 넘겨야 한다."""
    tools = FakeTools(_values(report=_report(_forecast())))
    await ActivityTeam(tools).execute(_task())
    names = [name for name, _ in tools.calls]
    assert names.count("read.disruptions") == 1
    assert "read.weather" not in names and "read.weather_warning" not in names
    arguments = dict(tools.calls)["read.disruptions"]
    assert arguments["latitude"] == 37.5 and arguments["longitude"] == 127.0
    assert arguments["starts_at"] is not None
    assert arguments["weather_sensitive"] is True and arguments["region"] == "서울"


@pytest.mark.asyncio
async def test_an_indoor_place_passes_its_sensitivity_so_the_check_skips_weather():
    """★실내 여부는 점검이 판단한다 — Team 은 속성을 넘길 뿐이다."""
    tools = FakeTools(_values(report=_report(), weather_sensitive=False))
    result = await ActivityTeam(tools).execute(_task())
    assert result.outcome == "completed"
    assert dict(tools.calls)["read.disruptions"]["weather_sensitive"] is False
    assert "weather" not in result.decisions[0]


@pytest.mark.asyncio
async def test_a_forecast_with_no_usable_values_does_not_claim_it_was_checked():
    result = await ActivityTeam(FakeTools(_values(report=_report(_forecast(
        precipitation_probability=None, wind_speed_kmh=None))))).execute(_task())
    assert "날씨는 판정에 넣지 않았습니다" in result.answer
    assert any("비어 있었다" in warning for warning in result.warnings)
