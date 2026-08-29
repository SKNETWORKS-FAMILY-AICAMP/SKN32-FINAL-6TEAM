from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.core.settings as settings_module
from app.application.case_service import CaseService, ResumeTokenError
from app.application.controller import Controller, ControllerError
from app.core.contracts import ActionProposal, ContextPack, Evidence, InvalidTransition, NextAction, StateConflict, TeamManifest, TeamResult
from app.core.idempotency import idempotency_key
from app.core.registry import RegistryError, TeamRegistry
from app.core.transition import OutboxMessage, replay_case, transition_case
from app.domain.events import EventType
from app.infrastructure.db.repository import create_case, get_case, get_case_events
from app.infrastructure.db.session import get_connection
from app.infrastructure.messaging.outbox import OutboxBrokerAdapter
from app.infrastructure.messaging.worker import OutboxWorker
from app.presentation import security
from app.presentation.api.app import app
from app.tools.read_tools import ReadToolbox, ToolLoopExceeded


class FakeTeam:
    manifest = TeamManifest(
        team_id="fake_order", display_name="Fake Order", contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"], capabilities=["order.investigate"],
        accepted_case_types=["billing"], required_context=["case_state", "policy", "db_facts", "history"],
        allowed_tools=[], knowledge_scope=["billing"], implementation_revision="test",
    )

    def __init__(self, wait_first: bool = False):
        self.calls = 0
        self.wait_first = wait_first

    async def execute(self, task):
        self.calls += 1
        if self.wait_first and self.calls == 1:
            proposal = ActionProposal(action_type="refund.request", arguments={"reason": "post_cancel_charge"},
                                      idempotency_key="test-refund-" + uuid4().hex, approval_required=True,
                                      risk_level="high")
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id, outcome="waiting",
                              confidence=1, next_action=NextAction.WAIT_FOR_APPROVAL, wait_reason="human_approval",
                              action_proposals=[proposal])
        evidence = [Evidence(evidence_id="fake:e2e", source_type="db", source_id="fake",
                             claim="deterministic fixture", value={"ok": True}, confidence=1,
                             observed_at=datetime.now(UTC))]
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id, outcome="completed",
                          confidence=1, answer="resolved by fake team", evidence=evidence, next_action=NextAction.RESPOND)


class FakeTechnicalTeam(FakeTeam):
    manifest = FakeTeam.manifest.model_copy(update={
        "team_id": "fake_technical", "display_name": "Fake Technical",
        "capabilities": ["return.diagnose"], "accepted_case_types": ["return"],
        "knowledge_scope": ["return"],
    })


class RepeatApprovalTeam(FakeTeam):
    async def execute(self, task):
        evidence = [Evidence(evidence_id="repeat:e2e", source_type="db", source_id="repeat",
                             claim="deterministic fixture", value={"ok": True}, confidence=1,
                             observed_at=datetime.now(UTC))]
        proposal = ActionProposal(action_type="refund.request", arguments={"reason": "repeat"},
                                  idempotency_key="team-controlled-" + uuid4().hex,
                                  approval_required=True, risk_level="high")
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id, outcome="waiting",
                          confidence=1, evidence=evidence, next_action=NextAction.WAIT_FOR_APPROVAL,
                          wait_reason="human_approval", action_proposals=[proposal])


class DemoTeam(FakeTeam):
    manifest = FakeTeam.manifest.model_copy(update={
        "team_id": "demo_investigator", "display_name": "Demo Investigator",
        "capabilities": ["demo.investigate"], "accepted_case_types": ["demo"],
        "knowledge_scope": ["demo"],
    })


class FakeContextBroker:
    def build(self, inputs):
        return ContextPack(pack_id=uuid4(), case_id=inputs.case_id, team_id=inputs.team_id,
                           tenant_id=inputs.tenant_id, knowledge_scope=inputs.knowledge_scope,
                           current_state=inputs.current_state, estimated_input_tokens=0)


