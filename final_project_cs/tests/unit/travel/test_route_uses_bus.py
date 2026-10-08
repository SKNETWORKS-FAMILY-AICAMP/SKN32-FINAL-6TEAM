# -*- coding: utf-8 -*-
"""`버스:<노선명>` 표기 — 서울시 노선 API 의 노선명 그대로 받는다. `[2026-09-28]`

☆Mobility 쪽 보고: 실제 서울 시내버스 노선 59개(투어버스 제외)가 거절됐고, 거절된 버스 후보는 **오류 없이 빠진 채**
  왔다 — 남산 순환 01A·01B 가 대안에서 조용히 사라졌다. 보고된 네 모양을 그대로 고정한다.
★정류장·동네 이름은 여전히 거절한다 — 사건 대조가 노선 단위라서다(`route_uses.py` 머리).
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components.itinerary.route_uses import problem

A_OR_B = ["01A", "01B", "702A", "702B", "750A", "750B", "2312A", "2312B", "6640A", "6640B",
          "7013A", "7013B", "6705A"]                                                        # 13
A_OR_B_WITH_PLACE = ["110A고려대", "110B국민대", "5522A난곡", "5522B호암"]                  # 4
COMMUTE = ([f"서울{n:02d}{kind}" for n in range(1, 11) for kind in ("출근", "퇴근")]           # 20
           + [f"{n}{kind}" for n in (8442, 8762, 8773, 8775) for kind in ("출근", "퇴근")])  # 8
AREA = ["청계A01", "동대문A01", "동작A01", "서대문A01", "상암A21", "새벽A148", "새벽A160", "새벽A504",
        "새벽A741", "심야A21", "서대문02대", "서대문02소", "서대문09대", "서대문09소"]          # 14
REPORTED = A_OR_B + A_OR_B_WITH_PLACE + COMMUTE + AREA
EARLIER = ["2224", "N26", "M7106", "9401-1", "성동10", "7022", "2016"]


def test_the_reported_count_is_fifty_nine():
    assert len(REPORTED) == len(set(REPORTED)) == 59


@pytest.mark.parametrize("name", REPORTED + EARLIER)
def test_real_seoul_route_names_are_accepted(name):
    assert problem(f"버스:{name}") is None


@pytest.mark.parametrize("name", ["성수동", "강남역", "2224번", "A01", "2224고려대", "01C", "서울출근", "버스정류장"])
def test_stop_or_place_names_and_other_shapes_are_still_refused(name):
    reason = problem(f"버스:{name}")
    assert reason is not None and "노선" in reason
