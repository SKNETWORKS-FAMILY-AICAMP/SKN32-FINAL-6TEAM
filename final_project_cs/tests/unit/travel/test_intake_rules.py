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


# ── 2026-09-28 평가셋에서 찾은 셋 ───────────────────────────────────
def test_a_short_line_between_timed_stops_is_an_untimed_item():
    r = read_plan(chr(10).join(["DAY 1 2026-10-27", "09:30 여의도한강공원", "광장시장 빈대떡", "15:00 경복궁 관람"]))
    assert [(i.start, i.title.text) for i in r.items] == [("09:30", "여의도한강공원"), ("15:00", "경복궁 관람"),
                                                         (None, "광장시장 빈대떡")]
    assert r.items[2].date == "2026-10-27" and r.unread_lines == []


def test_a_sentence_between_stops_is_left_for_the_model():
    r = read_plan(chr(10).join(["09:00 경복궁", "점심은 토속촌에서 먹을래", "15:00 인사동"]))
    assert [i.title.text for i in r.items] == ["경복궁", "인사동"] and r.unread_lines == [2]


def test_a_table_row_with_an_empty_time_cell_is_an_item_not_a_heading():
    text = chr(10).join(["일차 | 날짜 | 시각 | 일정 | 메모", "1일차 | 2026-10-10 | 09:30 | 국립중앙박물관 관람",
                         "1일차 | 2026-10-10 | 광장시장 빈대떡", "1일차 | 2026-10-10 | 15:00 | 국립민속박물관"])
    r = read_plan(text)
    assert [(i.start, i.title.text, i.date) for i in r.items] == [
        ("09:30", "국립중앙박물관 관람", "2026-10-10"), (None, "광장시장 빈대떡", "2026-10-10"),
        ("15:00", "국립민속박물관", "2026-10-10")]


def test_a_date_written_on_each_timed_line_is_that_items_date():
    """★`[2026-09-28]` 「2026-10-05 09:00 경복궁 관람」 — 전에는 날짜를 머리줄(시각 없는 줄)에서만 받아 버렸다(ui 세션 실서버 시험)."""
    r = read_plan("2026-10-05 09:00 경복궁 관람\n12:00 토속촌 삼계탕\n10월 6일 10:00 북촌한옥마을 산책")
    assert [(i.date, i.start, i.title.text) for i in r.items] == [
        ("2026-10-05", "09:00", "경복궁 관람"), ("2026-10-05", "12:00", "토속촌 삼계탕"),
        ("--10-06", "10:00", "북촌한옥마을 산책")]
    assert [c.value for c in r.claims if c.field.endswith(".date")] == ["2026-10-05", "--10-06"]


@pytest.mark.parametrize("text, title", [
    ("2026-10-05\n09:00 경복궁", "내 여행"),
    ("10월 5일 (월)\n09:00 경복궁", "내 여행"),
    ("2026-10-05 09:00 경복궁", "내 여행"),
    ("10월 5일 서울 가족여행\n09:00 경복궁", "10월 5일 서울 가족여행"),       # 날짜 뒤에 제목이 있으면 제목이다
    ("서울 가족여행\n1일차 · 2026-10-05\n09:00 경복궁", "서울 가족여행"),
])
def test_a_line_that_is_only_a_date_is_not_the_trip_title(text, title):
    """★`[2026-09-28]` 날짜 머리줄로 시작하는 글의 제목이 그 날짜가 됐다(ui 세션 실서버 시험)."""
    from app.modules.travel_ops.intake.assemble import _title

    assert _title({}, [{"transcript": text}]) == title
