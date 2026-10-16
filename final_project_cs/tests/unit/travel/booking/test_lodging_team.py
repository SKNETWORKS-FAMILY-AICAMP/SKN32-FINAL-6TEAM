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
from app.domains.travel_ops.instances.lodging.team import google_ts
from app.domains.travel_ops.instances.lodging.interpret import InterpretationInvalid, needs, parse
from app.tools.read_tools import ALLOWED_PROMPT_KEYS

TODAY = datetime.now(ZoneInfo("Asia/Seoul")).date()
#: 「다음 달 6일」 · 「9일」 — 시험 문장과 같은 날. `[2026-10-10]` 서버가 근거 조각의 날(일)에 값을 맞추므로(settle_years) 오늘+30일로 두면 문장과 어긋난다
_NEXT = (TODAY.replace(day=1) + timedelta(days=32)).replace(day=1)
IN, OUT = _NEXT.replace(day=6).isoformat(), _NEXT.replace(day=9).isoformat()
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


def _run(reply, tools=None, *, text="다음 달 6일부터 3박 용산 호텔 성인 2명 찾아줘", capability="lodging.assist", state=None):
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
    assert llm.calls[0][2]["today"] == TODAY.isoformat() and len(llm.calls[0][2]["calendar"]) == 70 and "trip" not in llm.calls[0][2]
    assert tools.calls[0] == ("read.landmark", {"name": "용산"}), "검색 지역 기준점(카카오)을 먼저 — 2026-10-15 검수 D"
    name, arguments = tools.calls[1]
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
    assert ("2. 둘째 호텔 — 1박 150,000원(목록 가격 · 객실은 링크에서 확인) · 평점 없음 · "
            f"https://accommodation.myrealtrip.com/union/products/12?checkIn={IN}&checkOut={OUT}&adultCount=2&childCount=0") in result.answer
    assert "37곳 중 2곳" in result.answer
    sources = [item.source_id for item in result.evidence]
    assert sources == ["lodging.interpret", "read.booking_search_stays", "read.stay_detail:11"], "못 읽은 상세는 근거로 싣지 않는다"
    assert result.decisions[0]["shown"][1] == {"gid": 12, "name": "둘째 호텔", "detail_read": False}


GOOGLE = {"stays": [
    {"name": "Namsan Ville", "type": "vacation rental", "price_per_night": 177960.0, "total_price": 533879.0,
     "rating": None, "review_count": None, "hotel_class": None, "link": "https://www.bluepillow.com/x"},
    {"name": "해밀톤 호텔", "type": "hotel", "price_per_night": 190000.0, "total_price": 570000.0, "rating": 4.0,
     "review_count": 1000, "hotel_class": 3, "link": "https://www.hamilton.co.kr"},
    {"name": "밀리오레호텔 명동", "type": "hotel", "price_per_night": 191878.0, "total_price": 575634.0, "rating": 3.3,
     "review_count": 1076, "hotel_class": 4, "link": "https://migliorehotel.co.kr"}],
    "page": "https://www.google.com/travel/search?q=%EC%9A%A9%EC%82%B0&hl=ko&gl=kr", "source": "serpapi_hotels"}


def test_google_hotels_are_a_separate_block_without_shown_names_and_rentals():
    result, _, _ = _run(SEARCH, {"read.stay_search": STAYS, "read.stay_detail": lambda a: DETAIL if a["gid"] == 11 else None,
                                 "read.stay_google": GOOGLE})
    answer = result.answer
    assert "구글 호텔에서 본 같은 조건 숙소(구글 순서, 숙박 공유 제외):" in answer
    assert ("   · 밀리오레호텔 명동 — 4성급 · 1박 191,878원 · 전체 575,634원 · 평점 3.3/5(후기 1,076): "
            "구글 호텔 https://www.google.com/travel/search?q=%EB%B0%80%EB%A6%AC%EC%98%A4%EB%A0%88%ED%98%B8%ED%85%94%20%EB%AA%85%EB%8F%99&hl=ko&gl=kr"
            f"&ts={google_ts(IN, OUT, 2)} · 숙소 사이트 https://migliorehotel.co.kr") in answer, "링크는 구글 호텔 화면 먼저, 숙소 사이트 뒤(2026-10-15 검수 L01)"
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
    assert [call[0] for call in tools.calls] == ["read.landmark", "read.booking_search_stays"], "쉬는 중이면 상세도 안 부른다"
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
    # `[2026-10-10]` 연도를 말하지 않은 지난 날짜는 서버가 다음 해로 옮기므로(settle_years), 연도를 **말한** 지난 날짜로 본다
    day = TODAY - timedelta(days=3)
    quote = f"{day.year}년 {day.month}월 {day.day}일부터"
    result, _, tools = _run({**SEARCH, "check_in": day.isoformat(), "check_in_text": quote, "missing": []},
                            text=f"{quote} 3박 용산 근처 호텔 찾아줘 2명")
    assert tools.calls == [] and result.decisions[0]["needs"] == ["check_in"]
    assert "체크인 날짜" in result.answer
    # `[2026-10-11]` 끝 근거가 박 수(「3박」)면 서버가 끝 = 시작 + 박 수로 다시 세므로, 끝 근거를 날로 적은 뒤집힌 날짜로 본다
    result, _, tools = _run({**SEARCH, "check_out": IN, "check_out_text": "6일까지", "missing": []}, text="다음 달 6일부터 6일까지 용산 근처 호텔 2명 찾아줘")
    assert tools.calls == [] and result.decisions[0]["needs"] == ["check_out"]


def test_places_without_rooms_are_skipped_and_the_next_ones_fill_in():
    stays = {**STAYS, "stays": [{"gid": n, "name": f"숙소{n}", "description": "", "price_per_night": 100000, "rating": 0.0,
                                 "review_count": None} for n in range(1, 11)]}
    full = lambda a: {**DETAIL, "gid": a["gid"], "no_rooms": a["gid"] == 2}      # noqa: E731
    result, _, tools = _run(SEARCH, {"read.stay_search": stays, "read.stay_detail": full})
    assert [item["gid"] for item in result.decisions[0]["shown"]] == [1, 3, 4]
    assert [item["gid"] for item in result.decisions[0]["skipped"]] == [2]
    assert len(tools.calls) == 4 and "객실이 없는 1곳은 건너뜀" in result.answer and "평점 없음" in result.answer
    assert [item["detail_read"] for item in result.decisions[0]["shown"]] == [True, False, False], "상세는 앞의 2번만(2026-10-10)"
    result, _, tools = _run(SEARCH, {"read.stay_search": stays, "read.stay_detail": {**DETAIL, "sold_out": True}})
    assert len(tools.calls) == 4, "상세는 정한 횟수(2)까지만 부른다(기준점 1 · booking 1)"
    assert [item["gid"] for item in result.decisions[0]["shown"]] == [3, 4, 5], "나머지는 목록 값으로"
    assert "숙소3 — 1박 100,000원(목록 가격 · 객실은 링크에서 확인)" in result.answer


def test_places_without_a_list_price_are_skipped_before_any_detail_call():
    stays = {**STAYS, "stays": [{"gid": n, "name": f"숙소{n}", "description": "", "rating": 4.0, "review_count": 3,
                                 "price_per_night": None if n in (1, 2) else 90000} for n in range(1, 6)]}
    result, _, tools = _run(SEARCH, {"read.stay_search": stays, "read.stay_detail": lambda a: {**DETAIL, "gid": a["gid"]}})
    assert [call[1]["gid"] for call in tools.calls if call[0] == "read.stay_detail"] == [3, 4]
    assert [item["gid"] for item in result.decisions[0]["shown"]] == [3, 4, 5]
    assert [(item["gid"], item["reason"]) for item in result.decisions[0]["skipped"]] == [(1, "no_price_in_list"), (2, "no_price_in_list")]


def test_an_unreadable_detail_stops_further_detail_calls():
    result, _, tools = _run(SEARCH, {"read.stay_search": STAYS, "read.stay_detail": None})
    assert [call[0] for call in tools.calls] == ["read.landmark", "read.booking_search_stays", "read.stay_detail"]
    assert result.decisions[0]["shown"] == [{"gid": 11, "name": "해밀톤 호텔", "detail_read": False},
                                            {"gid": 12, "name": "둘째 호텔", "detail_read": False}], "못 읽은 뒤로는 목록 값으로"


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


def test_my_stay_while_myrealtrip_rests_uses_kakao_and_says_where_it_came_from():
    """`[2026-10-13]` 마이리얼트립이 쉬는 중(429 뒤)이면 카카오 · 관광공사에서 위치만 찾는다. 전에는 쉬는 표시에서 `stays` 를 읽다 멈췄다."""
    kakao = {"source": "kakao", "stays": [
        {"name": "해밀톤호텔", "address": "서울 용산구 이태원로 179", "latitude": 37.5346, "longitude": 126.9941},
        {"name": "해밀톤호텔 주차장", "address": "서울 용산구 이태원로 180", "latitude": 37.5347, "longitude": 126.9942}]}
    result, _, tools = _run(MY_STAY, {"read.stay_search": {"cooldown_seconds": 540, "source": "myrealtrip"},
                                      "read.stay_lookup": kakao})
    assert [name for name, _ in tools.calls] == ["read.stay_search", "read.stay_lookup", "read.stay_google"], \
        "쉬는 중이면 마이리얼트립 상세를 부르지 않는다 · 구글 호텔은 현재 이름으로 한 번"
    assert tools.calls[1][1] == {"name": "해밀톤호텔"} and tools.calls[2][1]["keyword"] == "해밀톤호텔"
    stay = result.decisions[0]["my_stay"]
    assert (stay["name"], stay["latitude"], stay["source"], stay["link"]) == ("해밀톤호텔", 37.5346, "kakao", None)
    assert result.decisions[0]["my_stay_fallback"] == "resting"
    assert result.decisions[0]["google"] == {"asked": False, "matched": False, "detail": False}, "구글 호텔 소스가 없으면 위치만"
    assert "마이리얼트립이 요청 한도로 잠시 쉬는 중이라 카카오맵에 등록된 위치로 알려 드려요" in result.answer
    assert "날짜별 가격 · 예약 링크를 확인하지 못했어요" in result.answer


