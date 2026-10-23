# -*- coding: utf-8 -*-
"""**활동 팀 흐름 전체**에서 「이미 일정에 있는 장소를 이름만 다르게 또 추천하지 않는다」를 본다. `[2026-10-20]`

경복궁이 휴무인 날 대체 장소를 추천하는 흐름(`ActivityTeam.execute` → `read.itinerary` → `_drop_same_places` → 순위)을 가짜 도구로 끝까지 돌린다.
같은 장소 판정의 규칙 하나하나는 `test_activity_place_identity.py` · `test_activity_place_aliases.py`, 이 파일은 **흐름이 이어지는지**를 본다.

시나리오: 일정에 이미 들어 있는 장소 이름을 바꿔 가며, 원장 후보 「남산서울타워」(contentid 126535)가 대체 후보에 남는지 · 빠지는지 · 경고가 남는지.
"""
from __future__ import annotations

import pytest

from .test_activity_closed_alternatives import POOL, _row, _run_with_trip, _titles
import tests.unit.travel.activity.test_activity_closed_alternatives as flow

TOWER = _row("126535", "남산서울타워", x=126.9879, y=37.5511)          # 경복궁에서 약 3.7km
LIBRARY = _row("L1", "서울특별시교육청 남산도서관", x=126.9810, y=37.5560)


def _run(item_place: dict, *extra_candidates):
    pool = {**POOL, "candidates": [*POOL["candidates"], *extra_candidates]}
    original = flow.POOL
    flow.POOL = pool                          # `_run_with_trip` 이 이 값을 후보 풀로 읽는다
    try:
        result = _run_with_trip([{"item_id": "i1", "kind": "activity", "title": item_place["name"], "place": item_place}])
    finally:
        flow.POOL = original
    return _titles(result), result.warnings


def _spot(name, x=126.9885, y=37.5513, **extra):
    return {"place_id": "px", "name": name, "longitude": x, "latitude": y, **extra}


@pytest.mark.parametrize("name", ["N서울타워", "남산타워", "엔서울타워", "N 서울 타워"])
def test_an_alias_in_the_plan_keeps_the_same_tower_out_of_the_alternatives(name):
    titles, warnings = _run(_spot(name), TOWER)
    assert "남산서울타워" not in titles and "창덕궁" in titles            # 같은 곳만 빠지고 다른 후보는 그대로
    assert any("같은 장소 1곳을 대체 후보에서 뺐다" in w for w in warnings)


def test_the_alias_works_even_when_the_plan_item_has_no_coordinates():
    titles, _ = _run({"place_id": "px", "name": "N서울타워"}, TOWER)
    assert "남산서울타워" not in titles


def test_a_typo_is_not_an_alias_so_the_candidate_stays_and_is_flagged_as_maybe_the_same():
    titles, warnings = _run(_spot("남산서울타우"), TOWER)               # 오타 — 별칭 목록에 없다
    assert "남산서울타워" in titles
    assert any("같은 장소일 수 있는 후보 1곳" in w for w in warnings)    # 빼지는 않고 흔적을 남긴다


def test_the_same_alias_far_away_is_a_different_place_and_stays_with_a_flag():
    titles, warnings = _run(_spot("N서울타워", x=129.0756, y=35.1796), TOWER)   # 부산의 같은 이름
    assert "남산서울타워" in titles and any("같은 장소일 수 있는 후보 1곳" in w for w in warnings)


def test_a_similar_name_next_door_is_not_removed_it_is_only_flagged():
    titles, warnings = _run(_spot("서울특별시교육청 용산도서관", x=126.9811, y=37.5561), LIBRARY)
    assert "서울특별시교육청 남산도서관" in titles and any("같은 장소일 수 있는" in w for w in warnings)


def test_a_clearly_different_plan_item_changes_nothing():
    titles, warnings = _run(_spot("롯데월드 아쿠아리움", x=127.1, y=37.51), TOWER)
    assert "남산서울타워" in titles and not any("같은 장소" in w for w in warnings)
