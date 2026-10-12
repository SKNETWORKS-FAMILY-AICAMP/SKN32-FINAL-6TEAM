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