def test_my_stay_found_elsewhere_gets_google_prices_photo_and_booking_button():
    """`[2026-10-13 사용자 결정]` 마이리얼트립이 429 면 카카오 위치만으로는 보여 줄 게 없다 — 구글 호텔에서 같은 숙소를 찾아 판매처 가격 ·
    사진 · 예약 버튼을 붙인다. ☆12:00 playdata: 카카오 현재 이름으로 물으면 맨 앞(6m). 같은 숙소 = 이름 핵심 같음 + 100m 안(둘 다)."""
    kakao = {"source": "kakao", "stays": [{"name": "더그랜드롯데 서울", "address": "서울 중구 을지로 30",
                                           "latitude": 37.5651, "longitude": 126.9810}]}
    google = {"stays": [
        {"name": "더그랜드롯데 서울 이그제큐티브타워", "type": "hotel", "price_per_night": 400000.0, "latitude": 37.5652,
         "longitude": 126.9811, "link": "https://x", "property_token": "tok-tower", "image": "https://img/tower.jpg"},   # 이름 핵심 다름
        {"name": "더그랜드롯데 서울", "type": "hotel", "price_per_night": 350000.0, "latitude": 37.5651, "longitude": 126.9811,
         "link": "https://www.lottehotel.com/seoul", "property_token": "tok-main", "image": "https://img/main.jpg"},
        {"name": "더그랜드롯데 서울", "type": "hotel", "price_per_night": 1.0, "latitude": 37.60, "longitude": 127.10,
         "link": "https://far", "property_token": "tok-far", "image": None}]}                                              # 이름 같아도 멂
    detail = {"address": "30 Eulji-ro, Jung-gu", "image": None, "sellers": [
        {"seller": "Agoda", "price_per_night": 330000.0, "link": None, "official": False},
        {"seller": "Trip.com", "price_per_night": 340000.0, "link": "https://kr.trip.com/hotels/redirect?hotelid=9&locale=ko-KR", "official": False},
        {"seller": "Lotte Hotel", "price_per_night": 345000.0, "link": "https://www.lottehotel.com/seoul", "official": True}]}
    result, _, tools = _run({**MY_STAY, "stay_name": "롯데호텔 서울"},
                            {"read.stay_search": {"cooldown_seconds": 540, "source": "myrealtrip"}, "read.stay_lookup": kakao,
                             "read.stay_google": google, "read.stay_google_details": lambda a: {"details": {t: detail for t in a["tokens"]}}})
    assert [name for name, _ in tools.calls] == ["read.stay_search", "read.stay_lookup", "read.stay_google", "read.stay_google_details"]
    assert tools.calls[2][1]["keyword"] == "더그랜드롯데 서울", "고객이 말한 옛 이름이 아니라 카카오가 돌려준 현재 이름으로"
    assert tools.calls[3][1]["tokens"] == ["tok-main"], "이름 핵심이 같고 100m 안인 곳 하나만(신관 · 먼 곳은 뺌)"
    stay = result.decisions[0]["my_stay"]
    assert (stay["name"], stay["address"], stay["source"]) == ("더그랜드롯데 서울", "서울 중구 을지로 30", "kakao"), "이름 · 주소는 카카오 것"
    assert (stay["image"], stay["price_per_night"], stay["price_from"]) == ("https://img/main.jpg", 350000.0, 330000.0)
    assert [s["name"] for s in stay["sellers"]] == ["아고다", "트립닷컴", "공식 사이트"]
    assert (stay["link"], stay["link_seller"]) == ("https://kr.trip.com/hotels/redirect?hotelid=9&locale=ko-KR", "트립닷컴"), \
        "예약 버튼은 바로 갈 주소가 있는 가장 싼 판매처(아고다는 광고 링크라 주소 없음)"
    assert result.decisions[0]["google"] == {"asked": True, "matched": True, "detail": True}
    assert ("구글 호텔 기준 1박 330,000원~ (판매처 아고다 330,000원 · 트립닷컴 340,000원 · 공식 사이트 345,000원). "
            "예약은 트립닷컴에서: https://kr.trip.com/hotels/redirect?hotelid=9&locale=ko-KR") in result.answer
    assert "일정에는 아직 넣지 않았습니다" in result.answer
    unmatched, _, _ = _run({**MY_STAY, "stay_name": "롯데호텔 서울"},
                           {"read.stay_search": None, "read.stay_lookup": kakao, "read.stay_google": {"stays": google["stays"][:1]}})
    assert unmatched.decisions[0]["google"] == {"asked": True, "matched": False, "detail": False}
    assert "날짜별 가격 · 예약 링크를 확인하지 못했어요" in unmatched.answer, "같은 숙소가 없으면 위치만 — 옆 건물을 붙이지 않는다"


def test_my_stay_not_on_myrealtrip_is_looked_up_elsewhere_or_said_not_found():
    tour = {"source": "tour_api", "stays": [{"name": "신라스테이 삼성", "address": "서울 강남구 테헤란로 506",
                                             "latitude": 37.5069, "longitude": 127.0589}]}
    found, _, _ = _run({**MY_STAY, "stay_name": "신라스테이 삼성"},
                       {"read.stay_search": {**STAYS, "stays": []}, "read.stay_lookup": tour})
    assert "마이리얼트립에서 찾지 못해 한국관광공사에 등록된 위치로 알려 드려요" in found.answer
    nowhere, _, _ = _run(MY_STAY, {"read.stay_search": {**STAYS, "stays": []}})
    assert nowhere.answer.startswith("「해밀톤호텔」 이름으로 찾은 숙소가 없습니다"), "다른 곳을 부를 수 없으면 전처럼 답한다"
    failed, _, _ = _run(MY_STAY, {})
    assert (failed.outcome, failed.failure_code) == ("escalated", "unknown_숙소 위치"), "어디서도 못 읽었으면 모름 — 위치를 지어내지 않는다"


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
    assert manifest.default_capability == "lodging.assist" and set(manifest.capabilities) == {"lodging.assist", "lodging.status",
                                                                                                    "lodging.itinerary", "lodging.itinerary_question"}


def test_a_rejected_date_is_shown_back():
    # `[2026-10-10]` 연도를 말하지 않으면 서버가 연도를 고치므로, 연도를 **말한** 지난 날짜로 본다
    result, _, _ = _run({**SEARCH, "check_in": "2023-11-06", "check_out": "2023-11-09", "check_in_text": "2023년 11월 6일부터"},
                        text="2023년 11월 6일부터 3박 용산 근처 호텔 찾아줘 2명")
    assert result.decisions[0]["needs"] == ["check_in"] and result.decisions[0]["year_fixed"] == []
    assert result.answer.startswith("체크인 날짜 2023-11-06(으)로 읽었는데")


def test_a_wrong_year_without_a_written_year_is_fixed_by_the_server():
    """☆2026-10-10 17:47 playdata 해석 측정 — 「1월 3일부터 2박 3일」을 2024-01-03~05 로 옮겼다."""
    reply = {**SEARCH, "check_in": "2024-01-03", "check_out": "2024-01-05", "check_in_text": "1월 3일부터", "check_out_text": "2박 3일"}
    result, _, tools = _run(reply, {"read.stay_search": STAYS, "read.stay_detail": lambda a: DETAIL},
                            text="1월 3일부터 2박 3일 용산 호텔 2명")
    got = result.decisions[0]["interpretation"]
    assert got["check_in"][5:] == "01-03" and got["check_in"] > TODAY.isoformat() and got["check_out"][5:] == "01-05"
    assert result.decisions[0]["year_fixed"] == ["check_in", "check_out"] and tools.calls[1][1]["check_in"] == got["check_in"]


def test_the_model_context_carries_a_calendar_to_read_weekdays_from():
    from datetime import date

    from app.domains.travel_ops.instances.lodging.interpret import model_context

    context = model_context(date(2026, 10, 10))
    assert context["today_weekday"] == "토" and context["calendar"][6] == "2026-10-16 금" and len(context["calendar"]) == 70


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
    # `[2026-10-10]` 체크인이 없으면 박 수(「3박」)로 만든 체크아웃도 비운다(interpret_dates.ground_dates)
    assert tools.calls == [] and result.decisions[0]["ungrounded"] == ["check_in", "check_out"]
    assert result.decisions[0]["needs"] == ["check_in", "check_out", "adults"]
    assert result.answer.startswith("체크인 날짜 · 체크아웃 날짜 · 성인 인원을(를) 알려 주시면"), "모델 질문(인원만)은 쓰지 않는다"


def test_trip_as_a_quote_needs_a_trip_on_the_case():
    from app.domains.travel_ops.instances.lodging.interpret import ground, parse

    found = parse({**SEARCH, "check_in_text": "trip", "check_out_text": "trip"})
    assert ground(found, "이번 여행 숙소", has_trip=True)[1] == []
    assert ground(found, "이번 여행 숙소", has_trip=False)[1] == ["check_in", "check_out"]
    assert ground(parse({**SEARCH, "check_in_text": None}), "다음 달 6일부터 3박", has_trip=False)[1] == ["check_in", "check_out"], \
        "체크인이 없으면 박 수로 만든 체크아웃도 비운다(2026-10-10)"
    assert ground(parse(SEARCH), "다음 달  6일 부터 3 박", has_trip=False)[1] == [], "공백 차이는 같은 글로 본다"


def test_a_value_the_model_itself_lists_as_missing_is_not_used():
    """☆2026-10-08 15:30 playdata — 체크인을 오늘로 채우고 근거로 「3박」을 인용하면서 missing 에는 check_in 을 넣었다.

    `[2026-10-10]` 이제 missing 은 보지 않는다(맞는 날짜까지 지웠다). 같은 경우를 「박 수만 적힌 근거는 체크인 근거가 아니다」로 막는다."""
    reply = {**SEARCH, "keyword": "서울", "check_in_text": "3박", "check_out_text": "3박", "adults": None,
             "missing": ["check_in", "check_out", "adults"], "question": "체크인 날짜, 체크아웃 날짜, 성인 수를 알려주세요."}
    result, _, tools = _run(reply, text="서울에서 3박 할 숙소 추천해줘")
    assert tools.calls == [] and result.decisions[0]["ungrounded"] == ["check_in", "check_out"]
    assert result.decisions[0]["needs"] == ["check_in", "check_out", "adults"]
    assert result.answer == "체크인 날짜, 체크아웃 날짜, 성인 수를 알려주세요."


def test_lodging_wishes_without_a_slot_are_named_at_the_end():
    """`[2026-10-11]` ☆사용자 문장 「욕조 있는 숙소」 「얼리체크인」 — 말없이 사라졌다."""
    text = "다음 달 6일부터 3박 용산 근처 욕조 있는 호텔 찾아줘"
    result, _, _ = _run({**SEARCH, "other_requests": ["욕조 있는"]}, {"read.stay_search": STAYS, "read.stay_detail": lambda a: DETAIL},
                        text=text)
    assert result.answer.endswith("말씀하신 조건 중 아직 반영하지 못한 것: 「욕조 있는」 — 링크한 화면에서 직접 확인해 주세요.")
    result, _, _ = _run({**SEARCH, "keyword": None, "other_requests": ["욕조 있는"]}, text=text)
    assert "아직 반영하지 못한 것" in result.answer, "되묻는 답에도 적는다"


# ── 일정 숙소 항목 — `lodging.itinerary` (2026-10-11) ─────────────────
TRIP_ID, STAY_ID = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"


def _plan_item(item_id, seq, kind, title, day, place=None, *, ends=None, **extra):
    return {"item_id": item_id, "seq": seq, "kind": kind, "title": title, "place_id": (place or {}).get("place_id"),
            "starts_at": f"{day}T15:00:00+09:00", "ends_at": f"{ends}T11:00:00+09:00" if ends else None,
            "locked": False, "booking_id": None, "replaces_item_id": None, "detail": {}, "place": place, **extra}


def _plan(stay_kind="lodging", stay_detail=None, booking_id=None):
    hotel = {"place_id": "33333333-3333-4333-8333-333333333333", "name": "기존 호텔", "kind": "lodging",
             "latitude": 37.5600, "longitude": 126.9850, "district": "중구"}
    stay = _plan_item(STAY_ID, 2, stay_kind, "기존 호텔", IN, hotel, ends=OUT, booking_id=booking_id)
    stay["detail"] = dict(stay_detail or {})
    tower = {"place_id": "44444444-4444-4444-8444-444444444444", "name": "남산타워", "latitude": 37.5512, "longitude": 126.9882}
    street = {"place_id": "55555555-5555-4555-8555-555555555555", "name": "이태원 거리", "latitude": 37.5345, "longitude": 126.9946}
    return {"trip": {"trip_id": TRIP_ID, "version": 3, "party_size": 2, "customer_id": "c"},
            "items": [_plan_item("66666666-6666-4666-8666-666666666666", 1, "activity", "남산타워", IN, tower),
                      stay,
                      _plan_item("77777777-7777-4777-8777-777777777777", 3, "activity", "이태원 거리", OUT, street)]}


ITEM_STATE = {"subject_ref": {"kind": "trip", "id": TRIP_ID, "part_id": STAY_ID, "base_version": 3},
              "interpretation": {"report": {"type": "change"}}, "request_id": "r-lodging-1"}


def _itinerary(plan, extra_tools=None):
    tools = {"read.itinerary": plan, "read.stay_search": STAYS, "read.stay_google": NEAR_GOOGLE, **(extra_tools or {})}
    return _run({"task": "unclear"}, tools, text="숙소 다른 데로 바꿔줘", capability="lodging.itinerary", state=ITEM_STATE)


def test_a_case_pointing_at_a_trip_item_is_itinerary_work_and_a_bare_trip_stays_assist():
    assert LodgingTeam.select_capability(None, "x", {"subject_ref": {"kind": "trip", "id": TRIP_ID, "part_id": STAY_ID}}) == "lodging.itinerary"
    assert LodgingTeam.select_capability(None, "x", {"subject_ref": {"kind": "trip", "id": TRIP_ID}}) is None
    assert LodgingTeam.select_capability(None, "x", {}) is None
    question = {"subject_ref": {"kind": "trip", "id": TRIP_ID, "part_id": STAY_ID},
                "interpretation": {"report": {"type": "question"}}}
    assert LodgingTeam.select_capability(None, "x", question) == "lodging.itinerary_question"
    assert {"lodging.itinerary", "lodging.itinerary_question"} <= set(LodgingTeam.manifest.capabilities)
    # 식당 · 활동과 같게 — 규정 질문만 규정을 읽고, 나머지는 규정 검색 결과에 막히지 않는다
    manifest = LodgingTeam.manifest
    assert "policy" in manifest.required_context
    assert set(manifest.policy_optional_capabilities) == {"lodging.assist", "lodging.status", "lodging.itinerary"}
    assert {"read.policy", "read.booking_terms"} <= set(manifest.allowed_tools)


