# -*- coding: utf-8 -*-
"""식당 대안의 가격 — 구글 `priceRange`(1인당 원 범위) · `priceLevel`(0~4)을 **그때 불러 비교에만 쓰고 버린다**.
`[2026-09-30]` 사용자 결정

★가격을 모른다고 후보를 떨어뜨리지 않는다. 같거나 싼 곳 → 비싼 곳 → 모름 순으로 세운다.
★양쪽에 가격 범위가 있으면 범위 가운데 값(원)으로, 없으면 가격대(0~4)로 잰다.
★원 단위 가격(`price_krw`)이 양쪽에 있으면 지금처럼 원으로 잰다(시나리오가 그렇다).
★구글 값은 저장하지 않는다 — 결정 기록에는 비교 결과(같거나 쌈 · 비쌈 · 모름)만 남는다.
★하루 상한을 걸지 않는다. 월 무료 한도를 넘는 **첫 호출**에 운영자에게 알린다.

    python -m pytest tests/unit/travel/test_dining_price_tier.py -q
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import httpx
import pytest

from app.infrastructure.travel.google_places import METER_DETAILS, GooglePlaces, price_from_details
from app.modules.travel_ops.itinerary import Item
from app.modules.travel_ops.itinerary_changes import NoChange, plan_closed, plan_closed_on_day
from app.modules.travel_ops.replan import Candidate, apply_google_prices

KST = timezone(timedelta(hours=9))
T = lambda hm: datetime.fromisoformat(f"2026-10-07T{hm}:00+09:00")  # noqa: E731


# ── 구글 응답 → 가격 (순수 함수) ───────────────────────────────────
def _won(units):
    return {"currencyCode": "KRW", "units": str(units)}


@pytest.mark.parametrize("payload, expected", [
    ({"priceLevel": "PRICE_LEVEL_FREE"}, 0),
    ({"priceLevel": "PRICE_LEVEL_INEXPENSIVE"}, 1),
    ({"priceLevel": "PRICE_LEVEL_MODERATE"}, 2),
    ({"priceLevel": "PRICE_LEVEL_EXPENSIVE"}, 3),
    ({"priceLevel": "PRICE_LEVEL_VERY_EXPENSIVE"}, 4),
    ({"priceLevel": "PRICE_LEVEL_UNSPECIFIED"}, None),
    ({}, None),                                   # 칸이 없으면 모름 — 싸다고 읽지 않는다
])
def test_price_level_maps_to_a_tier_or_unknown(payload, expected):
    assert price_from_details(payload)["level"] == expected


@pytest.mark.parametrize("price_range, low, high", [
    ({"startPrice": _won(20000), "endPrice": _won(30000)}, 20000, 30000),
    ({"startPrice": _won(100000)}, 100000, None),                     # 상한 없음 = 「10만 원 이상」
    ({"startPrice": {"currencyCode": "USD", "units": "20"}, "endPrice": {"currencyCode": "USD", "units": "30"}},
     None, None),                                                   # 원이 아니면 쓰지 않는다
    ({}, None, None),
])
def test_price_range_is_read_in_won_only(price_range, low, high):
    price = price_from_details({"priceRange": price_range} if price_range else {})
    assert (price["low"], price["high"]) == (low, high)


# ── 어댑터 ───────────────────────────────────────────────────────
def _response(status: int, body) -> httpx.Response:
    return httpx.Response(status, json=body, request=httpx.Request("GET", "https://example.invalid"))


class CountingBudget:
    """세기만 하는 예산 — `count` 가 이번 달 사용량을 돌려준다. `try_reserve` 는 늘 거절(하루 상한이 찬 상태)."""

    def __init__(self, start: int = 0):
        self.month = start

    def count(self, meter, *, free):
        self.month += 1
        return self.month, free is not None and self.month == free + 1

    def try_reserve(self, meter):
        return False


class ClosedLimiter:
    """프로세스 안 하루 제한기가 이미 찬 상태."""

    def acquire(self, *args, **kwargs):
        from app.infrastructure.travel.ratelimit import RateLimited
        raise RateLimited("google_places", 0)


def test_price_level_asks_only_for_the_price_field_and_ignores_the_daily_caps():
    seen = []

    def request(method, url, headers, json):
        seen.append((method, url, headers))
        return _response(200, {"priceLevel": "PRICE_LEVEL_MODERATE",
                               "priceRange": {"startPrice": _won(20000), "endPrice": _won(30000)}})

    places = GooglePlaces(api_key="k", budget=CountingBudget(), request=request, limiter=ClosedLimiter())
    assert places.price("gid-1") == {"level": 2, "low": 20000, "high": 30000}
    method, url, headers = seen[0]
    assert method == "GET" and url.endswith("/places/gid-1")
    assert headers["X-Goog-FieldMask"] == "priceLevel,priceRange", "두 칸을 한 번에 — 영업시간 등 다른 칸은 받지 않는다"
    assert len(seen) == 1


def test_a_failed_price_call_is_unknown_not_cheap():
    places = GooglePlaces(api_key="k", budget=CountingBudget(), request=lambda *a: _response(403, {}))
    assert places.price("gid-1") is None
    assert places.misses["http_403"] == 1


def test_the_first_call_over_the_free_tier_alerts_once():
    alerts = []
    budget = CountingBudget(start=998)            # 무료 1,000 — 999, 1000 은 무료 안, 1001 이 첫 초과
    places = GooglePlaces(api_key="k", budget=budget, free_monthly={METER_DETAILS: 1000},
                          on_over_free=lambda meter, used, free: alerts.append((meter, used, free)),
                          request=lambda *a: _response(200, {"priceLevel": "PRICE_LEVEL_MODERATE"}))
    for _ in range(4):
        places.price("gid")
    assert alerts == [(METER_DETAILS, 1001, 1000)], "넘는 순간 한 번만 알린다"


def test_an_alert_failure_does_not_break_the_lookup():
    def boom(*a):
        raise RuntimeError("webhook down")

    places = GooglePlaces(api_key="k", budget=CountingBudget(start=1000), free_monthly={METER_DETAILS: 1000},
                          on_over_free=boom,
                          request=lambda *a: _response(200, {"priceLevel": "PRICE_LEVEL_EXPENSIVE"}))
    assert places.price("gid")["level"] == 3


# ── 순위 ─────────────────────────────────────────────────────────
def _cand(key: str, price: int | None = None, walk: int = 3) -> Candidate:
    attributes = {} if price is None else {"price_krw": price}
    return Candidate(key=key, place={"place_id": key, "name": key, "attributes": attributes},
                     changed_items=1, extra_cost_krw=None, shift_minutes=0, walk_min=walk)


def L(level):
    """가격대만 있는 구글 가격."""
    return {"level": level, "low": None, "high": None}


def R(low, high=None, level=None):
    """가격 범위가 있는 구글 가격(원)."""
    return {"level": level, "low": low, "high": high}


def _order(cands):
    return [c.key for c in sorted(cands, key=Candidate.rank)]


def test_same_or_cheaper_tier_comes_before_pricier_and_unknown_comes_last():
    original = {"place_id": "orig", "name": "원래"}
    pricey, same, unknown, cheaper = _cand("a"), _cand("b"), _cand("c"), _cand("d")
    prices = {"orig": L(2), "a": L(3), "b": L(2), "d": L(1)}
    apply_google_prices([pricey, same, unknown, cheaper], original=original, lookup=lambda ps: prices)
    order = _order([pricey, same, unknown, cheaper])
    assert order[-2:] == ["a", "c"], "비싼 곳 다음에 모름"
    assert set(order[:2]) == {"b", "d"}
    assert same.price_compare == "same_or_lower" and pricey.price_compare == "higher"
    assert unknown.price_compare == "unknown"
    assert same.price_basis == "level"


def test_ranges_on_both_sides_compare_in_won_by_the_middle_of_the_range():
    """★지도의 「1인당 ₩20,000~30,000」. 가운데 값으로 재고, 같은 쪽 안에서는 차액이 작은 곳이 먼저다."""
    original = {"place_id": "orig", "name": "원래"}
    a, b, c, d = _cand("a"), _cand("b"), _cand("c"), _cand("d")
    prices = {"orig": R(20000, 30000, level=2),
              "a": R(30000, 40000, level=2),        # 가운데 35,000 — 1만 원 비싸다(가격대는 같아도)
              "b": R(10000, 20000, level=2),        # 15,000 — 싸다
              "c": R(20000, 30000, level=2),        # 같다
              "d": R(22000, 33000, level=2)}        # 27,500 — 2,500원 비싸다
    apply_google_prices([a, b, c, d], original=original, lookup=lambda ps: prices)
    assert {x.key: x.price_compare for x in (a, b, c, d)} == {
        "a": "higher", "b": "same_or_lower", "c": "same_or_lower", "d": "higher"}
    assert all(x.price_basis == "range" for x in (a, b, c, d))
    assert _order([a, b, c, d])[2:] == ["d", "a"], "비싼 쪽 안에서는 덜 비싼 곳이 먼저"
    assert d.extra_cost_krw == 2500 and b.extra_cost_krw == 0


def test_an_open_ended_range_uses_its_lower_bound():
    original = {"place_id": "orig", "name": "원래"}
    a = _cand("a")
    apply_google_prices([a], original=original, lookup=lambda ps: {"orig": R(30000, 40000), "a": R(100000)})
    assert a.price_compare == "higher" and a.extra_cost_krw == 65000


def test_a_range_on_one_side_only_falls_back_to_the_level():
    original = {"place_id": "orig", "name": "원래"}
    a = _cand("a")
    apply_google_prices([a], original=original, lookup=lambda ps: {"orig": R(20000, 30000, level=2), "a": L(1)})
    assert (a.price_compare, a.price_basis, a.extra_cost_krw) == ("same_or_lower", "level", None)


def test_without_the_original_price_nothing_can_be_compared():
    original = {"place_id": "orig", "name": "원래"}
    a = _cand("a")
    apply_google_prices([a], original=original, lookup=lambda ps: {"a": L(1)})
    assert a.price_compare == "unknown"


def test_the_lookup_asks_for_the_original_and_at_most_eight_nearest_survivors():
    original = {"place_id": "orig", "name": "원래"}
    cands = [_cand(f"p{i}", walk=i) for i in range(12)]
    cands[0].rejected.append("그 시각 영업하지 않는다")             # 탈락한 후보는 묻지 않는다
    asked = []
    apply_google_prices(cands, original=original, lookup=lambda ps: asked.extend(p["place_id"] for p in ps) or {})
    assert asked[0] == "orig" and len(asked) == 9
    assert "p0" not in asked and asked[1:] == [f"p{i}" for i in range(1, 9)]


def test_a_lookup_that_fails_leaves_the_order_as_it_was():
    a, b = _cand("a", walk=5), _cand("b", walk=2)
    apply_google_prices([a, b], original={"place_id": "o", "name": "o"}, lookup=lambda ps: None)
    assert a.price_compare == "unknown" and a.rank()[:4] == b.rank()[:4]


def test_won_prices_on_both_sides_still_decide_by_won():
    original = {"place_id": "orig", "name": "원래", "attributes": {"price_krw": 15000}}
    a, b = _cand("a", price=18000), _cand("b", price=14000)
    for c in (a, b):
        c.extra_cost_krw = max(0, c.place["attributes"]["price_krw"] - 15000)
        c.price_compare = "won"
    asked = []
    apply_google_prices([a, b], original=original, lookup=lambda ps: asked.append(ps) or {})
    assert asked == [], "원 단위로 이미 잴 수 있으면 구글을 부르지 않는다"
    assert _order([a, b]) == ["b", "a"]


# ── 일정 변경까지 ────────────────────────────────────────────────
def _restaurant(name: str, lat: float, lon: float, **attributes) -> dict:
    return {"place_id": str(uuid4()), "name": name, "kind": "dining", "latitude": lat, "longitude": lon,
            "attributes": {"hours": ["10:00", "22:00"], **attributes}}


def _trip(meal_place: dict):
    meal = Item(item_id=uuid4(), seq=1, kind="dining", title="점심", place_id=None,
                starts_at=T("12:00"), ends_at=T("13:00"), place=meal_place)
    return {"trip_id": str(uuid4()), "version": 1, "constraints": {}}, [meal], meal


def test_a_closed_lunch_is_replaced_even_when_no_price_is_known():
    """★예전에는 가격을 모르면 후보가 전부 탈락해 「해결 못 함」이었다. 실제 식당 데이터에는 가격이 없다."""
    origin = _restaurant("원래 식당", 37.5700, 126.9800)
    near = _restaurant("옆 식당", 37.5705, 126.9805)
    trip, items, _ = _trip(origin)
    plan = plan_closed(trip=trip, items=items, places=[origin, near], at=T("12:00"),
                       message="오늘 쉰대요", request_id="r1")
    assert not isinstance(plan, NoChange), getattr(plan, "detail", None)
    assert plan.summary["to"] == "옆 식당"


def test_a_closed_lunch_prefers_a_place_in_the_same_price_tier():
    origin = _restaurant("원래 식당", 37.5700, 126.9800)
    pricey = _restaurant("비싼 옆집", 37.5701, 126.9801)            # 더 가깝지만 비싸다
    same = _restaurant("같은 급 식당", 37.5706, 126.9806)
    trip, items, _ = _trip(origin)
    prices = {origin["place_id"]: R(20000, 30000, level=2), pricey["place_id"]: R(60000, 80000, level=4),
              same["place_id"]: R(20000, 30000, level=2)}
    plan = plan_closed(trip=trip, items=items, places=[origin, pricey, same], at=T("12:00"),
                       message="오늘 쉰대요", request_id="r1", price_lookup=lambda ps: prices)
    assert plan.summary["to"] == "같은 급 식당"
    assert (plan.summary["price"], plan.summary["price_basis"]) == ("same_or_lower", "range")
    assert "구글" in plan.notice["text"] and "1인당" in plan.notice["text"], "구글 가격으로 골랐으면 추정이라고 밝힌다"
    record = json.dumps({"summary": plan.summary, "notice": plan.notice}, ensure_ascii=False, default=str)
    for raw in ("20000", "20,000", "30000", "30,000", "60000", "PRICE_LEVEL", '"level"', '"low"'):
        assert raw not in record, f"구글 원값({raw})을 기록에 남기지 않는다"


def test_the_dawn_path_uses_the_same_price_order():
    origin = _restaurant("원래 식당", 37.5700, 126.9800)
    pricey = _restaurant("비싼 옆집", 37.5701, 126.9801)
    same = _restaurant("같은 급 식당", 37.5706, 126.9806)
    trip, items, meal = _trip(origin)
    prices = {origin["place_id"]: L(1), pricey["place_id"]: L(3), same["place_id"]: L(1)}
    plan = plan_closed_on_day(trip=trip, items=items, places=[origin, pricey, same], meal=meal,
                              source="google_places", detail="임시 휴업", checked_at=T("03:00"),
                              price_lookup=lambda ps: prices)
    assert plan.summary["to"] == "같은 급 식당"
    assert plan.summary["price_basis"] == "level" and "가격대" in plan.notice["text"]


# ── 웹에 내려가는 것 ─────────────────────────────────────────────
def test_the_chosen_place_and_the_other_options_carry_the_comparison_to_the_web():
    """★`[2026-09-30]` 웹이 「같은 가격대 · 더 비쌈」을 보이게 비교 결과만 내려 준다 — 금액은 싣지 않는다."""
    from app.modules.travel_ops.trip_api import _item_view

    origin = _restaurant("원래 식당", 37.5700, 126.9800)
    same = _restaurant("같은 급 식당", 37.5701, 126.9801)
    pricey = _restaurant("비싼 옆집", 37.5706, 126.9806)
    unknown = _restaurant("모르는 집", 37.5708, 126.9808)
    trip, items, meal = _trip(origin)
    prices = {origin["place_id"]: R(20000, 30000, level=2), same["place_id"]: R(20000, 30000, level=2),
              pricey["place_id"]: R(60000, 80000, level=4)}
    plan = plan_closed(trip=trip, items=items, places=[origin, same, pricey, unknown], at=T("12:00"),
                       message="오늘 쉰대요", request_id="r1", price_lookup=lambda ps: prices)
    replacement = plan.replacements[meal.item_id]
    replacement.place = same
    view = _item_view(replacement)
    assert view["place"] == "같은 급 식당" and view["price_compare"] == "same_or_lower"
    assert {o["name"]: o["price_compare"] for o in view["other_options"]} == {
        "비싼 옆집": "higher", "모르는 집": "unknown"}
    dumped = json.dumps(view, ensure_ascii=False)
    assert "60000" not in dumped and "20000" not in dumped


def test_items_without_a_price_comparison_say_none():
    from app.modules.travel_ops.trip_api import _item_view

    _, _, meal = _trip(_restaurant("원래 식당", 37.57, 126.98))
    view = _item_view(meal)
    assert view["price_compare"] is None and view["other_options"] == []
