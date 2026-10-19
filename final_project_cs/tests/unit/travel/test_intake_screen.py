# -*- coding: utf-8 -*-
"""접수 입구의 빠른 거름 — 규칙만(모델 호출 0). `[2026-10-19 사용자 결정]` 설계서 §5.

★애매하면 거르지 않는다 — 여행 단서가 하나라도 있으면 지금처럼 읽는다. 파일이 붙으면 거르지 않는다.
DB 를 거치는 길(접수 → 조회 · 모델 호출 0 · 로딩 설문 없음)은 `tests/e2e/test_intake_screen.py`.
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components.intake.screen import screen, travel_clue


@pytest.mark.parametrize("text", ["파이썬 for 루프에 대해서 알려줘", "자바스크립트 함수 에러 고쳐줘", "이 문장 영어로 번역해 줘"])
def test_clearly_other_work_is_sent_back(text):
    assert screen(text, has_files=False) == {"code": "off_topic", "rule": "other_task"}


@pytest.mark.parametrize("text", ["안녕하세요", "ㅎㅇ", "고마워요"])
def test_text_without_any_travel_clue_is_sent_back(text):
    assert screen(text, has_files=False) == {"code": "off_topic", "rule": "no_travel_clue"}


@pytest.mark.parametrize("text", ["", "   \n "])
def test_empty_text_is_sent_back(text):
    assert screen(text, has_files=False) == {"code": "empty", "rule": "empty"}


@pytest.mark.parametrize("text", [
    "편안한 강남여행",                  # 여행 낱말
    "내일 경복궁",                      # 날짜 · 궁
    "10시 광장시장",                    # 시각 · 시장
    "롯데월드 남산",                    # 꼬리말(월드)
    "1일차 홍대 맛집",                  # 일차 · 맛집
    "성수 카페 투어",                   # 꼬리말
    "Day 1 Gyeongbokgung palace",       # 로마자 단서
    "파이썬 공부하다 지치면 서울 구경",  # 다른 일 낱말이 있어도 여행 단서가 있으면 읽는다
])
def test_anything_with_a_travel_clue_is_read_as_before(text):
    assert screen(text, has_files=False) is None


def test_attached_files_are_never_screened():
    assert screen("", has_files=True) is None and screen("안녕하세요", has_files=True) is None


def test_other_scripts_are_not_screened():
    """이 규칙이 단서를 모르는 글자(일본어 · 중국어 …) — 거르지 않는다."""
    assert screen("明日は浅草に行きたい", has_files=False) is None


def test_place_names_and_area_words_count_as_clues():
    assert screen("광장 통인", has_files=False, place_names=lambda text: "통인" in text) is None
    assert travel_clue("익선 가자", area_keys={"익선"}) == "place"
    assert travel_clue("엔서울타워", landmark_keys={"엔서울타워"}) == "place"
    assert screen("익선 좋아", has_files=False, area_keys={"없는말"}) == {"code": "off_topic", "rule": "no_travel_clue"}
