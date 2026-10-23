"""실제 점검→감시→알림 렌더러에서 부분 실패가 확인된 사건을 지우지 않는다."""
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.planning.pending import PendingStore
from app.domains.travel_ops.components.watch import trip_watch_batch, trip_watch_cases
from app.domains.travel_ops.components.watch.risk_report import judge_item
from app.domains.travel_ops.ports.data_sources.base import TravelSources
from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck
from app.infrastructure.notify.discord import render

NOW = datetime(2030, 1, 1, 11, 30, tzinfo=ZoneInfo("Asia/Seoul"))
ROAD = {"reason": "road_closed", "road": "합성 문화로", "section": "합성 동문~서문",
        "message": "문화 행사로 전면 통제", "incident_id": "synthetic-road-1",
        "starts_at": "2030-01-01T10:00:00+09:00", "ends_at": "2030-01-01T18:00:00+09:00",
        "distance_m": 240, "source": "utic"}


class Conn:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def transaction(self):
        return nullcontext(self)


def make_report():
    sources = TravelSources(
        weather=SimpleNamespace(forecast=lambda **kw: None),
        traffic=SimpleNamespace(near=lambda **kw: {"source": "utic", "sources": ["utic"],
            "partial_from": ["its"], "confirmed_at": NOW.isoformat(), "for_place": [deepcopy(ROAD)]}))
    place = {"name": "합성 여행지", "latitude": 37.57, "longitude": 127.1, "weather_sensitive": True}
    return DisruptionCheck(sources, limits=lambda: (60, 30)).check(place=place, starts_at=NOW)


class Store:
    """바깥함 UNIQUE 경계만 메모리로 대체한다. 점검·감시·문구 생성은 실제 경로다."""
    tenant_id = "synthetic-notice"

    def __init__(self, stop):
        self.trip_id = uuid4()
        self.trip = {"customer_id": uuid4(), "version": 1, "constraints": {}}
        self.items, self.messages = [stop], {}

    def due(self, *args, **kwargs):
        return [(self.trip_id, self.items[0])]

    def latest(self, *args):
        return self.trip, self.items

    def enqueue_message(self, conn, *, trip_id, key, payload):
        assert trip_id == self.trip_id
        if key in self.messages:
            return False
        self.messages[key] = deepcopy(payload)
        return True


@pytest.fixture
def world(monkeypatch):
    stop = Item(item_id=uuid4(), seq=1, kind="activity", title="합성 여행지",
                place_id=None, place={"name": "합성 여행지", "latitude": 37.57, "longitude": 127.1},
                starts_at=NOW-timedelta(hours=1), ends_at=NOW+timedelta(hours=1), detail={})
    store = Store(stop)
    report = make_report()
    monkeypatch.setattr(PendingStore, "expire", lambda *a, **kw: [])
    monkeypatch.setattr(trip_watch_batch, "skipped_watch", lambda *a, **kw: None)
    monkeypatch.setattr(trip_watch_cases, "forecast_attention", lambda *a, **kw: None)
    calls = []
    opener = trip_watch_cases.TripWatchCaseOpener(store=store, check=lambda **kw: deepcopy(report),
        connection_factory=Conn, clock=lambda: NOW, repository=None,
        run_case=lambda **kw: calls.append(kw))
    return SimpleNamespace(store=store, item=stop, report=report, opener=opener, calls=calls)


def test_real_check_keeps_both_confirmed_problem_and_unknown():
    report = make_report()
    assert report["verdict"] == "fatal" and report["failed_categories"] == ["forecast"]
    stop = Item(item_id=uuid4(), seq=1, kind="activity", title="합성 여행지", place_id=None,
                place={"name": "합성 여행지", "latitude": 37.57, "longitude": 127.1},
                starts_at=NOW, ends_at=NOW+timedelta(hours=1))
    risk = judge_item(lambda **kw: report, stop, mode="fresh", at=NOW)
    assert risk["status"] == "problem" and risk["problems"]
    assert {r["category"] for r in risk["unknown_categories"]} >= {"forecast", "traffic_control"}


