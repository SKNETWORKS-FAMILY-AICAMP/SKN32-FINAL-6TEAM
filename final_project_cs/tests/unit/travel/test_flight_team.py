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
              "direct_only": True, "cabin": None, "max_results": 10, "adults": 2, "children": None, "infants": None}
    assert tools.calls == [("read.flight_search", wanted), ("read.flight_offers", wanted)]
    assert result.outcome == "completed" and result.next_action.value == "respond"
    assert f"TPE → ICN · {GO} · 성인 2명 조건으로 찾은 결과(마이리얼트립 2개 · 판매처 비교 조회 실패)를" in result.answer
    # 가격이 낮은 순 — 국내선 64,000원이 먼저다
    assert result.answer.index("티웨이항공") < result.answer.index("제주항공")
    assert f"2. 제주항공 — {GO} TPE 13:10 → ICN 16:40 (직항, 2시간 30분)" in result.answer
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
    assert "찾은 결과(마이리얼트립 2개 · 항공사·여행사 판매처 2개)를" in answer
    assert answer.count("TPE 13:10 → ICN 16:40") == 1, "같은 편은 한 번만"
    assert "TPE 13:10 → ICN 16:40 7C1501 (직항, 2시간 30분)" in answer, "편명은 묶인 Ignav 쪽에서 빌린다"
    jeju = answer.index("제주항공(항공사 공식) 289,000원: https://www.jejuair.net/x")
    assert jeju < answer.index("마이리얼트립 302,000원"), "같은 편 안에서도 싼 판매처가 먼저"
    assert "에바항공" in answer and "Trip.com(여행사) 350,000원: https://www.trip.com/y" in answer
    shown = result.decisions[0]["shown"]
    assert [option["best"] for option in shown] == [64000, 289000.0, 350000.0]
    assert [offer["source"] for offer in shown[1]["offers"]] == ["ignav", "myrealtrip"]
    assert result.decisions[0]["both"] == [{"flight": "7C1501", "depart": "13:10", "myrealtrip": 302000, "ignav": 289000.0}], \
        "두 소스가 다 판 편만, 소스별 최저가로"
    assert [item.source_id for item in result.evidence] == ["flight.interpret", "read.flight_search", "read.flight_offers"]


def test_one_source_is_enough_and_both_missing_is_unknown():
    result, _, _ = _run(SEARCH, {"read.flight_search": None, "read.flight_offers": IGNAV})
    assert result.outcome == "completed" and "찾은 결과(마이리얼트립 조회 실패 · 항공사·여행사 판매처 2개)를" in result.answer
    result, _, _ = _run(SEARCH, {})
    assert (result.outcome, result.failure_code) == ("escalated", "unknown_항공편 검색 결과")


def test_a_round_trip_passes_the_return_date():
    _, _, tools = _run({**SEARCH, "return_date": BACK, "return_date_text": "9일에 오는"}, {"read.flight_search": FLIGHTS})
    assert tools.calls[0][1]["return_date"] == BACK


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
