# -*- coding: utf-8 -*-
"""role-activity 의 재난문자 자치구 판정(`disaster_msg_a.py`) 시험. `[2026-10-08]`

develop 은 좌표 상자 판정(`near` · `_lat_lon_to_gu`)을 없애고 장소의 구(`district`)를 받아 거른다 —
develop 판은 `test_disaster_msg.py` 가 본다. 이 파일은 병합 때 `_a` 로 보존한 우리 판을 본다.
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.ports.data_sources.disaster_msg_a import DisasterMsgCsv

from .test_disaster_msg import ROWS, _at, _csv


@pytest.fixture()
def source(tmp_path):
    return DisasterMsgCsv(_csv(tmp_path, *ROWS))
# ── 자치구 정하기 `[2026-10-07]` ─────────────────────────────────
from app.domains.travel_ops.ports.data_sources.disaster_msg_a import seoul_districts  # noqa: E402

#: 경희궁(종로구 새문안로 45) — 좌표가 서대문구·종로구 상자에 함께 들어 예전에는 서대문구로 정했다
GYEONGHUI = (37.5703879399457, 126.968491756842, "서울특별시 종로구 새문안로 45")


def test_the_address_decides_the_district():
    assert seoul_districts(*GYEONGHUI) == (["종로구"], "address")
    assert seoul_districts(None, None, "서울 중구 세종대로 110") == (["중구"], "address")
    assert seoul_districts(None, None, "서울특별시 구로구 경인로 662") == (["구로구"], "address")


def test_without_an_address_overlapping_boxes_are_all_kept():
    """★상자가 겹치면 한쪽을 고르지 않는다 — 진짜 구의 위급재난을 놓치지 않게."""
    districts, basis = seoul_districts(GYEONGHUI[0], GYEONGHUI[1])
    assert basis == "box_ambiguous" and set(districts) == {"서대문구", "종로구"}


def test_unknown_address_and_no_box_means_the_whole_city():
    assert seoul_districts(None, None, "부산광역시 해운대구 우동") == (None, "none")
    assert seoul_districts(35.16, 129.16) == (None, "none")


def test_a_district_list_matches_any_of_them(source):
    result = source.active(region="서울", at=_at(16, 0), district=["종로구", "강남구"])
    assert "교통통제" in [m["kind"] for m in result["for_region"]]


def test_near_uses_the_address_and_says_how(source):
    result = source.near(GYEONGHUI[0], GYEONGHUI[1], at=_at(16, 0), address=GYEONGHUI[2])
    assert result["district"] == "종로구" and result["district_basis"] == "address"
