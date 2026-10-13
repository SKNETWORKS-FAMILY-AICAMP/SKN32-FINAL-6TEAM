"""실제 여행 HTTP 처리기에서 필수 Team 계산과 독립 읽기를 구분한다."""
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import composition
from app.core.registry import TeamRegistry
from app.core.service_bindings import BindingTable, bind_services, collect_services, standalone_services
from app.core.team_availability import TeamUnavailable
from app.domains.travel_ops.components.itinerary.itinerary_checks import Part, with_ledger
from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.team_hooks import dining_ledger, mobility_shapes
from app.domains.travel_ops.entry import trip_api
from app.domains.travel_ops.instances.dining import ledger
from app.domains.travel_ops.instances.mobility import route_shape
from app.domains.travel_ops.modules.web_account import web_guard
from app.presentation.errors import install_error_handlers
from app.presentation.security import Principal
from tests.unit.core.test_plugin_availability import Team


@pytest.fixture
def http_boundary(monkeypatch):
    customer, trip_id = uuid4(), uuid4()
    calls = []
    items = [SimpleNamespace(seq=0, kind="activity", title="출발", item_id=uuid4(),
                place={"name": "출발", "latitude": 37.57, "longitude": 126.98}, detail={}),
             SimpleNamespace(seq=1, kind="mobility", title="도보", item_id=uuid4(), place=None,
                detail={"route_def": {"planned": "walk", "options": [{"id": "walk"}]}}),
             SimpleNamespace(seq=2, kind="activity", title="도착", item_id=uuid4(),
                place={"name": "도착", "latitude": 37.571, "longitude": 126.981}, detail={})]
    for index, item in enumerate(items):
        item.starts_at = datetime.fromisoformat('2026-10-12T12:00:00+09:00') + timedelta(minutes=30*index)
        item.ends_at = item.starts_at + timedelta(minutes=20)
    items = [Item(item_id=i.item_id, seq=i.seq, kind=i.kind, title=i.title, place_id=None,
                  starts_at=i.starts_at, ends_at=i.ends_at, detail=i.detail, place=i.place) for i in items]
    saved = {"trip_id": trip_id, "customer_id": customer, "title": "저장된 서울 여행",
             "locale": "ko", "party_size": 2, "version": 1, "constraints": {}}
    class Cursor:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def execute(self, sql, *args):
            if "FROM dining.dn_place" in sql:
                calls.append("dining_sql")
            elif "FROM trip_intakes" in sql:
                calls.append("intake_read")
            else:
                pytest.fail("unexpected SQL in synthetic fixture")
        def fetchall(self):
            return [(True, False)]
        def fetchone(self):
            return ("review", 1)
    class Connection:
        def cursor(self):
            return Cursor()
    @contextmanager
    def connection():
        calls.append("connection")
        yield Connection()
    class Store:
        def __init__(self, tenant):
            self.tenant_id = tenant
        def latest(self, conn, identifier):
            return saved, items
        def versions(self, conn, identifier):
            return []
    class Router:
        def route(self, a, b, profile):
            calls.append("mobility_graph_route")
            return {"paths": [{"points": {"coordinates": [list(a), list(b)]}}]}
    monkeypatch.setattr(trip_api, "get_connection", connection)
    monkeypatch.setattr(trip_api, "TripStore", Store)
    monkeypatch.setattr(web_guard, "assert_human_check_configured", lambda: None)
    monkeypatch.setattr(route_shape, "_engine", lambda: (Router(), None))
    monkeypatch.setattr(route_shape, "_line_order", lambda: None)
    from app.domains.travel_ops.components.intake import review
    monkeypatch.setattr(review, "load", lambda *a: {"items": [
        {"id": "a", "place": {"latitude": 37.57, "longitude": 126.98}},
        {"id": "b", "place": {"latitude": 37.571, "longitude": 126.981}}],
        "moves": [{"from": "a", "to": "b", "mode": "walk"}]})
    def client(table):
        router = trip_api.build_trip_router()
        app = FastAPI()
        app.include_router(router)
        install_error_handlers(app)
        for route in router.routes:
            if route.path in {"/v1/trips", "/v1/trips/plan"}:
                app.dependency_overrides[route.dependant.dependencies[0].call] = lambda: Principal(
                    "synthetic-travel", frozenset({"trip:write"}), "synthetic")
            elif route.path in {"/v1/web/trips/{trip_id}/route-shapes", "/v1/web/trips/{trip_id}",
                               "/v1/web/trip-intakes/{intake_id}/route-shapes",
                               "/v1/web/trip-intakes/{intake_id}/edits"}:
                app.dependency_overrides[route.dependant.dependencies[0].call] = lambda: ("synthetic-travel", customer)
        @app.middleware("http")
        async def bind(request, call_next):
            with bind_services(table):
                return await call_next(request)
        return TestClient(app)
    meal = {"request_id": "synthetic-review", "customer_id": str(customer), "title": "합성 식사 검증",
        "places": [{"key": "meal", "name": "합성 식당", "kind": "dining", "lat": 37.57, "lon": 126.98,
                    "attributes": {"dining_place_uid": str(uuid4())}}],
        "items": [{"seq": 1, "kind": "dining", "title": "합성 식사", "place": "meal",
                   "starts_at": "2026-10-12T12:00:00+09:00", "ends_at": "2026-10-12T13:00:00+09:00"}]}
    values = {("dining_ledger", "slot_verdicts"): ledger.slot_verdicts,
              ("mobility_shapes", "items"): route_shape.shapes_for_items,
              ("mobility_shapes", "review"): route_shape.shapes_for_review}
    return SimpleNamespace(client=client, calls=calls, meal=meal, values=values, trip_id=trip_id,
                           items=items, saved=saved)


