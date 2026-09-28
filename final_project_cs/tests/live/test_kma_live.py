# -*- coding: utf-8 -*-
"""기상청 단기예보 실호출. `-m live` 로만 돈다 — 공공데이터포털 키가 필요하다."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.settings import get_settings
from app.infrastructure.travel.kma import KST, KmaWeather

pytestmark = pytest.mark.live


def _key() -> str:
    settings = get_settings()
    return settings.public_data_key(settings.kma_api_key)


def test_kma_returns_a_forecast_for_seoul_city_hall():
    key = _key()
    if not key:
        pytest.skip("공공데이터포털 키가 비어 있다 — .env.apikeys 확인")
    source = KmaWeather(service_key=key)
    at = (datetime.now(KST) + timedelta(hours=3)).replace(minute=0, second=0, microsecond=0)
    result = source.forecast(latitude=37.5665, longitude=126.9780, at=at)
    assert result is not None, dict(source.misses)
    assert result["source"] == "kma" and result["grid"] == {"nx": 60, "ny": 127}
    assert result["temperature_c"] is not None
    assert result["precipitation_probability"] is not None
    assert result["wind_speed_kmh"] is not None
