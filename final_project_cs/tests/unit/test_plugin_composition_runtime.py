"""Request generations and real composition failure boundaries, without external I/O."""
import asyncio
from threading import Event
from types import SimpleNamespace

import pytest

from app import composition
from app.application.runtime import ControllerProxy, RuntimeComposition
from app.core.registry import TeamRegistry
from app.core.service_bindings import (
    BindingTable, PinCompositionMiddleware, bind_services, collect_services,
    current_bindings, standalone_services,
)
from app.core.team_availability import TeamUnavailable
from app.domains.travel_ops.components.team_hooks import legs, similarity
from app.domains.travel_ops.modules.live_progress import op_stream
from tests.unit.core.test_plugin_availability import Team, declaration, team_config
from app.core.project_config import config_from_declaration


def controller(revision, *, enabled=True):
    registry = TeamRegistry([Team(active=enabled)])
    table = BindingTable({("legs", "leg_planner"): lambda *a, **k: revision,
                          ("legs", "walk_limit_m"): lambda: revision}, registry, revision)
    return SimpleNamespace(registry=registry, service_bindings=table, composition_revision=revision)


def test_disabled_package_not_imported_and_other_team_loaded(monkeypatch):
    config = config_from_declaration(declaration([
        team_config(active=False, capabilities=["mobility.itinerary"]),
        team_config(team_id="activity", implementation_ref="app.domains.travel_ops.instances.activity:ActivityTeam")]), source="test")
    calls = []
    original = composition._import_ref
    def traced(ref, team):
        calls.append(team)
        return original(ref, team)
    monkeypatch.setattr(composition, "_import_ref", traced)
    registry = composition.build_registry(config=config, tools=object(), llm=object())
    assert calls == ["activity"]
    assert registry.require_runnable("activity").manifest.active
    with pytest.raises(TeamUnavailable, match="disabled"):
        registry.require_runnable("mobility")


@pytest.mark.parametrize("required", [False, True])
def test_import_failure_optional_vs_required(required):
    config = config_from_declaration(declaration([team_config(required=required)]), source="test")
    if required:
        with pytest.raises(composition.CompositionError):
            composition.build_registry(config=config, tools=object(), llm=object())
    else:
        registry = composition.build_registry(config=config, tools=object(), llm=object())
        with pytest.raises(TeamUnavailable, match="load_failed"):
            registry.require_runnable("mobility")


def test_all_disabled_provider_collection_has_no_import_or_legacy_change(monkeypatch):
    config = config_from_declaration(declaration([team_config(active=False)]), source="test")
    registry = composition.build_registry(config=config, tools=object(), llm=object())
    old_callback = legs._leg_planner
    with collect_services() as staged:
        assert composition.wire_domain_teams(config=config, registry=registry) == []
    assert staged == {}
    assert legs._leg_planner is old_callback


@pytest.mark.parametrize("failure", [ImportError, AttributeError, RuntimeError])
def test_failed_optional_hook_discards_partial_registrations(monkeypatch, failure):
    config = config_from_declaration(declaration([team_config(required=False)]), source="test")
    registry = TeamRegistry([Team()])
    def broken(**kwargs):
        legs.register(leg_planner=lambda *a: "partial", disruptions_from_events=lambda _: ([], []), walk_limit_m=lambda: 1)
        raise failure("missing hook dependency")
    monkeypatch.setattr(composition, "_wire_domain_providers", broken)
    with collect_services() as staged:
        assert composition.wire_domain_teams(config=config, registry=registry) == []
    assert staged == {}
    with pytest.raises(TeamUnavailable, match="load_failed"):
        registry.require_runnable("mobility")


def test_optional_hook_contract_error_still_rejects_candidate(monkeypatch):
    config = config_from_declaration(declaration([team_config(required=False)]), source="test")
    registry = TeamRegistry([Team()])
    def broken(**kwargs):
        raise composition.CompositionError("declared hooks mismatch")
    monkeypatch.setattr(composition, "_wire_domain_providers", broken)
    with collect_services(), pytest.raises(composition.CompositionError, match="hooks mismatch"):
        composition.wire_domain_teams(config=config, registry=registry)


