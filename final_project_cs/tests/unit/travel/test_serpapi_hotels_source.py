# -*- coding: utf-8 -*-
"""SerpApi 구글 호텔 어댑터 — 응답 모양(2026-10-10 14:21 playdata 실호출에서 본 항목 이름)을 흉내 낸 가짜 응답. 네트워크 없음."""
from __future__ import annotations

import httpx

from app.domains.travel_ops.ports.data_sources.base import TravelSources
from app.domains.travel_ops.ports.data_sources.serpapi_hotels import SerpApiHotels
from app.tools.read_tools import ReadToolbox

PAGE = "https://www.google.com/travel/search?q=%EC%84%9C%EC%9A%B8&hl=ko&gl=kr"
HOTEL = {"type": "hotel", "name": "밀리오레호텔 명동", "link": "https://migliorehotel.co.kr",
         "gps_coordinates": {"latitude": 37.56, "longitude": 126.98},
         "rate_per_night": {"lowest": "₩241,878", "extracted_lowest": 241878},
         "total_rate": {"lowest": "₩725,634", "extracted_lowest": 725634},
         "overall_rating": 3.3, "reviews": 1076, "extracted_hotel_class": 4, "property_token": "t"}
RENTAL = {"type": "vacation rental", "name": "Namsan Ville", "link": "https://www.bluepillow.com/x",
          "rate_per_night": {"extracted_lowest": 177960}, "total_rate": {"extracted_lowest": 533879}}
BODY = {"search_metadata": {"status": "Success", "google_hotels_url": PAGE}, "properties": [RENTAL, HOTEL]}


class Fake:
    def __init__(self, body=BODY):
        self.body, self.sent = body, []

    def __call__(self, url, params):
        self.sent.append(params)
        return httpx.Response(200, json=self.body, request=httpx.Request("GET", url))


def test_search_sends_korean_settings():
    fake = Fake()
    SerpApiHotels(api_key="k-test", transport=fake).stay_search(
        keyword=" 서울 명동 ", check_in="2026-11-06", check_out="2026-11-09", adults=2, children=1, max_price=200000, domestic=True)
    assert fake.sent == [{"engine": "google_hotels", "q": "서울 명동", "check_in_date": "2026-11-06", "check_out_date": "2026-11-09",
                          "currency": "KRW", "hl": "ko", "gl": "kr", "api_key": "k-test", "adults": 2, "children": 1,
                          "max_price": 200000}]


def test_properties_come_back_as_stays_with_the_page():
    found = SerpApiHotels(api_key="k", transport=Fake()).stay_search(keyword="서울 명동", check_in="2026-11-06", check_out="2026-11-09")
    assert found["source"] == "serpapi_hotels" and found["page"] == PAGE
    rental, hotel = found["stays"]
    assert hotel == {"name": "밀리오레호텔 명동", "type": "hotel", "price_per_night": 241878.0, "total_price": 725634.0,
                     "rating": 3.3, "review_count": 1076, "hotel_class": 4, "latitude": 37.56, "longitude": 126.98,
                     "link": "https://migliorehotel.co.kr"}
    assert (rental["type"], rental["rating"], rental["latitude"]) == ("vacation rental", None, None)


def test_no_results_and_missing_input_are_counted():
    source = SerpApiHotels(api_key="k", transport=Fake({"error": "Google Hotels hasn't returned any results for this query."}))
    assert source.stay_search(keyword="롯데호텔 서울", check_in="2026-11-06", check_out="2026-11-09") is None
    assert source.misses["body_error"] == 1
    assert SerpApiHotels(api_key="k", transport=Fake()).stay_search(keyword="", check_in="2026-11-06", check_out="2026-11-09") is None


def test_the_tool_is_absent_without_the_source():
    toolbox = ReadToolbox.__new__(ReadToolbox)
    toolbox.travel = TravelSources()
    assert toolbox.stay_google(None, keyword="서울", check_in="2026-11-06", check_out="2026-11-09") is None
