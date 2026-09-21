"""승인 없이 적용되는 제안 — 조건 · 한 트랜잭션 · 실패하면 되돌리고 사람에게 · 두 번 적용하지 않는다.

★`[결정 2026-09-17]` wiki `actions/approval.md` 「승인 없이 적용되는 제안」.
  전에는 `respond` 결과의 제안이 저장도 실행도 안 되고 사라졌다.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.case_intake import open_case
from app.application.controller import Controller
from app.core.actions import ActionConflict, ActionHandlers, AppliedAction
from app.core.contracts import ActionProposal, ContextPack, Evidence, NextAction, TeamManifest, TeamResult
from app.core.idempotency import idempotency_key
from app.core.registry import TeamRegistry
from app.core.transition import OutboxMessage
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.case_engine import cleanup_tenant

TOPIC = "test.applied"


class Broker:
    def build(self, inputs):
        return ContextPack(pack_id=uuid4(), case_id=inputs.case_id, team_id=inputs.team_id,
                           tenant_id=inputs.tenant_id, knowledge_scope=inputs.knowledge_scope,
                           current_state=inputs.current_state, estimated_input_tokens=0)


class ProposingTeam:
    manifest = TeamManifest(team_id="demo", display_name="demo", contract_name="a_cop.team_task",
                            supported_contract_versions=["1.0"], capabilities=["demo.act"],
                            accepted_case_types=["demo"], required_context=["case_state"],
                            allowed_tools=[], knowledge_scope=["demo"], implementation_revision="test")

    def __init__(self, *, action_type="demo.apply", risk="low", subject="thing-1"):
        self.action_type, self.risk, self.subject = action_type, risk, subject

    async def execute(self, task):
        evidence = [Evidence(evidence_id="demo:1", source_type="db", source_id="demo", claim="fixture",
                             value={"ok": True}, confidence=1, observed_at=datetime.now(UTC))]
        proposal = ActionProposal(action_type=self.action_type, arguments={"target": self.subject},
                                  idempotency_key="team-" + uuid4().hex, approval_required=False,
                                  risk_level=self.risk)
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id, outcome="completed",
                          confidence=1, answer="바꿨습니다", evidence=evidence, next_action=NextAction.RESPOND,
                          action_proposals=[proposal])


class Handler:
    action_type = "demo.apply"
    auto_apply = True

    def __init__(self, *, conflict=False):
        self.calls, self.conflict = 0, conflict

    def subject(self, arguments):
        return str(arguments["target"])

    def apply(self, conn, *, tenant_id, customer_id, case_id, arguments):
        self.calls += 1
        if self.conflict:
            # ★실패하기 전에 쓴 것이 되돌려지는지 본다
            with conn.cursor() as cur:
                cur.execute("INSERT INTO outbox (tenant_id, topic, dedupe_key, payload_json) VALUES (%s,%s,%s,%s)",
                            (tenant_id, TOPIC, "written-before-conflict", "{}"))
            raise ActionConflict("moved")
        return AppliedAction(result_ref=f"demo:{arguments['target']}:applied",
                             summary={"target": arguments["target"]},
                             outbox=[OutboxMessage(topic=TOPIC, payload={"text": "바꿨습니다"},
                                                   dedupe_key=f"{arguments['target']}:applied")])


@pytest.fixture()
def tenant():
    tenant_id = "autoapply_" + uuid4().hex[:10]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant_id, "auto apply"))
        cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id",
                    (tenant_id, "c"))
        customer = cur.fetchone()[0]
    yield tenant_id, customer
    cleanup_tenant(tenant_id)


def _run(tenant, team, handlers, request_id="r-1"):
    tenant_id, customer = tenant
    controller = Controller(TeamRegistry([team]), context_broker=Broker(), policy_search=lambda *a: [],
                            connection_factory=get_connection, repository=repository,
                            action_handlers=ActionHandlers(handlers))
    with get_connection() as conn:
        opened = open_case(conn, repository=repository, tenant_id=tenant_id, customer_id=customer,
                           request_id=request_id, message="바꿔 주세요", channel="test", actor_type="api",
                           actor_id="test", labels={"intent": "other", "issue_code": "demo_thing",
                                                    "sentiment": "neutral"})
    asyncio.run(controller.run_case(tenant_id=tenant_id, case_id=opened.case_id))
    with get_connection() as conn, conn.cursor() as cur:
        case = repository.get_case(conn, tenant_id=tenant_id, case_id=opened.case_id)
        cur.execute("SELECT event_type, payload_json FROM case_events WHERE case_id=%s ORDER BY aggregate_version",
                    (opened.case_id,))
        events = cur.fetchall()
        cur.execute("SELECT status, provider_ref FROM action_requests WHERE tenant_id=%s AND action_type=%s",
                    (tenant_id, team.action_type))
        actions = cur.fetchall()
        cur.execute("SELECT dedupe_key FROM outbox WHERE tenant_id=%s AND topic=%s", (tenant_id, TOPIC))
        outbox = [row[0] for row in cur.fetchall()]
    return case, events, actions, outbox


def test_an_auto_proposal_is_applied_with_the_completion_and_the_notice(tenant):
    handler = Handler()
    case, events, actions, outbox = _run(tenant, ProposingTeam(), [handler])
    assert str(case["status"]) == "resolved" and handler.calls == 1
    assert actions == [("succeeded", "demo:thing-1:applied")]
    assert outbox == ["thing-1:applied"]
    assert case["state_json"]["applied_actions"][0]["result_ref"] == "demo:thing-1:applied"


@pytest.mark.parametrize("team,handlers,guardrail", [
    (ProposingTeam(action_type="demo.unknown"), [], "action_handler_missing"),
    (ProposingTeam(risk="high"), None, "action_requires_approval"),
])
def test_an_auto_proposal_that_does_not_qualify_is_escalated_not_dropped(tenant, team, handlers, guardrail):
    handlers = [Handler()] if handlers is None else handlers
    case, events, actions, outbox = _run(tenant, team, handlers)
    assert str(case["status"]) == "escalated"
    assert events[-1][0] == "guardrail_escalated" and events[-1][1]["guardrail"] == guardrail
    assert actions == [] and outbox == []


def test_a_conflict_rolls_back_what_the_handler_wrote_and_escalates(tenant):
    handler = Handler(conflict=True)
    case, events, actions, outbox = _run(tenant, ProposingTeam(), [handler])
    assert str(case["status"]) == "escalated" and events[-1][1]["guardrail"] == "action_target_changed"
    assert actions == [] and outbox == []        # ★실패 전에 쓴 바깥함 행도 남지 않는다


def test_the_same_target_is_not_applied_twice(tenant):
    tenant_id, customer = tenant
    key = idempotency_key(tenant_id=tenant_id, request_id="r-1", action_type="demo.apply", business_subject="thing-1")
    with get_connection() as conn, conn.transaction():
        seed = open_case(conn, repository=repository, tenant_id=tenant_id, customer_id=customer,
                         request_id="seed", message="앞선 요청", channel="test", actor_type="api", actor_id="t",
                         labels={"intent": "other", "issue_code": "demo_thing", "sentiment": "neutral"})
        repository.create_action_request(conn, tenant_id=tenant_id, case_id=seed.case_id, action_type="demo.apply",
                                         arguments={"target": "thing-1"}, idempotency_key=key,
                                         status="succeeded", provider_ref="demo:thing-1:earlier")
    handler = Handler()
    case, events, actions, outbox = _run(tenant, ProposingTeam(), [handler])
    assert str(case["status"]) == "resolved" and handler.calls == 0
    assert case["state_json"]["applied_actions"][0] == {"action_id": case["state_json"]["applied_actions"][0]["action_id"],
                                                        "action_type": "demo.apply",
                                                        "result_ref": "demo:thing-1:earlier", "replayed": True}
