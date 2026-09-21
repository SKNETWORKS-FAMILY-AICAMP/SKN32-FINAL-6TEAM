# -*- coding: utf-8 -*-
"""영업시간 원문 구조화의 회귀 테스트.

★**왜 필요한가.** 이 파서는 정규식 덩어리라 한 줄만 건드려도 다른 표기가 깨진다.
  그리고 **깨져도 오류가 나지 않는다** — 값만 조용히 틀린 채 적재된다.
  적재된 뒤에는 판정이 멀쩡히 돌아가므로 사람이 원문과 대조하기 전에는 모른다.

★여기 있는 표기는 전부 **관광공사 표본 200건에 실제로 나온 것**이다.
  지어낸 문장이 아니라 고치다가 걸렸던 자리들이다.

★2026-09-21 에 잡은 버그 넷이 각각 시험으로 남아 있다.
    1. 옆 항목의 낱말을 자기 것으로 읽어 영업시간이 브레이크로 분류됐다
    2. 괄호가 열리자마자 나온 낱말을 앞 범위가 가져가 영업시간이 통째로 사라졌다
    3. 「토요일」 안의 「일」 을 일요일로 읽어 일요일 시간이 오염됐다
    4. 「21:00 라스트오더」 처럼 시각이 낱말 앞에 오면 못 읽었다

★시각은 자정부터의 분이다. 자정을 넘기면 1440 이상이 된다.
  브레이크는 별도 칸이 아니라 **연속한 두 구간 사이의 빈 시간**으로 표현한다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dining" / "parse_hours.py"


def _load():
    spec = importlib.util.spec_from_file_location("dining_parse_hours", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ph = _load()

MON, FRI, SAT, SUN = 1, 5, 6, 7


def shape(rules: dict, day: int) -> list[tuple]:
    """한 요일의 구간을 (시작, 끝, 라스트오더, 상태) 목록으로."""
    return [(i["open_min"], i["close_min"], i["last_order_min"], i["last_order_state"])
            for i in rules[day]["intervals"]]


# ── 고친 버그의 회귀 ────────────────────────────────────────────

def test_옆_항목의_낱말을_가져가지_않는다():
    """「11:00~21:00 - 준비시간 15:00~17:00」 에서 앞 범위는 영업시간이다.

    고치기 전에는 뒤 항목의 「준비시간」 을 앞 범위가 자기 것으로 읽어
    둘 다 브레이크가 됐고, 영업 범위가 하나도 안 남아 모름이 됐다.
    """
    rules, _ = ph.parse_hours("- 11:00~21:00 - 준비시간 15:00~17:00 - 마지막 주문 20:00")
    assert shape(rules, MON) == [(660, 900, None, "unknown"),
                                 (1020, 1260, 1200, "present")]
    assert rules[MON]["break_state"] == "present"


def test_괄호가_열리자마자_나온_낱말은_괄호의_것이다():
    """「11:00~22:00 (브레이크타임 15:00~17:00)」 에서 앞 범위는 영업시간이다.

    고치기 전에는 주중 영업시간이 통째로 사라져 평일 전체가 모름이었다.
    """
    rules, _ = ph.parse_hours(
        "주중 11:00~22:00 (브레이크타임 15:00~17:00 / 라스트오더 21:30) "
        "토요일 16:00~22:00 (라스트오더 21:30)")
    assert shape(rules, MON) == [(660, 900, None, "unknown"),
                                 (1020, 1320, 1290, "present")]
    assert shape(rules, SAT) == [(960, 1320, 1290, "present")]
    # 원문이 일요일을 말하지 않았다. 지어내지 않는다.
    assert rules[SUN]["coverage"] == "unknown"


@pytest.mark.parametrize("token, expected", [
    ("토요일", (SAT,)),
    ("일요일", (SUN,)),
    ("평일", (1, 2, 3, 4, 5)),
    ("주중", (1, 2, 3, 4, 5)),
    ("주말", (SAT, SUN)),
    ("화요일~토요일", (2, 3, 4, 5, 6)),
    ("일~목요일", (1, 2, 3, 4, 7)),
])
def test_요일_낱말을_정확히_읽는다(token, expected):
    """「토요일」 안의 「일」 을 일요일로 읽으면 일요일 시간이 오염된다."""
    assert set(ph.days_from_token(token)) == set(expected)


def test_시각이_낱말_앞에_와도_읽는다():
    """「21:00 라스트오더」 처럼 순서가 뒤집힌 표기."""
    rules, _ = ph.parse_hours(
        "일~목요일 11:30 ~ 22:00 (15:00~17:00 브레이크타임) 21:00 라스트오더 "
        "금~토요일 12:00~24:00 (15:00~17:00 브레이크타임) 23:00 라스트오더")
    assert shape(rules, MON)[1] == (1020, 1320, 1260, "present")
    assert shape(rules, FRI)[1] == (1020, 1440, 1380, "present")


# ── 요일별 전개 ────────────────────────────────────────────────

def test_대괄호_블록을_요일별로_나눈다():
    rules, _ = ph.parse_hours(
        "[평일] - 08:00~22:00 - 마지막 주문 21:30 [주말] - 09:00~22:00 - 마지막 주문 21:30")
    assert shape(rules, MON) == [(480, 1320, 1290, "present")]
    assert shape(rules, SAT) == [(540, 1320, 1290, "present")]


def test_구분자로_이어진_요일을_나눈다():
    rules, _ = ph.parse_hours("- 평일 10:00~20:00 - 토요일 12:00~21:00 - 일요일 12:00~20:00")
    assert shape(rules, MON)[0][:2] == (600, 1200)
    assert shape(rules, SAT)[0][:2] == (720, 1260)
    assert shape(rules, SUN)[0][:2] == (720, 1200)


def test_요일_언급이_없으면_모든_요일에_적용한다():
    rules, _ = ph.parse_hours("11:00~21:00")
    assert all(rules[d]["coverage"] == "intervals" for d in range(1, 8))


def test_브레이크에_붙은_요일_한정을_지킨다():
    """「준비시간(평일)」 은 평일에만 적용한다. 주말은 통으로 연다."""
    rules, _ = ph.parse_hours("- 11:00~21:00 - 준비시간(평일) 14:30~17:00 - 마지막 주문 20:00")
    assert len(shape(rules, MON)) == 2
    assert shape(rules, MON)[0] == (660, 870, None, "unknown")
    assert shape(rules, SAT) == [(660, 1260, 1200, "present")]
    assert rules[SAT]["break_state"] == "unknown"


# ── 모름을 없음으로 바꾸지 않는다 ───────────────────────────────

def test_브레이크_언급이_없으면_모름이다():
    """없다고 단정하지 않는다. 자료가 말하지 않은 것뿐이다."""
    rules, _ = ph.parse_hours("11:00~21:00")
    assert rules[MON]["break_state"] == "unknown"


def test_라스트오더_언급이_없으면_모름이다():
    rules, _ = ph.parse_hours("11:00~21:00")
    assert rules[MON]["intervals"][0]["last_order_state"] == "unknown"
    assert rules[MON]["intervals"][0]["last_order_min"] is None


def test_한_구간에_라스트오더_후보가_여럿이면_모름으로_둔다():
    """이른 쪽을 고르면 실제보다 좁게 잡혀 멀쩡한 시간을 거른다."""
    rules, notes = ph.parse_hours("- 11:00~21:00 - 마지막 주문 14:45, 20:15")
    assert rules[MON]["intervals"][0]["last_order_state"] == "unknown"
    assert any("여럿" in n for n in notes)


def test_원문이_없으면_규칙을_만들지_않는다():
    rules, notes = ph.parse_hours("")
    assert rules == {}
    assert notes


# ── 시간 표현 ──────────────────────────────────────────────────

def test_자정을_넘기면_1440_을_넘는다():
    """18시부터 새벽 2시까지가 하나의 구간이어야 비교가 성립한다."""
    rules, _ = ph.parse_hours("18:00~02:00")
    assert shape(rules, MON)[0][:2] == (1080, 1560)


def test_24시_표기를_1440_으로_읽는다():
    rules, _ = ph.parse_hours("12:00~24:00")
    assert shape(rules, MON)[0][:2] == (720, 1440)


def test_브레이크는_구간_사이의_빈_시간이다():
    """별도 칸을 두지 않는다. 구간 둘 사이가 곧 브레이크다."""
    rules, _ = ph.parse_hours("- 11:00~21:00 - 준비시간 15:00~17:00")
    got = shape(rules, MON)
    assert len(got) == 2
    assert got[0][1] == 900 and got[1][0] == 1020   # 15:00 에 끊고 17:00 에 다시 연다


# ── 휴무 ───────────────────────────────────────────────────────

@pytest.mark.parametrize("text, expected", [
    ("연중무휴", []),
    ("매주 일요일", [{"pattern_kind": "weekly", "weekday": 7}]),
    ("매주 월요일, 화요일", [{"pattern_kind": "weekly", "weekday": 1},
                              {"pattern_kind": "weekly", "weekday": 2}]),
    ("주말", [{"pattern_kind": "weekly", "weekday": 6},
              {"pattern_kind": "weekly", "weekday": 7}]),
    ("매월 둘째, 넷째 화요일", [{"pattern_kind": "monthly_nth", "weekday": 2, "nth": [2, 4]}]),
])
def test_휴무_표기를_규칙으로_바꾼다(text, expected):
    rules, _ = ph.parse_closure(text)
    assert rules == expected


def test_명절은_당일과_연휴를_구분한다():
    whole, _ = ph.parse_closure("설·추석 연휴")
    day_of, _ = ph.parse_closure("설·추석 당일")
    assert {r["holiday_scope"] for r in whole} == {"whole_period"}
    assert {r["holiday_scope"] for r in day_of} == {"day_of"}
    assert {r["holiday_name"] for r in whole} == {"설날", "추석"}


@pytest.mark.parametrize("text", ["격주 일요일", "매월 마지막 주 월요일",
                                  "- 봄, 가을 : 월요일, 화요일 - 여름, 겨울 : 월요일, 일요일"])
def test_담지_못하는_휴무는_규칙을_만들지_않고_남긴다(text):
    """표현할 수 없는 것을 억지로 담지 않는다. 사람이 볼 수 있게 사유만 남긴다.

    ★2026-09-21 회귀. 계절별 휴무에서 요일만 뽑아 「매주 월요일 휴무」 를 만들었다.
      실제보다 많이 닫힌 것으로 판정해 멀쩡한 집을 거르는 방향이라 더 나쁘다.
    """
    rules, notes = ph.parse_closure(text)
    assert rules == []
    assert notes


def test_당일의_일을_일요일로_읽지_않는다():
    """★2026-09-21 회귀. 「설·추석 당일」 에서 「당일」 의 「일」 을 일요일로 읽어
    매주 일요일 휴무가 함께 만들어졌다. 「토요일」 안의 「일」 과 같은 종류다.
    """
    rules, _ = ph.parse_closure("설·추석 당일")
    assert all(r["pattern_kind"] == "named_holiday" for r in rules)
    assert not any(r.get("weekday") == 7 for r in rules)
