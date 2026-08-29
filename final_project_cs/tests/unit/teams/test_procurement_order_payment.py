from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.contracts import ContextPack, Evidence, TeamModule, TeamTask
from app.modules.customer_ops import ProcurementOrderPaymentTeam


class FakeTools:
    def __init__(self, *, policy=None, order=None, catalog=None):
        self.policy = policy
        self.order_record = order
        self.catalog_record = catalog

    def call(self, name, context, arguments, allowed_tools, seen):
        if name == "read.policy":
            return self.policy
        if name == "read.order":
            return self.order_record
        if name == "read.catalog":
            return self.catalog_record
        raise AssertionError(name)


def make_task(capability, *, evidence=True, **state):
    case_id = uuid4()
    facts = []
    if evidence:
        facts.append(Evidence(
            evidence_id="ev:request", source_type="case_event", source_id=str(case_id),
            claim="request context", value={"request": "customer request"}, confidence=1.0,
            observed_at=datetime.now(UTC),
        ))
    pack = ContextPack(
        pack_id=uuid4(), case_id=case_id, team_id="procurement_order_payment",
        tenant_id="tenant-1", knowledge_scope=["catalog", "pricing", "order", "payment", "procurement"],
        current_state=state, evidence=facts, estimated_input_tokens=10,
    )
    return TeamTask(
        task_id=uuid4(), run_id=uuid4(), case_id=case_id,
        team_id="procurement_order_payment", capability=capability, case_version=1,
        input_text="Please check this request", context=pack,
        allowed_tools=["read.order", "read.account", "read.policy", "read.catalog"],
        deadline_at=datetime.now(UTC) + timedelta(seconds=30),
    )


def test_manifest_matches_registry_contract():
    team = ProcurementOrderPaymentTeam(FakeTools())
    assert isinstance(team, TeamModule)
    assert team.manifest.capabilities == [
        "procurement.quote", "order.verify", "order.create", "order.modify", "order.cancel", "payment.status",
    ]
    assert team.manifest.accepted_case_types == ["procurement", "order", "payment"]


@pytest.mark.asyncio
async def test_procurement_quote_uses_policy_and_pricing_evidence():
    result = await ProcurementOrderPaymentTeam(FakeTools(policy=[{"policy_ref": "pricing-1"}])).execute(
        make_task("procurement.quote", pricing={"sku-1": 1200})
    )
    assert result.outcome == "completed"
    assert result.evidence
    assert result.decisions[0]["classification"] == "procurement_quote"


@pytest.mark.asyncio
async def test_procurement_quote_reads_catalog_when_pricing_is_not_injected():
    tools = FakeTools(policy=[{"policy_ref": "pricing-1"}],
                      catalog={"sku": "SKU-CPG-01", "unit_cents": 4100, "status": "active"})
    result = await ProcurementOrderPaymentTeam(tools).execute(
        make_task("procurement.quote", sku="SKU-CPG-01")
    )
    assert result.outcome == "completed"
    assert result.decisions[0]["quote"] == {"SKU-CPG-01": 4100}


@pytest.mark.asyncio
async def test_procurement_quote_escalates_for_missing_or_discontinued_catalog_product():
    for catalog in (None, {"sku": "SKU-CPG-01", "unit_cents": 4100, "status": "discontinued"}):
        result = await ProcurementOrderPaymentTeam(FakeTools(catalog=catalog)).execute(
            make_task("procurement.quote", sku="SKU-CPG-01")
        )
        assert result.outcome == "escalated"
        assert result.failure_code == "quote_catalog_product_missing"


@pytest.mark.asyncio
async def test_order_verify_compares_local_order_record():
    tools = FakeTools(order={"order_id": "order-1", "order_no": "A-1", "status": "paid"})
    result = await ProcurementOrderPaymentTeam(tools).execute(make_task("order.verify", order_id="order-1"))
    assert result.outcome == "completed"
    assert result.decisions[0]["matched"] is True


@pytest.mark.asyncio
async def test_order_create_returns_approval_required_proposal_without_side_effect():
    result = await ProcurementOrderPaymentTeam(FakeTools()).execute(
        make_task("order.create", order_draft={"sku": "sku-1", "quantity": 1})
    )
    assert result.outcome == "waiting"
    proposal = result.action_proposals[0]
    assert proposal.action_type == "order.create"
    assert proposal.approval_required is True
    assert proposal.risk_level == "high"


@pytest.mark.asyncio
async def test_payment_status_reads_context_without_confirming_payment():
    result = await ProcurementOrderPaymentTeam(FakeTools()).execute(
        make_task("payment.status", payment_status="authorized")
    )
    assert result.outcome == "completed"
    assert result.decisions[0]["status"] == "authorized"
    assert result.action_proposals == []


@pytest.mark.asyncio
async def test_order_modify_returns_approval_required_proposal_before_shipment():
    tools = FakeTools(order={"order_id": "order-1", "fulfillment_status": "paid"})
    result = await ProcurementOrderPaymentTeam(tools).execute(
        make_task("order.modify", order_change={"shipping_address": "new-address"})
    )
    assert result.outcome == "waiting"
    proposal = result.action_proposals[0]
    assert proposal.action_type == "order.modify"
    assert proposal.approval_required is True
    assert proposal.arguments["fulfillment_status"] == "paid"


@pytest.mark.asyncio
async def test_order_cancel_returns_high_risk_proposal_with_cancellation_basis():
    tools = FakeTools(order={"order_no": "A-1", "status": "processing"})
    result = await ProcurementOrderPaymentTeam(tools).execute(
        make_task("order.cancel", cancellation_scope="partial", seller_fault=True, warehouse_handoff=False,
                  cancellation_reason="seller_fault")
    )
    assert result.outcome == "waiting"
    proposal = result.action_proposals[0]
    assert proposal.action_type == "order.cancel"
    assert proposal.risk_level == "high"
    assert proposal.arguments["scope"] == "partial"


@pytest.mark.asyncio
async def test_order_modify_without_order_evidence_escalates():
    result = await ProcurementOrderPaymentTeam(FakeTools()).execute(
        make_task("order.modify", evidence=False, order_change={"color": "blue"})
    )
    assert result.outcome == "escalated"
    assert result.failure_code == "order_change_evidence_missing"


@pytest.mark.asyncio
async def test_missing_evidence_escalates():
    result = await ProcurementOrderPaymentTeam(FakeTools()).execute(
        make_task("order.create", evidence=False, order_draft={"sku": "sku-1"})
    )
    assert result.outcome == "escalated"
    assert result.next_action.value == "escalate"
    assert result.failure_code == "order_create_evidence_missing"
