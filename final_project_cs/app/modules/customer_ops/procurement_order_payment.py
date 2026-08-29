"""Procurement, order, and payment read/proposal Team.

This module deliberately stops at verifiable facts and ``ActionProposal``
objects.  It does not create orders or call a payment provider.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.contracts import (
    ActionProposal,
    Evidence,
    NextAction,
    TeamManifest,
    TeamModule,
    TeamResult,
    TeamTask,
)
from app.core.idempotency import idempotency_key
from app.tools.read_tools import ReadToolbox, ToolLoopExceeded


class ProcurementOrderPaymentTeam:
    manifest = TeamManifest(
        team_id="procurement_order_payment",
        display_name="Procurement + Order & Payment Team",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=[
            "procurement.quote", "order.verify", "order.create", "order.modify", "order.cancel", "payment.status",
        ],
        accepted_case_types=["procurement", "order", "payment"],
        required_context=["case_state", "policy", "db_facts", "history"],
        allowed_tools=["read.order", "read.account", "read.policy", "read.catalog"],
        knowledge_scope=["catalog", "pricing", "order", "payment", "procurement"],
        max_steps=6,
        active=True,
        implementation_revision="2026-08-20",
    )

    def __init__(self, tools: ReadToolbox) -> None:
        self.tools = tools

    @staticmethod
    def _result(task: TeamTask, **kwargs: Any) -> TeamResult:
        return TeamResult(
            task_id=task.task_id,
            run_id=task.run_id,
            team_id=task.team_id,
            **kwargs,
        )

    @staticmethod
    def _evidence(task: TeamTask, *, source_id: str, claim: str, value: Any) -> list[Evidence]:
        evidence = list(task.context.evidence)
        if value is not None and value != {} and value != []:
            evidence.append(
                Evidence(
                    evidence_id=f"tool:procurement_order_payment:{source_id}",
                    source_type="tool_result" if source_id.startswith("read.") else "db",
                    source_id=source_id,
                    claim=claim,
                    value=value,
                    confidence=1.0,
                    observed_at=datetime.now(UTC),
                )
            )
        return evidence

    @staticmethod
    def _escalate(task: TeamTask, code: str, evidence: list[Evidence] | None = None) -> TeamResult:
        return ProcurementOrderPaymentTeam._result(
            task,
            outcome="escalated",
            confidence=0.0,
            evidence=evidence or [],
            next_action=NextAction.ESCALATE,
            failure_code=code,
        )

    def _read(self, task: TeamTask, name: str, arguments: dict[str, Any], seen: set[str]) -> Any:
        return self.tools.call(name, task.context, arguments, task.allowed_tools, seen)

    def _proposal(self, task: TeamTask, action_type: str, arguments: dict[str, Any], evidence: list[Evidence], risk: str = "high") -> ActionProposal:
        request_id = str(task.context.current_state.get("request_id") or task.case_id)
        subject = str(arguments.get("order_id") or arguments.get("customer_id") or task.case_id)
        return ActionProposal(
            action_type=action_type,
            arguments=arguments,
            idempotency_key=idempotency_key(
                tenant_id=task.context.tenant_id,
                request_id=request_id,
                action_type=action_type,
                business_subject=subject,
            ),
            approval_required=True,
            risk_level=risk,
            rationale_evidence_ids=[item.evidence_id for item in evidence],
        )

    @staticmethod
    def _order_status(order: Any) -> str | None:
        if not isinstance(order, dict):
            return None
        for key in ("fulfillment_status", "shipment_status", "status"):
            value = order.get(key)
            if value is not None and str(value).strip():
                return str(value).strip().lower()
        return None

    @staticmethod
    def _is_pre_shipment(status: str | None) -> bool | None:
        if status is None:
            return None
        if status in {"shipped", "dispatched", "in_transit", "warehouse_transferred", "delivered",
                      "출고완료", "배송중", "배송완료", "물류센터전달"}:
            return False
        if status in {"paid", "payment_completed", "preparing", "processing", "ready_to_ship",
                      "출고전", "결제완료", "상품준비중", "배송준비중"}:
            return True
        return None

    async def execute(self, task: TeamTask) -> TeamResult:
        if task.team_id != self.manifest.team_id:
            return self._result(task, outcome="handoff", confidence=1.0,
                                next_action=NextAction.HANDOFF,
                                handoff_capability=task.capability)
        if task.capability not in self.manifest.capabilities:
            return self._escalate(task, "unsupported_capability")
        if task.context.degraded:
            return self._escalate(task, "degraded_context")

        seen: set[str] = set()
        evidence = list(task.context.evidence)
        try:
            if task.capability == "procurement.quote":
                policy = self._read(task, "read.policy", {"query": task.input_text}, seen)
                pricing = task.context.current_state.get("pricing") or task.context.current_state.get("price")
                catalog_product = None
                if pricing is None:
                    sku = (task.context.current_state.get("sku")
                           or task.context.current_state.get("product_sku"))
                    if sku is None:
                        return self._escalate(task, "quote_sku_missing", evidence)
                    catalog_product = self._read(task, "read.catalog", {"sku": str(sku)}, seen)
                    if (not isinstance(catalog_product, dict)
                            or catalog_product.get("status") != "active"):
                        return self._escalate(
                            task,
                            "quote_catalog_product_missing",
                            self._evidence(task, source_id="read.catalog",
                                           claim="tenant-scoped active catalog product lookup",
                                           value=catalog_product),
                        )
                    pricing = {str(sku): catalog_product["unit_cents"]}
                evidence = self._evidence(task, source_id="read.policy",
                                           claim="procurement quote policy and pricing basis",
                                           value={"policy": policy, "pricing": pricing,
                                                  "catalog": catalog_product})
                if not evidence:
                    return self._escalate(task, "quote_evidence_missing")
                quote = pricing if pricing is not None else policy
                return self._result(task, outcome="completed", answer=f"Quote basis: {quote}",
                                    confidence=0.8, evidence=evidence,
                                    next_action=NextAction.RESPOND,
                                    decisions=[{"classification": "procurement_quote", "quote": quote}])

            if task.capability == "order.verify":
                order = self._read(task, "read.order", {}, seen)
                evidence = self._evidence(task, source_id="read.order",
                                           claim="order record retrieved from the tenant-scoped database",
                                           value=order)
                if not evidence:
                    return self._escalate(task, "order_evidence_missing")
                requested = task.context.current_state.get("order_id") or task.context.current_state.get("order_no")
                matches = bool(order) and (requested is None or str(requested) in {
                    str(order.get("order_id")), str(order.get("order_no"))
                })
                return self._result(task, outcome="completed",
                                    answer="Order verified against the local order record." if matches else "No matching local order record was found.",
                                    confidence=0.9 if matches else 0.7, evidence=evidence,
                                    next_action=NextAction.RESPOND,
                                    decisions=[{"classification": "order_verification", "matched": matches,
                                                "order": order}])

            if task.capability == "order.create":
                evidence = list(task.context.evidence)
                if not evidence:
                    return self._escalate(task, "order_create_evidence_missing")
                arguments = dict(task.context.current_state.get("order_draft") or {})
                if not arguments:
                    arguments = {"request": task.input_text}
                proposal = self._proposal(task, "order.create", arguments, evidence)
                return self._result(task, outcome="waiting", confidence=0.8, evidence=evidence,
                                    next_action=NextAction.WAIT_FOR_APPROVAL,
                                    wait_reason="human_approval", action_proposals=[proposal],
                                    decisions=[{"classification": "order_creation_proposal"}])

            if task.capability in {"order.modify", "order.cancel"}:
                order = self._read(task, "read.order", {}, seen)
                evidence = self._evidence(
                    task, source_id="read.order",
                    claim="order record and fulfillment state retrieved from the tenant-scoped database",
                    value=order,
                )
                if not isinstance(order, dict) or not order:
                    return self._escalate(task, "order_change_evidence_missing", evidence)
                order_id = order.get("order_id") or order.get("order_no")
                status = self._order_status(order)
                if not order_id or status is None:
                    return self._escalate(task, "order_change_state_unknown", evidence)

                current = task.context.current_state
                if task.capability == "order.modify":
                    if self._is_pre_shipment(status) is not True:
                        return self._escalate(task, "order_modify_after_shipment", evidence)
                    changes = (current.get("order_change") or current.get("requested_changes")
                               or current.get("change_request"))
                    if not changes:
                        return self._escalate(task, "order_modify_request_missing", evidence)
                    arguments = {"order_id": str(order_id), "changes": changes,
                                 "fulfillment_status": status}
                    proposal = self._proposal(task, "order.modify", arguments, evidence, risk="medium")
                    return self._result(task, outcome="waiting", confidence=0.9, evidence=evidence,
                                        next_action=NextAction.WAIT_FOR_APPROVAL,
                                        wait_reason="human_approval", action_proposals=[proposal],
                                        decisions=[{"classification": "order_modification_proposal",
                                                    "order_id": str(order_id), "fulfillment_status": status}])

                scope = current.get("cancellation_scope") or current.get("cancel_scope")
                if scope is None:
                    scope = "partial" if current.get("cancel_quantity") is not None else "full"
                if scope not in {"full", "partial"}:
                    return self._escalate(task, "order_cancel_scope_unknown", evidence)
                seller_fault = current.get("seller_fault", order.get("seller_fault"))
                warehouse_handoff = current.get("warehouse_handoff", order.get("warehouse_handoff"))
                if seller_fault is None or warehouse_handoff is None:
                    return self._escalate(task, "order_cancel_basis_missing", evidence)
                arguments = {
                    "order_id": str(order_id), "scope": scope,
                    "reason": current.get("cancellation_reason") or current.get("cancel_reason") or "customer_request",
                    "seller_fault": bool(seller_fault), "warehouse_handoff": bool(warehouse_handoff),
                    "fulfillment_status": status,
                }
                risk = "high" if bool(seller_fault) or bool(warehouse_handoff) else "medium"
                proposal = self._proposal(task, "order.cancel", arguments, evidence, risk=risk)
                return self._result(task, outcome="waiting", confidence=0.9, evidence=evidence,
                                    next_action=NextAction.WAIT_FOR_APPROVAL,
                                    wait_reason="human_approval", action_proposals=[proposal],
                                    decisions=[{"classification": "order_cancellation_proposal",
                                                "order_id": str(order_id), "scope": scope,
                                                "seller_fault": bool(seller_fault),
                                                "warehouse_handoff": bool(warehouse_handoff)}])

            payment = task.context.current_state.get("payment") or task.context.current_state.get("payment_status")
            if payment is None:
                db_facts = task.context.current_state.get("db_facts", {})
                payment = db_facts.get("payment") if isinstance(db_facts, dict) else None
            evidence = self._evidence(task, source_id="payment.status",
                                       claim="payment status supplied by the local context/database facts",
                                       value=payment)
            if not evidence:
                return self._escalate(task, "payment_status_evidence_missing")
            return self._result(task, outcome="completed",
                                answer=f"Current payment status: {payment}", confidence=0.9,
                                evidence=evidence, next_action=NextAction.RESPOND,
                                decisions=[{"classification": "payment_status", "status": payment}])
        except ToolLoopExceeded:
            return self._escalate(task, "tool_loop_guard", evidence)


__all__ = ["ProcurementOrderPaymentTeam", "TeamModule"]
