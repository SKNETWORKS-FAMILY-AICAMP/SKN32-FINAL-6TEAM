# -*- coding: utf-8 -*-
"""항공 팀 — 모델은 해석(공항 코드 포함)만 하고, 서버가 검증 · 조회 · 답을 맡는지 본다. 모델과 도구는 가짜다."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core.contracts import ContextPack, TeamTask, ToolNotAllowed
from app.domains.travel_ops.components.booking.offers import search_flights
from app.domains.travel_ops.instances.flight import FlightTeam
from app.domains.travel_ops.instances.flight.interpret import InterpretationInvalid, needs, parse
from app.tools.read_tools import ALLOWED_PROMPT_KEYS

TODAY = datetime.now(ZoneInfo("Asia/Seoul")).date()
#: 「다음 달 6일」 · 「9일」 — 시험 문장과 같은 날. `[2026-10-10]` 서버가 근거 조각의 날(일)에 값을 맞추므로(settle_years) 오늘+30일로 두면 문장과 어긋난다
_NEXT = (TODAY.replace(day=1) + timedelta(days=32)).replace(day=1)
GO, BACK = _NEXT.replace(day=6).isoformat(), _NEXT.replace(day=9).isoformat()
SEARCH = {"task": "search", "origin": "TPE", "destination": "ICN", "depart_date": GO, "return_date": None,
          "depart_date_text": "다음 달 6일", "return_date_text": None,
          "adults": 2, "children": None, "infants": None, "cabin": None, "direct_only": True, "domestic": False,
          "missing": [], "question": None}
LEG = {"origin": "TPE", "destination": "ICN", "departDate": GO, "departTime": "13:10", "arriveDate": GO,
       "arriveTime": "16:40", "durationMinutes": 150, "stops": 0, "isDirect": True}
FLIGHTS = {"flights": [
    {"airline_code": "7C", "airline": "제주항공", "legs": [LEG], "price_total": 302000, "currency": "KRW", "seats": 5,
     "link": "https://air-web.myrealtrip.com/results?trip=A.TPE.A.ICN", "link_kind": "search"},
    {"airline_code": "TW", "airline": "티웨이항공",
     "legs": [{"origin": "GMP", "destination": "CJU", "flightNumber": "TW727", "departDate": GO, "departTime": "18:30",
               "arriveDate": GO, "arriveTime": "19:45", "durationMinutes": 75}],
     "price_total": 64000, "currency": "KRW", "seats": None,
     "link": "https://flights.myrealtrip.com/air/b2c/x", "link_kind": "route_search"}],
    "total": 40, "cheapest_total": 64000, "confirmed_at": "2026-10-08T05:00:00+00:00", "source": "myrealtrip"}


class FakeLLM:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    async def complete(self, prompt_key, input_text, context, *, run_id=None):
        self.calls.append((prompt_key, input_text, context))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


#: 옛 소스별 도구 이름 → booking 모듈이 보는 `TravelSources` 칸. 시험은 소스마다 값을 주고, booking 모듈은 진짜로 돈다
SOURCE_SLOTS = {"read.flight_search": "travel_search", "read.flight_offers": "flight_offers", "read.flight_google": "flight_google"}


class StubSource:
    """어댑터 대신 — 정해 둔 값을 돌려주고 받은 인자를 남긴다."""

    def __init__(self, name, value, record):
        self.name, self.value, self.record = name, value, record

    def flight_search(self, **arguments):
        self.record.append((self.name, dict(arguments)))
        return self.value


class FakeTools:
    """`[2026-10-10]` 팀은 booking 도구 하나만 부른다. 소스별 값(`read.flight_search` 등)을 주면 진짜 booking 모듈에 가짜 어댑터로 넣어 돌린다."""

    def __init__(self, values):
        self.calls, self.source_calls = [], []
        travel = SimpleNamespace(**{slot: StubSource(name, values.get(name), self.source_calls)
                                    for name, slot in SOURCE_SLOTS.items()})
        self.values = {name: value for name, value in values.items() if name not in SOURCE_SLOTS}
        self.values.setdefault("read.booking_search_flights", lambda arguments: search_flights(travel, **arguments))

    def call(self, name, context, arguments, allowed_tools, seen, budget=None):
        if name not in allowed_tools:
            raise ToolNotAllowed(name)
        assert budget is None or len(seen) < budget, f"도구 예산 {budget} 을 넘겼다"
        seen.add(name + repr(sorted(arguments.items(), key=lambda pair: pair[0])))
        self.calls.append((name, dict(arguments)))
        value = self.values.get(name)
        return value(dict(arguments)) if callable(value) else value


def _run(reply, tools=None, *, text="다음 달 6일 타이베이에서 인천 가는 비행기 알아봐줘, 9일에 오는 편도", capability="flight.assist", llm=True, state=None):
    model, toolbox = FakeLLM(reply), FakeTools(tools or {})
    case_id = uuid4()
    pack = ContextPack(pack_id=uuid4(), case_id=case_id, team_id="flight", tenant_id="t", knowledge_scope=["flight"],
                       current_state={"customer_id": str(uuid4()), **(state or {})}, estimated_input_tokens=1)
    task = TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id="flight", capability=capability,
                    case_version=1, input_text=text, context=pack, allowed_tools=FlightTeam.manifest.allowed_tools,
                    deadline_at=datetime.now(UTC) + timedelta(seconds=90))
    return asyncio.run(FlightTeam(toolbox, model if llm else None).execute(task)), model, toolbox


def test_search_calls_the_model_once_and_both_sources_once():
    result, llm, tools = _run(SEARCH, {"read.flight_search": FLIGHTS})
    assert len(llm.calls) == 1 and llm.calls[0][0] == "flight.interpret"
    context = llm.calls[0][2]
    assert context["today"] == TODAY.isoformat() and len(context["calendar"]) == 70 and "trip" not in context, "달력을 준다(2026-10-10)"
    wanted = {"origin": "TPE", "destination": "ICN", "depart_date": GO, "return_date": None, "domestic": False,
              "direct_only": True, "cabin": None, "max_results": 100, "adults": 2, "children": None, "infants": None}
    assert tools.calls == [("read.booking_search_flights", wanted)], "팀은 booking 도구 하나만 부른다"
    given = {key: value for key, value in wanted.items() if value is not None}
    assert tools.source_calls == [("read.flight_search", given), ("read.flight_offers", given), ("read.flight_google", given)]
    assert result.outcome == "completed" and result.next_action.value == "respond"
    assert f"TPE → ICN · {GO} · 성인 2명 조건으로 찾은 결과(마이리얼트립 2개 · 판매처 비교 조회 실패 · 구글 항공권 조회 실패)를" in result.answer
    assert "출발 시간대마다 가장 싼 편을 보여 드립니다." in result.answer
    # 시간대 순서(새벽 → 저녁) — 오후 13:10 이 저녁 18:30 보다 먼저, 전체 최저가는 표시로 알린다
    assert f"1. [오후 최저가] 제주항공 — {GO} TPE 13:10 → ICN 16:40 (직항, 2시간 30분)" in result.answer
    assert "2. [저녁 최저가 · 전체 최저가] 티웨이항공 — " in result.answer
    assert "받은 결과에 새벽 · 오전 출발 편은 없었습니다" in result.answer, "없는 시간대는 「받은 결과에」 없다고 적는다"
    assert "가장 짧음" not in result.answer, "소요 시간을 모르거나 다 같으면 붙이지 않는다"
    assert "   · 마이리얼트립 302,000원 · 남은 좌석 5: https://air-web.myrealtrip.com/results?trip=A.TPE.A.ICN" in result.answer
    assert "TW727 (1시간 15분)" in result.answer, "국내선은 경유 칸이 없어 적지 않는다"
    assert "   · 마이리얼트립 64,000원\n" in result.answer, "국내선 편 줄에는 링크를 붙이지 않는다"
    assert "이 노선 · 날짜의 검색 결과 페이지(위 편을 목록에서 고르시면 됩니다): https://flights.myrealtrip.com/air/b2c/x" in result.answer
    assert [item.source_id for item in result.evidence] == ["flight.interpret", "read.booking_search_flights"]
    assert result.evidence[-1].value["sources"]["ignav"] == {"status": "failed"}


IGNAV = {"flights": [
    {"airline_code": "7C", "airline": "제주항공", "duration_minutes": 150, "stops": 0, "direct": True,
     "legs": [{**LEG, "flightNumber": "7C1501"}], "price_total": 289000.0, "currency": "KRW", "price_status": "verified",
     "seats": None, "seller": "제주항공", "seller_type": "airline", "link": "https://www.jejuair.net/x", "link_kind": "seller_airline"},
    {"airline_code": "BR", "airline": "에바항공", "duration_minutes": 140, "stops": 0, "direct": True,
     "legs": [{**LEG, "departTime": "09:00", "arriveTime": "12:20", "flightNumber": "BR160"}], "price_total": 350000.0,
     "currency": "KRW", "price_status": "verified", "seats": None, "seller": "Trip.com", "seller_type": "ota",
     "link": "https://www.trip.com/y", "link_kind": "seller_ota"}],
    "total": None, "source": "ignav"}


def test_the_same_flight_from_both_sources_is_shown_once_with_both_prices():
    result, _, _ = _run(SEARCH, {"read.flight_search": FLIGHTS, "read.flight_offers": IGNAV})
    answer = result.answer
    assert "찾은 결과(마이리얼트립 2개 · 항공사·여행사 판매처 2개 · 구글 항공권 조회 실패)를 같은 편끼리 묶어" in answer
    assert answer.count("TPE 13:10 → ICN 16:40") == 1, "같은 편은 한 번만"
    assert "TPE 13:10 → ICN 16:40 7C1501 (직항, 2시간 30분)" in answer, "편명은 묶인 Ignav 쪽에서 빌린다"
    jeju = answer.index("제주항공(항공사 공식) 289,000원: https://www.jejuair.net/x")
    assert jeju < answer.index("마이리얼트립 302,000원"), "같은 편 안에서도 싼 판매처가 먼저"
    assert "에바항공" in answer and "Trip.com(여행사) 350,000원: https://www.trip.com/y" in answer
    shown = result.decisions[0]["shown"]
    assert [(option["band"], option["best"]) for option in shown] == [
        ("morning", 350000.0), ("afternoon", 289000.0), ("evening", 64000)]
    assert [offer["source"] for offer in shown[1]["offers"]] == ["ignav", "myrealtrip"]
    assert result.decisions[0]["both"] == [{"flight": "7C1501", "depart": "13:10", "myrealtrip": 302000, "ignav": 289000.0}], \
        "두 소스가 다 판 편만, 소스별 최저가로"
    assert [item.source_id for item in result.evidence] == ["flight.interpret", "read.booking_search_flights"]


TEXT_MORNING = "다음 달 6일 타이베이에서 인천 가는 비행기 알아봐줘, 9일에 오는 편도 오전 출발로"


def test_a_time_of_day_the_customer_said_keeps_only_those_flights():
    result, _, _ = _run({**SEARCH, "depart_times": ["morning"], "depart_times_text": "오전 출발로"},
                        {"read.flight_search": FLIGHTS, "read.flight_offers": IGNAV}, text=TEXT_MORNING)
    assert "오전 출발 편을 가격이 낮은 순으로 1개 보여 드립니다." in result.answer
    assert "1. [오전] 에바항공 — " in result.answer
    assert "제주항공" not in result.answer and "티웨이항공" not in result.answer
    assert (result.decisions[0]["times"], result.decisions[0]["fallback"]) == (["morning"], False)


def test_several_times_of_day_show_the_cheapest_in_each_of_them():
    # `[2026-10-11]` 서버가 근거에 없는 시간대를 빼므로(flight.interpret.settle_years) 근거도 두 시간대를 말해야 한다
    result, _, _ = _run({**SEARCH, "depart_times": ["morning", "evening"], "depart_times_text": "오전이나 저녁 출발로"},
                        {"read.flight_search": FLIGHTS, "read.flight_offers": IGNAV},
                        text="다음 달 6일 타이베이에서 인천 가는 비행기 알아봐줘, 9일에 오는 편도 오전이나 저녁 출발로")
    assert "오전 · 저녁 출발 시간대마다 가장 싼 편을 보여 드립니다." in result.answer
    assert [option["band"] for option in result.decisions[0]["shown"]] == ["morning", "evening"], "오후는 고객이 빼지 않았어도 말한 것만"
    assert "1. [오전 최저가] 에바항공" in result.answer and "2. [저녁 최저가 · 전체 최저가] 티웨이항공" in result.answer


def test_a_time_of_day_with_nothing_found_shows_the_other_bands_and_says_so():
    result, _, _ = _run({**SEARCH, "depart_times": ["dawn"], "depart_times_text": "오전 출발로"},
                        {"read.flight_search": FLIGHTS, "read.flight_offers": IGNAV}, text=TEXT_MORNING)
    assert "새벽 출발 편이 없어, 다른 출발 시간대마다 가장 싼 편을 보여 드립니다" in result.answer
    assert [option["band"] for option in result.decisions[0]["shown"]] == ["morning", "afternoon", "evening"]
    assert result.decisions[0]["fallback"] is True and "받은 결과에 새벽" not in result.answer


def test_a_time_of_day_not_in_the_message_is_cleared():
    result, _, _ = _run({**SEARCH, "depart_times": ["morning"], "depart_times_text": "오전"},
                        {"read.flight_search": FLIGHTS, "read.flight_offers": IGNAV})
    assert result.decisions[0]["ungrounded"] == ["depart_times"]
    assert result.decisions[0]["times"] is None and "출발 시간대마다 가장 싼 편을" in result.answer


def test_time_of_day_shape():
    assert parse({**SEARCH, "depart_times": []}).depart_times is None
    assert parse({**SEARCH, "depart_times": ["morning", "evening"]}).depart_times == ["morning", "evening"]
    with pytest.raises(InterpretationInvalid):
        parse({**SEARCH, "depart_times": ["noon"]})


SLOW = {"airline_code": "5J", "airline": "세부퍼시픽항공", "duration_minutes": 685,
        "legs": [{**LEG, "departTime": "06:35", "arriveTime": "18:00", "durationMinutes": 685, "stops": 1, "isDirect": False}],
        "price_total": 732000, "currency": "KRW", "seats": 9, "link": "https://air-web.myrealtrip.com/results?x=5J",
        "link_kind": "search"}


def test_a_slow_connecting_flight_is_not_a_band_pick_when_direct_flights_exist():
    """☆2026-10-09 14:46 playdata 인천→나리타 — 새벽 최저가가 경유 11시간 25분 732,000원이었다."""
    result, _, _ = _run(SEARCH, {"read.flight_search": {**FLIGHTS, "flights": [*FLIGHTS["flights"], SLOW]},
                                 "read.flight_offers": IGNAV})
    assert "세부퍼시픽" not in result.answer and result.decisions[0]["dropped_slow"] == 1
    assert "새벽 출발은 경유로 직항보다 2배 넘게 걸리는 편뿐이라 뺐습니다." in result.answer
    assert "받은 결과에 새벽" not in result.answer


def test_a_connecting_flight_stays_when_there_is_no_direct_one():
    only = {**FLIGHTS, "flights": [SLOW]}
    result, _, _ = _run(SEARCH, {"read.flight_search": only})
    assert "1. [새벽 최저가 · 전체 최저가] 세부퍼시픽항공" in result.answer and result.decisions[0]["dropped_slow"] == 0


def test_the_answer_ends_with_the_same_search_on_sites_koreans_use():
    result, _, _ = _run(SEARCH, {"read.flight_search": FLIGHTS})
    day, short = GO.replace("-", ""), GO[2:].replace("-", "")
    assert "같은 조건으로 다른 곳에서 보기(가격은 그 사이트에서 확인):" in result.answer
    assert f"   · 네이버 항공권: https://flight.naver.com/flights/international/TPE-ICN-{day}?adult=2&child=0&infant=0&fareType=Y" in result.answer
    assert f"   · 스카이스캐너: https://www.skyscanner.co.kr/transport/flights/tpe/icn/{short}/?adultsv2=2&cabinclass=economy&rtn=0" in result.answer
    assert (f"   · 트립닷컴: https://kr.trip.com/flights/showfarefirst?dcity=tpe&acity=sel&dairport=tpe&aairport=icn&ddate={GO}"
            "&flighttype=ow&class=y&quantity=2&searchboxarg=t&locale=ko-KR&curr=KRW") in result.answer, "도시(인천→서울) + 공항 코드"
    assert f"   · NOL 인터파크 투어: https://tour.yanolja.com/air/search/a:TPE-a:ICN-{day}?cabin=ECONOMY&infant=0&child=0&adult=2" in result.answer
    assert f"   · 카약: https://www.kayak.co.kr/flights/TPE-ICN/{GO}/2adults?sort=bestflight_a" in result.answer


FAST_VIA = {"airline_code": "MM", "airline": "피치항공", "legs": [{**LEG, "departTime": "05:30", "arriveTime": "07:50",
                                                              "durationMinutes": 140, "stops": 1, "isDirect": False}],
            "price_total": 150000, "currency": "KRW", "seats": None, "link": "https://air-web.myrealtrip.com/results?x=MM",
            "link_kind": "search"}


def test_only_direct_flights_unless_the_traveller_says_connecting_is_fine():
    """`[2026-10-10 사용자 결정]` 말하지 않으면 직항만 — 느린 경유 거르기(직항 2배)에 안 걸리는 경유도 뺀다."""
    flights = {**FLIGHTS, "flights": [*FLIGHTS["flights"], FAST_VIA]}
    result, _, tools = _run({**SEARCH, "direct_only": None}, {"read.flight_search": flights})
    assert "피치항공" not in result.answer and result.decisions[0]["dropped_connecting"] == 1
    assert "새벽 출발은 경유 편뿐이라 뺐습니다(직항만 보여 드립니다. 경유도 괜찮으시면 말씀해 주세요)." in result.answer
    assert tools.source_calls[0][1].get("direct_only") is None, "소스에는 고객이 말한 값만 보낸다"
    result, _, _ = _run({**SEARCH, "direct_only": False}, {"read.flight_search": flights})
    assert "피치항공" in result.answer and result.decisions[0]["dropped_connecting"] == 0, "경유도 괜찮다고 하면 그대로"
    result, _, _ = _run({**SEARCH, "direct_only": None}, {"read.flight_search": {**FLIGHTS, "flights": [FAST_VIA]}})
    assert "피치항공" in result.answer and "받은 결과에 직항이 없어 경유 편을 보여 드립니다." in result.answer
    assert result.decisions[0]["no_direct"] is True


def test_a_round_trip_elsewhere_link_carries_both_dates():
    result, _, _ = _run({**SEARCH, "return_date": BACK, "return_date_text": "9일에 오는"}, {"read.flight_search": FLIGHTS})
    assert f"TPE-ICN-{GO.replace('-', '')}/ICN-TPE-{BACK.replace('-', '')}" in result.answer
    assert f"/{BACK[2:].replace('-', '')}/?adultsv2=2&cabinclass=economy&rtn=1" in result.answer
    assert f"&rdate={BACK}&flighttype=rt" in result.answer


GOOGLE = {"flights": [
    {"airline_code": "7C", "airline": "제주항공", "duration_minutes": 150, "stops": 0, "direct": True,
     "legs": [{**LEG, "flightNumber": "7C1501"}], "price_total": 280000.0, "currency": "KRW", "seats": None,
     "link": "https://www.google.com/travel/flights?hl=ko&gl=kr&curr=KRW&tfs=x", "link_kind": "route_search"}],
    "total": None, "source": "serpapi_flights"}


def test_google_flights_is_a_third_price_on_the_same_flight_with_one_page_link():
    result, _, _ = _run(SEARCH, {"read.flight_search": FLIGHTS, "read.flight_offers": IGNAV, "read.flight_google": GOOGLE})
    answer = result.answer
    assert "찾은 결과(마이리얼트립 2개 · 항공사·여행사 판매처 2개 · 구글 항공권 1개)를" in answer
    assert answer.count("TPE 13:10 → ICN 16:40") == 1, "세 소스의 같은 편은 한 번만"
    assert "   · 구글 항공권 280,000원\n" in answer, "구글 항공권은 편 줄에 링크를 붙이지 않는다"
    assert answer.index("구글 항공권 280,000원") < answer.index("제주항공(항공사 공식) 289,000원"), "싼 순"
    assert "구글 항공권 이 노선 · 날짜의 검색 결과 페이지(위 편을 목록에서 고르시면 됩니다): https://www.google.com/travel/flights?" in answer
    assert "마이리얼트립 이 노선 · 날짜의 검색 결과 페이지" in answer
    assert result.evidence[-1].value["sources"]["google"] == {"status": "ok", "count": 1}


def test_a_round_trip_shows_the_google_round_trip_lowest_as_a_reference_line():
    google = {"flights": [], "note": "왕복은 편별 대신 최저가 참고", "round_trip_lowest": 245000.0,
              "page": "https://www.google.com/travel/flights?hl=ko&tfs=rt", "source": "serpapi_flights"}
    result, _, _ = _run({**SEARCH, "return_date": BACK, "return_date_text": "9일에 오는"},
                        {"read.flight_search": FLIGHTS, "read.flight_google": google})
    assert "구글 항공권 왕복 최저가 참고)를" in result.answer
    assert ("구글 항공권 왕복 최저 참고 245,000원(가는 편 · 오는 편 합, 편별 비교 안 함): "
            "https://www.google.com/travel/flights?hl=ko&tfs=rt") in result.answer


def test_a_mixed_carrier_round_trip_is_flagged_and_same_price_offers_are_one_line():
    back = {**LEG, "origin": "ICN", "destination": "TPE", "departDate": BACK, "arriveDate": BACK, "flightNumber": "BR169"}
    go = {**LEG, "flightNumber": "7C1501"}
    one = {"airline_code": "7C", "airline": "제주항공", "duration_minutes": 150, "legs": [go, back], "price_total": 400000.0,
           "currency": "KRW", "seller": "제주항공", "link": "https://www.jejuair.net/a?gclid=1", "link_kind": "seller_airline"}
    twin = {**one, "link": "https://www.jejuair.net/a?gclid=2"}
    result, _, _ = _run({**SEARCH, "return_date": BACK, "return_date_text": "9일에 오는"},
                        {"read.flight_search": {"flights": [one, twin], "source": "myrealtrip"}})
    assert result.answer.count("마이리얼트립 400,000원") == 1, "링크만 다른 같은 판매처 · 같은 가격은 한 줄"
    assert "   ※ 가는 편과 오는 편 항공사가 달라(7C · BR) 따로 예약해야 할 수 있습니다." in result.answer


def test_myrealtrip_resting_after_a_429_is_said_as_resting_not_failed():
    result, _, _ = _run(SEARCH, {"read.flight_search": {"cooldown_seconds": 540, "source": "myrealtrip"},
                                 "read.flight_offers": IGNAV})
    assert "마이리얼트립은 요청 한도로 잠시 조회를 쉬는 중 · 항공사·여행사 판매처 2개" in result.answer
    assert result.evidence[-1].value["sources"]["myrealtrip"] == {"status": "resting", "cooldown_seconds": 540}
    assert "제주항공(항공사 공식) 289,000원" in result.answer


def test_one_source_is_enough_and_both_missing_is_unknown():
    result, _, _ = _run(SEARCH, {"read.flight_search": None, "read.flight_offers": IGNAV})
    assert result.outcome == "completed" and "찾은 결과(마이리얼트립 조회 실패 · 항공사·여행사 판매처 2개 · 구글 항공권 조회 실패)를" in result.answer
    result, _, _ = _run(SEARCH, {})
    assert (result.outcome, result.failure_code) == ("escalated", "unknown_항공편 검색 결과")


def test_a_round_trip_passes_the_return_date():
    result, _, tools = _run({**SEARCH, "return_date": BACK, "return_date_text": "9일에 오는"}, {"read.flight_search": FLIGHTS})
    assert tools.calls[0][1]["return_date"] == BACK
    assert [name for name, _ in tools.source_calls] == ["read.flight_search", "read.flight_google"], "왕복은 Ignav 를 부르지 않는다"
    assert "항공사·여행사 판매처는 편도만" in result.answer
    assert "같은 편끼리 묶어" not in result.answer, "편 목록을 준 소스가 하나뿐이면 묶었다고 하지 않는다"


def test_missing_values_are_asked_back_without_any_search():
    reply = {**SEARCH, "origin": None, "depart_date": None, "adults": None, "domestic": None,
             "missing": ["origin", "depart_date", "adults"], "question": "어디서, 언제, 몇 분이 출발하시나요?"}
    result, _, tools = _run(reply)
    assert tools.calls == [] and result.answer == "어디서, 언제, 몇 분이 출발하시나요?"
    assert result.decisions[0]["needs"] == ["origin", "depart_date", "adults"]


def test_the_server_recounts_what_is_missing():
    # `[2026-10-10]` 연도를 말하지 않은 지난 날짜는 서버가 다음 해로 옮기므로(settle_years), 연도를 **말한** 지난 날짜로 본다
    day = TODAY - timedelta(days=1)
    quote = f"{day.year}년 {day.month}월 {day.day}일"
    result, _, tools = _run({**SEARCH, "depart_date": day.isoformat(), "depart_date_text": quote}, text=f"{quote} 타이베이에서 인천 2명")
    assert tools.calls == [] and result.decisions[0]["needs"] == ["depart_date"] and "출발 날짜" in result.answer
    result, _, _ = _run({**SEARCH, "destination": "TPE"})
    assert result.decisions[0]["needs"] == ["destination"]
    early = _NEXT.replace(day=5).isoformat()          # 떠나는 날(6일)보다 앞
    result, _, _ = _run({**SEARCH, "return_date": early, "return_date_text": "5일에 오는"},
                        text="다음 달 6일 타이베이에서 인천 가는 비행기 알아봐줘, 5일에 오는")
    assert result.decisions[0]["needs"] == ["return_date"]


def test_no_flights_and_unreadable_search_are_different():
    result, _, _ = _run(SEARCH, {"read.flight_search": {**FLIGHTS, "flights": [], "total": 0}})
    assert result.outcome == "completed" and "찾은 항공편이 없습니다" in result.answer
    result, _, _ = _run(SEARCH, {"read.flight_search": None})
    assert (result.outcome, result.failure_code) == ("escalated", "unknown_항공편 검색 결과")


@pytest.mark.parametrize("reply,code", [
    ({"task": "book"}, "interpretation_invalid"),
    ({**SEARCH, "origin": "타이베이"}, "interpretation_invalid"),
    ({**SEARCH, "domestic": None}, "interpretation_invalid"),
    ({**SEARCH, "cabin": "PREMIUM"}, "interpretation_invalid"),
    (RuntimeError("no active prompt registered for flight.interpret"), "interpretation_failed"),
])
def test_a_bad_or_failed_interpretation_is_not_repaired(reply, code):
    result, _, tools = _run(reply)
    assert (result.outcome, result.failure_code, tools.calls) == ("escalated", code, [])


def test_without_a_model_and_other_branches():
    assert _run(SEARCH, llm=False)[0].failure_code == "interpreter_missing"
    result, _, tools = _run({"task": "unclear"})
    assert tools.calls == [] and result.decisions[0]["needs"] == ["task"]
    result, llm, tools = _run(SEARCH, {"read.booking": {"booking_id": "b1"}}, capability="flight.status")
    assert llm.calls == [] and [c[0] for c in tools.calls] == ["read.booking"] and "잠긴 예약" in result.answer


def test_a_trip_on_the_case_is_summarised_for_the_model():
    view = {"trip": {"party_size": 2}, "items": [{"title": "경복궁", "starts_at": "2026-11-06T10:00:00+09:00"}]}
    _, llm, tools = _run({"task": "unclear"}, {"read.itinerary": view}, state={"subject_ref": {"kind": "trip", "id": "T1"}})
    assert tools.calls[0] == ("read.itinerary", {"trip_id": "T1"})
    assert llm.calls[0][2]["trip"] == {"party_size": 2, "first_day": "2026-11-06", "last_day": "2026-11-06", "places": ["경복궁"]}


def test_parse_needs_and_registration():
    found = parse({**SEARCH, "origin": " ", "domestic": None})
    assert found.origin is None and needs(found, today=TODAY) == ["origin"]
    with pytest.raises(InterpretationInvalid):
        parse({**SEARCH, "adults": 0})
    assert "flight.interpret" in ALLOWED_PROMPT_KEYS
    from pathlib import Path

    files = list(Path("prompts/flight").glob("interpret.v*.md"))
    assert len(files) == 1 and "flight team" in files[0].read_text(encoding="utf-8")
    assert FlightTeam.manifest.default_capability == "flight.assist"


def test_a_rejected_value_is_shown_back_instead_of_asked_as_if_missing():
    """☆2026-10-08 14:58 playdata — 「11월 6일」이 2023-11-06 으로 옮겨졌다. 날짜를 말한 고객에게 날짜가 없다고 묻지 않는다.

    `[2026-10-10]` 연도를 말하지 않은 날짜는 이제 서버가 연도를 고친다(아래 시험). 연도를 **말한** 지난 날짜는 그대로 되묻는다."""
    result, _, tools = _run({**SEARCH, "depart_date": "2023-11-06", "return_date": "2023-11-09", "domestic": True,
                             "origin": "GMP", "destination": "CJU", "depart_date_text": "2023년 11월 6일"},
                            text="2023년 11월 6일 김포에서 제주 가는 비행기 2명")
    assert tools.calls == [] and result.decisions[0]["needs"] == ["depart_date"]
    assert result.answer.startswith("출발 날짜 2023-11-06(으)로 읽었는데 지난 날짜이거나")


def test_a_date_without_a_year_gets_the_year_from_today():
    """☆2026-10-10 17:47 playdata 해석 측정 — 「10월 3일」(지난 날)을 2026-10-03 으로 옮겼다. 규칙대로면 다음 해다."""
    past = TODAY - timedelta(days=7)
    wrong = past.isoformat()
    result, _, tools = _run({**SEARCH, "depart_date": wrong, "depart_date_text": f"{past.month}월 {past.day}일"},
                            {"read.flight_search": FLIGHTS}, text=f"{past.month}월 {past.day}일 타이베이에서 인천 2명")
    fixed = result.decisions[0]["interpretation"]["depart_date"]
    assert fixed > TODAY.isoformat() and fixed[5:] == wrong[5:], "월 · 일은 그대로, 연도만"
    assert result.decisions[0]["year_fixed"] == ["depart_date"] and tools.calls[0][1]["depart_date"] == fixed


def test_an_ungrounded_flight_date_is_cleared():
    result, _, tools = _run({**SEARCH, "depart_date_text": "내일"}, text="타이베이에서 인천 가는 비행기 2명")
    assert tools.calls == [] and result.decisions[0]["ungrounded"] == ["depart_date"]
    assert result.decisions[0]["needs"] == ["depart_date"]


def test_a_per_person_price_cap_keeps_only_flights_under_it_and_says_how_it_counted():
    """`[2026-10-11]` ☆사용자 문장 「가격은 왕복으로 50을 안넘었으면」 — 받는 칸이 없어 말없이 버려졌다."""
    result, _, _ = _run({**SEARCH, "max_price": 100000}, {"read.flight_search": FLIGHTS})
    assert "제주항공" not in result.answer and "티웨이항공" in result.answer, "2명 302,000원 = 1인 151,000원은 넘는다"
    assert "1인 100,000원 이하 편만 골랐습니다(가격 ÷ 인원으로 셈)." in result.answer
    assert result.decisions[0]["price_cap"] == {"per_person": 100000, "people": 2, "within": 1}
    result, _, _ = _run({**SEARCH, "max_price": 10000}, {"read.flight_search": FLIGHTS})
    assert "1인 10,000원 이하 편이 받은 결과에 없어 가장 싼 편들을 보여 드립니다" in result.answer and "제주항공" in result.answer
    result, _, _ = _run({**SEARCH, "max_price": 50}, {"read.flight_search": FLIGHTS})
    assert result.decisions[0]["price_cap"]["per_person"] == 500000, "맨숫자는 만 원 단위"


def test_return_times_pick_the_return_leg_band():
    from app.domains.travel_ops.instances.flight.interpret import parse
    from app.domains.travel_ops.instances.flight.team import _apply_limits

    def option(back_time, price):
        return {"legs": [{**LEG}, {**LEG, "origin": "ICN", "destination": "TPE", "departTime": back_time}], "best": price}
    pool = [option("09:00", 200000), option("15:00", 250000)]
    found = parse({**SEARCH, "return_date": BACK, "return_times": ["afternoon"], "return_times_text": "오후"})
    kept, notes, record = _apply_limits(pool, found)
    assert [item["legs"][1]["departTime"] for item in kept] == ["15:00"] and notes == ["오는 편은 오후 출발 편만 골랐습니다."]
    found = parse({**SEARCH, "return_date": BACK, "return_times": ["evening"], "return_times_text": "저녁"})
    kept, notes, _ = _apply_limits(pool, found)
    assert len(kept) == 2 and notes == ["받은 결과에 오는 편 저녁 출발이 없어 오는 편 시간은 가리지 않았습니다."]


def test_wishes_without_a_slot_are_named_at_the_end():
    text = "다음 달 6일 타이베이에서 인천 가는 비행기 알아봐줘, 9일에 오는 편도 창가 좌석으로"
    result, _, _ = _run({**SEARCH, "other_requests": ["창가 좌석", "지어낸 조건"]}, {"read.flight_search": FLIGHTS}, text=text)
    assert result.answer.endswith("말씀하신 조건 중 아직 반영하지 못한 것: 「창가 좌석」 — 링크한 화면에서 직접 확인해 주세요."), \
        "문장에 없는 조각은 버린다"


# ── 일정 항공편 항목 — `flight.itinerary` (2026-10-11, 숙소 팀과 같은 모양) ─────────
TRIP_ID, LEG_ID = "11111111-1111-4111-8111-111111111111", "99999999-9999-4999-8999-999999999999"


def _plan(kind="flight", detail=None, booking_id=None):
    leg = {"item_id": LEG_ID, "seq": 1, "kind": kind, "title": "타이베이 → 인천", "place_id": None,
           "starts_at": f"{GO}T12:00:00+09:00", "ends_at": f"{GO}T15:30:00+09:00", "locked": False,
           "booking_id": booking_id, "replaces_item_id": None, "place": None,
           "detail": {"origin": "TPE", "destination": "ICN", **(detail or {})}}
    return {"trip": {"trip_id": TRIP_ID, "version": 5, "party_size": 2, "customer_id": "c"}, "items": [leg]}


LEG_STATE = {"subject_ref": {"kind": "trip", "id": TRIP_ID, "part_id": LEG_ID, "base_version": 5},
             "interpretation": {"report": {"type": "change"}}, "request_id": "r-flight-1"}
WITH_VIA = {**FLIGHTS, "flights": [*FLIGHTS["flights"], FAST_VIA]}
TW_KEY, JEJU_KEY, VIA_KEY = f"티웨이항공 TW727 {GO} 18:30", f"제주항공 ? {GO} 13:10", f"피치항공 ? {GO} 05:30"


def _legrun(plan):
    return _run({"task": "unclear"}, {"read.itinerary": plan, "read.flight_search": WITH_VIA},
                text="이 비행기 다른 걸로 바꿔줘", capability="flight.itinerary", state=LEG_STATE)


def test_a_case_pointing_at_a_flight_item_is_itinerary_work_and_a_bare_trip_stays_assist():
    ref = {"kind": "trip", "id": TRIP_ID, "part_id": LEG_ID}
    assert FlightTeam.select_capability(None, "x", {"subject_ref": ref}) == "flight.itinerary"
    assert FlightTeam.select_capability(None, "x", {"subject_ref": {"kind": "trip", "id": TRIP_ID}}) is None
    assert FlightTeam.select_capability(None, "x", {"subject_ref": ref, "interpretation": {"report": {"type": "question"}}}) \
        == "flight.itinerary_question"
    manifest = FlightTeam.manifest
    assert {"flight.itinerary", "flight.itinerary_question"} <= set(manifest.capabilities)
    assert "policy" in manifest.required_context
    assert set(manifest.policy_optional_capabilities) == {"flight.assist", "flight.status", "flight.itinerary"}


def test_change_on_a_flight_item_holds_new_direct_flights_like_dining_and_activity():
    result, llm, tools = _legrun(_plan())
    assert llm.calls == [], "일정 항목에서 읽는다 — 모델을 부르지 않는다"
    searches = [arguments for name, arguments in tools.calls if name == "read.booking_search_flights"]
    assert searches == [{"origin": "TPE", "destination": "ICN", "depart_date": GO, "domestic": False, "adults": 2, "max_results": 100}]
    assert result.answer == ("타이베이 → 인천 대신 탈 수 있는 편이에요 — 1) 제주항공 13:10(1인 151,000원) · "
                             "2) 티웨이항공 TW727 18:30(1인 32,000원). 고르시면 바꿀게요. 고르지 않으시면 원래 일정을 그대로 둡니다."), \
        "원래 12:00 편 — 앞뒤 3시간 안(13:10)이 더 싼 18:30 보다 먼저(사용자 결정 10-12)"
    (proposal,) = result.action_proposals
    assert proposal.action_type == "itinerary.apply" and proposal.arguments["reason"] == "customer_request"
    new = proposal.arguments["replacements"][0]["item"]
    assert new["kind"] == "flight" and new["detail"]["origin"] == "TPE" and new["starts_at"] == f"{GO}T12:00:00+09:00", "편은 그대로"
    options = new["detail"]["alternates"]
    assert [(o["rank"], o["key"]) for o in options] == [(1, JEJU_KEY), (2, TW_KEY)]
    assert {"key", "name", "place_id", "starts_at", "ends_at", "walk_min"} <= set(options[0]), "식당 · 활동의 「다른 안」 칸"
    assert options[1]["starts_at"] == f"{GO}T18:30:00+09:00" and options[1]["per_person"] == 32000 and options[1]["best"] == 64000
    assert "피치항공" not in result.answer, "직항이 있으면 직항만(사용자 결정 10-10)"
    assert new["detail"]["shown"] == [JEJU_KEY, TW_KEY]
    assert proposal.arguments["summary"]["near_original"] == 1


def test_choosing_a_flight_moves_the_item_to_its_departure_and_keeps_the_old_one_as_an_option():
    plan = _plan()
    first, _, _ = _legrun(plan)
    plan["items"][0]["detail"] = first.action_proposals[0].arguments["replacements"][0]["item"]["detail"]
    state = {**LEG_STATE, "subject_ref": {**LEG_STATE["subject_ref"], "request": {"type": "change", "choice": JEJU_KEY}}}
    result, _, tools = _run({"task": "unclear"}, {"read.itinerary": plan}, text="2번", capability="flight.itinerary", state=state)
    assert [name for name, _ in tools.calls] == ["read.itinerary"], "고르면 다시 찾지 않는다"
    assert result.answer.startswith("요청하신 대로 타이베이 → 인천 대신 제주항공 13:10(으)로 바꿨습니다. 아직 예약 전이에요")
    new = result.action_proposals[0].arguments["replacements"][0]["item"]
    assert new["starts_at"] == f"{GO}T13:10:00+09:00" and new["ends_at"] is None
    assert new["detail"]["chosen"]["key"] == JEJU_KEY and new["detail"]["key"] == JEJU_KEY and new["detail"]["booked"] is False
    assert [o["name"] for o in new["detail"]["alternates"]] == ["티웨이항공 TW727 18:30", "타이베이 → 인천"]


def test_when_no_new_direct_flight_is_left_connecting_ones_are_held_and_said():
    result, _, _ = _legrun(_plan(detail={"shown": [TW_KEY, JEJU_KEY]}))
    assert result.answer == ("타이베이 → 인천 대신 탈 수 있는 편이에요 — 1) 피치항공 05:30(1인 75,000원). 새로 보여 드릴 직항이 없어 경유 편이에요. "
                             "원래 출발(12:00) 앞뒤 3시간 안에는 새 편이 없어 다른 시간대예요. 고르시면 바꿀게요. 고르지 않으시면 원래 일정을 그대로 둡니다.")
    assert result.action_proposals[0].arguments["summary"]["widened_to_connecting"] is True
    assert result.action_proposals[0].arguments["replacements"][0]["item"]["detail"]["shown"] == [TW_KEY, JEJU_KEY, VIA_KEY]


def test_new_flights_near_the_original_departure_come_first_then_the_rest_by_price():
    from app.domains.travel_ops.instances.flight.team import _fresh_flights

    def flight(clock, price):
        return {"airline": "A", "legs": [{**LEG, "departTime": clock, "flightNumber": clock}], "best": price}

    by_price = [flight("15:00", 100), flight("16:00", 200), flight("09:30", 300), flight("11:00", 400), flight("07:00", 500)]
    picked = _fresh_flights(by_price, set(), direct_only=True, around=10 * 60)
    assert [o["legs"][0]["departTime"] for o in picked] == ["09:30", "11:00", "07:00"], "10:00 앞뒤 3시간 안 셋 — 가격순"
    picked = _fresh_flights(by_price[:3], set(), direct_only=True, around=10 * 60)
    assert [o["legs"][0]["departTime"] for o in picked] == ["09:30", "15:00", "16:00"], "모자라면 나머지 가격순"
    picked = _fresh_flights(by_price, set(), direct_only=True)
    assert [o["legs"][0]["departTime"] for o in picked] == ["15:00", "16:00", "09:30"], "시각을 모르면 가격순 그대로"


def test_the_booking_link_skips_a_results_page_and_says_why():
    """`[2026-10-12]` ☆이스타 편 — 가장 싼 판매처가 구글 항공권(결과 페이지)이면 그 편을 바로 고를 수 있는 다음 판매처 링크를 쓴다."""
    from app.domains.travel_ops.instances.flight.team import _booking_note, _flight_option

    item = SimpleNamespace(starts_at=datetime.fromisoformat(f"{GO}T10:00:00+09:00"))
    option = {"airline": "이스타항공", "legs": [{**LEG, "flightNumber": "ZE607"}], "best": 300000,
              "offers": [{"label": "구글 항공권", "price_total": 300000, "link": "https://www.google.com/travel/flights?x", "link_kind": "route_search"},
                         {"label": "마이리얼트립", "price_total": 320000, "link": "https://air.myrealtrip.com/x", "link_kind": "search"}]}
    pick = _flight_option(1, option, item, 2)
    assert pick["seller"] == "구글 항공권" and pick["per_person"] == 150000, "가장 싼 값은 그대로 보인다"
    assert (pick["link"], pick["link_seller"], pick["link_price"]) == ("https://air.myrealtrip.com/x", "마이리얼트립", 320000)
    assert _booking_note(pick, 2) == (" — 가장 싼 구글 항공권은(는) 검색 결과 페이지라, 바로 예약할 수 있는 마이리얼트립(1인 160,000원) 링크예요: "
                                      "https://air.myrealtrip.com/x")
    only_page = _flight_option(1, {**option, "offers": option["offers"][:1]}, item, 2)
    assert only_page["link_kind"] == "route_search"
    assert _booking_note(only_page, 2).startswith(" — 이 편은 검색 결과 페이지만 있어요. 그 화면에서 이스타항공 ZE607 13:10 편을 골라")


def test_when_nothing_new_is_left_it_says_so_without_changing_the_plan():
    result, _, _ = _legrun(_plan(detail={"shown": [TW_KEY, JEJU_KEY, VIA_KEY]}))
    assert result.action_proposals == []
    assert result.answer == "타이베이 → 인천 대신 탈 수 있는 편을 더 찾지 못했어요. 일정은 그대로 두었어요."


def test_a_booked_flight_is_never_changed_and_nothing_is_searched():
    result, _, tools = _legrun(_plan(booking_id="88888888-8888-4888-8888-888888888888"))
    assert "이미 예약하신 항공편이라 바꾸지 않았어요" in result.answer and result.action_proposals == []
    assert [name for name, _ in tools.calls] == ["read.itinerary"]


def test_a_non_flight_item_or_a_missing_airport_is_not_guessed():
    result, _, _ = _legrun(_plan(kind="lodging"))
    assert result.outcome == "escalated" and result.failure_code == "target_kind_mismatch"
    plan = _plan()
    del plan["items"][0]["detail"]["origin"]
    result, _, tools = _legrun(plan)
    assert result.outcome == "escalated" and result.failure_code.startswith("unknown_")
    assert [name for name, _ in tools.calls] == ["read.itinerary"]
