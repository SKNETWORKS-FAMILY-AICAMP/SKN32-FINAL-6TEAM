# -*- coding: utf-8 -*-
"""규칙 읽기 — 읽은 줄 / 남은 줄. ★거절하지 않는다. 값은 원문 조각 그대로(바꿔 적지 않는다). `[2026-09-27]`"""
from __future__ import annotations

import pytest

from app.modules.travel_ops.intake.rules import read_plan


def _items(text):
    return [(i.start, i.end, i.title.text if i.title else None) for i in read_plan(text).items]


@pytest.mark.parametrize("text, expected", [
    ("09:00 경복궁", [("09:00", None, "경복궁")]),
    ("오전 9시 경복궁", [("09:00", None, "경복궁")]),
    ("오후 2시 광장시장 빈대떡", [("14:00", None, "광장시장 빈대떡")]),
    ("9시 반에 경복궁을 보고", [("09:30", None, "경복궁")]),
    ("12:30~13:30 토속촌삼계탕", [("12:30", "13:30", "토속촌삼계탕")]),
    ("10시~12시 한강 카약", [("10:00", "12:00", "한강 카약")]),
    ("10:00 북촌한옥마을", [("10:00", None, "북촌한옥마을")]),                 # ☆「을」을 조사로 자르던 결함
    ("12:30 토속촌삼계탕 점심", [("12:30", None, "토속촌삼계탕")]),           # 끼니 말은 떼고 식사 단서로
    ("09:00 | 경복궁", [("09:00", None, "경복궁")]),                          # ☆표 행 — 이름을 통째로 자르던 결함
    ("9시에 경복궁 가고, 오후 3시에 인사동 가요", [("09:00", None, "경복궁"), ("15:00", None, "인사동")]),
    ("저녁 7시에 명동", [("19:00", None, "명동")]),
])
def test_time_lines_are_read_and_names_are_cut_not_rewritten(text, expected):
    assert _items(text) == expected
    for item in read_plan(text).items:                          # ★이름은 원문 조각 그대로
        assert text.splitlines()[item.title.line - 1][item.title.start:item.title.end] == item.title.text


def test_booking_number_party_nights_and_days():
    r = read_plan("서울 2박3일 (4명)\n1일차 · 2026-10-15\n19:00 명동난타극장 예약번호 KY-20931\n2일차 · 2026-10-16\n10:00 북촌")
    assert (r.party_size, r.nights, r.days) == (4, 2, 3)
    assert [i.booking_no.text for i in r.items if i.booking_no] == ["KY-20931"]
    assert [(i.day, i.date) for i in r.items] == [(1, "2026-10-15"), (2, "2026-10-16")]
    assert r.unread_lines == []


def test_unclear_hour_is_kept_as_written_and_marked():
    claims = [c for c in read_plan("3시에 남산타워").claims if c.needs_review]
    assert [(c.field, c.value) for c in claims] == [("items[0].starts_at", "03:00")]


def test_arrows_keep_order_without_inventing_times():
    items = read_plan("경복궁 → 광장시장 → 명동").items
    assert [(i.title.text, i.start, i.order_only) for i in items] == [
        ("경복궁", None, True), ("광장시장", None, True), ("명동", None, True)]


def test_lines_that_rules_cannot_read_are_left_not_refused():
    r = read_plan("09:00 경복궁\n점심은 아무 데나 괜찮아요\n넷이서 가요")
    assert r.unread_lines == [2] and r.party_size == 4



@pytest.mark.parametrize("text, party", [
    ("19:00 명동난타극장 예약번호 KY-20931", None),     # ☆실제 화면 — 「00 명」을 0명으로 읽었다
    ("10:00 인사동 산책", None),
    ("점심 2인분 포장", None),
    ("서울 가족여행 (4명)", 4),
    ("4명이서 가요", 4),
    ("4인 가족", 4),
    ("3인가족 여행", 3),
])
def test_party_size_is_not_read_from_times_or_place_names(text, party):
    read = read_plan(text)
    assert read.party_size == party
