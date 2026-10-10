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


def test_hard_set_shapes_from_the_2159_measurement():
    """☆2026-10-10 21:59 playdata 어려운 문장 측정에서 틀린 모양들."""
    # 범위 근거 「13~15일」은 날을 맞추지 않는다(전에는 체크인이 15일로 바뀌었다)
    assert _stay({"check_in": "2026-11-13", "check_out": "2026-11-15", "check_in_text": "다음달 13~15일",
                  "check_out_text": "다음달 13~15일"}, "어른 2 초등학생 2 다음달 13~15일 경주")[0] == ("2026-11-13", "2026-11-15")
    # 지역 이름 · 사람 수는 날짜 근거가 아니다
    assert _stay({"check_in": "2026-10-10", "check_out": "2026-10-12", "check_in_text": "명동", "check_out_text": "2명"},
                 "명동 2명")[1] == ["check_in", "check_out"]
    # 「하루만」은 시작 날짜 근거가 아니다
    assert "check_in" in _stay({"check_in": "2026-10-11", "check_in_text": "하루만"}, "이번 여행 마지막 날 하루만 공항 근처 호텔")[1]
    # 요일 근거는 그 요일인 가장 가까운 날로 — 「금요일까지」 10-14(수) → 10-16(금)
    got = _stay({"check_in": "2026-10-12", "check_out": "2026-10-14", "check_in_text": "월요일부터", "check_out_text": "금요일까지"},
                "강남 비즈니스호텔 월요일부터 금요일까지 출장 1명")
    assert got[0] == ("2026-10-12", "2026-10-16") and got[2] == ["check_out"]


def test_a_price_band_start_becomes_the_band_end():
    found = lodging.parse({**BASE, "max_price_per_night": 150000})
    assert lodging.settle_years(found, today=TODAY, text="명동 2명 호텔 15만원대")[0].max_price_per_night == 159999
    found = lodging.parse({**BASE, "max_price_per_night": 200000})
    assert lodging.settle_years(found, today=TODAY, text="20만원 이하")[0].max_price_per_night == 200000, "이하는 그대로"
    assert lodging.settle_years(found, today=TODAY, text="20만 원대")[0].max_price_per_night == 299999


def test_english_dates_are_date_shaped():
    """☆22:25 「flight from Incheon to Taipei on Nov 6 for 1」 — 근거 「Nov 6」이 지워졌다."""
    from app.domains.travel_ops.instances._shared.interpret_dates import looks_like_date

    assert looks_like_date("Nov 6") and looks_like_date("November 6th") and looks_like_date("tomorrow")
    assert not looks_like_date("for 1") and not looks_like_date("Myeongdong")


def test_holidays_move_the_check_in_and_the_nights_follow():
    """☆22:28 「크리스마스에 2박」 — 12-24~26 으로 냈다."""
    got = _stay({"check_in": "2026-12-24", "check_out": "2026-12-26", "check_in_text": "크리스마스에", "check_out_text": "2박"},
                "해운대 근처 오션뷰 호텔 크리스마스에 2박 커플")
    assert got[0] == ("2026-12-25", "2026-12-27") and got[2] == ["check_in", "check_out"]
    got = _stay({"check_in": "2026-12-24", "check_out": "2026-12-25", "check_in_text": "크리스마스 이브에", "check_out_text": "1박"},
                "크리스마스 이브에 1박")
    assert got[0] == ("2026-12-24", "2026-12-25") and got[2] == []


def test_a_bare_day_number_ends_a_range_whose_start_is_a_date():
    """☆22:28 「hotel in Myeongdong Nov 6-9」 — 끝 근거가 「9」뿐."""
    got = _stay({"check_in": "2026-11-06", "check_out": "2026-11-09", "check_in_text": "Nov 6", "check_out_text": "9"},
                "hotel in Myeongdong Nov 6-9 for 2 people")
    assert got[0] == ("2026-11-06", "2026-11-09") and got[1] == []
    assert _stay({"check_in": "2026-11-06", "check_out": "2026-11-09", "check_in_text": "명동", "check_out_text": "2"},
                 "명동 2명")[1] == ["check_in", "check_out"], "시작 근거가 날짜가 아니면 받지 않는다"
