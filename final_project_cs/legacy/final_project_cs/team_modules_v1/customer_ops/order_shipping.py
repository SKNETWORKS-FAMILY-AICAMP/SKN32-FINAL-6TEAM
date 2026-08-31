"""Order/Shipping Team: read, investigate, and propose only.

★sample(구독·결제) 의 `BillingSubscriptionTeam` 을 커머스로 갈아 끼운 것이다.
  시나리오1 — 배송완료로 찍혔는데 고객이 받지 못했다 → 조사 → 환불 제안.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from app.core.contracts import ActionProposal, Evidence, NextAction, TeamManifest, TeamModule, TeamResult, TeamTask
from app.core.idempotency import idempotency_key
from app.tools.read_tools import ReadToolbox, ToolLoopExceeded


class LLM(Protocol):
    async def complete(self, prompt_key: str, input_text: str, context: dict[str, Any], *, run_id: UUID | None = None) -> dict[str, Any]: ...


def _business_days_since(start: datetime, now: datetime) -> int:
    """Count weekdays after start through now, without a holiday calendar."""
    start = start.astimezone(UTC)
    now = now.astimezone(UTC)
    day = start.date() + timedelta(days=1)
    days = 0
    while day <= now.date():
        if day.weekday() < 5:
            days += 1
        day += timedelta(days=1)
    return days


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else None
    return None


class OrderShippingTeam:
    manifest = TeamManifest(
        team_id="order_shipping", display_name="Order/Shipping Team", contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=["order.investigate", "refund.propose"],
        accepted_case_types=["order", "shipping"],
        required_context=["case_state", "policy", "db_facts", "history"],
        allowed_tools=["read.order", "read.shipment", "read.policy"],
        knowledge_scope=["order", "shipping", "refund"],
        max_steps=6, active=True, implementation_revision="2026-08-17",
    )

    def __init__(self, tools: ReadToolbox, llm: LLM | None = None) -> None:
        self.tools, self.llm = tools, llm

    def _evidence(self, task: TeamTask, facts: list[Any]) -> list[Evidence]:
        evidence = list(task.context.evidence)
        if facts:
            evidence.append(Evidence(evidence_id="tool:order_shipping", source_type="tool_result",
                                     source_id="read.order_shipping", claim="주문 및 배송 이력을 조회했다",
                                     value=facts, confidence=1.0,
                                     observed_at=evidence[0].observed_at if evidence
                                     else __import__("datetime").datetime.now(__import__("datetime").UTC)))
        return evidence

    async def _llm_answer(self, task: TeamTask, evidence: list[Evidence]) -> str | None:
        context = {"evidence": evidence, "context": task.context.model_dump(mode="json")}
        response = await self.llm.complete("order_shipping.answer", task.input_text, context, run_id=task.run_id)
        answer = self._answer_from_response(response)
        if answer is not None:
            return answer
        repaired = await self.llm.complete(
            "order_shipping.answer.repair", task.input_text,
            {**context, "invalid_response": response,
             "repair_instruction": "Return a JSON object with a non-empty string answer field only."},
            run_id=task.run_id,
        )
        return self._answer_from_response(repaired)

    @staticmethod
    def _answer_from_response(response: Any) -> str | None:
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except json.JSONDecodeError:
                return None
        if not isinstance(response, dict):
            return None
        answer = response.get("answer")
        return answer.strip() if isinstance(answer, str) and answer.strip() else None

    async def execute(self, task: TeamTask) -> TeamResult:
        if task.team_id != self.manifest.team_id:
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                              outcome="handoff", confidence=1.0, next_action=NextAction.HANDOFF,
                              handoff_capability="order.investigate")
        if task.context.degraded:
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                              outcome="escalated", confidence=0.0, next_action=NextAction.ESCALATE,
                              failure_code="degraded_context",
                              warnings=["정책 근거가 불완전하여 확정 답변을 만들지 않음"])
        seen: set[str] = set()
        try:
            order = self.tools.call("read.order", task.context, {}, task.allowed_tools, seen)
            shipments = self.tools.call("read.shipment", task.context, {}, task.allowed_tools, seen)
            policy = self.tools.call("read.policy", task.context, {"query": task.input_text}, task.allowed_tools, seen)
        except ToolLoopExceeded:
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                              outcome="escalated", confidence=0.0, next_action=NextAction.ESCALATE,
                              failure_code="tool_loop_guard")
        evidence = self._evidence(task, [order, shipments, policy])
        if not policy:
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                              outcome="escalated", confidence=0.0, evidence=evidence,
                              next_action=NextAction.ESCALATE, failure_code="policy_not_found")

        request_id = str(task.context.current_state.get("request_id") or task.case_id)
        issue_code = task.context.current_state.get("issue_code")
        order_status = (order or {}).get("status")
        if issue_code == "order_change_or_cancel" and order:
            if order_status in ("placed", "paid"):
                proposal = ActionProposal(
                    action_type="order.cancel",
                    arguments={"order_id": str(order["order_id"])},
                    idempotency_key=idempotency_key(
                        tenant_id=task.context.tenant_id, request_id=request_id,
                        action_type="order.cancel", business_subject=str(task.case_id)),
                    approval_required=True, risk_level="medium",
                    rationale_evidence_ids=[e.evidence_id for e in evidence],
                )
                return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                                  outcome="waiting", confidence=0.85, evidence=evidence,
                                  next_action=NextAction.WAIT_FOR_APPROVAL, wait_reason="human_approval",
                                  action_proposals=[proposal],
                                  decisions=[{"classification": "cancel_before_shipment"}])
            if order_status in ("shipped", "delivered"):
                # 출고 후 취소는 반품 절차이므로 임의 접수하지 않고 기존 정책/LLM 경로로 넘긴다.
                pass

        # ★시나리오1 — 배송이 완료로 찍혔는데(운송장 표시) 고객이 못 받았다는 문의가 왔다.
        #   DB 만으로는 "고객이 못 받았다" 를 알 수 없다 — 그건 문의 내용이다.
        #   여기서는 **배송 완료 표시가 있다는 사실**까지만 확인하고, 조사·환불은 제안까지만 한다.
        delayed_shipment = next(
            (shipment for shipment in shipments
             if shipment.get("status") != "delivered" and shipment.get("shipped_at")),
            None,
        )
        shipped_at = _parse_datetime(delayed_shipment.get("shipped_at")) if delayed_shipment else None
        if shipped_at is not None and _business_days_since(shipped_at, datetime.now(UTC)) >= 5 and order:
            action_type = "shipping.delay_compensation_propose"
            proposal = ActionProposal(
                action_type=action_type,
                arguments={"order_id": str(order["order_id"])},
                idempotency_key=idempotency_key(
                    tenant_id=task.context.tenant_id, request_id=request_id,
                    action_type=action_type, business_subject=str(task.case_id)),
                approval_required=True, risk_level="medium",
                rationale_evidence_ids=[e.evidence_id for e in evidence],
            )
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                              outcome="waiting", confidence=0.85, evidence=evidence,
                              next_action=NextAction.WAIT_FOR_APPROVAL, wait_reason="human_approval",
                              action_proposals=[proposal],
                              decisions=[{"classification": "shipping_delay_compensation_review"}])

        delivered = any(s.get("status") == "delivered" for s in shipments)
        if delivered and order:
            proposal = ActionProposal(
                action_type="refund.request",
                # ★필드 이름이 verification_policy.CUSTOMER_OPS_POLICY 의 선언과 일치해야
                #   Controller 가 실재·상한을 대조할 수 있다 (v7 §9-E).
                arguments={"order_id": str(order["order_id"])},
                idempotency_key=idempotency_key(tenant_id=task.context.tenant_id, request_id=request_id,
                                                action_type="refund.request", business_subject=str(task.case_id)),
                approval_required=True, risk_level="high",
                rationale_evidence_ids=[e.evidence_id for e in evidence],
            )
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                              outcome="waiting", confidence=0.9, evidence=evidence,
                              next_action=NextAction.WAIT_FOR_APPROVAL, wait_reason="human_approval",
                              action_proposals=[proposal],
                              decisions=[{"classification": "delivered_but_not_received"}])

        answer = "주문과 배송 이력을 확인했습니다. 정책 근거를 바탕으로 안내할 수 있습니다."
        if self.llm is not None:
            answer = await self._llm_answer(task, evidence)
            if answer is None:
                return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                                  outcome="failed", confidence=0.0, evidence=evidence,
                                  next_action=NextAction.ESCALATE, failure_code="malformed_llm_response",
                                  warnings=["LLM 응답이 TeamResult answer 스키마와 일치하지 않음"])
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                          outcome="completed", confidence=0.8, answer=answer, evidence=evidence,
                          next_action=NextAction.RESPOND)


__all__ = ["OrderShippingTeam", "TeamModule"]
