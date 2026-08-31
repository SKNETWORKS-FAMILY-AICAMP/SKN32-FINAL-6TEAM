"""계약 모델 검증 — `docs/handoff/01_계약_Pydantic.md` 와의 대조.

★"근거 없이 확정하지 않는다"와 "승인 없이 실행하지 않는다"(CLAUDE.md §0)가
  문서상의 다짐이 아니라 **계약이 거부하는 것**임을 여기서 증명한다.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.contracts import (
    ActionProposal,
    ContextPack,
    Evidence,
    NextAction,
    TeamResult,
    TeamTask,
)

NOW = datetime.now(UTC)


def make_evidence(evidence_id: str = "ev_1") -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_type="policy",
        source_id="doc_04#c12",
        claim="해지 후 청구는 14일 이내 환불 요청 가능",
        value={"days": 14},
        confidence=0.9,
        observed_at=NOW,
    )


def make_pack(case_id=None, team_id="order_shipping", **overrides) -> ContextPack:
    payload = {
        "pack_id": uuid4(),
        "case_id": case_id or uuid4(),
        "team_id": team_id,
        "tenant_id": "demo",
        "knowledge_scope": ["order"],
        "current_state": {"status": "running"},
        "estimated_input_tokens": 5000,
    }
    payload.update(overrides)
    return ContextPack(**payload)


def make_result(**overrides) -> TeamResult:
    payload = {
        "task_id": uuid4(),
        "run_id": uuid4(),
        "team_id": "order_shipping",
        "outcome": "completed",
        "confidence": 0.8,
        "next_action": NextAction.RESPOND,
        "answer": "환불이 가능합니다.",
        "evidence": [make_evidence()],
    }
    payload.update(overrides)
    return TeamResult(**payload)


# ── extra='forbid' — 조용한 필드 유입 차단 ─────────────────────────────


@pytest.mark.parametrize("model_factory", [make_evidence, make_pack, make_result])
def test_models_forbid_extra_fields(model_factory) -> None:
    base = model_factory().model_dump()
    base["sneaky_field"] = "x"
    with pytest.raises(ValidationError):
        type(model_factory())(**base)


# ── ContextPack: 토큰 예산과 degraded 신호 ────────────────────────────


def test_context_pack_rejects_over_budget() -> None:
    """★예산을 넘긴 팩은 만들어질 수 없다. 절삭이 선행해야 한다(v5 §9-1)."""
    with pytest.raises(ValidationError):
        make_pack(estimated_input_tokens=12001)


def test_context_pack_accepts_exact_budget() -> None:
    assert make_pack(estimated_input_tokens=12000).estimated_input_tokens == 12000


def test_degraded_without_omissions_is_rejected() -> None:
    """★신호 없는 축소는 폴백이다(RULE.md §3.2)."""
    with pytest.raises(ValidationError):
        make_pack(degraded=True)


def test_degraded_with_omissions_is_accepted() -> None:
    pack = make_pack(degraded=True, omissions=["policy_rag"])
    assert pack.degraded and pack.omissions == ["policy_rag"]


def test_token_budget_is_literal_12000() -> None:
    """다른 값으로 바꿔치기할 수 없다."""
    with pytest.raises(ValidationError):
        make_pack(token_budget=9500)


# ── TeamResult: 근거 없는 답변 금지 (CLAUDE.md §0.1) ───────────────────


def test_answer_without_evidence_is_rejected() -> None:
    with pytest.raises(ValidationError, match="evidence"):
        make_result(evidence=[])


# ── TeamResult: next_action 일관성 (계약 문서 §6) ──────────────────────


def test_respond_requires_answer() -> None:
    with pytest.raises(ValidationError):
        make_result(next_action=NextAction.RESPOND, answer=None)


def test_wait_for_input_requires_schema_and_reason() -> None:
    with pytest.raises(ValidationError):
        make_result(
            next_action=NextAction.WAIT_FOR_INPUT,
            outcome="waiting",
            answer=None,
            evidence=[],
            wait_reason="customer_input",
            required_input_schema=None,
        )


def test_handoff_requires_capability() -> None:
    with pytest.raises(ValidationError):
        make_result(
            next_action=NextAction.HANDOFF, outcome="handoff", answer=None, evidence=[]
        )


def test_escalate_requires_failure_code_or_warnings() -> None:
    with pytest.raises(ValidationError):
        make_result(
            next_action=NextAction.ESCALATE, outcome="escalated", answer=None, evidence=[]
        )


# ── ★승인 없이 실행하지 않는다 (CLAUDE.md §0.2) ────────────────────────


def _refund_proposal(approval_required: bool = True) -> ActionProposal:
    return ActionProposal(
        action_type="refund.request",
        arguments={"amount": 19900},
        idempotency_key="a" * 32,
        approval_required=approval_required,
        risk_level="high",
        rationale_evidence_ids=["ev_1"],
    )


def test_approval_required_proposal_forces_wait_for_approval() -> None:
    """승인이 필요한 제안을 내면서 곧장 respond 하면 계약이 거부한다."""
    with pytest.raises(ValidationError, match="wait_for_approval"):
        make_result(action_proposals=[_refund_proposal(True)])


def test_approval_required_proposal_with_wait_is_accepted() -> None:
    result = make_result(
        outcome="waiting",
        next_action=NextAction.WAIT_FOR_APPROVAL,
        wait_reason="human_approval",
        answer=None,
        evidence=[make_evidence()],
        action_proposals=[_refund_proposal(True)],
    )
    assert result.next_action is NextAction.WAIT_FOR_APPROVAL


def test_wait_for_approval_needs_at_least_one_proposal() -> None:
    with pytest.raises(ValidationError):
        make_result(
            outcome="waiting",
            next_action=NextAction.WAIT_FOR_APPROVAL,
            wait_reason="human_approval",
            answer=None,
            evidence=[],
            action_proposals=[],
        )


def test_proposal_cannot_cite_unknown_evidence() -> None:
    """제안의 근거가 결과에 없는 evidence 를 가리키면 추적이 끊긴다."""
    proposal = ActionProposal(
        action_type="refund.request",
        arguments={},
        idempotency_key="b" * 32,
        approval_required=False,
        risk_level="low",
        rationale_evidence_ids=["ev_없음"],
    )
    with pytest.raises(ValidationError, match="evidence"):
        make_result(action_proposals=[proposal])


# ── TeamTask: resume / context 정합 ───────────────────────────────────


def _task(**overrides) -> TeamTask:
    case_id = overrides.pop("case_id", uuid4())
    payload = {
        "task_id": uuid4(),
        "run_id": uuid4(),
        "case_id": case_id,
        "team_id": "order_shipping",
        "capability": "billing.investigate",
        "case_version": 3,
        "input_text": "해지했는데 결제가 됐어요",
        "context": make_pack(case_id=case_id),
        "allowed_tools": ["read.payment_history"],
        "deadline_at": NOW + timedelta(seconds=90),
    }
    payload.update(overrides)
    return TeamTask(**payload)


def test_resume_true_requires_resume_node() -> None:
    with pytest.raises(ValidationError):
        _task(resume=True)


def test_resume_node_without_resume_flag_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _task(resume=False, resume_node="validate_input")


def test_context_pack_case_id_must_match_task() -> None:
    """다른 Case 의 근거로 답하는 것을 막는다."""
    with pytest.raises(ValidationError, match="case_id"):
        _task(context=make_pack(case_id=uuid4()))


def test_task_input_text_cannot_be_empty() -> None:
    with pytest.raises(ValidationError):
        _task(input_text="")


# ── 2026-08-31: 빈 값과 None 을 구분하지 않아 생긴 사각지대 ────────────
#
# 위 세 테스트는 값을 **None 으로** 넣어 거부되는 것만 확인했다. 그래서
# `not x` 를 `x is None` 으로 바꾸는 변경을 전체 424개가 잡지 못했다.
# 빈 문자열은 None 이 아니다 — 빈 답변, 넘길 곳 없는 인계가 통과한다.


def test_respond_rejects_empty_answer() -> None:
    """빈 문자열도 답변이 아니다. 고객에게 아무것도 가지 않는다."""
    with pytest.raises(ValidationError):
        make_result(next_action=NextAction.RESPOND, answer="")


def test_handoff_rejects_empty_capability() -> None:
    """빈 capability 로는 Registry 가 담당 Team 을 찾지 못한다."""
    with pytest.raises(ValidationError):
        make_result(
            next_action=NextAction.HANDOFF, outcome="handoff", answer=None, evidence=[],
            handoff_capability="",
        )


def test_wait_for_input_rejects_other_wait_reason() -> None:
    """대기 사유는 재개 경로를 고르는 값이다. 아무 문자열이나 통과하면 안 된다."""
    with pytest.raises(ValidationError):
        make_result(
            next_action=NextAction.WAIT_FOR_INPUT, outcome="waiting", answer=None,
            evidence=[], wait_reason="human_approval",
            required_input_schema={"type": "object"},
        )