def test_required_hook_failure_keeps_published_generation(monkeypatch):
    config = config_from_declaration(declaration([team_config(required=True)]), source="test")
    runtime = RuntimeComposition(controller("old"), "old")
    def broken(**kwargs):
        raise ImportError("required hook dependency")
    monkeypatch.setattr(composition, "_wire_domain_providers", broken)
    with pytest.raises(ImportError), collect_services():
        composition.wire_domain_teams(config=config, registry=TeamRegistry([Team()]))
    assert runtime.controller.composition_revision == "old"


def test_request_two_hook_reads_keep_old_generation_across_disable():
    runtime = RuntimeComposition(controller("old"), "old")
    proxy = ControllerProxy(runtime)
    with runtime.pin():
        assert legs.leg_planner(1, {}) == "old"
        runtime.swap(controller("new", enabled=False), "new")
        assert proxy.composition_revision == "old"
        assert legs.walk_limit_m() == "old"
        assert runtime.published_snapshot().revision == "new"
        assert runtime.state("new") == "active"
    with runtime.pin(), pytest.raises(TeamUnavailable, match="disabled"):
        legs.leg_planner(1, {})


def test_repeated_enabled_reload_never_changes_pinned_callbacks():
    runtime = RuntimeComposition(controller("old"), "old")
    with runtime.pin():
        for index in range(30):
            revision = str(index)
            runtime.swap(controller(revision), revision)
            assert legs.walk_limit_m() == "old"
    with runtime.pin():
        assert legs.walk_limit_m() == "29"


def test_binding_table_is_immutable_and_copied():
    values = {("check", "value"): "before"}
    table = BindingTable(values)
    values[("check", "value")] = "after"
    assert table.values[("check", "value")] == "before"
    with pytest.raises(TypeError):
        table.values[("check", "value")] = "after"


def test_publication_rejects_mixed_registry_or_revision():
    runtime = RuntimeComposition(controller("old"), "old")
    bad = controller("new")
    with pytest.raises(ValueError, match="revision"):
        runtime.swap(bad, "other")
    bad.registry = TeamRegistry()
    with pytest.raises(ValueError, match="registry"):
        runtime.swap(bad, "new")
    assert runtime.active_revision == "old"


def test_missing_request_context_never_uses_legacy_callback():
    with standalone_services(False), pytest.raises(TeamUnavailable, match="composition_unbound"):
        legs.leg_planner(1, {})


def test_enabled_engine_off_never_returns_estimate():
    registry = TeamRegistry([Team()])
    with bind_services(BindingTable({("legs", "leg_planner"): lambda *a, **k: None}, registry)), pytest.raises(TeamUnavailable, match="engine_unavailable"):
        legs.leg_planner(1, {})


def test_review_does_not_swallow_disabled_required_calculation():
    from app.domains.travel_ops.components.intake.review import default_engine
    with bind_services(controller("off", enabled=False).service_bindings), pytest.raises(TeamUnavailable):
        default_engine(1)


def test_optional_similarity_emits_omission_reason(caplog):
    with caplog.at_level("INFO"), bind_services(BindingTable({}, TeamRegistry(), "off")):
        assert similarity.scorer(None) is None
    record = next(record for record in caplog.records if record.msg == "optional_service_omitted")
    assert record.reason == "provider_unavailable"
    assert record.composition_revision == "off"


def test_mobility_setting_reload_rejected_before_live_engine_mutation(monkeypatch):
    from app.domains.travel_ops.instances.mobility import wiring
    monkeypatch.setattr(wiring, "mode", lambda: "enabled")
    monkeypatch.setattr(composition, "_mobility_configuration_key", ("old", None, None, None, None))
    monkeypatch.setattr(composition, "_configure_mobility_once", lambda _: pytest.fail("live engine mutated"))
    with pytest.raises(composition.CompositionError, match="restart"):
        composition._configure_mobility(SimpleNamespace(mobility_data_dir="new"))
    assert composition._configure_mobility(SimpleNamespace(mobility_data_dir="old")) == {"mode": "enabled"}


