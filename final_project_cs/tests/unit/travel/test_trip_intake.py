# -*- coding: utf-8 -*-
"""자유 문장 → 구조화된 신고. ★모델이 **문장에 없는 값**을 만들어 내면 받지 않는다."""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components.conversation.trip_intake import extract, validate

DELAY = "팝업스토어 줄이 길어서 점심에 70분 늦을 것 같아요"
CLOSED = "저녁 먹으려던 식당이 오늘 임시휴무래요"
STOCK = "라면 선물세트랑 스팸 선물세트가 품절이에요. 이 근처에 이거 파는 다른 곳 없어?"


def test_the_three_scenario_sentences_pass_with_the_values_they_contain():
    assert validate({"type": "delay", "minutes": 70, "products": ["팝업스토어"]}, DELAY) == {
        "type": "delay", "minutes": 70}
    assert validate({"type": "closed", "minutes": None, "products": []}, CLOSED) == {"type": "closed"}
    assert validate({"type": "stock_out", "products": ["라면 선물세트", "스팸 선물세트"]}, STOCK) == {
        "type": "stock_out", "products": ["라면 선물세트", "스팸 선물세트"]}


@pytest.mark.parametrize("raw", [
    {"type": "delay", "minutes": 90},            # ★문장에는 70 — 모델이 숫자를 만들어 냈다
    {"type": "delay", "minutes": None},
    {"type": "delay", "minutes": 0},
    {"type": "unknown"},
    "not a dict",
])
def test_made_up_or_missing_delay_values_are_refused(raw):
    assert validate(raw, DELAY) is None


def test_a_product_that_is_not_in_the_sentence_is_dropped_and_none_left_is_refused():
    assert validate({"type": "stock_out", "products": ["컵라면"]}, STOCK) is None
    assert validate({"type": "stock_out", "products": ["라면 선물세트", "컵라면"]}, STOCK) == {
        "type": "stock_out", "products": ["라면 선물세트"]}


def test_extract_uses_the_chat_and_validates():
    class Chat:
        def json(self, system, user):
            assert "type" in system and user == DELAY
            return {"type": "delay", "minutes": "70", "products": []}
    assert extract(DELAY, Chat()) == {"type": "delay", "minutes": 70}


def test_rollback_needs_a_version_number_that_is_in_the_sentence():
    from app.domains.travel_ops.components.conversation.trip_intake import validate
    assert validate({"type": "rollback", "to_version": 6}, "6번 일정으로 되돌려 주세요") == {"type": "rollback", "to_version": 6}
    # ★`[2026-09-29]` 지어낸 번호는 버리고 번호 없는 되돌리기로 — 번호는 서버가 그 항목의 최근 변경에서 정한다
    assert validate({"type": "rollback", "to_version": 4}, "6번 일정으로 되돌려 주세요") == {"type": "rollback", "to_version": None}
    assert validate({"type": "rollback", "to_version": None}, "예전 일정으로 되돌려 주세요") == {"type": "rollback", "to_version": None}


def test_the_interpreter_picks_the_team_from_the_report_not_the_classifier():
    from app.domains.travel_ops.components.core_hooks.subjects import make_subject_interpreter
    reports = {"늦": {"type": "delay", "minutes": 70}, "품절": {"type": "stock_out", "products": ["라면"]},
               "바꿔": {"type": "change"}, "궁금": {"type": "other"}}
    calls = []

    def extractor(text):
        calls.append(text)
        return next(value for key, value in reports.items() if key in text)

    interpret = make_subject_interpreter(extractor)
    ref = {"kind": "trip", "id": "t", "recent_part_kind": "mobility"}
    assert interpret(text="70분 늦어요", subject_ref=ref)["routing_hint"] == "dining"
    assert interpret(text="라면 품절", subject_ref=ref)["routing_hint"] == "activity"
    assert interpret(text="다른 걸로 바꿔줘", subject_ref=ref)["routing_hint"] == "mobility"
    assert interpret(text="그냥 궁금해요", subject_ref=ref)["routing_hint"] is None
    # ★화면 버튼(구조가 정해진 요청)은 모델을 부르지 않는다
    before = len(calls)
    structured = interpret(text="화면에서 다른 안 선택",
                           subject_ref={**ref, "part_kind": "dining", "request": {"type": "change", "at": "x"}})
    assert structured == {"routing_hint": "dining", "report": {"type": "change"}} and len(calls) == before


# ── 질문 (2026-09-25) ───────────────────────────────────────────
@pytest.mark.parametrize("raw, message", [
    ({"type": "closed"}, "내일 경복궁 휴관 아니에요?"),                 # ★질문이 「닫혔다」로 둔갑하던 것
    ({"type": "other"}, "비 오면 오후 한강 카약 취소돼요? 위약금 있어요?"),
    ({"type": "other"}, "저녁 식당에 아이 데려가도 되나요"),
    ({"type": "delay", "minutes": 70}, "70분 늦을 것 같은데 괜찮을까요?"),
    ({"type": "question"}, "여기 몇 시에 닫아요?"),
])
def test_a_question_is_never_taken_as_a_report_that_changes_the_plan(raw, message):
    assert validate(raw, message) == {"type": "question"}


@pytest.mark.parametrize("raw, message, expected", [
    ({"type": "delay", "minutes": 70}, "점심 식당 70분 늦을 것 같아요", {"type": "delay", "minutes": 70}),
    ({"type": "closed"}, CLOSED, {"type": "closed"}),
    ({"type": "change"}, "다른 식당으로 바꿔줄 수 있어요?", {"type": "change"}),   # 묻는 꼴의 **요청**
    ({"type": "stock_out", "products": ["라면 선물세트", "스팸 선물세트"]}, STOCK,
     {"type": "stock_out", "products": ["라면 선물세트", "스팸 선물세트"]}),        # 품절은 원래 묻는다
])
def test_reports_and_requests_stay_what_they_were(raw, message, expected):
    assert validate(raw, message) == expected