def test_traffic_projection_keeps_public_incident_identity_and_period_only():
    report = make_report()
    [cause] = report["disruptions"]
    for name in ("incident_id", "section", "starts_at", "ends_at"):
        assert cause[name] == ROAD[name]
    assert cause["confirmed_at"] == NOW.isoformat()


def test_fatal_check_announces_confirmed_road_and_failure_without_changing_trip(world):
    before = deepcopy((world.store.trip, world.store.items))
    result = world.opener.tick()
    assert result.fatal and not result.opened and not world.calls
    assert (world.store.trip, world.store.items) == before
    [payload] = world.store.messages.values()
    assert any(c.get("category") == "traffic_control" for c in payload["causes"])
    assert any(c.get("kind") == "source_unavailable" for c in payload["causes"])
    assert payload["type"] == "guidance" and payload["changed"] is None
    text = render(payload)
    assert "합성 문화로" in text and "문화 행사로 전면 통제" in text
    assert "주변" in text and "일부 자료" in text and "기존 일정을 유지" in text
    assert "자동 변경" in text and "확인 시각" in text


def test_repoll_distance_confirmation_and_order_do_not_create_another_notice(world):
    assert len(world.opener.tick().notified) == 1
    world.report["checked_at"] = (NOW+timedelta(minutes=3)).isoformat()
    for cause in world.report["disruptions"]:
        cause.update(distance_m=333, confirmed_at=(NOW+timedelta(minutes=3)).isoformat())
    world.report["checks"].reverse()
    assert world.opener.tick().notified == []
    assert len(world.store.messages) == 1


@pytest.mark.parametrize("field,value", [("incident_id", "synthetic-road-2"),
    ("ends_at", "2030-01-01T20:00:00+09:00"), ("road", "합성 강변로")])
def test_new_incident_or_material_state_can_notify_again(world, field, value):
    world.opener.tick()
    world.report["disruptions"][0][field] = value
    assert len(world.opener.tick().notified) == 1
    assert len(world.store.messages) == 2


def test_changed_failure_state_is_not_swallowed(world):
    world.opener.tick()
    world.report["failed_categories"] = ["air_quality"]
    assert len(world.opener.tick().notified) == 1
    assert len(world.store.messages) == 2


def test_failure_details_and_unlisted_event_fields_are_not_copied(world):
    secret = "PRIVATE_TEST_ERROR_TOKEN_NOT_FOR_CUSTOMER"
    world.report.update(reason=secret, raw={"key": secret}, error_code=secret)
    world.report["checks"][0]["reason"] = secret
    world.report["disruptions"][0].update(raw={"key": secret}, api_key=secret)
    world.opener.tick()
    [payload] = world.store.messages.values()
    assert secret not in repr(payload) and secret not in render(payload)


@pytest.mark.parametrize("category", ["disaster_msg", "earthquake", "weather_warning"])
def test_failed_safety_source_is_not_a_confirmed_safety_event(world, category):
    world.report.update(disruptions=[], failed_categories=[category])
    world.opener.tick()
    [payload] = world.store.messages.values()
    assert payload["type"] == "guidance" and "안전 알림" not in render(payload)
    assert not world.calls


def test_same_event_set_in_different_order_is_one_notice(world):
    second = {**deepcopy(world.report["disruptions"][0]), "incident_id": "synthetic-road-2", "road": "합성 공원로"}
    world.report["disruptions"].append(second)
    world.opener.tick()
    world.report["disruptions"].reverse()
    world.report["failed_categories"] *= 2
    assert world.opener.tick().notified == [] and len(world.store.messages) == 1


def test_without_event_id_distinct_roads_are_not_collapsed(world):
    world.report["disruptions"][0].pop("incident_id", None)
    world.opener.tick()
    world.report["disruptions"][0]["road"] = "합성 새 길"
    assert len(world.opener.tick().notified) == 1 and len(world.store.messages) == 2