@pytest.fixture()
def db():
    tenant = "test_" + uuid4().hex
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "controller integration"))
        try:
            yield conn, tenant
        finally:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM action_approvals WHERE action_id IN (SELECT action_id FROM action_requests WHERE tenant_id=%s)", (tenant,))
                    cur.execute("DELETE FROM team_tasks WHERE run_id IN (SELECT run_id FROM agent_runs WHERE tenant_id=%s)", (tenant,))
                    cur.execute("DELETE FROM llm_calls WHERE run_id IN (SELECT run_id FROM agent_runs WHERE tenant_id=%s)", (tenant,))
                    cur.execute("DELETE FROM agent_runs WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM action_requests WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM case_events WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM outbox WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM returns WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM shipments WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM order_items WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM orders WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM customer_cases WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM customers WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (tenant,))


def seed_case(conn, tenant, *, intent="billing", issue="invoice"):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id", (tenant, uuid4().hex))
        customer = cur.fetchone()[0]
    case_id = create_case(conn, tenant_id=tenant, customer_id=customer, subject="deterministic controller test")
    with conn.transaction():
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=0, event_type=EventType.CREATED,
                        payload={"channel": "test", "message": "deterministic"}, actor_type="test")
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=1, event_type=EventType.CLASSIFIED,
                        payload={"intent": intent, "issue_code": issue, "sentiment": "neutral"}, actor_type="test")
    conn.commit()
    return case_id, customer


def case_versions(conn, tenant, case_id):
    with conn.cursor() as cur:
        cur.execute("SELECT status,version FROM customer_cases WHERE tenant_id=%s AND case_id=%s", (tenant, case_id))
        return cur.fetchone()


def fake_policy(*_args):
    return []


def test_controller_capability_comes_from_registered_new_team():
    controller = Controller(TeamRegistry([DemoTeam()]))
    assert controller._capability({"intent": "demo", "issue_code": "anything"}) == "demo.investigate"


def test_inactive_team_is_not_resolved():
    team = DemoTeam()
    team.manifest = team.manifest.model_copy(update={"active": False})
    registry = TeamRegistry([team])
    with pytest.raises(RegistryError):
        registry.resolve(case_type="demo", intent="demo")


def test_e2e_cancelled_customer_post_charge_approval_flow(db, monkeypatch):
    conn, tenant = db
    case_id, customer = seed_case(conn, tenant)
    fake = FakeTeam(wait_first=True)
    controller = Controller(TeamRegistry([fake]), policy_search=fake_policy, context_broker=FakeContextBroker())
    first = asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    assert first["status"] == "waiting_approval"
    with conn.cursor() as cur:
        cur.execute("SELECT action_id FROM action_requests WHERE tenant_id=%s AND case_id=%s", (tenant, case_id))
        action_id = cur.fetchone()[0]

    original = settings_module.get_settings()
    test_settings = original.model_copy(update={"tenant_id": tenant})
    monkeypatch.setattr(settings_module, "get_settings", lambda: test_settings)
    monkeypatch.setattr(security, "get_settings", lambda: test_settings)
    token = "Bearer " + security._development_key("action:approve", original.secret_key)
    response = TestClient(app).post(f"/v1/cases/{case_id}/actions/{action_id}/approve",
                                    headers={"Authorization": token},
                                    json={"decision": "approved", "approver_id": "test-operator"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "resuming"
    with get_connection() as check:
        assert case_versions(check, tenant, case_id) == ("resuming", 5)
        assert [(e["event_type"], e["aggregate_version"]) for e in get_case_events(check, tenant_id=tenant, case_id=case_id)] == [
            ("created", 1), ("classified", 2), ("routed", 3), ("approval_required", 4), ("approved", 5)]
        result = asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
        assert result["status"] == "resolved"
        assert [(e["event_type"], e["aggregate_version"]) for e in get_case_events(check, tenant_id=tenant, case_id=case_id)] == [
            ("created", 1), ("classified", 2), ("routed", 3), ("approval_required", 4), ("approved", 5),
            ("resumed", 6), ("completed", 7)]


def test_approval_rerun_does_not_create_action_request_again(db):
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    controller = Controller(TeamRegistry([RepeatApprovalTeam()]), policy_search=fake_policy,
                            context_broker=FakeContextBroker())
    first = asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    assert first["status"] == "waiting_approval"
    with conn.cursor() as cur:
        cur.execute("SELECT count(*), min(idempotency_key) FROM action_requests WHERE tenant_id=%s AND case_id=%s", (tenant, case_id))
        count, stored_key = cur.fetchone()
    expected = idempotency_key(tenant_id=tenant, request_id=str(case_id), action_type="refund.request", business_subject=str(case_id))
    assert count == 1
    assert stored_key == expected

    with conn.transaction():
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=4,
                        event_type=EventType.APPROVED, payload={"action_id": "test-approval", "approver_id": "test"}, actor_type="test")
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=5,
                        event_type=EventType.RESUMED, payload={"resume_node": "team.execute"}, actor_type="test")
    conn.commit()
    result = asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    assert result["status"] == "waiting_approval"
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM action_requests WHERE tenant_id=%s AND case_id=%s", (tenant, case_id))
        assert cur.fetchone()[0] == 1


