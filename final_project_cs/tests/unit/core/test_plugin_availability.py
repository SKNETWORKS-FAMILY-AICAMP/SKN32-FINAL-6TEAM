"""Travel plugin availability contract, without database or external network."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.contracts import ContextPack, Evidence, NextAction, TeamManifest, TeamResult, TeamTask
from app.core.project_config import ProjectConfigError, config_from_declaration
from app.core.registry import RegistryError, TeamRegistry
from app.core.remote_team.a2a_executor import A2ATeamExecutor
from app.core.remote_team.executor import LocalTeamExecutor, ToolScopeViolation
from app.core.team_availability import TeamContractViolation, TeamUnavailable


def manifest(team_id="mobility", **overrides):
    fields = dict(team_id=team_id, display_name=team_id, contract_name="a_cop.team_task",
                  supported_contract_versions=["1.0"], capabilities=[f"{team_id}.itinerary"],
                  accepted_case_types=[team_id], required_context=[], allowed_tools=[],
                  knowledge_scope=[], implementation_revision="availability-test")
    fields.update(overrides)
    return TeamManifest(**fields)


def task():
    case_id = uuid4()
    context = ContextPack(pack_id=uuid4(), case_id=case_id, team_id="mobility", tenant_id="travel-test",
                          knowledge_scope=[], current_state={}, estimated_input_tokens=1)
    return TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id="mobility",
                    capability="mobility.itinerary", case_version=1, input_text="이동 경로를 확인해 주세요",
                    context=context, allowed_tools=[], deadline_at=datetime.now(UTC) + timedelta(seconds=2))


class Team:
    def __init__(self, **overrides):
        self.manifest = manifest(**overrides)
        self.calls = 0

    async def execute(self, value):
        self.calls += 1
        return TeamResult(task_id=value.task_id, run_id=value.run_id, team_id=value.team_id,
                          outcome="completed", answer="경로 확인", confidence=1, evidence=[Evidence(evidence_id="travel-route-fixture", source_type="db", source_id="travel-route-fixture", claim="시험용 이동 경로", value={"duration_min": 12}, confidence=1, observed_at=datetime(2026, 10, 11, tzinfo=UTC))], next_action=NextAction.RESPOND)


def declaration(teams):
    return dict(modules={}, ports=dict(team_executor="local", message_broker="outbox", graph_store="sql"),
                teams=teams)


def team_config(**overrides):
    fields = dict(team_id="mobility", active=True, implementation_ref="missing.travel:MobilityTeam")
    fields.update(overrides)
    return fields


@pytest.mark.parametrize("reason", ["disabled", "not_installed", "load_failed", "remote_unavailable"])
def test_declared_unavailable_is_operational(reason):
    registry = TeamRegistry()
    registry.declare_unavailable("mobility", reason, capabilities=["mobility.itinerary"])
    with pytest.raises(TeamUnavailable) as caught:
        registry.require_runnable("mobility")
    assert (caught.value.team_id, caught.value.reason, caught.value.code) == ("mobility", reason, "team_unavailable")
    assert not isinstance(caught.value, ValueError)
    with pytest.raises(TeamUnavailable):
        registry.resolve(case_type="mobility")


def test_unknown_team_execution_is_not_installed_and_metadata_remains_registry_error():
    registry = TeamRegistry()
    with pytest.raises(TeamUnavailable, match="not_installed"):
        registry.require_runnable("mobility")
    with pytest.raises(RegistryError, match="unknown team"):
        registry.get("mobility")


def test_inactive_metadata_remains_readable_but_never_runnable():
    registry = TeamRegistry([Team(active=False)])
    assert not registry.get("mobility").manifest.active
    with pytest.raises(TeamUnavailable, match="disabled"):
        registry.require_runnable("mobility")
    with pytest.raises(TeamUnavailable, match="disabled"):
        registry.resolve(case_type="mobility")


def test_unavailable_metadata_registration_does_not_require_implementation():
    registry = TeamRegistry()
    registry.declare_unavailable("mobility", "disabled", manifest=manifest(active=False))
    assert registry.get("mobility").manifest.team_id == "mobility"
    with pytest.raises(TeamUnavailable):
        registry.require_runnable("mobility")


def test_disabled_declaration_without_capabilities_blocks_matching_business():
    registry = TeamRegistry()
    registry.declare_unavailable("mobility", "disabled")
    with pytest.raises(TeamUnavailable, match="disabled"):
        registry.resolve(case_type="mobility")


def test_loaded_plugin_hook_failure_can_be_marked_unavailable_and_diagnostics_are_detached():
    registry = TeamRegistry([Team()])
    registry.declare_unavailable("mobility", "load_failed")
    assert registry.get("mobility").manifest.active
    with pytest.raises(TeamUnavailable, match="load_failed"):
        registry.require_runnable("mobility")
    snapshot = registry.availability()
    assert snapshot["mobility"] == dict(available=False, reason="load_failed", capabilities=["mobility.itinerary"])
    snapshot["mobility"]["capabilities"].clear()
    assert registry.availability()["mobility"]["capabilities"] == ["mobility.itinerary"]


def test_removed_team_is_unavailable_and_duplicate_capabilities_are_configuration_failures():
    registry = TeamRegistry([Team()])
    registry.declare_case_types("dining", ["dining"])
    with pytest.raises(TeamUnavailable, match="not_installed"):
        registry.resolve(case_type="dining")
    with pytest.raises(RegistryError):
        registry.resolve(case_type="")
    with pytest.raises(RegistryError, match="duplicate capability"):
        registry.register(Team(team_id="dining", capabilities=["mobility.itinerary"]))


def test_unavailable_capability_also_claims_unique_ownership():
    registry = TeamRegistry()
    registry.declare_unavailable("mobility", "disabled", capabilities=["mobility.itinerary"])
    with pytest.raises(RegistryError, match="duplicate capability"):
        registry.register(Team(team_id="dining", capabilities=["mobility.itinerary"]))


def test_registry_rejects_incompatible_contract_and_undeclared_capability():
    with pytest.raises(RegistryError, match="does not support"):
        TeamRegistry([Team(supported_contract_versions=["2.0"])])
    with pytest.raises(TeamContractViolation, match="undeclared capability"):
        TeamRegistry([Team()]).require_runnable("mobility", "dining.itinerary")


def test_static_config_never_imports_implementation(monkeypatch):
    import importlib
    monkeypatch.setattr(importlib, "import_module", lambda *args: pytest.fail("static validation imported plugin"))
    config = config_from_declaration(declaration([team_config(required=False, capabilities=["mobility.itinerary"], hooks=[])]), source="test")
    assert config.teams[0].required is False
    assert config.teams[0].hooks == []


def test_config_required_defaults_and_legacy_inactive_placeholder():
    config = config_from_declaration(declaration([team_config(active=False, implementation_ref="removed placeholder")]), source="test")
    assert config.teams[0].required is True
    assert config.teams[0].capabilities is None


@pytest.mark.parametrize("teams", [
    [team_config(implementation_ref="bad")],
    [team_config(capabilities=["mobility.itinerary", "mobility.itinerary"])],
    [team_config(hooks=[""])],
    [team_config(capabilities=["mobility.itinerary"]), team_config(team_id="dining", capabilities=["mobility.itinerary"])],
])
def test_static_config_rejects_invalid_declarations(teams):
    with pytest.raises(ProjectConfigError):
        config_from_declaration(declaration(teams), source="test")


@pytest.mark.asyncio
async def test_local_disabled_team_execute_is_never_called():
    team = Team(active=False)
    with pytest.raises(TeamUnavailable):
        await LocalTeamExecutor(TeamRegistry([team])).execute(task())
    assert team.calls == 0


@pytest.mark.asyncio
async def test_local_capability_and_scope_checked_before_business():
    team = Team()
    executor = LocalTeamExecutor(TeamRegistry([team]))
    with pytest.raises(TeamContractViolation):
        await executor.execute(task().model_copy(update={"capability": "dining.itinerary"}))
    with pytest.raises(ToolScopeViolation):
        await executor.execute(task().model_copy(update={"allowed_tools": ["write.travel"]}))
    assert team.calls == 0
    assert not issubclass(ToolScopeViolation, ValueError)


class Transport:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    async def submit(self, endpoint, value):
        self.calls += 1
        return self.response


@pytest.mark.asyncio
async def test_a2a_disabled_and_missing_registry_never_resolve_or_send():
    transport = Transport({})
    def resolver(_):
        pytest.fail("disabled team reached endpoint resolver")
    for registry in (None, TeamRegistry([Team(active=False)])):
        with pytest.raises(TeamUnavailable):
            await A2ATeamExecutor(transport, resolver, registry=registry).execute(task())
    assert transport.calls == 0


@pytest.mark.asyncio
async def test_a2a_endpoint_mismatch_is_rejected_before_submit():
    transport = Transport({})
    with pytest.raises(TeamContractViolation, match="endpoint team_id"):
        await A2ATeamExecutor(transport, lambda _: {"team_id": "dining"}, registry=TeamRegistry([Team()])).execute(task())
    assert transport.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["team_id", "task_id", "run_id"])
async def test_a2a_wrong_result_identity_rejected(field):
    value = task()
    result = dict(team_id=value.team_id, task_id=str(value.task_id), run_id=str(value.run_id),
                  outcome="completed", confidence=1, next_action="respond")
    result[field] = "wrong"
    with pytest.raises(TeamContractViolation, match=field):
        await A2ATeamExecutor(Transport({"status": "completed", "artifact": result}), lambda _: "endpoint", registry=TeamRegistry([Team()])).execute(value)


@pytest.mark.asyncio
async def test_a2a_missing_identifiers_are_not_filled_from_request():
    with pytest.raises(TeamContractViolation, match="team_id"):
        await A2ATeamExecutor(Transport({"status": "completed", "artifact": {"confidence": 1}}), lambda _: "endpoint", registry=TeamRegistry([Team()])).execute(task())


@pytest.mark.asyncio
async def test_a2a_valid_result_and_remote_unavailable_are_distinct():
    value = task()
    result = TeamResult(task_id=value.task_id, run_id=value.run_id, team_id=value.team_id,
                        outcome="completed", answer="경로 확인", confidence=1, evidence=[Evidence(evidence_id="travel-route-fixture", source_type="db", source_id="travel-route-fixture", claim="시험용 이동 경로", value={"duration_min": 12}, confidence=1, observed_at=datetime(2026, 10, 11, tzinfo=UTC))], next_action=NextAction.RESPOND)
    executor = A2ATeamExecutor(Transport({"status": "completed", "artifact": result}), lambda _: "endpoint", registry=TeamRegistry([Team()]))
    assert await executor.execute(value) == result
    executor.transport.response = {"status": "failed", "failure_code": "team_unavailable"}
    with pytest.raises(TeamUnavailable, match="remote_unavailable"):
        await executor.execute(value)


@pytest.mark.asyncio
async def test_resolver_implementation_errors_are_not_turned_into_unavailability():
    def broken(_):
        raise KeyError("broken endpoint table")
    with pytest.raises(KeyError, match="broken endpoint table"):
        await A2ATeamExecutor(Transport({}), broken, registry=TeamRegistry([Team()])).execute(task())


@pytest.mark.asyncio
async def test_a2a_unknown_status_cannot_accept_completed_artifact():
    value = task()
    result = TeamResult(task_id=value.task_id, run_id=value.run_id, team_id=value.team_id,
                        outcome="completed", answer="경로 확인", confidence=1, evidence=[Evidence(evidence_id="travel-route-fixture", source_type="db", source_id="travel-route-fixture", claim="시험용 이동 경로", value={"duration_min": 12}, confidence=1, observed_at=datetime(2026, 10, 11, tzinfo=UTC))], next_action=NextAction.RESPOND)
    with pytest.raises(TeamContractViolation, match="unsupported status"):
        await A2ATeamExecutor(Transport({"status": "unexpected", "artifact": result}), lambda _: "endpoint", registry=TeamRegistry([Team()])).execute(value)


@pytest.mark.asyncio
async def test_a2a_resolver_timeout_is_deadline_failure_without_submit():
    import asyncio
    async def resolver(_):
        await asyncio.sleep(10)
    value = task().model_copy(update={"deadline_at": datetime.now(UTC) + timedelta(milliseconds=30)})
    transport = Transport({})
    result = await A2ATeamExecutor(transport, resolver, registry=TeamRegistry([Team()])).execute(value)
    assert result.failure_code == "remote_deadline_exceeded"
    assert transport.calls == 0


@pytest.mark.asyncio
async def test_a2a_waiting_artifact_identity_is_checked_before_wait_mapping():
    with pytest.raises(TeamContractViolation, match="team_id"):
        await A2ATeamExecutor(Transport({"status": "input_required", "artifact": {"team_id": "dining"}}), lambda _: "endpoint", registry=TeamRegistry([Team()])).execute(task())


@pytest.mark.asyncio
async def test_a2a_hanging_cancel_is_bounded_and_recorded(caplog):
    import asyncio
    async def resolver(_):
        return "endpoint"
    class HangingCancel(Transport):
        async def poll(self, remote, value):
            await asyncio.sleep(10)
        async def cancel(self, remote):
            await asyncio.sleep(10)
    value = task().model_copy(update={"deadline_at": datetime.now(UTC) + timedelta(milliseconds=30)})
    executor = A2ATeamExecutor(HangingCancel({"status": "working"}), resolver, registry=TeamRegistry([Team()]), cancel_timeout_seconds=0.03)
    started = asyncio.get_running_loop().time()
    result = await executor.execute(value)
    assert asyncio.get_running_loop().time() - started < 0.5
    assert result.failure_code == "remote_deadline_exceeded"
    record = next(record for record in caplog.records if record.message == "a2a_cancel_failed")
    assert record.error_type == "TimeoutError"
    assert record.run_id == str(value.run_id)
    assert value.input_text not in caplog.text


@pytest.mark.asyncio
async def test_sync_resolver_timeout_keeps_loop_responsive_and_never_submits_late():
    import asyncio
    import threading
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    await asyncio.to_thread(lambda: None)
    def resolver(_):
        started.set()
        try:
            release.wait(timeout=1)
            return "endpoint"
        finally:
            finished.set()
    transport = Transport({})
    value = task().model_copy(update={"deadline_at": datetime.now(UTC) + timedelta(milliseconds=40)})
    executor = A2ATeamExecutor(transport, resolver, registry=TeamRegistry([Team()]))
    ticks = []
    async def ticker():
        await asyncio.sleep(0.01)
        ticks.append(True)
    heartbeat = asyncio.create_task(ticker())
    try:
        result = await asyncio.wait_for(executor.execute(value), timeout=0.3)
        await heartbeat
        assert started.is_set()
        assert ticks == [True]
        assert not finished.is_set()
        assert result.failure_code == "remote_deadline_exceeded"
        assert transport.calls == 0
    finally:
        release.set()
        await asyncio.to_thread(finished.wait, 1)
    await asyncio.sleep(0)
    assert finished.is_set()
    assert transport.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("returns_awaitable", [False, True])
async def test_sync_resolver_copies_context_and_supports_awaitable_result(returns_awaitable):
    import threading
    from contextvars import ContextVar
    revision = ContextVar("a2a_test_revision")
    seen = []
    request_thread = threading.get_ident()
    def resolver(_):
        seen.append((revision.get(), threading.get_ident()))
        if returns_awaitable:
            async def endpoint():
                seen.append((revision.get(), threading.get_ident()))
                return "endpoint"
            return endpoint()
        return "endpoint"
    token = revision.set("pinned-generation")
    try:
        executor = A2ATeamExecutor(Transport({"status": "failed", "failure_code": "contract-test-only"}), resolver, registry=TeamRegistry([Team()]))
        result = await executor.execute(task())
    finally:
        revision.reset(token)
    assert result.failure_code == "contract-test-only"
    assert seen[0][0] == "pinned-generation"
    assert seen[0][1] != request_thread
    if returns_awaitable:
        assert seen[1] == ("pinned-generation", request_thread)


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["submit", "poll", "cancel"])
async def test_sync_transport_is_rejected_before_any_call(method):
    transport = Transport({})
    forbidden_calls = []
    def blocking(*args):
        forbidden_calls.append(args)
        return {}
    setattr(transport, method, blocking)
    with pytest.raises(TeamContractViolation, match=f"{method} must be an async function"):
        await A2ATeamExecutor(transport, lambda _: "endpoint", registry=TeamRegistry([Team()])).execute(task())
    assert forbidden_calls == []
    assert transport.calls == 0


@pytest.mark.asyncio
async def test_sync_resolver_late_coroutine_is_closed_without_running():
    import asyncio
    import inspect
    import threading
    release, finished = threading.Event(), threading.Event()
    returned = []
    executed = []
    async def late_endpoint():
        executed.append(True)
        return "endpoint"
    def resolver(_):
        release.wait(timeout=1)
        value = late_endpoint()
        returned.append(value)
        finished.set()
        return value
    await asyncio.to_thread(lambda: None)
    value = task().model_copy(update={"deadline_at": datetime.now(UTC) + timedelta(milliseconds=40)})
    transport = Transport({})
    try:
        result = await A2ATeamExecutor(transport, resolver, registry=TeamRegistry([Team()])).execute(value)
        assert result.failure_code == "remote_deadline_exceeded"
    finally:
        release.set()
        await asyncio.to_thread(finished.wait, 1)
    # Let the worker completion and discard callback run.
    for _ in range(4):
        await asyncio.sleep(0)
    assert len(returned) == 1
    assert inspect.getcoroutinestate(returned[0]) == inspect.CORO_CLOSED
    assert executed == []
    assert transport.calls == 0


@pytest.mark.parametrize("case_type", ["other", "general", "unclassified", ""])
def test_unknown_case_type_remains_routing_error(case_type):
    registry = TeamRegistry([Team()])
    registry.declare_case_types("dining", ["dining"])
    with pytest.raises(RegistryError):
        registry.resolve(case_type=case_type)


def test_missing_known_owner_may_have_a_different_id_than_case_type():
    registry = TeamRegistry([Team()])
    registry.declare_case_types("dining_plugin", ["dining"])
    with pytest.raises(TeamUnavailable) as failure:
        registry.resolve(case_type="dining")
    assert (failure.value.team_id, failure.value.reason) == ("dining_plugin", "not_installed")


def test_ambiguous_known_owners_remain_routing_error():
    registry = TeamRegistry()
    registry.declare_case_types("dining_primary", ["dining"])
    registry.declare_case_types("dining_alternative", ["dining"])
    with pytest.raises(RegistryError):
        registry.resolve(case_type="dining")
