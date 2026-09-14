# -*- coding: utf-8 -*-
"""기상특보·외교부 여행경보 실호출. `-m live` 로만 돈다 — 공공데이터포털 키가 필요하다."""
from __future__ import annotations

import pytest

from app.core.settings import get_settings
from app.infrastructure.travel.kma_warning import KmaWarningSource
from app.infrastructure.travel.mofa import MofaTravelAlarm

pytestmark = pytest.mark.live


def _key(field: str) -> str:
    settings = get_settings()
    key = settings.public_data_key(getattr(settings, field))
    if not key:
        pytest.skip("공공데이터포털 키가 비어 있다 — .env.apikeys 확인")
    return key


def test_kma_warning_status_is_readable():
    source = KmaWarningSource(service_key=_key("kma_warning_api_key"))
    result = source.active(region="서울")
    assert result is not None, dict(source.misses)
    # ★발효 중인 특보는 날마다 다르다. 모양만 본다 — 목록이면 읽은 것이다.
    assert isinstance(result["in_effect"], list) and isinstance(result["for_region"], list)
    assert result["announced_at"]


def test_mofa_japan_has_a_partial_region_alarm():
    source = MofaTravelAlarm(service_key=_key("mofa_api_key"))
    result = source.country(iso2="JP")
    assert result is not None, dict(source.misses)
    assert result["country_iso2"] == "JP" and result["country_name"] == "일본"
    assert result["max_level"] >= 1
