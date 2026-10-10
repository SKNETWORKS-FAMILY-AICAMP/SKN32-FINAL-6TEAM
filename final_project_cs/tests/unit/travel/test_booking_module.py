# -*- coding: utf-8 -*-
"""booking 모듈 — 어댑터를 어떻게 부르고(왕복 · 쉬는 중 · 없는 소스) 무엇을 돌려주는지. 어댑터는 가짜다(네트워크 없음). `[2026-10-10]`"""
from __future__ import annotations

from types import SimpleNamespace

from app.domains.travel_ops.components.booking.offers import search_flights, search_stays
from app.domains.travel_ops.ports.data_sources.base import TravelSources
from app.tools.read_tools import ReadToolbox

LEG = {"origin": "ICN", "destination": "NRT", "departDate": "2026-10-20", "departTime": "07:10", "arriveDate": "2026-10-20",
       "arriveTime": "10:00", "durationMinutes": 170, "stops": 0, "isDirect": True}
MRT = {"flights": [{"airline_code": "BX", "airline": "에어부산", "legs": [LEG], "price_total": 132900, "currency": "KRW", "seats": 9,
                    "link": "https://air-web.myrealtrip.com/results?x=BX", "link_kind": "search"}], "source": "myrealtrip"}
IGNAV = {"flights": [{"airline_code": "BX", "airline": "에어부산", "legs": [{**LEG, "flightNumber": "BX164"}], "price_total": 122900.0,
                      "currency": "KRW", "seller": "에어부산", "link": "https://www.airbusan.com/a", "link_kind": "seller_airline"}],
         "source": "ignav"}


class Stub:
    def __init__(self, value):
        self.value, self.calls = value, []

    def flight_search(self, **arguments):
        self.calls.append(arguments)
        return self.value

    def stay_search(self, **arguments):
        self.calls.append(arguments)
        return self.value


def _travel(mrt=None, ignav=None, google=None, *, stays=False):
    if stays:
        return SimpleNamespace(travel_search=Stub(mrt), stay_google=Stub(google))
    return SimpleNamespace(travel_search=Stub(mrt), flight_offers=Stub(ignav), flight_google=Stub(google))


def test_flights_are_merged_across_sources_with_statuses_and_links():
    travel = _travel(MRT, IGNAV, None)
    found = search_flights(travel, origin="ICN", destination="NRT", depart_date="2026-10-20", adults=1, domestic=False)
    assert found["sources"] == {"myrealtrip": {"status": "ok", "count": 1}, "ignav": {"status": "ok", "count": 1},
                                "google": {"status": "failed"}}
    (option,) = found["options"]
    assert option["best"] == 122900.0 and [offer["source"] for offer in option["offers"]] == ["ignav", "myrealtrip"]
    assert option["legs"][0]["flightNumber"] == "BX164", "편명은 묶인 다른 소스에서 빌린다"
    assert [link["name"] for link in found["elsewhere"]] == ["네이버 항공권", "스카이스캐너", "트립닷컴"]
    assert travel.travel_search.calls == [{"origin": "ICN", "destination": "NRT", "depart_date": "2026-10-20",
                                           "domestic": False, "max_results": 100, "adults": 1}], "값이 없는 인자는 보내지 않는다"


def test_round_trip_skips_ignav_and_google_gives_a_reference():
    google = {"flights": [], "note": "왕복은 편별 대신 최저가 참고", "round_trip_lowest": 340015.0, "page": "https://www.google.com/travel/flights?x"}
    travel = _travel(MRT, IGNAV, google)
    found = search_flights(travel, origin="ICN", destination="NRT", depart_date="2026-10-20", return_date="2026-10-23")
    assert travel.flight_offers.calls == [], "왕복은 Ignav 를 부르지 않는다(사용자 결정 2026-10-10)"
    assert found["sources"]["ignav"] == {"status": "skipped", "reason": "round_trip"}
    assert found["sources"]["google"]["status"] == "reference" and found["sources"]["google"]["round_trip_lowest"] == 340015.0
    assert "&rdate=2026-10-23&flighttype=rt" in found["elsewhere"][2]["url"]


