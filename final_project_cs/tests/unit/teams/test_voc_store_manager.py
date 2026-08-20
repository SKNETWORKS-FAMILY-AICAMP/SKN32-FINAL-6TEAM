from __future__ import annotations

import pytest

from app.core.contracts import NextAction
from app.modules.customer_ops.voc_store_manager import VocStoreManagerTeam
from legacy.final_project_cs.team_modules_v1.tests.test_team_scenarios import FakeTools, pack, policy, task


def voc_task(*, similar_cases: int = 0, degraded: bool = False):
    context = pack("voc_store_manager", degraded=degraded)
    context.similar_cases = [{"case_id": str(index)} for index in range(similar_cases)]
    return context, task(
        "voc_store_manager", "voc.aggregate", context, VocStoreManagerTeam.manifest.allowed_tools,
    )


@pytest.mark.asyncio
async def test_repeated_complaint_proposes_voc_escalation():
    context, request = voc_task(similar_cases=2)
    result = await VocStoreManagerTeam(FakeTools({"read.policy": policy()})).execute(request)

    assert result.outcome == "waiting"
    assert result.next_action is NextAction.WAIT_FOR_APPROVAL
    assert result.action_proposals[0].action_type == "voc.escalate"
    assert result.action_proposals[0].arguments == {}
    assert result.decisions == [{"classification": "repeated_complaint_escalation", "similar_case_count": 2}]


@pytest.mark.asyncio
@pytest.mark.parametrize("similar_cases", [0, 1])
async def test_non_repeated_feedback_is_completed(similar_cases: int):
    context, request = voc_task(similar_cases=similar_cases)
    result = await VocStoreManagerTeam(FakeTools({"read.policy": policy()})).execute(request)

    assert result.outcome == "completed"
    assert result.next_action is NextAction.RESPOND
    assert result.answer == "피드백을 확인했습니다. 접수된 의견은 운영 개선에 반영됩니다."


@pytest.mark.asyncio
async def test_degraded_context_escalates_without_policy_lookup():
    _, request = voc_task(degraded=True)
    tools = FakeTools({})
    result = await VocStoreManagerTeam(tools).execute(request)

    assert result.outcome == "escalated"
    assert result.failure_code == "degraded_context"


@pytest.mark.asyncio
async def test_missing_policy_escalates():
    _, request = voc_task()
    result = await VocStoreManagerTeam(FakeTools({"read.policy": []})).execute(request)

    assert result.outcome == "escalated"
    assert result.failure_code == "policy_not_found"
