"""운영시간 규칙 읽기 — 「평일·금·토·일·휴일 A ~ B」(모든 요일 묶음 + 휴일이 같은 시간)는 매일 A~B 다. `[2026-10-27 장소 품질 전수검사]`

☆실측(로컬 acop_cs `activity.ac_place` 읽기 전용): 운영시간 모름 1,873행 중 464행이 이 모양(브랜드 매장 CSV)이었고, 규칙이 「평일」 글자가 있으면
  통째로 거절해 휴무가 단순한(빈 칸 · 연중무휴 · 매주 X요일) 216행까지 모름으로 남았다.
★좁게만 받는다(Codex 검토 Q4): 다섯 묶음이 **모두** 적히고 시간대가 **하나**일 때만. 묶음마다 시간이 다른 원문(「평일·금 A~B / 토·일·휴일 C~D」)과
  휴무가 명절 · 격주 같은 날짜 조건인 원문은 지금처럼 규칙 밖(모델로) — 주간표가 공휴일 · 날짜 조건을 담지 못한다.
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components.places.place_hours import DAYS, read_by_rule


@pytest.mark.parametrize("use", ["평일·금·토·일·휴일 10:30 ~ 22:00", "평일·금·토·일·휴일 10:30~22:00", " 평일 · 금 · 토 · 일 · 휴일  10:30 ~ 22:00 "])
@pytest.mark.parametrize("rest", ["", None, "연중무휴"])
def test_all_day_groups_with_one_range_is_every_day(use, rest):
    read = read_by_rule(use, rest)
    assert read is not None and read.method == "rule"
    assert all(read.week[day] == {"open": "10:30", "close": "22:00", "last_entry": None} for day in DAYS)
    assert read.quotes[0] == " ".join(use.split())             # 인용은 원문 그대로(요일 묶음 포함, 공백만 정리)


def test_all_day_groups_keep_a_weekly_closed_day():
    read = read_by_rule("평일·금·토·일·휴일 10:00 ~ 22:30", "매주 월요일")
    assert read.week["mon"] == "closed" and read.week["tue"]["close"] == "22:30"


@pytest.mark.parametrize("use,rest", [
    ("평일·금 10:00 ~ 22:00 / 토·일·휴일 10:00 ~ 23:00", ""),     # 묶음마다 시간이 다르다 — 범위 밖(모델로)
    ("평일·금·토·일 10:00 ~ 22:00", ""),                        # 휴일이 빠졌다 — 공휴일 시간을 모른다
    ("평일·토·일·휴일 10:00 ~ 22:00", ""),                       # 금이 빠졌다
    ("평일·금·토·일·휴일 10:00 ~ 22:00", "명절 당일 휴무"),        # 날짜 조건 휴무 — 주간표에 못 담는다
    ("평일·금·토·일·휴일 10:00 ~ 22:00", "2,4주 일요일"),
    ("평일 10:00~22:00", ""),                                   # 평일만 — 주말을 모른다
])
def test_other_group_shapes_stay_outside_the_rule(use, rest):
    assert read_by_rule(use, rest) is None
