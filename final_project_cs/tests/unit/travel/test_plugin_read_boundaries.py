"""Actual import and calculation boundaries for intentionally absent travel Teams."""
import subprocess
import sys
from contextlib import nullcontext
from datetime import UTC, datetime

import pytest

from app.core.registry import TeamRegistry
from app.core.service_bindings import BindingTable, bind_services
from app.core.team_availability import TeamUnavailable
from app.domains.travel_ops.components.intake import hours
from app.domains.travel_ops.components.itinerary import move_judge
from tests.unit.core.test_plugin_availability import Team


NOW = datetime(2026, 10, 11, 3, tzinfo=UTC)
A = move_judge.as_place({"name": "경복궁", "lat": 37.5796, "lon": 126.977}, key="a")
B = move_judge.as_place({"name": "시청", "lat": 37.5663, "lon": 126.9779}, key="b")


def test_clean_process_imports_no_disabled_team_implementation():
    script = '''
import importlib.abc
import sys
attempts = []
class BlockTeams(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith("app.domains.travel_ops.instances.") and not fullname.startswith("app.domains.travel_ops.instances._shared"):
            attempts.append(fullname)
            raise AssertionError("disabled implementation was imported")
sys.meta_path.insert(0, BlockTeams())
from app import composition
from app.core.project_config import config_from_declaration
from app.core.service_bindings import collect_services
config = config_from_declaration(dict(modules={}, ports=dict(team_executor="local", message_broker="outbox", graph_store="sql"), teams=[
    dict(team_id=name, active=False, implementation_ref="not_installed.module:Team")
    for name in ("activity", "dining", "mobility", "booking_handoff", "lodging", "flight")
]), source="import-boundary-test")
registry = composition.build_registry(config=config, tools=object(), llm=object())
with collect_services() as staged:
    composition.wire_domain_teams(config=config, registry=registry)
assert attempts == [], attempts
assert staged == {}, staged
assert not any(name.startswith("app.domains.travel_ops.instances.") and not name.startswith("app.domains.travel_ops.instances._shared") for name in sys.modules)
print("disabled Team import attempts=0; providers=0; declarations=6")
'''
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "import attempts=0" in result.stdout


def test_move_judge_preserves_disabled_reason_without_estimate():
    registry = TeamRegistry([Team(active=False)])
    with bind_services(BindingTable({}, registry, "off")):
        with pytest.raises(TeamUnavailable) as caught:
            move_judge.judge(origin=A, dest=B, now=NOW)
    assert (caught.value.team_id, caught.value.reason) == ("mobility", "disabled")


@pytest.mark.parametrize("stage", ["factory", "execute", "shape", "missing"])
def test_bound_engine_failure_never_becomes_straight_line_success(stage):
    def failed(*args, **kwargs):
        raise RuntimeError("engine failure")
    factory = {"factory": failed, "execute": lambda *a: failed,
               "shape": lambda *a: (lambda *args: ({"route": {}}, None)),
               "missing": lambda *a: None}[stage]
    table = BindingTable({("legs", "leg_planner"): factory}, TeamRegistry([Team()]), "on")
    with bind_services(table):
        with pytest.raises(TeamUnavailable) as caught:
            move_judge.judge(origin=A, dest=B, now=NOW, arrive_by=NOW)
    assert caught.value.reason == "engine_unavailable"


class NoDatabase:
    def cursor(self):
        pytest.fail("disabled Dining touched the database")

    def transaction(self):
        return nullcontext()


@pytest.mark.parametrize("registered", [False, True])
def test_dining_intake_disabled_before_any_database_read(registered):
    registry = TeamRegistry([Team(team_id="dining", active=False)])
    place = {"name": "서울 시험 식당", "content_id": "fixture", **({"place_id": "core"} if registered else {})}
    with bind_services(BindingTable({}, registry, "off")):
        with pytest.raises(TeamUnavailable) as caught:
            hours.facts_for(NoDatabase(), "test", place, "dining", NOW, NOW)
    assert (caught.value.team_id, caught.value.reason) == ("dining", "disabled")


@pytest.mark.parametrize("registered", [False, True])
def test_dining_intake_uses_frozen_provider_for_both_place_kinds(registered):
    calls = []
    def state(*args, **kwargs):
        calls.append((args, kwargs))
        return dict(linked=True, available=True, attributes={"hours": ["11:00", "22:00"]},
                    open_at_slot=True, order_ok=False, needs_check=True)
    place = {"name": "서울 시험 식당", "_hours": {"hours": ["00:00", "23:59"]},
             **({"place_id": "core"} if registered else {})}
    key = "state" if registered else "catalog_state"
    table = BindingTable({("dining_ledger", key): state}, TeamRegistry([Team(team_id="dining")]), "on")
    with bind_services(table):
        result = hours.facts_for(NoDatabase(), "test", place, "dining", NOW, NOW)
    assert len(calls) == 1
    assert result.source == "dining_ledger"
    assert result.attributes["hours"] == ["11:00", "22:00"]
    assert result.open_at_slot is True and result.order_ok is False and result.needs_check