def test_change_on_a_lodging_item_holds_three_new_options_like_dining_and_activity():
    """`[2026-10-12 사용자]` 내보내는 것은 대본이 아니라 후보 — 식당 · 활동처럼 항목의 「다른 안」에 싣고 답은 한 줄."""
    result, llm, tools = _itinerary(_plan())
    assert llm.calls == [], "일정 항목에서 읽는다 — 모델을 부르지 않는다"
    searches = [arguments for name, arguments in tools.calls if name == "read.booking_search_stays"]
    assert searches == [{"keyword": "서울 중구", "check_in": IN, "check_out": OUT, "adults": 2, "children": None,
                         "domestic": True, "size": 20}]
    assert [a["gid"] for name, a in tools.calls if name == "read.stay_detail"] == [11], \
        "`[2026-10-12]` 마이리얼트립은 앞 2곳까지 상세로 좌표를 얻는다 — 첫 상세를 못 읽으면 더 부르지 않는다"
    assert result.outcome == "completed"
    assert result.answer == ("기존 호텔 대신 갈 수 있는 곳이에요 — 1) 가까운 호텔(1박 120,000원 · 원래 숙소에서 2.0km) · "
                             "2) 해밀톤 호텔(1박 188,597원) · 3) 둘째 호텔(1박 150,000원). 고르시면 바꿀게요. 고르지 않으시면 원래 일정을 그대로 둡니다."), \
        "`[2026-10-12]` 원래 숙소에서 3km 안인 곳을 먼저 — 마이리얼트립 목록은 좌표가 없어 그 뒤(모은 순서)"
    (proposal,) = result.action_proposals
    assert proposal.action_type == "itinerary.apply" and proposal.approval_required is False
    arguments = proposal.arguments
    # `[2026-10-13]` 일정은 바꾸지 않는다 — 「선택이 필요해요」 보류 제안으로 내민다(식당 · 활동의 「다른 후보」와 같다). 일정 판 그대로
    assert arguments["reason"] == "requested_options" and arguments["base_version"] == 3
    assert "replacements" not in arguments and "full_items" not in arguments, "후보를 보여 줄 때 일정 판을 올리지 않는다"
    ask = arguments["ask_options"]
    assert ask["item_id"] == STAY_ID and ask["text"] == result.answer
    assert ask["shown_key"] == f"lodging:{IN}:{OUT}", "보여 준 후보는 숙소 · 항공 원장에 적는다(적용기가)"
    options = ask["options"]
    assert [(o["rank"], o["key"], o["name"]) for o in options] == [
        (1, "google:가까운호텔", "가까운 호텔"), (2, "myrealtrip:11", "해밀톤 호텔"), (3, "myrealtrip:12", "둘째 호텔")]
    first = options[1]
    assert {"key", "name", "place_id", "starts_at", "ends_at", "walk_min"} <= set(first), "식당 · 활동의 「다른 안」 칸"
    assert first["place_id"] is None and first["starts_at"] == f"{IN}T15:00:00+09:00" and first["price_per_night"] == 188597
    assert first["link"].startswith("https://accommodation.myrealtrip.com/union/products/11?")
    assert options[0]["latitude"] == 37.5430 and options[0]["distance_km"] == 2.0, "좌표가 있는 후보는 고를 때 그 여행 전용 장소로 들여놓는다"
    assert arguments["summary"]["anchor"] == "원래 숙소" and arguments["summary"]["near"] == 1


def test_choosing_an_option_moves_the_item_to_that_lodging_and_keeps_the_old_one_as_an_option():
    plan = _plan()
    first, _, _ = _itinerary(plan)
    plan["items"][1]["detail"] = _held(first, plan)
    state = {**ITEM_STATE, "subject_ref": {**ITEM_STATE["subject_ref"], "request": {"type": "change", "choice": "myrealtrip:12"}}}
    result, _, tools = _run({"task": "unclear"}, {"read.itinerary": plan}, text="2번으로 할게", capability="lodging.itinerary",
                            state=state)
    assert [name for name, _ in tools.calls] == ["read.itinerary", "read.stay_detail"], \
        "`[2026-10-12]` 고르면 다시 찾지는 않고, 고른 곳 상세만 한 번 더 읽어 가격을 본다"
    assert result.answer.startswith("요청하신 대로 기존 호텔 대신 둘째 호텔(으)로 바꿨습니다. 아직 예약 전이에요 — 예약은 이 링크에서 해 주세요: "
                                    "https://accommodation.myrealtrip.com/union/products/12?")
    assert result.answer.endswith(" 지금 가격은 다시 확인하지 못했어요(보여 드릴 때 1박 150,000원) — 예약 전에 링크에서 확인해 주세요."), \
        "상세를 못 읽었다 — 바꾸되 확인하지 못했다고 적는다"
    new = result.action_proposals[0].arguments["replacements"][0]["item"]
    assert new["title"] == "둘째 호텔" and new["place_id"] is None, "우리 후보는 장소 표에 없다 — 이름 · 링크는 detail.chosen"
    assert new["detail"]["chosen"]["key"] == "myrealtrip:12" and new["detail"]["booked"] is False
    assert [o["name"] for o in new["detail"]["alternates"]] == ["가까운 호텔", "해밀톤 호텔", "기존 호텔"], "원래 숙소는 다른 안 끝으로"
    state["subject_ref"]["request"] = {"type": "change", "choice": "nope"}
    result, _, _ = _run({"task": "unclear"}, {"read.itinerary": plan}, capability="lodging.itinerary", state=state)
    assert result.outcome == "escalated" and result.failure_code == "itinerary_unknown_choice"


def _held(first, plan):
    """`[2026-10-13]` 후보는 이제 보류 제안(`ask_options`)에 있다 — Case 경로 고르기 시험은 그 안을 항목 「다른 안」에 얹어 흉내 낸다."""
    options = first.action_proposals[0].arguments["ask_options"]["options"]
    return {**plan["items"][1]["detail"], "alternates": options, "other_options": [o["name"] for o in options]}


def _choose(choice, detail=None):
    """후보를 보여 준 뒤 `choice` 를 고른다. 고를 때 상세(`read.stay_detail`)는 `detail` 을 돌려준다."""
    plan = _plan()
    first, _, _ = _itinerary(plan)
    plan["items"][1]["detail"] = _held(first, plan)
    state = {**ITEM_STATE, "subject_ref": {**ITEM_STATE["subject_ref"], "request": {"type": "change", "choice": choice}}}
    return _run({"task": "unclear"}, {"read.itinerary": plan, "read.stay_detail": detail}, text="고를게",
                capability="lodging.itinerary", state=state)


def test_choosing_rechecks_the_nightly_price_and_says_it_is_the_same_or_changed():
    """`[2026-10-12]` 고를 때 가격 재확인 — 목록 1박과 상세 1박 평균은 같은 기준(☆10-12 18:22 playdata)."""
    same, _, tools = _choose("myrealtrip:12", {**DETAIL, "gid": 12, "price_per_night": 150000})
    assert [a for name, a in tools.calls if name == "read.stay_detail"] == [
        {"gid": "12", "check_in": IN, "check_out": OUT, "adults": 2, "children": None}]
    assert same.answer.endswith(" 지금 가격도 1박 150,000원 그대로예요.")
    assert same.action_proposals[0].arguments["summary"]["price_check"] == {"status": "same", "before": 150000, "now": 150000, "basis": "list"}
    changed, _, _ = _choose("myrealtrip:12", {**DETAIL, "gid": 12, "price_per_night": 171000})
    assert changed.answer.endswith(" 목록에서는 1박 150,000원이었는데, 예약 화면 기준으로 지금 1박 171,000원이에요."), \
        "보여 줄 때 상세를 못 읽어 목록 값이었다 — 「가격이 바뀌었다」가 아니라 기준이 다르다고 적는다(☆20:28)"
    new = changed.action_proposals[0].arguments["replacements"][0]["item"]
    assert new["detail"]["chosen"]["price_per_night"] == 171000 and new["title"] == "둘째 호텔"
    assert [o["name"] for o in new["detail"]["alternates"]] == ["가까운 호텔", "해밀톤 호텔", "기존 호텔"]


def test_a_stay_whose_detail_was_read_shows_and_rechecks_the_detail_price():
    """`[2026-10-12]` ☆20:28 playdata — 목록 257,044원 · 상세 251,993원. 상세를 읽은 곳은 상세 값으로 보이고, 재확인도 같은 기준이다."""
    from app.domains.travel_ops.instances.lodging.team import _fresh_picks, _price_note

    booked = {"myrealtrip": {"stays": [{"gid": 1, "name": "밀리오레 호텔 서울 명동", "price_per_night": 257044}]}, "google": {"stays": []}}
    (pick,) = _fresh_picks(booked, set(), None, {"check_in": IN, "check_out": OUT}, {"adults": 2, "children": None},
                           details={1: {"price_per_night": 251993}})
    assert (pick["price_per_night"], pick["price_basis"]) == (251993, "detail")
    assert _price_note({"status": "changed", "before": 251993, "now": 260000, "basis": "detail"}) == \
        " 보여 드릴 때 1박 251,993원이던 가격이 지금 1박 260,000원이에요."


def test_a_chosen_stay_without_rooms_now_is_not_applied():
    gone, _, _ = _choose("myrealtrip:12", {**DETAIL, "gid": 12, "no_rooms": True})
    assert gone.action_proposals == []
    assert gone.answer == ("둘째 호텔은(는) 다시 확인해 보니 그 날짜에 남은 객실이 없어요. 일정은 그대로 두었어요. "
                           "다른 후보를 고르시거나 「바꿔 줘」라고 하시면 새로 찾아 드릴게요.")


def test_a_chosen_google_hotel_is_not_rechecked_and_says_so():
    """구글 후보에 `property_token` 이 없으면(옛 판 후보) 다시 볼 수 없다 — 그렇다고 적는다."""
    result, _, tools = _choose("google:가까운호텔", DETAIL)
    assert [name for name, _ in tools.calls] == ["read.itinerary"], "token 이 없으면 다시 볼 도구가 없다"
    assert result.answer.endswith(" 지금 가격은 다시 확인하지 못했어요(보여 드릴 때 1박 120,000원) — 예약 전에 링크에서 확인해 주세요.")
    assert result.action_proposals[0].arguments["summary"]["price_check"]["reason"] == "no_recheck_tool"


def _choose_google(detail_now, *, listed=120000.0):
    """구글 후보(token 있음)를 보여 준 뒤 고른다. 고를 때 상세(`read.stay_google_details`)는 `detail_now` 를 돌려준다."""
    google = {**NEAR_GOOGLE, "stays": [{**row, "property_token": f"tok-{i}", "image": None} for i, row in enumerate(NEAR_GOOGLE["stays"])]}
    shown = {"address": None, "image": None, "sellers": [
        {"seller": "Agoda", "price_per_night": listed - 5000, "link": None, "official": False},
        {"seller": "Trip.com", "price_per_night": listed, "link": "https://kr.trip.com/x", "official": False}]}
    calls = {"n": 0}

    def details(a):
        calls["n"] += 1
        return {"details": {t: (shown if calls["n"] == 1 else detail_now) for t in a["tokens"]}}
    plan = _plan()
    first, _, _ = _itinerary(plan, {"read.stay_google": google, "read.stay_google_details": details})
    plan["items"][1]["detail"] = _held(first, plan)
    state = {**ITEM_STATE, "subject_ref": {**ITEM_STATE["subject_ref"], "request": {"type": "change", "choice": "google:가까운호텔"}}}
    return _run({"task": "unclear"}, {"read.itinerary": plan, "read.stay_google": google, "read.stay_google_details": details},
                text="고를게", capability="lodging.itinerary", state=state)