def test_first_engine_configuration_failure_can_retry_without_live_generation(monkeypatch):
    from app.domains.travel_ops.instances.mobility import wiring
    state = {"mode": "unconfigured", "calls": 0}
    monkeypatch.setattr(wiring, "mode", lambda: state["mode"])
    monkeypatch.setattr(composition, "_mobility_configuration_key", None)
    def configure(settings, *, preload=True):
        assert preload is True
        state["calls"] += 1
        if state["calls"] == 1:
            state["mode"] = "broken"
            raise RuntimeError("initial data check failed")
        state["mode"] = "enabled"
        return {"mode": "enabled"}
    monkeypatch.setattr(composition, "_configure_mobility_once", configure)
    with pytest.raises(RuntimeError, match="initial data"):
        composition._configure_mobility(SimpleNamespace(mobility_data_dir="fixed"))
    assert composition._configure_mobility(SimpleNamespace(mobility_data_dir="fixed")) == {"mode": "enabled"}
    assert state["calls"] == 2


@pytest.mark.asyncio
async def test_asgi_pin_survives_sse_send_and_reload():
    runtime = RuntimeComposition(controller("old"), "old")
    seen = []
    async def inner(scope, receive, send):
        seen.append(current_bindings().revision)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        seen.append(current_bindings().revision)
        await send({"type": "http.response.body", "body": b"done"})
    async def send(message):
        runtime.swap(controller("new"), "new")
    await PinCompositionMiddleware(inner, runtime)({"type": "http"}, None, send)
    assert seen == ["old", "old"]
    assert current_bindings() is None


@pytest.mark.asyncio
async def test_stream_worker_and_deferred_work_keep_request_generation():
    runtime = RuntimeComposition(controller("old"), "old")
    finished = Event()
    observed = []
    def deferred():
        observed.append(current_bindings().revision)
        finished.set()
    def work(progress, defer):
        observed.append(current_bindings().revision)
        runtime.swap(controller("new"), "new")
        defer(deferred)
        return {"revision": current_bindings().revision}
    async def connected():
        return False
    cfg = {"beat_seconds": 0.01, "slow_seconds": 1, "max_seconds": 5}
    with runtime.pin():
        chunks = [chunk async for chunk in op_stream.run(work, op="test", is_disconnected=connected, cfg=cfg)]
    assert await asyncio.to_thread(finished.wait, 3)
    assert observed == ["old", "old"]
    assert '"revision": "old"' in "".join(chunks)


@pytest.mark.parametrize("reason,retryable", [("disabled", False), ("not_installed", False), ("load_failed", False), ("remote_unavailable", True), ("engine_unavailable", False)])
def test_stream_error_preserves_reason(reason, retryable):
    body = op_stream.error_payload(TeamUnavailable("mobility", reason))
    assert (body["code"], body["status"], body["reason"], body["retryable"]) == ("team_unavailable", 503, reason, retryable)


@pytest.mark.asyncio
async def test_json_and_mcp_keep_disabled_reason_while_independent_reads_work():
    from fastapi import FastAPI
    import httpx
    from app.presentation.errors import install_error_handlers
    from app.domains.travel_ops.modules.mcp.mcp_server import AsgiBackend, Caller, McpApiError

    app = FastAPI()
    runtime = RuntimeComposition(controller("off", enabled=False), "off")
    app.add_middleware(PinCompositionMiddleware, runtime=runtime)
    install_error_handlers(app)
    @app.get("/health")
    def health():
        return {"status": "ok"}
    @app.get("/existing-plan")
    def read():
        return {"title": "서울 여행 기존 일정"}
    @app.get("/required")
    def required():
        return {"leg": legs.leg_planner(1, {})}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://local-test") as client:
        assert (await client.get("/health")).status_code == 200
        assert (await client.get("/existing-plan")).status_code == 200
        response = await client.get("/required")
        assert response.status_code == 503
        assert response.json()["error"]["reason"] == "disabled"
    with pytest.raises(McpApiError) as caught:
        await AsgiBackend(lambda: app).request("GET", "/required", caller=Caller("synthetic-test-key"))
    assert (caught.value.status, caught.value.code, caught.value.extra["reason"]) == (503, "team_unavailable", "disabled")
    assert '"reason": "disabled"' in caught.value.text()
