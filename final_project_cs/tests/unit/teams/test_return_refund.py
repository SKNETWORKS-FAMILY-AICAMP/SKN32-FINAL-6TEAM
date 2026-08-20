from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.contracts import ContextPack, NextAction, TeamTask
from app.modules.customer_ops.return_refund import ReturnRefundTeam


class FakeTools:
    def __init__(self, values):
        self.values = values

    def call(self, name, context, arguments, allowed_tools, seen):
        return self.values.get(name)


def make_task(capability: str, *, ordered_at=None, returns=None, order=None, policy=None):
    case_id = uuid4()
    context = ContextPack(
        pack_id=uuid4(), case_id=case_id, team_id="return_refund", tenant_id="tenant",
        knowledge_scope=ReturnRefundTeam.manifest.knowledge_scope,
        current_state={"customer_id": str(uuid4()), "reason_code": "changed_mind", "return_quantity": 1},
        estimated_input_tokens=10,
    )
    task = TeamTask(
        task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id="return_refund",
        capability=capability, case_version=1, input_text="반품 요청", context=context,
        allowed_tools=ReturnRefundTeam.manifest.allowed_tools,
        deadline_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    order = order or {"order_id": "o1", "total_cents": 10000, "item_count": 2,
                      "ordered_at": ordered_at or datetime.now(UTC) - timedelta(days=2)}
    returns = returns if returns is not None else []
    policy = policy if policy is not None else [{"return_period_days": 7}]
    return task, FakeTools({"read.order": order, "read.return": returns, "read.policy": policy})


@pytest.mark.asyncio
async def test_normal_return_request_is_approval_proposal():
    task, tools = make_task("return.request")
    result = await ReturnRefundTeam(tools).execute(task)
    assert result.outcome == "waiting"
    assert result.next_action is NextAction.WAIT_FOR_APPROVAL
    assert result.action_proposals[0].action_type == "return.request"
    assert result.action_proposals[0].approval_required is True


@pytest.mark.asyncio
async def test_expired_return_is_rejected_without_proposal():
    task, tools = make_task("return.check_eligibility", ordered_at=datetime.now(UTC) - timedelta(days=8))
    result = await ReturnRefundTeam(tools).execute(task)
    assert result.outcome == "escalated"
    assert result.failure_code == "return_period_expired"
    assert result.action_proposals == []


@pytest.mark.asyncio
async def test_missing_evidence_escalates():
    task, tools = make_task("return.check_eligibility", order=None, policy=None)
    tools.values["read.order"] = None
    tools.values["read.policy"] = None
    result = await ReturnRefundTeam(tools).execute(task)
    assert result.outcome == "escalated"
    assert result.failure_code == "required_evidence_missing"


@pytest.mark.asyncio
async def test_refund_calculation_is_not_completed_side_effect():
    task, tools = make_task("refund.calculate")
    result = await ReturnRefundTeam(tools).execute(task)
    assert result.outcome != "completed"
    assert result.next_action is NextAction.WAIT_FOR_APPROVAL
    assert result.action_proposals[0].action_type == "refund.calculate"
    assert result.action_proposals[0].arguments["refund_amount_cents"] == 5000