def test_a_chosen_google_hotel_is_rechecked_by_its_seller_prices():
    """`[2026-10-13]` 구글 후보도 고를 때 상세를 다시 읽어 **판매처 최저가끼리** 비교한다(SerpApi 1회). 전에는 「확인 못 함」."""
    same_detail = {"address": None, "image": None, "sellers": [
        {"seller": "Agoda", "price_per_night": 115000.0, "link": None, "official": False},
        {"seller": "Trip.com", "price_per_night": 120000.0, "link": "https://kr.trip.com/x", "official": False}]}
    same, _, tools = _choose_google(same_detail)
    recheck = [a for name, a in tools.calls if name == "read.stay_google_details"]
    assert recheck[-1]["tokens"] == ["tok-2"] and recheck[-1]["check_in"] == IN
    assert same.answer.endswith(" 지금도 판매처 최저가 1박 115,000원~ 그대로예요.")
    assert same.action_proposals[0].arguments["summary"]["price_check"] == {"status": "same", "before": 115000.0, "now": 115000.0, "basis": "sellers"}
    changed_detail = {"address": None, "image": None, "sellers": [
        {"seller": "Trip.com", "price_per_night": 131000.0, "link": "https://kr.trip.com/y", "official": False},
        {"seller": "Agoda", "price_per_night": 140000.0, "link": None, "official": False}]}
    changed, _, _ = _choose_google(changed_detail)
    assert changed.answer.endswith(" 보여 드릴 때 1박 115,000원~이던 판매처 최저가가 지금 1박 131,000원~이에요.")
    chosen = changed.action_proposals[0].arguments["replacements"][0]["item"]["detail"]["chosen"]
    assert (chosen["price_from"], chosen["link"], chosen["link_seller"], [s["name"] for s in chosen["sellers"]]) == \
        (131000.0, "https://kr.trip.com/y", "트립닷컴", ["트립닷컴", "아고다"]), "바뀌면 판매처 · 예약 버튼 · 「1박 ○원~」도 새 값"
    assert "예약은 이 링크에서 해 주세요: https://kr.trip.com/y" in changed.answer
    empty, _, _ = _choose_google({"address": None, "image": None, "sellers": []})
    assert empty.action_proposals and empty.action_proposals[0].arguments["summary"]["price_check"]["reason"] == "no_price", \
        "판매처가 없으면 「없어졌다」가 아니라 확인 못 함 — 매진인지 표시만 안 된 건지 가를 수 없다"
    assert "지금 가격은 다시 확인하지 못했어요(보여 드릴 때 1박 115,000원)" in empty.answer


def test_the_same_stay_from_both_sources_is_shown_once_as_myrealtrip():
    """`[2026-10-12]` ☆18:53 playdata 명동 — 「밀리오레 호텔 서울 명동」(마이리얼트립)과 「밀리오레호텔 명동」(구글)이 42m. 이름 핵심이 같고
    100m 안이면 같은 숙소로 보고 마이리얼트립만 남긴다. 핵심이 같아도 멀면 다른 숙소, 한쪽이 다른 쪽을 품는 이름은 다른 숙소."""
    from app.domains.travel_ops.instances.lodging.team import _core, _fresh_picks

    assert _core("밀리오레 호텔 서울 명동") == _core("밀리오레호텔 명동") == "밀리오레명동"
    booked = {"myrealtrip": {"stays": [{"gid": 1, "name": "밀리오레 호텔 서울 명동", "price_per_night": 250342},
                                       {"gid": 2, "name": "롯데시티호텔 명동", "price_per_night": 300000},
                                       {"gid": 3, "name": "스탠포드호텔 명동", "price_per_night": 200000}]},
              "google": {"stays": [
                  {"name": "밀리오레호텔 명동", "type": "hotel", "price_per_night": 240000.0, "latitude": 37.56372, "longitude": 126.98290,
                   "link": "https://g/1"},
                  {"name": "롯데시티호텔 명동", "type": "hotel", "price_per_night": 290000.0, "latitude": 37.5650, "longitude": 126.9840,
                   "link": "https://g/2"},
                  {"name": "카페스탠포드 명동", "type": "hotel", "price_per_night": 150000.0, "latitude": 37.5600, "longitude": 126.9860,
                   "link": "https://g/3"}]}}
    details = {1: {"latitude": 37.56340, "longitude": 126.98270}}
    picks = _fresh_picks(booked, set(), None, {"check_in": IN, "check_out": OUT}, {"adults": 2, "children": None}, details=details)
    picks += _fresh_picks(booked, {p["name"] for p in picks}, None, {"check_in": IN, "check_out": OUT},
                          {"adults": 2, "children": None}, details=details)
    names = [pick["name"] for pick in picks]
    assert "밀리오레호텔 명동" not in names and "밀리오레 호텔 서울 명동" in names, "42m · 같은 핵심 — 마이리얼트립만"
    assert "카페스탠포드 명동" in names, "이름을 품는 것은 같은 숙소로 보지 않는다"
    assert names.count("롯데시티호텔 명동") == 1, "마이리얼트립 좌표를 모르면 이름 핵심만으로 묶는다"
    far = {"myrealtrip": {"stays": booked["myrealtrip"]["stays"][:1]},
           "google": {"stays": [{**booked["google"]["stays"][0], "latitude": 37.5700}]}}
    names = [p["name"] for p in _fresh_picks(far, set(), None, {"check_in": IN, "check_out": OUT}, {"adults": 2, "children": None},
                                             details=details)]
    assert "밀리오레호텔 명동" in names, "핵심이 같아도 100m 넘게 떨어지면 다른 숙소(지점)로 본다"


def test_a_stay_shown_before_does_not_come_back_under_the_other_sources_name():
    from app.domains.travel_ops.instances.lodging.team import _fresh_picks

    booked = {"myrealtrip": {"stays": []}, "google": {"stays": [
        {"name": "밀리오레호텔 명동", "type": "hotel", "price_per_night": 240000.0, "latitude": 37.5637, "longitude": 126.9829,
         "link": "https://g/1"}]}}
    assert _fresh_picks(booked, {"밀리오레호텔서울명동"}, None, {"check_in": IN, "check_out": OUT}, {"adults": 2, "children": None}) == []


def test_google_options_carry_seller_prices_photo_and_address():
    """`[2026-10-13 사용자 결정]` 후보 3곳 모두 판매처 가격 — 구글 호텔 후보는 상세를 한 번에 읽어 한국인이 많이 쓰는 판매처 · 공식 사이트를
    싼 순 3곳까지 붙인다. 화면에 보일 것은 이름 · 가격 · 링크 · 사진."""
    google = {**NEAR_GOOGLE, "stays": [{**row, "property_token": f"tok-{i}", "image": f"https://img/{i}.jpg"}
                                       for i, row in enumerate(NEAR_GOOGLE["stays"])]}
    detail = {"address": "서울 용산구 어딘가", "image": None, "sellers": [
        {"seller": "Agoda", "price_per_night": 125000.0, "link": None, "official": False},
        {"seller": "Trip.com", "price_per_night": 118000.0, "link": "https://us.trip.com/hotels/redirect?hotelid=1", "official": False},
        {"seller": "Vio.com", "price_per_night": 99000.0, "link": "https://vio.example", "official": False},
        {"seller": "가까운 호텔", "price_per_night": 117000.0, "link": None, "official": True},
        {"seller": "Booking.com", "price_per_night": 130000.0, "link": None, "official": False}]}
    result, _, tools = _itinerary(_plan(), {"read.stay_google": google,
                                            "read.stay_google_details": lambda a: {"details": {t: detail for t in a["tokens"]}}})
    (asked,) = [a for name, a in tools.calls if name == "read.stay_google_details"]
    assert asked["tokens"] == ["tok-2"] and asked["keyword"] == "서울 중구", "구글 호텔 후보만, 한 번에"
    assert "1) 가까운 호텔(1박 117,000원~ · 원래 숙소에서 2.0km · 판매처 공식 사이트 117,000원 · 트립닷컴 118,000원 · 아고다 125,000원)" in result.answer, \
        "Vio.com 처럼 목록에 없는 판매처는 빼고, 싼 순 3곳. `[2026-10-13 사용자 결정]` 대표 가격은 가장 싼 곳 「○원~」(목록 120,000원보다 공식 117,000원)"
    option = result.action_proposals[0].arguments["ask_options"]["options"][0]
    assert (option["image"], option["address"]) == ("https://img/2.jpg", "서울 용산구 어딘가")
    assert (option["price_from"], option["price_per_night"]) == (117000.0, 120000), "순서 · 재확인은 목록 값 그대로"
    assert (option["link"], option["link_seller"]) == ("https://us.trip.com/hotels/redirect?hotelid=1", "트립닷컴"), \
        "예약 버튼은 바로 갈 주소가 있는 가장 싼 판매처 — 공식 사이트(117,000원)는 주소가 없어 트립닷컴(118,000원)"
    assert result.action_proposals[0].arguments["summary"]["google_details"] == {"asked": 1, "read": 1}


def test_a_google_option_named_in_japanese_is_shown_with_the_detail_korean_name():
    """`[2026-10-13]` ☆14:03 playdata 명동: 구글 목록이 hl=ko 인데도 「相鉄フレッサイン ソウル明洞」로 왔다 — 상세 이름이 한글이면 그걸 보이고,
    원래 이름은 `source_name` · `shown` 에 남겨 다음 「바꿔 줘」에서 같은 곳이 다시 안 나오게 한다. 상세도 원어면 그대로."""
    rows = [{**row, "property_token": f"tok-{i}", "image": None} for i, row in enumerate(NEAR_GOOGLE["stays"])]
    rows[2] = {**rows[2], "name": "相鉄フレッサイン ソウル明洞"}
    detail = {"name": "소테츠 프레사 인 서울 명동", "address": "서울 중구", "image": None,
              "sellers": [{"seller": "Agoda", "price_per_night": 125000.0, "link": None, "official": False}]}
    result, _, _ = _itinerary(_plan(), {"read.stay_google": {**NEAR_GOOGLE, "stays": rows},
                                        "read.stay_google_details": lambda a: {"details": {t: detail for t in a["tokens"]}}})
    option = result.action_proposals[0].arguments["ask_options"]["options"][0]
    assert (option["name"], option["source_name"], option["key"]) == ("소테츠 프레사 인 서울 명동", "相鉄フレッサイン ソウル明洞", "google:相鉄フレッサインソウル明洞"), \
        "보이는 이름은 한글, 키 · source_name 은 목록 이름 그대로"
    assert "1) 소테츠 프레사 인 서울 명동(" in result.answer and "相鉄" not in result.answer
    # `[2026-10-13]` 보여 준 후보는 원장에 「보인 이름」으로 남는다 — 다음 「바꿔 줘」는 후보 key(google:<목록 이름 열쇠>)로도 뺀다
    shown = {"offers": [{"key": option["key"], "name": option["name"]}]}
    again, _, _ = _itinerary(_plan(), {"read.stay_google": {**NEAR_GOOGLE, "stays": rows}, "read.offers_shown": shown,
                                       "read.stay_google_details": lambda a: {"details": {t: detail for t in a["tokens"]}}})
    assert "소테츠" not in again.answer and "相鉄" not in again.answer, "원어 이름으로 다시 와도 같은 곳은 빠진다"
    same, _, _ = _itinerary(_plan(), {"read.stay_google": {**NEAR_GOOGLE, "stays": rows},
                                      "read.stay_google_details": lambda a: {"details": {t: {**detail, "name": "相鉄フレッサイン"} for t in a["tokens"]}}})
    option = same.action_proposals[0].arguments["ask_options"]["options"][0]
    assert (option["name"], option["source_name"]) == ("相鉄フレッサイン ソウル明洞", None), "상세도 원어면 목록 이름 그대로(지어내지 않는다)"


