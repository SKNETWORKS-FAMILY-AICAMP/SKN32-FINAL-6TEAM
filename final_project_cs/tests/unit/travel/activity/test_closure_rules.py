# -*- coding: utf-8 -*-
"""정기휴무 원문 판정(`closure_rules.py`) — 결함 2026-10-06_1610 의 재발 방지와 새 규칙.

★가장 중요한 검사 — CSV 장소 목록의 「매주 X」 원문은 **한 주 안에 적어도 하루는 휴무로 잡혀야** 한다.
  전에는 309건 중 307건이 어느 요일에도 휴무로 안 잡혔다(정규식이 「매주 X 휴무」 모양만 읽었다).
"""
from __future__ import annotations

import csv
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest


from app.domains.travel_ops.instances.activity.closure_rules import holiday_dates_needed, read_closure


KST = timezone(timedelta(hours=9))
CSV_PATH = (Path(__file__).resolve().parents[4] / "app" / "domains" / "travel_ops" / "instances" / "activity"
            / "data_processing" / "activity_total_data.csv")
#: 2026년 특일(한국천문연구원 응답 모양). ★추석 사흘이 같은 이름으로 온다고 가정한다 — 실측 확인 필요(키 403)
CAL = {date(2026, 9, 24): "추석", date(2026, 9, 25): "추석", date(2026, 9, 26): "추석",
       date(2026, 10, 3): "개천절", date(2026, 10, 5): "대체공휴일", date(2026, 10, 9): "한글날",
       date(2027, 1, 1): "1월1일"}


def known(day):
    return {"is_holiday": day in CAL, "holiday_name": CAL.get(day)}


def at(m, d, h=14, y=2026):
    return datetime(y, m, d, h, tzinfo=KST)


@pytest.mark.skipif(not CSV_PATH.exists(), reason="CSV 장소 목록이 없다")
def test_every_weekly_text_in_the_csv_closes_on_some_weekday():
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        texts = [(r.get("closed_days") or "").strip() for r in csv.DictReader(fh)]
    weekly = [t for t in texts if re.search(r"매주\s*[월화수목금토일]", t)]
    week = [at(10, 12 + i) for i in range(7)]            # 2026-10-12(월) ~ 18(일) — 공휴일 없는 주
    missed = [t for t in weekly if not any(read_closure(t, day, known).value for day in week)]
    assert len(weekly) > 200 and missed == [], missed[:5]


@pytest.mark.parametrize("text, when, expected, reason", [
    ("매주 월요일", at(10, 12), True, "weekly"),                       # 「휴무」 낱말이 없다 — 옛 정규식이 놓친 모양
    ("매주 월요일", at(10, 13), False, None),
    ("매주 토요일~일요일", at(10, 11), True, "weekly"),
    ("매주 일요일~월요일", at(10, 12), True, "weekly"),                # 주를 넘는 범위
    ("매주 월, 화, 공휴일 휴무", at(10, 13), True, "weekly"),          # 요일 글자 나열
    ("주말", at(10, 17), True, "weekend"),
    ("연중무휴", at(10, 12), False, None),
    ("휴무일 없음", at(10, 12), False, None),                         # 한강 수영장 · 눈썰매장 공식 문구(2026-10-15)
    ("휴관일 없음", at(10, 12), False, None),
    ("매월 둘째 주 화요일 휴무", at(10, 13), True, "nth_weekday"),
    ("매월 둘째 주 화요일 휴무", at(10, 20), False, None),
    ("매월 첫째·셋째 주 월요일", at(10, 19), True, "nth_weekday"),
    ("매월 마지막 주 수요일 휴관", at(10, 28), True, "nth_weekday"),
    ("매년 3월, 6월, 9월, 12월 첫 번째 월요일", at(9, 7), True, "nth_weekday"),
    ("매년 3월, 6월, 9월, 12월 첫 번째 월요일", at(10, 5), False, None),   # 10월은 해당 달이 아니다
    ("매주 월요일 / 1월 1일 / 설·추석 당일", at(1, 1, y=2027), True, "date"),
    ("월요일, 1월 1일, 설날, 추석날", at(10, 12), True, "weekly"),      # 한 절에 요일·날짜·명절이 섞였다
    ("점포별 상이함", at(10, 12), None, "unknown_marker"),
    ("오늘은 임시휴무입니다", at(10, 12), None, "unparsed"),            # ★못 읽으면 모름 — 「아님」으로 확정하지 않는다
    ("", at(10, 12), None, "empty"),
])
def test_rules_without_holiday_info(text, when, expected, reason):
    result = read_closure(text, when)
    assert result.value is expected
    if reason:
        assert result.reason == reason


