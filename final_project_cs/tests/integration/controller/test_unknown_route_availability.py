"""미분류 재배분과 알려진 여행 담당 부재를 실제 Registry·Controller로 구분한다."""
from __future__ import annotations

import asyncio

import pytest

from app.core.case_lifecycle.events import EventType
from app.core.registry import TeamRegistry
from app.core.remote_team.executor import LocalTeamExecutor
from app.core.team_availability import TeamUnavailable
from app.core.transition import transition_case
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from .test_conversation_resume import travel  # noqa: F401


def new_routing_case(tenant, customer, issue_code):
    with get_connection() as conn:
        case_id = repository.create_case(conn, tenant_id=tenant, customer_id=customer, subject="식당 지연 확인")
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=0,
                        event_type=EventType.CREATED, payload={"channel": "web", "message": "식당 지연 확인"}, actor_type="test")
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=1,
                        event_type=EventType.CLASSIFIED,
                        payload={"intent": "other", "issue_code": issue_code, "sentiment": "neutral"}, actor_type="test")
    return case_id


@pytest.mark.parametrize("case_type", ["other", "general"])
@pytest.mark.parametrize("reroute_succeeds", [True, False])
def test_unclassified_reaches_one_reroute_or_escalation(travel, case_type, reroute_succeeds):
    controller, team, tenant, customer, _, _ = travel
    case_id = new_routing_case(tenant, customer, case_type)
    controller.registry.declare_case_types("absent_activity", ["activity"])
    calls = []

    def reroute(**kwargs):
        calls.append(kwargs)
        return {"case_type": "dining", "why": "식당 지연"} if reroute_succeeds else None

    controller.reroute = reroute
    before = len(team.tasks)
    outcome = asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    assert len(calls) == 1 and calls[0]["case_type"] == case_type
    assert outcome["status"] == ("waiting_input" if reroute_succeeds else "escalated")
    assert len(team.tasks) == before + int(reroute_succeeds)
    with get_connection() as conn:
        case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
        events = repository.get_case_events(conn, tenant_id=tenant, case_id=case_id)
    assert case["owner_team_id"] == (team.manifest.team_id if reroute_succeeds else None)
    expected_event = "ROUTED" if reroute_succeeds else "ROUTING_FAILED"
    assert any(str(event["event_type"]).upper() == expected_event for event in events)


def test_removed_known_team_never_reroutes_to_another_team(travel):
    controller, team, tenant, customer, _, _ = travel
    case_id = new_routing_case(tenant, customer, "activity_cancel_or_change")
    registry = TeamRegistry([team])
    registry.declare_case_types("activity", ["activity"])
    controller.registry = registry
    controller.team_executor = LocalTeamExecutor(registry)
    calls = []
    controller.reroute = lambda **kwargs: calls.append(kwargs) or {"case_type": "dining"}
    with get_connection() as conn:
        before = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
    task_count = len(team.tasks)
    with pytest.raises(TeamUnavailable) as failure:
        asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    assert (failure.value.team_id, failure.value.reason) == ("activity", "not_installed")
    assert calls == [] and len(team.tasks) == task_count
    with get_connection() as conn:
        assert repository.get_case(conn, tenant_id=tenant, case_id=case_id) == before
        assert conn.execute("SELECT count(*) FROM agent_runs WHERE tenant_id=%s AND case_id=%s", (tenant, case_id)).fetchone()[0] == 0
