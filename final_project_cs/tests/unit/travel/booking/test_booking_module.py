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
    assert [link["name"] for link in found["elsewhere"]] == ["네이버 항공권", "스카이스캐너", "트립닷컴", "NOL 인터파크 투어", "카약"]
    assert found["elsewhere"][3]["url"] == "https://tour.yanolja.com/air/search/a:ICN-a:NRT-20261020?cabin=ECONOMY&infant=0&child=0&adult=1"
    assert found["elsewhere"][4] == {"name": "카약", "url": "https://www.kayak.co.kr/flights/ICN-NRT/2026-10-20/1adults?sort=bestflight_a"}
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
    assert found["elsewhere"][3]["url"].startswith("https://tour.yanolja.com/air/search/a:ICN-a:NRT-20261020/a:NRT-a:ICN-20261023?")
    assert found["elsewhere"][4]["url"].startswith("https://www.kayak.co.kr/flights/ICN-NRT/2026-10-20/2026-10-23/")


def test_flight_links_carry_cabin_and_say_when_children_cannot_be_put_in():
    from datetime import date

    from app.domains.travel_ops.components.booking.offers.flights import elsewhere

    links = elsewhere(origin="GMP", destination="CJU", depart_date=date(2026, 11, 6), return_date=None, domestic=True,
                      cabin="BUSINESS", adults=2, children=1, infants=0)
    nol, kayak = links[3], links[4]
    assert nol["url"] == "https://tour.yanolja.com/air/search/a:GMP-a:CJU-20261106?cabin=BUSINESS&infant=0&child=1&adult=2"
    assert "note" not in nol, "NOL 은 어린이 수를 받는다(2026-10-10 「3명」 확인)"
    assert kayak == {"name": "카약", "url": "https://www.kayak.co.kr/flights/GMP-CJU/2026-11-06/business/2adults?sort=bestflight_a",
                     "note": "어린이 · 유아 인원은 그 화면에서 넣어 주세요"}


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


def test_sources_are_called_at_the_same_time():
    """`[2026-10-11]` 소스를 동시에 부른다 — 전체 시간 ≈ 가장 느린 소스. ☆16:57 playdata 26.0초 = Ignav 18.7 + 마이리얼트립 1.5 + 구글 2.0 쯤."""
    import threading
    import time

    started = threading.Barrier(3, timeout=2)

    class Slow(Stub):
        def flight_search(self, **arguments):
            started.wait()                            # 셋이 동시에 들어와야 지나간다(차례로 부르면 2초 뒤 BrokenBarrierError)
            time.sleep(0.2)
            return super().flight_search(**arguments)

    travel = SimpleNamespace(travel_search=Slow(MRT), flight_offers=Slow(IGNAV), flight_google=Slow(None))
    begun = time.perf_counter()
    found = search_flights(travel, origin="ICN", destination="NRT", depart_date="2026-10-20", adults=1, domestic=False)
    assert time.perf_counter() - begun < 0.5
    assert [offer["source"] for offer in found["options"][0]["offers"]] == ["ignav", "myrealtrip"]
    assert found["sources"]["google"] == {"status": "failed"}


def test_a_source_slower_than_the_limit_is_left_out_as_timeout(monkeypatch):
    """`[2026-10-12]` 소스마다 기다리는 시간에 상한 — 늦은 소스는 `timeout` 으로 세고 받은 소스로만 묶는다. 걸린 시간도 돌려준다."""
    import time

    from app.domains.travel_ops.components.booking.offers import flights

    monkeypatch.setattr(flights, "SOURCE_WAIT_SECONDS", 0.3)

    class Late(Stub):
        def flight_search(self, **arguments):
            time.sleep(1.0)
            return super().flight_search(**arguments)

    travel = SimpleNamespace(travel_search=Stub(MRT), flight_offers=Late(IGNAV), flight_google=Stub(None))
    begun = time.perf_counter()
    found = search_flights(travel, origin="ICN", destination="NRT", depart_date="2026-10-20", adults=1, domestic=False)
    assert time.perf_counter() - begun < 0.8, "늦은 소스를 끝까지 기다리지 않는다"
    assert found["sources"]["ignav"] == {"status": "timeout", "seconds": 0.3}
    assert found["sources"]["myrealtrip"] == {"status": "ok", "count": 1}
    assert [offer["source"] for offer in found["options"][0]["offers"]] == ["myrealtrip"], "늦은 소스의 편은 묶지 않는다"
    assert found["elapsed"]["ignav"] is None and isinstance(found["elapsed"]["myrealtrip"], float)


def test_google_details_are_read_at_the_same_time_and_a_missing_source_is_none():
    """`[2026-10-13]` 구글 호텔 후보 셋의 상세를 동시에 — 전체 시간 ≈ 가장 느린 한 곳."""
    import time

    class Detail:
        def __init__(self):
            self.calls = []

        def stay_detail(self, **arguments):
            self.calls.append(arguments["property_token"])
            time.sleep(0.2)
            return {"property_token": arguments["property_token"], "sellers": []}

    from app.domains.travel_ops.components.booking.offers import google_details

    adapter = Detail()
    begun = time.perf_counter()
    got = google_details(SimpleNamespace(stay_google=adapter), tokens=["a", "b", "a", "c"], keyword="서울 명동",
                         check_in="2026-11-06", check_out="2026-11-09", adults=2)
    assert time.perf_counter() - begun < 0.5
    assert sorted(adapter.calls) == ["a", "b", "c"], "같은 열쇠는 한 번만"
    assert set(got["details"]) == {"a", "b", "c"}
    assert google_details(SimpleNamespace(), tokens=["a"], keyword="x", check_in="2026-11-06", check_out="2026-11-09") is None
