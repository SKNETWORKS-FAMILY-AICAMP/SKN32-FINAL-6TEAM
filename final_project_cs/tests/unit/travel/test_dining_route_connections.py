"""요식업 대체·낮 감시·현재 위치 추천이 앞뒤 일정 이동 시간을 지키는지 검증한다."""
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.itinerary import itinerary_changes as changes
from app.domains.travel_ops.components.team_hooks import legs

NOON = datetime(2030, 10, 9, 12, tzinfo=ZoneInfo("Asia/Seoul"))


def place(name, east, kind="dining"):
    return {"place_id": str(uuid4()), "name": name, "kind": kind, "latitude": 37.57,
            "longitude": 126.98 + east / 88000,
            "attributes": {"hours": ["09:00", "22:00"]}}


def item(spot, seq, start, end):
    return Item(item_id=uuid4(), seq=seq, kind=spot["kind"], title=spot["name"],
                place_id=uuid4(), starts_at=start, ends_at=end, place=spot)


def schedule(next_east=1500, next_min=80):
    before = item(place("앞 엑티비티", -600, "activity"), 1, NOON - timedelta(hours=1), NOON)
    meal = item(place("원래 식당", 0), 2, NOON, NOON + timedelta(hours=1))
    after = item(place("뒤 엑티비티", next_east, "activity"), 3,
                 NOON + timedelta(minutes=next_min), NOON + timedelta(hours=3))
    return before, meal, after


@pytest.mark.parametrize("mode", ["watch", "alternate"])
def test_new_connections_exclude_late_restaurant_and_accept_reachable_one(mode, monkeypatch):
    monkeypatch.setattr(legs, "leg_planner", lambda *args: None)
    before, meal, after = schedule()
    west, east = place("늦는 서쪽 식당", -200), place("닿는 동쪽 식당", 350)
    kwargs = {"trip": {}, "items": [before, meal, after], "places": [meal.place, west, east]}
    if mode == "watch":
        plan = changes.plan_dining_disrupted(**kwargs, meal=meal,
            report={"disruptions": [{"kind": "화재"}]}, check=lambda **args: {"verdict": "clear"})
    else:
        plan = changes.plan_fresh_alternate(**kwargs, trip_version=1, base_version=1,
            item_id=meal.item_id, message="다른 식당으로 바꿔 줘", request_id="test-route")
    assert isinstance(plan, changes.ItineraryChange)
    assert plan.summary["to"] == east["name"]
    assert west["name"] not in plan.notice["other_options"]


def test_day_watch_keeps_disaster_recheck_after_route_filter(monkeypatch):
    monkeypatch.setattr(legs, "leg_planner", lambda *args: None)
    before, meal, after = schedule()
    west, east = place("늦는 식당", -200), place("다른 재난에 걸린 식당", 350)
    checked = []

    def check(**args):
        checked.append(args["place"]["name"])
        return {"verdict": "disrupted", "disruptions": [{"kind": "통제"}]}

    plan = changes.plan_dining_disrupted(trip={}, items=[before, meal, after],
        places=[west, east], meal=meal, report={"disruptions": [{"kind": "화재"}]}, check=check)
    assert isinstance(plan, changes.NoChange) and plan.status == "unresolved"
    assert checked == [east["name"]]


@pytest.mark.parametrize("mode", ["watch", "alternate"])
def test_far_next_schedule_uses_injected_leg_engine(mode, monkeypatch):
    before, meal, after = schedule(next_east=-8000, next_min=105)
    west, east = place("늦는 서쪽 식당", -300), place("빠른 동쪽 식당", 300)
    etas = {meal.place["name"]: 40, west["name"]: 55, east["name"]: 32}
    calls = []

    def leg(a, b, arrive, leave):
        calls.append((a["name"], b["name"]))
        return {"eta_min": etas[a["name"]]}, None

    monkeypatch.setattr(legs, "leg_planner", lambda *args: leg)
    kwargs = {"trip": {}, "items": [before, meal, after], "places": [west, east]}
    if mode == "watch":
        plan = changes.plan_dining_disrupted(**kwargs, meal=meal,
            report={"disruptions": [{"kind": "통제"}]}, check=lambda **args: {"verdict": "clear"})
    else:
        plan = changes.plan_fresh_alternate(**kwargs, trip_version=1, base_version=1,
            item_id=meal.item_id, message="다른 식당", request_id="test-transit")
    assert isinstance(plan, changes.ItineraryChange) and plan.summary["to"] == east["name"]
    assert set(calls) == {(name, after.place["name"]) for name in etas}


def test_current_location_changes_actual_arrival_and_does_not_mutate_itinerary(monkeypatch):
    monkeypatch.setattr(legs, "leg_planner", lambda *args: None)
    origin, candidate = place("현재 위치", 0), place("식당", 400)
    found, _, _ = changes.plan_nearby("dining", trip={}, places=[candidate], origin=origin, at=NOON)
    assert found and found[0].starts_at > NOON
    second_origin = {**origin, "longitude": candidate["longitude"] - 100 / 88000}
    closer, _, _ = changes.plan_nearby("dining", trip={}, places=[candidate], origin=second_origin, at=NOON)
    assert NOON < closer[0].starts_at < found[0].starts_at
    assert closer[0].ends_at - closer[0].starts_at == timedelta(hours=1)


def test_current_location_restaurant_must_allow_travel_to_next_schedule(monkeypatch):
    monkeypatch.setattr(legs, "leg_planner", lambda *args: None)
    origin, west, east = place("현재 위치", 0), place("늦는 식당", -200), place("닿는 식당", 350)
    after = item(place("다음 엑티비티", 1500, "activity"), 3,
                 NOON + timedelta(minutes=80), NOON + timedelta(hours=2))
    found, _, _ = changes.plan_nearby("dining", trip={}, places=[west, east], origin=origin, at=NOON, items=[after])
    assert [c.name for c in found] == [east["name"]]


def test_current_location_long_route_rejects_next_schedule_lateness(monkeypatch):
    origin, restaurant = place("현재 위치", 0), place("식당", 300)
    after = item(place("먼 다음 일정", 8000, "activity"), 3,
                 NOON + timedelta(minutes=90), NOON + timedelta(hours=3))
    calls = []

    def leg(a, b, arrive, leave):
        calls.append(a["name"])
        return {"eta_min": 40}, None

    monkeypatch.setattr(legs, "leg_planner", lambda *args: leg)
    found, _, _ = changes.plan_nearby("dining", trip={}, places=[restaurant], origin=origin, at=NOON, items=[after])
    assert not found and restaurant["name"] in calls and origin["name"] in calls


def test_relaxed_restaurant_search_still_filters_impossible_next_route(monkeypatch):
    monkeypatch.setattr(legs, "leg_planner", lambda *args: None)
    before, meal, after = schedule()
    west, east = place("늦는 식당", -200), place("닿는 식당", 350)
    options = changes.relaxed_options(trip={}, items=[before, meal, after], places=[west, east], current=meal)
    assert options and all(option["name"] != west["name"] for option in options)
    assert any(option["name"] == east["name"] for option in options)
