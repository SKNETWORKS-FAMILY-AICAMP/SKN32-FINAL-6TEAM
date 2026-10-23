"""재개 커밋·실행 사이 중단을 DB 없이 주입하는 여행 단위 시험."""
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace
from uuid import uuid4

import asyncio
import pytest

from app.application.case_service import ActiveRunError, CaseService, ResumeTokenExpired
from app.application.controller import Controller, ControllerError
from app.core.case_lifecycle.case import CaseProjection, apply_event
from app.core.case_lifecycle.events import EventType
from app.core.contracts import CaseStatus, StateConflict, TeamManifest
from app.core.registry import TeamRegistry
from app.core.team_availability import TeamUnavailable


class MemoryConnection:
    """SQL 연결·트랜잭션 경계만 대역으로 두며 상태는 실제 리듀서로 전이한다."""

    def __init__(self):
        self.active = False
        self.commits = 0
        self.rollbacks = 0
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def transaction(self):
        return nullcontext()

    def cursor(self):
        return self

    def execute(self, sql, params):
        if "FROM agent_runs" in sql:
            self.result = (1,) if self.active else None
        elif "FROM customer_cases" in sql and "FOR UPDATE" in sql:
            self.result = (1,)
        else:
            raise AssertionError(f"unexpected SQL: {sql}")

    def fetchone(self):
        return self.result

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


@pytest.fixture
def recovery(monkeypatch):
    service = CaseService()
    token = "travel-unit-resume-token"
    conn = MemoryConnection()
    case = dict(case_id=uuid4(), tenant_id="travel-unit", customer_id=uuid4(),
                subject="식당 방문이 늦어요", status=CaseStatus.WAITING_INPUT, version=5,
                intent="incident_report", issue_code="dining_delay", sentiment="neutral",
                owner_team_id="dining", state_json=service.resume_metadata(token, "customer_input"))
    events = []

    def transition(connection, *, expected_version, event_type, payload, **kwargs):
        assert connection is conn
        if expected_version != case["version"]:
            raise StateConflict("version changed")
        projection = CaseProjection(**{key: case[key] for key in
                                      ("status", "version", "state_json", "intent", "issue_code", "sentiment", "owner_team_id")})
        case.update(asdict(apply_event(projection, event_type, payload)))
        events.append(event_type)
        return deepcopy(case)

    monkeypatch.setattr("app.application.controller.transition_case", transition)
    manifest = TeamManifest(team_id="dining", display_name="식당 일정", contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"], capabilities=["dining.itinerary"], accepted_case_types=["dining"],
        required_context=[], allowed_tools=[], knowledge_scope=[], implementation_revision="resume-unit")
    registry = TeamRegistry([SimpleNamespace(manifest=manifest)])
    repository = SimpleNamespace(get_case=lambda connection, **kwargs: deepcopy(case))
    controller = Controller(registry, connection_factory=lambda: conn, repository=repository,
                            case_service=service, policy_search=lambda *a, **k: [])
    return SimpleNamespace(controller=controller, conn=conn, case=case, events=events,
                           token=token, transition=transition)


def reply(recovery, **overrides):
    options = dict(tenant_id=recovery.case["tenant_id"], case_id=recovery.case["case_id"],
                   token=recovery.token, event_id="travel-reply-30", message="30분이요")
    options.update(overrides)
    return asyncio.run(recovery.controller.resume(**options))


def test_team_exception_collects_after_failed_run_cleanup_and_preserves_exception(recovery, monkeypatch):
    state = recovery
    state.case['status'] = CaseStatus.RUNNING
    steps = []
    failure = RuntimeError('private provider response')
    monkeypatch.setattr(state.controller.case_service, 'start_run', lambda *a, **k: uuid4())
    monkeypatch.setattr(state.controller, '_task', lambda *a, **k: object())
    monkeypatch.setattr(state.controller, '_abandon_run', lambda *a: steps.append('cleanup'))

    async def execute(task):
        raise failure

    def collect(payload):
        steps.append('collect')
        assert payload['customer_id'] == state.case['customer_id']
        assert payload['code'] == 'team_exception'
        assert 'private provider response' not in str(payload)
        return {'status': 'spooled'}

    monkeypatch.setattr(state.controller, '_execute_team_task', execute)
    state.controller.diagnostic_recorder = collect
    with pytest.raises(RuntimeError) as raised:
        asyncio.run(state.controller.run_case(tenant_id=state.case['tenant_id'], case_id=state.case['case_id']))
    assert raised.value is failure and steps == ['cleanup', 'collect']


def test_controller_collector_failure_is_visible_and_does_not_raise(recovery, caplog):
    def broken(payload):
        raise OSError('private diagnostic error')

    recovery.controller.diagnostic_recorder = broken
    assert recovery.controller._report_failure(recovery.case, 'team_exception') == {'status': 'collection_degraded'}
    assert 'status=collection_degraded' in caplog.text and 'private diagnostic error' not in caplog.text


def test_same_event_retries_interrupted_resuming_without_consuming_input_twice(recovery, monkeypatch):
    starts = []
    applied = []

    async def run_case(**kwargs):
        starts.append(recovery.case["status"])
        if len(starts) == 1:
            raise ConnectionError("injected stop before run start")
        recovery.transition(recovery.conn, expected_version=recovery.case["version"],
            event_type=EventType.RESUMED, payload={"resume_node": "validate_input"})
        applied.append(recovery.case["state_json"]["customer_input"])
        recovery.transition(recovery.conn, expected_version=recovery.case["version"],
            event_type=EventType.COMPLETED, payload={"answer_ref": "travel-unit-answer"})
        return {"status": "resolved"}

    monkeypatch.setattr(recovery.controller, "run_case", run_case)
    with pytest.raises(ConnectionError):
        reply(recovery)
    assert recovery.case["status"] == CaseStatus.RESUMING
    assert recovery.conn.commits == 1
    assert reply(recovery)["status"] == "resolved"
    assert reply(recovery)["idempotent"] is True
    assert starts == [CaseStatus.RESUMING, CaseStatus.RESUMING]
    assert applied == ["30분이요"]
    assert recovery.case["state_json"]["customer_input_history"] == ["30분이요"]
    assert recovery.events.count(EventType.VALID_INPUT) == 1
    assert recovery.events.count(EventType.RESUMED) == 1


