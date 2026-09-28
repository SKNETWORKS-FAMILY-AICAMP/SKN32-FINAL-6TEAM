# -*- coding: utf-8 -*-
"""장소를 바꾸면 바로 앞뒤 이동도 새 장소 기준으로 — 이동 계산기 문제목록(2026-09-29) #44."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.modules.travel_ops.itinerary import Item
from app.modules.travel_ops.itinerary_changes import ItineraryChange
from app.modules.travel_ops.mobility import wiring

KST = timezone(timedelta(hours=9))
T = lambda hm: datetime.fromisoformat(f"2026-10-07T{hm}:00+09:00")  # noqa: E731


def _place(name, lat, lon):
    return {"place_id": str(uuid4()), "name": name, "latitude": lat, "longitude": lon}


def _items():
    p1, p2 = _place("미술관", 37.570, 126.980), _place("옛 식당", 37.575, 126.985)
    act = Item(item_id=uuid4(), seq=1, kind="activity", title="미술관", place_id=None, starts_at=T("10:00"),
               ends_at=T("11:30"), place=p1)
    old_route = {"from": "미술관", "to": "옛 식당", "planned": "subway_1",
                 "options": [{"id": "subway_1", "label": "3호선 경복궁→안국", "eta_min": 8, "uses": ["3호선:경복궁"]}]}
    move = Item(item_id=uuid4(), seq=2, kind="mobility", title="미술관 → 옛 식당", place_id=None,
                starts_at=T("11:40"), ends_at=T("11:48"), detail={"route_def": old_route})
    meal = Item(item_id=uuid4(), seq=3, kind="dining", title="옛 식당 식사", place_id=None, starts_at=T("12:00"),
                ends_at=T("13:00"), place=p2)
    return act, move, meal


def test_44_place_swap_refreshes_the_move_before_it(monkeypatch):
    monkeypatch.setitem(wiring._STATE, "mode", "disabled")
    act, move, meal = _items()
    new_place = _place("새 식당", 37.590, 127.000)          # 약 2.8 km — 도보 상한(1,200 m) 밖
    swapped = meal.replaced_by(place=new_place, title="새 식당 식사")
    swapped.place = new_place
    change = ItineraryChange(reason="customer_report", causes=[], notice={}, replacements={meal.item_id: swapped})
    after = change.new_items([act, move, meal])
    moved = next(i for i in after if i.kind == "mobility")
    assert moved.item_id != move.item_id and moved.replaces_item_id == move.item_id, "이동도 새 버전 항목이 된다"
    route = moved.detail["route_def"]
    assert route["to"] == "새 식당" and all(o["uses"] == [] for o in route["options"]), \
        "옛 식당으로 가던 3호선 경로(uses)를 새 장소의 경로처럼 남기지 않는다"
    assert moved.title == "미술관 → 새 식당"


def test_44_no_place_change_leaves_moves_alone(monkeypatch):
    monkeypatch.setitem(wiring._STATE, "mode", "disabled")
    act, move, meal = _items()
    retimed = meal.replaced_by(place=None, title=meal.title, starts_at=T("12:30"))
    retimed.place = meal.place
    change = ItineraryChange(reason="x", causes=[], notice={}, replacements={meal.item_id: retimed})
    after = change.new_items([act, move, meal])
    assert next(i for i in after if i.kind == "mobility") is move


def test_44_swap_to_a_place_next_door_keeps_the_route(monkeypatch):
    """걸어갈 거리(도보 상한 1,200 m 안)로 바뀌면 같은 역을 쓸 수 있다 — 옛 경로(탈 노선)를 지우지 않는다."""
    monkeypatch.setitem(wiring._STATE, "mode", "disabled")
    act, move, meal = _items()
    near = _place("옆 식당", 37.5755, 126.9855)            # 약 70 m
    swapped = meal.replaced_by(place=near, title="옆 식당 식사")
    swapped.place = near
    change = ItineraryChange(reason="customer_report", causes=[], notice={}, replacements={meal.item_id: swapped})
    after = change.new_items([act, move, meal])
    assert next(i for i in after if i.kind == "mobility") is move