def test_a_resting_source_is_said_in_the_change_answer():
    """`[2026-10-13]` 마이리얼트립이 쉬는 중(429)이면 「바꿔 줘」 답 끝에 그렇다고 적는다(항공 팀과 같은 꼴). 조회 실패(시험의 빈 구글)는 적지 않는다."""
    resting = {"cooldown_seconds": 540, "source": "myrealtrip"}
    result, _, _ = _itinerary(_plan(), {"read.stay_search": resting, "read.stay_google": NEAR_GOOGLE})
    assert "마이리얼트립은 요청 한도로 잠시 쉬는 중이에요 — 그쪽 숙소는 빠져 있어요. 고르시면 바꿀게요." in result.answer
    assert result.decisions[0]["sources"] == {"myrealtrip": "resting", "google": "ok"}
    assert [o["source"] for o in result.action_proposals[0].arguments["ask_options"]["options"]] == ["구글 호텔"] * 3
    plain, _, _ = _itinerary(_plan())
    assert "쉬는 중" not in plain.answer and plain.decisions[0]["sources"] == {"myrealtrip": "ok", "google": "ok"}


def test_change_again_skips_what_was_already_shown():
    result, _, _ = _itinerary(_plan(stay_detail={"shown": ["해밀톤 호텔", "둘째 호텔", "가까운 호텔"]}))
    assert result.answer.startswith("기존 호텔 대신 갈 수 있는 곳이에요 — 1) 먼 호텔(1박 100,000원 · 원래 숙소에서 11.5km) · "
                                    "2) 좌표 없는 호텔(1박 110,000원).")
    assert result.action_proposals[0].arguments["summary"]["shown_total"] == 5


def test_change_again_skips_what_the_ledger_says_was_shown():
    """`[2026-10-13]` 보여 준 후보는 숙소 · 항공 원장에 있다(`read.offers_shown`) — 항목 상세에 없어도 뺀다."""
    shown = {"item_key": f"lodging:{IN}:{OUT}", "offers": [{"key": "google:가까운호텔", "name": "가까운 호텔"},
                                                         {"key": "myrealtrip:11", "name": "해밀톤 호텔"},
                                                         {"key": "myrealtrip:12", "name": "둘째 호텔"}]}
    result, _, tools = _itinerary(_plan(), {"read.offers_shown": shown})
    assert [a for name, a in tools.calls if name == "read.offers_shown"] == [
        {"trip_id": TRIP_ID, "item_key": f"lodging:{IN}:{OUT}"}]
    assert [o["name"] for o in result.action_proposals[0].arguments["ask_options"]["options"]] == ["먼 호텔", "좌표 없는 호텔"]


def test_alternates_near_the_old_stay_and_in_its_price_band_come_first():
    """`[2026-10-12]` 원래 1박 가격을 알면 ±30% 안을 먼저, 그 안에서 원래 숙소 3km 안을 가까운 순으로, 나머지는 모은 순서."""
    result, _, _ = _itinerary(_plan(stay_detail={"price_per_night": 110000}))
    options = result.action_proposals[0].arguments["ask_options"]["options"]
    assert [o["name"] for o in options] == ["가까운 호텔", "먼 호텔", "해밀톤 호텔"], \
        "77,000~143,000원 안(가까운 · 먼)이 먼저 — 셋째는 마이리얼트립이 하나도 없어 마이리얼트립 첫 곳으로 바꾼다"
    assert result.decisions[0]["anchor"] == "원래 숙소"


def test_myrealtrip_details_give_distances_and_drop_full_stays():
    """`[2026-10-12]` 마이리얼트립 목록에는 좌표가 없어 앞 2곳만 상세로 좌표 · 객실 여부를 얻는다."""
    full = {**DETAIL, "gid": 12, "name": "둘째 호텔", "no_rooms": True}
    result, _, tools = _itinerary(_plan(), {"read.stay_detail": lambda a: DETAIL if a["gid"] == 11 else full})
    assert [a["gid"] for name, a in tools.calls if name == "read.stay_detail"] == [11, 12]
    options = result.action_proposals[0].arguments["ask_options"]["options"]
    assert [o["name"] for o in options] == ["가까운 호텔", "해밀톤 호텔", "먼 호텔"], "해밀톤은 2.9km 라 가까운 곳 · 둘째는 객실 없어 뺌"
    assert "해밀톤 호텔(1박 188,597원 · 원래 숙소에서 2.9km)" in result.answer
    assert result.decisions[0]["details_read"] == 2 and result.decisions[0]["near"] == 2


def test_without_the_old_stays_coordinates_the_trip_center_is_the_anchor():
    plan = _plan()
    plan["items"][1]["place"] = {"name": "기존 호텔", "district": "중구"}
    result, _, _ = _itinerary(plan)
    assert result.decisions[0]["anchor"] == "일정 가운데"
    assert "일정 가운데에서" in result.answer


def _with_conditions(plan, **conditions):
    state = {**ITEM_STATE, "interpretation": {"report": {"type": "change", **conditions}}}
    tools = {"read.itinerary": plan, "read.stay_search": STAYS, "read.stay_google": NEAR_GOOGLE}
    return _run({"task": "unclear"}, tools, text="더 싼 데로 바꿔줘", capability="lodging.itinerary", state=state)


def test_a_price_limit_from_the_intake_keeps_only_stays_under_it():
    """`[2026-10-12]` 조건은 접수 해석이 뽑아 넘긴다(사용자 결정) — 문장을 다시 해석하지 않고 `max_price` 칸만 읽는다."""
    result, llm, _ = _with_conditions(_plan(), max_price=130000)
    assert llm.calls == []
    options = result.action_proposals[0].arguments["ask_options"]["options"]
    assert [o["name"] for o in options] == ["가까운 호텔", "먼 호텔", "좌표 없는 호텔"], "13만 원 넘는 해밀톤 · 둘째는 뺀다"
    assert "말씀하신 대로 1박 130,000원 이하만 골랐어요." in result.answer
    assert result.decisions[0]["conditions"]["price_limit"] == 130000


def test_cheaper_uses_the_old_stays_price_or_says_it_sorted_by_price():
    result, _, _ = _with_conditions(_plan(stay_detail={"price_per_night": 120000}), cheaper=True)
    options = result.action_proposals[0].arguments["ask_options"]["options"]
    assert [o["name"] for o in options] == ["먼 호텔", "좌표 없는 호텔"], "원래 12만 원보다 싼 곳만"
    assert "원래 숙소(1박 120,000원)보다 싼 곳만 골랐어요." in result.answer
    result, _, _ = _with_conditions(_plan(), cheaper=True)
    options = result.action_proposals[0].arguments["ask_options"]["options"]
    assert [o["price_per_night"] for o in options] == [100000.0, 110000.0, 120000.0], "원래 가격을 모르면 낮은 순"
    assert "원래 숙소 가격을 몰라 1박 가격이 낮은 순으로 골랐어요." in result.answer


def test_a_price_limit_nothing_meets_says_so_without_changing_the_plan():
    result, _, tools = _with_conditions(_plan(), max_price=50000)
    assert [a["size"] for name, a in tools.calls if name == "read.booking_search_stays"] == [20, 50]
    assert result.action_proposals == []
    assert result.answer == "기존 호텔 대신 갈 수 있는 1박 50,000원 이하 숙소를 더 찾지 못했어요. 일정은 그대로 두었어요."


def test_when_nothing_new_is_left_it_widens_once_then_says_so_without_changing_the_plan():
    every = ["해밀톤 호텔", "둘째 호텔", "가까운 호텔", "먼 호텔", "좌표 없는 호텔"]
    result, _, tools = _itinerary(_plan(stay_detail={"shown": every}))
    sizes = [arguments["size"] for name, arguments in tools.calls if name == "read.booking_search_stays"]
    assert sizes == [20, 50]
    assert result.outcome == "completed" and result.action_proposals == []
    assert result.answer == "기존 호텔 대신 갈 수 있는 숙소를 더 찾지 못했어요. 일정은 그대로 두었어요."


def test_a_booked_lodging_is_never_changed_and_nothing_is_searched():
    result, _, tools = _itinerary(_plan(booking_id="88888888-8888-4888-8888-888888888888"))
    assert "이미 예약하신 숙소라 바꾸지 않았어요" in result.answer
    assert result.action_proposals == [] and result.decisions[0]["itinerary"] == "booked_kept"
    assert [name for name, _ in tools.calls] == ["read.itinerary"]


def test_an_item_of_another_kind_is_not_lodging_work():
    result, _, tools = _itinerary(_plan(stay_kind="activity"))
    assert result.outcome == "escalated" and result.failure_code == "target_kind_mismatch"
    assert [name for name, _ in tools.calls] == ["read.itinerary"]


def test_an_empty_myrealtrip_list_with_google_hotels_is_not_said_as_no_stays():
    """`[2026-10-15 검수 · GPT 검토 #10]` 마이리얼트립 목록이 비어도 구글 호텔에 후보가 있으면 「숙소가 없습니다」라고 하지 않는다."""
    result, _, _ = _run(SEARCH, {"read.stay_search": {**STAYS, "stays": [], "total": 0}, "read.stay_google": GOOGLE})
    assert "찾은 숙소가 없습니다" not in result.answer and "마이리얼트립에서는 숙소를 찾지 못했습니다" in result.answer
    assert "구글 호텔에서 본 같은 조건 숙소" in result.answer and result.decisions[0]["google"] == 3


# ── 검수 D(2026-10-15): 지역 · 유형 · 성급 · 싼 순 · 거리 · 아이 · 내 숙소 ───────────────
from app.domains.travel_ops.instances.lodging.wants import read_wants, stay_city, stay_kinds, stay_stars, strip_handled  # noqa: E402

SEONGSU = {"source": "kakao", "found": True, "name": "성수역 2호선", "latitude": 37.5446, "longitude": 127.0559}
GANGNAM = {"source": "kakao", "found": True, "name": "강남역 2호선", "latitude": 37.4979, "longitude": 127.0276}


def _listing(rows, total=None):
    return {"stays": [{"gid": gid, "name": name, "description": about, "price_per_night": price, "rating": 4.0, "review_count": 10}
                      for gid, name, about, price in rows], "total": total or len(rows), "source": "myrealtrip"}


def _google(rows):
    return {"stays": [{"name": name, "type": "hotel", "price_per_night": price, "total_price": price, "rating": 4.0, "review_count": 9,
                       "hotel_class": stars, "latitude": lat, "longitude": lon, "link": f"https://{gid}.example"}
                      for gid, (name, price, stars, lat, lon) in enumerate(rows)], "page": "https://www.google.com/travel/search?q=x"}


def test_rules_read_kind_stars_cheap_and_distance_words():
    """서버 규칙(사용자 결정 10-15) — 검수 문장 L01 · L03 · L05 · L06 · L09 · L12."""
    couple = read_wants("여자친구랑 성수 쪽 분위기 좋은 숙소")
    assert couple.no_dorm and strip_handled(["여자친구랑", "분위기 좋은 숙소"], couple, near_done=False) == ["분위기 좋은 숙소"], \
        "동행 말은 반영(호스텔 · 게스트하우스 제외), 「분위기」는 반영 못 함으로 남긴다(☆10-15 17:32 L01)"
    walk = read_wants("강남역 걸어갈 수 있는 비즈니스호텔, 1박 10만 원대")
    assert (walk.kind, walk.near) == ("호텔", "walk")
    assert read_wants("홍대 게스트하우스 1박 5만 원 이하").kind == "게스트하우스"
    hanok = read_wants("경복궁 근처 한옥 숙소 3명")
    assert (hanok.kind, hanok.near) == ("한옥", "near")
    five = read_wants("한강 보이는 5성급 호텔 2명")
    assert (five.stars, five.no_dorm) == (5.0, True)
    assert read_wants("서울 아무 데나 싼 곳 3명").cheapest and not read_wants("비싼 곳도 괜찮아").cheapest
    assert read_wants("호스텔 말고 조용한 곳").avoid == {"호스텔"} and read_wants("성인 1명 1박").stars is None
    assert stay_kinds("게스트하우스 · 송파 · 서울", "호스텔 베네") == {"게스트하우스", "호스텔"}
    assert (stay_city("모텔 · 군산"), stay_city("3성급 · 호텔 · 강남 · 서울"), stay_city("호텔")) == ("군산", "서울", None)
    assert (stay_stars("2.5성급 · 호텔 · 강남 · 서울"), stay_stars(None, 4), stay_stars("")) == (2.5, 4.0, None)


