# -*- coding: utf-8 -*-
"""Ignav MCP 어댑터 — 응답 모양(2026-10-09 11:53 playdata 실호출)을 그대로 흉내 낸 가짜 서버로 본다. 네트워크 없음."""
from __future__ import annotations

import json

import httpx

from app.domains.travel_ops.ports.data_sources.base import TravelSources
from app.domains.travel_ops.ports.data_sources.ignav import IgnavMcp
from app.tools.read_tools import ReadToolbox

#: 실호출에서 본 모양 그대로(링크만 줄였다)
ITINERARY = {
    "price": {"amount": 122900.0, "currency": "KRW", "status": "verified"},
    "outbound": {"segments": [{
        "marketing_carrier_code": "BX", "flight_number": "164", "operating_carrier_name": "에어부산",
        "departure_airport": "ICN", "departure_time_local": "2026-10-20T07:10:00",
        "arrival_airport": "NRT", "arrival_time_local": "2026-10-20T10:00:00", "duration_minutes": 170,
        "aircraft": "Airbus A321", "departure_timezone": "Asia/Seoul", "arrival_timezone": "Asia/Tokyo",
        "departure_time_utc": "2026-10-19T22:10:00Z", "arrival_time_utc": "2026-10-20T01:00:00Z"}],
        "carrier": "에어부산", "duration_minutes": 170},
    "requires_self_transfer": False, "cabin_class": "economy",
    "booking_link": {"provider_name": "에어부산", "url": "https://www.airbusan.com/web/individual/booking/googleAvail?x=1",
                     "provider_type": "airline", "price": {"amount": 122900.0, "currency": "KRW", "status": "verified"}},
    "booking_url": "https://www.airbusan.com/web/individual/booking/googleAvail?x=1",
    "booking_provider_name": "에어부산", "booking_provider_type": "airline"}
CONNECTING = {**ITINERARY,
              "outbound": {"segments": [
                  {**ITINERARY["outbound"]["segments"][0], "marketing_carrier_code": "KE", "flight_number": "1",
                   "arrival_airport": "KIX", "arrival_time_local": "2026-10-20T09:00:00"},
                  {**ITINERARY["outbound"]["segments"][0], "marketing_carrier_code": "KE", "flight_number": "2",
                   "departure_airport": "KIX", "departure_time_local": "2026-10-20T11:00:00"}],
                  "carrier": "대한항공", "duration_minutes": 290},
              "booking_url": "", "booking_provider_type": "ota"}
BODY = {"origin": "ICN", "destination": "NRT", "departure_date": "2026-10-20", "itineraries": [ITINERARY, CONNECTING]}


def _reply(message, result):
    return httpx.Response(200, json={"jsonrpc": "2.0", "id": message.get("id"), "result": result},
                          request=httpx.Request("POST", "https://x"))


class FakeServer:
    def __init__(self, body=BODY):
        self.body, self.sent, self.headers = body, [], []

    def __call__(self, url, message, headers):
        self.sent.append(message)
        self.headers.append(headers)
        if message["method"] == "initialize":
            return _reply(message, {"protocolVersion": "2025-03-26", "serverInfo": {"name": "Ignav"}})
        if message["method"] == "notifications/initialized":
            return httpx.Response(202, request=httpx.Request("POST", "https://x"))
        return _reply(message, {"content": [{"type": "text", "text": "Flights ICN -> NRT"}], "structuredContent": self.body})

    def calls(self):
        return [m["params"] for m in self.sent if m["method"] == "tools/call"]


def test_search_sends_the_key_header_and_the_ignav_argument_names():
    server = FakeServer()
    IgnavMcp(api_key="k-test", post=server).flight_search(
        origin=" icn ", destination="NRT", depart_date="2026-10-20", adults=2, infants=1, cabin="BUSINESS",
        direct_only=True, max_results=5, domestic=False)
    assert all(headers["X-Api-Key"] == "k-test" for headers in server.headers)
    assert server.calls() == [{"name": "search_flights", "arguments": {
        "origin": "ICN", "destination": "NRT", "departure_date": "2026-10-20", "market": "KR", "max_results": 5,
        "adults": 2, "infants_on_lap": 1, "cabin_class": "business", "max_stops": 0}}]


def test_more_than_ten_is_asked_as_ten():
    server = FakeServer()
    IgnavMcp(api_key="k", post=server).flight_search(origin="GMP", destination="CJU", depart_date="2026-10-20", max_results=30)
    assert server.calls()[0]["arguments"]["max_results"] == 10, "도구 상한 10 — 넘기면 검증 오류로 결과가 통째로 빠진다"


def test_itineraries_come_back_in_the_myrealtrip_shape_with_the_seller():
    found = IgnavMcp(api_key="k", post=FakeServer()).flight_search(origin="ICN", destination="NRT", depart_date="2026-10-20")
    assert found["source"] == "ignav" and found["confirmed_at"]
    direct, connecting = found["flights"]
    assert (direct["airline_code"], direct["airline"], direct["price_total"], direct["currency"]) == ("BX", "에어부산", 122900.0, "KRW")
    assert (direct["seller"], direct["link_kind"]) == ("에어부산", "seller_airline")
    assert direct["link"].startswith("https://www.airbusan.com/")
    assert direct["legs"] == [{"origin": "ICN", "destination": "NRT", "flightNumber": "BX164", "departDate": "2026-10-20",
                               "departTime": "07:10", "arriveDate": "2026-10-20", "arriveTime": "10:00", "stops": 0,
                               "isDirect": True, "carrierCode": "BX", "durationMinutes": 170}]
    leg = connecting["legs"][0]
    assert (leg["origin"], leg["destination"], leg["flightNumber"], leg["stops"]) == ("ICN", "NRT", "KE1/KE2", 1)
    assert connecting["direct"] is False and (connecting["link"], connecting["link_kind"]) == ("", ""), "링크가 없으면 지어내지 않는다"


def test_a_bad_airport_code_or_shape_is_counted_not_guessed():
    source = IgnavMcp(api_key="k", post=FakeServer())
    assert source.flight_search(origin="서울", destination="NRT", depart_date="2026-10-20") is None
    assert IgnavMcp(api_key="k", post=FakeServer({"oops": 1})).flight_search(
        origin="ICN", destination="NRT", depart_date="2026-10-20") is None


def test_the_tool_is_absent_without_the_source():
    toolbox = ReadToolbox.__new__(ReadToolbox)
    toolbox.travel = TravelSources()
    assert toolbox.flight_offers(None, origin="ICN", destination="NRT", depart_date="2026-10-20") is None
