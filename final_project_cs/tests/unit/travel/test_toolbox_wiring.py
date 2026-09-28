# -*- coding: utf-8 -*-
"""`read.weather` 배선 — **기본값이 「바깥으로 안 나간다」**여야 한다.

★도구가 소스를 스스로 만들면 테스트가 조용히 네트워크를 탄다. 그러면
  공급자가 죽은 날 우리 테스트가 붉어지고, 원인을 찾는 데 반나절이 간다.
  주입을 안 하면 「모름」이 되게 **구조로** 막는다.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.contracts import ToolNotAllowed
from app.infrastructure.travel.base import TravelSources
from app.tools.read_tools import ReadToolbox, ToolContext

SCOPE = ToolContext(tenant_id="t", customer_id=__import__("uuid").uuid4(),
                    case_id=__import__("uuid").uuid4(), knowledge_scope=["activity"])


class _RecordingWeather:
    def __init__(self, result=None):
        self.result, self.seen = result, []

    def forecast(self, *, latitude, longitude, at=None):
        self.seen.append((latitude, longitude, at))
        return self.result


def test_without_injection_the_tool_is_unknown_and_makes_no_call():
    """★`ReadToolbox(lambda: None)` — 저장소 전역의 테스트가 쓰는 형태다."""
    assert ReadToolbox(lambda: None).weather(SCOPE, latitude=37.5, longitude=127.0) is None


def test_an_injected_but_empty_source_set_is_unknown():
    toolbox = ReadToolbox(lambda: None, travel=TravelSources())
    assert toolbox.weather(SCOPE, latitude=37.5, longitude=127.0) is None


def test_without_coordinates_the_source_is_not_even_asked():
    source = _RecordingWeather({"x": 1})
    toolbox = ReadToolbox(lambda: None, travel=TravelSources(weather=source))
    assert toolbox.weather(SCOPE, place_id="p1") is None
    assert source.seen == [], "좌표가 없는데 바깥으로 나갔다"


def test_with_coordinates_it_delegates_and_returns_the_source_result():
    source = _RecordingWeather({"temperature_c": 20})
    toolbox = ReadToolbox(lambda: None, travel=TravelSources(weather=source))
    result = toolbox.weather(SCOPE, latitude=37.5, longitude=127.0,
                             at="2026-09-10T14:00:00+00:00")
    assert result == {"temperature_c": 20}
    latitude, longitude, at = source.seen[0]
    assert (latitude, longitude) == (37.5, 127.0)
    assert isinstance(at, datetime)


def test_an_unparseable_time_becomes_none_not_now():
    """★못 읽은 시각을 「지금」으로 대체하면 내일 일정에 오늘 날씨로 답한다."""
    source = _RecordingWeather({"ok": True})
    ReadToolbox(lambda: None, travel=TravelSources(weather=source)).weather(
        SCOPE, latitude=37.5, longitude=127.0, at="언젠가")
    assert source.seen[0][2] is None


def test_a_datetime_passes_through_untouched():
    source = _RecordingWeather({"ok": True})
    moment = datetime(2026, 9, 10, 14, tzinfo=UTC)
    ReadToolbox(lambda: None, travel=TravelSources(weather=source)).weather(
        SCOPE, latitude=37.5, longitude=127.0, at=moment)
    assert source.seen[0][2] == moment


def test_read_weather_still_obeys_the_allowlist():
    """★새 도구라고 권한 검사를 비켜 가지 않는다."""
    from app.core.contracts import ContextPack
    from uuid import uuid4

    pack = ContextPack(pack_id=uuid4(), case_id=uuid4(), team_id="activity",
                       tenant_id="t", knowledge_scope=["activity"],
                       current_state={"customer_id": str(uuid4())},
                       estimated_input_tokens=1)
    with pytest.raises(ToolNotAllowed):
        ReadToolbox(lambda: None).call("read.weather", pack, {}, ["read.booking"], set())
