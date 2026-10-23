# -*- coding: utf-8 -*-
"""SerpApi 호출 예산 — 무료 **월 250회**(구글 호텔 · 구글 항공권 한 계정). `[2026-10-13 사용자 지시]`

★두 어댑터가 각자 이름으로 세면 계정 하나의 한도를 둘이 따로 세어 합이 넘는다 — 같은 이름(`serpapi`)으로 센다.
★월 · 일 줄은 DB 로 센다(가드레일 `travel.source_budget_sources`) — 프로세스 · 재시작을 건너 같은 줄. 하나라도 차면 부르지 않는다(`CallBudget`).
"""
from __future__ import annotations

from app.core.settings import Settings, get_guardrails
from app.domains.travel_ops.ports.data_sources.serpapi_flights import SerpApiFlights
from app.domains.travel_ops.ports.data_sources.serpapi_hotels import SerpApiHotels


def test_hotels_and_flights_count_the_same_serpapi_budget():
    assert SerpApiHotels.name == SerpApiFlights.name == "serpapi"
    settings = Settings.model_construct()
    assert settings.source_rate_limits()["serpapi"] == 8, "하루 = 250 / 31"
    assert settings.source_monthly_limits()["serpapi"] == 250, "월 = 무료 250회"
    guardrails = get_guardrails()
    assert "serpapi" in guardrails.get("travel.source_budget_sources"), "DB 로 센다(재시작해도 이어서)"
    assert guardrails.get("travel.rate_burst_by_source")["serpapi"] == 8, "「바꿔 줘」 한 번의 연달은 호출(목록 1 + 상세 3)이 들어간다"


class _Response:
    def __init__(self, status_code, text):
        self.status_code, self.text = status_code, text


def test_running_out_of_searches_stops_the_month():
    hotels = SerpApiHotels(api_key="test")
    assert hotels._quota_signal(_Response(429, '{"error": "Your account has run out of searches."}')) == "month"
    assert hotels._quota_signal(_Response(200, '{"properties": []}')) is None
    assert SerpApiFlights(api_key="test")._quota_signal(_Response(429, "Your account has run out of searches.")) == "month"