def registry_for(reason):
    registry = TeamRegistry()
    if reason != "not_installed":
        for owner in ("dining", "mobility"):
            registry.declare_unavailable(owner, reason)
    return registry


@pytest.mark.parametrize("reason", ["disabled", "not_installed", "load_failed"])
@pytest.mark.parametrize("route", ["meal", "trip-shapes", "intake-shapes"])
def test_actual_http_rejects_unavailable_owner_before_domain_io(http_boundary, reason, route):
    f = http_boundary
    # Even a stale available callback cannot bypass the current Registry gate.
    with f.client(BindingTable(f.values, registry_for(reason), "off")) as client:
        response = client.post("/v1/trips", json=f.meal) if route == "meal" else client.get(
            f"/v1/web/trips/{f.trip_id}/route-shapes" if route == "trip-shapes" else
            f"/v1/web/trip-intakes/{uuid4()}/route-shapes")
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["team_id"] == ("dining" if route == "meal" else "mobility")
    assert error["reason"] == reason and error["code"] == "team_unavailable"
    assert "dining_sql" not in f.calls and "mobility_graph_route" not in f.calls
    if route == "meal":
        assert f.calls == []


@pytest.mark.parametrize("route", ["meal", "trip-shapes", "intake-shapes"])
def test_active_http_keeps_original_ledger_and_graph_algorithms(http_boundary, route):
    f = http_boundary
    registry = TeamRegistry([Team(team_id="dining"), Team(team_id="mobility")])
    with f.client(BindingTable(f.values, registry, "on")) as client:
        response = client.post("/v1/trips", json=f.meal) if route == "meal" else client.get(
            f"/v1/web/trips/{f.trip_id}/route-shapes" if route == "trip-shapes" else
            f"/v1/web/trip-intakes/{uuid4()}/route-shapes")
    if route == "meal":
        # Real Dining SQL result still rejects a closed meal before persistence.
        assert response.status_code == 422
        assert "dining_sql" in f.calls
        assert response.json()["error"]["code"] == "itinerary_infeasible"
    else:
        assert response.status_code == 200
        assert response.json()["shapes"][0]["source"] == "local_road_graph"
        assert "mobility_graph_route" in f.calls


@pytest.mark.parametrize("reason", ["disabled", "not_installed"])
def test_actual_saved_trip_read_remains_independent(http_boundary, monkeypatch, reason):
    f = http_boundary
    f.items.clear()
    monkeypatch.setattr(trip_api.safety_pause, "view", lambda *a, **k: {"paused": False})
    monkeypatch.setattr(trip_api.guardian_module, "view", lambda *a, **k: {"enabled": False})
    with f.client(BindingTable({}, registry_for(reason), "off")) as client:
        response = client.get(f"/v1/web/trips/{f.trip_id}")
    assert response.status_code == 200 and response.json()["title"] == "저장된 서울 여행"
    assert f.calls == ["connection", "intake_read"]  # 저장된 접수 연결만 읽으며 Team 계산은 하지 않는다.


@pytest.mark.parametrize("key", ["lookup_factory", "slot_verdicts", "planner_factory", "link_core_place", "closure_observation"])
def test_dining_http_provider_uses_pinned_callable_and_arguments(key):
    calls = []
    provider = lambda *args, **kwargs: calls.append((args, kwargs)) or "pinned"
    registry = TeamRegistry([Team(team_id="dining")])
    with bind_services(BindingTable({("dining_ledger", key): provider}, registry, "pinned")):
        assert getattr(dining_ledger, key)("argument", marker=7) == "pinned"
    assert calls == [(("argument",), {"marker": 7})]


def test_real_assembly_captures_original_providers_without_changing_legacy_globals():
    old_items = mobility_shapes._items
    with collect_services() as values:
        composition._wire_domain_providers(active_ids={"dining", "mobility"})
    assert values[("dining_ledger", "slot_verdicts")] is ledger.slot_verdicts
    assert values[("dining_ledger", "planner_factory")] is ledger.PlannerLedger
    assert values[("dining_ledger", "link_core_place")] is ledger.link_core_place_to
    assert values[("dining_ledger", "closure_observation")] is ledger.closure_observation
    assert values[("mobility_shapes", "items")] is route_shape.shapes_for_items
    assert values[("mobility_shapes", "review")] is route_shape.shapes_for_review
    assert mobility_shapes._items is old_items


