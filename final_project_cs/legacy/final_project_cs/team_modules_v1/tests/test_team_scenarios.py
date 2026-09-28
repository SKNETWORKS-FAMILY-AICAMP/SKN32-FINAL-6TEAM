from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

__test__ = False  # Legacy fixtures remain importable; the isolated suite is not active.

from app.core.contracts import ContextPack, Evidence, NextAction, TeamTask, ToolNotAllowed
from app.tools.read_tools import ReadToolbox, ToolLoopExceeded


NOW = datetime.now(UTC)


def pack(team_id: str, degraded: bool = False) -> ContextPack:
    return ContextPack(pack_id=uuid4(), case_id=uuid4(), team_id=team_id, tenant_id="test-team-tenant", knowledge_scope=["order", "shipping"], current_state={"customer_id": str(uuid4()), "status": "running"}, estimated_input_tokens=10, degraded=degraded, omissions=["fixture"] if degraded else [])


def task(team_id: str, capability: str, context: ContextPack, allowed: list[str]) -> TeamTask:
    return TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=context.case_id, team_id=team_id, capability=capability, case_version=1, input_text="고객 요청", context=context, allowed_tools=allowed, deadline_at=NOW + timedelta(seconds=90))


class FakeTools:
    def __init__(self, values): self.values = values
    def call(self, name, context, arguments, allowed_tools, seen):
        if name not in allowed_tools: raise ToolNotAllowed(name)
        return self.values[name]


def policy():
    return [Evidence(evidence_id="policy:refund#c1", source_type="policy", source_id="refund#c1", claim="policy", value={}, confidence=1, observed_at=NOW)]


@pytest.mark.asyncio
async def test_delivered_shipment_waits_for_refund_approval():
    """★시나리오1 — 배송완료 표시가 있으면 조사를 열고 환불을 제안(승인 대기)한다."""
    context = pack("order_shipping")
    tools = FakeTools({"read.order": {"order_id": "o1", "order_no": "ORD-1", "total_cents": 50000, "item_count": 2, "status": "delivered"},
                       "read.shipment": [{"shipment_id": "s1", "order_id": "o1", "status": "delivered"}],
                       "read.policy": policy()})
    result = await OrderShippingTeam(tools).execute(task("order_shipping", "order.investigate", context, OrderShippingTeam.manifest.allowed_tools))
    assert result.outcome == "waiting" and result.next_action is NextAction.WAIT_FOR_APPROVAL
    assert result.action_proposals[0].action_type == "refund.request"
    assert result.action_proposals[0].arguments["order_id"] == "o1"
    assert result.action_proposals[0].rationale_evidence_ids


@pytest.mark.asyncio
async def test_return_request_proposes_action_without_mutation():
    """★시나리오2 — 반품 요청이 있으면 제안까지만 만든다. 수량 상한 판단은 team 몫이 아니다."""
    context = pack("return_exchange")
    tools = FakeTools({"read.order": {"order_id": "o1", "order_no": "ORD-1", "total_cents": 50000, "item_count": 3, "status": "delivered"},
                       "read.return": [{"return_id": "r1", "order_id": "o1", "reason_code": "defective", "quantity": 5, "status": "requested"}],
                       "read.policy": policy()})
    result = await ReturnExchangeTeam(tools).execute(task("return_exchange", "return.diagnose", context, ReturnExchangeTeam.manifest.allowed_tools))
    assert result.outcome == "waiting" and result.next_action is NextAction.WAIT_FOR_APPROVAL
    assert result.action_proposals[0].action_type == "return.accept"
    assert result.action_proposals[0].arguments == {"order_id": "o1", "return_quantity": 5}
    # ★team 은 수량 초과를 관측만 한다 — 차단은 Controller 몫이다(DoD-24·25)
    assert result.decisions[-1]["classification"] == "return_quantity_exceeds_order"


@pytest.mark.asyncio
async def test_order_cancel_before_shipment_waits_for_approval():
    context = pack("order_shipping")
    context.current_state["issue_code"] = "order_change_or_cancel"
    tools = FakeTools({"read.order": {"order_id": "o1", "status": "paid"},
                       "read.shipment": [], "read.policy": policy()})
    result = await OrderShippingTeam(tools).execute(
        task("order_shipping", "order.investigate", context, OrderShippingTeam.manifest.allowed_tools))
    assert result.action_proposals[0].action_type == "order.cancel"
    assert result.next_action is NextAction.WAIT_FOR_APPROVAL


