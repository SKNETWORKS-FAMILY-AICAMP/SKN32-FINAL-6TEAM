"""악천후에는 확정 실내를 먼저 찾고 현재 이후 도착 가능한 안만 묻는다."""
from contextlib import nullcontext
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.itinerary import itinerary_changes as changes
from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.places import catalog_pool
from app.domains.travel_ops.components.team_hooks import legs
from app.domains.travel_ops.components.watch import watch_relaxed

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2030, 1, 1, 14, tzinfo=KST)
CAUSES = [{"category": "weather_warning", "kind": "강풍주의보"}]


class Cursor:
    def __init__(self, rows=()):
        self.rows, self.calls = rows, []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, rows=()):
        self.cur = Cursor(rows)

    def cursor(self):
        return self.cur

    def transaction(self):
        return nullcontext()


def place(name="실내 전시관", *, meters=1000, sensitive=False):
    return {"place_id": str(uuid4()), "name": name, "kind": "activity", "latitude": 37.5 + meters / 111000,
            "longitude": 127.0, "weather_sensitive": sensitive,
            "attributes": {"hours": ["09:00", "22:00"]}}


def ongoing():
    origin = place("원래 야외 축제", meters=0, sensitive=True)
    return Item(item_id=uuid4(), seq=1, kind="activity", title=origin["name"], place_id=origin["place_id"],
                place=origin, starts_at=NOW - timedelta(hours=1), ends_at=NOW + timedelta(hours=2))


def test_catalog_filters_confirmed_indoor_and_hours_before_the_limit(monkeypatch):
    monkeypatch.setattr(catalog_pool, "_catalog_tenants", lambda tenant: [tenant])
    conn = Connection([("1", "14", "공식 전시관", None, 37.5, 127.0, "VE", "VE07")])
    [cand] = catalog_pool.nearby_activities(conn, "unit", latitude=37.5, longitude=127.0, radius_m=5000,
                                           exclude_names={"이미 넣은 곳"}, now=NOW, require_hours=True, indoor_only=True)
    sql, params = conn.cur.calls[0]
    assert sql.index("IS FALSE") < sql.index("LIMIT") and sql.index("hours_week") < sql.index("LIMIT")
    assert "c.raw_json->>'lclsSystm2'" in sql and "pc.raw_json" not in sql
    assert "이미 넣은 곳" in str(params) and cand.weather_sensitive is False
    assert cand.attributes["weather_sensitive_basis"]["lcls2"] == "VE07"


def test_content_type_assumption_does_not_become_confirmed_indoor(monkeypatch):
    monkeypatch.setattr(catalog_pool, "_catalog_tenants", lambda tenant: [tenant])
    conn = Connection([("2", "14", "분류 모르는 시설", None, 37.5, 127.0, None, None)])
    [cand] = catalog_pool.nearby_activities(conn, "unit", latitude=37.5, longitude=127.0, radius_m=5000, exclude_names=set())
    assert cand.attributes.get("indoor_assumed") is True
    assert cand.weather_sensitive is None and "weather_sensitive_basis" not in cand.attributes


def test_expanding_the_radius_is_not_suppressed_by_the_smaller_radius_memo(monkeypatch):
    calls = []
    monkeypatch.setattr(catalog_pool, "nearby_activities", lambda *a, **k: calls.append(k["radius_m"]) or [])
    monkeypatch.setattr(catalog_pool, "reuse_hours", lambda *a: {})
    target = uuid4()
    for radius in (5000, 10000, 15000):
        catalog_pool.widen_activity_pool(Connection(), tenant_id="unit", trip_id=target, place=place(meters=0),
                                         known_names=set(), radius_m=radius, now=NOW, indoor_only=True)
    assert calls == [5000, 10000, 15000]


def test_an_ongoing_visit_starts_after_current_departure_and_real_travel_time(monkeypatch):
    monkeypatch.setattr(legs, "leg_planner", lambda *args: lambda *a: ({"eta_min": 30}, None))
    current, far = ongoing(), place(meters=8000)
    options = changes.relaxed_options(trip={}, items=[current], places=[far], current=current,
                                      causes=CAUSES, now=NOW, wide_radius_m=10000)
    assert options
    for option in options:
        assert datetime.fromisoformat(option["starts_at"]) == NOW + timedelta(minutes=30)
        assert datetime.fromisoformat(option["ends_at"]) == NOW + timedelta(minutes=150)
        assert "이동 계산 30분" in option["note"] and "10km" in option["note"]


def test_without_a_route_calculator_walking_is_explicit_and_not_instant(monkeypatch):
    monkeypatch.setattr(legs, "leg_planner", lambda *args: None)
    current = ongoing()
    options = changes.relaxed_options(trip={}, items=[current], places=[place(meters=1000)], current=current,
                                      causes=CAUSES, now=NOW)
    assert options and all(datetime.fromisoformat(o["starts_at"]) > NOW for o in options)
    assert all("도보 추정" in o["note"] for o in options)


