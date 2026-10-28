# -*- coding: utf-8 -*-
"""일정 검사 위반(`itinerary_checks`)과 채팅 시각 변경 거절(`chat_edit._refusal`)의 고객 문장 — `[2026-10-28 x600 e78e038b 보고]`.

재현: 「오후 5시 30분으로 옮겨줘」의 거절 답이 「그렇게 바꾸면 일정이 맞지 않아 바꾸지 않았어요 — 북촌한옥마을: 19:00 까지인데 17:00 에 닫는다
/ 지하철 …(19:50 종료)와 N서울타워(19:00 시작)이 겹친다」였고, 응답 `violations[].remedy` 는 「N서울타워 를 19:50 뒤로 옮기거나 …」였다.
반말 평서형 · 숫자와 조사 사이 띄어쓰기 · 받침과 맞지 않는 조사가 고객에게 그대로 보였다.

고객 문장 규칙: 해요체로 끝난다 · 시각/숫자 뒤 조사는 붙여 쓴다(19:00까지) · 받침에 맞는 조사(광장시장을 · N서울타워를) ·
내부 항목 순번(`items`)은 문장에 넣지 않는다(공개 필드 `items` 자체는 그대로 둔다).
"""
from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation.chat_edit import _refusal
from app.domains.travel_ops.components.itinerary.itinerary_checks import Part, check_itinerary, particle, refusal_message

KST = ZoneInfo("Asia/Seoul")
#: 해요체 끝 — 끝에 근거 괄호(「…이에요(휴관 안내)」)가 붙을 수 있다. 웹 `error-text.ts` 의 POLITE_KOREAN 과 같은 모양
POLITE = re.compile(r"(요|니다)[.!?]?(\s*\([^)]*\))?$")
#: 숫자(시각 · 분 · 원) 뒤에 띄어 쓴 조사 — 「19:00 까지」 「17:00 에」
SPACED_PARTICLE = re.compile(r"\d\s+(에|에는|까지|부터|이|가|을|를|은|는|으로|로|만|인데)(?=[\s,.·)]|$)")
#: 한글로 끝나는 이름 뒤의 겸용 조사 · 띄어 쓴 조사 — 「N서울타워 를」 「겹친다」 같은 반말 평서형
BANMAL_END = re.compile(r"(는다|한다|이다|있다|없다|걸린다|겹친다|닫는다|연다|받는다|빠르다|끝난다|줄인다|옮긴다|바꾼다|뺀다|고른다|둔다|앞당긴다|끝낸다)[.)]?$")


def _at(hhmm: str, day: int = 23) -> datetime:
    hour, minute = hhmm.split(":")
    return datetime(2026, 9, day, int(hour), int(minute), tzinfo=KST)


def _part(seq, title, start, end=None, *, kind="activity", place=None, route=None, day=23):
    return Part(seq=seq, kind=kind, title=title, starts_at=_at(start, day),
                ends_at=_at(end, day) if end else None, place=place, route=route)


def _hours(opens: str, closes: str, **extra):
    return {"name": "x", "attributes": {"hours": [opens, closes], **extra}}


