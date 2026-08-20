"""Fulfillment and logistics Team: inspect delivery facts and propose actions only."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.contracts import ActionProposal, Evidence, NextAction, TeamManifest, TeamModule, TeamResult, TeamTask, ToolNotAllowed
from app.core.idempotency import idempotency_key
from app.tools.read_tools import ReadToolbox, ToolLoopExceeded


class FulfillmentLogisticsTeam:
    manifest = TeamManifest(
        team_id="fulfillment_logistics", display_name="Fulfillment & Logistics Team",
        contract_name="a_cop.team_task", supported_contract_versions=["1.0"],
        capabilities=["fulfillment.track", "shipment.status", "shipment.exception"],
        accepted_case_types=["fulfillment", "shipping", "shipment"],
        required_context=["case_state", "policy", "db_facts", "history"],
        allowed_tools=["read.order", "read.shipment", "read.policy"],
        knowledge_scope=["order", "shipping", "warehouse", "delivery_exception"],
        max_steps=6, active=True, implementation_revision="2026-08-20",
    )

    def __init__(self, tools: ReadToolbox) -> None:
        self.tools = tools

    @staticmethod
    def _evidence(name: str, value: Any) -> Evidence:
        return Evidence(evidence_id=f"tool:fulfillment_logistics:{name}", source_type="tool_result",
                         source_id=name, claim=f"{name} read result", value=value, confidence=1.0,
                         observed_at=datetime.now(UTC))

    def _read(self, task: TeamTask, name: str, seen: set[str]) -> Any:
        return self.tools.call(name, task.context, {}, task.allowed_tools, seen)

    @staticmethod
    def _result(task: TeamTask, evidence: list[Evidence], **kwargs: Any) -> TeamResult:
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id="fulfillment_logistics",
                          evidence=evidence, **kwargs)

    def _escalate(self, task: TeamTask, evidence: list[Evidence], code: str) -> TeamResult:
        return self._result(task, evidence, outcome="escalated", confidence=0.0,
                            next_action=NextAction.ESCALATE, failure_code=code,
                            warnings=["배송 provider 상태를 확인할 근거가 부족하여 unknown으로 남김"])

    async def execute(self, task: TeamTask) -> TeamResult:
        if task.capability not in self.manifest.capabilities:
            return self._escalate(task, list(task.context.evidence), "unsupported_capability")
        if task.context.degraded:
            return self._escalate(task, list(task.context.evidence), "degraded_context")

        seen: set[str] = set()
        evidence = list(task.context.evidence)
        try:
            if task.capability == "fulfillment.track":
                order = self._read(task, "read.order", seen)
                shipments = self._read(task, "read.shipment", seen)
                evidence += [self._evidence("read.order", order), self._evidence("read.shipment", shipments)]
                if not isinstance(order, dict):
                    return self._escalate(task, evidence, "fulfillment_data_unavailable")
                phase = order.get("fulfillment_status") or order.get("status")
                if not phase:
                    return self._escalate(task, evidence, "fulfillment_status_unknown")
                count = len(shipments) if isinstance(shipments, list) else 0
                return self._result(task, evidence, outcome="completed", confidence=0.9,
                                    answer=f"주문 이행 상태는 {phase}입니다. 조회된 배송 건은 {count}건입니다.",
                                    decisions=[{"classification": "fulfillment_status", "status": phase,
                                                "shipment_count": count}], next_action=NextAction.RESPOND)

            shipments = self._read(task, "read.shipment", seen)
            evidence.append(self._evidence("read.shipment", shipments))
            if not isinstance(shipments, list) or not shipments:
                return self._escalate(task, evidence, "shipment_status_unknown")
            shipment = shipments[0]
            status = shipment.get("status") if isinstance(shipment, dict) else None
            if not status or str(status).lower() in {"unknown", "unavailable"}:
                return self._escalate(task, evidence, "shipment_status_unknown")

            if task.capability == "shipment.status":
                return self._result(task, evidence, outcome="completed", confidence=0.9,
                                    answer=f"배송 상태는 {status}입니다.",
                                    decisions=[{"classification": "shipment_status", "status": status,
                                                "shipment_id": shipment.get("shipment_id")}],
                                    next_action=NextAction.RESPOND)

            normalized = str(status).lower()
            action_type = {"lost": "shipment.replace", "damaged": "shipment.replace",
                           "delayed": "shipment.reroute"}.get(normalized)
            shipment_id = shipment.get("shipment_id")
            if action_type is None:
                return self._escalate(task, evidence, "shipment_exception_unconfirmed")
            if not shipment_id:
                return self._escalate(task, evidence, "shipment_identity_unknown")
            request_id = str(task.context.current_state.get("request_id") or task.case_id)
            proposal = ActionProposal(
                action_type=action_type, arguments={"shipment_id": str(shipment_id), "reason": normalized},
                idempotency_key=idempotency_key(tenant_id=task.context.tenant_id, request_id=request_id,
                                                action_type=action_type, business_subject=str(shipment_id)),
                approval_required=True, risk_level="medium",
                rationale_evidence_ids=[item.evidence_id for item in evidence],
            )
            return self._result(task, evidence, outcome="waiting", confidence=0.9,
                                decisions=[{"classification": f"shipment_{normalized}",
                                            "shipment_id": str(shipment_id)}], action_proposals=[proposal],
                                next_action=NextAction.WAIT_FOR_APPROVAL, wait_reason="human_approval")
        except (ToolLoopExceeded, ToolNotAllowed, ValueError):
            return self._escalate(task, evidence, "read_tool_failed")


__all__ = ["FulfillmentLogisticsTeam", "TeamModule"]