@pytest.mark.parametrize("status", [CaseStatus.RESUMING, CaseStatus.RUNNING])
def test_same_event_never_starts_when_active_run_exists(recovery, monkeypatch, status):
    async def interrupted(**kwargs):
        raise ConnectionError("injected stop")

    monkeypatch.setattr(recovery.controller, "run_case", interrupted)
    with pytest.raises(ConnectionError):
        reply(recovery)
    recovery.case["status"] = status
    recovery.conn.active = True
    result = reply(recovery)
    assert result["idempotent"] is True and result["status"] == status
    assert recovery.events == [EventType.VALID_INPUT]


def test_resuming_retry_keeps_team_gate_and_original_input(recovery, monkeypatch):
    async def interrupted(**kwargs):
        raise ConnectionError("injected stop")

    monkeypatch.setattr(recovery.controller, "run_case", interrupted)
    with pytest.raises(ConnectionError):
        reply(recovery)
    before = deepcopy(recovery.case)
    registry = TeamRegistry()
    registry.declare_unavailable("dining", "disabled")
    recovery.controller.registry = registry
    with pytest.raises(TeamUnavailable, match="disabled"):
        reply(recovery)
    assert recovery.case == before


def test_resuming_retry_race_returns_in_progress_state(recovery, monkeypatch):
    async def first_interrupted(**kwargs):
        raise ConnectionError("injected stop")

    monkeypatch.setattr(recovery.controller, "run_case", first_interrupted)
    with pytest.raises(ConnectionError):
        reply(recovery)
    calls = []

    async def active_race(**kwargs):
        calls.append(True)
        raise ActiveRunError("another retry started")

    monkeypatch.setattr(recovery.controller, "run_case", active_race)
    result = reply(recovery)
    assert calls == [True]
    assert result["status"] == CaseStatus.RESUMING and result["idempotent"] is True
    assert recovery.events == [EventType.VALID_INPUT]


def test_expired_resume_preserves_typed_cause_and_does_not_apply_input(recovery, monkeypatch):
    recovery.case["state_json"]["resume_token_expires_at"] = "2020-01-01T00:00:00+00:00"

    async def forbidden(**kwargs):
        pytest.fail("expired explicit token must not run")

    monkeypatch.setattr(recovery.controller, "run_case", forbidden)
    with pytest.raises(ResumeTokenExpired) as caught:
        reply(recovery)
    assert isinstance(caught.value, ControllerError)
    assert recovery.case["status"] == CaseStatus.ESCALATED
    assert recovery.events == [EventType.WAIT_EXPIRED]
    assert not recovery.case["state_json"]["resume_token_used"]
    assert "customer_input" not in recovery.case["state_json"]
    assert recovery.conn.commits == 1


def test_disabled_owner_expiry_preserves_waiting_token_and_input(recovery):
    recovery.case["state_json"]["resume_token_expires_at"] = "2020-01-01T00:00:00+00:00"
    registry = TeamRegistry()
    registry.declare_unavailable("dining", "disabled")
    recovery.controller.registry = registry
    before = deepcopy(recovery.case)
    with pytest.raises(TeamUnavailable, match="disabled"):
        reply(recovery)
    assert recovery.case == before and recovery.events == []


def test_interrupted_reply_cannot_reuse_request_for_a_different_message(recovery, monkeypatch):
    async def interrupted(**kwargs):
        raise ConnectionError("injected stop")

    monkeypatch.setattr(recovery.controller, "run_case", interrupted)
    with pytest.raises(ConnectionError):
        reply(recovery)
    before = deepcopy(recovery.case)
    with pytest.raises(StateConflict):
        reply(recovery, message="60분이요")
    assert recovery.case == before


@pytest.mark.parametrize("expired", [True, False])
def test_explicit_bad_or_expired_token_keeps_http_error_contract(recovery, monkeypatch, expired):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.presentation.api import cases
    from app.presentation.security import Principal

    if expired:
        recovery.case["state_json"]["resume_token_expires_at"] = "2020-01-01T00:00:00+00:00"
    monkeypatch.setattr(cases, "get_connection", lambda: recovery.conn)
    monkeypatch.setattr(cases, "repository", recovery.controller.repository)
    application = FastAPI()
    application.include_router(cases.build_router(controller=recovery.controller))
    route = next(r for r in application.routes if getattr(r, "path", "") == "/v1/cases/{case_id}/messages")
    principal_dependency = route.dependant.dependencies[0].call
    application.dependency_overrides[principal_dependency] = lambda: Principal(
        tenant_id=recovery.case["tenant_id"], key_id="resume-unit", scopes=frozenset({"case:write"}))
    with TestClient(application) as client:
        response = client.post(f"/v1/cases/{recovery.case['case_id']}/messages", json={
            "request_id": "explicit-expired", "message": "30분이요",
            "token": recovery.token if expired else "wrong-travel-token"})
    assert response.status_code == 401
    assert response.json()["detail"]["error"]["code"] == "invalid_resume_token"
    assert recovery.case["status"] == (CaseStatus.ESCALATED if expired else CaseStatus.WAITING_INPUT)
    assert "customer_input" not in recovery.case["state_json"]
