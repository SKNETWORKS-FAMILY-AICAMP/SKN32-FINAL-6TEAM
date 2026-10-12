"""꺼진 여행 담당 업무는 실행·입력 소비 없이 거절하고 원격 실패는 재시도한다."""
from __future__ import annotations

import asyncio
import logging
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.registry import TeamRegistry
from app.core.remote_team.executor import LocalTeamExecutor
from app.core.team_availability import TeamUnavailable
from app.core.transition import transition_case
from app.core.case_lifecycle.events import EventType
from app.application.case_service import ResumeTokenExpired
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.presentation.api.cases import build_router
from app.presentation.errors import install_error_handlers
from app.presentation.security import Principal
from .test_conversation_resume import travel, saved  # noqa: F401


def snapshot(tenant, case_id):
    with get_connection() as conn:
        case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
        events = repository.get_case_events(conn, tenant_id=tenant, case_id=case_id)
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM agent_runs WHERE tenant_id=%s AND case_id=%s ORDER BY started_at",
                        (tenant, case_id))
            runs = cur.fetchall()
    return case, events, runs


def unavailable(controller, team, reason):
    registry = TeamRegistry()
    if reason != "not_installed":
        registry.declare_unavailable(team.manifest.team_id, reason,
                                    manifest=team.manifest.model_copy(update={"active": False}))
    controller.registry = registry
    controller.team_executor = LocalTeamExecutor(registry)
    controller.composition_revision = "plugin-unavailable-test"


@pytest.mark.parametrize("reason", ["disabled", "not_installed", "load_failed"])
@pytest.mark.parametrize("with_token", [True, False])
def test_unavailable_resume_preserves_case_token_input_events_and_runs(travel, reason, with_token, caplog):
    controller, team, tenant, customer, case_id, first = travel
    before = snapshot(tenant, case_id)
    unavailable(controller, team, reason)
    route_calls, prepare_calls = [], []
    kwargs = dict(tenant_id=tenant, case_id=case_id, message="30분이요", event_id="plugin-reply",
                  resume_route=lambda *_: route_calls.append(True),
                  resume_prepare=lambda *_: prepare_calls.append(True))
    with caplog.at_level(logging.WARNING), pytest.raises(TeamUnavailable) as failure:
        asyncio.run(controller.resume(token=first["resume_token"], **kwargs) if with_token else
                    controller.resume_customer_input(customer_id=customer, **kwargs))
    assert failure.value.reason == reason
    assert snapshot(tenant, case_id) == before
    assert route_calls == prepare_calls == []
    assert len(team.tasks) == 1
    assert any(getattr(record, "composition_revision", None) == "plugin-unavailable-test"
               and getattr(record, "reason", None) == reason for record in caplog.records)


def test_selected_disabled_owner_cannot_prepare_candidates_or_consume_reply(travel):
    controller, team, tenant, _, case_id, first = travel
    target = team.manifest.model_copy(update={"team_id": "activity_plugin_test", "active": False,
                                             "capabilities": ["activity.change"], "accepted_case_types": ["activity"]})
    controller.registry.declare_unavailable(target.team_id, "disabled", manifest=target)
    before, calls = snapshot(tenant, case_id), []
    with pytest.raises(TeamUnavailable, match="disabled"):
        asyncio.run(controller.resume(tenant_id=tenant, case_id=case_id, token=first["resume_token"],
                    event_id="choose-activity", message="활동이요",
                    resume_route=lambda *_: target.team_id,
                    resume_prepare=lambda *_: calls.append("candidate_write")))
    assert calls == [] and snapshot(tenant, case_id) == before


def test_disabled_owner_preserves_case_even_when_valid_token_has_expired(travel, monkeypatch):
    controller, team, tenant, _, case_id, first = travel
    before = snapshot(tenant, case_id)
    unavailable(controller, team, "disabled")

    def expired(*args, **kwargs):
        raise ResumeTokenExpired("resume token expired")

    monkeypatch.setattr(controller.case_service, "validate_resume", expired)
    with pytest.raises(TeamUnavailable, match="disabled"):
        asyncio.run(controller.resume(tenant_id=tenant, case_id=case_id, token=first["resume_token"],
                                      message="30분이요", event_id="expired-disabled"))
    assert snapshot(tenant, case_id) == before


