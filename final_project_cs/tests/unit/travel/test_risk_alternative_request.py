"""고객 위험 대안 요청의 소유·정지·경합·중복·CSRF 경계를 확인한다."""
from contextlib import nullcontext
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.watch import risk_alternatives as service
from app.domains.travel_ops.components.watch import risk_report, watch_relaxed
from app.domains.travel_ops.entry import trip_api
from app.domains.travel_ops.modules.web_account import web_cookie, web_guard

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2030, 1, 1, 14, tzinfo=KST)
ROAD = {"category": "traffic_control", "kind": "road_closed", "message": "시험로 양방향 통제", "source": "utic"}


def report(*problems, failed=False):
    return {"verdict": "fatal" if failed else "disrupted" if problems else "clear", "disruptions": list(problems),
            "checks": [{"category": category, "status": "ok", "source": "test", "confirmed_at": NOW.isoformat()}
                       for category in risk_report.CATEGORIES], "checked_at": NOW.isoformat()}


@pytest.fixture
def world(monkeypatch):
    owner, trip_id, proposal = uuid4(), uuid4(), uuid4()
    item = Item(item_id=uuid4(), seq=1, kind="activity", title="야외 방문", place_id=uuid4(),
                starts_at=NOW - timedelta(hours=1), ends_at=NOW + timedelta(hours=2),
                place={"name": "야외 방문", "latitude": 37.5, "longitude": 127.0, "weather_sensitive": True})
    trip = {"customer_id": owner, "version": 1, "constraints": {}, "party_size": 2}
    gate = [owner, "active", False]
    sql, checked, offers, messages = [], [], [], []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, statement, params):
            assert params == ("unit", trip_id)
            sql.append(statement)
        def fetchone(self): return tuple(gate)
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def transaction(self): return nullcontext()
        def cursor(self): return Cursor()
    store = SimpleNamespace(tenant_id="unit", latest=lambda *a: (trip, [item]),
                            enqueue_message=lambda *a, **kw: messages.append(kw))
    def check(**kwargs):
        checked.append(kwargs)
        return report(ROAD)
    def offer(conn, **kwargs):
        offers.append(kwargs)
        kwargs["store"].enqueue_message(conn, trip_id=trip_id, key="proposal", payload={})
        return {"status": "asked", "already": False, "proposal_id": str(proposal), "options": [{"key": "x"}]}
    monkeypatch.setattr(watch_relaxed, "enabled", lambda: True)
    monkeypatch.setattr(watch_relaxed, "offer_relaxed", offer)
    monkeypatch.setattr(service, "_may_notify", lambda *a: True)
    def run(**kwargs):
        args = {"tenant_id": "unit", "customer_id": owner, "trip_id": trip_id, "item_id": item.item_id,
                "check": check, "now": NOW, "store_factory": lambda tenant: store}
        args.update(kwargs)
        return service.request(Connection, **args)
    return SimpleNamespace(owner=owner, trip_id=trip_id, proposal=proposal, item=item, trip=trip, gate=gate,
        sql=sql, checked=checked, offers=offers, messages=messages, run=run, connect=Connection, store=store)


def test_ownership_is_checked_before_any_provider_call(world):
    with pytest.raises(LookupError):
        world.run(customer_id=uuid4())
    assert not world.checked and not world.offers


@pytest.mark.parametrize("status,paused,reason", [("closed", False, "inactive"), ("active", True, "paused")])
def test_inactive_and_paused_trips_never_start_an_alternative_search(world, status, paused, reason):
    world.gate[1:] = [status, paused]
    assert world.run()["reason"] == reason and not world.checked


def test_ended_and_unknown_place_items_do_not_call_sources(world):
    world.item.ends_at = NOW
    assert world.run()["status"] == "ended"
    world.item.ends_at = NOW + timedelta(hours=1)
    world.item.place = None
    assert world.run()["status"] == "unavailable" and not world.checked


def test_a_valid_request_checks_now_locks_then_only_opens_a_proposal(world):
    result = world.run()
    assert result["status"] == "offered" and result["proposal_id"] == str(world.proposal)
    assert world.checked[0]["starts_at"] == NOW and "FOR UPDATE OF t" in world.sql[-1]
    assert world.trip["version"] == 1 and world.item.starts_at == NOW - timedelta(hours=1)
    assert len(world.offers) == len(world.messages) == 1


def test_source_failure_preserves_confirmed_road_information(world):
    result = world.run(check=lambda **kwargs: report(ROAD, failed=True))
    assert result["status"] == "unavailable" and result["reason"] == "verification_failed"
    assert result["report"]["problems"][0]["message"] == ROAD["message"] and not world.offers


def test_clear_disabled_and_real_no_alternative_are_distinct(world, monkeypatch):
    assert world.run(check=lambda **kw: report())["status"] == "no_risk"
    monkeypatch.setattr(watch_relaxed, "enabled", lambda: False)
    assert world.run()["reason"] == "feature_disabled"
    monkeypatch.setattr(watch_relaxed, "enabled", lambda: True)
    monkeypatch.setattr(watch_relaxed, "offer_relaxed", lambda *a, **k: None)
    assert world.run()["status"] == "no_alternate"