@pytest.mark.asyncio
async def test_order_cancel_after_delivery_does_not_propose_cancel():
    context = pack("order_shipping")
    context.current_state["issue_code"] = "order_change_or_cancel"
    tools = FakeTools({"read.order": {"order_id": "o1", "status": "delivered"},
                       "read.shipment": [], "read.policy": policy()})
    result = await OrderShippingTeam(tools).execute(
        task("order_shipping", "order.investigate", context, OrderShippingTeam.manifest.allowed_tools))
    assert result.action_proposals == []
    assert result.outcome == "completed"


@pytest.mark.asyncio
async def test_exchange_request_requires_stock_verification_approval():
    context = pack("return_exchange")
    tools = FakeTools({"read.order": {"order_id": "o1", "item_count": 3, "status": "delivered"},
                       "read.return": [{"return_id": "r1", "order_id": "o1", "reason_code": "size_mismatch",
                                         "quantity": 1, "status": "requested"}],
                       "read.policy": policy()})
    result = await ReturnExchangeTeam(tools).execute(
        task("return_exchange", "return.diagnose", context, ReturnExchangeTeam.manifest.allowed_tools))
    assert result.action_proposals[0].action_type == "exchange.request"
    assert result.action_proposals[0].risk_level == "high"
    assert any(e.source_id == "doc_15#재고 확인의 선행" for e in result.evidence)


@pytest.mark.asyncio
async def test_defective_return_still_accepts_return():
    context = pack("return_exchange")
    tools = FakeTools({"read.order": {"order_id": "o1", "item_count": 3, "status": "delivered"},
                       "read.return": [{"return_id": "r1", "order_id": "o1", "reason_code": "defective",
                                         "quantity": 1, "status": "requested"}],
                       "read.policy": policy()})
    result = await ReturnExchangeTeam(tools).execute(
        task("return_exchange", "return.diagnose", context, ReturnExchangeTeam.manifest.allowed_tools))
    assert result.action_proposals[0].action_type == "return.accept"


@pytest.mark.asyncio
async def test_simple_return_expired_after_seven_days_escalates():
    context = pack("return_exchange")
    tools = FakeTools({"read.order": {"order_id": "o1", "item_count": 1,
                                      "ordered_at": datetime.now(UTC) - timedelta(days=8)},
                       "read.return": [{"return_id": "r1", "reason_code": "changed_mind",
                                         "quantity": 1, "status": "requested"}],
                       "read.policy": policy()})
    result = await ReturnExchangeTeam(tools).execute(
        task("return_exchange", "return.diagnose", context, ReturnExchangeTeam.manifest.allowed_tools))
    assert result.outcome == "escalated"
    assert result.failure_code == "return_period_expired"
    assert result.action_proposals == []


@pytest.mark.asyncio
async def test_simple_return_within_period_still_accepts_return():
    context = pack("return_exchange")
    tools = FakeTools({"read.order": {"order_id": "o1", "item_count": 1,
                                      "ordered_at": datetime.now(UTC) - timedelta(days=5)},
                       "read.return": [{"return_id": "r1", "reason_code": "changed_mind",
                                         "quantity": 1, "status": "requested"}],
                       "read.policy": policy()})
    result = await ReturnExchangeTeam(tools).execute(
        task("return_exchange", "return.diagnose", context, ReturnExchangeTeam.manifest.allowed_tools))
    assert result.action_proposals[0].action_type == "return.accept"


@pytest.mark.asyncio
async def test_defective_return_expired_after_ninety_days_escalates():
    context = pack("return_exchange")
    tools = FakeTools({"read.order": {"order_id": "o1", "item_count": 1,
                                      "ordered_at": datetime.now(UTC) - timedelta(days=100)},
                       "read.return": [{"return_id": "r1", "reason_code": "defective",
                                         "quantity": 1, "status": "requested"}],
                       "read.policy": policy()})
    result = await ReturnExchangeTeam(tools).execute(
        task("return_exchange", "return.diagnose", context, ReturnExchangeTeam.manifest.allowed_tools))
    assert result.outcome == "escalated"
    assert result.failure_code == "return_period_expired"