def test_preparation_runs_after_gate_and_before_input_is_persisted(travel):
    controller, team, tenant, _, case_id, first = travel
    observed = []

    def prepare(prospective, message):
        controller.require_team(prospective["owner_team_id"], case_id=case_id)
        durable = saved(tenant, case_id)
        observed.append((prospective["status"], prospective["state_json"]["customer_input"],
                         durable["status"], durable["state_json"].get("resume_token_used", False)))

    outcome = asyncio.run(controller.resume(tenant_id=tenant, case_id=case_id,
                          token=first["resume_token"], event_id="prepare-order", message="30분이요",
                          resume_prepare=prepare))
    assert outcome["status"] == "resolved"
    assert observed == [("resuming", "30분이요", "waiting_input", False)]


def test_web_dispatch_gate_precedes_candidate_writes_and_routed(monkeypatch):
    from app.domains.travel_ops.components.conversation import case_dispatch

    calls = []

    class DisabledController:
        def require_team(self, team_id, **_):
            raise TeamUnavailable(team_id, "disabled")

    monkeypatch.setattr(case_dispatch, "_prepare_candidates", lambda *a, **kw: calls.append("candidate_write"))
    monkeypatch.setattr(case_dispatch, "transition_case", lambda *a, **kw: calls.append("routed"))
    with pytest.raises(TeamUnavailable, match="disabled"):
        case_dispatch.execute(None, controller=DisabledController(), tenant="travel", trip={},
                              case_id=uuid4(), team="dining", request={}, actor_id="test")
    assert calls == []


def test_routing_disabled_owner_creates_no_run_and_never_reroutes(travel):
    controller, team, tenant, customer, _, _ = travel
    with get_connection() as conn:
        case_id = repository.create_case(conn, tenant_id=tenant, customer_id=customer, subject="식당 지연 확인")
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=0,
                        event_type=EventType.CREATED, payload={"channel": "web", "message": "식당 지연 확인"}, actor_type="test")
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=1,
                        event_type=EventType.CLASSIFIED,
                        payload={"intent": "incident_report", "issue_code": "dining_delay", "sentiment": "neutral"}, actor_type="test")
    unavailable(controller, team, "disabled")
    calls, before = [], snapshot(tenant, case_id)
    controller.reroute = lambda **_: calls.append(True)
    with pytest.raises(TeamUnavailable, match="disabled"):
        asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    assert calls == [] and snapshot(tenant, case_id) == before


def test_remote_unavailable_after_input_can_retry_same_event_without_second_input_event(travel):
    controller, team, tenant, _, case_id, first = travel
    local = controller.team_executor

    class RemoteUnavailableOnce:
        calls = 0

        async def execute(self, task):
            self.calls += 1
            if self.calls == 1:
                raise TeamUnavailable(task.team_id, "remote_unavailable")
            return await local.execute(task)

    remote = RemoteUnavailableOnce()
    controller.team_executor = remote
    kwargs = dict(tenant_id=tenant, case_id=case_id, token=first["resume_token"],
                  event_id="remote-reply", message="30분이요", expected_version=first["version"])
    with pytest.raises(TeamUnavailable, match="remote_unavailable"):
        asyncio.run(controller.resume(**kwargs))
    assert saved(tenant, case_id)["status"] == "running"
    assert snapshot(tenant, case_id)[2][-1] == ("failed",)
    outcome = asyncio.run(controller.resume(**kwargs))
    assert outcome["status"] == "resolved" and remote.calls == 2
    assert team.tasks[-1].resume is True and team.tasks[-1].resume_node == "validate_input"
    events = snapshot(tenant, case_id)[1]
    assert [event["event_type"] for event in events].count("valid_input") == 1
    assert saved(tenant, case_id)["state_json"]["customer_input_history"] == ["30분이요"]
    assert asyncio.run(controller.resume(**kwargs))["idempotent"] is True


def api(controller, tenant, classifier=None):
    application = FastAPI()
    application.include_router(build_router(controller=controller, classifier=classifier))
    install_error_handlers(application)
    for route in application.routes:
        if getattr(route, "dependant", None):
            for dependency in route.dependant.dependencies:
                application.dependency_overrides[dependency.call] = lambda: Principal(
                    tenant_id=tenant, key_id="plugin-test", scopes=frozenset({"case:write", "case:read"}))
    return application


