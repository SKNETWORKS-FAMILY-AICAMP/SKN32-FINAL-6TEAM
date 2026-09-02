"""Team 이 **실제로 내는** 제안의 모든 필드가 검증 정책에 선언돼 있는가.

★이 검사가 없어서 두 번 새어나갔다.

    2026-08-17  `evidence`           — 실 브라우저 승인 클릭으로 발견
    2026-09-03  `calculation_basis`  — 코드를 읽다 발견

  둘 다 같은 구멍이다: 제안을 **만드는 쪽**과 승인 직전 **재검증하는 쪽**을
  이어서 보는 검사가 없었다. 각자의 단위 테스트는 다 초록이었다 —
  제안 생성 테스트는 제안이 나오는지만 봤고, 검증 테스트는 손으로 만든
  arguments 를 썼다. 그 사이에서 새는 것을 아무도 안 봤다.

★선언되지 않은 필드는 `verify_proposal` 이 "검사 규칙이 없으면 실행하지 않는다"
  로 막는다. 그 설계는 옳다 — 문제는 **막힌다는 사실을 아무도 몰랐다**는 것이다.
  환불 제안은 승인 자체가 되지 않는 상태였다.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.contracts import ContextPack, TeamTask
from app.modules.customer_ops.return_refund import ReturnRefundTeam
from app.modules.customer_ops.verification_policy import CUSTOMER_OPS_POLICY

DECLARED = (set(CUSTOMER_OPS_POLICY.references)
            | CUSTOMER_OPS_POLICY.quantity_fields
            | CUSTOMER_OPS_POLICY.opaque
            | CUSTOMER_OPS_POLICY.ignored)

ITEMS = [{"order_item_id": "item-A", "sku": "SKU-1", "name": "위젯",
          "quantity": 2, "unit_cents": 5000}]
ORDER = {"order_id": "o1", "total_cents": 10000, "item_count": 2}
POLICY = [{"return_period_days": 7}]


class FakeTools:
    def __init__(self, values):
        self.values = values

    def call(self, name, context, arguments, allowed_tools, seen):
        return self.values.get(name)


def _task(capability: str) -> tuple[TeamTask, FakeTools]:
    case_id = uuid4()
    context = ContextPack(
        pack_id=uuid4(), case_id=case_id, team_id="return_refund", tenant_id="tenant",
        knowledge_scope=ReturnRefundTeam.manifest.knowledge_scope,
        current_state={"customer_id": str(uuid4()), "reason_code": "changed_mind",
                       "return_quantity": 1},
        estimated_input_tokens=10,
    )
    task = TeamTask(
        task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id="return_refund",
        capability=capability, case_version=1, input_text="반품 요청", context=context,
        allowed_tools=ReturnRefundTeam.manifest.allowed_tools,
        deadline_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    order = dict(ORDER, ordered_at=datetime.now(UTC) - timedelta(days=2))
    return task, FakeTools({"read.order": order, "read.return": [], "read.policy": POLICY,
                            "read.order_items": ITEMS})


@pytest.mark.asyncio
@pytest.mark.parametrize("capability", ["return.request", "refund.calculate"])
async def test_every_proposal_field_is_declared_in_the_policy(capability):
    """★제안이 실제로 내는 키만 본다 — 손으로 만든 arguments 가 아니다."""
    task, tools = _task(capability)
    result = await ReturnRefundTeam(tools).execute(task)

    assert result.action_proposals, f"{capability} 가 제안을 내지 않았다"
    for proposal in result.action_proposals:
        undeclared = sorted(set(proposal.arguments) - DECLARED)
        assert not undeclared, (
            f"{capability} 제안에 선언되지 않은 필드가 있다: {undeclared}.\n"
            "이대로면 승인 직전 재검증(proposal_guard.recheck_before_execution)이 "
            "막아 승인 자체가 되지 않는다. 대조 대상이면 references/quantities 에, "
            "설명용이면 ignored 에 **이유와 함께** 넣어라.")


#: 각 Team 이 실제로 내는 제안의 최상위 키. ★코드를 읽어 옮긴 것이다 —
#:  코드에서 가져오면 "코드가 코드와 같다" 는 항상 참인 검사가 된다
#:  (`tests/contract/test_case_state_table.py` 와 같은 이유).
EMITTED_ARGUMENT_KEYS = {
    "refund.calculate": {"order_id", "refund_amount_cents", "return_quantity",
                         "calculation_basis"},
    "return.request": {"order_id", "reason_code", "return_quantity"},
    # Procurement + Order & Payment
    "order.create(fallback)": {"request"},
    "order.modify": {"order_id", "changes", "fulfillment_status"},
    "order.cancel": {"order_id", "scope", "reason", "seller_fault",
                     "warehouse_handoff", "fulfillment_status"},
    # Fulfillment & Logistics
    "shipment.reship": {"shipment_id", "reason"},
}

#: ★의도적으로 막히는 것. `opaque` 는 "확인 못 하니 거부한다" 는 선언이다.
DELIBERATELY_REFUSED = {"order.modify": {"changes"}}


@pytest.mark.parametrize("action_type", sorted(EMITTED_ARGUMENT_KEYS))
def test_no_proposal_type_is_blocked_by_an_undeclared_field(action_type):
    """★2026-09-03 실측: 이 검사가 없어 **다섯 종류가 막혀 있었다.**

    `refund.calculate`(calculation_basis) 와 Procurement 의 세 종류
    (request·changes·fulfillment_status·scope·seller_fault·warehouse_handoff).
    선언되지 않은 필드는 승인 직전 재검증이 막으므로, 그 제안은 **승인 자체가
    되지 않는다.** 각 Team 의 단위 테스트는 전부 초록이었다 — 제안이 나오는지만
    봤기 때문이다.
    """
    keys = EMITTED_ARGUMENT_KEYS[action_type]
    undeclared = sorted(keys - DECLARED)
    assert not undeclared, (
        f"{action_type} 제안의 필드가 정책에 없다: {undeclared}. "
        "대조할 수 있으면 references/quantities, 설명용이면 ignored, "
        "확인할 수단이 없으면 opaque 에 **이유와 함께** 넣어라.")


@pytest.mark.parametrize("action_type", sorted(DELIBERATELY_REFUSED))
def test_unverifiable_fields_are_refused_not_waved_through(action_type):
    """★`changes` 는 고객이 준 변경 요청 그대로다 — 금액·수량이 들어올 수 있는데
    대조할 규칙이 없다. `ignored` 로 빼면 검사 없이 실행된다. 막히는 것이 맞다.
    """
    from app.modules.customer_ops.verification_policy import CUSTOMER_OPS_POLICY

    assert DELIBERATELY_REFUSED[action_type] <= CUSTOMER_OPS_POLICY.opaque
