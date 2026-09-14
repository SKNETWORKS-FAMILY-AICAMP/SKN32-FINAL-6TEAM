# -*- coding: utf-8 -*-
"""Open-Meteo 실호출. `-m live` 로만 돈다.

★키가 필요 없는 유일한 소스라 **실제로 붙었는지 재현 가능하게** 남긴다.
  나머지 셋(TourAPI·기상청·ODsay)은 키가 있어야 하고, 2026-09-09 실측으로
  각각 401 / 401 / 200+ApiKeyAuthFailed 를 확인했다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.infrastructure.travel.open_meteo import OpenMeteoWeather

pytestmark = pytest.mark.live


def test_a_real_forecast_comes_back_with_provenance():
    source = OpenMeteoWeather()
    target = (datetime.now() + timedelta(days=1)).replace(
        minute=0, second=0, microsecond=0)

    result = source.forecast(latitude=37.5665, longitude=126.9780, at=target)

    assert result is not None, f"예보를 못 받았다: {dict(source.misses)}"
    assert result["source"] == "open_meteo"
    assert result["kind"] == "forecast"
    assert result["confirmed_at"]
    assert result["matched_hour"] == target.strftime("%Y-%m-%dT%H:%M")
    assert isinstance(result["temperature_c"], (int, float))
    assert dict(source.misses) == {}


def test_the_heritage_api_answers_without_any_key():
    """★국가유산청 — **인증 파라미터를 아예 안 넣고** 부른다(2026-09-10 실측).

    Open-Meteo 에 이어 두 번째 무키 소스다. 키가 필요해지면 여기서 붉어진다.
    """
    from app.infrastructure.travel.heritage import HeritageSource

    source = HeritageSource()
    result = source.locate("경복궁 근정전")

    assert result is not None, f"못 찾았다: {dict(source.misses)}"
    assert 33 < result["latitude"] < 39, result["latitude"]      # 한반도 범위
    assert 124 < result["longitude"] < 132, result["longitude"]
    assert result["source"] == "heritage_khs"
    assert result["provides_opening_hours"] is False