def test_resting_and_missing_sources_are_counted_not_guessed():
    travel = SimpleNamespace(travel_search=Stub({"cooldown_seconds": 300, "source": "myrealtrip"}))
    found = search_flights(travel, origin="ICN", destination="NRT", depart_date="2026-10-20")
    assert found["sources"] == {"myrealtrip": {"status": "resting", "cooldown_seconds": 300},
                                "ignav": {"status": "failed"}, "google": {"status": "failed"}}
    assert found["options"] == []


def test_stays_give_both_lists_and_the_booking_link():
    mrt = {"stays": [{"gid": 1, "name": "해밀톤 호텔"}], "total": 37, "source": "myrealtrip"}
    google = {"stays": [{"name": "밀리오레호텔 명동"}], "page": "https://www.google.com/travel/search?q=x", "source": "serpapi_hotels"}
    travel = _travel(mrt, google=google, stays=True)
    found = search_stays(travel, keyword="명동", check_in="2026-11-06", check_out="2026-11-09", adults=2, domestic=True,
                         min_review_rating=4.0)
    assert found["myrealtrip"] == mrt and found["google"] == google
    assert found["sources"] == {"myrealtrip": {"status": "ok", "count": 1}, "google": {"status": "ok", "count": 1}}
    assert "domestic" not in travel.stay_google.calls[0] and "min_review_rating" not in travel.stay_google.calls[0]
    assert [link["name"] for link in found["elsewhere"]] == ["부킹닷컴", "익스피디아", "여기어때", "야놀자"], "국내"
    assert found["elsewhere"][0] == {"name": "부킹닷컴", "url": "https://www.booking.com/searchresults.ko.html?ss=%EB%AA%85%EB%8F%99"
                                                             "&checkin=2026-11-06&checkout=2026-11-09&group_adults=2&no_rooms=1&group_children=0"}
    assert found["elsewhere"][2]["url"] == ("https://www.yeogi.com/domestic-accommodations?keyword=%EB%AA%85%EB%8F%99"
                                            "&checkIn=2026-11-06&checkOut=2026-11-09&personal=2")
    assert found["elsewhere"][3]["note"], "야놀자는 날짜가 주소로 안 들어간다 — 그렇다고 적는다"


def test_stay_links_depend_on_domestic_and_children():
    from app.domains.travel_ops.components.booking.offers.stays import elsewhere

    abroad = elsewhere(keyword="시부야", check_in="2026-11-06", check_out="2026-11-09", adults=2, children=1, domestic=False)
    assert [link["name"] for link in abroad] == ["부킹닷컴", "익스피디아", "호텔스닷컴", "에어비앤비(숙박 공유)"]
    assert abroad[1]["url"] == ("https://www.expedia.co.kr/Hotel-Search?destination=%EC%8B%9C%EB%B6%80%EC%95%BC"
                                "&startDate=2026-11-06&endDate=2026-11-09&adults=2&rooms=1")
    assert abroad[1]["note"] == "어린이 인원은 그 화면에서 넣어 주세요", "익스피디아는 어린이 나이가 있어야 한다"
    assert abroad[3]["url"].endswith("&adults=2&children=1")
    unknown = elsewhere(keyword="x", check_in="2026-11-06", check_out="2026-11-09", adults=None, children=None)
    assert [link["name"] for link in unknown] == ["부킹닷컴", "익스피디아"] and "note" not in unknown[1]


def test_the_tools_are_absent_without_sources():
    toolbox = ReadToolbox.__new__(ReadToolbox)
    toolbox.travel = None
    assert toolbox.booking_search_flights(None, origin="ICN", destination="NRT", depart_date="2026-10-20") is None
    toolbox.travel = TravelSources()
    found = toolbox.booking_search_stays(None, keyword="명동", check_in="2026-11-06", check_out="2026-11-09")
    assert found["sources"] == {"myrealtrip": {"status": "failed"}, "google": {"status": "failed"}}
