# -*- coding: utf-8 -*-
"""숙소 팀 — 모델은 해석만 하고, 서버가 검증 · 조회 · 답을 맡는지 본다. 모델과 도구는 가짜다(네트워크 · DB 없음)."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core.contracts import ContextPack, TeamTask, ToolNotAllowed
from app.domains.travel_ops.instances.lodging import LodgingTeam
from app.domains.travel_ops.instances.lodging.interpret import InterpretationInvalid, needs, parse
from app.tools.read_tools import ALLOWED_PROMPT_KEYS

TODAY = datetime.now(ZoneInfo("Asia/Seoul")).date()
IN, OUT = (TODAY + timedelta(days=30)).isoformat(), (TODAY + timedelta(days=33)).isoformat()
SEARCH = {"task": "search", "keyword": "용산", "stay_name": None, "check_in": IN, "check_out": OUT, "adults": 2,
          "children": None, "max_price_per_night": 200000, "min_rating": 4.0, "domestic": True, "missing": [],
          "question": None}
STAYS = {"stays": [{"gid": 11, "name": "해밀톤 호텔", "description": "3성급 · 호텔 · 용산구 · 서울", "price_per_night": 188597,
                    "rating": 4.0, "review_count": 1009},
                   {"gid": 12, "name": "둘째 호텔", "description": "", "price_per_night": 150000, "rating": None,
                    "review_count": None}],
         "total": 37, "has_next": True, "confirmed_at": "2026-10-07T08:00:00+00:00", "source": "myrealtrip"}
DETAIL = {"gid": 11, "name": "해밀톤 호텔", "address": "서울 용산구 이태원로 179", "latitude": 37.534563,
          "longitude": 126.994116, "link": "https://accommodation.myrealtrip.com/union/products/11",
          "price_per_night": 188597, "total_price": 622370, "no_rooms": False, "sold_out": False,
          "confirmed_at": "2026-10-07T08:00:01+00:00", "source": "myrealtrip"}


class FakeLLM:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    async def complete(self, prompt_key, input_text, context, *, run_id=None):
        self.calls.append((prompt_key, input_text, context))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


class FakeTools:
    """이름 → 값(또는 인자를 받는 함수). 권한 · 예산을 실제 도구함과 같은 순서로 본다."""

    def __init__(self, values):
        self.values, self.calls = values, []

    def call(self, name, context, arguments, allowed_tools, seen, budget=None):
        if name not in allowed_tools:
            raise ToolNotAllowed(name)
        assert budget is None or len(seen) < budget, f"도구 예산 {budget} 을 넘겼다"
        seen.add(name + repr(sorted(arguments.items(), key=lambda pair: pair[0])))
        self.calls.append((name, dict(arguments)))
        value = self.values.get(name)
        return value(arguments) if callable(value) else value


def _run(reply, tools=None, *, text="용산 근처 호텔 찾아줘", capability="lodging.assist", state=None):
    llm, toolbox = FakeLLM(reply), FakeTools(tools or {})
    case_id = uuid4()
    pack = ContextPack(pack_id=uuid4(), case_id=case_id, team_id="lodging", tenant_id="t", knowledge_scope=["lodging"],
                       current_state={"customer_id": str(uuid4()), **(state or {})}, estimated_input_tokens=1)
    task = TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id="lodging", capability=capability,
                    case_version=1, input_text=text, context=pack, allowed_tools=LodgingTeam.manifest.allowed_tools,
                    deadline_at=datetime.now(UTC) + timedelta(seconds=90))
    return asyncio.run(LodgingTeam(toolbox, llm).execute(task)), llm, toolbox


# ── 찾기 ────────────────────────────────────────────────────────
def test_search_calls_the_model_once_and_answers_from_tool_values():
    result, llm, tools = _run(SEARCH, {"read.stay_search": STAYS,
                                       "read.stay_detail": lambda a: DETAIL if a["gid"] == 11 else None})
    assert len(llm.calls) == 1 and llm.calls[0][0] == "lodging.interpret"
    assert llm.calls[0][2] == {"today": TODAY.isoformat()}
    name, arguments = tools.calls[0]
    assert name == "read.stay_search"
    assert arguments == {"keyword": "용산", "check_in": IN, "check_out": OUT, "adults": 2, "children": None,
                         "domestic": True, "size": 20, "max_price": 200000, "min_review_rating": 4.0}
    assert [call[1]["gid"] for call in tools.calls[1:]] == [11, 12]
    assert "2. 둘째 호텔" in result.answer
    assert result.outcome == "completed" and result.next_action.value == "respond"
    assert "1. 해밀톤 호텔 — 1박 188,597원 · 전체 622,370원(세금 포함) · 평점 4.0/5(후기 1,009)" in result.answer
    assert "https://accommodation.myrealtrip.com/union/products/11" in result.answer
    assert "2. 둘째 호텔 — 1박 150,000원 · 평점 없음" in result.answer and "불러오지 못했습니다" in result.answer
    assert "37곳 중 2곳" in result.answer
    sources = [item.source_id for item in result.evidence]
    assert sources == ["lodging.interpret", "read.stay_search", "read.stay_detail:11"], "못 읽은 상세는 근거로 싣지 않는다"
    assert result.decisions[0]["shown"][1] == {"gid": 12, "name": "둘째 호텔", "detail_read": False}


def test_missing_values_are_asked_back_without_any_search():
    reply = {**SEARCH, "check_in": None, "check_out": None, "adults": None,
             "missing": ["adults", "check_in", "check_out"], "question": "언제, 몇 분이 묵으실 예정인가요?"}
    result, _, tools = _run(reply)
    assert tools.calls == []
    assert (result.outcome, result.answer) == ("completed", "언제, 몇 분이 묵으실 예정인가요?")
    assert result.decisions[0]["needs"] == ["check_in", "check_out", "adults"]


def test_the_server_recounts_what_is_missing_instead_of_trusting_the_model():
    """모델이 `missing=[]` 이라 해도 날짜가 지났거나 앞뒤가 뒤집혔으면 서버가 되묻는다."""
    past = (TODAY - timedelta(days=3)).isoformat()
    result, _, tools = _run({**SEARCH, "check_in": past, "missing": []})
    assert tools.calls == [] and result.decisions[0]["needs"] == ["check_in"]
    assert "체크인 날짜" in result.answer
    result, _, tools = _run({**SEARCH, "check_out": IN, "missing": []})
    assert tools.calls == [] and result.decisions[0]["needs"] == ["check_out"]


def test_places_without_rooms_are_skipped_and_the_next_ones_fill_in():
    stays = {**STAYS, "stays": [{"gid": n, "name": f"숙소{n}", "description": "", "price_per_night": None, "rating": 0.0,
                                 "review_count": None} for n in range(1, 11)]}
    full = lambda a: {**DETAIL, "gid": a["gid"], "no_rooms": a["gid"] == 2}      # noqa: E731
    result, _, tools = _run(SEARCH, {"read.stay_search": stays, "read.stay_detail": full})
    assert [item["gid"] for item in result.decisions[0]["shown"]] == [1, 3, 4]
    assert [item["gid"] for item in result.decisions[0]["skipped"]] == [2]
    assert len(tools.calls) == 5 and "객실이 없는 1곳은 건너뜀" in result.answer and "평점 없음" in result.answer
    result, _, tools = _run(SEARCH, {"read.stay_search": stays, "read.stay_detail": {**DETAIL, "sold_out": True}})
    assert len(tools.calls) == 5, "상세는 정한 횟수(4)까지만 부른다"
    assert "4곳을 확인했지만" in result.answer and result.decisions[0]["shown"] == []


def test_an_unreadable_detail_stops_further_detail_calls():
    result, _, tools = _run(SEARCH, {"read.stay_search": STAYS, "read.stay_detail": None})
    assert [call[0] for call in tools.calls] == ["read.stay_search", "read.stay_detail"]
    assert result.decisions[0]["shown"] == [{"gid": 11, "name": "해밀톤 호텔", "detail_read": False}]


def test_the_models_question_is_used_only_when_it_asks_for_everything_missing():
    reply = {**SEARCH, "keyword": None, "check_in": None, "check_out": None, "adults": None,
             "missing": ["keyword"], "question": "어디에서 숙소를 찾으시나요?"}
    result, _, _ = _run(reply)
    assert result.answer.startswith("지역 · 체크인 날짜 · 체크아웃 날짜 · 성인 인원")


def test_no_result_and_unreadable_search_are_different():
    result, _, _ = _run(SEARCH, {"read.stay_search": {**STAYS, "stays": [], "total": 0}})
    assert result.outcome == "completed" and "찾은 숙소가 없습니다" in result.answer
    result, _, _ = _run(SEARCH, {"read.stay_search": None})
    assert (result.outcome, result.failure_code) == ("escalated", "unknown_숙소 검색 결과")


# ── 내 숙소 ──────────────────────────────────────────────────────
MY_STAY = {**SEARCH, "task": "my_stay", "keyword": None, "stay_name": "해밀톤호텔", "adults": None,
           "max_price_per_night": None, "min_rating": None}


def test_my_stay_returns_coordinates_address_and_link():
    result, _, tools = _run(MY_STAY, {"read.stay_search": STAYS, "read.stay_detail": DETAIL},
                            text="해밀톤호텔 예약했는데 일정에 넣어줘")
    assert tools.calls[0][1]["keyword"] == "해밀톤호텔" and tools.calls[0][1]["size"] == 5
    assert tools.calls[1] == ("read.stay_detail", {"gid": 11, "check_in": IN, "check_out": OUT, "adults": None,
                                                   "children": None}), "띄어쓰기만 다른 이름은 같은 숙소로 본다"
    stay = result.decisions[0]["my_stay"]
    assert (stay["latitude"], stay["longitude"], stay["address"]) == (37.534563, 126.994116, "서울 용산구 이태원로 179")
    assert "위도 37.534563" in result.answer and "일정에는 아직 넣지 않았습니다" in result.answer


def test_my_stay_asks_which_one_when_the_name_matches_several():
    result, _, tools = _run({**MY_STAY, "stay_name": "호텔"}, {"read.stay_search": STAYS})
    assert len(tools.calls) == 1, "어느 곳인지 모르면 상세를 부르지 않는다"
    assert "해밀톤 호텔 / 둘째 호텔" in result.answer and result.decisions[0]["needs"] == ["stay_name"]


def test_my_stay_without_coordinates_is_unknown_not_a_made_up_place():
    result, _, _ = _run(MY_STAY, {"read.stay_search": STAYS, "read.stay_detail": {**DETAIL, "latitude": None}})
    assert (result.outcome, result.failure_code) == ("escalated", "unknown_숙소 위치")


# ── 해석이 안 될 때 · 다른 갈래 ───────────────────────────────────
@pytest.mark.parametrize("reply,code", [
    ({"task": "book_it_now"}, "interpretation_invalid"),
    ({**SEARCH, "check_in": "다음 주"}, "interpretation_invalid"),
    ("not an object", "interpretation_invalid"),
    (RuntimeError("no active prompt registered for lodging.interpret"), "interpretation_failed"),
])
def test_a_bad_or_failed_interpretation_is_not_repaired(reply, code):
    result, _, tools = _run(reply)
    assert (result.outcome, result.failure_code, tools.calls) == ("escalated", code, [])


def test_without_a_model_the_team_does_not_guess():
    team = LodgingTeam(FakeTools({}), None)
    pack = ContextPack(pack_id=uuid4(), case_id=uuid4(), team_id="lodging", tenant_id="t", knowledge_scope=["lodging"],
                       current_state={"customer_id": str(uuid4())}, estimated_input_tokens=1)
    task = TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=pack.case_id, team_id="lodging", capability="lodging.assist",
                    case_version=1, input_text="호텔", context=pack, allowed_tools=team.manifest.allowed_tools,
                    deadline_at=datetime.now(UTC) + timedelta(seconds=90))
    assert asyncio.run(team.execute(task)).failure_code == "interpreter_missing"


def test_unclear_asks_and_status_keeps_the_locked_booking_answer():
    result, _, tools = _run({"task": "unclear"})
    assert tools.calls == [] and result.decisions[0]["needs"] == ["task"]
    result, _, tools = _run({"task": "status"}, {"read.booking": {"booking_id": "b1", "locked": True}})
    assert [call[0] for call in tools.calls] == ["read.booking"] and "잠긴 예약" in result.answer
    result, llm, _ = _run(SEARCH, {"read.booking": {"booking_id": "b1"}}, capability="lodging.status")
    assert llm.calls == [] and "잠긴 예약" in result.answer


def test_a_trip_on_the_case_is_summarised_for_the_model():
    view = {"trip": {"party_size": 3}, "items": [
        {"title": "경복궁", "starts_at": "2026-11-06T10:00:00+09:00"}, {"title": "남산타워", "starts_at": "2026-11-08T15:00:00+09:00"}]}
    _, llm, tools = _run({"task": "unclear"}, {"read.itinerary": view}, state={"subject_ref": {"kind": "trip", "id": "T1"}})
    assert tools.calls[0] == ("read.itinerary", {"trip_id": "T1"})
    assert llm.calls[0][2]["trip"] == {"party_size": 3, "first_day": "2026-11-06", "last_day": "2026-11-08",
                                      "places": ["경복궁", "남산타워"]}


# ── 검증 부품 · 등록 ──────────────────────────────────────────────
def test_parse_and_needs():
    found = parse({**MY_STAY, "stay_name": "  ", "extra_key": 1})
    assert found.stay_name is None and needs(found, today=TODAY) == ["stay_name"]
    with pytest.raises(InterpretationInvalid):
        parse({**SEARCH, "adults": 0})


def test_the_prompt_key_is_registrable_and_the_file_exists():
    from pathlib import Path

    assert "lodging.interpret" in ALLOWED_PROMPT_KEYS
    files = list(Path("prompts/lodging").glob("interpret.v*.md"))
    assert len(files) == 1 and "lodging team" in files[0].read_text(encoding="utf-8")
    manifest = LodgingTeam.manifest
    assert manifest.default_capability == "lodging.assist" and set(manifest.capabilities) == {"lodging.assist", "lodging.status"}
