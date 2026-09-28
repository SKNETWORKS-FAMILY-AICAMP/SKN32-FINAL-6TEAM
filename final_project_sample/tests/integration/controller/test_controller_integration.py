from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import acop_basement.core.settings as settings_module
from acop_basement.application.case_service import CaseService, ResumeTokenError
from acop_basement.application.controller import Controller, ControllerError
from acop_basement.core.contracts import ActionProposal, ContextPack, Evidence, NextAction, StateConflict, TeamManifest, TeamResult
from acop_basement.core.idempotency import idempotency_key
from acop_basement.core.registry import RegistryError, TeamRegistry
from acop_basement.core.transition import OutboxMessage, replay_case, transition_case
from acop_basement.domain.events import EventType
from acop_basement.infrastructure.db.repository import create_case, get_case, get_case_events
from acop_basement.infrastructure.db.session import get_connection
from acop_basement.infrastructure.messaging.outbox import OutboxBrokerAdapter
from acop_basement.infrastructure.messaging.worker import OutboxWorker
from acop_basement.presentation import security
from acop_basement.presentation.api.app import app
from acop_basement.tools.read_tools import ReadToolbox, ToolLoopExceeded


class FakeTeam:
    manifest = TeamManifest(
        team_id="fake_billing", display_name="Fake Billing", contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"], capabilities=["billing.investigate"],
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
        "capabilities": ["entitlement.diagnose"], "accepted_case_types": ["technical"],
        "knowledge_scope": ["technical"],
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


class WaitForInputTeam(FakeTeam):
    """★버그사냥 2026-08-17 (라운드 04·06·08) — WAIT_FOR_INPUT/Controller.resume()
    경로는 이 세션 전까지 어떤 테스트에도 없었다. 첫 호출은 고객 추가 입력을
    기다리고, 재개되면(두 번째 호출) 완료한다."""
    manifest = FakeTeam.manifest.model_copy(update={
        "team_id": "fake_wait_input", "display_name": "Fake Wait Input",
    })

    async def execute(self, task):
        self.calls += 1
        if self.calls == 1:
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id, outcome="waiting",
                              confidence=1, next_action=NextAction.WAIT_FOR_INPUT, wait_reason="customer_input",
                              required_input_schema={"type": "object", "properties": {"answer": {"type": "string"}}})
        evidence = [Evidence(evidence_id="wait-input:e2e", source_type="db", source_id="fake",
                             claim="deterministic fixture", value={"ok": True}, confidence=1,
                             observed_at=datetime.now(UTC))]
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id, outcome="completed",
                          confidence=1, answer="resolved after resume", evidence=evidence, next_action=NextAction.RESPOND)


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
                    cur.execute("DELETE FROM incidents WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM payments WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM entitlements WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM subscriptions WHERE tenant_id=%s", (tenant,))
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


def test_e2e_resume_completes_with_the_real_token(db):
    """★버그사냥 2026-08-17 (라운드 04·06·08) — Controller.resume() 은 이 세션
    전까지 어떤 테스트에도 없이 죽어 있었다. 실제 발급된 토큰으로 끝까지
    (waiting_input -> resuming -> running -> resolved) 완주하는지 처음으로 증명한다.
    """
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    team = WaitForInputTeam()
    controller = Controller(TeamRegistry([team]), policy_search=fake_policy, context_broker=FakeContextBroker())
    first = asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    assert first["status"] == "waiting_input"
    real_token = first["resume_token"]
    assert real_token

    # ★resume() 자신이 내부에서 run_case() 까지 부른다(controller.py:280) — 검증
    #   부터 재실행·완료까지 한 호출로 끝난다. 여기서 또 run_case() 를 부르면
    #   이미 resolved 된 Case 에 완료 이벤트가 두 번 적용돼 InvalidTransition
    #   이 난다 — 실제로 이 자리에서 그렇게 재현됐다.
    outcome = asyncio.run(controller.resume(tenant_id=tenant, case_id=case_id, token=real_token, event_id="req-1"))
    assert outcome.get("idempotent") is not True
    assert outcome["status"] == "resolved"
    with get_connection() as check:
        assert [(e["event_type"], e["aggregate_version"]) for e in get_case_events(check, tenant_id=tenant, case_id=case_id)] == [
            ("created", 1), ("classified", 2), ("routed", 3), ("missing_input", 4),
            ("valid_input", 5), ("resumed", 6), ("completed", 7)]


