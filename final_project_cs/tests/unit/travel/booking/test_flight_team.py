# -*- coding: utf-8 -*-
"""항공 팀 — 모델은 해석(공항 코드 포함)만 하고, 서버가 검증 · 조회 · 답을 맡는지 본다. 모델과 도구는 가짜다."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core.contracts import ContextPack, TeamTask, ToolNotAllowed
from app.domains.travel_ops.components.booking.offers import search_flights
from app.domains.travel_ops.instances.booking import FlightTeam
from app.domains.travel_ops.instances.booking.interpret import InterpretationInvalid, needs, parse
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


_BAND_KO = {"dawn": "새벽", "morning": "오전", "afternoon": "오후", "evening": "저녁"}


def _say(reply):
    """`[2026-10-14]` 해석이 규칙(모델 없음)이 되면서 시험의 「모델 답」(reply)을 **고객 문장**으로 바꾼다 — 규칙이 같은 구조를 뽑는다.
    옛 시험은 reply 로 해석 결과를 지정했으므로, 그 값을 말하는 문장을 만든다."""
    if not isinstance(reply, dict):
        return "비행기 알아봐줘"
    if reply.get("task") == "status":
        return "내 항공권 확정됐어?"
    if reply.get("task") == "unclear":
        return "비행기 말고 숙소 알아봐줘"
    parts = []
    if reply.get("depart_date"):
        day = date.fromisoformat(reply["depart_date"])
        parts.append(f"{day.month}월 {day.day}일" if day.year >= TODAY.year else f"{day.year}년 {day.month}월 {day.day}일")
    origin, destination = reply.get("origin"), reply.get("destination")
    parts.append(f"{origin}→{destination}" if origin and destination else f"{origin}에서" if origin else f"{destination} 가는" if destination else "")
    parts.append("비행기")
    if reply.get("return_date"):
        back = date.fromisoformat(reply["return_date"])
        parts.append(f"{back.month}월 {back.day}일에 돌아오는")
    elif reply.get("depart_date"):
        parts.append("편도")
    for key, word in (("adults", "성인"), ("children", "아이"), ("infants", "유아")):
        if reply.get(key) is not None:
            parts.append(f"{word} {reply[key]}")
    if reply.get("cabin"):
        parts.append({"BUSINESS": "비즈니스", "FIRST": "퍼스트", "ECONOMY": "이코노미"}[reply["cabin"]])
    if reply.get("direct_only") is True:
        parts.append("직항만")
    elif reply.get("direct_only") is False:
        parts.append("경유도 괜찮아")
    if reply.get("depart_times"):
        parts.append(reply.get("depart_times_text") or (" · ".join(_BAND_KO[b] for b in reply["depart_times"]) + " 출발로"))
    if reply.get("return_times"):
        parts.append("오는 날은 " + (reply.get("return_times_text") or " · ".join(_BAND_KO[b] for b in reply["return_times"])))
    if reply.get("max_price"):
        price = reply["max_price"]
        parts.append(f"1인 {price}만원 이하" if price < 1000 else f"1인 {price // 10000}만원 이하")
    for wish in reply.get("other_requests") or []:
        parts.append(wish)
    return " ".join(part for part in parts if part)


def _run(reply, tools=None, *, text=None, capability="flight.assist", llm=True, state=None):
    text = _say(reply) if text is None else text
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
    assert llm.calls == [], "`[2026-10-14]` 예약 모듈 — 문장 해석은 규칙(interpret_rules), 모델을 부르지 않는다"
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
    assert [item.source_id for item in result.evidence] == ["flight.interpret_rules", "read.booking_search_flights"]
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
    assert [item.source_id for item in result.evidence] == ["flight.interpret_rules", "read.booking_search_flights"]


TEXT_MORNING = "다음 달 6일 타이베이에서 인천 가는 비행기 알아봐줘, 2명 편도 직항만 오전 출발로"


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
                        text="다음 달 6일 타이베이에서 인천 가는 비행기 알아봐줘, 2명 편도 직항만 오전이나 저녁 출발로")
    assert "오전 · 저녁 출발 시간대마다 가장 싼 편을 보여 드립니다." in result.answer
    assert [option["band"] for option in result.decisions[0]["shown"]] == ["morning", "evening"], "오후는 고객이 빼지 않았어도 말한 것만"
    assert "1. [오전 최저가] 에바항공" in result.answer and "2. [저녁 최저가 · 전체 최저가] 티웨이항공" in result.answer


def test_a_time_of_day_with_nothing_found_shows_the_other_bands_and_says_so():
    result, _, _ = _run({**SEARCH, "depart_times": ["dawn"], "depart_times_text": "새벽 출발로"},
                        {"read.flight_search": FLIGHTS, "read.flight_offers": IGNAV}, text=TEXT_MORNING.replace("오전 출발로", "새벽 출발로"))
    assert "새벽 출발 편이 없어, 다른 출발 시간대마다 가장 싼 편을 보여 드립니다" in result.answer
    assert [option["band"] for option in result.decisions[0]["shown"]] == ["morning", "afternoon", "evening"]
    assert result.decisions[0]["fallback"] is True and "받은 결과에 새벽" not in result.answer


def test_a_time_of_day_not_in_the_message_is_not_invented():
    """`[2026-10-14]` 규칙은 문장에 없는 시간대를 만들지 않는다(모델 때는 근거 없는 시간대를 서버가 지웠다)."""
    result, _, _ = _run(SEARCH, {"read.flight_search": FLIGHTS, "read.flight_offers": IGNAV})
    assert result.decisions[0]["ungrounded"] == []
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
    assert tools.calls == [] and result.answer == "출발지 · 출발 날짜 · 성인 인원을 알려 주시면 이어서 찾아 드리겠습니다."
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
                        text="다음 달 6일 타이베이에서 인천 가는 비행기 알아봐줘 2명, 5일에 오는")
    assert result.decisions[0]["needs"] == ["return_date"]


def test_no_flights_and_unreadable_search_are_different():
    result, _, _ = _run(SEARCH, {"read.flight_search": {**FLIGHTS, "flights": [], "total": 0}})
    # `[10-15 검수 · GPT 검토 #10]` 다른 소스를 확인하지 못했으면 「없습니다」가 아니라 「받은 결과에는 없었다」
    assert result.outcome == "completed" and "받은 결과에는 항공편이 없었습니다" in result.answer and "확인하지 못했습니다" in result.answer
    empty = {"flights": [], "source": "x"}
    result, _, _ = _run(SEARCH, {"read.flight_search": {**FLIGHTS, "flights": [], "total": 0},
                                 "read.flight_offers": empty, "read.flight_google": empty})
    assert "찾은 항공편이 없습니다" in result.answer and result.decisions[0]["found"] == 0
    result, _, _ = _run(SEARCH, {"read.flight_search": None})
    assert (result.outcome, result.failure_code) == ("escalated", "unknown_항공편 검색 결과")


@pytest.mark.parametrize("text,needs", [
    ("비행기 예매 좀", ["origin", "destination", "depart_date", "adults"]),
    ("다음 주에 어디든 가고 싶어", ["origin", "destination", "depart_date", "adults"]),
    ("11월 6일 비행기 2명", ["origin", "destination"]),
])
def test_what_the_rules_cannot_read_is_asked_back_never_invented(text, needs):
    """`[2026-10-14]` 규칙 해석은 못 뽑은 칸을 비워 두고 되묻는다 — 지어내지도, 사람에게 넘기지도 않는다(모델 때의 invalid · failed 가 없다)."""
    result, _, tools = _run({"task": "unclear"}, text=text)
    assert (result.outcome, tools.calls, result.decisions[0]["needs"]) == ("completed", [], needs)


def test_without_a_model_and_other_branches():
    assert _run(SEARCH, {"read.flight_search": FLIGHTS}, llm=False)[0].outcome == "completed", "`[2026-10-14]` 모델이 없어도 돈다(규칙)"
    result, _, tools = _run({"task": "unclear"})
    assert tools.calls == [] and result.decisions[0]["needs"] == ["task"]
    result, llm, tools = _run(SEARCH, {"read.booking": {"booking_id": "b1"}}, capability="flight.status")
    assert llm.calls == [] and [c[0] for c in tools.calls] == ["read.booking"] and "잠긴 예약" in result.answer


def test_a_trip_on_the_case_fills_the_date_and_the_party():
    """`[2026-10-14]` 「이번 여행」 — 규칙이 여행 첫날 · 인원을 쓴다(근거 `trip`). 공항은 모르니 되묻는다."""
    view = {"trip": {"party_size": 2}, "items": [{"title": "경복궁", "starts_at": "2026-11-06T10:00:00+09:00"}]}
    result, llm, tools = _run({"task": "unclear"}, {"read.itinerary": view}, text="이번 여행 갈 때 비행기 찾아줘",
                              state={"subject_ref": {"kind": "trip", "id": "T1"}})
    assert tools.calls[0] == ("read.itinerary", {"trip_id": "T1"}) and llm.calls == []
    found = result.decisions[0]["interpretation"]
    assert (found["depart_date"], found["adults"], result.decisions[0]["needs"]) == ("2026-11-06", 2, ["origin", "destination"])


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


def test_a_date_the_customer_did_not_say_is_not_invented():
    """`[2026-10-14]` 규칙 해석은 문장에 없는 날짜를 만들지 않는다(모델 때는 「내일」을 지어내 서버가 지웠다)."""
    result, _, tools = _run({"task": "unclear"}, text="타이베이에서 인천 가는 비행기 2명")
    assert tools.calls == [] and result.decisions[0]["ungrounded"] == []
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
    from app.domains.travel_ops.instances.booking.interpret import parse
    from app.domains.travel_ops.instances.booking.team import _apply_limits

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
    # `[2026-10-13]` 일정은 바꾸지 않는다 — 「선택이 필요해요」 보류 제안(식당 · 활동의 「다른 후보」와 같다). 일정 판 그대로
    assert proposal.action_type == "itinerary.apply" and proposal.arguments["reason"] == "requested_options"
    assert "replacements" not in proposal.arguments, "후보를 보여 줄 때 일정 판을 올리지 않는다"
    ask = proposal.arguments["ask_options"]
    assert ask["item_id"] == LEG_ID and ask["text"] == result.answer
    assert ask["shown_key"] == f"flight:TPE-ICN:{GO}", "보여 준 편은 숙소 · 항공 원장에 적는다(적용기가)"
    options = ask["options"]
    assert [(o["rank"], o["key"]) for o in options] == [(1, JEJU_KEY), (2, TW_KEY)]
    assert {"key", "name", "place_id", "starts_at", "ends_at", "walk_min"} <= set(options[0]), "식당 · 활동의 「다른 안」 칸"
    assert options[1]["starts_at"] == f"{GO}T18:30:00+09:00" and options[1]["per_person"] == 32000 and options[1]["best"] == 64000
    assert "피치항공" not in result.answer, "직항이 있으면 직항만(사용자 결정 10-10)"
    assert proposal.arguments["summary"]["flight_options"] == [JEJU_KEY, TW_KEY]
    assert proposal.arguments["summary"]["near_original"] == 1


def test_a_source_that_timed_out_is_said_in_the_change_answer():
    """`[2026-10-13]` ☆14:49 playdata ICN→NRT: Ignav 가 20초 상한에 걸려 `timeout` 으로 빠졌는데 「바꿔 줘」 답은 아무 말이 없었다 —
    판매처 비교가 빠진 줄 모르고 고르게 된다. timeout · resting 만 적는다(조회 실패는 기록에만 — 시험의 빈 소스를 실패로 보지 않게)."""
    base = FakeTools({"read.flight_search": WITH_VIA}).values["read.booking_search_flights"]

    def late(arguments):
        got = base(arguments)
        return {**got, "sources": {**got["sources"], "ignav": {"status": "timeout", "seconds": 20.0}}}
    result, _, _ = _run({"task": "unclear"}, {"read.itinerary": _plan(), "read.booking_search_flights": late},
                        text="바꿔줘", capability="flight.itinerary", state=LEG_STATE)
    assert result.answer.endswith("(1인 32,000원). 항공사 · 여행사 판매처 비교는 20초 안에 답이 없어 뺐어요 — 그쪽 가격이 더 쌀 수 있어요. "
                                  "고르시면 바꿀게요. 고르지 않으시면 원래 일정을 그대로 둡니다.")
    assert result.decisions[0]["sources"] == {"myrealtrip": "ok", "ignav": "timeout", "google": "failed"}
    plain, _, _ = _legrun(_plan())
    assert "답이 없어" not in plain.answer and "쉬는 중" not in plain.answer, "빈 소스(failed)는 답에 적지 않는다"


def test_choosing_a_flight_moves_the_item_to_its_departure_and_keeps_the_old_one_as_an_option():
    plan = _plan()
    first, _, _ = _legrun(plan)
    plan["items"][0]["detail"] = _held(first, plan)
    state = {**LEG_STATE, "subject_ref": {**LEG_STATE["subject_ref"], "request": {"type": "change", "choice": JEJU_KEY}}}
    result, _, tools = _run({"task": "unclear"}, {"read.itinerary": plan}, text="2번", capability="flight.itinerary", state=state)
    assert [name for name, _ in tools.calls] == ["read.itinerary", "read.booking_search_flights"], \
        "`[2026-10-12]` 고르면 같은 조건으로 한 번 더 찾아 가격을 확인한다"
    assert result.answer.startswith("요청하신 대로 타이베이 → 인천 대신 제주항공 13:10(으)로 바꿨습니다. 아직 예약 전이에요")
    assert result.answer.endswith(" 지금 가격은 다시 확인하지 못했어요(보여 드릴 때 1인 151,000원) — 예약 전에 링크에서 확인해 주세요."), \
        "소스가 모두 답하지 않았다 — 바꾸되 확인하지 못했다고 적는다"
    new = result.action_proposals[0].arguments["replacements"][0]["item"]
    assert new["starts_at"] == f"{GO}T13:10:00+09:00" and new["ends_at"] is None
    assert new["detail"]["chosen"]["key"] == JEJU_KEY and new["detail"]["key"] == JEJU_KEY and new["detail"]["booked"] is False
    assert [o["name"] for o in new["detail"]["alternates"]] == ["티웨이항공 TW727 18:30", "타이베이 → 인천"]


def _held(first, plan):
    """`[2026-10-13]` 후보는 이제 보류 제안(`ask_options`)에 있다 — Case 경로 고르기 시험은 그 안을 항목 「다른 안」에 얹어 흉내 낸다."""
    options = first.action_proposals[0].arguments["ask_options"]["options"]
    return {**plan["items"][0]["detail"], "alternates": options, "other_options": [o["name"] for o in options]}


def _choose_jeju(search):
    """제주항공 13:10 을 보여 준 뒤, 고르는 순간 `search`(마이리얼트립 값)로 다시 찾는다."""
    plan = _plan()
    first, _, _ = _legrun(plan)
    plan["items"][0]["detail"] = _held(first, plan)
    state = {**LEG_STATE, "subject_ref": {**LEG_STATE["subject_ref"], "request": {"type": "change", "choice": JEJU_KEY}}}
    return _run({"task": "unclear"}, {"read.itinerary": plan, "read.flight_search": search}, text="2번",
                capability="flight.itinerary", state=state)[0]


def test_choosing_rechecks_the_price_and_says_it_is_the_same_or_changed():
    """`[2026-10-12]` 고를 때 가격 재확인 — 같으면 그대로라고, 바뀌면 바뀐 값으로 바꾸고 두 값을 적는다."""
    same = _choose_jeju(WITH_VIA)
    assert same.answer.endswith(" 지금 가격도 1인 151,000원 그대로예요.")
    assert same.action_proposals[0].arguments["summary"]["price_check"] == {
        "status": "same", "before": 151000, "now": 151000, "seller_before": "마이리얼트립", "seller_now": "마이리얼트립"}
    dearer = {**WITH_VIA, "flights": [{**WITH_VIA["flights"][0], "price_total": 340000}, *WITH_VIA["flights"][1:]]}
    changed = _choose_jeju(dearer)
    assert changed.answer.endswith(" 보여 드릴 때 1인 151,000원이던 가격이 지금 1인 170,000원이에요.")
    new = changed.action_proposals[0].arguments["replacements"][0]["item"]
    assert new["detail"]["chosen"]["per_person"] == 170000 and new["detail"]["chosen"]["key"] == JEJU_KEY
    assert [o["name"] for o in new["detail"]["alternates"]] == ["티웨이항공 TW727 18:30", "타이베이 → 인천"]


def test_a_cheaper_seller_on_recheck_is_said_as_a_seller_change_not_a_price_change():
    """☆10-12 18:41 playdata — 같은 편인데 고를 때 다른 판매처(Ignav)가 더 싸게 들어왔다. 값이 「바뀌었다」고 하지 않고 판매처를 적는다."""
    from app.domains.travel_ops.instances.booking.team import _price_note

    note = _price_note({"status": "changed", "before": 150700, "now": 143616,
                        "seller_before": "마이리얼트립", "seller_now": "Gotogate(여행사)"})
    assert note == " 보여 드릴 때 가장 싼 곳은 마이리얼트립(1인 150,700원)이었는데, 지금은 Gotogate(여행사)이(가) 1인 143,616원으로 가장 싸요."


def test_a_chosen_flight_its_source_no_longer_lists_is_not_applied():
    """그 편을 준 소스(마이리얼트립)가 답했는데 편이 없다 — 바꾸지 않고 그렇다고 답한다."""
    gone = _choose_jeju({**WITH_VIA, "flights": WITH_VIA["flights"][1:]})
    assert gone.action_proposals == []
    assert gone.answer == ("제주항공 13:10 편을 다시 찾아보니 지금은 나오지 않아요(매진됐거나 시각이 바뀌었을 수 있어요). "
                           "일정은 그대로 두었어요. 다른 후보를 고르시거나 「바꿔 줘」라고 하시면 새로 찾아 드릴게요.")
    assert gone.decisions[0]["price_check"]["status"] == "gone"


def test_when_no_new_direct_flight_is_left_connecting_ones_are_held_and_said():
    result, _, _ = _legrun(_plan(detail={"shown": [TW_KEY, JEJU_KEY]}))
    assert result.answer == ("타이베이 → 인천 대신 탈 수 있는 편이에요 — 1) 피치항공 05:30(1인 75,000원). 새로 보여 드릴 직항이 없어 경유 편이에요. "
                             "원래 출발(12:00) 앞뒤 3시간 안에는 새 편이 없어 다른 시간대예요. 고르시면 바꿀게요. 고르지 않으시면 원래 일정을 그대로 둡니다.")
    assert result.action_proposals[0].arguments["summary"]["widened_to_connecting"] is True
    assert [o["key"] for o in result.action_proposals[0].arguments["ask_options"]["options"]] == [VIA_KEY]


def test_change_again_skips_flights_the_ledger_says_were_shown():
    """`[2026-10-13]` 보여 준 편은 숙소 · 항공 원장에 있다(`read.offers_shown`) — 항목 상세에 없어도 뺀다."""
    shown = {"item_key": f"flight:TPE-ICN:{GO}", "offers": [{"key": TW_KEY, "name": "티웨이"}, {"key": JEJU_KEY, "name": "제주"}]}
    result, _, tools = _run({"task": "unclear"}, {"read.itinerary": _plan(), "read.flight_search": WITH_VIA, "read.offers_shown": shown},
                            text="이 비행기 다른 걸로 바꿔줘", capability="flight.itinerary", state=LEG_STATE)
    assert [a["item_key"] for name, a in tools.calls if name == "read.offers_shown"] == [f"flight:TPE-ICN:{GO}"]
    assert [o["key"] for o in result.action_proposals[0].arguments["ask_options"]["options"]] == [VIA_KEY]


def test_new_flights_near_the_original_departure_come_first_then_the_rest_by_price():
    from app.domains.travel_ops.instances.booking.team import _fresh_flights

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
    from app.domains.travel_ops.instances.booking.team import _booking_note, _flight_option

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


def _legrun_with(plan, **conditions):
    state = {**LEG_STATE, "interpretation": {"report": {"type": "change", **conditions}}}
    return _run({"task": "unclear"}, {"read.itinerary": plan, "read.flight_search": WITH_VIA},
                text="더 싼 걸로 바꿔줘", capability="flight.itinerary", state=state)


def test_a_per_person_limit_from_the_intake_keeps_only_flights_under_it():
    """`[2026-10-12]` 조건은 접수 해석이 넘긴다 — `max_price` 는 1인 값."""
    result, llm, _ = _legrun_with(_plan(), max_price=100000)
    assert llm.calls == []
    assert result.answer == ("타이베이 → 인천 대신 탈 수 있는 편이에요 — 1) 티웨이항공 TW727 18:30(1인 32,000원). "
                             "원래 출발(12:00) 앞뒤 3시간 안에는 새 편이 없어 다른 시간대예요. 말씀하신 대로 1인 100,000원 이하만 골랐어요. "
                             "고르시면 바꿀게요. 고르지 않으시면 원래 일정을 그대로 둡니다.")


def test_cheaper_without_the_current_price_sorts_by_price_and_drops_the_time_preference():
    result, _, _ = _legrun_with(_plan(), cheaper=True)
    assert result.answer == ("타이베이 → 인천 대신 탈 수 있는 편이에요 — 1) 티웨이항공 TW727 18:30(1인 32,000원) · "
                             "2) 제주항공 13:10(1인 151,000원). 지금 편 가격을 몰라 1인 가격이 낮은 순으로 골랐어요. "
                             "고르시면 바꿀게요. 고르지 않으시면 원래 일정을 그대로 둡니다.")
    result, _, _ = _legrun_with(_plan(detail={"per_person": 100000}), cheaper=True)
    assert "지금 편(1인 100,000원)보다 싼 편만 골랐어요." in result.answer and "제주항공" not in result.answer


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


# ── 검수 10-15 고침 묶음 A (GPT 검토 #9) ─────────────
def test_an_explicit_cheapest_request_lists_by_price_instead_of_one_per_time_band():
    text = TEXT_MORNING.replace("오전 출발로", "최저가로")
    result, _, _ = _run(SEARCH, {"read.flight_search": FLIGHTS, "read.flight_offers": IGNAV}, text=text)
    shown = [option["best"] for option in result.decisions[0]["shown"]]
    assert result.decisions[0]["prefer"] == "cheapest" and shown == sorted(shown)
    assert "가격이 낮은 순으로" in result.answer


def test_the_last_flight_lists_the_latest_departures_and_warns_the_list_is_partial():
    text = TEXT_MORNING.replace("오전 출발로", "마지막 비행기로")
    result, _, _ = _run(SEARCH, {"read.flight_search": FLIGHTS, "read.flight_offers": IGNAV}, text=text)
    bands = [option["band"] for option in result.decisions[0]["shown"]]
    assert result.decisions[0]["prefer"] == "last" and bands[0] == "evening"
    assert "출발이 늦은 순으로" in result.answer and "그날의 실제 마지막 편이 아닐 수 있습니다" in result.answer


def test_a_clock_limit_keeps_only_flights_leaving_after_it():
    text = TEXT_MORNING.replace("오전 출발로", "오후 3시 이후 출발로")
    result, _, _ = _run(SEARCH, {"read.flight_search": FLIGHTS, "read.flight_offers": IGNAV}, text=text)
    assert result.decisions[0]["clock_limit"] == ["15:00", None]
    assert all(option["band"] in ("afternoon", "evening") for option in result.decisions[0]["shown"])
    assert "출발 15:00 이후 편만 골랐습니다." in result.answer or "받은 결과에 출발 15:00 이후 편이 없어" in result.answer


# ── 검수 10-15 고침 묶음 B (GPT 검토 #10 · #14) ─────────────
def test_a_resting_source_and_a_round_trip_reference_are_not_said_as_no_flights():
    """☆10-15 14:58 F01 — 마이리얼트립이 쉬는 중이고 구글은 왕복 참고가만 줬는데 「찾은 항공편이 없습니다」라고 답했다."""
    google = {"flights": [], "note": "왕복은 편별 대신 최저가 참고", "round_trip_lowest": 326400.0,
              "page": "https://www.google.com/travel/flights?hl=ko&tfs=rt", "source": "serpapi_flights"}
    result, _, _ = _run({**SEARCH, "return_date": BACK, "return_date_text": "9일에 오는"},
                        {"read.flight_search": {"cooldown_seconds": 540, "source": "myrealtrip"}, "read.flight_google": google})
    answer = result.answer
    assert "찾은 항공편이 없습니다" not in answer and "항공편 목록을 받지 못했습니다" in answer and "항공편이 없다는 뜻은 아닙니다" in answer
    assert "마이리얼트립 요청 한도로 쉬는 중" in answer and "구글 항공권 왕복 최저가 참고만" in answer
    assert "구글 항공권 왕복 최저 참고 326,400원" in answer and result.decisions[0]["found"] is None


def test_one_source_raising_keeps_the_other_sources():
    class Boom:
        misses: dict = {}

        def flight_search(self, **_):
            raise ValueError("bad nested shape")

    from types import SimpleNamespace as _NS
    from app.domains.travel_ops.components.booking.offers.flights import search_flights as _search
    ok = StubSource("read.flight_search", FLIGHTS, [])
    got = _search(_NS(travel_search=ok, flight_offers=Boom(), flight_google=None), origin="TPE", destination="ICN",
                  depart_date=GO, domestic=False, adults=2)
    assert got["sources"]["ignav"] == {"status": "failed", "error": "ValueError"}
    assert got["sources"]["myrealtrip"]["status"] == "ok" and got["options"], "정상 소스 결과는 남는다"
