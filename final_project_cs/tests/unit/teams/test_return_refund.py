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


#: ★기본 픽스처를 **품목 하나짜리 주문**으로 바꿨다(2026-09-01, D-001 1-A).
#:  단가 10,000 × 1개 = 총액 10,000 으로 맞춰 둔다 — 합이 총액과 다르면 할인이
#:  있다는 뜻이고, 그때는 금액을 만들지 않는 것이 새 계약이다.
DEFAULT_ITEMS = [{"sku": "SKU-1", "name": "위젯", "quantity": 1, "unit_cents": 10000}]


def make_task(capability: str, *, ordered_at=None, returns=None, order=None, policy=None,
              items=None):
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
    order = order or {"order_id": "o1", "total_cents": 10000, "item_count": 1,
                      "ordered_at": ordered_at or datetime.now(UTC) - timedelta(days=2)}
    returns = returns if returns is not None else []
    policy = policy if policy is not None else [{"return_period_days": 7}]
    items = DEFAULT_ITEMS if items is None else items
    return task, FakeTools({"read.order": order, "read.return": returns, "read.policy": policy,
                            "read.order_items": items})


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
    # ★품목 단가 그대로다. 옛 구현은 `total * qty // item_count` 라 2품목 주문이면
    #   5,000 을 냈다 — 품목 값이 서로 다르면 그 액수는 근거가 없다(D-001).
    assert result.action_proposals[0].arguments["refund_amount_cents"] == 10000
    assert result.action_proposals[0].arguments["calculation_basis"]["basis"] == "order_item_unit_price"


@pytest.mark.asyncio
async def test_multi_item_order_does_not_get_a_made_up_amount():
    """★어느 품목을 반품하는지 모르면 금액을 만들지 않는다.

    `returns` 테이블에는 품목 참조가 없다(order_id·reason_code·quantity 뿐).
    옛 구현은 총액을 품목 수로 나눠 5,000 을 냈는데, 품목 값이 다르면 고객이
    받을 금액이 달라진다.
    """
    task, tools = make_task("refund.calculate",
                            order={"order_id": "o1", "total_cents": 30000, "item_count": 2,
                                   "ordered_at": datetime.now(UTC) - timedelta(days=2)},
                            items=[{"sku": "A", "name": "비싼 것", "quantity": 1, "unit_cents": 25000},
                                   {"sku": "B", "name": "싼 것", "quantity": 1, "unit_cents": 5000}])
    result = await ReturnRefundTeam(tools).execute(task)

    assert result.outcome == "escalated"
    assert result.failure_code == "refund_item_unattributable"
    assert not result.action_proposals


@pytest.mark.asyncio
async def test_multi_item_order_is_exact_when_the_return_names_the_item():
    """★마이그레이션 007 이후 — 반품이 품목을 밝히면 다품목도 정확히 계산된다.

    비싼 품목(25,000)을 반품했는데 옛 구현은 총액 30,000 ÷ 2 = 15,000 을 냈다.
    """
    task, tools = make_task(
        "refund.calculate",
        order={"order_id": "o1", "total_cents": 30000, "item_count": 2,
               "ordered_at": datetime.now(UTC) - timedelta(days=2)},
        items=[{"order_item_id": "item-A", "sku": "A", "name": "비싼 것",
                "quantity": 1, "unit_cents": 25000},
               {"order_item_id": "item-B", "sku": "B", "name": "싼 것",
                "quantity": 1, "unit_cents": 5000}],
        returns=[{"return_id": "r1", "order_id": "o1", "order_item_id": "item-A",
                  "reason_code": "defective", "quantity": 1, "status": "requested"}])
    result = await ReturnRefundTeam(tools).execute(task)

    proposal = result.action_proposals[0]
    assert proposal.arguments["refund_amount_cents"] == 25000
    assert proposal.arguments["calculation_basis"]["order_item_id"] == "item-A"
    assert proposal.arguments["calculation_basis"]["sku"] == "A"


@pytest.mark.asyncio
async def test_a_return_pointing_at_another_order_is_refused():
    """★반품이 가리키는 품목이 이 주문에 없으면 데이터가 어긋난 것이다."""
    task, tools = make_task(
        "refund.calculate",
        order={"order_id": "o1", "total_cents": 30000, "item_count": 2,
               "ordered_at": datetime.now(UTC) - timedelta(days=2)},
        items=[{"order_item_id": "item-A", "sku": "A", "name": "가", "quantity": 1, "unit_cents": 25000},
               {"order_item_id": "item-B", "sku": "B", "name": "나", "quantity": 1, "unit_cents": 5000}],
        returns=[{"return_id": "r1", "order_id": "o1", "order_item_id": "item-Z",
                  "reason_code": "defective", "quantity": 1, "status": "requested"}])
    result = await ReturnRefundTeam(tools).execute(task)

    assert result.outcome == "escalated"
    assert result.failure_code == "refund_item_not_in_order"