def test_resume_with_the_wrong_token_is_rejected_and_escalates(db):
    """★가짜 토큰(고객 메시지 원문의 해시 같은 것)으로는 재개할 수 없다 —
    라운드 04·06 이 찾은 원래 결함이 바로 이걸 검증 안 했다는 것이었다."""
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    team = WaitForInputTeam()
    controller = Controller(TeamRegistry([team]), policy_search=fake_policy, context_broker=FakeContextBroker())
    first = asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    assert first["status"] == "waiting_input"

    with pytest.raises(ControllerError):
        asyncio.run(controller.resume(tenant_id=tenant, case_id=case_id, token="not-the-real-token", event_id="req-1"))
    with get_connection() as check:
        assert case_versions(check, tenant, case_id)[0] == "escalated"


def test_resume_token_cannot_be_reused(db):
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    team = WaitForInputTeam()
    controller = Controller(TeamRegistry([team]), policy_search=fake_policy, context_broker=FakeContextBroker())
    first = asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    real_token = first["resume_token"]

    asyncio.run(controller.resume(tenant_id=tenant, case_id=case_id, token=real_token, event_id="req-1"))
    # ★같은 event_id 재시도는 idempotent 로 조용히 통과한다(재실행 아님).
    replay = asyncio.run(controller.resume(tenant_id=tenant, case_id=case_id, token=real_token, event_id="req-1"))
    assert replay.get("idempotent") is True
    # ★다른 event_id 로 같은 토큰을 다시 쓰면(진짜 재사용 시도) 거부된다.
    with pytest.raises(ControllerError):
        asyncio.run(controller.resume(tenant_id=tenant, case_id=case_id, token=real_token, event_id="req-2"))


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


def test_e2e_free_pro_entitlement_mismatch_is_read_only(db):
    conn, tenant = db
    case_id, customer = seed_case(conn, tenant, intent="technical", issue="entitlement_access")
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("INSERT INTO subscriptions (tenant_id,customer_id,plan,status,started_at) VALUES (%s,%s,'Pro','active',now())", (tenant, customer))
            cur.execute("INSERT INTO entitlements (tenant_id,customer_id,plan,source) VALUES (%s,%s,'Free','seed')", (tenant, customer))
    conn.commit()
    with conn.cursor() as cur:
        cur.execute("SELECT plan,source,updated_at FROM entitlements WHERE tenant_id=%s AND customer_id=%s", (tenant, customer))
        before = cur.fetchone()
    team = FakeTechnicalTeam()
    result = asyncio.run(Controller(TeamRegistry([team]), policy_search=fake_policy,
                                    context_broker=FakeContextBroker()).run_case(tenant_id=tenant, case_id=case_id))
    assert result["status"] == "resolved"
    with conn.cursor() as cur:
        cur.execute("SELECT plan,source,updated_at FROM entitlements WHERE tenant_id=%s AND customer_id=%s", (tenant, customer))
        assert cur.fetchone() == before


def test_replay_case_is_projection_equivalent(db):
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    with conn.transaction():
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=2, event_type=EventType.ROUTED,
                        payload={"owner_team_id": "fake_billing", "capability": "billing.investigate"}, actor_type="test")
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
                            payload={"owner_team_id": "fake_billing", "capability": "billing.investigate"}, actor_type="test", outbox=[message])
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


def test_loop_guard_rejects_same_tool_and_arguments(db):
    toolbox = ReadToolbox({"read.policy": lambda scope, *, query, **_: []})
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
                                    payload={"owner_team_id": "fake_billing", "capability": "billing.investigate"}, actor_type="test")
                return "success"
            except StateConflict:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(outcomes) == ["conflict", "success"]
