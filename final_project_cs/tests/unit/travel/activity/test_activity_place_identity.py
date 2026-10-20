# -*- coding: utf-8 -*-
"""같은 장소 판정(`place_identity`) — 이름이 달라도 같은 곳이면 대체 후보에서 뺀다. `[2026-10-19]`

규칙만 본다(LLM 은 쓰지 않는다 — 지웠다). 별칭이 같다고 정하는 경우는 `test_activity_place_aliases`.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domains.travel_ops.instances.activity import place_aliases as pa
from app.domains.travel_ops.instances.activity import place_identity as pi
from app.domains.travel_ops.instances.activity.replacement import ReplacementMixin

#: 원장의 「서울로봇인공지능과학관」(후보) · 일정의 「서울로봇과학관」 — 이름은 다르고(별칭 없음) 닮았고 약 60m 어긋난다
ROBOT_ROW = {"contentid": "4060676", "title": "서울로봇인공지능과학관", "mapy": "37.5510545", "mapx": "126.9878829", "lclsSystm3": "VE010100"}
PLAN_ROBOT = pi.Spot("서울로봇과학관", 37.5512, 126.9885, None, "관광,명소")
LIBRARY_ROW = {"contentid": "L1", "title": "서울특별시교육청 남산도서관", "mapy": "37.5560", "mapx": "126.9810"}
OTHER_LIBRARY = pi.Spot("서울특별시교육청 용산도서관", 37.5561, 126.9811, None, None)


# ── 규칙 판정 ────────────────────────────────────────────────────

def test_same_content_id_is_same_even_if_names_differ():
    assert pi.verdict(pi.Spot("아무 이름", None, None, "4060676"), pi.spot_of(ROBOT_ROW)) == "same"


def test_equal_normalized_name_is_same_regardless_of_distance():
    assert pi.verdict(pi.Spot("서울 로봇인공지능 과학관", 37.0, 127.0), pi.spot_of(ROBOT_ROW)) == "same"


def test_similar_name_within_300m_is_ambiguous_not_same():
    assert pi.verdict(PLAN_ROBOT, pi.spot_of(ROBOT_ROW)) == "ambiguous"


def test_a_different_library_next_door_is_only_ambiguous_never_auto_same():
    """★이름이 아무리 닮아도(0.92) 규칙이 「같다」고 하지 않는다 — 다른 곳일 수 있다."""
    assert pi.name_similarity(OTHER_LIBRARY.name, LIBRARY_ROW["title"]) > 0.9
    assert pi.verdict(OTHER_LIBRARY, pi.spot_of(LIBRARY_ROW)) == "ambiguous"


def test_far_away_or_without_coordinates_is_different():
    far = pi.Spot("서울로봇과학관", 37.60, 127.05, None, None)
    assert pi.verdict(far, pi.spot_of(ROBOT_ROW)) == "different"
    assert pi.verdict(pi.Spot("서울로봇과학관", None, None), pi.spot_of(ROBOT_ROW)) == "different"


def test_unrelated_names_nearby_are_different():
    assert pi.verdict(pi.Spot("롯데월드 아쿠아리움", 37.5511, 126.9879), pi.spot_of(ROBOT_ROW)) == "different"


def test_short_names_never_count_as_similar():
    assert pi.name_similarity("남산", "서울로봇인공지능과학관") == 0.0


# ── 후보 가르기 ──────────────────────────────────────────────────

def test_split_removes_rule_same_keeps_ambiguous_and_counts_it():
    same = {"contentid": "9", "title": "서울 로봇과학관", "mapy": "37.5512", "mapx": "126.9885"}
    plain = {"contentid": "7", "title": "경복궁", "mapy": "37.5796", "mapx": "126.977"}
    kept, removed, maybe = pi.split([PLAN_ROBOT], [ROBOT_ROW, same, plain])
    assert removed == 1 and maybe == 1
    assert [c["contentid"] for c in kept] == ["4060676", "7"]          # 애매한 후보는 남는다


def test_split_with_no_plan_spots_keeps_everything():
    assert pi.split([], [ROBOT_ROW]) == ([ROBOT_ROW], 0, 0)


# ── 대체 흐름 연결(`ReplacementMixin._drop_same_places`) ─────────

class _Host(ReplacementMixin):
    pass


def _run(rows, spots=(PLAN_ROBOT,), aliases=pa.EMPTY):
    warnings: list[str] = []
    kept = _Host()._drop_same_places(SimpleNamespace(run_id=uuid4()), list(rows), list(spots), warnings, aliases=aliases)
    return kept, warnings


def test_rule_same_candidate_is_removed_with_a_warning():
    kept, warnings = _run([{**ROBOT_ROW, "title": "서울 로봇 과학관"}])
    assert kept == [] and any("같은 장소 1곳" in w for w in warnings)


def test_ambiguous_candidate_stays_and_the_count_is_warned():
    kept, warnings = _run([ROBOT_ROW])
    assert [c["contentid"] for c in kept] == ["4060676"]
    assert any("같은 장소일 수 있는 후보 1곳" in w for w in warnings)


def test_no_in_plan_spots_returns_candidates_untouched():
    kept, warnings = _run([ROBOT_ROW], spots=())
    assert kept == [ROBOT_ROW] and warnings == []


@pytest.mark.parametrize("name", ["N서울타워", "남산타워", "엔서울타워"])
def test_alias_removes_the_candidate_when_the_places_are_near(name):
    row = {"contentid": "126535", "title": "남산서울타워", "mapy": "37.5510", "mapx": "126.9878"}
    table = pa.AliasTable([("남산타워", "126535"), ("N서울타워", "126535"), ("엔서울타워", "126535")])   # 후보 조회가 싣는 별칭 표
    near = (pi.Spot(name, 37.5512, 126.9885, None, None),)
    kept, _ = _run([row], spots=near, aliases=table)
    assert kept == []
    kept, _ = _run([row], spots=near)                                         # 표가 없으면(시드도 안 합치면) 이름이 달라 안 뺀다
    assert [c["contentid"] for c in kept] == ["126535"]


def test_alias_does_not_remove_a_candidate_that_is_far_from_the_plan_item():
    row = {"contentid": "126535", "title": "남산서울타워", "mapy": "37.5510", "mapx": "126.9878"}
    table = pa.AliasTable([("N서울타워", "126535")])
    kept, warnings = _run([row], spots=(pi.Spot("N서울타워", 35.18, 129.08, None, None),), aliases=table)    # 같은 이름의 다른 곳(부산)
    assert [c["contentid"] for c in kept] == ["126535"]
    assert any("같은 장소일 수 있는 후보 1곳" in w for w in warnings)          # 흔적을 남긴다 — 나중에 기준(3km)을 고칠 근거