@pytest.mark.parametrize("text, when, without, with_info", [
    ("매주 토요일~일요일 / 법정공휴일", at(10, 9), None, True),          # 한글날
    ("매주 토요일~일요일 / 법정공휴일", at(10, 14), None, False),
    ("명절 당일 휴무", at(9, 25), None, True),                         # 추석 당일(사흘의 가운데)
    ("명절 당일 휴무", at(9, 24), None, None),                          # 연휴 첫날 — 당일인지 확정하지 않는다
    ("명절 당일 휴무", at(10, 15), None, False),
    ("설·추석 연휴 휴관", at(9, 26), None, True),
])
def test_holiday_conditions_need_holiday_info(text, when, without, with_info):
    assert read_closure(text, when).value is without
    assert read_closure(text, when, known).value is with_info


def test_holiday_exception_on_weekly_closure():
    """「매주 X (단, 공휴일이면 개방)」 — 모르면 휴무+단서(전과 같다), 공휴일이 아니면 휴무, 공휴일이면 아님."""
    text = "매주 월요일 (단, 월요일이 공휴일인 경우 정상 운영)"
    unknown = read_closure(text, at(10, 12))
    assert (unknown.value, unknown.needs_caveat) == (True, True)
    assert read_closure(text, at(10, 12), known).value is True
    assert read_closure(text, at(10, 5), known).value is False          # 10/5 대체공휴일 — 연다


def test_carry_over_rule_is_not_guessed():
    """「공휴일이면 개방하고 다음 평일 휴관」 — 전날이 공휴일이었으면 오늘이 휴무일 수 있다. 모르면 확정하지 않는다."""
    text = "매주 월요일<br>※ 단, 월요일이 공휴일인 경우 개방하며, 그 다음 첫 번째 평일에 휴관"
    assert read_closure(text, at(10, 6), known).value is None           # 10/5 가 공휴일이었다 → 10/6 은 모름
    assert read_closure(text, at(10, 13), known).value is False


def test_closure_is_judged_on_the_korean_date():
    """15:00 UTC 는 다음 날 00:00 KST — 한국 날짜의 요일로 판정한다."""
    sunday_utc = datetime(2026, 10, 11, 15, tzinfo=timezone.utc)        # = 10/12(월) 00:00 KST
    assert read_closure("매주 월요일", sunday_utc).value is True


@pytest.mark.parametrize("text, when, expected", [
    ("명절, 월1회", at(10, 12), None),                    # ★전에는 월요일 True(weekly) — 「월」을 요일로 읽었다
    ("월 1회", at(10, 12), None),
    ("월 1회 비정기 휴무", at(10, 14), None),
    ("매월 2회 휴무", at(10, 12), None),
    ("명절, 월 1회 월요일", at(10, 12), None),             # 월요일 가운데 어느 날인지 모른다
    ("명절, 월 1회 월요일", at(10, 13), False),            # 화요일 — 이 원문으로는 휴무가 아니다
    ("명절, 월2회 일요일", at(10, 18), None),
    ("명절, 월2회 일요일", at(10, 12), False),             # ★전에는 월요일 True
    ("매월 5번째 월요일", at(11, 30), True),               # 숫자 서수 — 11/30 은 다섯째 월요일
    ("매월 5번째 월요일", at(10, 12), False),              # ★전에는 매주 월요일 True
    ("2·4주차 일요일", at(10, 25), True),                  # 넷째 일요일
    ("2·4주차 일요일", at(10, 18), False),                 # ★전에는 매주 일요일 True — 셋째 일요일
    ("2,4주 수요일", at(10, 14), True),
    ("2,4주 수요일", at(10, 21), False),
    ("매달 1, 3, 5번째 일요일", at(11, 1), True),           # 첫째 일요일 — ★전에는 5 만 읽어 모름
    ("매달 1, 3, 5번째 일요일", at(11, 15), True),          # 셋째
    ("매달 1, 3, 5번째 일요일", at(11, 29), True),          # 다섯째
    ("매달 1, 3, 5번째 일요일", at(11, 8), False),          # 둘째
    ("매달 1, 3, 5번째 일요일", at(11, 2), False),          # 월요일 — ★「매달」이 군말 목록에 없어 모름이었다
])
def test_monthly_count_is_not_a_monday(text, when, expected):
    """결함 2026-10-14_2208 — 「월 N회」의 「월」은 달이다. 날짜가 정해지지 않았으니 모름이다."""
    assert read_closure(text, when, known).value is expected


