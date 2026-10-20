"""지정 위치 근처의 원장 조회와 대안 계산이 같은 반경 계약을 쓴다."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation import trip_desk
from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.itinerary.itinerary_changes import ALTERNATE_RADII_M, NoChange


class Conn:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.fixture
def world(monkeypatch):
    now = datetime(2030, 1, 1, 12, tzinfo=ZoneInfo("Asia/Seoul"))
    original = {"place_id": str(uuid4()), "name": "원래 식사", "kind": "dining", "latitude": 37.57, "longitude": 126.98}
    origin = {"place_id": str(uuid4()), "name": "기준 장소", "kind": "activity", "latitude": 37.56, "longitude": 127.13}
    stop = Item(item_id=uuid4(), seq=1, kind="dining", title=original["name"], place=original,
                place_id=None, starts_at=now, ends_at=now+timedelta(hours=1))
    store = SimpleNamespace(tenant_id="synthetic-origin-radius")
    desk = trip_desk.TripDesk(store=store, connection_factory=Conn)
    monkeypatch.setattr(desk, "_read", lambda _: ({"version": 1, "constraints": {}}, [stop], [original]))
    calls = []
    monkeypatch.setattr(trip_desk, "plan_fresh_alternate", lambda **kw: calls.append(kw) or NoChange("no_alternate", {}))
    return SimpleNamespace(desk=desk, trip_id=uuid4(), stop=stop, origin=origin, original=original, calls=calls)


def test_existing_default_hook_call_keeps_its_previous_shape(world, monkeypatch):
    seen = []
    def existing_hook(conn, store, trip_id, items, places):
        seen.append((store, trip_id, items, places))
        return places
    monkeypatch.setattr(trip_desk.dining_hook, "add_nearby", existing_hook)
    assert world.desk._add_nearby(world.trip_id, world.stop, [world.original]) == [world.original]
    assert len(seen) == 1


def test_explicit_radius_is_passed_to_the_existing_hook(world, monkeypatch):
    seen = []
    monkeypatch.setattr(trip_desk.dining_hook, "add_nearby", lambda *a, **kw: seen.append(kw) or a[4])
    radius = max(ALTERNATE_RADII_M["dining"])
    world.desk._add_nearby(world.trip_id, world.stop, [world.original], radius_m=radius)
    assert seen == [{"radius_m": radius}]


def test_near_request_loads_max_existing_radius_and_preserves_search_origin(world, monkeypatch):
    seen = []
    monkeypatch.setattr(trip_desk.dining_hook, "add_nearby", lambda *a, **kw: seen.append((a, kw)) or a[4])
    world.desk.near_alternate(trip_id=world.trip_id, item_id=world.stop.item_id, base_version=1, origin=world.origin)
    [(args, kwargs)] = seen
    assert kwargs == {"radius_m": max(ALTERNATE_RADII_M["dining"])}
    assert args[3][0].place is world.origin
    assert world.calls[0]["search_origin"] is world.origin


def test_radius_comes_from_the_shared_contract_instead_of_a_new_number(world, monkeypatch):
    monkeypatch.setitem(ALTERNATE_RADII_M, "dining", (700, 1700, 3200))
    seen = []
    monkeypatch.setattr(trip_desk.dining_hook, "add_nearby", lambda *a, **kw: seen.append(kw) or a[4])
    world.desk.near_alternate(trip_id=world.trip_id, item_id=world.stop.item_id, base_version=1, origin=world.origin)
    assert seen == [{"radius_m": max(ALTERNATE_RADII_M["dining"])}]


def test_scenario_disabled_ledger_never_calls_the_hook(world, monkeypatch):
    world.desk._use_ledger = False
    def forbidden(*args, **kwargs):
        raise AssertionError("disabled ledger was called")
    monkeypatch.setattr(trip_desk.dining_hook, "add_nearby", forbidden)
    world.desk.near_alternate(trip_id=world.trip_id, item_id=world.stop.item_id, base_version=1, origin=world.origin)
    assert len(world.calls) == 1


@pytest.mark.parametrize("protected", ["locked", "booked", "stale"])
def test_existing_protection_stops_before_loading_candidates(world, monkeypatch, protected):
    if protected == "locked":
        world.stop.locked = True
    if protected == "booked":
        world.stop.booking_id = uuid4()
    def forbidden(*args, **kwargs):
        raise AssertionError("protected request loaded candidates")
    monkeypatch.setattr(trip_desk.dining_hook, "add_nearby", forbidden)
    result = world.desk.near_alternate(trip_id=world.trip_id, item_id=world.stop.item_id,
                                      base_version=0 if protected == "stale" else 1, origin=world.origin)
    assert result["status"] == ("stale" if protected == "stale" else "edit_refused")
    assert not world.calls