@pytest.mark.parametrize("change", ["version", "place", "title", "time"])
def test_changes_during_verification_do_not_open_a_stale_proposal(world, change):
    def checked(**kwargs):
        if change == "version": world.trip["version"] += 1
        if change == "place": world.item.place["latitude"] += 0.01
        if change == "title": world.item.title = "변경됨"
        if change == "time": world.item.starts_at += timedelta(minutes=1)
        return report(ROAD)
    assert world.run(check=checked)["status"] == "stale" and not world.offers


def test_an_existing_open_proposal_returns_its_id_instead_of_sending_again(world, monkeypatch):
    monkeypatch.setattr(watch_relaxed, "offer_relaxed", lambda *a, **k: {"already": True, "options": []})
    monkeypatch.setattr(service.PendingStore, "list", lambda *a, **k: [{"proposal_id": world.proposal,
        "item_id": world.item.item_id, "base_version": 1, "options_json": [{"key": "existing"}]}])
    result = world.run()
    assert result["status"] == "already" and result["proposal_id"] == str(world.proposal)
    assert result["options"] == [{"key": "existing"}] and not world.messages


def test_a_closed_proposal_is_not_claimed_to_be_open(world, monkeypatch):
    monkeypatch.setattr(watch_relaxed, "offer_relaxed", lambda *a, **k: {"already": True, "options": []})
    monkeypatch.setattr(service.PendingStore, "list", lambda *a, **k: [])
    result = world.run()
    assert result["status"] == "unavailable" and result["reason"] == "closed_proposal"


def test_guest_or_missing_channel_consent_allows_web_proposal_without_external_notice(world, monkeypatch):
    monkeypatch.setattr(service, "_may_notify", lambda *a: False)
    assert world.run()["status"] == "offered" and not world.messages


def test_candidate_verification_failure_is_not_a_no_alternative_result(world, monkeypatch):
    def unavailable(*a, **k): raise watch_relaxed.VerificationUnavailable(["traffic_control"])
    monkeypatch.setattr(watch_relaxed, "offer_relaxed", unavailable)
    result = world.run()
    assert result["status"] == "unavailable" and result["failed_categories"] == ["traffic_control"]


@pytest.fixture
def http(monkeypatch, world):
    monkeypatch.setattr(web_guard, "assert_human_check_configured", lambda: None)
    counts = []
    monkeypatch.setattr(web_guard, "count", lambda tenant, action, **kw: counts.append({"tenant_id": tenant, "action": action, **kw}))
    monkeypatch.setattr(trip_api, "get_connection", world.connect)
    monkeypatch.setattr(trip_api, "TripStore", lambda tenant: world.store)
    monkeypatch.setattr(web_cookie, "get_connection", world.connect)
    monkeypatch.setattr(web_cookie, "cookie_name", lambda: "test_session")
    monkeypatch.setattr(web_cookie, "csrf_token", lambda *a: "valid-csrf")
    monkeypatch.setattr(web_cookie, "_admin_access", lambda *a: None)
    monkeypatch.setattr(web_cookie, "_consent_gate", lambda *a: None)
    monkeypatch.setattr(web_cookie, "resolve_key", lambda *a, **k: None)
    monkeypatch.setattr(web_cookie, "lookup", lambda *a, **k: web_cookie.Session(
        world.owner, "synthetic", "member", NOW + timedelta(days=1), NOW + timedelta(days=1)))
    monkeypatch.setattr(service, "request", lambda *a, **kw: {"status": "offered", "proposal_id": str(world.proposal), "options": []})
    app = FastAPI()
    app.include_router(trip_api.build_trip_router(check_factory=lambda: lambda **kw: report(ROAD)))
    return SimpleNamespace(client=TestClient(app), url=f"/v1/web/trips/{world.trip_id}/risks/{world.item.item_id}/alternatives",
                           counts=counts)


def test_http_requires_authentication_before_counting_or_searching(http):
    assert http.client.post(http.url, json={}).status_code == 401 and not http.counts


def test_http_cookie_request_requires_the_existing_csrf_token(http):
    http.client.cookies.set("test_session", "synthetic")
    response = http.client.post(http.url, json={}, headers={"sec-fetch-site": "same-origin"})
    assert response.status_code == 403 and not http.counts


def test_http_honors_the_current_owner_and_counts_the_expensive_request(http, world):
    http.client.cookies.set("test_session", "synthetic")
    response = http.client.post(http.url, json={}, headers={"sec-fetch-site": "same-origin", "x-csrf-token": "valid-csrf"})
    assert response.status_code == 200 and response.json()["status"] == "offered"
    assert http.counts[0]["action"] == "risk_check"
    assert http.counts[0]["customer_id"] == world.owner
    world.trip["customer_id"] = uuid4()
    assert http.client.post(http.url, json={}, headers={"sec-fetch-site": "same-origin", "x-csrf-token": "valid-csrf"}).status_code == 404
    assert len(http.counts) == 1
