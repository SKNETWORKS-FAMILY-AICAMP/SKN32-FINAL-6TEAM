from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from acop_basement.core.contracts import ContextPack, Evidence, TeamTask
from acop_basement.core.contracts import TeamModule
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
        claim="refund policy", value={"policy_ref": "policy-1"}, confidence=1.0,
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
        case_version=1, input_text="고객 요청을 확인했습니다.", context=pack,
        allowed_tools=["read.policy"], deadline_at=datetime.now(UTC) + timedelta(seconds=30),
    )


def test_manifest_and_protocol() -> None:
    team = ResponseGenerationReviewTeam()
    assert isinstance(team, TeamModule)
    assert team.manifest.accepted_case_types == []
    assert team.manifest.capabilities == ["response.generate_review"]


@pytest.mark.asyncio
async def test_normal_generation_review_returns_contract_result() -> None:
    llm = FakeLLM([{"final_response_text": "확인 후 안내드리겠습니다.", "status": "completed", "tone_ok": True}])
    result = await ResponseGenerationReviewTeam(llm).execute(make_task())
    assert result.outcome == "completed"
    assert result.answer == "확인 후 안내드리겠습니다."
    assert result.evidence
    assert result.decisions[0]["retry_count"] == 0


@pytest.mark.asyncio
async def test_negative_sentiment_decides_empathetic_tone_before_generation() -> None:
    """★v8 §8-B 내부 흐름의 1단계(톤 결정, 규칙) — LLM 이 아니라
    `case["sentiment"]`(`controller.py`가 채우는 `current_state["sentiment"]`)
    으로 결정하고, GEN·톤 REV 양쪽 호출에 같은 값이 전달되는지 본다."""
    llm = FakeLLM([{"final_response_text": "확인 후 안내드리겠습니다.", "tone_ok": True}])
    result = await ResponseGenerationReviewTeam(llm).execute(make_task(sentiment="negative"))
    assert result.outcome == "completed"
    assert result.decisions[0]["tone_profile"] == "empathetic"
    assert llm.contexts[0]["tone_profile"] == "empathetic"


@pytest.mark.asyncio
async def test_missing_sentiment_defaults_to_professional_tone() -> None:
    llm = FakeLLM([{"final_response_text": "확인 후 안내드리겠습니다.", "tone_ok": True}])
    result = await ResponseGenerationReviewTeam(llm).execute(make_task())
    assert result.decisions[0]["tone_profile"] == "professional"


@pytest.mark.asyncio
async def test_forbidden_word_retries_then_escalates() -> None:
    llm = FakeLLM([{"final_response_text": "무조건 환불됩니다."}] * 4)
    result = await ResponseGenerationReviewTeam(llm).execute(make_task())
    assert result.outcome == "escalated"
    assert len([call for call in llm.calls if call == "response.generate"]) == 4
    assert [d["retry_count"] for d in result.decisions] == [0, 1, 2, 3]


@pytest.mark.asyncio
async def test_fact_mismatch_retries_and_later_pass_is_recorded() -> None:
    llm = FakeLLM([
        {"final_response_text": "환불을 처리합니다.", "claims": {"payment_id": "p1", "refund_amount": 99}},
        {"final_response_text": "환불을 처리합니다.", "claims": {"payment_id": "p1", "refund_amount": 10}, "tone_ok": True},
    ])
    result = await ResponseGenerationReviewTeam(llm).execute(make_task(db_facts={"payments": {"p1": {"amount_cents": 1000}}}))
    assert result.outcome == "completed"
    assert result.decisions[0]["review_history"]
    assert result.decisions[-1]["retry_count"] == 1


@pytest.mark.asyncio
async def test_pii_escalates_without_retry() -> None:
    llm = FakeLLM([{"final_response_text": "연락처 test@example.com"}])
    result = await ResponseGenerationReviewTeam(llm).execute(make_task())
    assert result.outcome == "escalated"
    assert result.failure_code == "pii_detected"
    assert result.decisions[0]["retry_count"] == 0
    assert llm.calls == ["response.generate"]


@pytest.mark.asyncio
async def test_deterministic_review_runs_before_tone_llm() -> None:
    """결정론 REV(생성된 초안의 금칙어)가 실패하면 톤 리뷰 LLM 은 호출되지 않는다.

    ★`task.input_text` 는 고객의 원문 메시지다(`case["subject"]`, controller.py:87) —
      고객 메시지 자체를 REV 규칙으로 스캔하면(구 preflight) 고객이 자기 연락처를
      적었다는 이유만으로 초안 생성도 없이 escalate 됐다. REV 는 생성된 응답만
      검사한다(docs/handoff/04 §3 "흐름": GEN 초안 → 결정론 REV → LLM 톤 REV).
    """
    llm = FakeLLM([
        {"final_response_text": "무조건 환불됩니다."},
        {"final_response_text": "확인 후 안내드리겠습니다.", "tone_ok": True},
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
    assert [call for call in llm.calls if call == "response.generate"] == ["response.generate"]


@pytest.mark.asyncio
async def test_status_escalated_is_mapped_to_escalation_contract() -> None:
    llm = FakeLLM([{"final_response_text": "검토가 필요합니다.", "status": "escalated"}])
    result = await ResponseGenerationReviewTeam(llm).execute(make_task())
    assert result.outcome == "escalated"
    assert result.next_action.value == "escalate"