@pytest.mark.parametrize("valid", [True, False])
def test_dining_enrichment_failure_keeps_only_previously_validated_facts(world, valid):
    world.item.kind = "dining"
    world.report["advisories"] = [{"category": "air_quality", "field": "grade", "value": 3}]
    if not valid:
        world.report["verdict"] = "invalid-source-response"
    before = deepcopy(world.report)
    calls = []
    def lookup(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("PRIVATE_SYNTHETIC_ENRICHMENT_ERROR")
    world.opener.place_status = SimpleNamespace(lookup=lookup)
    result = world.opener.tick()
    [fatal] = result.fatal
    report = fatal["report"]
    assert report["verdict"] == "fatal" and "place_check" in report["failed_categories"]
    [payload] = world.store.messages.values()
    if valid:
        assert len(calls) == 1
        assert report["disruptions"] == before["disruptions"]
        assert report["checks"] == before["checks"] and report["advisories"] == before["advisories"]
        assert "forecast" in report["failed_categories"]
        assert "합성 문화로" in render(payload)
    else:
        assert not calls and not report.get("disruptions")
        assert "합성 문화로" not in render(payload)
    assert "PRIVATE_SYNTHETIC_ENRICHMENT_ERROR" not in repr(payload)
    assert not result.opened and not world.calls and world.store.trip["version"] == 1


def test_a_later_item_check_exception_never_inherits_an_earlier_items_fact(world):
    second = deepcopy(world.item)
    second.item_id = uuid4()
    second.seq = 2
    second.title = "다음 합성 여행지"
    second.place["name"] = second.title
    world.store.items.append(second)
    world.store.due = lambda *a, **kw: [(world.store.trip_id, i) for i in world.store.items]
    def check(*, place, starts_at):
        if place["name"] == second.title:
            raise RuntimeError("PRIVATE_SYNTHETIC_SECOND_CHECK_ERROR")
        return deepcopy(world.report)
    world.opener.check = check
    result = world.opener.tick()
    assert len(result.fatal) == 2 and len(world.store.messages) == 2
    later = next(r for r in result.fatal if r["item"] == second.title)
    assert not later["report"].get("disruptions")
    payload = next(p for p in world.store.messages.values() if p["items"] == [str(second.item_id)])
    assert all(c["kind"] == "source_unavailable" for c in payload["causes"])
    assert "합성 문화로" not in render(payload) and "PRIVATE_SYNTHETIC_SECOND_CHECK_ERROR" not in repr(payload)
    assert not result.opened and not world.calls


def test_failure_without_events_never_invents_a_control(world):
    world.report["disruptions"] = []
    world.opener.tick()
    [payload] = world.store.messages.values()
    assert all(c.get("kind") == "source_unavailable" for c in payload["causes"])
    assert "통제" not in render(payload) and payload["type"] == "guidance"


def test_multiple_independent_facts_and_safety_are_retained(world):
    world.report["disruptions"].append({"category": "disaster_msg", "kind": "fire",
        "text": "합성 전시관 화재로 접근 금지", "serial": "synthetic-fire-1", "source": "disaster_msg"})
    world.opener.tick()
    [payload] = world.store.messages.values()
    assert payload["type"] == "safety_alert" and len(payload["causes"]) == 3
    assert "문화 행사로 전면 통제" in render(payload) and "합성 전시관 화재" in render(payload)
    assert not world.calls


@pytest.mark.parametrize("protected", ["pinned", "locked", "booked"])
def test_protected_items_still_get_facts_but_no_mutation(world, protected):
    if protected == "pinned":
        world.item.detail["customer_pinned"] = True
    elif protected == "locked":
        world.item.locked = True
    else:
        world.item.booking_id = uuid4()
    before = deepcopy((world.store.trip, world.store.items))
    world.opener.tick()
    assert (world.store.trip, world.store.items) == before and not world.calls
    [payload] = world.store.messages.values()
    assert "합성 문화로" in render(payload)
