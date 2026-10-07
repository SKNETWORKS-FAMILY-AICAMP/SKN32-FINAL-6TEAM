# -*- coding: utf-8 -*-
"""대체 식당 — 비슷함(`meal_likeness`)과 동선(`replan.MealRoute`) · 순위. 순수 계산."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.modules.travel_ops import meal_likeness as ml
from app.modules.travel_ops.replan import (ROUTE_TOLERANCE_MIN, WALKABLE_LEG_MIN, Candidate, MealRoute, choose,
                                           dining_candidates)

KST = ZoneInfo("Asia/Seoul")
NOON = datetime(2026, 10, 21, 12, 0, tzinfo=KST)
M_PER_DEG_LNG = 88_000


def shop(key, east_m, *, category=None, cuisine=None, name=None, kind="dining"):
    attributes = {"hours": ["10:00", "22:00"]}
    if category:
        attributes["category"] = category
    if cuisine:
        attributes["cuisine"] = cuisine
    return {"place_id": key, "name": name or key, "kind": kind, "latitude": 37.57,
            "longitude": 126.98 + east_m / M_PER_DEG_LNG, "attributes": attributes}


# ── 비슷함 ──
def test_likeness_grades():
    samgye = shop("토속촌삼계탕", 0, category="한식")
    assert ml.likeness(shop("스타벅스 가나점", 0), shop("스타벅스 다라점", 0)) == ml.BRAND
    assert ml.likeness(samgye, shop("고려삼계탕", 0, category="한식")) == ml.DISH          # 이름의 메뉴 말
    assert ml.likeness(samgye, shop("광화문국밥", 0, category="한식")) == ml.KIND
    assert ml.likeness(samgye, shop("어느 카페", 0, category="카페디저트")) == ml.OTHER
    assert ml.likeness(samgye, shop("어느 식당", 0, category="미상")) == ml.UNKNOWN          # 미상은 모름이다
    assert ml.likeness(shop("이름만", 0), shop("다른 곳", 0, category="한식")) == ml.UNKNOWN


def test_kind_reads_ledger_kakao_and_cuisine():
    assert ml.kind_of(shop("a", 0, category="카페디저트")) == "카페"
    assert ml.kind_of(shop("a", 0, category="음식점 > 한식 > 삼계탕")) == "한식"
    assert ml.dish_of(shop("a", 0, category="음식점 > 한식 > 삼계탕")) == "삼계탕"
    assert ml.kind_of(shop("a", 0, cuisine=["중식", "짬뽕"])) == "중식"
    assert ml.dish_of(shop("평양냉면집", 0)) == "냉면"


# ── 동선 ──
def _cands(original, places, route, minutes=60):
    return dining_candidates(original=original, places=places, arrival=NOON, minutes=minutes, constraints={},
                             radius_m=700, next_start=route.after[1] if route.after else None, route=route)


def test_next_item_later_than_with_original_is_rejected():
    original, nxt = shop("O", 0), shop("N", 1500, kind="activity")
    west, east = shop("W", -200), shop("E", 350)
    route = MealRoute(planned_end=NOON + timedelta(hours=1), after=(nxt, NOON + timedelta(minutes=80)))
    by_key = {c.key: c for c in _cands(original, [original, west, east], route)}
    assert any("늦는다" in why for why in by_key["W"].rejected)
    assert not by_key["E"].rejected and by_key["E"].added_move_min < 0


def test_far_next_item_is_not_judged_by_walking():
    """원래 식당에서 다음 일정이 걸어서 WALKABLE_LEG_MIN 넘게 걸리면 교통을 탄다 — 도보로 탈락시키지 않는다."""
    original, nxt = shop("O", 0), shop("N", 8000, kind="activity")
    route = MealRoute(planned_end=NOON + timedelta(hours=1), after=(nxt, NOON + timedelta(minutes=90)))
    assert WALKABLE_LEG_MIN * 80 < 8000
    assert not _cands(original, [original, shop("W", -300)], route)[0].rejected


def test_previous_item_only_ranks_never_rejects():
    """앞 활동 13:00 끝 · 점심 13:00 처럼 원래 식당도 몇 분 늦는 계획 — 후보를 탈락시키지 않는다(새벽 확인 시험)."""
    original, prev = shop("O", 0), shop("P", -600, kind="activity")
    route = MealRoute(planned_end=NOON + timedelta(hours=1), before=(prev, NOON))
    got = {c.key: c for c in _cands(original, [original, shop("W", -200), shop("E", 300)], route)}
    assert not got["W"].rejected and not got["E"].rejected
    assert got["W"].added_move_min < got["E"].added_move_min


# ── 먼 다음 일정 — 이동 계산기로 다시 잰다 ──
def _transit(etas, calls=None):
    """가짜 이동 계산기 — 출발 장소 이름별 소요(분). 이름이 없으면 못 잼(None)."""
    def leg(a, b, arrive, leave):
        if calls is not None:
            calls.append(a["name"])
        if a["name"] == "boom":
            raise RuntimeError("계산기 장애")
        eta = etas.get(a["name"])
        if eta is None:
            return None, {"code": "no_route"}
        if leave + timedelta(minutes=eta) > arrive:              # 진짜 계산기처럼 — 제시간에 못 닿으면 소요 대신 「늦음」
            return None, {"code": "arrive_late"}
        return {"eta_min": eta}, None
    return leg


def test_far_next_item_uses_the_transit_engine_over_walking_guess():
    """도보로는 서쪽이 더 가깝지만 시간표로는 동쪽(역 앞)이 빠르다 — 계산기를 따른다. 원래보다 늦게 닿는 곳은 탈락."""
    original, nxt = shop("O", 0), shop("N", -8000, kind="activity")
    west, east = shop("W", -300), shop("E", 300)
    starts = NOON + timedelta(hours=1, minutes=45)            # 식사 13:00 끝 · 다음 13:45 — 원래 식당 40분이면 닿는다
    route = MealRoute(planned_end=NOON + timedelta(hours=1), after=(nxt, starts),
                      leg=_transit({"O": 40, "W": 55, "E": 32}))
    got = {c.key: c for c in _cands(original, [original, west, east], route)}
    assert any("이동 계산기" in why for why in got["W"].rejected)            # 13:55 — 원래(13:40)보다 늦다
    assert not got["E"].rejected and got["E"].added_move_min < 0
    assert choose(list(got.values()))[0].key == "E"


def test_transit_engine_only_for_top_candidates_and_failures_keep_walking():
    original, nxt = shop("O", 0), shop("N", 8000, kind="activity")
    calls: list[str] = []
    places = [original, *[shop(f"S{i}", 50 * (i + 1)) for i in range(6)], shop("boom", 20)]
    route = MealRoute(planned_end=NOON + timedelta(hours=1), after=(nxt, NOON + timedelta(hours=2)),
                      leg=_transit({"O": 40}, calls))
    got = _cands(original, places, route)
    assert calls[0] == "O" and len(calls) == 1 + 3           # 원래 식당 + 도보 어림 앞 3곳만(TRANSIT_REFINE_LIMIT)
    assert not any(c.rejected for c in got)                  # 못 재거나 장애면 도보 어림 그대로 — 탈락시키지 않는다


def test_no_engine_or_walkable_leg_never_calls_transit():
    calls: list[str] = []
    original = shop("O", 0)
    near = MealRoute(planned_end=NOON + timedelta(hours=1), after=(shop("N", 500, kind="activity"),
                     NOON + timedelta(hours=2)), leg=_transit({"O": 5}, calls))
    _cands(original, [original, shop("A", 100)], near)
    assert calls == []                                        # 걸어서 닿는 구간은 도보로 이미 쟀다


# ── 순위 ──
def test_rank_tolerance_then_likeness_then_move():
    near_other = Candidate(key="a", place={"name": "a"}, changed_items=1, extra_cost_krw=None, shift_minutes=0,
                           likeness=ml.OTHER, added_move_min=0, walk_min=2)
    similar = Candidate(key="b", place={"name": "b"}, changed_items=1, extra_cost_krw=None, shift_minutes=0,
                        likeness=ml.DISH, added_move_min=ROUTE_TOLERANCE_MIN, walk_min=6)
    too_far = Candidate(key="c", place={"name": "c"}, changed_items=1, extra_cost_krw=None, shift_minutes=0,
                        likeness=ml.BRAND, added_move_min=ROUTE_TOLERANCE_MIN + 1, walk_min=8)
    best, alternates, _ = choose([too_far, near_other, similar])
    assert best.key == "b"                                  # 허용 범위 안에서 가장 비슷한 곳
    assert [c.key for c in alternates] == ["a", "c"]        # 범위를 넘으면 브랜드여도 뒤


def test_non_dining_candidates_keep_old_order():
    a = Candidate(key="b", place=None, changed_items=1, extra_cost_krw=100, shift_minutes=0)
    b = Candidate(key="a", place=None, changed_items=1, extra_cost_krw=200, shift_minutes=0)
    assert choose([b, a])[0].key == "b"                     # 비용이 먼저 — 새 칸은 모두 0
