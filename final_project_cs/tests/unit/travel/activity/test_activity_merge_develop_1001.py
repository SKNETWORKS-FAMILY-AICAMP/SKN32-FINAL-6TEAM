# -*- coding: utf-8 -*-
"""조직 develop 의 활동 팀 새 작업(2026-09-29~10-01)에서 가져온 장점과, 같은 데이터로 두 코드를 돌려 보다 찾은 결함의 수정. `[2026-10-01]`

기록 — `wiki/records/reports/2026-10-01_Activity_develop_반영_리포트.md`

① 영업시간·휴무 **글**을 규칙만으로 요일별 칸으로 옮긴다(`activity/hours_text.py`) — 팀 읽기 규칙을 가져오되 슬래시 뒤 요일 결함을 고쳤다.
② 자정에 닫는 곳(「08:00 ~ 00:00」)을 항상 닫힘으로 읽던 우리 결함을 고쳤다.
③ 같은 브랜드 · 같은 구의 후보를 유사도 맨 앞에 둔다.
④ 실내·야외 표를 **이름을 확인한 분류만** 넓혔다(팀 표 중 섞인 갈래는 가져오지 않았다).
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.modules.travel_ops.activity.hours_text import closed_weekdays, read_week
from app.modules.travel_ops.activity.similarity import score
from app.modules.travel_ops.itinerary import weather_from_class
from app.modules.travel_ops.place_hours import fits


def _week(business, closed):
    read = read_week(business, closed)
    return None if read is None else read.week


def _open_days(week):
    return {day for day, entry in week.items() if entry != "closed"}


# ── ① 글 → 요일별 칸 ───────────────────────────────────────────
@pytest.mark.parametrize("closed, expected", [
    ("매주 일요일 / 월요일", {"sun", "mon"}),                   # ★팀 규칙이 슬래시 뒤 요일을 놓치던 자리
    ("매주 월요일 / 토요일 / 일요일", {"mon", "sat", "sun"}),
    ("매주 일요일~월요일", {"sun", "mon"}),
    ("매주 월요일, 화요일", {"mon", "tue"}),
    ("매주 월요일 (단, 공휴일이면 다음날 휴무)", {"mon"}),      # 괄호 안 예외는 읽지 않는다 — 앞은 매주 쉰다
    ("주말", {"sat", "sun"}),
    ("연중무휴", set()),
    ("없음", set()),
    ("공휴일", set()),                                          # 공휴일은 펴지 않는다 — 매주 쉬는 요일은 없다
    ("매주 월요일 / 매월 둘째 일요일", {"mon"}),                # ★잇지 않는다: 일요일은 매주 쉬는 날이 아니다
    ("매주 월요일, 매월 둘째 화요일", {"mon"}),
])
def test_closed_weekdays(closed, expected):
    assert closed_weekdays(closed) == expected


@pytest.mark.parametrize("closed", ["점포별 상이", "홈페이지 참조", "매월 둘째, 넷째 주 월요일", "부정기 휴무",
                                    "[1월~3월/8월]매주 월요일[4월~7월/9~12월]매주 일요일", "화요일"])
def test_a_closure_we_cannot_read_is_unknown_not_none(closed):
    """★읽을 수 없으면 `None`(모름) — 「쉬는 날 없음」으로 읽지 않는다. 그러면 열린 시간도 내지 않는다."""
    assert closed_weekdays(closed) is None
    assert _week("10:00~18:00", closed) is None


def test_slash_closed_days_remove_both_days_from_the_open_week():
    week = _week("11:00~18:00", "매주 일요일 / 월요일")
    assert week["mon"] == "closed" and week["sun"] == "closed"
    assert week["tue"] == {"open": "11:00", "close": "18:00", "last_entry": None}


def test_weekday_labels_split_the_week():
    week = _week("평일 09:00~18:00 / 주말 10:00~17:00", "없음")
    assert week["mon"]["open"] == "09:00" and week["sat"]["open"] == "10:00" and week["sun"]["close"] == "17:00"


def test_two_windows_on_the_same_day_are_not_read():
    """점심 휴게 같은 두 구간은 요일별 칸 하나로 못 옮긴다 — 지어내지 않고 비운다."""
    assert _week("10:00~13:00 / 14:00~18:00", "연중무휴") is None


def test_a_holiday_only_window_that_differs_is_not_guessed():
    assert _week("평일 09:00~18:00 / 공휴일 10:00~15:00", "없음") is None


def test_the_last_entry_time_is_carried():
    week = _week("10:00~19:10 (입장 마감 18:15)", "매주 월요일")
    assert week["tue"]["last_entry"] == "18:15"


def test_unsure_hours_words_leave_only_the_closed_days():
    week = _week("점포별 상이", "매주 월요일")
    assert week == {"mon": "closed"}


def test_nothing_readable_is_none():
    assert read_week("", "") is None
    assert read_week("점포별 상이", "점포별 상이") is None


def test_the_read_week_is_what_the_hours_check_understands():
    week = _week("11:00~18:00", "매주 일요일 / 월요일")
    attributes = {"hours_week": week}
    monday = datetime(2026, 10, 5, 13)
    tuesday = datetime(2026, 10, 6, 13)
    assert fits(attributes, monday, monday) is False         # 월요일은 쉰다
    assert fits(attributes, tuesday, tuesday) is True
    late = datetime(2026, 10, 6, 19)
    assert fits(attributes, late, late) is False


# ── ② 자정에 닫는 곳 ───────────────────────────────────────────
@pytest.mark.parametrize("hours, at, expected", [
    (["08:00", "00:00"], 21, True),        # ★전에는 항상 False 였다(다이소 같은 브랜드 매장 형식)
    (["00:00", "00:00"], 3, True),
    (["09:00", "18:00"], 19, False),       # 보통 곳은 그대로
    (["18:00", "02:00"], 21, True),        # 새벽까지 여는 곳은 그날 자정까지만 인정한다(보수적)
    (["18:00", "02:00"], 17, False),
])
def test_a_close_at_or_before_the_opening_means_end_of_day(hours, at, expected):
    moment = datetime(2026, 10, 5, at, 30)
    assert fits({"hours": hours}, moment, moment) is expected


def test_a_midnight_close_from_text_is_open_in_the_evening():
    week = _week("08:00 ~ 00:00", "연중무휴")
    evening = datetime(2026, 10, 7, 21)
    assert fits({"hours_week": week}, evening, evening) is True


# ── ③ 같은 브랜드 · 같은 구 ────────────────────────────────────
SHOP = {"lcls1": "SH", "lcls2": "SH04", "lcls3": "SH040100", "sigungu": "1", "brand": "올리브영"}


def test_the_same_brand_in_the_same_district_comes_first():
    same = dict(SHOP)
    same_class_other_brand = {**SHOP, "brand": "다이소"}
    assert score(SHOP, same) > score(SHOP, same_class_other_brand)


def test_the_same_brand_in_another_district_is_not_put_first():
    """구 밖 같은 브랜드보다 더 가까운 다른 매장이 낫다 — 거리는 순위 뒷단이 본다."""
    other_district = {**SHOP, "sigungu": "2"}
    same_district_other_brand = {**SHOP, "brand": "다이소"}
    assert score(SHOP, other_district) < score(SHOP, same_district_other_brand)


@pytest.mark.parametrize("origin, candidate", [
    ({**SHOP, "brand": None}, SHOP),               # 원래 장소가 브랜드를 모른다
    (SHOP, {**SHOP, "brand": None}),               # 후보가 브랜드를 모른다
    ({**SHOP, "sigungu": ""}, {**SHOP, "sigungu": ""}),   # 구를 모른다
])
def test_unknown_brand_or_district_never_counts_as_the_same(origin, candidate):
    plain = {k: v for k, v in origin.items() if k != "brand"}
    plain_candidate = {k: v for k, v in candidate.items() if k != "brand"}
    assert score(origin, candidate) == score(plain, plain_candidate)


# ── ④ 실내·야외 표 ─────────────────────────────────────────────
@pytest.mark.parametrize("lcls1, lcls2, expected", [
    ("SH", "SH01", False), ("SH", "SH02", False), ("SH", "SH04", False),       # 백화점 · 쇼핑몰 · 전문매장 → 실내
    ("EX", "EX02", False), ("EX", "EX05", False), ("VE", "VE12", False),       # 공예체험 · 스파 · 서점·문화센터 → 실내
    ("LS", "LS03", True), ("EX", "EX03", True),                                # 항공레저 · 농산어촌체험 → 야외
    ("NA", "NA01", True), ("VE", "VE03", True), ("VE", "VE07", False),         # 앞부터 있던 것은 그대로
])
def test_added_classes(lcls1, lcls2, expected):
    assert weather_from_class(lcls1, lcls2) is expected


@pytest.mark.parametrize("lcls1, lcls2", [
    ("LS", "LS02"),       # 「실내수영장」과 「수영장(실외)」이 한 분류
    ("HS", "HS01"),       # 경복궁과 덕수궁 중명전이 한 분류
    ("SH", "SH05"), ("SH", "SH06"), ("SH", "SH07"),       # 상가 · 시장 · 기타 쇼핑 — 노천이 섞인다
    ("EV", "EV01"), ("LS", "LS01"), ("VE", "VE02"),
])
def test_mixed_classes_stay_unknown(lcls1, lcls2):
    """섞인 갈래는 모름으로 둔다 — 모름은 날씨 사건 때 먼저 묻는 길로 간다(`pending.needs_consent`)."""
    assert weather_from_class(lcls1, lcls2) is None