def test_idempotency_key_separates_business_subject_and_action_type():
    common = {"tenant_id": "tenant", "request_id": "request", "business_subject": "case-a"}
    refund = idempotency_key(**common, action_type="refund.request")
    support = idempotency_key(**common, action_type="support.request")
    other_case = idempotency_key(**{**common, "business_subject": "case-b"}, action_type="refund.request")
    assert len(refund) == 64 and 8 <= len(refund) <= 128
    assert refund != support
    assert refund != other_case


def test_idempotency_key_preserves_field_boundaries():
    common = {"action_type": "action", "business_subject": "subject"}
    left = idempotency_key(tenant_id="ab", request_id="c", **common)
    right = idempotency_key(tenant_id="a", request_id="bc", **common)
    assert left != right


def test_run_persists_fixed_graph_revision_and_checkpoint_is_not_projection_state(db):
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    team = FakeTeam()
    controller = Controller(TeamRegistry([team]), policy_search=fake_policy,
                            context_broker=FakeContextBroker(), graph_revision="test-graph-v1")
    result = asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    run_id = result["run_id"]
    with get_connection() as check:
        with check.cursor() as cur:
            cur.execute("SELECT graph_revision FROM agent_runs WHERE tenant_id=%s AND run_id=%s", (tenant, run_id))
            revision = cur.fetchone()[0]
            cur.execute("SELECT count(DISTINCT graph_revision) FROM agent_runs WHERE tenant_id=%s AND case_id=%s", (tenant, case_id))
            revision_count = cur.fetchone()[0]
        assert revision == "test-graph-v1"
        assert revision_count == 1
        before = case_versions(check, tenant, case_id)
        checkpoint = controller.case_service.checkpoint(case_id=case_id, run_id=uuid4(), node_name="previous-node",
                                                         runtime_state={"case_version": 0})
        checkpoint["runtime_state"]["case_version"] = -1
        after = case_versions(check, tenant, case_id)
        assert checkpoint["graph_revision"] == revision
        assert after == before


def test_routing_failure_escalates_when_no_registered_team(db):
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant, intent="unhandled", issue="unknown")
    result = asyncio.run(Controller(TeamRegistry([]), policy_search=fake_policy,
                                    context_broker=FakeContextBroker()).run_case(tenant_id=tenant, case_id=case_id))
    assert result["status"] == "escalated"
    with get_connection() as check:
        events = get_case_events(check, tenant_id=tenant, case_id=case_id)
        assert events[-1]["event_type"] == "routing_failed"