def test_a_seoul_search_drops_other_cities_and_far_google_hotels():
    """☆10-15 검수 L01 「성수」에 「군산 성수」(모텔 · 군산), L03 「강남역」에 속초 · 부산 호텔."""
    listing = _listing([(1, "파루스셀라 성수", "호텔 · 성동 · 서울", 160000), (2, "군산 성수", "모텔 · 군산", 43000),
                        (3, "건대 성수스테이", "", 150000)])
    google = _google([("속초 마리나베이", 42000.0, 4, 38.19, 128.60), ("서울숲 호텔", 90000.0, 3, 37.5440, 127.0420)])
    detail = lambda a: {**DETAIL, "gid": a["gid"], "latitude": 37.5440, "longitude": 127.0560}      # noqa: E731
    reply = {**SEARCH, "keyword": "성수", "max_price_per_night": 200000, "min_rating": None}
    result, _, tools = _run(reply, {"read.landmark": SEONGSU, "read.stay_search": listing, "read.stay_detail": detail,
                                    "read.stay_google": google}, text="다음 달 6일부터 3박 성수 숙소 2명")
    assert [item["gid"] for item in result.decisions[0]["shown"]] == [1, 3]
    assert result.decisions[0]["dropped"] == {"region": 1} and "다른 지역 1곳은 뺌" in result.answer
    assert "군산" not in result.answer.split("구글 호텔")[0] and "속초 마리나베이" not in result.answer and "서울숲 호텔" in result.answer
    google_call = next(arguments for name, arguments in tools.source_calls if name == "read.stay_google")
    mrt_call = next(arguments for name, arguments in tools.source_calls if name == "read.stay_search")
    assert (google_call["keyword"], mrt_call["keyword"]) == ("서울 성수", "성수"), "구글 호텔에만 「서울」을 붙인다"


def test_wanted_kind_and_stars_filter_the_lists_and_unmet_ones_are_said():
    listing = _listing([(1, "명동 비즈호텔", "3성급 · 호텔 · 중구 · 서울", 120000), (2, "북촌 한옥 스테이", "한옥 · 종로 · 서울", 180000),
                        (3, "종로 게스트하우스", "게스트하우스 · 종로 · 서울", 50000)])
    google = _google([("청춘재", 400000.0, None, 37.5800, 126.9850), ("광화문 호스텔", 40000.0, None, 37.5720, 126.9770),
                      ("북촌 한옥 담박재", 600000.0, None, 37.5820, 126.9840)])
    reply = {**SEARCH, "keyword": "경복궁", "max_price_per_night": None, "min_rating": None, "other_requests": ["한옥 숙소"]}
    spot = {"source": "kakao", "found": True, "name": "경복궁", "latitude": 37.5796, "longitude": 126.9770}
    result, _, tools = _run(reply, {"read.landmark": spot, "read.stay_search": listing, "read.stay_google": google,
                                    "read.stay_detail": lambda a: {**DETAIL, "gid": a["gid"], "latitude": 37.5820, "longitude": 126.9830}},
                            text="다음 달 6일부터 3박 경복궁 근처 한옥 숙소 2명")
    assert [item["gid"] for item in result.decisions[0]["shown"]] == [2], "한옥만"
    assert "반영한 조건: 한옥만 · 경복궁에서 직선 3km 안." in result.answer and "한옥 아님 2곳" in result.answer
    assert "북촌 한옥 담박재" in result.answer and "청춘재" not in result.answer and "광화문 호스텔" not in result.answer, \
        "한옥은 구글 칸도 이름에 「한옥」이 있을 때만(☆사용자 판정 L06 「나인트리 인사동」)"
    assert next(a for n, a in tools.source_calls if n == "read.stay_google")["keyword"] == "서울 경복궁 한옥"
    assert "아직 반영하지 못한 것" not in result.answer, "규칙이 반영한 「한옥」은 반영 못 함 목록에서 뺀다"

    five = _listing([(1, "3성 호텔", "3성급 · 호텔 · 용산 · 서울", 150000), (2, "5성 호텔", "5성급 · 호텔 · 용산 · 서울", 190000)])
    result, _, _ = _run({**SEARCH, "min_rating": None}, {"read.stay_search": five, "read.stay_detail": lambda a: None,
                                                         "read.stay_google": _google([("4성 호텔", 150000.0, 4, None, None)])},
                        text="다음 달 6일부터 3박 용산 5성급 호텔 2명")
    assert [item["gid"] for item in result.decisions[0]["shown"]] == [2] and "5성급 미만이거나 성급 모름 1곳" in result.answer
    assert "4성 호텔" not in result.answer


def test_cheap_requests_sort_by_price_inside_a_bigger_list_and_google_obeys_the_price_cap():
    listing = _listing([(1, "비싼 곳", "", 380000), (2, "싼 곳", "", 90000), (3, "중간", "", 150000)])
    google = _google([("상한 넘음", 50135.0, 3, None, None), ("상한 안", 40000.0, 2, None, None)])
    reply = {**SEARCH, "keyword": "서울", "max_price_per_night": None, "min_rating": None}
    result, _, tools = _run(reply, {"read.stay_search": listing, "read.stay_detail": lambda a: None, "read.stay_google": google},
                            text="다음 달 6일부터 3박 서울 아무 데나 싼 곳 2명")
    assert [item["gid"] for item in result.decisions[0]["shown"]] == [2, 3, 1]
    assert "받은 3곳 안에서 1박 가격 낮은 순" in result.answer
    assert next(a for n, a in tools.calls if n == "read.booking_search_stays")["size"] == 50
    assert "read.landmark" not in [n for n, _ in tools.calls], "「서울」 전체면 기준점을 찾지 않는다(☆17:49 L12 「청계천에서 16km」)"
    capped = {**SEARCH, "keyword": "홍대", "max_price_per_night": 50000, "min_rating": None}
    result, _, _ = _run(capped, {"read.stay_search": _listing([]), "read.stay_google": google}, text="다음 달 6일부터 3박 홍대 1박 5만 원 이하 2명")
    assert "상한 안" in result.answer and "상한 넘음" not in result.answer, "☆L05 50,135원 — 1박 상한을 넘으면 뺀다"


def test_walking_distance_uses_the_kakao_anchor_and_drops_far_places():
    """☆L03 「강남역 걸어갈 수 있는」 — 2 · 3번이 도보 20분이었다. 상세 좌표 · 카카오 위치로 1km 넘는 곳을 뺀다."""
    listing = _listing([(1, "먼 호텔", "호텔 · 강남 · 서울", 120000), (2, "가까운 호텔", "호텔 · 강남 · 서울", 130000),
                        (3, "토요코인 서울 강남", "호텔 · 강남 · 서울", 139000), (4, "위치 모를 호텔", "호텔 · 강남 · 서울", 110000),
                        (5, "다섯째 호텔", "호텔 · 강남 · 서울", 100000)])
    coords = {1: (37.4870, 127.0450), 2: (37.4990, 127.0290)}
    detail = lambda a: {**DETAIL, "gid": a["gid"], "latitude": coords[a["gid"]][0], "longitude": coords[a["gid"]][1]}   # noqa: E731
    lookup = lambda a: {"source": "kakao", "stays": [{"name": "토요코인서울강남", "address": "서울 서초구", "latitude": 37.5010,   # noqa: E731
                                                     "longitude": 127.0250}]} if "토요코인" in a["name"] else {"source": "kakao", "stays": []}
    reply = {**SEARCH, "keyword": "강남역", "adults": 1, "max_price_per_night": 199999, "min_rating": None}
    result, _, tools = _run(reply, {"read.landmark": GANGNAM, "read.stay_search": listing, "read.stay_detail": detail,
                                    "read.stay_lookup": lookup}, text="다음 달 6일부터 3박 혼자 강남역 걸어갈 수 있는 비즈니스호텔")
    decision = result.decisions[0]
    assert [item["gid"] for item in decision["shown"]] == [2, 3, 4]
    assert [(item["gid"], item["reason"]) for item in decision["skipped"]] == [(1, "far")]
    assert decision["shown"][1]["located"] == "kakao" and "강남역 2호선에서 0.4km" in result.answer
    assert "위치 모를 호텔" in result.answer and "거리 확인 안 함" in result.answer, "위치를 못 찾으면 가깝다고 하지 않는다"
    assert [name for name, _ in tools.calls].count("read.stay_lookup") == 2, "카카오 위치 찾기는 2번까지"
    assert "강남역 2호선에서 0.8km 넘음 1곳" in result.answer and "이동 계산기를 못 써 직선거리로 봄" in result.answer and "거리는 카카오맵의 「강남역 2호선」 위치에서" in result.answer


def test_children_without_ages_search_a_room_for_everyone():
    """☆L02 「어른 2명 아이 2명」 — 성인 2명 방을 찾았다. 아이 나이를 모르니 4명이 묵을 방으로."""
    reply = {**SEARCH, "keyword": "잠실", "children": 2, "min_rating": None}
    result, _, tools = _run(reply, {"read.stay_search": _listing([(1, "잠실 호텔", "", 150000)]), "read.stay_detail": lambda a: None},
                            text="다음 달 6일부터 3박 어른 2명 아이 2명 잠실")
    search = next(a for n, a in tools.calls if n == "read.booking_search_stays")
    assert (search["adults"], search["children"]) == (4, 0)
    assert "성인 2명 · 아이 2명 조건으로" in result.answer and "아이 나이별 요금은 반영하지 못해 4명이 묵을 방 기준으로 찾았습니다" in result.answer
    assert "adultCount=4&childCount=0" in result.answer


def test_a_trip_without_a_region_is_asked_by_its_place_names():
    """GPT 검토 #17 — 일정이 있는데 지역이 없으면 일정 장소 이름으로 묻는다."""
    reply = {**SEARCH, "keyword": None, "missing": ["keyword"]}
    result, _, tools = _run(reply, {"read.itinerary": NEAR_TRIP}, state=TRIP_STATE, text="다음 달 6일부터 3박 숙소 찾아줘")
    assert result.answer.startswith("일정의 남산타워 · 이태원 거리 · 숙소 이전 날 장소 중 어느 곳 근처로 찾을까요?")
    assert [name for name, _ in tools.calls] == ["read.itinerary"]


def test_a_single_my_stay_result_with_another_name_is_not_confirmed():
    """GPT 검토 #13 — 결과가 하나여도 이름이 다르면 「확인했다」고 하지 않고 맞는지 묻는다."""
    other = {**STAYS, "stays": [{**STAYS["stays"][0], "gid": 77, "name": "해밀톤 레지던스"}]}
    result, _, _ = _run(MY_STAY, {"read.stay_search": other, "read.stay_detail": lambda a: {**DETAIL, "gid": 77, "name": "해밀톤 레지던스"}})
    assert result.decisions[0]["name_unmatched"] is True
    assert "숙박으로 확인했습니다" not in result.answer and "「해밀톤호텔」(으)로 찾은 곳은 이 한 곳뿐이라" in result.answer


def test_landmark_tool_returns_name_and_coordinates_only():
    from app.tools.read_tools import ReadToolbox

    class Kakao:
        def __init__(self):
            self.calls = []

        def search(self, query, **options):
            self.calls.append((query, options))
            if options.get("category_group_code") == "SW8":
                return []
            return [{"id": "1", "name": "강남역", "category": "교통", "address": "서울 강남구", "latitude": 37.49, "longitude": 127.02}]

    kakao = Kakao()
    toolbox = ReadToolbox(lambda: None, kakao=kakao)
    got = toolbox.landmark(None, name="강남역")
    assert got == {"source": "kakao", "found": True, "name": "강남역", "latitude": 37.49, "longitude": 127.02}
    assert [options.get("category_group_code") for _, options in kakao.calls] == ["SW8", None], "「…역」은 지하철역부터"
    assert ReadToolbox(lambda: None).landmark(None, name="강남역") is None, "카카오가 없으면 모름"


