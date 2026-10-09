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


def test_holiday_dates_needed():
    assert holiday_dates_needed("매주 월요일", at(10, 12)) == []        # 공휴일 조건 없음 — 도구를 부르지 않는다
    assert holiday_dates_needed("매주 월요일 / 법정공휴일", at(10, 12)) == [date(2026, 10, 12)]
    assert holiday_dates_needed("설·추석 연휴", at(10, 12)) == [date(2026, 10, 12), date(2026, 10, 11),
                                                              date(2026, 10, 13)]
