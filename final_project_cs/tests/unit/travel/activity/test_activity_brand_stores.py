# -*- coding: utf-8 -*-
"""브랜드 매장(올리브영·다이소·아트박스·무신사) — 대체 후보에서 같은 브랜드의 가까운 매장을 앞세우고, 같은 브랜드는 한 곳만 보인다. `[2026-10-05]`

출처: 활동 팀(조직 develop `alternatives.same_brand_nearby` · `one_per_brand`). 다른 점 — 팀은 후보 풀을 CSV·카탈로그에서 거르는 쪽이고,
우리는 일정 항목의 대체 후보(`activity_candidates` → `choose`)라 **순위 한 칸**(`Candidate.brand_nearby`)과 **같은 곳 판정**
(`_same_activity_site`)으로 넣었다. 구(시군구)가 아니라 **거리 1km** 로 잰다(팀이 10/2 에 시군구를 반경으로 바꾼 이유 — 경계 문제).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import partial
from zoneinfo import ZoneInfo

from app.domains.travel_ops.instances.activity.similarity import score
from app.domains.travel_ops.components.itinerary.itinerary_changes import _same_activity_site
from app.domains.travel_ops.components.planning.replan import BRAND_NEARBY_M, activity_candidates, brand_of, choose, same_brand_nearby

AT = datetime(2026, 10, 7, 14, tzinfo=ZoneInfo("Asia/Seoul"))
SHOP = {"lcls1": "SH", "lcls2": "SH04", "lcls3": "SH040100", "sigungu": "1"}


def _place(pid, lat, lon, brand=None, cls=None):
    cls = {**(cls or SHOP), **({"brand": brand} if brand else {})}
    return {"place_id": pid, "name": pid, "kind": "activity", "latitude": lat, "longitude": lon,
            "catalog_class": cls, "weather_sensitive": False,
            "attributes": {"price_krw": 5_000, "hours": ["09:00", "22:00"]}}


ORIGIN = _place("origin", 37.5600, 126.9850, brand="올리브영")


def _order(places, **kwargs):
    out = activity_candidates(original=ORIGIN, places=places, start=AT, end=AT + timedelta(hours=1), causes=[],
                              similarity=partial(score, preference="activity"), radius_m=5_000, **kwargs)
    best, alternates, rejected = choose(out, None, distinct=_same_activity_site)
    return [c.key for c in ([best] if best else []) + alternates], rejected


def test_brand_helpers_never_treat_unknown_as_the_same():
    assert brand_of(None) == "" and brand_of({"catalog_class": None}) == ""
    assert same_brand_nearby(ORIGIN, _place("a", 37.5601, 126.9850, "올리브영"), 100) is True
    assert same_brand_nearby(ORIGIN, _place("a", 37.5601, 126.9850, "다이소"), 100) is False
    assert same_brand_nearby(ORIGIN, _place("a", 37.5601, 126.9850), 100) is False               # 후보 브랜드를 모른다
    assert same_brand_nearby(_place("o", 37.56, 126.98), _place("a", 37.5601, 126.985, "올리브영"), 100) is False  # 원래 장소가 모른다
    assert same_brand_nearby(ORIGIN, _place("a", 37.57, 126.985, "올리브영"), BRAND_NEARBY_M + 1) is False   # 1km 밖


def test_the_same_brand_within_a_kilometre_beats_a_closer_other_shop():
    near_other = _place("near_other", 37.5602, 126.9850, "다이소")              # 약 22m, 같은 분류·다른 브랜드
    same_brand = _place("same_brand", 37.5650, 126.9850, "올리브영")             # 약 556m
    order, _ = _order([near_other, same_brand])
    assert order[0] == "same_brand"


def test_a_same_brand_shop_beyond_a_kilometre_does_not_jump_the_queue():
    near_other = _place("near_other", 37.5602, 126.9850, "다이소")
    far_brand = _place("far_brand", 37.5800, 126.9850, "올리브영")               # 약 2.2km
    order, _ = _order([near_other, far_brand])
    assert order[0] == "near_other"        # 더 가까운 다른 매장이 낫다 — 같은 브랜드라고 먼 곳을 앞세우지 않는다


def test_only_the_nearest_shop_of_a_brand_is_offered():
    shops = [_place(f"oy{i}", 37.5600 + 0.0006 * (i + 1), 126.9850, "올리브영") for i in range(3)]
    other = _place("other", 37.5640, 126.9850, "다이소")
    order, _ = _order([*shops, other])
    assert [k for k in order if k.startswith("oy")] == ["oy0"]       # 올리브영은 가장 가까운 하나만
    assert "other" in order                                          # 자리를 비워 다른 브랜드가 들어온다


def test_places_without_a_brand_are_not_merged_with_each_other():
    plain = [_place(f"p{i}", 37.5600 + 0.0006 * (i + 1), 126.9850) for i in range(3)]
    order, _ = _order(plain)
    assert sorted(order) == ["p0", "p1", "p2"]            # 브랜드를 모르면 같은 곳으로 묶지 않는다


def test_distinct_treats_two_shops_of_a_brand_as_one():
    a = type("C", (), {"place": _place("a", 37.5600, 126.9850, "아트박스")})
    b = type("C", (), {"place": _place("b", 37.5650, 126.9900, "아트박스")})     # 같은 브랜드 · 다른 곳
    c = type("C", (), {"place": _place("c", 37.5700, 126.9951, "무신사")})   # 다른 브랜드 · 멀리(같은 장소 규칙에도 안 걸린다)
    assert _same_activity_site(a, b) is True
    assert _same_activity_site(a, c) is False