def test_message_http503_and_read_view_expose_unavailable_without_consuming_token(travel):
    controller, team, tenant, _, case_id, first = travel
    before = snapshot(tenant, case_id)
    unavailable(controller, team, "disabled")
    with TestClient(api(controller, tenant)) as client:
        response = client.post(f"/v1/cases/{case_id}/messages", json={
            "request_id": "http-plugin-reply", "message": "30분이요", "token": first["resume_token"]})
        view = client.get(f"/v1/cases/{case_id}")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "team_unavailable"
    assert response.json()["error"]["retryable"] is False
    assert view.status_code == 200 and view.json()["execution_error"]["reason"] == "disabled"
    assert snapshot(tenant, case_id) == before


def test_new_case_unavailable503_can_be_retried_after_reactivation(travel):
    controller, team, tenant, customer, _, _ = travel
    available_registry = controller.registry
    unavailable(controller, team, "disabled")
    application = api(controller, tenant, classifier=lambda _: {
        "intent": "incident_report", "issue_code": "dining_delay", "sentiment": "neutral"})
    body = {"request_id": uuid4().hex, "message": "식당에 늦을 것 같아요", "channel": "web",
            "customer_id": str(customer)}
    with TestClient(application) as client:
        rejected = client.post("/v1/cases", json=body)
        assert rejected.status_code == 503, rejected.text
        case_id = UUID(rejected.json()["error"]["case_id"])
        assert snapshot(tenant, case_id)[2] == []
        assert saved(tenant, case_id)["status"] == "routing"
        controller.registry = available_registry
        controller.team_executor = LocalTeamExecutor(available_registry)
        retried = client.post("/v1/cases", json=body)
    assert retried.status_code == 201 and retried.json()["case_id"] == str(case_id)
    assert saved(tenant, case_id)["status"] == "waiting_input"
    assert len(snapshot(tenant, case_id)[2]) == 1


@pytest.fixture
def changing_trip(travel):
    """실제 일정 버전과 Core 적용 장부를 함께 확인하는 재개 시험 장치."""
    from datetime import UTC, datetime, timedelta
    from dataclasses import replace
    from app.core.actions import ActionHandlers, AppliedAction
    from app.core.contracts import ActionProposal
    from app.domains.travel_ops.components.itinerary.itinerary import Item, TripStore

    controller, team, tenant, customer, case_id, _ = travel
    store = TripStore(tenant)
    item = Item(uuid4(), 1, "dining", "서울 점심", None,
                datetime(2026, 10, 20, 3, tzinfo=UTC), datetime(2026, 10, 20, 4, tzinfo=UTC))
    with get_connection() as conn:
        trip_id, version = store.create_trip(conn, customer_id=customer, title="서울 일정 재개",
                                             locale="ko", party_size=1, items=[item])
    assert version == 1

    class Change:
        action_type = "travel.acceptance_delay"
        auto_apply = True
        calls = 0

        def subject(self, arguments):
            return arguments["trip_id"]

        def apply(self, conn, **kwargs):
            self.calls += 1
            new_version = store.append_version(conn, trip_id=trip_id, base_version=1,
                items=[replace(item, starts_at=item.starts_at + timedelta(minutes=30),
                               ends_at=item.ends_at + timedelta(minutes=30))],
                reason="고객 지연 답변", causes=[], case_id=case_id)
            return AppliedAction(result_ref=f"trip:{trip_id}:v{new_version}")

    handler = Change()
    controller.action_handlers = ActionHandlers([handler])
    original = team.execute

    async def execute(task):
        result = await original(task)
        return result.model_copy(update={"action_proposals": [ActionProposal(
            action_type=handler.action_type, arguments={"trip_id": str(trip_id)},
            idempotency_key="untrusted-team-key", approval_required=False, risk_level="low")]})

    team.execute = execute
    try:
        yield store, trip_id, item, handler
    finally:
        with get_connection() as conn, conn.cursor() as cur:
            for table in ("itinerary_items", "itinerary_versions", "trips"):
                cur.execute(f"DELETE FROM {table} WHERE tenant_id=%s AND trip_id=%s", (tenant, trip_id))


def assert_trip_changed_once(tenant, case_id, changing_trip):
    from datetime import timedelta

    store, trip_id, original, handler = changing_trip
    with get_connection() as conn:
        trip, items = store.latest(conn, trip_id)
        assert [v["version"] for v in store.versions(conn, trip_id)] == [1, 2]
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM action_requests WHERE tenant_id=%s AND case_id=%s AND status='succeeded'",
                        (tenant, case_id))
            assert cur.fetchone()[0] == 1
    assert trip["version"] == 2 and handler.calls == 1
    assert items[0].starts_at == original.starts_at + timedelta(minutes=30)


