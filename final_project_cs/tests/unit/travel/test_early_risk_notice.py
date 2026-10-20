"""대안 계산 전 위험 안내의 순서·범위·묶음 중복을 검증한다. 실제 DB 잠금은 별도 검증한다."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.watch import monitoring, trip_watch_cases as watch
from app.infrastructure.notify.discord import render

NOW = datetime(2030, 1, 1, 12, tzinfo=ZoneInfo("Asia/Seoul"))


def cause(kind="강풍주의보", **extra):
    return {"category": "weather_warning", "kind": kind, **extra}


class Rows:
    def __init__(self, values):
        self.values = values

    def fetchone(self):
        return self.values[0] if self.values else None

    def fetchall(self):
        return self.values


class Store:
    tenant_id = "synthetic-early-notice"

    def __init__(self):
        self.trip = uuid4()
        self.current = []
        self.messages = {}
        self.events = []
        self.connections = 0
        self.locked = False
        self.trip_exists = True

    def due(self, conn, **kwargs):
        assert self.locked
        self.events.append("due")
        return [(self.trip, item) for item in self.current]

    def enqueue_message(self, conn, *, trip_id, key, payload):
        assert self.locked and trip_id == self.trip
        self.events.append("enqueue")
        if key in self.messages:
            return False
        self.messages[key] = deepcopy(payload)
        return True

    @contextmanager
    def connection(self):
        self.connections += 1
        self.events.append("connection_open")
        store = self

        class Conn:
            @contextmanager
            def transaction(self):
                before = deepcopy(store.messages)
                try:
                    yield self
                except Exception:
                    store.messages = before
                    store.events.append("rollback")
                    raise
                else:
                    store.events.append("commit")
                finally:
                    store.locked = False

            def execute(self, sql, params):
                if "FOR UPDATE" in sql:
                    store.locked = True
                    store.events.append("lock")
                    assert params == (store.tenant_id, store.trip)
                    return Rows([(1,)] if store.trip_exists else [])
                assert "risk_fingerprints" in sql and "?|" in sql and store.locked
                assert params[:2] == (store.tenant_id, str(store.trip) + ":watch-risk-detected:%")
                wanted = set(params[2])
                return Rows([(p["risk_fingerprints"],) for p in store.messages.values()
                             if wanted.intersection(p.get("risk_fingerprints", []))])

        try:
            yield Conn()
        finally:
            self.connections -= 1
            self.events.append("connection_closed")


@pytest.fixture
def world(monkeypatch):
    store = Store()
    item = Item(item_id=uuid4(), seq=1, kind="activity", title="합성 여행 활동", place_id=uuid4(),
                starts_at=NOW-timedelta(minutes=10), ends_at=NOW+timedelta(hours=1),
                place={"name": "합성 방문지", "latitude": 37.57, "longitude": 127.1})
    store.current = [deepcopy(item)]
    opener = watch.TripWatchCaseOpener(store=store, check=None, connection_factory=store.connection,
        clock=lambda: NOW, repository=None, run_case=None)
    monkeypatch.setattr(monitoring, "recording", lambda: True)
    issue = watch.Issue(store.trip, item, [cause()], "activity_weather_risk", "place")
    return SimpleNamespace(store=store, item=item, opener=opener, issue=issue)


def early(world, issues=None):
    result = watch.CaseTickResult()
    world.opener._early_notice(world.store.trip, [world.issue] if issues is None else issues, result)
    return result


def test_notice_commits_before_case_or_alternative_work_with_no_outer_connection(world, monkeypatch):
    monkeypatch.setattr(world.opener, "_attempt", lambda *a: (0, None))
    monkeypatch.setattr(world.opener, "_refresh_existing_alternatives", lambda *a: pytest.fail("no existing issue"))

    def open_single(*args):
        assert world.store.connections == 0 and not world.store.locked
        assert "commit" in world.store.events and len(world.store.messages) == 1
        world.store.events.append("case")

    monkeypatch.setattr(world.opener, "_open_single", open_single)
    world.opener._open_issues([world.issue], NOW, watch.CaseTickResult(), [])
    assert world.store.events.index("commit") < world.store.events.index("case")
    assert world.store.events.index("lock") < world.store.events.index("due") < world.store.events.index("enqueue")


def test_roads_public_facts_end_time_and_current_itinerary_are_preserved(world):
    secret = "PRIVATE_SYNTHETIC_ERROR_TOKEN"
    road = {"category": "traffic_control", "kind": "전면 통제", "message": "합성 문화로 동문~서문 전면 통제",
            "incident_id": "synthetic-A", "source": "utic", "ends_at": "2030-01-01T18:00:00+09:00",
            "raw": {"api_key": secret}, "error": secret}
    world.issue.causes += [road, {"category": "disaster_msg", "kind": "강풍"}]
    before = deepcopy(world.store.current)
    result = early(world)
    [payload] = world.store.messages.values()
    assert payload["type"] == "safety_alert" and payload["kind"] == "risk_detected"
    text = render(payload)
    assert "강풍주의보" in text and "동문~서문" in text and "18:00" in text
    assert "대안을 확인하고 있어요" in text and "현재 일정은 그대로" in text
    assert secret not in repr(payload) and payload["item_id"] == str(world.item.item_id)
    assert len(result.notified) == 1 and world.store.current == before


@pytest.mark.parametrize("kind,safety", [("강풍주의보", False), ("호우경보", True)])
def test_safety_category_uses_existing_policy(world, kind, safety):
    world.issue.causes = [cause(kind)]
    early(world)
    [payload] = world.store.messages.values()
    assert payload["type"] == ("safety_alert" if safety else "guidance")


def test_same_fingerprint_and_observation_time_only_notify_once(world):
    early(world)
    world.issue.causes[0].update(confirmed_at="later", distance_m=123)
    assert early(world).notified == [] and len(world.store.messages) == 1


def test_batch_is_one_notice_and_subset_or_changed_composition_do_not_repeat_members(world):
    second = replace(world.item, item_id=uuid4(), seq=2, title="합성 두 번째 방문지")
    third = replace(world.item, item_id=uuid4(), seq=3, title="합성 세 번째 방문지")
    world.store.current += [deepcopy(second), deepcopy(third)]
    two = watch.Issue(world.store.trip, second, [cause()], "activity_weather_risk", "place")
    three = watch.Issue(world.store.trip, third, [cause()], "activity_weather_risk", "place")
    early(world, [world.issue, two])
    assert len(world.store.messages) == 1
    [first] = world.store.messages.values()
    assert len(first["items"]) == 2 and len(first["risk_fingerprints"]) == 2
    assert "합성 두 번째 방문지" in first["text"] and "12월" not in first["text"]
    assert early(world, [two, world.issue]).notified == []
    assert early(world, [two]).notified == []
    early(world, [two, three])
    assert len(world.store.messages) == 2
    last = list(world.store.messages.values())[-1]
    assert [member["item_id"] for member in last["items"]] == [str(third.item_id)]


@pytest.mark.parametrize("field,value", [
    ("title", "고친 이름"), ("starts_at", NOW+timedelta(minutes=5)), ("ends_at", NOW+timedelta(hours=2)),
    ("place_id", uuid4()), ("place", {"name": "다른 장소"}), ("kind", "dining"),
    ("locked", True), ("booking_id", uuid4()), ("detail", {"customer_pinned": True}),
])
def test_changed_item_snapshot_never_receives_stale_early_notice(world, field, value):
    world.store.current = [replace(world.item, **{field: value})]
    assert early(world).notified == [] and not world.store.messages


def test_no_longer_due_or_deleted_trip_has_no_notice(world):
    world.store.current = []
    assert not early(world).notified
    world.store.current = [world.item]; world.store.trip_exists = False
    assert not early(world).notified and not world.store.messages


@pytest.mark.parametrize("protected", ["locked", "booked", "pinned"])
def test_protected_current_item_still_receives_facts_without_mutation(world, protected):
    if protected == "locked": world.item.locked = True
    elif protected == "booked": world.item.booking_id = uuid4()
    else: world.item.detail = {"customer_pinned": True}
    world.store.current = [deepcopy(world.item)]
    before = deepcopy(world.store.current)
    assert len(early(world).notified) == 1 and world.store.current == before


def test_normal_recording_context_is_required(world, monkeypatch):
    monkeypatch.setattr(monitoring, "recording", lambda: False)
    assert early(world).notified == [] and world.store.events == []


def test_unconfirmed_error_or_empty_causes_do_not_create_risk_alert(world):
    world.issue.causes = [{"category": "forecast", "kind": "source_unavailable"}]
    assert not early(world).notified and not world.store.messages
    world.issue.causes = []
    assert not early(world).notified


def test_existing_case_without_initial_notice_receives_facts_once(world, monkeypatch):
    monkeypatch.setattr(world.opener, "_attempt", lambda *a: (None, str(uuid4())))
    monkeypatch.setattr(world.opener, "_repair_traffic_notice", lambda *a: None)
    monkeypatch.setattr(world.opener, "_refresh_existing_alternatives", lambda *a: None)
    first = watch.CaseTickResult()
    world.opener._open_issues([world.issue], NOW, first, [])
    assert len(first.notified) == 1 and len(world.store.messages) == 1
    second = watch.CaseTickResult()
    world.opener._open_issues([world.issue], NOW, second, [])
    assert not second.notified and len(world.store.messages) == 1


def test_initial_warning_failure_does_not_block_original_case_handling(world, monkeypatch):
    monkeypatch.setattr(world.opener, "_attempt", lambda *a: (0, None))
    monkeypatch.setattr(world.opener, "_early_notice", lambda *a: (_ for _ in ()).throw(RuntimeError("synthetic")))
    opened = []
    monkeypatch.setattr(world.opener, "_open_single", lambda *args: opened.append(True))
    result = watch.CaseTickResult()
    world.opener._open_issues([world.issue], NOW, result, [])
    assert opened == [True] and result.failed[0]["reason"] == "early_notice_failed"


def test_new_road_incident_is_not_hidden_by_same_control_type(world):
    road = {"category": "traffic_control", "kind": "전면 통제", "source": "utic", "incident_id": "A", "road": "문화로"}
    world.issue.causes = [road]
    early(world)
    world.issue.causes = [{**road, "incident_id": "B"}]
    assert len(early(world).notified) == 1 and len(world.store.messages) == 2
    assert not early(world).notified


def test_remaining_cause_after_another_clears_is_not_reannounced(world):
    road = {"category": "traffic_control", "kind": "전면 통제", "source": "utic", "incident_id": "A"}
    world.issue.causes += [road]
    early(world)
    world.issue.causes = [road]
    assert not early(world).notified and len(world.store.messages) == 1
