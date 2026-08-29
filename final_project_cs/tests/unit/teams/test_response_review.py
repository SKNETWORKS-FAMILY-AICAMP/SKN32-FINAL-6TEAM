from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.contracts import ContextPack, TeamTask
from app.modules.customer_ops.response_review import ResponseGenerationReviewTeam
from app.modules.customer_ops.response_review_policy import CUSTOMER_OPS_POLICY, decide_tone


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def complete(self, prompt_key, input_text, context):
        self.calls.append((prompt_key, context))
        if prompt_key == "response.review_tone":
            return {"tone_ok": True}
        return self.responses.pop(0)


def make_task(state=None):
    case_id = uuid4()
    context = ContextPack(
        pack_id=uuid4(), case_id=case_id, team_id="response_generation_review",
        tenant_id="tenant-1", knowledge_scope=["response_review"],
        current_state=state or {}, estimated_input_tokens=1,
    )
    return TeamTask(
        task_id=uuid4(), run_id=uuid4(), case_id=case_id,
        team_id="response_generation_review", capability="response.generate_review",
        case_version=1, input_text="주문 배송 문의입니다.", context=context,
        allowed_tools=["read.policy"], deadline_at=datetime.now(UTC) + timedelta(seconds=10),
    )


@pytest.mark.asyncio
async def test_normal_response_passes_once():
    llm = FakeLLM([{"final_response_text": "주문 상태를 확인해 안내드립니다.", "tone_ok": True}])
    result = await ResponseGenerationReviewTeam(llm).execute(make_task({"sentiment": "neutral"}))
    assert result.outcome == "completed"
    assert result.answer == "주문 상태를 확인해 안내드립니다."
    assert [call[0] for call in llm.calls] == ["response.generate"]


@pytest.mark.asyncio
async def test_forbidden_word_retries_then_passes():
    llm = FakeLLM([
        {"final_response_text": "항상 100% 보장됩니다."},
        {"final_response_text": "주문 상태를 확인해 안내드립니다.", "tone_ok": True},
    ])
    result = await ResponseGenerationReviewTeam(llm).execute(make_task())
    assert result.outcome == "completed"
    assert len(result.decisions) == 2
    assert any(item.startswith("forbidden_word:") for item in result.decisions[0]["review_history"])


@pytest.mark.asyncio
async def test_pii_escalates_without_retry():
    llm = FakeLLM([{"final_response_text": "연락처 010-1234-5678로 안내드립니다."}])
    result = await ResponseGenerationReviewTeam(llm).execute(make_task())
    assert result.outcome == "escalated"
    assert result.failure_code == "pii_detected"
    assert len(llm.calls) == 1
    assert len(result.decisions) == 1


@pytest.mark.asyncio
async def test_verified_name_with_honorific_escalates_without_retry():
    llm = FakeLLM([{"final_response_text": "김민수님께 안내드립니다."}])
    result = await ResponseGenerationReviewTeam(llm).execute(make_task())
    assert result.outcome == "escalated"
    assert result.failure_code == "pii_detected"
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_surname_without_name_context_does_not_escalate():
    llm = FakeLLM([{"final_response_text": "김치 배송 상태를 확인했습니다.", "tone_ok": True}])
    result = await ResponseGenerationReviewTeam(llm).execute(make_task())
    assert result.outcome == "completed"


@pytest.mark.asyncio
async def test_refund_amount_above_order_total_is_fact_mismatch():
    state = {"db_facts": {"orders": {"o-1": {"order_id": "o-1", "total_cents": 10000, "item_count": 2}}}}
    llm = FakeLLM([{"final_response_text": "환불을 처리합니다.", "claims": {"order_id": "o-1", "refund_amount": 101}}] * 4)
    result = await ResponseGenerationReviewTeam(llm).execute(make_task(state))
    assert result.outcome == "escalated"
    assert result.failure_code == "review_retries_exhausted"
    assert all("fact_mismatch:refund_amount" in item["review_history"] for item in result.decisions)


@pytest.mark.asyncio
async def test_four_failed_reviews_escalate_with_retry_code():
    llm = FakeLLM([{"final_response_text": "This is always processed."}] * 4)
    result = await ResponseGenerationReviewTeam(llm).execute(make_task())
    assert result.outcome == "escalated"
    assert result.failure_code == "review_retries_exhausted"
    assert len(result.decisions) == 4


def test_policy_and_tone_use_commerce_vocabulary():
    assert CUSTOMER_OPS_POLICY.references == {
        "order_id": "orders", "shipment_id": "shipments", "return_id": "returns",
    }
    assert decide_tone("negative") == "empathetic"
    assert decide_tone("positive") == "professional"