def test_reactivation_same_reply_changes_real_itinerary_only_once(travel, changing_trip):
    controller, team, tenant, _, case_id, first = travel
    registry = controller.registry
    before = snapshot(tenant, case_id)
    kwargs = dict(tenant_id=tenant, case_id=case_id, token=first["resume_token"],
                  event_id="same-delay-reply", message="30분이요", expected_version=first["version"])
    unavailable(controller, team, "disabled")
    with pytest.raises(TeamUnavailable, match="disabled"):
        asyncio.run(controller.resume(**kwargs))
    assert snapshot(tenant, case_id) == before
    controller.registry = registry
    controller.team_executor = LocalTeamExecutor(registry)
    assert registry.contract_version == "1.0"
    assert asyncio.run(controller.resume(**kwargs))["status"] == "resolved"
    assert asyncio.run(controller.resume(**kwargs))["idempotent"] is True
    assert_trip_changed_once(tenant, case_id, changing_trip)


def test_inflight_disable_keeps_old_team_and_applies_real_itinerary_once(travel, changing_trip, caplog):
    from app.application.controller import Controller
    from app.application.runtime import ControllerProxy, RuntimeComposition
    from app.core.service_bindings import BindingTable, current_bindings

    controller, team, tenant, _, case_id, first = travel
    controller.composition_revision = "acceptance-old"
    controller.service_bindings = BindingTable({}, controller.registry, "acceptance-old")
    off = Controller(TeamRegistry())
    off.composition_revision = "acceptance-off"
    off.service_bindings = BindingTable({}, off.registry, "acceptance-off")
    runtime = RuntimeComposition(controller, "acceptance-old")
    proxy = ControllerProxy(runtime)
    original = team.execute
    observed = []

    async def experiment():
        started, finish = asyncio.Event(), asyncio.Event()

        async def blocked(task):
            observed.append(current_bindings().revision)
            started.set()
            await finish.wait()
            observed.append(current_bindings().revision)
            return await original(task)

        team.execute = blocked
        kwargs = dict(tenant_id=tenant, case_id=case_id, token=first["resume_token"],
                      event_id="inflight-delay-reply", message="30분이요")

        async def old_request():
            with runtime.pin():
                result = await proxy.resume(**kwargs)
                observed.append(runtime.active_revision)
                assert (await proxy.resume(**kwargs))["idempotent"] is True
                return result

        pending = asyncio.create_task(old_request())
        await asyncio.wait_for(started.wait(), timeout=5)
        runtime.swap(off, "acceptance-off")
        try:
            with runtime.pin(), pytest.raises(TeamUnavailable, match="not_installed"):
                proxy.require_team(team.manifest.team_id, "dining.delay")
        finally:
            finish.set()
        assert (await asyncio.wait_for(pending, timeout=5))["status"] == "resolved"

    with caplog.at_level(logging.INFO):
        asyncio.run(experiment())
    assert observed == ["acceptance-old"] * 3
    assert runtime.active_revision == "acceptance-off"
    assert_trip_changed_once(tenant, case_id, changing_trip)
    assert any(record.msg == "controller_call_finished"
               and record.operation == "resume" and record.call_outcome == "returned"
               and record.composition_revision == "acceptance-old" for record in caplog.records)
    assert current_bindings() is None


def test_unavailable_at_final_route_gate_leaves_no_owner_or_candidate_write(travel, monkeypatch):
    from app.domains.travel_ops.components.conversation import case_dispatch

    controller, team, tenant, customer, _, _ = travel
    with get_connection() as conn:
        case_id = repository.create_case(conn, tenant_id=tenant, customer_id=customer, subject="식당 지연")
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=0,
                        event_type=EventType.CREATED, payload={"channel": "web", "message": "식당 지연"}, actor_type="test")
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=1,
                        event_type=EventType.CLASSIFIED,
                        payload={"intent": "incident_report", "issue_code": "dining_delay", "sentiment": "neutral"}, actor_type="test")
    before = snapshot(tenant, case_id)
    original, gates, writes = controller.require_team, [], []

    def final_gate(team_id, capability=None, **kwargs):
        gates.append(capability)
        if capability is not None:
            raise TeamUnavailable(team_id, "disabled")
        return original(team_id, capability, **kwargs)

    monkeypatch.setattr(controller, "require_team", final_gate)
    monkeypatch.setattr(case_dispatch, "_prepare_candidates", lambda *a, **kw: writes.append(True))
    with get_connection() as conn, pytest.raises(TeamUnavailable, match="disabled"):
        case_dispatch.execute(conn, controller=controller, tenant=tenant, trip={}, case_id=case_id,
                              team=team.manifest.team_id, request={}, actor_id="test")
    assert gates == [None, "dining.delay"] and writes == []
    assert snapshot(tenant, case_id) == before
    assert saved(tenant, case_id)["owner_team_id"] is None


