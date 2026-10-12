# -*- coding: utf-8 -*-
"""접수의 체인점 지점 고르기 연결(`intake/places._chain_branch` · `pipeline._near_hint` · `_cluster_centre`). 카카오는 지은 가짜다."""
from __future__ import annotations

from app.domains.travel_ops.components.intake.places import resolve
from app.domains.travel_ops.components.intake.pipeline import _cluster_centre, _near_hint

GYEONGBOK = (37.5788, 126.9770)


def hit(name, lat, lng, group="CE7"):
    return {"id": name, "name": name, "category_group": group, "latitude": lat, "longitude": lng,
            "address": "서울 어딘가", "category": ""}


BRANCHES = [hit("스타벅스 더북한산점", 37.6590, 126.9800), hit("스타벅스 적선점", 37.5767, 126.9737),
            hit("스타벅스 강남역신분당역사점", 37.4969, 127.0282)]


class FakeKakao:
    def __init__(self):
        self.calls = []
        self.misses = {}

    def search(self, query, size=5, near=None, radius=None, category_group_code=None, anywhere=False, **kw):
        self.calls.append({"query": query, "near": near, "radius": radius, "group": category_group_code,
                           "anywhere": anywhere})
        if category_group_code == "SW8":
            return [hit("강남역 2호선", 37.4979, 127.0276, "SW8")] if query == "강남역" else []
        if query in ("스타벅스", "Starbucks", "스타벅스 강남역점"):
            return list(BRANCHES)
        return []


def _resolve(title, near=None, kakao=None):
    return resolve(title, our_places=[], kakao=kakao or FakeKakao(), near=near)


def test_chain_with_a_neighbour_picks_the_nearby_branch_for_review():
    found = _resolve("스타벅스", near=GYEONGBOK)
    assert found.status == "resolved" and found.method == "kakao_branch"
    assert found.name == "스타벅스 적선점" and found.needs_review and found.kind == "dining"


def test_chain_without_any_anchor_is_deferred_not_guessed():
    found = _resolve("스타벅스")
    assert found.status == "unresolved" and found.chain_deferred and found.name is None
    assert "어느 지점" in found.note


def test_branch_name_is_located_anywhere_and_beats_the_neighbour():
    kakao = FakeKakao()
    found = _resolve("스타벅스 강남역점", near=GYEONGBOK, kakao=kakao)
    assert found.name == "스타벅스 강남역신분당역사점"
    station = next(c for c in kakao.calls if c["group"] == "SW8")
    assert station["anywhere"] is True                                   # 지점명 위치는 앞 일정 근처가 아니라 서울 전역에서


class RelevanceFirstKakao(FakeKakao):
    """관련도 순 첫 결과에는 1km 안의 먼 지점만 있고, 더 가까운 지점은 근처(거리순) 찾기에만 나온다 — 통합 뒤 실측 모양."""

    def search(self, query, size=5, near=None, radius=None, category_group_code=None, anywhere=False, **kw):
        self.calls.append({"query": query, "near": near, "radius": radius, "group": category_group_code,
                           "anywhere": anywhere})
        if near is None:
            return [hit("스타벅스 종로R점", 37.5713, 126.9790), hit("스타벅스 강남역신분당역사점", 37.4969, 127.0282)]
        return [hit("스타벅스 적선점", 37.5767, 126.9737), hit("스타벅스 종로R점", 37.5713, 126.9790)]


def test_a_branch_within_the_first_radius_still_gets_a_nearby_search():
    """☆2026-10-08 — 관련도 순 결과의 종로R점(앞 일정에서 ~850m)이 1km 안이라 근처를 찾지 않고 골랐다. 가까운 적선점(~400m)을 놓쳤다."""
    kakao = RelevanceFirstKakao()
    found = _resolve("스타벅스", near=GYEONGBOK, kakao=kakao)
    assert found.name == "스타벅스 적선점"
    assert any(c["near"] is not None and c["radius"] == 1000 for c in kakao.calls)


def test_romanized_chain_searches_by_relevance_first():
    kakao = FakeKakao()
    found = _resolve("Starbucks", near=GYEONGBOK, kakao=kakao)
    assert kakao.calls[0]["anywhere"] is True and found.name == "스타벅스 적선점"


class Found:
    def __init__(self, status, method=None, lat=None, lon=None, candidates=()):
        self.status, self.method, self.latitude, self.longitude = status, method, lat, lon
        self.candidates = list(candidates)


class Dated:
    def __init__(self, value):
        self.value = value


def _items(n):
    return [{"title": f"항목{i}"} for i in range(n)]


def test_the_previous_resolved_item_of_the_same_day_is_the_near_hint():
    """★`[2026-10-07]` 우리 접수는 요청 상태 객체 대신 같은 날 앞뒤 항목의 좌표를 기준으로 쓴다(`_neighbours`)."""
    resolved = {0: Found("resolved", "places", 37.5788, 126.977), 2: Found("resolved", "tour_api", 37.0, 127.0)}
    dated = [Dated("2026-10-15")] * 3
    assert _near_hint(1, _items(3), resolved, dated) == (37.5788, 126.977)         # 앞 항목이 먼저
    assert _near_hint(0, _items(3), {2: resolved[2]}, dated) == (37.0, 127.0)       # 앞이 없으면 뒤
    assert _near_hint(1, _items(3), resolved, [Dated("a"), Dated("b"), Dated("b")]) == (37.0, 127.0)   # 다른 날 항목은 보지 않는다
    assert _near_hint(1, _items(3), {}, dated) is None


def test_clustered_candidates_give_their_centre_even_with_one_outlier():
    """홍대입구역 — 노선별 역 셋은 붙어 있고 「사거리」 하나가 조금 떨어졌다(서로 가장 먼 거리 555m). 1위 근처가 절반 넘게 모였다."""
    stations = [hit("홍대입구역 2호선", 37.5569, 126.9238), hit("홍대입구역 공항철도", 37.5573, 126.9270),
                hit("홍대입구역 경의중앙선", 37.5574, 126.9271), hit("홍대입구역사거리", 37.5552, 126.9215)]
    centre = _cluster_centre(Found("unresolved", candidates=stations))
    assert centre is not None and abs(centre[0] - 37.557) < 0.001
    scattered = [hit("a", 37.50, 126.90), hit("b", 37.60, 127.10), hit("c", 37.55, 127.00)]
    assert _cluster_centre(Found("unresolved", candidates=scattered)) is None       # 흩어져 있으면 쓰지 않는다
    # 정하지 못한 항목의 후보 가운데가 다음 항목의 기준이 된다
    assert _near_hint(1, _items(2), {0: Found("unresolved", candidates=stations)}, [Dated("d")] * 2) == centre
