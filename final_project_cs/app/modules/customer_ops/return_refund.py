"""Mock-only Return & Refund Team.

This module may calculate and propose actions, but it never performs a return
or refund side effect.  Approval is the boundary for every such proposal.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.contracts import ActionProposal, Evidence, NextAction, TeamManifest, TeamResult, TeamTask
from app.core.idempotency import idempotency_key
from app.tools.read_tools import ReadToolbox, ToolLoopExceeded


class ReturnRefundTeam:
    manifest = TeamManifest(
        team_id="return_refund",
        display_name="Return & Refund Team",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=["return.check_eligibility", "return.request", "refund.calculate"],
        accepted_case_types=["return", "refund", "exchange"],
        required_context=["case_state", "policy", "db_facts", "history"],
        allowed_tools=["read.order", "read.return", "read.policy"],
        knowledge_scope=["order", "return", "refund", "exchange", "policy"],
        max_steps=6,
        active=True,
        implementation_revision="2026-08-20",
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
            item_count = order.get("item_count")
            if not isinstance(total, int) or not isinstance(item_count, int) or item_count <= 0:
                return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                    next_action=NextAction.ESCALATE, failure_code="refund_calculation_evidence_missing")
            amount = total * int(quantity) // item_count
            action_type = "refund.calculate"
            arguments = {"order_id": order_id, "refund_amount_cents": amount, "return_quantity": quantity,
                         "calculation_basis": {"order_total_cents": total, "order_item_count": item_count}}
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