def test_landmark_prefers_same_name_station_then_name_match():
    """`[2026-10-16 GPT 검수]` 관련도 1위가 「여의도」→「한강」, 「DDP」→「서울디자인로드」였다."""
    from app.tools.read_tools import ReadToolbox

    def spot(name):
        return {"name": name, "latitude": 37.5, "longitude": 127.0}

    class Kakao:
        def __init__(self, answers):
            self.answers, self.calls = answers, []

        def search(self, query, **options):
            self.calls.append((query, options.get("category_group_code")))
            return self.answers.get((query, options.get("category_group_code")), [])

    def pick(word, answers):
        return ReadToolbox(lambda: None, kakao=Kakao(answers)).landmark(None, name=word)["name"]

    assert pick("여의도", {("여의도역", "SW8"): [spot("여의도역 5호선")], ("여의도", None): [spot("한강")]}) == "여의도역 5호선"
    assert pick("홍대", {("홍대역", "SW8"): [spot("홍대입구역 2호선")], ("홍대", None): [spot("홍대걷고싶은거리")]}) == "홍대걷고싶은거리", \
        "이름이 다른 역(홍대입구역)은 같은 이름 역이 아니다"
    assert pick("DDP", {("DDP", None): [spot("서울디자인로드"), spot("동대문디자인플라자(DDP)")]}) == "동대문디자인플라자(DDP)"
    assert pick("성동구", {("성동구", None): [spot("성수동카페거리"), spot("성동구청")]}) == "성동구청"
    assert pick("경리단길", {("경리단길", None): [spot("경리단길")]}) == "경리단길"


def test_a_city_less_stay_name_with_seoul_coordinates_searches_in_seoul():
    """ST4F-557 — x600 실서버 「더플라자호텔」(서울 중구 좌표)을 바꿔 달라 했더니 후보가 광주(268km)였다. 좌표가 서울이면 검색어에 「서울」."""
    from app.domains.travel_ops.instances.lodging.team import LodgingTeam as Team

    item = SimpleNamespace(starts_at=datetime(2026, 11, 6, 15, tzinfo=ZoneInfo("Asia/Seoul")),
                           ends_at=datetime(2026, 11, 9, 11, tzinfo=ZoneInfo("Asia/Seoul")), detail={},
                           place={"name": "더플라자호텔", "latitude": 37.5647, "longitude": 126.9779})
    assert Team._stay_query(item, {"party_size": 2})["keyword"] == "서울 더플라자호텔"
    item.place = {"name": "롯데호텔 서울", "latitude": 37.5651, "longitude": 126.9810}
    assert Team._stay_query(item, {"party_size": 2})["keyword"] == "롯데호텔 서울", "이미 「서울」이 있으면 그대로"
    item.place = {"name": "해운대 호텔", "latitude": 35.1587, "longitude": 129.1604}
    assert Team._stay_query(item, {"party_size": 2})["keyword"] == "해운대 호텔", "서울 밖 좌표는 그대로"


def test_a_renamed_hotel_with_its_old_name_in_brackets_is_treated_as_already_shown():
    """ST4F-578 — 「롯데호텔 서울」을 바꿔 달라 했더니 첫 후보가 「더그랜드롯데 서울 (구: 롯데호텔 서울)」(같은 호텔)이었다."""
    from app.domains.travel_ops.instances.lodging.team import _fresh_picks, _key

    booked = {"myrealtrip": {"stays": [{"gid": 1, "name": "더그랜드롯데 서울 (구: 롯데호텔 서울)", "price_per_night": 300000},
                                       {"gid": 2, "name": "롯데호텔 월드", "price_per_night": 280000}]},
              "google": {"stays": [{"name": "더그랜드롯데 서울(舊 롯데호텔 서울)", "type": "hotel", "price_per_night": 290000.0,
                                    "link": "https://x"}]}}
    picks = _fresh_picks(booked, {_key("롯데호텔 서울")}, None, {"check_in": IN, "check_out": OUT}, {"adults": 2, "children": None})
    assert [pick["name"] for pick in picks] == ["롯데호텔 월드"]


def test_walking_minutes_come_from_the_mobility_walk_planner_when_it_is_there(monkeypatch):
    """사용자 판정 L03 — 직선 0.9km 가 걸어서 20분이었다. 이동 계산기(도보)가 있으면 몇 분으로 거른다(이동 모듈은 부르기만)."""
    from app.domains.travel_ops.components.team_hooks import legs

    minutes = {37.4990: 6, 37.4870: 22}
    asked = []

    def planner(party_size, constraints, *, disruptions=None, modes=None):
        asked.append(modes)
        return lambda a, b, arrive, not_before=None: ({"eta_min": minutes[round(a["lat"], 4)]}, None)

    monkeypatch.setattr(legs, "leg_planner", planner)
    listing = _listing([(1, "먼 호텔", "호텔 · 강남 · 서울", 120000), (2, "가까운 호텔", "호텔 · 강남 · 서울", 130000)])
    coords = {1: (37.4870, 127.0280), 2: (37.4990, 127.0290)}
    detail = lambda a: {**DETAIL, "gid": a["gid"], "latitude": coords[a["gid"]][0], "longitude": coords[a["gid"]][1]}   # noqa: E731
    reply = {**SEARCH, "keyword": "강남역", "adults": 1, "max_price_per_night": None, "min_rating": None}
    result, _, _ = _run(reply, {"read.landmark": GANGNAM, "read.stay_search": listing, "read.stay_detail": detail},
                        text="다음 달 6일부터 3박 강남역 걸어서 갈 수 있는 호텔 2명")
    assert asked == [["walk"]]
    decision = result.decisions[0]
    assert [item["gid"] for item in decision["shown"]] == [2] and decision["skipped"][0]["walk_min"] == 22, \
        "직선 1.2km 는 1km 근처지만 걸어서 22분이라 뺀다"
    assert "강남역 2호선에서 걸어서 6분(0.2km)" in result.answer and "강남역 2호선에서 걸어서 15분 안(이동 계산기 도보)" in result.answer


def test_a_guesthouse_request_asks_who_will_stay_before_searching():
    """사용자 판정 4차 L05(10-16) — 게스트하우스는 이용 조건(성별 · 국적 · 나이)이 붙은 곳이 많아 바로 찾지 않고 먼저 묻는다."""
    reply = {**SEARCH, "keyword": "홍대", "adults": 1, "max_price_per_night": 50000, "min_rating": None}
    result, _, tools = _run(reply, {"read.stay_search": _listing([]), "read.stay_google": _google([])},
                            text="다음 달 6일부터 3박 홍대 게스트하우스 1명")
    assert result.decisions[0]["needs"] == ["guest_profile"] and result.decisions[0]["guest_missing"] == ["나이", "성별", "내국인/외국인"]
    assert tools.calls == [], "묻기 전에는 도구를 부르지 않는다"
    assert "게스트하우스는 여성 전용" in result.answer and "묵으실 분의 정보(나이 · 성별 · 내국인/외국인)" in result.answer
    partly, _, _ = _run(reply, {}, text="다음 달 6일부터 3박 홍대 호스텔 1명 20대 여자")
    assert partly.decisions[0]["guest_missing"] == ["내국인/외국인"] and "호스텔은" in partly.answer


def test_restricted_stays_are_filtered_by_who_will_stay():
    """사용자 판정 L05 — 「YAB-GuestHouse, FemaleOnly, ForeignOnly」. 묵을 분(20대 · 여성 · 내국인)에게 맞는 조건만 남긴다."""
    listing = _listing([(1, "홍대 여성전용 게스트하우스", "게스트하우스 · 마포 · 서울", 30000), (2, "홍대 남성전용 게스트하우스", "게스트하우스 · 마포 · 서울", 35000)])
    google = _google([("YAB-GuestHouse, FemaleOnly, ForeignOnly", 36782.0, None, None, None), ("하이데어 게스트하우스", 32612.0, None, None, None)])
    reply = {**SEARCH, "keyword": "홍대", "adults": 1, "max_price_per_night": 50000, "min_rating": None}
    result, _, _ = _run(reply, {"read.stay_search": listing, "read.stay_detail": lambda a: None, "read.stay_google": google},
                        text="다음 달 6일부터 3박 홍대 게스트하우스 1명, 20대 여자 내국인")
    assert [item["gid"] for item in result.decisions[0]["shown"]] == [1] and result.decisions[0]["dropped"] == {"restricted": 1}, \
        "여성 전용은 여성에게 남기고 남성 전용은 뺀다"
    assert "YAB-GuestHouse" not in result.answer and "하이데어 게스트하우스" in result.answer, "외국인 전용은 내국인에게 맞지 않는다"
    assert "묵을 분(20대 · 여성 · 내국인)과 맞지 않는" in result.answer and "묵을 분 20대 · 여성 · 내국인" in result.answer
    assert "링크한 화면에서 꼭 확인" in result.answer


def test_restricted_stays_are_dropped_when_who_will_stay_is_unknown():
    """게스트하우스를 묻지 않은 문장(호텔 · 유형 없음)에서는 전처럼 이용 조건이 붙은 곳을 빼고 알려 준다."""
    google = _google([("YAB-GuestHouse, FemaleOnly, ForeignOnly", 36782.0, None, None, None), ("하이데어 호텔", 32612.0, None, None, None)])
    reply = {**SEARCH, "keyword": "홍대", "adults": 1, "max_price_per_night": 50000, "min_rating": None}
    result, _, _ = _run(reply, {"read.stay_search": _listing([(2, "홍대 호텔", "호텔 · 마포 · 서울", 35000)]),
                                "read.stay_detail": lambda a: None, "read.stay_google": google},
                        text="다음 달 6일부터 3박 홍대 숙소 1명")
    assert "YAB-GuestHouse" not in result.answer and "이용 조건이 붙은 1곳은 뺐어요(성별 · 국적 · 나이를 알려 주시면" in result.answer


def test_pets_get_their_own_guidance_and_google_says_dates_do_not_carry_over():
    result, _, _ = _run({**SEARCH, "keyword": "서울", "min_rating": None, "max_price_per_night": None},
                        {"read.stay_search": _listing([(1, "서울 호텔", "", 150000)]), "read.stay_detail": lambda a: None,
                         "read.stay_google": _google([("구글 호텔", 90000.0, 3, None, None)])},
                        text="반려견 데리고 다음 달 6일부터 3박 서울 숙소 2명")
    assert "반려동물 동반은 숙소마다 달라요" in result.answer, "사용자 판정 L10"
    assert "구글 호텔 링크는 날짜 · 인원을 채워 엽니다" in result.answer and "&ts=" in result.answer, "사용자 판정 L01 · L12"


def test_wide_places_and_seoul_neighbours():
    """사용자 판정 L09 「한강」은 기준점으로 안 씀 · L08 「김포 · 강서는 코앞」 — 기준점이 있으면 맞닿은 시는 거리로 본다."""
    result, _, tools = _run({**SEARCH, "keyword": "한강", "min_rating": None, "max_price_per_night": None},
                            {"read.stay_search": _listing([(1, "군산 호텔", "호텔 · 군산", 90000), (2, "용산 호텔", "호텔 · 용산구 · 서울", 150000)]),
                             "read.stay_detail": lambda a: None}, text="다음 달 6일부터 3박 한강 근처 호텔 2명")
    assert "read.landmark" not in [n for n, _ in tools.calls] and result.decisions[0]["dropped"] == {"region": 1}
    assert "「한강」은(는) 넓게 이어진 곳이라 거리 조건" in result.answer
    gimpo = {"source": "kakao", "found": True, "name": "김포국제공항 국내선", "latitude": 37.5622, "longitude": 126.8011}
    listing = _listing([(1, "고촌 호텔", "호텔 · 김포", 80000), (2, "군산 호텔", "호텔 · 군산", 50000)])
    result, _, _ = _run({**SEARCH, "keyword": "김포공항", "adults": 1, "min_rating": None, "max_price_per_night": None},
                        {"read.landmark": gimpo, "read.stay_search": listing,
                         "read.stay_detail": lambda a: {**DETAIL, "gid": a["gid"], "latitude": 37.5650, "longitude": 126.7900}},
                        text="다음 달 6일부터 3박 김포공항 근처 1명")
    assert [item["gid"] for item in result.decisions[0]["shown"]] == [1] and result.decisions[0]["dropped"] == {"region": 1}


