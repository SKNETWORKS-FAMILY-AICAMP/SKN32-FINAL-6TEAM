# -*- coding: utf-8 -*-
"""숙소 · 항공 해석 공용 날짜 검증(`instances/_shared/interpret_dates.py`). 모델 없음 — 2026-10-10 해석 측정에서 틀린 모양 그대로. `[2026-10-10]`"""
from __future__ import annotations

from datetime import date

from app.domains.travel_ops.instances.flight import interpret as flight
from app.domains.travel_ops.instances.lodging import interpret as lodging
from app.domains.travel_ops.instances._shared.interpret_dates import model_context, quote_found

TODAY = date(2026, 10, 10)
TRIP = {"party_size": 3, "first_day": "2026-11-06", "last_day": "2026-11-09", "places": ["경복궁"]}
BASE = {"task": "search", "keyword": "x", "adults": 2}


def _stay(raw, text, trip=None):
    found, cleared = lodging.ground(lodging.parse({**BASE, **raw}), text, has_trip=trip is not None, trip=trip)
    found, fixed = lodging.settle_years(found, today=TODAY)
    return (str(found.check_in), str(found.check_out)), cleared, fixed


def test_the_models_missing_list_no_longer_clears_a_grounded_date():
    """☆17:55 「다음 달 6일부터 9일까지」 — 맞게 읽고 근거도 맞는데 missing 에 넣어 지워졌다."""
    got = _stay({"check_in": "2026-11-06", "check_out": "2026-11-09", "check_in_text": "다음 달 6일부터", "check_out_text": "9일까지",
                 "missing": ["keyword", "check_in", "check_out", "adults"]}, "다음 달 6일부터 9일까지 부산 해운대 근처 2명")
    assert got == (("2026-11-06", "2026-11-09"), [], [])


def test_nights_alone_are_not_a_check_in_and_take_the_check_out_with_them():
    """☆10-08 15:30 · 10-10 17:58 「서울에서 3박」 — 체크인을 오늘로 채우고 근거로 「3박」."""
    got = _stay({"check_in": "2026-10-10", "check_out": "2026-10-13", "check_in_text": "3박", "check_out_text": "3박"},
                "서울에서 3박 할 숙소 추천해줘")
    assert got == (("None", "None"), ["check_in", "check_out"], [])


def test_a_range_quote_with_the_same_numbers_is_accepted_but_numbers_out_of_order_are_not():
    assert quote_found("11월 6일", "20만원대 호텔 명동 11월 6~8일 성인 2"), "☆17:55 「11월 6~8일」"
    assert not quote_found("11월 6일", "6명이서 11시에 3박 서울"), "숫자 순서가 다르면 아니다"
    assert not quote_found("오늘", "서울에서 3박 할 숙소 추천해줘")


def test_a_trip_date_is_kept_even_when_the_model_made_up_the_quote():
    """☆17:55 「이번 여행 숙소 일정 근처로 찾아줘」 — 값은 여행 날짜인데 근거를 「11월 6일부터」로 지어 적었다."""
    got = _stay({"check_in": "2026-11-06", "check_out": "2026-11-09", "check_in_text": "11월 6일부터", "check_out_text": "9일까지"},
                "이번 여행 숙소 일정 근처로 찾아줘", trip=TRIP)
    assert got == (("2026-11-06", "2026-11-09"), [], [])
    _, cleared, _ = _stay({"check_in": "2026-11-06", "check_out": "2026-11-09", "check_in_text": "11월 6일부터",
                           "check_out_text": "9일까지"}, "이번 여행 숙소 일정 근처로 찾아줘")
    assert cleared == ["check_in", "check_out"], "여행이 없으면 지운다"


def test_the_day_follows_the_quote_and_the_year_follows_today():
    """☆17:55 「9일 체크아웃 … 1박 30만원」 → 11-07, ☆17:47 「1월 3일부터 2박 3일」 → 2024."""
    got = _stay({"check_in": "2026-11-06", "check_out": "2026-11-07", "check_in_text": "11월 6일", "check_out_text": "9일"},
                "11월 6일 체크인 9일 체크아웃 시부야 2명 1박 30만원 이하")
    assert got == (("2026-11-06", "2026-11-09"), [], ["check_out"])
    got = _stay({"check_in": "2024-01-03", "check_out": "2024-01-05", "check_in_text": "1월 3일부터", "check_out_text": "2박 3일"},
                "1월 3일부터 2박 3일 오사카 난바 호텔 어른 2명 아이 1명")
    assert got == (("2027-01-03", "2027-01-05"), [], ["check_in", "check_out"])
    got = _stay({"check_in": "2023-11-06", "check_out": "2023-11-09", "check_in_text": "2023년 11월 6일부터", "check_out_text": "3박"},
                "2023년 11월 6일부터 3박")
    assert got[0] == ("2023-11-06", "2023-11-09") and got[2] == [], "연도를 말했으면 바꾸지 않는다"


def test_a_return_before_the_departure_is_left_for_needs_to_ask():
    raw = {"task": "search", "origin": "ICN", "destination": "CTS", "domestic": False, "adults": 1, "depart_date": "2026-11-06",
           "return_date": "2026-11-04", "depart_date_text": "11월 6일", "return_date_text": "11월 4일에"}
    found, cleared = flight.ground(flight.parse(raw), "11월 6일 인천에서 삿포로 갔다가 11월 4일에 돌아와 1명", has_trip=False)
    found, fixed = flight.settle_years(found, today=TODAY)
    assert (cleared, fixed, str(found.return_date)) == ([], [], "2026-11-04")
    assert flight.needs(found, today=TODAY) == ["return_date"]


def test_the_calendar_lets_the_model_read_weekdays():
    context = model_context(TODAY, TRIP)
    assert context["today_weekday"] == "토" and context["calendar"][6] == "2026-10-16 금" and context["trip"] == TRIP
