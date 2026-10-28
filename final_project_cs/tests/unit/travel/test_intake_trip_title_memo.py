# -*- coding: utf-8 -*-
"""ST4F-631 — 일정 중간의 메모 줄이 여행 제목이 되던 결함.

★`[2026-10-28]` 읽기 결과에 여행 이름이 없으면(읽기 에이전트는 `trip` 에 인원 · 일수 · 박수만 낸다) `assemble._title` 이
원문에서 날짜 · 시각으로 시작하지 않는 **첫 줄**을 제목으로 썼다. 날짜 머리줄 · 시각 줄로만 된 목록에서는 일정 사이에
끼운 메모(「도착일이라 가볍게」 · 시험 원문 test20)가 그 첫 줄이 되어 x600 실서버에서 여행 제목으로 보였다.

계약: 제목은 일정이 시작되기 **앞**(머리)에 적힌 줄이다. 판단 근거는 규칙 읽기(`rules.read_plan`) 결과의 구조 —
일정 항목 claim(`items[*]`)이 있는 줄 · 읽은 날짜/일차 머리줄의 줄 번호 — 와 원문 순서다. 그 줄부터는 일정 본문이므로
그 줄과 뒤 줄(뒤 원문 포함)은 제목으로 쓰지 않고 정해진 기본값 「내 여행」을 둔다(확인 화면에서 고친다).
"""
from __future__ import annotations

from datetime import date

import pytest

from app.domains.travel_ops.components.intake import test_plans
from app.domains.travel_ops.components.intake.assemble import _title


def _prepared(name: str) -> str:
    """시험 원문(`test_plans`)에서 이름으로 찾은 원문 — 날짜는 고정한다."""
    numbers = [n for n in range(1, test_plans.TOTAL + 1)
               if test_plans.prepared(n, today=date(2026, 10, 21))["name"] == name]
    assert len(numbers) == 1, (name, numbers)
    return test_plans.prepared(numbers[0], today=date(2026, 10, 21))["text"]


def test_the_test20_memo_line_is_not_the_trip_title():
    """x600 에서 본 그대로 — 7일 목록 첫날 메모 「도착일이라 가볍게」가 제목이 됐다."""
    text = _prepared("김 · 7일, 하루 두세 곳과 메모")
    assert "도착일이라 가볍게" in text.splitlines()
    assert _title({}, [{"transcript": text}]) == "내 여행"


@pytest.mark.parametrize("text", [
    "10/28(수)\n10:00 경복궁\n비 오면 실내로",                                  # 날짜 머리줄 → 시각 줄 → 메모
    "1일차 10/28(수)\n11:00 북촌한옥마을\n버스 타고 남산으로\n15:00 남산골한옥마을",  # 일차 머리줄 아래 이동 메모
    "10:00 경복궁\n택시 타고 갈게요\n12:30 토속촌삼계탕",                         # 시각 줄로 바로 시작
    "2026-10-28\n09:00 경복궁\n\n2026-10-29\n아침은 숙소에서 늦게 먹고\n11:00 국립중앙박물관",
])
def test_a_line_after_the_plan_began_is_not_the_trip_title(text):
    assert _title({}, [{"transcript": text}]) == "내 여행"


@pytest.mark.parametrize("text, title", [
    ("서울 가족여행\n10/28(수)\n10:00 경복궁\n비 오면 실내로", "서울 가족여행"),  # 머리에 적은 제목은 그대로
    ("10월 5일 서울 가족여행\n09:00 경복궁\n도착일이라 가볍게", "10월 5일 서울 가족여행"),
    ("경복궁 갔다가 광장시장\n인사동", "경복궁 갔다가 광장시장"),                 # 규칙이 읽은 일정 줄이 없는 글은 지금과 같다
])
def test_a_title_written_before_the_plan_is_still_used(text, title):
    assert _title({}, [{"transcript": text}]) == title


def test_a_heading_title_in_a_prepared_plan_is_kept():
    """일차 묶음 시험 원문은 머리에 「서울 N일 여행 · 4명」이 있다 — 그 줄이 제목이다."""
    assert _title({}, [{"transcript": _prepared("서울 2일 기본 일정")}]) == "서울 2일 여행 · 4명"


@pytest.mark.parametrize("text", [
    "경복궁 → 북촌 → 인사동\n도착일이라 가볍게",          # 시각 없는 화살표 나열도 규칙이 일정 항목으로 읽은 줄
    "10/28 경복궁 → 북촌\n비 오면 실내로",                # 날짜 머리줄에 일정 항목이 같이 있으면 본문 줄
])
def test_a_line_read_as_schedule_items_is_not_the_trip_title(text):
    assert _title({}, [{"transcript": text}]) == "내 여행"


def test_a_title_before_the_trip_size_line_is_still_used():
    """인원 · 박일 줄은 여행 전체 정보다 — 일정 본문의 시작으로 세지 않는다."""
    assert _title({}, [{"transcript": "서울 가족여행\n4명 2박3일\n10/28(수)\n10:00 경복궁"}]) == "서울 가족여행"


def test_a_later_source_does_not_give_a_title_after_the_plan_began():
    """여러 원문은 차례로 이어 읽는다 — 앞 원문에서 일정이 시작됐으면 뒤 원문의 메모도 제목이 아니다."""
    sources = [{"transcript": "10/28(수)\n10:00 경복궁"}, {"transcript": "도착일이라 가볍게\n15:00 남산골한옥마을"}]
    assert _title({}, sources) == "내 여행"


def test_the_reader_title_still_wins():
    assert _title({"title": {"value": "서울 7일"}}, [{"transcript": _prepared("김 · 7일, 하루 두세 곳과 메모")}]) == "서울 7일"
