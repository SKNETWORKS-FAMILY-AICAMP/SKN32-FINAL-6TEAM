"""다른 여행 Team의 읽기 도구도 Dining 실행 관문을 우회하지 않는다."""
from contextlib import contextmanager
from uuid import uuid4

import pytest

from app.core.contracts import ContextPack
from app.core.registry import TeamRegistry
from app.core.service_bindings import BindingTable, bind_services
from app.core.team_availability import TeamUnavailable
from app.tools.read_tools import ReadToolbox
from tests.unit.core.test_plugin_availability import Team


def context():
    return ContextPack(pack_id=uuid4(), case_id=uuid4(), tenant_id="synthetic-travel",
        team_id="activity", knowledge_scope=[], estimated_input_tokens=0,
        current_state={"customer_id": str(uuid4())})


def arguments(name):
    return {"slots": [{"place_id": "meal"}]} if name.endswith("states") else {"place_id": "meal"}


@pytest.mark.parametrize("name", ["read.dining_state", "read.dining_states"])
@pytest.mark.parametrize("reason", ["disabled", "not_installed", "load_failed"])
@pytest.mark.parametrize("ledger_enabled", [True, False])
def test_unavailable_owner_rejected_before_connection_or_provider(name, reason, ledger_enabled):
    registry = TeamRegistry()
    if reason != "not_installed":
        registry.declare_unavailable("dining", reason)
    calls = []

    @contextmanager
    def connection():
        calls.append("connection")
        yield object()

    def provider(*args, **kwargs):
        calls.append("provider")
        return {"open": True}

    tools = ReadToolbox(connection, dining_ledger=ledger_enabled)
    table = BindingTable({("dining_ledger", "state"): provider, ("dining_ledger", "states"): provider}, registry, "read-tool-test")
    with bind_services(table), pytest.raises(TeamUnavailable) as failure:
        tools.call(name, context(), arguments(name), [name], set())
    assert (failure.value.team_id, failure.value.reason) == ("dining", reason)
    assert calls == []


@pytest.mark.parametrize("name", ["read.dining_state", "read.dining_states"])
def test_active_owner_calls_only_pinned_provider_with_original_arguments(name):
    registry = TeamRegistry([Team(team_id="dining")])
    calls = []
    marker = object()

    @contextmanager
    def connection():
        calls.append("connection")
        yield marker

    def provider(*args, **kwargs):
        calls.append((args, kwargs))
        return {"source": "pinned-provider"}

    key = "states" if name.endswith("states") else "state"
    tools = ReadToolbox(connection)
    with bind_services(BindingTable({("dining_ledger", key): provider}, registry, "read-tool-test")):
        result = tools.call(name, context(), {**arguments(name), "order_margin_min": 17}, [name], set())
    assert result == {"source": "pinned-provider"}
    assert calls[0] == "connection" and calls[1][0][0] is marker
    assert calls[1][0][1] == "synthetic-travel"
    assert calls[1][1] == {"order_margin_min": 17}
    assert calls[1][0][2] == ([{"place_id": "meal"}] if key == "states" else "meal")


@pytest.mark.parametrize("name", ["read.dining_state", "read.dining_states"])
def test_missing_pinned_provider_rejected_before_connection(name):
    registry = TeamRegistry([Team(team_id="dining")])
    tools = ReadToolbox(lambda: pytest.fail("must not open connection"))
    with bind_services(BindingTable({}, registry, "read-tool-test")), pytest.raises(TeamUnavailable, match="not_installed"):
        tools.call(name, context(), arguments(name), [name], set())


@pytest.mark.parametrize("name", ["read.dining_state", "read.dining_states"])
@pytest.mark.parametrize("ledger_enabled", [True, False])
def test_unbound_non_standalone_rejected_even_when_ledger_disabled(name, ledger_enabled):
    tools = ReadToolbox(lambda: pytest.fail("must not open connection"), dining_ledger=ledger_enabled)
    from app.core.service_bindings import standalone_services

    # The unit harness defaults to standalone; explicitly exercise the product boundary.
    with standalone_services(False), pytest.raises(TeamUnavailable, match="composition_unbound"):
        tools.call(name, context(), arguments(name), [name], set())


@pytest.mark.parametrize("name", ["read.dining_state", "read.dining_states"])
def test_explicit_standalone_may_disable_ledger_without_connection(name):
    from app.core.service_bindings import standalone_services

    tools = ReadToolbox(lambda: pytest.fail("must not open connection"), dining_ledger=False)
    with standalone_services():
        assert tools.call(name, context(), arguments(name), [name], set()) is None