@pytest.mark.skipif(not CSV_PATH.exists(), reason="CSV 장소 목록이 없다")
def test_no_monthly_count_text_in_the_csv_closes_every_week():
    """CSV 「월 N회」 원문 중 공휴일 없는 주에 휴무(True)로 잡히는 날이 하나도 없다. 고치기 전 101/102행이 월요일 True."""
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        texts = [(r.get("closed_days") or "").strip() for r in csv.DictReader(fh)]
    monthly = [t for t in texts if re.search(r"(?:매월|(?<![가-힣\d])월)\s*(?:\d+|한|두|세)\s*(?:회|번|차례)(?!\s*째)", t)]
    week = [at(10, 12 + i) for i in range(7)]
    closed = [t for t in monthly if any(read_closure(t, day, known).value for day in week)]
    assert len(monthly) > 90 and closed == [], closed[:5]


@pytest.mark.parametrize("text, when, expected", [
    # 해를 넘기는 범위 — x600 서버 관광공사 운영시간 표의 실제 문장(2026-10-21). ★전에는 양 끝만 True, 사이(12-30 · 12-31 · 1-1)는 False
    ("12월 29일~1월 2일", at(12, 28), False),              # 시작 전날
    ("12월 29일~1월 2일", at(12, 29), True),               # 시작일
    ("12월 29일~1월 2일", at(12, 30), True),               # 사이
    ("12월 29일~1월 2일", at(12, 31), True),               # 사이 — 실제 결함 재현
    ("12월 29일~1월 2일", at(1, 1, y=2027), True),          # 사이(해 넘김)
    ("12월 29일~1월 2일", at(1, 2, y=2027), True),          # 끝일
    ("12월 29일~1월 2일", at(1, 3, y=2027), False),         # 끝 다음 날
    ("12월 29일~1월 2일", at(7, 15), False),               # 한참 밖
    # 같은 해 안의 범위 · 끝의 달 생략 · 글자 모양 달라도 같다
    ("3월 1일~3월 10일", at(3, 5, y=2027), True),
    ("3월 1일~3월 10일", at(3, 11, y=2027), False),
    ("3월 1일 ~ 3월 10일", at(3, 10, y=2027), True),
    ("12월 29일-31일", at(12, 30), True),                  # 끝의 달을 빼면 시작과 같은 달
    ("12월 29일-31일", at(1, 1, y=2027), False),
    ("12월 29일부터 1월 2일까지", at(12, 31), True),
    ("12월 29일부터 1월 2일까지", at(1, 3, y=2027), False),
    ("매주 월요일 / 설·추석 연휴 / 근로자의 날 / 선거일 / 12월 29일~1월 2일", at(1, 1, y=2027), True),   # 실제 문장 전체
])
def test_date_range_covers_every_day_between_its_ends(text, when, expected):
    """날짜 범위는 양 끝만이 아니라 사이 날짜까지 휴무다. 해를 넘기면(끝이 시작보다 앞서면) 연말에서 연초로 이어진다."""
    assert read_closure(text, when, known).value is expected


def test_date_range_inside_the_range_is_reported_as_a_date_range_closure():
    result = read_closure("12월 29일~1월 2일", at(12, 31))
    assert (result.value, result.reason, result.quote) == (True, "date_range", "12월 29일~1월 2일")


def test_date_range_with_only_a_month_at_the_end_is_unknown():
    """「12월 29일~1월 초」 — 끝 날짜를 모르면 사이를 정하지 못한다. 「아님」으로 확정하지 않는다(CLAUDE.md §0)."""
    for day in (at(12, 28), at(12, 31), at(1, 15, y=2027)):
        assert read_closure("12월 29일~1월 초", day).value is None


def test_holiday_dates_needed():
    assert holiday_dates_needed("매주 월요일", at(10, 12)) == []        # 공휴일 조건 없음 — 도구를 부르지 않는다
    assert holiday_dates_needed("매주 월요일 / 법정공휴일", at(10, 12)) == [date(2026, 10, 12)]
    assert holiday_dates_needed("설·추석 연휴", at(10, 12)) == [date(2026, 10, 12), date(2026, 10, 11),
                                                              date(2026, 10, 13)]