@pytest.mark.parametrize("failure_kind", ["import", "constructor"])
def test_optional_load_failure_keeps_independent_team_executable(monkeypatch, caplog, failure_kind):
    from app import composition
    from app.core.project_config import config_from_declaration
    from tests.unit.core.test_plugin_availability import Team, declaration, task, team_config

    independent = Team(team_id="activity")

    class Broken:
        def __init__(self):
            raise RuntimeError("optional constructor rejected")

    def load(ref, team_id):
        if team_id == "activity":
            return lambda: independent
        if failure_kind == "import":
            raise ImportError("optional package absent")
        return Broken

    monkeypatch.setattr(composition, "_import_ref", load)
    config = config_from_declaration(declaration([
        team_config(required=False, capabilities=["mobility.itinerary"]),
        team_config(team_id="activity", implementation_ref="travel.activity:Team")]), source="acceptance")
    with caplog.at_level(logging.ERROR):
        registry = composition.build_registry(config=config, tools=object(), llm=object())
    with pytest.raises(TeamUnavailable, match="load_failed"):
        registry.require_runnable("mobility")
    request = task().model_copy(update={"team_id": "activity", "capability": "activity.itinerary"})
    request.context.team_id = "activity"
    outcome = asyncio.run(LocalTeamExecutor(registry).execute(request))
    assert outcome.outcome == "completed" and independent.calls == 1
    assert any("optional_team_load_failed" in record.getMessage()
               and "mobility" in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize("failure_kind", ["duplicate_capability", "incompatible_contract"])
def test_invalid_candidate_keeps_published_controller_hooks_revision(monkeypatch, failure_kind):
    from app import composition
    from app.application.runtime import RuntimeComposition
    from app.core.project_config import config_from_declaration
    from app.core.registry import RegistryError
    from app.core.service_bindings import current_bindings
    from tests.unit.core.test_plugin_availability import Team, declaration, team_config
    from tests.unit.test_plugin_composition_runtime import controller as bound_controller

    runtime = RuntimeComposition(bound_controller("acceptance-preserved"), "acceptance-preserved")
    before = runtime.published_snapshot()
    config = config_from_declaration(declaration([
        team_config(required=False), team_config(team_id="activity", required=False,
                                                implementation_ref="travel.activity:Team")]), source="acceptance")

    def load(ref, team_id):
        if team_id == "activity":
            return lambda: Team(team_id="activity", capabilities=["mobility.itinerary"])
        return lambda: Team(supported_contract_versions=["2.0"] if failure_kind == "incompatible_contract" else ["1.0"])

    monkeypatch.setattr(composition, "_import_ref", load)

    @runtime.serialize_reload
    def reload():
        candidate_registry = composition.build_registry(config=config, tools=object(), llm=object())
        # 잘못된 후보는 여기까지 도달하지 않아 기존 게시물에 섞이지 않는다.
        candidate = bound_controller("candidate")
        candidate.registry = candidate_registry
        runtime.swap(candidate, "candidate")

    with pytest.raises((composition.CompositionError, RegistryError)):
        reload()
    assert runtime.published_snapshot() is before
    assert runtime.controller is before.controller
    assert runtime.controller.service_bindings is before.controller.service_bindings
    with runtime.pin():
        assert current_bindings().revision == "acceptance-preserved"
        assert current_bindings().values[("legs", "leg_planner")]() == "acceptance-preserved"


def test_removed_team_rejects_only_its_business_and_independent_team_runs():
    from tests.unit.core.test_plugin_availability import Team, task

    team = Team()
    registry = TeamRegistry([team])
    with pytest.raises(TeamUnavailable, match="not_installed"):
        registry.require_runnable("dining")
    outcome = asyncio.run(LocalTeamExecutor(registry).execute(task()))
    assert outcome.outcome == "completed" and team.calls == 1


def test_independent_candidate_sort_omits_similarity_without_replacing_activity_business(caplog):
    from datetime import UTC, datetime, timedelta
    from app.core.service_bindings import BindingTable, bind_services
    from app.domains.travel_ops.components.planning.replan import Candidate, activity_candidates
    from app.domains.travel_ops.components.team_hooks import similarity
    from tests.unit.core.test_plugin_availability import Team, task

    disabled = Team(team_id="activity", active=False)
    registry = TeamRegistry([disabled])
    origin = {"place_id": "original", "name": "서울 원래 장소", "kind": "activity",
              "latitude": 37.57, "longitude": 126.98, "attributes": {"price_krw": 0}}
    places = [{**origin, "place_id": name, "name": name, "latitude": 37.57 + offset}
              for name, offset in (("far", .003), ("near", .001))]
    start = datetime(2026, 10, 20, 3, tzinfo=UTC)
    with caplog.at_level(logging.INFO), bind_services(BindingTable({}, registry, "sort-off")):
        scorer = similarity.scorer(None)
        assert scorer is None
        candidates = activity_candidates(original=origin, places=places, start=start,
            end=start + timedelta(hours=1), causes=[], similarity=scorer, proposal=True)
        assert [candidate.key for candidate in sorted(candidates, key=Candidate.rank)] == ["near", "far"]
        request = task().model_copy(update={"team_id": "activity", "capability": "activity.itinerary"})
        with pytest.raises(TeamUnavailable, match="disabled"):
            asyncio.run(LocalTeamExecutor(registry).execute(request))
    assert disabled.calls == 0
    assert any(record.msg == "optional_service_omitted" and record.reason == "provider_unavailable"
               and record.composition_revision == "sort-off" for record in caplog.records)


@pytest.mark.parametrize("deadline_seconds", [.06, .08, .1])
@pytest.mark.parametrize("hanging_cancel", [False, True])
def test_controller_remote_deadline_leaves_budget_for_cancel_and_original_failure(
        travel, monkeypatch, caplog, deadline_seconds, hanging_cancel):
    from types import SimpleNamespace
    import app.application.controller as controller_module
    from app.core.remote_team.a2a_executor import A2ATeamExecutor

    controller, team, tenant, _, case_id, first = travel
    actual_guardrails = controller_module.get_guardrails()
    limits = {"reliability.team_timeout_seconds": deadline_seconds,
              "reliability.team_cleanup_grace_seconds": .05}
    monkeypatch.setattr(controller_module, "get_guardrails", lambda: SimpleNamespace(
        get=lambda key: limits[key] if key in limits else actual_guardrails.get(key)))

    class Transport:
        submit_calls = cancel_started = cancel_finished = 0

        async def submit(self, endpoint, task):
            self.submit_calls += 1
            return {"status": "working", "id": str(task.task_id)}

        async def poll(self, remote, task):
            await asyncio.Event().wait()

        async def cancel(self, remote):
            self.cancel_started += 1
            if hanging_cancel:
                await asyncio.Event().wait()
            else:
                await asyncio.sleep(.02)
            self.cancel_finished += 1

    transport = Transport()
    controller.team_executor = A2ATeamExecutor(transport, lambda _: "test-endpoint",
        registry=controller.registry, cancel_timeout_seconds=.25)
    with caplog.at_level(logging.WARNING):
        result = asyncio.run(controller.resume(tenant_id=tenant, case_id=case_id,
            token=first["resume_token"], event_id="deadline-reply", message="30분이요"))
    assert transport.submit_calls == transport.cancel_started == 1
    assert transport.cancel_finished == (0 if hanging_cancel else 1)
    assert result["status"] == "escalated"
    events = snapshot(tenant, case_id)[1]
    last = events[-1]
    assert last["payload_json"]["guardrail"] == "remote_deadline_exceeded"
    assert saved(tenant, case_id)["status"] == "escalated"
    if hanging_cancel:
        assert any(record.msg == "a2a_cancel_failed" and record.error_type == "TimeoutError"
                   for record in caplog.records)


@pytest.mark.parametrize("budget", [-1, float("nan"), float("inf"), "invalid"])
def test_invalid_cleanup_budget_is_rejected_before_executor_call(budget):
    from app.application.controller import Controller, ControllerError
    from tests.unit.core.test_plugin_availability import task

    class Executor:
        cleanup_budget_seconds = budget
        calls = 0

        async def execute(self, task):
            self.calls += 1
            pytest.fail("invalid execution contract must fail before invocation")

    executor = Executor()
    controller = Controller(TeamRegistry(), team_executor=executor)
    with pytest.raises(ControllerError, match="cleanup budget"):
        asyncio.run(controller._execute_team_task(task()))
    assert executor.calls == 0