def test_an_ongoing_alternative_can_shorten_the_visit_to_preserve_the_next_leg(monkeypatch):
    monkeypatch.setattr(legs, "leg_planner", lambda *args: lambda *a: ({"eta_min": 30}, None))
    current = ongoing()
    move = Item(item_id=uuid4(), seq=2, kind="mobility", title="다음 방문 이동", place_id=None,
                starts_at=NOW + timedelta(hours=2), ends_at=NOW + timedelta(hours=3))
    following = Item(item_id=uuid4(), seq=3, kind="activity", title="다음 방문", place=place("다음 방문"), place_id=None,
                     starts_at=NOW + timedelta(hours=3), ends_at=NOW + timedelta(hours=4))
    options = changes.relaxed_options(trip={}, items=[current, move, following], places=[place()], current=current,
                                      causes=CAUSES, now=NOW)
    assert options
    for option in options:
        assert datetime.fromisoformat(option["starts_at"]) >= NOW + timedelta(minutes=30)
        assert datetime.fromisoformat(option["ends_at"]) <= NOW + timedelta(hours=2)
        assert "방문 90분으로 줄임" in option["note"]
        assert changes.shift_moves_after([current, move, following], current,
                                         datetime.fromisoformat(option["ends_at"]))[1] is None


def test_a_shortened_visit_still_needs_at_least_25_minutes(monkeypatch):
    monkeypatch.setattr(legs, "leg_planner", lambda *args: lambda *a: ({"eta_min": 30}, None))
    current = ongoing()
    following = Item(item_id=uuid4(), seq=2, kind="activity", title="다음 방문", place=place("다음 방문"), place_id=None,
                     starts_at=NOW + timedelta(minutes=50), ends_at=NOW + timedelta(hours=2))
    assert changes.relaxed_options(trip={}, items=[current, following], places=[place()], current=current,
                                   causes=CAUSES, now=NOW) == []


def test_an_ended_visit_has_no_new_proposal(monkeypatch):
    current = ongoing()
    current.ends_at = NOW
    assert changes.relaxed_options(trip={}, items=[current], places=[place()], current=current, causes=CAUSES, now=NOW) == []


def test_wider_distance_does_not_relax_indoor_or_opening_requirements(monkeypatch):
    monkeypatch.setattr(legs, "leg_planner", lambda *args: None)
    current = ongoing()
    unknown, closed = place("실내 미확인", meters=8000, sensitive=None), place("닫힌 실내", meters=8000)
    closed["attributes"]["hours"] = ["09:00", "10:00"]
    assert changes.relaxed_options(trip={}, items=[current], places=[unknown, closed], current=current,
                                   causes=CAUSES, now=NOW, wide_radius_m=15000) == []


@pytest.mark.parametrize("success_radius", [10000, 15000])
def test_the_watch_expands_only_until_a_verified_option_exists(monkeypatch, success_radius):
    current, trip_id, calls = ongoing(), uuid4(), []
    trip = {"version": 1, "constraints": {}}
    store = SimpleNamespace(tenant_id="unit", latest=lambda *a: (trip, [current]), places=lambda *a: [current.place],
                            enqueue_message=lambda *a, **k: None)
    monkeypatch.setattr(watch_relaxed, "enabled", lambda: True)
    monkeypatch.setattr(catalog_pool, "widen_activity_pool", lambda *a, **k: calls.append((k["radius_m"], k["indoor_only"])))
    monkeypatch.setattr(watch_relaxed, "relaxed_options", lambda **k: [dict(key="x", name="먼 실내", rank=1)] if k["wide_radius_m"] == success_radius else [])
    monkeypatch.setattr(watch_relaxed, "verified_options", lambda **k: k["options"])
    monkeypatch.setattr(watch_relaxed.PendingStore, "open", lambda *a, **k: uuid4())
    result = watch_relaxed.offer_relaxed(Connection(), store=store, trip_id=trip_id, item_id=current.item_id,
                                         causes=CAUSES, now=NOW)
    assert result["status"] == "asked"
    assert calls == [(radius, True) for radius in (5000, 10000, 15000) if radius <= success_radius]


def test_recheck_failure_is_not_reported_as_no_alternative(monkeypatch):
    current = ongoing()
    store = SimpleNamespace(tenant_id="unit", latest=lambda *a: ({"version": 1}, [current]), places=lambda *a: [current.place])
    monkeypatch.setattr(watch_relaxed, "enabled", lambda: True)
    monkeypatch.setattr(catalog_pool, "widen_activity_pool", lambda *a, **k: None)
    monkeypatch.setattr(watch_relaxed, "relaxed_options", lambda **k: [{"key": "x"}])
    def failed(**kwargs):
        raise watch_relaxed.VerificationUnavailable(["traffic_control"])
    monkeypatch.setattr(watch_relaxed, "verified_options", failed)
    with pytest.raises(watch_relaxed.VerificationUnavailable):
        watch_relaxed.offer_relaxed(Connection(), store=store, trip_id=uuid4(), item_id=current.item_id, causes=CAUSES, now=NOW)
