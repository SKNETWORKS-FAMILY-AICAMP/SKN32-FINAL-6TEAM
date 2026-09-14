# -*- coding: utf-8 -*-
"""자유 문장 → 구조화된 신고. ★모델이 **문장에 없는 값**을 만들어 내면 받지 않는다."""
from __future__ import annotations

import pytest

from app.modules.travel_ops.trip_intake import extract, validate

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
