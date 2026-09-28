"""제안이 실행 경로에 들어가기 전에 차단되는지 검사한다 (v7 §9-E · DoD-24·25).

★단위 테스트(`tests/unit/core/test_proposal_verification.py`)는 대조 함수를 검사한다.
  여기서는 **Controller 가 그 함수를 실제로 부르는지** 를 검사한다.

  이 프로젝트에서 "코드는 있는데 안 불린다" 로 여섯 번 당했다 —
  분류기 미연결 · RAG 검색 전건 실패 · Team LLM 미호출 · ablation flag 4종 · composer 미등록.
  **함수가 맞게 도는 것과 그 함수가 경로에 있는 것은 다른 주장이다.**
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from acop_basement.core.contracts import (ActionProposal, ContextPack, Evidence, NextAction,
                                TeamManifest, TeamResult)
from acop_basement.application.controller import Controller
from acop_basement.core.registry import TeamRegistry

from .test_controller_integration import (db, seed_case, fake_policy,  # noqa: F401
                                          case_versions, FakeContextBroker)

MANIFEST = TeamManifest(
    team_id="fake_billing", display_name="Fake Billing", contract_name="a_cop.team_task",
    supported_contract_versions=["1.0"], capabilities=["billing.investigate"],
    accepted_case_types=["billing"], required_context=["case_state", "policy", "db_facts", "history"],
    allowed_tools=[], knowledge_scope=["billing"], implementation_revision="test",
)


class ProposingTeam:
    """★지어낸 값을 제안하는 Team. 실제 LLM 이 할 수 있는 일을 고정값으로 재현한다."""

    manifest = MANIFEST

    def __init__(self, arguments: dict, *, evidence_ids: list[str] | None = None):
        self.arguments = arguments
        self.evidence_ids = evidence_ids

    async def execute(self, task):
        evidence = [Evidence(evidence_id="ev-real", source_type="db", source_id="x",
                             claim="fixture", value={}, confidence=1, observed_at=datetime.now(UTC))]
        proposal = ActionProposal(
            action_type="refund.request", arguments=self.arguments,
            idempotency_key="guard-" + uuid4().hex, approval_required=True, risk_level="high",
            rationale_evidence_ids=self.evidence_ids if self.evidence_ids is not None else ["ev-real"])
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id,
                          outcome="waiting", confidence=1, evidence=evidence,
                          next_action=NextAction.WAIT_FOR_APPROVAL, wait_reason="human_approval",
                          action_proposals=[proposal])


def _controller(team, *, broker=None):
    """★대조 선언을 **주입**한다.

    Controller 는 기본값으로 아무 어휘도 갖지 않는다 — basement 이기 때문이다.
    선언을 안 주면 대조를 건너뛴다. 그래서 여기서 도메인 선언을 붙인다.
    """
    from app.modules.customer_ops.verification_policy import CUSTOMER_OPS_POLICY, FACT_QUERIES
    return Controller(TeamRegistry([team]), policy_search=fake_policy,
                      context_broker=broker or FakeContextBroker(),
                      verification_policy=CUSTOMER_OPS_POLICY, fact_queries=FACT_QUERIES)


def _run(conn, tenant, team):
    case_id, _ = seed_case(conn, tenant)
    asyncio.run(_controller(team).run_case(tenant_id=tenant, case_id=case_id))
    return case_id


def _action_rows(conn, tenant, case_id) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM action_requests WHERE tenant_id=%s AND case_id=%s",
                    (tenant, case_id))
        return cur.fetchone()[0]


def _last_event(conn, tenant, case_id):
    with conn.cursor() as cur:
        cur.execute("SELECT event_type, payload_json FROM case_events "
                    "WHERE tenant_id=%s AND case_id=%s ORDER BY aggregate_version DESC LIMIT 1",
                    (tenant, case_id))
        return cur.fetchone()


def test_invented_payment_id_never_reaches_action_requests(db):  # noqa: F811
    """★지어낸 결제 식별자로는 action_requests 행이 생기지 않는다."""
    conn, tenant = db
    case_id = _run(conn, tenant, ProposingTeam(
        {"payment_id": str(uuid4()), "amount": 50_000}))

    assert _action_rows(conn, tenant, case_id) == 0, "검증 실패 제안이 저장됐다"
    status, _ = case_versions(conn, tenant, case_id)
    assert status == "escalated", f"escalated 여야 하는데 {status} 다"


def test_rejection_is_recorded_with_hashed_values_not_raw(db):  # noqa: F811
    """★조용히 무시하지 않는다. 그러나 원문 금액·식별자를 남기지도 않는다."""
    conn, tenant = db
    invented = str(uuid4())
    case_id = _run(conn, tenant, ProposingTeam({"payment_id": invented, "amount": 50_000}))

    event_type, payload = _last_event(conn, tenant, case_id)
    assert event_type == "guardrail_escalated"
    assert payload["guardrail"] == "action_proposal_verification_failed"
    audit = payload["state_patch"]["rejected_proposal_audit"]
    assert "payment_id" in audit["failed_fields"]
    # ★감사 로그에 결제 식별자 원문이 없어야 한다 (설계 원칙 §1)
    blob = str(payload)
    assert invented not in blob
    assert "50000" not in blob


def test_unverifiable_order_id_is_blocked(db):  # noqa: F811
    """이 MVP 에 orders 가 없다 — 확인 못 하면 실행하지 않는다."""
    conn, tenant = db
    case_id = _run(conn, tenant, ProposingTeam({"order_id": "ord-42"}))
    assert _action_rows(conn, tenant, case_id) == 0
    assert case_versions(conn, tenant, case_id)[0] == "escalated"


def test_evidence_outside_the_result_is_blocked(db):  # noqa: F811
    conn, tenant = db
    case_id = _run(conn, tenant, ProposingTeam({"template": "apology"},
                                               evidence_ids=["ev-real"]))
    # ev-real 은 결과 evidence 에 있으나 ContextPack evidence 에는 없다 → 거부
    assert _action_rows(conn, tenant, case_id) == 0
    assert case_versions(conn, tenant, case_id)[0] == "escalated"


class DegradedBroker:
    """★degraded 인 ContextPack 을 만드는 Broker.

    degraded 는 **Controller 쪽에서 생긴다** — RAG 가 죽었거나 예산에 걸려 잘렸을 때다.
    Team 이 스스로 만드는 값이 아니다. 그래서 여기서 재현한다.
    """

    def build(self, inputs):
        return ContextPack(pack_id=uuid4(), case_id=inputs.case_id, team_id=inputs.team_id,
                           tenant_id=inputs.tenant_id, knowledge_scope=inputs.knowledge_scope,
                           current_state=inputs.current_state, estimated_input_tokens=0,
                           degraded=True, omissions=["policy_rag:all"])


def test_core_blocks_proposals_when_context_is_degraded(db):  # noqa: F811
    """★Team 이 degraded 검사를 빼먹어도 Core 가 막는다 (DoD-25).

    기존 두 Team 은 스스로 `task.context.degraded` 를 본다. 그러나 그건 **Team 의 선의**다.
    새 Team 이 그 줄을 빠뜨려도 제안이 실행 경로에 들어가면 안 된다.
    여기 쓰는 ProposingTeam 은 degraded 를 **보지 않는다** — 그게 이 테스트의 요점이다.
    """
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    controller = _controller(ProposingTeam({"template": "apology"}, evidence_ids=[]),
                             broker=DegradedBroker())
    asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))

    assert _action_rows(conn, tenant, case_id) == 0
    event_type, payload = _last_event(conn, tenant, case_id)
    assert event_type == "guardrail_escalated"
    assert payload["guardrail"] == "degraded_context_blocks_action"
