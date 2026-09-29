# -*- coding: utf-8 -*-
"""「다른 데로 바꿔 줘」 — 후보를 **실제로 다 뒤져도** 없을 때만 「없어요」, 그 이유를 싣는다. `[2026-09-29]`"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.modules.travel_ops.itinerary import Item
from app.modules.travel_ops.itinerary_changes import NoChange, plan_fresh_alternate

KST = ZoneInfo("Asia/Seoul")


def _place(name, kind, lat, lon, hours=("09:00", "22:00")):
    return {"place_id": uuid4(), "name": name, "kind": kind, "latitude": lat, "longitude": lon,
            "attributes": {"hours": list(hours), "payment": ["card", "cash"]}}


def _item(place, hour):
    return Item(item_id=uuid4(), seq=1, kind=place["kind"], title=f"{place['name']} 식사", place_id=place["place_id"],
                starts_at=datetime(2030, 1, 1, hour, tzinfo=KST), ends_at=datetime(2030, 1, 1, hour + 1, tzinfo=KST),
                place=place)


def _plan(item, places):
    return plan_fresh_alternate(trip={"constraints": {}}, trip_version=1, base_version=1, items=[item], places=places,
                                item_id=item.item_id, message="다른 데로 바꿔 줘", request_id="r1")


def test_a_nearby_open_place_is_chosen_and_the_rest_become_other_options():
    home = _place("원래 식당", "dining", 37.5700, 126.9800)
    near_a = _place("가까운 식당", "dining", 37.5705, 126.9805)
    near_b = _place("조금 먼 식당", "dining", 37.5712, 126.9812)
    plan = _plan(_item(home, 12), [home, near_a, near_b])
    assert not isinstance(plan, NoChange), plan
    assert plan.summary["to"] == "가까운 식당" and plan.notice["other_options"] == ["조금 먼 식당"]


def test_no_alternate_only_when_nothing_fits_and_it_says_why():
    home = _place("원래 식당", "dining", 37.5700, 126.9800)
    closed = _place("그 시각 닫는 식당", "dining", 37.5705, 126.9805, hours=("17:00", "22:00"))
    far = _place("먼 식당", "dining", 37.6500, 127.0800)
    plan = _plan(_item(home, 12), [home, closed, far])
    assert isinstance(plan, NoChange) and plan.status == "no_alternate"
    assert plan.detail["rejected"], plan.detail                          # 무엇이 왜 떨어졌는지


def test_a_replacement_never_repeats_a_place_already_in_the_trip():
    """`[2026-09-29 ui 세션 지적]` 점심을 바꿨더니 같은 날 저녁 식당이 골라져 하루에 같은 곳이 두 번 들어갔다.
    일정 짜기와 같게 여행 전체에서 이미 쓴 곳은 뺀다 — 다른 장소 행이어도 **이름이 같으면** 같은 곳이다."""
    home = _place("원래 식당", "dining", 37.5700, 126.9800)
    dinner_spot = _place("저녁 식당", "dining", 37.5705, 126.9805)          # 가장 가깝다 — 전에는 이게 골라졌다
    same_name_row = {**_place("저녁 식당", "dining", 37.5706, 126.9806)}     # 같은 가게의 다른 장소 행
    other = _place("다른 식당", "dining", 37.5712, 126.9812)
    lunch, dinner = _item(home, 12), _item(dinner_spot, 18)
    dinner = replace(dinner, seq=2)
    plan = plan_fresh_alternate(trip={"constraints": {}}, trip_version=1, base_version=1, items=[lunch, dinner],
                                places=[home, dinner_spot, same_name_row, other], item_id=lunch.item_id,
                                message="다른 데로 바꿔 줘", request_id="r2")
    assert not isinstance(plan, NoChange), plan
    assert plan.summary["to"] == "다른 식당" and "저녁 식당" not in plan.notice["other_options"]


def test_when_nothing_is_near_it_widens_the_search_before_saying_no():
    """`[2026-09-29 ui 세션 지적]` 700m 안에 0곳이면 1.5km · 3km 로 넓혀 다시 찾는다(08:00 아침이 「없어요」로 끝났다)."""
    home = _place("원래 식당", "dining", 37.5700, 126.9800)
    two_km = _place("2km 식당", "dining", 37.5880, 126.9800)
    plan = _plan(_item(home, 12), [home, two_km])
    assert not isinstance(plan, NoChange), plan
    assert plan.summary["to"] == "2km 식당"


def test_saying_no_names_the_time_the_distance_and_the_main_reason():
    home = _place("원래 식당", "dining", 37.5700, 126.9800)
    closed = _place("아침엔 닫는 식당", "dining", 37.5705, 126.9805, hours=("11:00", "22:00"))
    plan = _plan(_item(home, 8), [home, closed])
    assert isinstance(plan, NoChange) and plan.status == "no_alternate"
    assert "08:00" in plan.detail["text"] and "3km" in plan.detail["text"], plan.detail
    assert "살펴본 1곳 중 1곳은" in plan.detail["text"] and plan.detail["radius_m"] == 3000
