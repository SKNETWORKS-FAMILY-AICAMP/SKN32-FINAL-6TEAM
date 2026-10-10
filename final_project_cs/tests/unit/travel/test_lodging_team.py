# -*- coding: utf-8 -*-
"""숙소 팀 — 모델은 해석만 하고, 서버가 검증 · 조회 · 답을 맡는지 본다. 모델과 도구는 가짜다(네트워크 · DB 없음)."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core.contracts import ContextPack, TeamTask, ToolNotAllowed
from app.domains.travel_ops.components.booking.offers import search_stays
from app.domains.travel_ops.instances.lodging import LodgingTeam
from app.domains.travel_ops.instances.lodging.interpret import InterpretationInvalid, needs, parse
from app.tools.read_tools import ALLOWED_PROMPT_KEYS

TODAY = datetime.now(ZoneInfo("Asia/Seoul")).date()
IN, OUT = (TODAY + timedelta(days=30)).isoformat(), (TODAY + timedelta(days=33)).isoformat()
SEARCH = {"task": "search", "keyword": "용산", "stay_name": None, "check_in": IN, "check_out": OUT,
          "check_in_text": "다음 달 6일부터", "check_out_text": "3박", "adults": 2,
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


class StubSource:
    """어댑터 대신 — 정해 둔 값(또는 인자를 받는 함수)을 돌려주고 받은 인자를 남긴다."""

    def __init__(self, name, value, record):
        self.name, self.value, self.record = name, value, record

    def stay_search(self, **arguments):
        self.record.append((self.name, dict(arguments)))
        return self.value(arguments) if callable(self.value) else self.value


class FakeTools:
    """이름 → 값(또는 인자를 받는 함수). 권한 · 예산을 실제 도구함과 같은 순서로 본다.

    `[2026-10-10]` 찾기는 booking 도구 하나(`read.booking_search_stays`)를 부른다 — `read.stay_search` · `read.stay_google` 값을 주면 진짜 booking
    모듈에 가짜 어댑터로 넣어 돌린다. 내 숙소(이름 찾기)는 지금처럼 `read.stay_search` 를 바로 부른다.
    """

    def __init__(self, values):
        self.values, self.calls, self.source_calls = dict(values), [], []
        travel = SimpleNamespace(travel_search=StubSource("read.stay_search", values.get("read.stay_search"), self.source_calls),
                                 stay_google=StubSource("read.stay_google", values.get("read.stay_google"), self.source_calls))
        self.values.setdefault("read.booking_search_stays", lambda arguments: search_stays(travel, **arguments))

    def call(self, name, context, arguments, allowed_tools, seen, budget=None):
        if name not in allowed_tools:
            raise ToolNotAllowed(name)
        assert budget is None or len(seen) < budget, f"도구 예산 {budget} 을 넘겼다"
        seen.add(name + repr(sorted(arguments.items(), key=lambda pair: pair[0])))
        self.calls.append((name, dict(arguments)))
        value = self.values.get(name)
        return value(arguments) if callable(value) else value


def _run(reply, tools=None, *, text="다음 달 6일부터 3박 용산 근처 호텔 찾아줘", capability="lodging.assist", state=None):
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
    assert name == "read.booking_search_stays"
    assert arguments == {"keyword": "용산", "check_in": IN, "check_out": OUT, "adults": 2, "children": None,
                         "domestic": True, "size": 20, "max_price": 200000, "min_review_rating": 4.0}
    assert [source for source, _ in tools.source_calls] == ["read.stay_search", "read.stay_google"]
    assert tools.source_calls[1][1] == {"keyword": "용산", "check_in": IN, "check_out": OUT, "adults": 2, "size": 20, "max_price": 200000}
    assert [call[1]["gid"] for call in tools.calls if call[0] == "read.stay_detail"] == [11, 12]
    assert "2. 둘째 호텔" in result.answer
    assert result.outcome == "completed" and result.next_action.value == "respond"
    assert "1. 해밀톤 호텔 — 1박 188,597원 · 전체 622,370원(세금 포함) · 평점 4.0/5(후기 1,009)" in result.answer
    assert "https://accommodation.myrealtrip.com/union/products/11" in result.answer
    assert "2. 둘째 호텔 — 1박 150,000원 · 평점 없음" in result.answer and "불러오지 못했습니다" in result.answer
    assert "37곳 중 2곳" in result.answer
    sources = [item.source_id for item in result.evidence]
    assert sources == ["lodging.interpret", "read.booking_search_stays", "read.stay_detail:11"], "못 읽은 상세는 근거로 싣지 않는다"
    assert result.decisions[0]["shown"][1] == {"gid": 12, "name": "둘째 호텔", "detail_read": False}


GOOGLE = {"stays": [
    {"name": "Namsan Ville", "type": "vacation rental", "price_per_night": 177960.0, "total_price": 533879.0,
     "rating": None, "review_count": None, "hotel_class": None, "link": "https://www.bluepillow.com/x"},
    {"name": "해밀톤 호텔", "type": "hotel", "price_per_night": 190000.0, "total_price": 570000.0, "rating": 4.0,
     "review_count": 1000, "hotel_class": 3, "link": "https://www.hamilton.co.kr"},
    {"name": "밀리오레호텔 명동", "type": "hotel", "price_per_night": 241878.0, "total_price": 725634.0, "rating": 3.3,
     "review_count": 1076, "hotel_class": 4, "link": "https://migliorehotel.co.kr"}],
    "page": "https://www.google.com/travel/search?q=%EC%9A%A9%EC%82%B0&hl=ko&gl=kr", "source": "serpapi_hotels"}


def test_google_hotels_are_a_separate_block_without_shown_names_and_rentals():
    result, _, _ = _run(SEARCH, {"read.stay_search": STAYS, "read.stay_detail": lambda a: DETAIL if a["gid"] == 11 else None,
                                 "read.stay_google": GOOGLE})
    answer = result.answer
    assert "구글 호텔에서 본 같은 조건 숙소(구글 순서, 숙박 공유 제외):" in answer
    assert "   · 밀리오레호텔 명동 — 4성급 · 1박 241,878원 · 전체 725,634원 · 평점 3.3/5(후기 1,076): https://migliorehotel.co.kr" in answer
    assert "Namsan Ville" not in answer, "숙박 공유는 뺀다"
    priceless = {**GOOGLE, "stays": [{**GOOGLE["stays"][2], "name": "지요크 명동", "price_per_night": None, "link": ""}]}
    other, _, _ = _run(SEARCH, {"read.stay_search": STAYS, "read.stay_detail": lambda a: DETAIL, "read.stay_google": priceless})
    assert "지요크 명동" not in other.answer, "가격 없는 곳은 뺀다"
    linkless = {**GOOGLE, "stays": [{**GOOGLE["stays"][2], "name": "필스테이 명동 메트로", "link": ""}]}
    other, _, _ = _run(SEARCH, {"read.stay_search": STAYS, "read.stay_detail": lambda a: DETAIL, "read.stay_google": linkless})
    assert "필스테이 명동 메트로" not in other.answer, "링크 없는 곳은 뺀다(2026-10-10 17:02 playdata)"
    assert answer.count("해밀톤 호텔") == 1, "마이리얼트립에서 이미 보인 이름은 뺀다"
    assert "구글 호텔 검색 결과 페이지(날짜는 그 화면에서 다시 고르셔야 할 수 있습니다): https://www.google.com/travel/search?" in answer
    assert ("   · 부킹닷컴: https://www.booking.com/searchresults.ko.html?ss=%EC%9A%A9%EC%82%B0"
            f"&checkin={IN}&checkout={OUT}&group_adults=2&no_rooms=1&group_children=0") in answer
    assert "   · 야놀자(날짜 · 인원은 그 화면에서 다시 고르셔야 합니다): https://www.yanolja.com/search/%EC%9A%A9%EC%82%B0" in answer
    assert result.decisions[0]["google"] == 3


def test_google_hotels_alone_answer_when_myrealtrip_fails():
    result, _, _ = _run(SEARCH, {"read.stay_search": None, "read.stay_google": GOOGLE})
    assert result.outcome == "completed" and "마이리얼트립 검색은 결과를 받지 못했습니다(조회 실패)" in result.answer
    assert "밀리오레호텔 명동" in result.answer
    result, _, _ = _run(SEARCH, {})
    assert result.outcome == "escalated", "둘 다 못 받으면 모름"


def test_myrealtrip_resting_after_a_429_still_answers_with_google_and_links():
    resting = {"cooldown_seconds": 540, "source": "myrealtrip"}
    result, _, tools = _run(SEARCH, {"read.stay_search": resting, "read.stay_google": GOOGLE})
    assert result.outcome == "completed" and "마이리얼트립 검색은 요청 한도로 잠시 조회를 쉬고 있습니다." in result.answer
    assert "밀리오레호텔 명동" in result.answer and "부킹닷컴" in result.answer
    assert [call[0] for call in tools.calls] == ["read.booking_search_stays"], "쉬는 중이면 상세도 안 부른다"
    result, _, _ = _run(SEARCH, {"read.stay_search": resting})
    assert result.outcome == "completed" and "부킹닷컴" in result.answer, "구글 호텔도 없으면 링크라도"
    result, _, tools = _run(SEARCH, {"read.stay_search": STAYS, "read.stay_detail": resting})
    assert [call[0] for call in tools.calls].count("read.stay_detail") == 1, "상세 도중 쉬기 시작하면 더 안 부른다"


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
    stays = {**STAYS, "stays": [{"gid": n, "name": f"숙소{n}", "description": "", "price_per_night": 100000, "rating": 0.0,
                                 "review_count": None} for n in range(1, 11)]}
    full = lambda a: {**DETAIL, "gid": a["gid"], "no_rooms": a["gid"] == 2}      # noqa: E731
    result, _, tools = _run(SEARCH, {"read.stay_search": stays, "read.stay_detail": full})
    assert [item["gid"] for item in result.decisions[0]["shown"]] == [1, 3, 4]
    assert [item["gid"] for item in result.decisions[0]["skipped"]] == [2]
    assert len(tools.calls) == 5 and "객실이 없는 1곳은 건너뜀" in result.answer and "평점 없음" in result.answer
    result, _, tools = _run(SEARCH, {"read.stay_search": stays, "read.stay_detail": {**DETAIL, "sold_out": True}})
    assert len(tools.calls) == 5, "상세는 정한 횟수(4)까지만 부른다(booking 1)"
    assert "10곳 중 4곳이 가격이 없거나" in result.answer and result.decisions[0]["shown"] == []


def test_places_without_a_list_price_are_skipped_before_any_detail_call():
    stays = {**STAYS, "stays": [{"gid": n, "name": f"숙소{n}", "description": "", "rating": 4.0, "review_count": 3,
                                 "price_per_night": None if n in (1, 2) else 90000} for n in range(1, 6)]}
    result, _, tools = _run(SEARCH, {"read.stay_search": stays, "read.stay_detail": lambda a: {**DETAIL, "gid": a["gid"]}})
    assert [call[1]["gid"] for call in tools.calls if call[0] == "read.stay_detail"] == [3, 4, 5]
    assert [(item["gid"], item["reason"]) for item in result.decisions[0]["skipped"]] == [(1, "no_price_in_list"), (2, "no_price_in_list")]


def test_an_unreadable_detail_stops_further_detail_calls():
    result, _, tools = _run(SEARCH, {"read.stay_search": STAYS, "read.stay_detail": None})
    assert [call[0] for call in tools.calls] == ["read.booking_search_stays", "read.stay_detail"]
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
                            text="해밀톤호텔 다음 달 6일부터 3박 예약했는데 일정에 넣어줘")
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



# ── 일정 반영(팀 피드백 4, 2026-10-10) ─────────────────────────────
def _item(title, day, lat=None, lon=None):
    place = {"place_id": title, "name": title, "latitude": lat, "longitude": lon} if lat is not None else None
    return {"title": title, "starts_at": f"{day}T10:00:00+09:00", "place": place}


NEAR_TRIP = {"trip": {"party_size": 2}, "items": [
    _item("남산타워", IN, 37.5512, 126.9882), _item("이태원 거리", OUT, 37.5345, 126.9946),
    _item("숙소 이전 날 장소", (TODAY + timedelta(days=10)).isoformat(), 37.2000, 127.2000),   # 숙박 기간 밖 — 빼고 잰다
    _item("좌표 없는 일정", IN)]}
NEAR_GOOGLE = {"stays": [
    {"name": "먼 호텔", "type": "hotel", "price_per_night": 100000.0, "total_price": 300000.0, "rating": 4.1, "review_count": 10,
     "hotel_class": 3, "latitude": 37.6500, "longitude": 127.0500, "link": "https://far.example"},
    {"name": "좌표 없는 호텔", "type": "hotel", "price_per_night": 110000.0, "total_price": 330000.0, "rating": 4.0, "review_count": 5,
     "hotel_class": None, "link": "https://none.example"},
    {"name": "가까운 호텔", "type": "hotel", "price_per_night": 120000.0, "total_price": 360000.0, "rating": 4.2, "review_count": 20,
     "hotel_class": 4, "latitude": 37.5430, "longitude": 126.9910, "link": "https://near.example"}],
    "page": "https://www.google.com/travel/search?q=x", "source": "serpapi_hotels"}
TRIP_STATE = {"subject_ref": {"kind": "trip", "id": "T1"}}


def test_the_trip_center_of_the_stay_dates_gives_distances_and_orders_google():
    result, llm, _ = _run(SEARCH, {"read.itinerary": NEAR_TRIP, "read.stay_search": STAYS, "read.stay_google": NEAR_GOOGLE,
                                   "read.stay_detail": lambda a: DETAIL if a["gid"] == 11 else None}, state=TRIP_STATE)
    center = result.decisions[0]["trip_center"]
    assert (center["places"], center["window"], center["usable"]) == (2, True, True), "숙박 기간 밖 · 좌표 없는 장소는 빼고 잰다"
    assert "latitude" not in str(llm.calls[0][2]["trip"]), "좌표는 모델에 주지 않는다"
    answer = result.answer
    assert "거리는 이 숙박 기간 일정 장소 2곳의 가운데에서 잰 직선거리입니다(이동 시간 아님)." in answer
    assert "서울 용산구 이태원로 179 · 일정 가운데에서 1.0km · https://accommodation.myrealtrip.com/union/products/11" in answer
    assert "구글 호텔에서 본 같은 조건 숙소(일정 장소 가운데에서 가까운 순, 숙박 공유 제외):" in answer
    near, none, far = answer.index("가까운 호텔"), answer.index("좌표 없는 호텔"), answer.index("먼 호텔")
    assert near < far < none, "가까운 순, 좌표 없는 곳은 뒤로"
    assert "좌표 없는 호텔 — 1박 110,000원 · 전체 330,000원 · 평점 4.0/5(후기 5) · 거리 모름" in answer


def test_a_spread_out_trip_does_not_use_distance_and_says_so():
    spread = {"trip": {}, "items": [_item("서울역", IN, 37.5547, 126.9707), _item("부산역", OUT, 35.1151, 129.0422)]}
    result, _, _ = _run(SEARCH, {"read.itinerary": spread, "read.stay_search": STAYS, "read.stay_google": NEAR_GOOGLE,
                                 "read.stay_detail": lambda a: DETAIL}, state=TRIP_STATE)
    assert result.decisions[0]["trip_center"]["usable"] is False
    assert "이 숙박 기간 일정 장소 2곳이 넓게 흩어져 있어" in result.answer and "거리는 재지 않았습니다." in result.answer
    assert "일정 가운데에서" not in result.answer and "(구글 순서, 숙박 공유 제외)" in result.answer
    assert result.answer.index("먼 호텔") < result.answer.index("가까운 호텔"), "거리를 안 쓰면 구글 순서 그대로"


def test_without_coordinates_in_the_trip_nothing_about_distance_is_said():
    bare = {"trip": {}, "items": [_item("좌표 없는 일정", IN)]}
    result, _, _ = _run(SEARCH, {"read.itinerary": bare, "read.stay_search": STAYS, "read.stay_detail": lambda a: DETAIL},
                        state=TRIP_STATE)
    assert "trip_center" not in result.decisions[0] and "거리" not in result.answer

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


def test_a_rejected_date_is_shown_back():
    result, _, _ = _run({**SEARCH, "check_in": "2023-11-06", "check_out": "2023-11-09"})
    assert result.decisions[0]["needs"] == ["check_in"]
    assert result.answer.startswith("체크인 날짜 2023-11-06(으)로 읽었는데")


def test_the_prompts_tell_the_model_where_the_year_comes_from():
    from pathlib import Path

    for folder in ("lodging", "flight"):
        # 프롬프트 판이 오르면 파일 이름이 바뀐다(항공은 2026-10-09 v3) — 그 폴더에 하나뿐인 판을 읽는다
        (prompt,) = Path(f"prompts/{folder}").glob("interpret.v*.md")
        assert "take the\n  year from `context.today`" in prompt.read_text(encoding="utf-8")


def test_a_date_whose_quote_is_not_in_the_message_is_cleared_and_asked():
    """☆2026-10-08 15:26 playdata — 「서울에서 3박 할 숙소 추천해줘」에 모델이 체크인을 오늘로 지어냈다."""
    reply = {**SEARCH, "keyword": "서울", "check_in_text": "오늘", "adults": None, "missing": ["adults"],
             "question": "몇 명이 숙소에 머무실 예정인가요?"}
    result, _, tools = _run(reply, text="서울에서 3박 할 숙소 추천해줘")
    assert tools.calls == [] and result.decisions[0]["ungrounded"] == ["check_in"]
    assert result.decisions[0]["needs"] == ["check_in", "adults"]
    assert result.answer.startswith("체크인 날짜 · 성인 인원을(를) 알려 주시면"), "모델 질문(인원만)은 쓰지 않는다"


def test_trip_as_a_quote_needs_a_trip_on_the_case():
    from app.domains.travel_ops.instances.lodging.interpret import ground, parse

    found = parse({**SEARCH, "check_in_text": "trip", "check_out_text": "trip"})
    assert ground(found, "이번 여행 숙소", has_trip=True)[1] == []
    assert ground(found, "이번 여행 숙소", has_trip=False)[1] == ["check_in", "check_out"]
    assert ground(parse({**SEARCH, "check_in_text": None}), "다음 달 6일부터 3박", has_trip=False)[1] == ["check_in"]
    assert ground(parse(SEARCH), "다음 달  6일 부터 3 박", has_trip=False)[1] == [], "공백 차이는 같은 글로 본다"


def test_a_value_the_model_itself_lists_as_missing_is_not_used():
    """☆2026-10-08 15:30 playdata — 체크인을 오늘로 채우고 근거로 「3박」을 인용하면서 missing 에는 check_in 을 넣었다."""
    reply = {**SEARCH, "keyword": "서울", "check_in_text": "3박", "check_out_text": "3박", "adults": None,
             "missing": ["check_in", "check_out", "adults"], "question": "체크인 날짜, 체크아웃 날짜, 성인 수를 알려주세요."}
    result, _, tools = _run(reply, text="서울에서 3박 할 숙소 추천해줘")
    assert tools.calls == [] and result.decisions[0]["ungrounded"] == ["check_in", "check_out"]
    assert result.decisions[0]["needs"] == ["check_in", "check_out", "adults"]
    assert result.answer == "체크인 날짜, 체크아웃 날짜, 성인 수를 알려주세요."