def _every_violation():
    """코드마다 하나씩 — 고객 문장 규칙을 모든 위반 문장에 건다."""
    route = {"planned": "subway", "options": [{"id": "subway", "label": "2호선 직통", "eta_min": 13}]}
    found = []
    found += check_itinerary([_part(1, "전망대", "10:00", "09:30")])                                        # time_order
    found += check_itinerary([_part(1, "지하철 3호선→4호선 50분 · 3.5km", "18:00", "19:50", kind="mobility"),
                              _part(2, "N서울타워", "19:00", "20:00")])                                        # overlap
    found += check_itinerary([_part(1, "북촌", "10:00", "11:00"), _part(2, "광장시장", "10:30", "11:30")])     # overlap(받침)
    found += check_itinerary([_part(1, "전망대", "10:00", "10:45"),
                              _part(2, "잠실 → 성수", "10:50", "10:55", kind="mobility", route=route)])        # move_too_short
    found += check_itinerary([_part(1, "전망대", "10:00", "11:00", place={"name": "잠실", "attributes": {"district": "송파구"}}),
                              _part(2, "쇼핑", "11:00", "12:00", place={"name": "성수", "attributes": {"district": "성동구"}})])
    found += check_itinerary([_part(1, "북촌한옥마을", "17:30", "19:00", place=_hours("09:00", "17:00"))])    # after_closing
    found += check_itinerary([_part(1, "박물관", "08:00", "09:00", place=_hours("10:00", "18:00"))])          # before_opening
    found += check_itinerary([_part(1, "고궁", "17:30", "18:00", place={"name": "x", "attributes": {
        "hours_week": {"wed": {"open": "09:00", "close": "18:00", "last_entry": "17:00"}}}})])                 # after_last_entry
    found += check_itinerary([_part(1, "옛 식당", "12:00", "13:00", place={"name": "x", "ledger": {"open_at_slot": False, "closed": True}})])
    found += check_itinerary([_part(1, "정원", "17:00", "19:00", place={"name": "x", "activity": {"cut_short": True, "closes_at": "18:00"}})])
    found += check_itinerary([_part(1, "식당", "15:00", "16:00",
                                    place={"name": "x", "attributes": {"hours": ["11:00", "21:00"], "break": ["15:00", "17:00"]}})])
    found += check_itinerary([_part(1, "가게", "12:00", "13:00", place={"name": "x", "attributes": {"payment": ["현금"]}})],
                             constraints={"payment": "카드"})
    found += check_itinerary([_part(1, "가게", "12:00", "13:00", place={"name": "x", "attributes": {"price_krw": 90000}})],
                             constraints={"budget_krw": 50000}, party_size=2)
    found += check_itinerary([_part(1, "야경", "20:00", "23:00")], constraints={"day_hours": {"end": "22:00"}})
    found += check_itinerary([_part(1, "식당", "12:00", "13:00", place={"name": "x", "ledger": {"open_at_slot": False}})])
    found += check_itinerary([_part(1, "공원", "17:00", "19:00",
                                    place={"name": "x", "activity": {"cut_short": True, "closes_at": "18:00", "usable_minutes": 60}})])
    found += check_itinerary([_part(1, "궁", "10:00", "11:00",
                                    place={"name": "x", "activity": {"closed": True, "quote": "매주 화요일 휴관(공휴일 제외)"}})])
    found += check_itinerary([_part(1, "전시", "21:00", "22:00",
                                    place={"name": "x", "activity": {"within_hours": False, "closed": False}})])
    found += check_itinerary([Part(seq=1, kind="lodging", title="호텔 A", starts_at=_at("15:00", 23), ends_at=_at("11:00", 25)),
                              Part(seq=2, kind="lodging", title="호텔 B", starts_at=_at("15:00", 24), ends_at=_at("11:00", 26))])
    return found


def test_every_code_is_covered():
    codes = {v.code for v in _every_violation()}
    assert {"time_order", "overlap", "move_too_short", "no_transfer_time", "after_closing", "before_opening", "after_last_entry", "break_time",
            "payment_not_accepted", "over_budget", "day_deadline", "dining_closed_at_slot", "outside_hours",
            "closed_day", "stay_overlap"} <= codes, codes


@pytest.mark.parametrize("field", ["reason", "remedy"])
def test_every_reason_and_remedy_is_polite_with_attached_particles(field):
    for violation in _every_violation():
        text = getattr(violation, field)
        assert POLITE.search(text), (violation.code, text)
        assert not BANMAL_END.search(text), (violation.code, text)
        assert not SPACED_PARTICLE.search(text), (violation.code, text)
        assert "은(는)" not in text and "이(가)" not in text and "(으)로" not in text, (violation.code, text)
        assert "원장" not in text, (violation.code, text)                   # 내부 자료 이름(요식 · 활동 원장)은 고객 문장에 없다


def test_after_closing_reads_as_a_customer_sentence():
    [found] = check_itinerary([_part(5, "북촌한옥마을", "17:30", "19:00", place=_hours("09:00", "17:00"))])
    assert found.reason == "북촌한옥마을: 17:00에 문을 닫는데 19:00까지 머물게 돼요"
    assert found.remedy == "17:00 전에 끝나도록 줄이거나 앞당겨 주세요"
    assert found.as_dict()["items"] == [5]                                  # 공개 필드는 그대로 — 문장에만 순번이 없다
    assert "5" not in found.reason.replace("15", "").replace("17:00", "").replace("19:00", "")


