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


# ── 2026-08-31: 제안에 근거 id 가 붙는지 아무도 안 세던 사각지대 ──────
#
# `rationale_evidence_ids` 를 빈 리스트로 만들어도 전체 424개가 전부 통과했다.
# 근거를 모아 놓고 제안에 달지 않으면 승인자는 무엇을 보고 판단할지 모르고,
# 검증기도 대조할 것이 없다.


@pytest.mark.asyncio
async def test_proposal_carries_the_evidence_it_was_built_from():
    result = await ProcurementOrderPaymentTeam(FakeTools()).execute(
        make_task("order.create", order_draft={"sku": "sku-1", "quantity": 1})
    )
    proposal = result.action_proposals[0]
    assert proposal.rationale_evidence_ids, "제안에 근거 id 가 하나도 붙지 않았다"
    known = {item.evidence_id for item in result.evidence}
    assert set(proposal.rationale_evidence_ids) <= known, (
        "제안이 결과에 없는 근거 id 를 든다 — 지어낸 근거다"
    )


# ★2026-09-01 — "order" intent 는 늘 order.verify(정보성 조회)로만 갔다.
#   select_capability 가 취소/변경 요청 문구를 잡아 order.cancel/order.modify
#   경로로 보낼 수 있는지 확인한다
#   (wiki/records/reports/debugs/2026-09-01_capability_for_폴백이_근거없이_기능을_고른다.md).
def test_select_capability_routes_explicit_cancel_request_to_order_cancel():
    assert ProcurementOrderPaymentTeam.select_capability("order", "주문 취소해주세요") == "order.cancel"


def test_select_capability_routes_explicit_change_request_to_order_modify():
    assert ProcurementOrderPaymentTeam.select_capability("order", "배송지를 변경하고 싶어요") == "order.modify"


def test_select_capability_returns_none_for_plain_status_inquiry():
    assert ProcurementOrderPaymentTeam.select_capability("order", "제 주문이 잘 들어갔는지 확인하고 싶어요") is None


def test_select_capability_ignores_unrelated_intents():
    assert ProcurementOrderPaymentTeam.select_capability("shipping", "주문 취소해주세요") is None
    assert ProcurementOrderPaymentTeam.select_capability(None, "주문 취소해주세요") is None


# ★2026-09-02 holdout 실측(h-order-02) — "취소해야 하나요?"(고민)를
#   "취소해 주세요"(요청)로 잘못 잡던 것을 좁혔다. 물어본 것을 실행 제안으로
#   바꾸면 승인 큐에 없던 일이 생긴다.
def test_deliberating_about_cancelling_is_not_a_cancel_request():
    assert ProcurementOrderPaymentTeam.select_capability(
        "order", "받은 상품 중 한 개의 옵션만 잘못 왔습니다. 주문 전체를 취소해야 하나요?") is None


def test_an_explicit_cancel_request_still_routes_to_cancel():
    assert ProcurementOrderPaymentTeam.select_capability("order", "주문 취소해 주세요") == "order.cancel"
    assert ProcurementOrderPaymentTeam.select_capability("order", "주문 취소 부탁드립니다") == "order.cancel"


@pytest.mark.asyncio
async def test_order_modify_carries_field_names_not_raw_values():
    """★값은 실행 인자에 넣지 않는다 (2026-09-03).

    전에는 고객이 준 dict 를 `changes` 로 통째로 실었다. 대조할 규칙이 없어
    검증 정책이 막았고 **주문 변경은 승인 자체가 안 됐다.** 지금은 이름만 싣고
    값은 근거로 보낸다 — 승인자는 보되, 대조되지 않은 값이 실행 인자로는
    들어가지 않는다.
    """
    tools = FakeTools(order={"order_id": "order-1", "fulfillment_status": "paid"})
    result = await ProcurementOrderPaymentTeam(tools).execute(
        make_task("order.modify", order_change={"shipping_address": "new-address",
                                                "delivery_message": "문 앞에"})
    )

    arguments = result.action_proposals[0].arguments
    assert "changes" not in arguments
    assert arguments["change_fields"] == ["delivery_message", "shipping_address"]
    assert "new-address" not in str(arguments)
    # 값은 근거에 있다 — 승인자가 무엇을 승인하는지 볼 수 있어야 한다
    assert any("new-address" in str(item.value) for item in result.evidence)


@pytest.mark.asyncio
async def test_a_quantity_change_is_flattened_so_it_can_be_checked():
    """★수량만은 최상위로 편다 — `orders.item_count` 상한 검사를 받게."""
    tools = FakeTools(order={"order_id": "order-1", "fulfillment_status": "paid"})
    result = await ProcurementOrderPaymentTeam(tools).execute(
        make_task("order.modify", order_change={"quantity": 3})
    )

    assert result.action_proposals[0].arguments["change_quantity"] == 3


@pytest.mark.asyncio
async def test_an_unknown_change_kind_is_refused_not_proposed():
    """★모르는 변경은 제안하지 않는다. 무엇을 바꾸는지 모르면 승인자도 판단 못 한다."""
    tools = FakeTools(order={"order_id": "order-1", "fulfillment_status": "paid"})
    result = await ProcurementOrderPaymentTeam(tools).execute(
        make_task("order.modify", order_change={"total_price": 1})
    )

    assert result.outcome == "escalated"
    assert result.failure_code == "order_modify_unsupported_change"
    assert result.action_proposals == []


@pytest.mark.asyncio
async def test_an_unreadable_quantity_is_refused():
    tools = FakeTools(order={"order_id": "order-1", "fulfillment_status": "paid"})
    result = await ProcurementOrderPaymentTeam(tools).execute(
        make_task("order.modify", order_change={"quantity": "세 개"})
    )

    assert result.outcome == "escalated"
    assert result.failure_code == "order_modify_quantity_unreadable"
