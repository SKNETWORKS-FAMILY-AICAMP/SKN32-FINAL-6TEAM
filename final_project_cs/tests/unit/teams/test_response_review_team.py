from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.contracts import ContextPack, Evidence, TeamModule, TeamTask
from app.modules.customer_ops.response_review import ResponseGenerationReviewTeam


class FakeLLM:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.contexts = []

    async def complete(self, prompt_key, input_text, context):
        self.calls.append(prompt_key)
        self.contexts.append(context)
        return next(self.responses)


def make_task(**state) -> TeamTask:
    case_id = uuid4()
    evidence = Evidence(
        evidence_id="ev-policy", source_type="policy", source_id="policy-1",
        claim="return and refund policy", value={"policy_ref": "policy-1"}, confidence=1.0,
        observed_at=datetime.now(UTC),
    )
    pack = ContextPack(
        pack_id=uuid4(), case_id=case_id, team_id="response_generation_review",
        tenant_id="test", knowledge_scope=["response_review"], current_state=state,
        evidence=[evidence], estimated_input_tokens=100,
    )
    return TeamTask(
        task_id=uuid4(), run_id=uuid4(), case_id=case_id,
        team_id="response_generation_review", capability="response.generate_review",
        case_version=1, input_text="주문 상태를 확인해 주세요.", context=pack,
        allowed_tools=["read.policy"], deadline_at=datetime.now(UTC) + timedelta(seconds=30),
    )


def test_manifest_and_protocol() -> None:
    team = ResponseGenerationReviewTeam()
    assert isinstance(team, TeamModule)
    assert team.manifest.team_id == "response_generation_review"
    assert team.manifest.accepted_case_types == []
    assert team.manifest.capabilities == ["response.generate_review"]


@pytest.mark.asyncio
async def test_normal_generation_review_returns_contract_result() -> None:
    llm = FakeLLM([{"final_response_text": "주문을 확인했습니다.", "status": "completed", "tone_ok": True}])
    result = await ResponseGenerationReviewTeam(llm).execute(make_task())
    assert result.outcome == "completed"
    assert result.answer == "주문을 확인했습니다."
    assert result.evidence and result.decisions[0]["retry_count"] == 0


@pytest.mark.asyncio
async def test_negative_sentiment_decides_empathetic_tone_before_generation() -> None:
    llm = FakeLLM([{"final_response_text": "불편을 드려 죄송합니다.", "tone_ok": True}])
    result = await ResponseGenerationReviewTeam(llm).execute(make_task(sentiment="negative"))
    assert result.outcome == "completed"
    assert result.decisions[0]["tone_profile"] == "empathetic"
    assert llm.contexts[0]["tone_profile"] == "empathetic"


@pytest.mark.asyncio
async def test_missing_sentiment_defaults_to_professional_tone() -> None:
    result = await ResponseGenerationReviewTeam(FakeLLM([{"final_response_text": "확인했습니다.", "tone_ok": True}])).execute(make_task())
    assert result.decisions[0]["tone_profile"] == "professional"


@pytest.mark.asyncio
async def test_forbidden_word_retries_then_escalates() -> None:
    llm = FakeLLM([{"final_response_text": "This is guaranteed."}] * 4)
    result = await ResponseGenerationReviewTeam(llm).execute(make_task())
    assert result.outcome == "escalated"
    assert llm.calls.count("response.generate") == 4
    assert [d["retry_count"] for d in result.decisions] == [0, 1, 2, 3]


@pytest.mark.asyncio
async def test_fact_mismatch_retries_and_later_pass_is_recorded() -> None:
    llm = FakeLLM([
        {"final_response_text": "환불을 처리합니다.", "claims": {"order_id": "o1", "refund_amount": 99}},
        {"final_response_text": "환불을 처리합니다.", "claims": {"order_id": "o1", "refund_amount": 10}, "tone_ok": True},
    ])
    result = await ResponseGenerationReviewTeam(llm).execute(make_task(db_facts={"orders": {"o1": {"total_cents": 1000}}}))
    assert result.outcome == "completed"
    assert result.decisions[0]["review_history"]
    assert result.decisions[-1]["retry_count"] == 1


@pytest.mark.asyncio
async def test_return_quantity_over_item_count_is_fact_mismatch() -> None:
    llm = FakeLLM([{"final_response_text": "반품을 접수합니다.", "claims": {"order_id": "o1", "return_quantity": 3}}] * 4)
    result = await ResponseGenerationReviewTeam(llm).execute(make_task(db_facts={"orders": {"o1": {"item_count": 2}}}))
    assert result.outcome == "escalated"
    assert "fact_mismatch:return_quantity" in result.decisions[0]["review_history"]


@pytest.mark.asyncio
async def test_pii_escalates_without_retry() -> None:
    llm = FakeLLM([{"final_response_text": "문의: test@example.com"}])
    result = await ResponseGenerationReviewTeam(llm).execute(make_task())
    assert result.outcome == "escalated"
    assert result.failure_code == "pii_detected"
    assert result.decisions[0]["retry_count"] == 0
    assert llm.calls == ["response.generate"]


@pytest.mark.asyncio
async def test_deterministic_review_runs_before_tone_llm() -> None:
    llm = FakeLLM([
        {"final_response_text": "This is guaranteed."},
        {"final_response_text": "확인했습니다.", "tone_ok": True},
    ])
    result = await ResponseGenerationReviewTeam(llm).execute(make_task())
    assert result.outcome == "completed"
    assert llm.calls == ["response.generate", "response.generate"]
    assert "response.review_tone" not in llm.calls


@pytest.mark.asyncio
async def test_tone_only_failure_is_warning_without_retry() -> None:
    llm = FakeLLM([{"final_response_text": "확인했습니다.", "tone_ok": False}])
    result = await ResponseGenerationReviewTeam(llm).execute(make_task())
    assert result.outcome == "completed"
    assert result.warnings == ["tone_review_failed"]
    assert llm.calls == ["response.generate"]


@pytest.mark.asyncio
async def test_status_escalated_is_mapped_to_escalation_contract() -> None:
    llm = FakeLLM([{"final_response_text": "상담원이 확인하겠습니다.", "status": "escalated"}])
    result = await ResponseGenerationReviewTeam(llm).execute(make_task())
    assert result.outcome == "escalated"
    assert result.next_action.value == "escalate"
