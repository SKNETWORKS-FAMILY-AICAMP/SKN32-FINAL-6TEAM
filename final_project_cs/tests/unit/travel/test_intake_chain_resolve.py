# -*- coding: utf-8 -*-
"""접수의 체인점 지점 고르기 연결(`intake/places._chain_branch` · `pipeline._remember_cluster`). 카카오는 지은 가짜다."""
from __future__ import annotations

from app.modules.travel_ops.intake.places import resolve
from app.modules.travel_ops.intake.pipeline import _remember, _remember_cluster

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


def test_romanized_chain_searches_by_relevance_first():
    kakao = FakeKakao()
    found = _resolve("Starbucks", near=GYEONGBOK, kakao=kakao)
    assert kakao.calls[0]["anywhere"] is True and found.name == "스타벅스 적선점"


class Ctx:
    def __init__(self):
        self.points = []

    def add(self, lat, lon):
        self.points.append((lat, lon))


class Found:
    def __init__(self, status, method=None, lat=None, lon=None, candidates=()):
        self.status, self.method, self.latitude, self.longitude = status, method, lat, lon
        self.candidates = list(candidates)


def test_places_and_kakao_hits_feed_the_near_hint():
    ctx = Ctx()
    _remember(ctx, Found("resolved", "places", 37.5788, 126.977))
    _remember(ctx, Found("resolved", "tour_api", 37.0, 127.0))           # 관광지 CSV 는 스스로 넣는다 — 두 번 넣지 않는다
    assert ctx.points == [(37.5788, 126.977)]


def test_clustered_candidates_feed_their_centre_even_with_one_outlier():
    """홍대입구역 — 노선별 역 셋은 붙어 있고 「사거리」 하나가 조금 떨어졌다(서로 가장 먼 거리 555m). 1위 근처가 절반 넘게 모였다."""
    ctx = Ctx()
    stations = [hit("홍대입구역 2호선", 37.5569, 126.9238), hit("홍대입구역 공항철도", 37.5573, 126.9270),
                hit("홍대입구역 경의중앙선", 37.5574, 126.9271), hit("홍대입구역사거리", 37.5552, 126.9215)]
    _remember_cluster(ctx, Found("unresolved", candidates=stations))
    assert len(ctx.points) == 1 and abs(ctx.points[0][0] - 37.557) < 0.001
    scattered = [hit("a", 37.50, 126.90), hit("b", 37.60, 127.10), hit("c", 37.55, 127.00)]
    _remember_cluster(ctx, Found("unresolved", candidates=scattered))
    assert len(ctx.points) == 1                                          # 흩어져 있으면 넣지 않는다