def test_e2e_delivery_inquiry_does_not_touch_the_order(db):
    """★조회형 문의는 도메인 데이터를 건드리지 않는다.

    sample(구독)에서는 Free/Pro 권한 불일치였다. 커머스에서는 **배송 조회**가
    같은 성질을 갖는다 — 답을 만들되 주문·배송 상태를 바꾸지 않는다.
    """
    conn, tenant = db
    case_id, customer = seed_case(conn, tenant, intent="return", issue="delivery_status")
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("INSERT INTO orders (tenant_id,customer_id,order_no,total_cents,item_count,status) "
                        "VALUES (%s,%s,'ORD-RO-1',50000,2,'shipped') RETURNING order_id", (tenant, customer))
            order_id = cur.fetchone()[0]
            cur.execute("INSERT INTO shipments (tenant_id,customer_id,order_id,carrier,status) "
                        "VALUES (%s,%s,%s,'CJ','in_transit')", (tenant, customer, order_id))
    conn.commit()
    with conn.cursor() as cur:
        cur.execute("SELECT status,carrier FROM shipments WHERE tenant_id=%s AND customer_id=%s",
                    (tenant, customer))
        before = cur.fetchone()
    team = FakeTechnicalTeam()
    result = asyncio.run(Controller(TeamRegistry([team]), policy_search=fake_policy,
                                    context_broker=FakeContextBroker()).run_case(tenant_id=tenant, case_id=case_id))
    assert result["status"] == "resolved"
    with conn.cursor() as cur:
        cur.execute("SELECT status,carrier FROM shipments WHERE tenant_id=%s AND customer_id=%s",
                    (tenant, customer))
        assert cur.fetchone() == before, "조회형 문의가 배송 상태를 바꿨다"


def test_replay_case_is_projection_equivalent(db):
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    with conn.transaction():
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=2, event_type=EventType.ROUTED,
                        payload={"owner_team_id": "fake_order", "capability": "order.investigate"}, actor_type="test")
    original = get_case(conn, tenant_id=tenant, case_id=case_id)
    replay = replay_case(conn, tenant_id=tenant, case_id=case_id)
    assert (replay.status.value, replay.version) == (original["status"], original["version"])


def test_transition_exception_rolls_back_event_and_outbox(db):
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    message = OutboxMessage(topic="test.atomic", dedupe_key="atomic-" + tenant, payload={"case_id": str(case_id)})
    with pytest.raises(RuntimeError):
        with conn.transaction():
            transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=2, event_type=EventType.ROUTED,
                            payload={"owner_team_id": "fake_order", "capability": "order.investigate"}, actor_type="test", outbox=[message])
            raise RuntimeError("injected failure")
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM case_events WHERE tenant_id=%s AND case_id=%s AND aggregate_version=3", (tenant, case_id))
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM outbox WHERE tenant_id=%s AND dedupe_key=%s", (tenant, message.dedupe_key))
        assert cur.fetchone()[0] == 0


def test_outbox_duplicate_is_delivered_once(db):
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    adapter = OutboxBrokerAdapter(lambda: get_connection())
    payload = {"tenant_id": tenant, "case_id": str(case_id), "value": 1}
    first = asyncio.run(adapter.publish("test.once", payload, "same-" + tenant))
    second = asyncio.run(adapter.publish("test.once", payload, "same-" + tenant))
    assert first != second  # first returns message_id; duplicate returns its dedupe key
    delivered = []
    worker = OutboxWorker(get_connection, delivered.append, tenant_id=tenant)
    assert worker.process_once() is True
    assert worker.process_once() is False
    assert len(delivered) == 1


