# -*- coding: utf-8 -*-
"""CsvPlaceLookup.find() — 지역명 포함 검색 (이름+지역 분리 전략 ③)."""
from __future__ import annotations

import pytest

from app.modules.travel_ops.activity.csv_places import CsvPlaceLookup

_csv = CsvPlaceLookup()


def test_brand_and_district_finds_the_right_branch():
    """'다이소 용산' → '다이소 용산아이파크몰점' (용산이 제목에 포함된 것)."""
    r = _csv.find("다이소 용산")
    assert r is not None and "용산" in r["matched_title"]


def test_plain_brand_defers_without_near():
    """브랜드만 쓰고 near 없으면 None — 다른 장소 확정 후 재시도하도록 미룬다."""
    r = _csv.find("다이소")
    assert r is None

def test_plain_brand_with_near_returns_closest():
    """near 좌표가 있으면 브랜드만으로도 가장 가까운 점포를 반환한다."""
    r = _csv.find("다이소", near=(37.5796, 126.977))  # 경복궁 근처
    assert r is not None


def test_brand_and_district_with_address_match():
    """올리브영 홍대 — 제목에 홍대가 포함된 것을 찾는다."""
    r = _csv.find("올리브영 홍대")
    assert r is not None and "홍대" in r["matched_title"]


def test_unknown_district_returns_none():
    """지역 필터 결과가 0건이면 None을 반환한다 (엉뚱한 곳을 고르지 않는다)."""
    r = _csv.find("다이소 없는구역XYZ")
    assert r is None


def test_near_hint_picks_geographically_closest():
    """near 좌표가 있으면 지역 필터 결과 중 가장 가까운 것을 고른다."""
    # 용산 아이파크몰 근처 좌표 (37.530, 126.964)
    r_near = _csv.find("다이소 용산", near=(37.530, 126.964))
    assert r_near is not None and "용산" in r_near["matched_title"]
