"""Mock-only Return & Refund Team.

This module may calculate and propose actions, but it never performs a return
or refund side effect.  Approval is the boundary for every such proposal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.contracts import ActionProposal, Evidence, NextAction, TeamManifest, TeamResult, TeamTask
from app.core.idempotency import idempotency_key
from app.tools.read_tools import ReadToolbox, ToolLoopExceeded


@dataclass(frozen=True)
class RefundOutcome:
    """환불 금액을 구했거나, 왜 못 구했는지.

    ★"못 구했다" 를 0 이나 None 으로 돌려주지 않는다. 부르는 쪽이 그걸 금액으로
      쓰면 고객에게 잘못된 액수가 나간다. 실패는 이유와 함께 돌려준다.
    """

    amount: int = 0
    basis: dict[str, Any] = field(default_factory=dict)
    failure_code: str | None = None
    reason: str = ""


class ReturnRefundTeam:
    manifest = TeamManifest(
        team_id="return_refund",
        display_name="Return & Refund Team",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=["return.check_eligibility", "return.request", "refund.calculate"],
        accepted_case_types=["return", "refund", "exchange"],
        required_context=["case_state", "policy", "db_facts", "history"],
        # ★`read.order_items` 는 2026-09-01 에 더했다. 환불 금액을 주문 총액의
        #   균등 분할로 추정하던 것을 품목 단가로 정확히 구하기 위해서다(D-001 1-A).
        #   툴은 이미 있었지만 이 Team 의 allowed_tools 에 없어 Registry 가 막고 있었다.
        allowed_tools=["read.order", "read.order_items", "read.return", "read.policy"],
        knowledge_scope=["order", "return", "refund", "exchange", "policy"],
        max_steps=6,
        active=True,
        implementation_revision="2026-09-01",
        # ★"exchange" intent 는 이름으로 매칭되는 capability 가 없다 — 셋 다
        #   "exchange." 로 시작하지 않는다(return./refund.). 지금 실제
        #   동작(capabilities[0])과 같은 값을 명시적으로 선언한다.
        default_capability="return.check_eligibility",
    )

    def __init__(self, tools: ReadToolbox) -> None:
        self.tools = tools

    @staticmethod
    def _result(task: TeamTask, **kwargs: Any) -> TeamResult:
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id, **kwargs)

    @staticmethod
    def _evidence(task: TeamTask, order: Any, returns: Any, policy: Any) -> list[Evidence]:
        evidence = list(task.context.evidence)
        evidence.append(Evidence(
            evidence_id="tool:return_refund",
            source_type="tool_result",
            source_id="read.order+read.return+read.policy",
            claim="주문, 반품 이력, 반품·환불 정책을 조회했다.",
            value={"order": order, "returns": returns, "policy": policy},
            confidence=1.0,
            observed_at=datetime.now(UTC),
        ))
        return evidence

    @staticmethod
    def _policy_days(policy: Any, reason: str | None) -> int:
        # The mock accepts common policy shapes while retaining conservative defaults.
        values: list[Any] = policy if isinstance(policy, list) else [policy]
        for item in values:
            value = item.value if isinstance(item, Evidence) else item
            if isinstance(value, dict):
                key = "defective_return_period_days" if reason == "defective" else "return_period_days"
                if isinstance(value.get(key), int):
                    return value[key]
                if isinstance(value.get("return_period_days"), int):
                    return value["return_period_days"]
        return 90 if reason == "defective" else 7

    @staticmethod
    def _refund_amount(items: Any, order_total_cents: int, quantity: int,
                       order_item_id: str | None = None) -> "RefundOutcome":
        """반품 수량에 해당하는 환불 금액을 **구할 수 있을 때만** 구한다.

        ★이전 구현은 `total_cents * quantity // item_count` 였다. 이 한 줄에
          말하지 않은 가정이 둘 들어 있었다(D-001):

            (1) 주문의 모든 품목 값이 같다
            (2) 주문에 할인이 없다

          둘 다 틀리면 고객이 받을 금액이 달라진다. 여기서는 두 가정을 **검사
          가능한 조건**으로 바꾼다 — 성립하면 정확히 계산하고, 안 하면 계산하지
          않는다.

        ★(2)를 어떻게 아는가: 품목 단가 합이 주문 총액과 다르면 그 차액이
          할인·쿠폰·배송비 같은 조정이다. 그게 있으면 "이 품목의 실결제액" 을
          이 데이터만으로는 모른다 — 쇼핑몰이 실결제액을 줘야 한다(D-001 1-B).

        ★(1)을 어떻게 아는가: 품목이 하나면 가정이 필요 없다. 여럿이면 **어느
          품목을 반품하는지** 를 알아야 한다. 2026-09-01 마이그레이션 007 로
          `returns.order_item_id` 가 생겨서, 그 값이 있으면 다품목 주문도 정확히
          계산한다. **없으면(NULL) 여전히 만들지 않는다** — 그 이전에 쌓인
          반품에는 품목 정보가 없고, 지금 와서 찍으면 지어낸 값이다.
        """
        if not isinstance(items, list) or not items:
            return RefundOutcome(failure_code="refund_calculation_evidence_missing",
                                 reason="주문 품목을 읽지 못해 환불 금액을 계산할 수 없습니다.")
        try:
            lines = [(str(item.get("order_item_id") or ""), str(item["sku"]),
                      int(item["quantity"]), int(item["unit_cents"]))
                     for item in items]
        except (KeyError, TypeError, ValueError, AttributeError):
            return RefundOutcome(failure_code="refund_calculation_evidence_missing",
                                 reason="주문 품목에 수량·단가가 없어 환불 금액을 계산할 수 없습니다.")

        subtotal = sum(unit * count for _, _, count, unit in lines)
        if subtotal != order_total_cents:
            # 차액이 곧 할인·쿠폰·배송비다. 어느 품목에 얼마가 붙었는지 모른다.
            return RefundOutcome(
                failure_code="refund_amount_not_derivable",
                reason=(f"품목 단가 합({subtotal})과 주문 총액({order_total_cents})이 달라 "
                        "실제 결제액을 알 수 없습니다. 쇼핑몰의 실결제 내역이 필요합니다."))
        if len(lines) == 1:
            selected = lines[0]
        elif order_item_id:
            # 반품이 어느 품목인지 밝혔다(마이그레이션 007).
            selected = next((line for line in lines if line[0] == str(order_item_id)), None)
            if selected is None:
                return RefundOutcome(
                    failure_code="refund_item_not_in_order",
                    reason=("반품이 가리키는 품목이 이 주문에 없습니다. "
                            "주문과 반품이 어긋나 있습니다."))
        else:
            return RefundOutcome(
                failure_code="refund_item_unattributable",
                reason=("주문에 품목이 여러 개인데 반품 요청에 어느 품목인지가 없어 "
                        "환불 금액을 정할 수 없습니다."))

        item_id, sku, ordered_quantity, unit_cents = selected
        if quantity <= 0 or quantity > ordered_quantity:
            return RefundOutcome(
                failure_code="refund_quantity_exceeds_order",
                reason=f"반품 수량({quantity})이 주문 수량({ordered_quantity})을 벗어납니다.")
        return RefundOutcome(amount=unit_cents * quantity,
                             basis={"basis": "order_item_unit_price", "sku": sku,
                                    "order_item_id": item_id or None,
                                    "unit_cents": unit_cents, "return_quantity": quantity,
                                    "order_total_cents": order_total_cents,
                                    "order_item_lines": len(lines)})

    @staticmethod
    def _date(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
            except ValueError:
                return None
        return None

    async def execute(self, task: TeamTask) -> TeamResult:
        evidence = list(task.context.evidence)
        if task.context.degraded:
            return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                next_action=NextAction.ESCALATE, failure_code="degraded_context")
        if task.capability not in self.manifest.capabilities:
            return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                next_action=NextAction.ESCALATE, failure_code="unsupported_capability")

        seen: set[str] = set()
        try:
            order = self.tools.call("read.order", task.context, {}, task.allowed_tools, seen)
            returns = self.tools.call("read.return", task.context, {}, task.allowed_tools, seen)
            policy = self.tools.call("read.policy", task.context, {"query": task.input_text}, task.allowed_tools, seen)
        except ToolLoopExceeded:
            return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                next_action=NextAction.ESCALATE, failure_code="tool_loop_guard")

        evidence = self._evidence(task, order, returns, policy)
        history = returns if isinstance(returns, list) else []
        current = task.context.current_state
        request = next((item for item in history if isinstance(item, dict)), None)
        reason = (request or {}).get("reason_code") or current.get("reason_code")
        quantity = (request or {}).get("quantity") or current.get("return_quantity")
        if not order or not policy:
            return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                next_action=NextAction.ESCALATE, failure_code="required_evidence_missing")
        if reason is None or quantity is None:
            return self._result(task, outcome="waiting", confidence=0.0, evidence=evidence,
                                next_action=NextAction.WAIT_FOR_INPUT, wait_reason="customer_input",
                                required_input_schema={"required": ["reason_code", "return_quantity"]},
                                warnings=["반품 사유와 수량을 확인할 근거가 필요합니다."])

        # ``requested`` can be the current request supplied by the read tool;
        # only a previously accepted/in-flight/completed record blocks a new one.
        active_history = {"approved", "processing", "completed"}
        if any(item.get("status") in active_history for item in history if isinstance(item, dict)):
            return self._result(task, outcome="escalated", confidence=0.9, evidence=evidence,
                                next_action=NextAction.ESCALATE, failure_code="return_already_in_history")

        ordered_at = self._date(order.get("ordered_at")) if isinstance(order, dict) else None
        period_days = self._policy_days(policy, reason)
        if ordered_at and (datetime.now(UTC) - ordered_at.astimezone(UTC)).days > period_days:
            return self._result(task, outcome="escalated", confidence=0.9, evidence=evidence,
                                next_action=NextAction.ESCALATE, failure_code="return_period_expired",
                                warnings=[f"반품 가능 기간 {period_days}일이 경과했습니다."])

        if task.capability == "return.check_eligibility":
            return self._result(task, outcome="completed", confidence=0.9, evidence=evidence,
                                answer="제공된 주문·반품 이력·정책 근거상 반품 요청을 검토할 수 있습니다.",
                                next_action=NextAction.RESPOND,
                                decisions=[{"eligible": True, "period_days": period_days}])

        order_id = str(order.get("order_id"))
        request_id = str(current.get("request_id") or task.case_id)
        if task.capability == "return.request":
            action_type = "return.request"
            arguments = {"order_id": order_id, "reason_code": reason, "return_quantity": quantity}
            decision = {"classification": "return_request_proposed", "mock_side_effect": False}
        else:
            total = order.get("total_cents")
            if not isinstance(total, int):
                return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                    next_action=NextAction.ESCALATE, failure_code="refund_calculation_evidence_missing")
            try:
                items = self.tools.call("read.order_items", task.context, {"order_id": order_id},
                                        task.allowed_tools, seen)
            except ToolLoopExceeded:
                return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                    next_action=NextAction.ESCALATE, failure_code="tool_loop_guard")

            # ★어느 품목을 반품하는가 — 반품 레코드가 밝혔으면 그것을 쓴다.
            #   없으면(옛 데이터) 다품목 주문에서는 금액을 만들지 않는다.
            returned_item = (request or {}).get("order_item_id") or current.get("order_item_id")
            outcome = self._refund_amount(items, total, int(quantity),
                                          str(returned_item) if returned_item else None)
            if outcome.failure_code is not None:
                # ★근거 없이 금액을 만들지 않는다. "환불됩니다" 를 잘못 말하면
                #   고객이 손해를 본다(`CLAUDE.md` §0). 못 구하면 사람에게 넘긴다.
                return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                    next_action=NextAction.ESCALATE, failure_code=outcome.failure_code,
                                    warnings=[outcome.reason])
            amount = outcome.amount
            action_type = "refund.calculate"
            arguments = {"order_id": order_id, "refund_amount_cents": amount, "return_quantity": quantity,
                         "calculation_basis": outcome.basis}
            decision = {"classification": "refund_calculation_proposed", "calculated_amount_cents": amount,
                        "mock_side_effect": False}
        proposal = ActionProposal(action_type=action_type, arguments=arguments,
                                  idempotency_key=idempotency_key(tenant_id=task.context.tenant_id,
                                  request_id=request_id, action_type=action_type, business_subject=str(task.case_id)),
                                  approval_required=True, risk_level="medium",
                                  rationale_evidence_ids=[item.evidence_id for item in evidence])
        return self._result(task, outcome="waiting", confidence=0.9, evidence=evidence,
                            next_action=NextAction.WAIT_FOR_APPROVAL, wait_reason="human_approval",
                            action_proposals=[proposal], decisions=[decision],
                            warnings=["Mock 단계에서는 승인 제안만 생성하며 실제 처리는 수행하지 않습니다."])


__all__ = ["ReturnRefundTeam"]
