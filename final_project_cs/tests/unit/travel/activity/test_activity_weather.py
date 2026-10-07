# -*- coding: utf-8 -*-
"""Activity `check_feasible` — 기상 예보 경로.

[2026-09-28 역복원]
  구: read.weather + read.disaster 개별 도구 (role-activity 아키텍처)
  일시: read.disruptions 단일 도구 (develop 병합)
  복원: read.weather 직접 호출로 되돌림

★★예보 수치로 「불가」를 만들지 않는다. 강수확률이 얼마부터 취소·순연인지는
  운영 규정이 정할 일이고, 가드레일 수치는 **우리가 고른 주의 문구 기준**이다.
"""
from __future__ import annotations

import pytest

from app.core.context import PolicyChunk
from app.core.contracts import NextAction
from app.modules.travel_ops.activity import ActivityTeam

from ..helpers import FakeTools, in_hours, pack, task

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


def _values(*, weather=None, weather_sensitive=True, party=2, capacity=4):
    return {
        "read.booking": {"booking_id": "b1", "place_id": "p1",
                         "starts_at": in_hours(30), "party_size": party,
                         "capacity": capacity},
        "read.policy": [PolicyChunk(document_id="t_doc_01", chunk_no=1, scope="travel_activity", score=0.7,
                                     content="취소·환급은 업체 조건을 따른다.")],
        "read.place": {"place_id": "p1", "weather_sensitive": weather_sensitive,
                       "latitude": 37.5, "longitude": 127.0},
        "read.weather": weather,
    }


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
async def test_the_forecast_hour_and_source_are_recorded():
    result = await ActivityTeam(FakeTools(_values(weather=_forecast()))).execute(_task())
    weather = result.decisions[0]["weather"]
    assert weather["matched_hour"] == "2026-09-10T14:00"
    assert weather["source"] == "open_meteo"
    assert weather["confirmed_at"]


@pytest.mark.asyncio
async def test_weather_is_skipped_when_read_weather_returns_none():
    """read.weather → None 이면 weather 키가 결정에 없다 — 모름을 없음으로 안 읽는다."""
    result = await ActivityTeam(FakeTools(_values(weather=None))).execute(_task())
    assert result.outcome == "completed"
    assert "weather" not in result.decisions[0]


@pytest.mark.asyncio
async def test_weather_tool_is_called_with_coordinates_and_time():
    """★read.weather 가 좌표·시각을 받아 호출되는지."""
    tools = FakeTools(_values(weather=_forecast()))
    await ActivityTeam(tools).execute(_task())
    names = [name for name, _ in tools.calls]
    assert "read.weather" in names
    assert "read.disruptions" not in names
    arguments = dict(tools.calls)["read.weather"]
    assert arguments["latitude"] == 37.5 and arguments["longitude"] == 127.0
    # ★`[2026-10-07]` 도구가 읽는 이름은 `at` 이다 — 예전 `starts_at` 은 버려져 지금 시각의 예보를 봤다
    assert arguments["at"] is not None and "starts_at" not in arguments


@pytest.mark.asyncio
async def test_an_indoor_place_skips_weather():
    """★실내(`weather_sensitive=False`)면 read.weather 를 부르지 않는다."""
    tools = FakeTools(_values(weather_sensitive=False))
    result = await ActivityTeam(tools).execute(_task())
    assert result.outcome == "completed"
    names = [name for name, _ in tools.calls]
    assert "read.weather" not in names
    assert "weather" not in result.decisions[0]


@pytest.mark.asyncio
async def test_a_forecast_with_no_usable_values_does_not_claim_it_was_checked():
    result = await ActivityTeam(FakeTools(_values(weather=_forecast(
        precipitation_probability=None, wind_speed_kmh=None)))).execute(_task())
    assert "날씨는 판정에 넣지 않았습니다" in result.answer
    assert any("비어 있었다" in warning for warning in result.warnings)
