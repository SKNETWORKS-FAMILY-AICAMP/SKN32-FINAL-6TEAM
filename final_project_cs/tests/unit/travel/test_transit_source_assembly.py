# -*- coding: utf-8 -*-
"""대중교통(ODsay) 소스 조립 — **키가 있어도 조립이 죽지 않고, 없다는 이유를 남기는가.**

★2026-09-18 결함: `build_travel_sources` 가 키가 있으면 `from .odsay import OdsayTransit` 를 불렀는데
  `odsay.py` 는 한 번도 커밋된 적이 없다. 키를 채우는 순간 조립 전체가 ModuleNotFoundError 로 죽었다.
  이 시험 전에는 키가 빈 경로만 지났다.
  → wiki/records/reports/debugs/2026-09-18_1520_ODsay_키를_넣으면_감시소스_조립이_죽는다.md
"""
from __future__ import annotations

from app.core.settings import Settings
from app.infrastructure.travel.base import build_travel_sources


def _build(**overrides):
    # ★model_construct — .env 를 읽지 않는다. 실제 키 유무와 무관하게 같은 결과가 나온다.
    return build_travel_sources(Settings.model_construct(**overrides))


def test_a_filled_odsay_key_does_not_break_source_assembly():
    sources = _build(odsay_api_key="dummy-key")
    assert sources.transit is None and sources.route is None
    assert "ODsay 어댑터 미구현" in sources.unavailable["transit"]


def test_an_empty_odsay_key_says_the_key_is_missing():
    sources = _build(odsay_api_key="")
    assert sources.transit is None and sources.route is None
    assert "ACOP_ODSAY_API_KEY 가 비어 있다" in sources.unavailable["transit"]