@pytest.mark.asyncio
async def test_defective_return_within_period_still_accepts_return():
    context = pack("return_exchange")
    tools = FakeTools({"read.order": {"order_id": "o1", "item_count": 1,
                                      "ordered_at": datetime.now(UTC) - timedelta(days=60)},
                       "read.return": [{"return_id": "r1", "reason_code": "defective",
                                         "quantity": 1, "status": "requested"}],
                       "read.policy": policy()})
    result = await ReturnExchangeTeam(tools).execute(
        task("return_exchange", "return.diagnose", context, ReturnExchangeTeam.manifest.allowed_tools))
    assert result.action_proposals[0].action_type == "return.accept"


@pytest.mark.asyncio
async def test_shipping_delay_proposes_compensation_review_without_amount():
    context = pack("order_shipping")
    tools = FakeTools({"read.order": {"order_id": "o1", "status": "shipped"},
                       "read.shipment": [{"shipment_id": "s1", "status": "in_transit",
                                           "shipped_at": datetime.now(UTC) - timedelta(days=8)}],
                       "read.policy": policy()})
    result = await OrderShippingTeam(tools).execute(
        task("order_shipping", "order.investigate", context, OrderShippingTeam.manifest.allowed_tools))
    proposal = result.action_proposals[0]
    assert proposal.action_type == "shipping.delay_compensation_propose"
    assert "amount" not in proposal.arguments
    assert "compensation" not in proposal.arguments


@pytest.mark.asyncio
async def test_shipping_delay_under_five_business_days_does_not_propose():
    context = pack("order_shipping")
    tools = FakeTools({"read.order": {"order_id": "o1", "status": "shipped"},
                       "read.shipment": [{"shipment_id": "s1", "status": "in_transit",
                                           "shipped_at": datetime.now(UTC) - timedelta(days=2)}],
                       "read.policy": policy()})
    result = await OrderShippingTeam(tools).execute(
        task("order_shipping", "order.investigate", context, OrderShippingTeam.manifest.allowed_tools))
    assert result.action_proposals == []


@pytest.mark.asyncio
async def test_return_without_order_date_keeps_existing_logic():
    context = pack("return_exchange")
    tools = FakeTools({"read.order": {"order_id": "o1", "item_count": 1},
                       "read.return": [{"return_id": "r1", "reason_code": "changed_mind",
                                         "quantity": 1, "status": "requested"}],
                       "read.policy": policy()})
    result = await ReturnExchangeTeam(tools).execute(
        task("return_exchange", "return.diagnose", context, ReturnExchangeTeam.manifest.allowed_tools))
    assert result.action_proposals[0].action_type == "return.accept"


@pytest.mark.asyncio
async def test_delivered_shipment_keeps_refund_flow_before_delay_review():
    context = pack("order_shipping")
    tools = FakeTools({"read.order": {"order_id": "o1", "status": "delivered"},
                       "read.shipment": [{"shipment_id": "s1", "status": "delivered",
                                           "shipped_at": datetime.now(UTC) - timedelta(days=20)}],
                       "read.policy": policy()})
    result = await OrderShippingTeam(tools).execute(
        task("order_shipping", "order.investigate", context, OrderShippingTeam.manifest.allowed_tools))
    assert result.action_proposals[0].action_type == "refund.request"


@pytest.mark.asyncio
async def test_degraded_context_escalates_without_answer():
    context = pack("order_shipping", degraded=True)
    result = await OrderShippingTeam(FakeTools({})).execute(task("order_shipping", "order.investigate", context, OrderShippingTeam.manifest.allowed_tools))
    assert result.outcome == "escalated" and result.next_action is NextAction.ESCALATE
    assert result.answer is None


def test_tool_allowlist_and_repetition_guard():
    toolbox = ReadToolbox(lambda: None)
    context = pack("order_shipping")
    with pytest.raises(ToolNotAllowed):
        toolbox.call("read.account", context, {}, ["read.order"], set())
    seen = set()
    # no DB call is needed: the second identical request is rejected first
    toolbox.order = lambda scope, **kwargs: {"order_id": "o1", "status": "delivered"}
    toolbox.call("read.order", context, {}, ["read.order"], seen)
    with pytest.raises(ToolLoopExceeded):
        toolbox.call("read.order", context, {}, ["read.order"], seen)
