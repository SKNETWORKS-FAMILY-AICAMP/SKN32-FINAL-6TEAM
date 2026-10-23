# -*- coding: utf-8 -*-
"""CsvPlaceLookup.find() — 지역명 포함 검색 (이름+지역 분리 전략 ③)."""
from __future__ import annotations

from app.domains.travel_ops.instances.activity.csv_places import CsvPlaceLookup

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


def test_swapped_word_order_finds_same_place():
    """'명동 올리브영 타운' = '올리브영 명동 타운' — 어순만 다르면 같은 장소, 확인 필요로 낸다."""
    r = _csv.find("명동 올리브영 타운", fuzzy=True)
    assert r is not None and r["matched_title"] == "올리브영 명동 타운" and r["needs_review"] is True


def test_typo_finds_unique_title_with_review():
    """자모 거리 비율 0.2 이하인 제목이 하나면 오타로 고쳐 찾는다."""
    r = _csv.find("남산서울타우", fuzzy=True)
    assert r is not None and r["matched_title"] == "남산서울타워" and r["needs_review"] is True


def test_exact_match_is_not_marked_for_review():
    """정확히 같은 이름은 확인 필요를 붙이지 않는다."""
    r = _csv.find("남산서울타워")
    assert r is not None and "needs_review" not in r


def test_unrelated_name_still_not_found():
    """이름이 비슷하지도 않으면 억지로 고르지 않는다."""
    assert _csv.find("없는곳테스트장소", fuzzy=True) is None


def test_fuzzy_is_off_by_default():
    """★기본은 정확·접두사·이름+지역만 — 어순·오타 매칭은 호출하는 쪽이 켤 때만(판정 쪽이 짐작한 장소를 읽지 않게)."""
    assert _csv.find("남산서울타우") is None
    assert _csv.find("명동 올리브영 타운") is None
