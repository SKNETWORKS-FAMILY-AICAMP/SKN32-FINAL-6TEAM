# -*- coding: utf-8 -*-
"""`[2026-10-26 x600 c34bd376]` 활동 「다른 곳으로 바꿔줘」 — 쇼핑이 아닌 활동의 다른 안을 상점(관광공사 종류 38 · 분류 SH)으로 채우지 않는다.

x600 증거: 국립중앙박물관(14) → 다른 안 CU 중앙박물관점 · 올리브영 동부이촌점 · 정관장 동부이촌점(모두 38 / SH04).
분류 코드만 본다(이름 낱말을 보지 않는다).
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.itinerary.itinerary_changes import (
    NoChange, is_shopping, plan_fresh_alternate, same_family)

KST = ZoneInfo("Asia/Seoul")


def spot(name, lat, lon, content_type=None, lcls1=None, **attrs):
    attributes = {"hours": ["08:00", "21:00"], **({"source_content_type_id": content_type} if content_type else {}), **attrs}
    return {"place_id": uuid4(), "name": name, "kind": "activity", "latitude": lat, "longitude": lon,
            "attributes": attributes, **({"catalog_class": {"lcls1": lcls1}} if lcls1 else {})}


def plan_for(original, places):
    current = Item(item_id=uuid4(), seq=1, kind="activity", title=original["name"], place_id=original["place_id"],
                   starts_at=datetime(2030, 1, 1, 15, tzinfo=KST), ends_at=datetime(2030, 1, 1, 16, tzinfo=KST),
                   place=original)
    return plan_fresh_alternate(trip={"constraints": {}}, trip_version=1, base_version=1, items=[current],
                                places=[original, *places], item_id=current.item_id, message="다른 곳으로 바꿔 줘",
                                request_id="r1")


def museum_area():
    museum = spot("국립중앙박물관", 37.5240, 126.9800, "14", "VE")
    shops = [spot("CU 중앙박물관점", 37.5262, 126.9822, "38", "SH"),
             spot("올리브영 동부이촌점", 37.5224, 126.9784, "38"),
             spot("브랜드 매장", 37.5215, 126.9830, catalog_source="oliveyoung")]
    parks = [spot("용산가족공원", 37.5250, 126.9810, "12", "VE"), spot("이촌한강공원", 37.5200, 126.9750, "12")]
    return museum, shops, parks


def test_museum_alternates_are_not_shops():
    museum, shops, parks = museum_area()
    plan = plan_for(museum, shops + parks)
    assert not isinstance(plan, NoChange), plan
    shown = [plan.summary["to"], *plan.notice["other_options"]]
    assert set(shown) <= {p["name"] for p in parks} and not set(shown) & {s["name"] for s in shops}, shown


def test_only_shops_nearby_is_no_alternate_rather_than_a_shop():
    museum, shops, _ = museum_area()
    plan = plan_for(museum, shops)
    assert isinstance(plan, NoChange) and plan.status == "no_alternate", plan


def test_a_shopping_original_may_still_get_shops():
    market = spot("광장시장", 37.5700, 126.9990, "38", "SH")
    other = spot("동대문 상가", 37.5720, 127.0010, "38", "SH")
    plan = plan_for(market, [other])
    assert not isinstance(plan, NoChange) and plan.summary["to"] == "동대문 상가", plan


def test_unknown_original_class_excludes_shops_like_plan_reading_candidates():
    unknown = spot("분류 모르는 곳", 37.5240, 126.9800)
    shop = spot("CU", 37.5242, 126.9802, "38")
    park = spot("공원", 37.5243, 126.9803, "12")
    kept = same_family([unknown, shop, park], unknown)
    assert [p["name"] for p in kept] == ["분류 모르는 곳", "공원"]
    assert (is_shopping(unknown), is_shopping(shop), is_shopping(park)) == (None, True, False)
