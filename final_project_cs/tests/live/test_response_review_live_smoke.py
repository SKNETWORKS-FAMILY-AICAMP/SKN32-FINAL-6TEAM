"""One real-LLM smoke test for the Response Generation & Review Team."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.contracts import ContextPack, TeamTask
from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection
from app.infrastructure.llm.openai import OpenAITeamLLM
from app.modules.customer_ops.response_review import ResponseGenerationReviewTeam


@pytest.mark.live
@pytest.mark.asyncio
async def test_response_generation_review_team_with_real_llm():
    if not get_settings().openai_api_key.strip():
        pytest.skip("OPENAI_API_KEY is not configured")

    case_id = uuid4()
    task = TeamTask(
        task_id=uuid4(),
        run_id=uuid4(),
        case_id=case_id,
        team_id="response_generation_review",
        capability="response.generate_review",
        case_version=1,
        input_text="주문하신 상품은 내일 도착 예정입니다.",
        context=ContextPack(
            pack_id=uuid4(),
            case_id=case_id,
            team_id="response_generation_review",
            tenant_id="live-response-review-smoke",
            knowledge_scope=["response_review"],
            current_state={"sentiment": "neutral"},
            evidence=[],
            estimated_input_tokens=1,
        ),
        allowed_tools=["read.policy"],
        deadline_at=datetime.now(UTC) + timedelta(seconds=60),
    )

    result = await ResponseGenerationReviewTeam(OpenAITeamLLM()).execute(task)

    assert result.outcome in {"completed", "escalated"}
    assert result.decisions


@pytest.mark.live
@pytest.mark.asyncio
async def test_response_generation_review_team_with_db_audited_llm():
    """Same as above, but through the exact wiring app/composition.py uses in
    production (connection_factory=get_connection) -- this is the path the
    2026-08-30 empty-ALLOWED_PROMPT_KEYS regression broke and the smoke test
    above never exercised."""
    if not get_settings().openai_api_key.strip():
        pytest.skip("OPENAI_API_KEY is not configured")

    case_id = uuid4()
    task = TeamTask(
        task_id=uuid4(),
        run_id=uuid4(),
        case_id=case_id,
        team_id="response_generation_review",
        capability="response.generate_review",
        case_version=1,
        input_text="주문하신 상품은 내일 도착 예정입니다.",
        context=ContextPack(
            pack_id=uuid4(),
            case_id=case_id,
            team_id="response_generation_review",
            tenant_id="live-response-review-db-audited",
            knowledge_scope=["response_review"],
            current_state={"sentiment": "neutral"},
            evidence=[],
            estimated_input_tokens=1,
        ),
        allowed_tools=["read.policy"],
        deadline_at=datetime.now(UTC) + timedelta(seconds=60),
    )

    llm = OpenAITeamLLM(connection_factory=get_connection)
    result = await ResponseGenerationReviewTeam(llm).execute(task)

    assert result.outcome in {"completed", "escalated"}
    assert result.decisions