@pytest.mark.parametrize("hook", [lambda: dining_ledger.lookup_factory(None),
                                  lambda: mobility_shapes.items([])])
def test_non_standalone_unbound_http_hook_never_uses_legacy_provider(hook):
    with standalone_services(False), pytest.raises(TeamUnavailable, match="composition_unbound"):
        hook()


def test_ledger_unavailable_is_not_converted_to_unknown_success():
    from datetime import datetime
    part = Part(seq=1, kind="dining", title="식사", starts_at=datetime(2026, 10, 12, 12),
                place={"attributes": {"dining_place_uid": str(uuid4())}})
    def unavailable(slots):
        raise TeamUnavailable("dining", "disabled")
    with pytest.raises(TeamUnavailable, match="disabled"):
        with_ledger([part], unavailable)


def test_activity_only_resolve_does_not_load_disabled_dining_factory():
    from app.domains.travel_ops.components.intake.places import resolve
    calls = []
    def forbidden_factory(*args, **kwargs):
        calls.append("dining_factory")
        pytest.fail("independent Activity intake must not acquire Dining")
    tour = SimpleNamespace(misses={}, find=lambda *a, **k: {
        "matched_title": "경복궁", "content_id": "synthetic-palace", "content_type_id": "12",
        "latitude": 37.577, "longitude": 126.976, "address": "서울특별시 종로구"})
    table = BindingTable({("dining_ledger", "lookup_factory"): forbidden_factory},
                         registry_for("disabled"), "off")
    with bind_services(table):
        result = resolve("경복궁", our_places=[], tour=tour, dining=trip_api._dining_lookup(), kind_hint="activity")
    assert result.status == "resolved" and result.kind == "activity"
    assert calls == []


def test_deferred_real_dining_lookup_still_checks_owner_before_factory():
    calls = []
    table = BindingTable({("dining_ledger", "lookup_factory"): lambda *a, **k: calls.append("factory")},
                         registry_for("disabled"), "off")
    with bind_services(table):
        lookup = trip_api._dining_lookup()
        assert lookup.misses == {}
        with pytest.raises(TeamUnavailable, match="disabled"):
            lookup.find("점심 식당")
    assert calls == []


@pytest.mark.parametrize("reason", ["disabled", "not_installed", "load_failed"])
@pytest.mark.parametrize("route", ["lookup", "planner", "uid-link"])
def test_remaining_dining_hooks_reject_from_actual_http(http_boundary, monkeypatch, reason, route):
    from app.domains.travel_ops.components.intake import pipeline, places

    f = http_boundary
    calls = []
    def forbidden(*args, **kwargs):
        calls.append("provider")
        pytest.fail("unavailable provider must not execute")
    values = {("dining_ledger", key): forbidden for key in
              ("lookup_factory", "planner_factory", "link_core_place")}
    # Synthetic intake persistence seam; use the actual name-resolution calculation.
    def edited(conn, **kwargs):
        return places.resolve("점심 합성 식당", our_places=[], dining=kwargs["dining"], kind_hint="dining")
    monkeypatch.setattr(pipeline, "edit", edited)
    with f.client(BindingTable(values, registry_for(reason), "off")) as client:
        if route == "lookup":
            response = client.post(f"/v1/web/trip-intakes/{uuid4()}/edits", json={
                "revision": 1, "edits": [{"field": "items[0].place", "value": "합성 식당"}]})
        elif route == "planner":
            response = client.post("/v1/trips/plan", json={"request_id": "synthetic-plan",
                "customer_id": str(f.saved["customer_id"]), "start_date": "2026-10-12", "days": 1,
                "party_size": 2})
        else:
            body = {**f.meal, "items": [{**f.meal["items"][0], "kind": "activity"}]}
            response = client.post("/v1/trips", json=body)
    assert response.status_code == 503
    assert response.json()["error"]["reason"] == reason
    assert response.json()["error"]["team_id"] == "dining"
    assert calls == [] and "dining_sql" not in f.calls
    if route != "lookup":
        assert f.calls == []


@pytest.mark.parametrize("reason", ["disabled", "not_installed"])
def test_no_saved_review_returns_empty_shapes_without_mobility_calculation(http_boundary, monkeypatch, reason):
    from app.domains.travel_ops.components.intake import review

    f = http_boundary
    monkeypatch.setattr(review, "load", lambda *args: None)
    def forbidden(*args, **kwargs):
        pytest.fail("a missing stored review is a pure empty read")
    values = {("mobility_shapes", "review"): forbidden}
    with f.client(BindingTable(values, registry_for(reason), "off")) as client:
        response = client.get(f"/v1/web/trip-intakes/{uuid4()}/route-shapes")
    assert response.status_code == 200 and response.json()["shapes"] == []
    assert f.calls == ["connection", "intake_read"]


def test_default_engine_preserves_non_standalone_unbound_failure():
    from app.domains.travel_ops.components.intake.review import default_engine

    with standalone_services(False), pytest.raises(TeamUnavailable, match="composition_unbound"):
        default_engine(2)
