# -*- coding: utf-8 -*-
"""Activity 가 기상 예보를 **어떻게 쓰는지** — 핵심은 「쓰지 않는 방식」이다.

★★**날씨로 「불가」를 만들지 않는다.** 강수확률이 얼마부터 취소·순연인지는
  운영 규정이 정할 일이고, 규정은 `read.policy` 가 댄다. 가드레일의 수치는
  주의 문구 기준이며 **측정이 아니라 우리가 고른 값**이다. 그걸로 확정
  판정을 만들면 근거 없는 확정이 된다(CLAUDE.md §0.1) — 이 저장소가
  「정책 근거상 가능합니다」로 이미 한 번 데인 자리다.
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


def _values(*, weather=None, weather_sensitive=True, party=2, capacity=4):
    return {
        "read.booking": {"booking_id": "b1", "place_id": "p1",
                         "starts_at": in_hours(30), "party_size": party,
                         "capacity": capacity},
        "read.policy": [{"cancel_deadline_hours": 24}],
        "read.place": {"place_id": "p1", "weather_sensitive": weather_sensitive,
                       "latitude": 37.5, "longitude": 127.0},
        "read.weather": weather,
    }


def _forecast(**overrides):
    base = {"matched_hour": "2026-09-10T14:00", "precipitation_probability": 10,
            "wind_speed_kmh": 5.0, "temperature_c": 21.0, "kind": "forecast",
            "source": "open_meteo", "confirmed_at": "2026-09-09T12:00:00+00:00"}
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_a_bad_forecast_still_does_not_produce_a_refusal():
    """★강수확률 90% 여도 판정은 「성립」이고, 기준 미확인을 **말한다.**"""
    result = await ActivityTeam(FakeTools(_values(
        weather=_forecast(precipitation_probability=90)))).execute(_task())

    assert result.outcome == "completed"
    assert result.next_action is NextAction.RESPOND
    assert result.decisions[0]["feasible"] is True
    assert "90%" in result.answer
    assert any("주의 기준" in warning for warning in result.warnings)
    assert "판정하지 않았습니다" in result.answer
    # ★단정하는 낱말이 답변에 있으면 안 된다.
    assert "불가" not in result.answer and "취소해야" not in result.answer


@pytest.mark.asyncio
async def test_a_calm_forecast_adds_no_advisory():
    result = await ActivityTeam(FakeTools(_values(weather=_forecast()))).execute(_task())
    assert result.decisions[0]["feasible"] is True
    assert not [w for w in result.warnings if "주의 기준" in w]
    assert "강수확률 10%" in result.answer


@pytest.mark.asyncio
async def test_the_answer_says_it_is_a_forecast_not_an_observation():
    """★v10 §4-D — 예보를 현장 확인처럼 전하지 않는다."""
    result = await ActivityTeam(FakeTools(_values(weather=_forecast()))).execute(_task())
    assert "예보" in result.answer
    assert "현장 확인이 아닙니다" in result.answer


@pytest.mark.asyncio
async def test_the_forecast_hour_and_source_are_recorded_in_decisions():
    result = await ActivityTeam(FakeTools(_values(weather=_forecast()))).execute(_task())
    weather = result.decisions[0]["weather"]
    assert weather["matched_hour"] == "2026-09-10T14:00"
    assert weather["source"] == "open_meteo"
    assert weather["confirmed_at"]


@pytest.mark.asyncio
async def test_an_unknown_forecast_escalates_instead_of_guessing():
    """★소스가 모르면 확정 답을 만들지 않는다."""
    result = await ActivityTeam(FakeTools(_values(weather=None))).execute(_task())
    assert result.outcome == "escalated"
    assert result.failure_code == "unknown_기상 정보"
    assert any("모르는" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_an_indoor_place_is_never_asked_about_the_weather():
    """★실내 활동에 기상을 걸면 틀린 이유로 판정이 흔들린다."""
    tools = FakeTools(_values(weather=None, weather_sensitive=False))
    result = await ActivityTeam(tools).execute(_task())
    assert result.outcome == "completed"
    assert "read.weather" not in [name for name, _ in tools.calls]


@pytest.mark.asyncio
async def test_the_weather_call_carries_coordinates_and_the_booking_time():
    """★「어디인지 모르는 곳의 날씨」는 없다 — 좌표와 시각을 넘겨야 한다."""
    tools = FakeTools(_values(weather=_forecast()))
    await ActivityTeam(tools).execute(_task())
    arguments = dict(tools.calls)["read.weather"]
    assert arguments["latitude"] == 37.5 and arguments["longitude"] == 127.0
    assert arguments["at"] is not None


@pytest.mark.asyncio
async def test_a_forecast_with_no_usable_values_does_not_claim_it_was_checked():
    result = await ActivityTeam(FakeTools(_values(weather=_forecast(
        precipitation_probability=None, wind_speed_kmh=None)))).execute(_task())
    assert "날씨는 판정에 넣지 않았습니다" in result.answer
    assert any("비어 있었다" in warning for warning in result.warnings)
