"""담당 불가가 다른 구성원의 결과·재시도 표지를 지우지 않는지 검증한다."""
from types import SimpleNamespace
from uuid import uuid4

from app.core.registry import TeamRegistry
from app.core.service_bindings import BindingTable, bind_services
from app.domains.travel_ops.instances.activity import ActivityTeam
from app.domains.travel_ops.instances.dining import DiningTeam
from app.domains.travel_ops.components.watch.trip_watch_batch import Outcome, WatchBatch
from .helpers import pack, task


def batch():
    work = ActivityTeam(None)
    trip = {"trip_id": str(uuid4()), "version": 1}
    request = task("activity", "activity.itinerary", pack("activity"), work.manifest.allowed_tools)
    evidence = work._evidence(request, source_id="fixture.watch", claim="합성 점검 결과", value={"verdict": "disrupted"})
    return WatchBatch(work, request, {"trip": trip, "evidence": evidence}), trip


def item(kind):
    return SimpleNamespace(item_id=uuid4(), kind=kind, title=f"서울 {kind} 일정")


def test_partial_completed_batch_retains_unavailable_item_for_retry():
    work, trip = batch()
    off, on = item("dining"), item("activity")
    result = work._result(trip, [], [Outcome(off, "unavailable", reasons=["disabled"]),
                                   Outcome(on, "consent")])
    assert result.action_proposals[0].arguments["batch"]["retry"] == [str(off.item_id)]
    assert result.action_proposals[0].arguments["batch"]["consents"][0]["item_id"] == str(on.item_id)


def test_unavailable_does_not_discard_independent_unresolved_outcome():
    work, trip = batch()
    off, on = item("dining"), item("activity")
    result = work._result(trip, [], [Outcome(off, "unavailable", reasons=["disabled"]),
                                   Outcome(on, "no_alternate")])
    assert result.failure_code == "fatal_source_failure"
    assert f"retry:{off.item_id}" in result.warnings
    assert f"outcome:{on.item_id}:no_alternate" in result.warnings


def test_unavailable_does_not_discard_independent_retry_outcome():
    work, trip = batch()
    off, on = item("dining"), item("activity")
    result = work._result(trip, [], [Outcome(off, "unavailable", reasons=["disabled"]),
                                   Outcome(on, "source_failed")])
    assert {f"retry:{i.item_id}" for i in [off, on]} <= set(result.warnings)


def test_batch_uses_each_owner_tools_scope_and_budget():
    work, _ = batch()
    own_tools = object()
    dining = DiningTeam(own_tools)
    registry = TeamRegistry([work.work, dining])
    with bind_services(BindingTable({}, registry)):
        owner, request = work._scoped_work(SimpleNamespace(team_id="dining"))
    assert owner.tools is own_tools
    assert owner.manifest.max_steps == dining.manifest.max_steps
    assert request.team_id == request.context.team_id == "dining"
    assert request.capability == "dining.itinerary"
    assert request.allowed_tools == dining.manifest.allowed_tools
    assert request.context.knowledge_scope == dining.manifest.knowledge_scope
    assert request.deadline_at == work.task.deadline_at