def test_resume_token_is_single_use_expiring_and_hashed(db):
    service = CaseService()
    token = service.new_resume_token()
    metadata = service.resume_metadata(token, "customer_input")
    assert token not in str(metadata)
    assert metadata["resume_token_hash"] == service.token_hash(token)
    case = {"state_json": metadata}
    assert service.validate_resume(case, token) is None
    case["state_json"]["resume_token_used"] = True
    with pytest.raises(ResumeTokenError, match="already been used"):
        service.validate_resume(case, token)
    expired = {"state_json": {**metadata, "resume_token_used": False,
                               "resume_token_expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()}}
    with pytest.raises(ResumeTokenError, match="expired"):
        service.validate_resume(expired, token)


def test_expired_resume_escalation_survives_outer_rollback(db):
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    service = CaseService()
    with conn.transaction():
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=2,
                        event_type=EventType.ROUTED,
                        payload={"owner_team_id": "fake_order", "capability": "order.investigate"}, actor_type="test")
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=3,
                        event_type=EventType.MISSING_INPUT,
                        payload={"required_input_schema": {}, "state_patch": service.resume_metadata("valid", "customer_input")},
                        actor_type="test")
    conn.commit()

    controller = Controller(TeamRegistry([FakeTeam()]), policy_search=fake_policy,
                            context_broker=FakeContextBroker())
    with pytest.raises(ControllerError, match="resume token"):
        asyncio.run(controller.resume(tenant_id=tenant, case_id=case_id, token="expired"))

    with get_connection() as check:
        assert case_versions(check, tenant, case_id) == ("escalated", 5)


def test_stale_resume_on_resolved_case_is_handled_without_invalid_transition(db, caplog):
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    controller = Controller(TeamRegistry([FakeTeam()]), policy_search=fake_policy,
                            context_broker=FakeContextBroker())
    assert asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))["status"] == "resolved"

    with pytest.raises(ControllerError, match="resume token"):
        asyncio.run(controller.resume(tenant_id=tenant, case_id=case_id, token="stale"))

    assert "stale resume token ignored" in caplog.text
    with get_connection() as check:
        assert case_versions(check, tenant, case_id)[0] == "resolved"


def test_valid_resume_race_invalid_transition_is_logged_and_ignored(db, monkeypatch, caplog):
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    service = CaseService()
    token = service.new_resume_token()
    with conn.transaction():
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=2,
                        event_type=EventType.ROUTED,
                        payload={"owner_team_id": "fake_order", "capability": "order.investigate"}, actor_type="test")
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=3,
                        event_type=EventType.MISSING_INPUT,
                        payload={"required_input_schema": {}, "state_patch": service.resume_metadata(token, "customer_input")},
                        actor_type="test")
    conn.commit()

    controller = Controller(TeamRegistry([FakeTeam()]), policy_search=fake_policy,
                            context_broker=FakeContextBroker())

    def raise_invalid_transition(*args, **kwargs):
        raise InvalidTransition("case already transitioned")

    monkeypatch.setattr(controller, "_transition_with_retry", raise_invalid_transition)
    outcome = asyncio.run(controller.resume(tenant_id=tenant, case_id=case_id, token=token))

    assert outcome["stale"] is True
    assert outcome["status"] == "waiting_input"
    assert "stale resume transition ignored" in caplog.text


def test_loop_guard_rejects_same_tool_and_arguments(db):
    toolbox = ReadToolbox(get_connection, policy_search=lambda *_: [])
    context = type("Context", (), {"tenant_id": "test", "case_id": uuid4(), "knowledge_scope": ["billing"],
                                    "current_state": {"customer_id": str(uuid4())}})()
    seen = set()
    toolbox.call("read.policy", context, {"query": "same"}, ["read.policy"], seen)
    with pytest.raises(ToolLoopExceeded):
        toolbox.call("read.policy", context, {"query": "same"}, ["read.policy"], seen)


def test_same_expected_version_has_one_success_and_one_state_conflict(db):
    _, tenant = db
    with get_connection() as setup:
        case_id, _ = seed_case(setup, tenant)

    def attempt():
        with get_connection() as conn:
            try:
                with conn.transaction():
                    transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=2, event_type=EventType.ROUTED,
                                    payload={"owner_team_id": "fake_order", "capability": "order.investigate"}, actor_type="test")
                return "success"
            except StateConflict:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(outcomes) == ["conflict", "success"]