@pytest.mark.asyncio
async def test_an_old_return_without_attribution_still_escalates():
    """★007 이전에 쌓인 반품에는 품목 정보가 없다. 지금 와서 찍지 않는다."""
    task, tools = make_task(
        "refund.calculate",
        order={"order_id": "o1", "total_cents": 30000, "item_count": 2,
               "ordered_at": datetime.now(UTC) - timedelta(days=2)},
        items=[{"order_item_id": "item-A", "sku": "A", "name": "가", "quantity": 1, "unit_cents": 25000},
               {"order_item_id": "item-B", "sku": "B", "name": "나", "quantity": 1, "unit_cents": 5000}],
        returns=[{"return_id": "r1", "order_id": "o1", "order_item_id": None,
                  "reason_code": "defective", "quantity": 1, "status": "requested"}])
    result = await ReturnRefundTeam(tools).execute(task)

    assert result.outcome == "escalated"
    assert result.failure_code == "refund_item_unattributable"


@pytest.mark.asyncio
async def test_a_discounted_order_is_not_computed_from_list_prices():
    """★품목 단가 합이 총액과 다르면 할인·쿠폰·배송비가 끼어 있다는 뜻이다.

    정가로 계산하면 실제 결제액보다 많이 환불된다. 쇼핑몰의 실결제 내역이
    필요하다(D-001 1-B) — 그 전까지는 사람에게 넘긴다.
    """
    task, tools = make_task("refund.calculate",
                            order={"order_id": "o1", "total_cents": 8000, "item_count": 1,
                                   "ordered_at": datetime.now(UTC) - timedelta(days=2)},
                            items=[{"sku": "A", "name": "할인된 것", "quantity": 1, "unit_cents": 10000}])
    result = await ReturnRefundTeam(tools).execute(task)

    assert result.outcome == "escalated"
    assert result.failure_code == "refund_amount_not_derivable"
    assert "실제 결제액" in result.warnings[0]


@pytest.mark.asyncio
async def test_multiple_units_of_one_item_are_multiplied_not_split():
    task, tools = make_task("refund.calculate",
                            order={"order_id": "o1", "total_cents": 30000, "item_count": 3,
                                   "ordered_at": datetime.now(UTC) - timedelta(days=2)},
                            items=[{"sku": "A", "name": "위젯", "quantity": 3, "unit_cents": 10000}])
    result = await ReturnRefundTeam(tools).execute(task)

    # 반품 수량 1개 → 10,000. 옛 구현도 우연히 같은 값을 냈지만 근거가 달랐다
    # (총액 ÷ 품목 수). 이제는 단가 × 수량이다.
    assert result.action_proposals[0].arguments["refund_amount_cents"] == 10000


@pytest.mark.asyncio
async def test_returning_more_than_ordered_is_refused():
    task, tools = make_task("refund.calculate",
                            order={"order_id": "o1", "total_cents": 10000, "item_count": 1,
                                   "ordered_at": datetime.now(UTC) - timedelta(days=2)},
                            items=[{"sku": "A", "name": "위젯", "quantity": 1, "unit_cents": 10000}])
    task.context.current_state["return_quantity"] = 5
    result = await ReturnRefundTeam(tools).execute(task)

    assert result.outcome == "escalated"
    assert result.failure_code == "refund_quantity_exceeds_order"


@pytest.mark.asyncio
async def test_missing_order_items_escalates_instead_of_guessing():
    task, tools = make_task("refund.calculate", items=[])
    result = await ReturnRefundTeam(tools).execute(task)

    assert result.outcome == "escalated"
    assert result.failure_code == "refund_calculation_evidence_missing"


def test_the_team_is_allowed_to_read_order_items():
    """★툴은 전부터 있었지만 allowed_tools 에 없어 Registry 가 막고 있었다."""
    assert "read.order_items" in ReturnRefundTeam.manifest.allowed_tools


# ★2026-09-01 — "exchange" intent 는 이름으로 매칭되는 capability 가 없어
#   늘 check_eligibility(정보성 응답)로만 갔다. select_capability 가 실행
#   요청 문구를 잡아 return.request 경로로 보낼 수 있는지 확인한다
#   (docs/reports/debugs/2026-09-01_capability_for_폴백이_근거없이_기능을_고른다.md).
def test_select_capability_routes_explicit_exchange_request_to_return_request():
    assert ReturnRefundTeam.select_capability("exchange", "사이즈가 안 맞아서 교환하고 싶어요") == "return.request"


def test_select_capability_routes_explicit_return_request_to_return_request():
    assert ReturnRefundTeam.select_capability("return", "반품 신청 부탁드려요") == "return.request"


def test_select_capability_returns_none_for_plain_eligibility_inquiry():
    # 신호가 없으면 기존 규칙(default_capability=check_eligibility)에 맡긴다.
    assert ReturnRefundTeam.select_capability("exchange", "교환 가능한 기간이 얼마나 되나요?") is None


def test_select_capability_ignores_unrelated_intents():
    assert ReturnRefundTeam.select_capability("order", "교환하고 싶어요") is None
    assert ReturnRefundTeam.select_capability(None, "교환하고 싶어요") is None


# ★procurement 의 "취소해" 와 같은 부류 — "교환해야 하나요?"(고민)를
#   요청으로 보지 않는다(2026-09-02 함께 좁힘).
def test_deliberating_about_exchanging_is_not_an_exchange_request():
    assert ReturnRefundTeam.select_capability("exchange", "이 경우 교환해야 하나요?") is None


def test_an_explicit_exchange_request_still_routes_to_request():
    assert ReturnRefundTeam.select_capability("exchange", "사이즈가 안 맞아서 교환해 주세요") == "return.request"
