# -*- coding: utf-8 -*-
"""SerpApi 구글 항공권 어댑터 — 응답 모양(2026-10-09 15:08 playdata 실호출에서 본 항목 이름)을 흉내 낸 가짜 응답으로 본다. 네트워크 없음."""
from __future__ import annotations

import httpx

from app.domains.travel_ops.ports.data_sources.base import TravelSources
from app.domains.travel_ops.ports.data_sources.serpapi_flights import SerpApiFlights
from app.tools.read_tools import ReadToolbox

PAGE = "https://www.google.com/travel/flights?hl=ko&gl=kr&curr=KRW&tfs=x"
BX = {"flights": [{"departure_airport": {"id": "ICN", "time": "2026-10-20 07:10"},
                   "arrival_airport": {"id": "NRT", "time": "2026-10-20 10:00"},
                   "duration": 170, "airline": "에어부산", "flight_number": "BX 164"}],
      "total_duration": 170, "price": 122900, "type": "One way", "booking_token": "t"}
VIA = {"flights": [{"departure_airport": {"id": "ICN", "time": "2026-10-20 06:35"},
                    "arrival_airport": {"id": "MNL", "time": "2026-10-20 10:00"}, "airline": "세부퍼시픽항공",
                    "flight_number": "5J 187"},
                   {"departure_airport": {"id": "MNL", "time": "2026-10-20 13:00"},
                    "arrival_airport": {"id": "NRT", "time": "2026-10-20 18:00"}, "airline": "세부퍼시픽항공",
                    "flight_number": "5J 5054"}],
       "total_duration": 685, "price": 732000}
BODY = {"search_metadata": {"status": "Success", "google_flights_url": PAGE}, "best_flights": [BX], "other_flights": [VIA]}


class Fake:
    def __init__(self, body=BODY, status=200):
        self.body, self.status, self.sent = body, status, []

    def __call__(self, url, params):
        self.sent.append(params)
        return httpx.Response(self.status, json=self.body, request=httpx.Request("GET", url))


def test_search_sends_korean_settings_and_the_ignav_style_arguments():
    fake = Fake()
    SerpApiFlights(api_key="k-test", transport=fake).flight_search(
        origin=" icn ", destination="NRT", depart_date="2026-10-20", adults=2, infants=1, cabin="BUSINESS", direct_only=True)
    assert fake.sent == [{"engine": "google_flights", "departure_id": "ICN", "arrival_id": "NRT", "outbound_date": "2026-10-20",
                          "type": 2, "currency": "KRW", "hl": "ko", "gl": "kr", "api_key": "k-test",
                          "adults": 2, "infants_on_lap": 1, "travel_class": 3, "stops": 1}]


def test_itineraries_come_back_in_the_shared_shape_with_the_results_page_link():
    found = SerpApiFlights(api_key="k", transport=Fake()).flight_search(origin="ICN", destination="NRT", depart_date="2026-10-20")
    assert found["source"] == "serpapi_flights" and found["confirmed_at"]
    direct, via = found["flights"]
    assert (direct["airline_code"], direct["airline"], direct["price_total"], direct["currency"]) == ("BX", "에어부산", 122900.0, "KRW")
    assert (direct["link"], direct["link_kind"]) == (PAGE, "route_search")
    assert direct["legs"] == [{"origin": "ICN", "destination": "NRT", "flightNumber": "BX164", "departDate": "2026-10-20",
                               "departTime": "07:10", "arriveDate": "2026-10-20", "arriveTime": "10:00", "stops": 0,
                               "isDirect": True, "carrierCode": "BX", "durationMinutes": 170}]
    assert (via["legs"][0]["flightNumber"], via["legs"][0]["stops"], via["direct"]) == ("5J187/5J5054", 1, False)


def test_a_round_trip_gives_only_the_lowest_price_and_the_page():
    fake = Fake({**BODY, "price_insights": {"lowest_price": 245000}})
    found = SerpApiFlights(api_key="k", transport=fake).flight_search(
        origin="ICN", destination="NRT", depart_date="2026-10-20", return_date="2026-10-23")
    assert (fake.sent[0]["type"], fake.sent[0]["return_date"]) == (1, "2026-10-23")
    assert found["flights"] == [] and found["note"] == "왕복은 편별 대신 최저가 참고"
    assert (found["round_trip_lowest"], found["page"]) == (245000.0, PAGE)


def test_errors_are_counted_not_guessed():
    source = SerpApiFlights(api_key="k", transport=Fake({"error": "Invalid API key."}))
    assert source.flight_search(origin="ICN", destination="NRT", depart_date="2026-10-20") is None
    assert source.misses["body_error"] == 1
    assert SerpApiFlights(api_key="k", transport=Fake()).flight_search(origin="서울", destination="NRT", depart_date="2026-10-20") is None


def test_the_tool_is_absent_without_the_source():
    toolbox = ReadToolbox.__new__(ReadToolbox)
    toolbox.travel = TravelSources()
    assert toolbox.flight_google(None, origin="ICN", destination="NRT", depart_date="2026-10-20") is None