def test_dates_the_model_left_empty_are_read_by_rule():
    """사용자 판정 L02 — 「11월 14일부터 2박」을 모델이 비웠다(17:49). 모델이 비웠을 때만 규칙으로 채운다."""
    from datetime import date as day

    from app.domains.travel_ops.instances.lodging.interpret import Interpretation, rule_dates

    today = day(2026, 10, 15)
    got, used = rule_dates(Interpretation(task="search"), "11월 14일부터 2박 어른 2명 아이 2명 잠실", today=today)
    assert used and (got.check_in, got.check_out, got.check_in_text, got.check_out_text) == (day(2026, 11, 14), day(2026, 11, 16), "11월 14일", "2박")
    got, _ = rule_dates(Interpretation(task="search"), "11월 7일 1박 성수, 1박 20만 원 이하로", today=today)
    assert got.check_out == day(2026, 11, 8), "가격 말 「1박 20만 원」은 박 수가 아니다"
    assert not rule_dates(Interpretation(task="search"), "11월 12일 비행기라 11월 11일 1박", today=today)[1], "날이 둘이면 그대로 둔다"
    kept = Interpretation(task="search", check_in=day(2026, 11, 20))
    assert rule_dates(kept, "11월 14일부터 2박", today=today) == (kept, False), "모델 값이 있으면 건드리지 않는다"


def test_a_seoul_search_without_an_anchor_still_drops_places_outside_seoul():
    """☆19:03 playdata 검수 L09 「한강」 — 기준점을 안 찾는 검색어에 구글 칸으로 「롯데호텔앤리조트 김해」가 왔다. 서울 경계 밖 좌표는 뺀다."""
    google = _google([("롯데호텔앤리조트 김해", 160824.0, 5, 35.2285, 128.8894), ("용산 5성 호텔", 300000.0, 5, 37.5290, 126.9640)])
    result, _, _ = _run({**SEARCH, "keyword": "한강", "min_rating": None, "max_price_per_night": None},
                        {"read.stay_search": _listing([(1, "용산 호텔", "5성급 · 호텔 · 용산구 · 서울", 250000)]),
                         "read.stay_detail": lambda a: None, "read.stay_google": google},
                        text="다음 달 6일부터 3박 한강 5성급 호텔 2명")
    assert "김해" not in result.answer and "용산 5성 호텔" in result.answer


def test_google_hotel_links_carry_dates_and_adults():
    """사용자 질문(10-15) 「안내 대신 날짜 · 인원을 넣어 링크를 보낼 수 없냐」 — ☆18시대 playdata 내장 브라우저에서 화면이 만든 `ts` 와 같은 값."""
    from app.domains.travel_ops.instances.lodging.team import _google_page, google_ts

    assert google_ts("2026-11-28", "2026-11-30", 3) == "CAESDgoCCAMKAggDCgIIAxABGh4KAhoAEhgSEgoHCOoPEAsYHBIHCOoPEAsYHjICCAIqCQoFOgNLUlcaAA"
    assert google_ts("2026-11-07", "2026-11-08", 4) == "CAESEgoCCAMKAggDCgIIAwoCCAMQARoeCgIaABIYEhIKBwjqDxALGAcSBwjqDxALGAgyAggCKgkKBToDS1JXGgA"
    assert _google_page("호텔 리베라", {"check_in": "2026-11-28", "check_out": "2026-11-30"}, 3).endswith(
        "&ts=CAESDgoCCAMKAggDCgIIAxABGh4KAhoAEhgSEgoHCOoPEAsYHBIHCOoPEAsYHjICCAIqCQoFOgNLUlcaAA")
    assert "&ts=" not in _google_page("호텔 리베라"), "날짜를 모르면 이름만"
    from app.domains.travel_ops.instances.lodging.team import google_qs
    # ☆10-16 playdata 내장 브라우저 — 「렉시 호텔」 목록에서 숙소를 눌렀을 때 주소의 `qs` 와 같은 값
    assert google_qs("ChgI7NLDu7iQ6KXqARoLL2cvMXRsYm0yYnAQAQ") == "MiZDaGdJN05MRHU3aVE2S1hxQVJvTEwyY3ZNWFJzWW0weVluQVFBUTgN"
    link = _google_page("렉시 호텔", {"check_in": "2026-11-20", "check_out": "2026-11-22"}, 2,
                        token="ChgI7NLDu7iQ6KXqARoLL2cvMXRsYm0yYnAQAQ", area="서울")
    assert link.startswith("https://www.google.com/travel/search?q=%EB%A0%89%EC%8B%9C%20%ED%98%B8%ED%85%94&") and \
        link.endswith("&qs=MiZDaGdJN05MRHU3aVE2S1hxQVJvTEwyY3ZNWFJzWW0weVluQVFBUTgN"), "열쇠가 있으면 이름 + qs 로 그 숙소 화면"
    assert "q=%EB%A0%89%EC%8B%9C%20%ED%98%B8%ED%85%94%20%EC%84%9C%EC%9A%B8&" in _google_page("렉시 호텔", area="서울"), \
        "열쇠가 없으면 이름 + 서울(이름만이면 「결과 없음」이었다)"


def test_who_will_stay_is_read_from_the_sentence():
    """사용자 판정 4차 L05(10-16) — 나이 · 성별 · 내국인/외국인. 「여자친구」 「여성 전용」은 성별이 아니고, 「외국인 친구랑」은 섞임."""
    from app.domains.travel_ops.instances.lodging.wants import guest_block, read_guest

    guest = read_guest("홍대 게스트하우스 2박 1명, 20대 여자 내국인")
    assert (guest.age, guest.gender, guest.nation) == (20, "여성", "내국인") and guest.missing() == []
    assert read_guest("여자친구랑 여성 전용 말고").gender is None
    assert read_guest("외국인 친구랑 둘이").nation == "섞임" and read_guest("25살 남자 1명, 여자 1명").gender == "혼성"
    assert guest_block("YAB-GuestHouse, FemaleOnly, ForeignOnly", guest) == "외국인 전용"
    assert guest_block("Adults only hostel", guest) is None and guest_block("Adults only hostel", guest, children=1) == "성인 전용"


def test_hanok_search_keeps_foreign_named_hanok_rentals_and_records_dropped_names():
    """사용자 판정 5차 L06(10-16) — 「Hanok」처럼 외국어로 한옥이라 적힌 곳도 넣는다(숙박 공유로 와도). 뺀 이름은 판단 기록에 남긴다."""
    google = _google([("Bukchon Hanok Stay", 180000.0, None, None, None), ("Seoul Apartment", 90000.0, None, None, None),
                      ("韓屋ゲストハウス 楽古斎", 200000.0, None, None, None), ("나인트리 인사동", 150000.0, None, None, None)])
    for stay in google["stays"][:2]:
        stay["type"] = "vacation rental"
    reply = {**SEARCH, "keyword": "인사동", "adults": 2, "max_price_per_night": None, "min_rating": None}
    result, _, _ = _run(reply, {"read.stay_search": _listing([(1, "인사동 호텔", "호텔 · 종로 · 서울", 150000)]),
                                "read.stay_detail": lambda a: None, "read.stay_google": google},
                        text="다음 달 6일부터 3박 인사동 한옥 2명")
    answer, decision = result.answer, result.decisions[0]
    assert "Bukchon Hanok Stay" in answer and "숙박 공유" in answer and "韓屋ゲストハウス" in answer
    assert "Seoul Apartment" not in answer and "나인트리 인사동" not in answer
    assert decision["dropped_names"] == [{"name": "인사동 호텔", "why": "kind"}]
    assert {"name": "Seoul Apartment", "why": "vacation_rental"} in decision["google_dropped"]
    assert {"name": "나인트리 인사동", "why": "kind"} in decision["google_dropped"]


def test_date_ranges_people_and_vague_dates_are_read_by_rules():
    """평가 2차(10-16) — 날짜 범위 표기 · 근거 없는 인원 · 정해지지 않은 날 · 무관한 「오늘」."""
    from datetime import date as day

    from app.domains.travel_ops.instances.lodging.interpret import Interpretation, parse, rule_checks, rule_ranges

    today = day(2026, 10, 16)
    for text, start, end in (("12/24~26 커플", day(2026, 12, 24), day(2026, 12, 26)), ("1/11~13 성인 2명", day(2027, 1, 11), day(2027, 1, 13)),
                             ("12/18-12/20 두 명", day(2026, 12, 18), day(2026, 12, 20)), ("1월 15~17일", day(2027, 1, 15), day(2027, 1, 17)),
                             ("11월 29일 들어가서 12월 1일 나올", day(2026, 11, 29), day(2026, 12, 1)), ("12/30~2", day(2026, 12, 30), day(2027, 1, 2))):
        found, fixed = rule_ranges(Interpretation(task="search"), text, today=today)
        assert fixed and (found.check_in, found.check_out) == (start, end), text
    assert rule_ranges(Interpretation(task="search"), "11월 14일부터 2박", today=today)[1] is False, "범위 표기가 없으면 손대지 않는다"
    weather = Interpretation(task="search", check_in=today, check_out=day(2026, 10, 17), check_in_text="오늘", adults=1)
    assert rule_checks(weather, "오늘 날씨 추운데 종로 1박 모텔")[1] == ["check_in", "adults"]
    weekend = Interpretation(task="search", check_in=day(2026, 11, 6), check_out=day(2026, 11, 8), check_in_text="주말", adults=2)
    assert rule_checks(weekend, "11월 중에 주말 2박 신촌 성인 둘")[1] == ["check_in"]
    last_sat = Interpretation(task="search", check_in=day(2027, 1, 30), check_out=day(2027, 1, 31), check_in_text="2027년 1월의 마지막 토요일", adults=2)
    assert rule_checks(last_sat, "2027년 1월의 마지막 토요일에 들어가서 다음 날 나올 용산 숙소, 성인 2명")[1] == [], "몇째 요일은 날짜다(F-33)"
    parents = Interpretation(task="search", check_in=day(2026, 12, 18), check_in_text="12월 18일", adults=2)
    assert rule_checks(parents, "부모님 모시고 종로 한옥 12월 18일 1박")[1] == ["adults"]
    family = Interpretation(task="search", adults=2, children=1)
    assert rule_checks(family, "엄마랑 아빠, 그리고 10개월 된 아기 이렇게 세 식구가 묵을 온돌방 숙소")[1] == [], "세 식구 · 엄마 아빠는 인원 근거(H-31)"
    assert parse({"task": "search", "max_price_per_night": 0}).max_price_per_night is None, "「0원」으로 해석 전체가 거절되지 않는다(I-05)"


def test_price_band_walk_minutes_and_kind_spellings_are_read():
    """평가 2차 — 「10만 원대」 아래 끝 · 「걸어서 10분」 · 「호탤」 「hotel」 「guesthouse」."""
    assert (read_wants("1박 10만원대").min_price, read_wants("1박 십만원대").band_max) == (100000, 199999)
    assert read_wants("1박 15만~20만 원").min_price == 150000 and read_wants("100,000~199,999 KRW").min_price == 100000
    assert read_wants("홍대입구역 도보 5분 이내 호스텔").walk_min == 5 and read_wants("걸어서 십분 안에 가는 호탤").walk_min == 10
    assert [read_wants(t).kind for t in ("호탤 찾아주세여", "Gangnam hotel", "guesthouse 찾아줘", "게스트하우쓰 잇나여")] == \
        ["호텔", "호텔", "게스트하우스", "게스트하우스"]
    listing = _listing([(1, "싼 호텔", "호텔 · 용산 · 서울", 70000), (2, "맞는 호텔", "호텔 · 용산 · 서울", 150000)])
    google = _google([("너무 싼 호텔", 60000.0, 3, None, None), ("구간 안 호텔", 120000.0, 3, None, None)])
    result, _, tools = _run({**SEARCH, "max_price_per_night": 100000, "min_rating": None},
                            {"read.stay_search": listing, "read.stay_detail": lambda a: None, "read.stay_google": google},
                            text="다음 달 6일부터 3박 용산 호텔 2명 1박 10만 원대")
    assert [item["gid"] for item in result.decisions[0]["shown"]] == [2] and "1박 100,000원 미만 1곳" in result.answer
    assert "구간 안 호텔" in result.answer and "너무 싼 호텔" not in result.answer
    assert next(a for n, a in tools.calls if n == "read.booking_search_stays")["max_price"] == 199999, "구간 시작으로 낸 상한은 구간 끝으로"
