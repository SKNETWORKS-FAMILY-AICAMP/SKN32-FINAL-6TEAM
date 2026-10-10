# -*- coding: utf-8 -*-
"""항공 팀 — 모델은 해석(공항 코드 포함)만 하고, 서버가 검증 · 조회 · 답을 맡는지 본다. 모델과 도구는 가짜다."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core.contracts import ContextPack, TeamTask, ToolNotAllowed
from app.domains.travel_ops.instances.flight import FlightTeam
from app.domains.travel_ops.instances.flight.interpret import InterpretationInvalid, needs, parse
from app.tools.read_tools import ALLOWED_PROMPT_KEYS

TODAY = datetime.now(ZoneInfo("Asia/Seoul")).date()
GO, BACK = (TODAY + timedelta(days=30)).isoformat(), (TODAY + timedelta(days=33)).isoformat()
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


class FakeTools:
    def __init__(self, values):
        self.values, self.calls = values, []

    def call(self, name, context, arguments, allowed_tools, seen, budget=None):
        if name not in allowed_tools:
            raise ToolNotAllowed(name)
        assert budget is None or len(seen) < budget, f"도구 예산 {budget} 을 넘겼다"
        seen.add(name + repr(sorted(arguments.items(), key=lambda pair: pair[0])))
        self.calls.append((name, dict(arguments)))
        return self.values.get(name)


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
    assert len(llm.calls) == 1 and llm.calls[0][0] == "flight.interpret" and llm.calls[0][2] == {"today": TODAY.isoformat()}
    wanted = {"origin": "TPE", "destination": "ICN", "depart_date": GO, "return_date": None, "domestic": False,
              "direct_only": True, "cabin": None, "max_results": 100, "adults": 2, "children": None, "infants": None}
    assert tools.calls == [("read.flight_search", wanted), ("read.flight_offers", wanted), ("read.flight_google", wanted)]
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
    # 판매처 비교가 None(조회 실패)이면 근거로 붙이지 않는다 — `_base._evidence` 「값이 비면 붙이지 않는다」
    assert [item.source_id for item in result.evidence] == ["flight.interpret", "read.flight_search"]


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
    assert [item.source_id for item in result.evidence] == ["flight.interpret", "read.flight_search", "read.flight_offers"]


TEXT_MORNING = "다음 달 6일 타이베이에서 인천 가는 비행기 알아봐줘, 9일에 오는 편도 오전 출발로"


def test_a_time_of_day_the_customer_said_keeps_only_those_flights():
    result, _, _ = _run({**SEARCH, "depart_times": ["morning"], "depart_times_text": "오전 출발로"},
                        {"read.flight_search": FLIGHTS, "read.flight_offers": IGNAV}, text=TEXT_MORNING)
    assert "오전 출발 편을 가격이 낮은 순으로 1개 보여 드립니다." in result.answer
    assert "1. [오전] 에바항공 — " in result.answer
    assert "제주항공" not in result.answer and "티웨이항공" not in result.answer
    assert (result.decisions[0]["times"], result.decisions[0]["fallback"]) == (["morning"], False)


def test_several_times_of_day_show_the_cheapest_in_each_of_them():
    result, _, _ = _run({**SEARCH, "depart_times": ["morning", "evening"], "depart_times_text": "오전 출발로"},
                        {"read.flight_search": FLIGHTS, "read.flight_offers": IGNAV}, text=TEXT_MORNING)
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
    assert [item.source_id for item in result.evidence][-1] == "read.flight_google"


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


def test_one_source_is_enough_and_both_missing_is_unknown():
    result, _, _ = _run(SEARCH, {"read.flight_search": None, "read.flight_offers": IGNAV})
    assert result.outcome == "completed" and "찾은 결과(마이리얼트립 조회 실패 · 항공사·여행사 판매처 2개 · 구글 항공권 조회 실패)를" in result.answer
    result, _, _ = _run(SEARCH, {})
    assert (result.outcome, result.failure_code) == ("escalated", "unknown_항공편 검색 결과")


def test_a_round_trip_passes_the_return_date():
    result, _, tools = _run({**SEARCH, "return_date": BACK, "return_date_text": "9일에 오는"}, {"read.flight_search": FLIGHTS})
    assert tools.calls[0][1]["return_date"] == BACK
    assert [name for name, _ in tools.calls] == ["read.flight_search", "read.flight_google"], "왕복은 Ignav 를 부르지 않는다"
    assert "항공사·여행사 판매처는 편도만" in result.answer
    assert "같은 편끼리 묶어" not in result.answer, "편 목록을 준 소스가 하나뿐이면 묶었다고 하지 않는다"


def test_missing_values_are_asked_back_without_any_search():
    reply = {**SEARCH, "origin": None, "depart_date": None, "adults": None, "domestic": None,
             "missing": ["origin", "depart_date", "adults"], "question": "어디서, 언제, 몇 분이 출발하시나요?"}
    result, _, tools = _run(reply)
    assert tools.calls == [] and result.answer == "어디서, 언제, 몇 분이 출발하시나요?"
    assert result.decisions[0]["needs"] == ["origin", "depart_date", "adults"]


def test_the_server_recounts_what_is_missing():
    past = (TODAY - timedelta(days=1)).isoformat()
    result, _, tools = _run({**SEARCH, "depart_date": past})
    assert tools.calls == [] and result.decisions[0]["needs"] == ["depart_date"] and "출발 날짜" in result.answer
    result, _, _ = _run({**SEARCH, "destination": "TPE"})
    assert result.decisions[0]["needs"] == ["destination"]
    result, _, _ = _run({**SEARCH, "return_date": (TODAY + timedelta(days=10)).isoformat(), "return_date_text": "9일에 오는"})
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
    """☆2026-10-08 14:58 playdata — 「11월 6일」이 2023-11-06 으로 옮겨졌다. 날짜를 말한 고객에게 날짜가 없다고 묻지 않는다."""
    result, _, tools = _run({**SEARCH, "depart_date": "2023-11-06", "return_date": "2023-11-09", "domestic": True,
                             "origin": "GMP", "destination": "CJU"})
    assert tools.calls == [] and result.decisions[0]["needs"] == ["depart_date"]
    assert result.answer.startswith("출발 날짜 2023-11-06(으)로 읽었는데 지난 날짜이거나")


def test_an_ungrounded_flight_date_is_cleared():
    result, _, tools = _run({**SEARCH, "depart_date_text": "내일"}, text="타이베이에서 인천 가는 비행기 2명")
    assert tools.calls == [] and result.decisions[0]["ungrounded"] == ["depart_date"]
    assert result.decisions[0]["needs"] == ["depart_date"]