def test_overlap_uses_the_right_particle_for_the_later_stop():
    [market] = check_itinerary([_part(6, "북촌", "10:00", "11:00"), _part(7, "광장시장", "10:30", "11:30")])
    assert market.remedy == "광장시장을 11:00 뒤로 옮기거나 앞 일정을 줄여 주세요"
    [tower] = check_itinerary([_part(6, "지하철 3호선→4호선 50분 · 3.5km", "18:00", "19:50", kind="mobility"),
                               _part(7, "N서울타워", "19:00", "20:00")])
    assert tower.reason == "N서울타워: 19:00에 시작하는데 앞 일정(지하철 3호선→4호선 50분 · 3.5km)이 19:50에 끝나 시간이 겹쳐요"
    assert tower.remedy == "N서울타워를 19:50 뒤로 옮기거나 앞 일정을 줄여 주세요"
    assert "6" not in tower.reason.replace("3호선→4호선 50분 · 3.5km", "") and "7" not in tower.reason


@pytest.mark.parametrize("word,pair,expected", [
    ("광장시장", "을/를", "을"), ("N서울타워", "을/를", "를"), ("공원", "이/가", "이"), ("카페", "이/가", "가"),
    ("서울", "으로/로", "로"), ("경복궁", "으로/로", "으로"), ("카페", "으로/로", "로"), ("북촌", "과/와", "과"),
    ("10", "을/를", "을"), ("12", "은/는", "는"), ("17", "으로/로", "로"),
    ("card", "을/를", "을(를)"), ("card", "으로/로", "(으)로"), ("", "이/가", "이(가)"),
])
def test_particle_follows_the_final_consonant(word, pair, expected):
    assert particle(word, pair) == expected


def test_registration_refusal_message_is_one_polite_sentence():
    found = check_itinerary([_part(1, "북촌한옥마을", "17:30", "19:00", place=_hours("09:00", "17:00")),
                             _part(2, "N서울타워", "18:30", "20:00")])
    message = refusal_message(found)
    assert message.startswith("이 일정은 그대로 진행할 수 없어요 — ") and POLITE.search(message), message
    assert "수행할 수 없습니다" not in message and not SPACED_PARTICLE.search(message)


def _x600_violations():
    return [{"code": "after_closing", "items": [5], "reason": "북촌한옥마을: 17:00에 문을 닫는데 19:00까지 머물게 돼요",
             "remedy": "17:00 전에 끝나도록 줄이거나 앞당겨 주세요"},
            {"code": "overlap", "items": [6, 7],
             "reason": "N서울타워: 19:00에 시작하는데 앞 일정(지하철 3호선→4호선 50분 · 3.5km)이 19:50에 끝나 시간이 겹쳐요",
             "remedy": "N서울타워를 19:50 뒤로 옮기거나 앞 일정을 줄여 주세요"}]


def test_chat_refusal_lists_the_reasons_as_polite_sentences():
    violations = _x600_violations()
    text = _refusal("itinerary_infeasible", refusal_message([]) + "x", violations=violations)
    assert text == ("그렇게 바꾸면 일정이 맞지 않아 일정은 바꾸지 않았어요. 북촌한옥마을: 17:00에 문을 닫는데 19:00까지 머물게 돼요. "
                    "N서울타워: 19:00에 시작하는데 앞 일정(지하철 3호선→4호선 50분 · 3.5km)이 19:50에 끝나 시간이 겹쳐요.")
    assert " — " not in text and not SPACED_PARTICLE.search(text) and not BANMAL_END.search(text)


def test_chat_refusal_without_violations_does_not_echo_the_developer_message():
    text = _refusal("itinerary_infeasible", "이 일정은 그대로 수행할 수 없습니다: 북촌한옥마을: 19:00 까지인데 17:00 에 닫는다")
    assert text == "그렇게 바꾸면 일정이 맞지 않아 일정은 바꾸지 않았어요."


def test_a_quoted_notice_with_brackets_still_ends_as_a_polite_sentence():
    """Codex 검토 — 원문 인용에 괄호가 있어도 문장 끝은 해요체다(웹 POLITE_KOREAN 이 서버 문장을 그대로 보이는 조건)."""
    found = check_itinerary([_part(1, "궁", "10:00", "11:00",
                                   place={"name": "x", "activity": {"closed": True, "quote": "매주 화요일 휴관(공휴일 제외)"}})])
    assert found[0].reason == "궁: 안내 문구 「매주 화요일 휴관(공휴일 제외)」에 따라 9월 23일은 쉬는 날이에요"
    assert POLITE.search(refusal_message(found))
