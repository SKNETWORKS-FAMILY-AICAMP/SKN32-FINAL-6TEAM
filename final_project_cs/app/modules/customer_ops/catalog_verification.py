"""Tenant-scoped catalog lookup and order listing verification."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.contracts import Evidence, NextAction, TeamManifest, TeamResult, TeamTask
from app.core.contracts import ToolNotAllowed
from app.tools.read_tools import ReadToolbox, ToolLoopExceeded


class CatalogVerificationTeam:
    manifest = TeamManifest(
        team_id="catalog_verification",
        display_name="Catalog & Verification Team",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=["catalog.lookup_sku", "catalog.verify_listing", "catalog.compliance_check"],
        accepted_case_types=["catalog"],
        required_context=["case_state", "policy", "db_facts", "history"],
        allowed_tools=["read.catalog", "read.order_items", "read.policy"],
        knowledge_scope=["catalog"],
        max_steps=6,
        active=True,
        implementation_revision="2026-08-24",
    )

    def __init__(self, tools: ReadToolbox) -> None:
        self.tools = tools

    @staticmethod
    def _result(task: TeamTask, **kwargs: Any) -> TeamResult:
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id, **kwargs)

    @staticmethod
    def _evidence(source_id: str, claim: str, value: Any, confidence: float = 1.0) -> Evidence:
        return Evidence(evidence_id=f"tool:catalog_verification:{source_id}", source_type="tool_result",
                         source_id=source_id, claim=claim, value=value, confidence=confidence,
                         observed_at=datetime.now(UTC))

    @staticmethod
    def _sku(state: dict[str, Any]) -> str | None:
        value = state.get("sku") or state.get("product_sku") or state.get("claimed_sku")
        return str(value) if value is not None else None

    @staticmethod
    def _claimed_name(state: dict[str, Any]) -> str | None:
        value = state.get("product_name") or state.get("name") or state.get("claimed_product_name")
        return str(value) if value is not None else None

    async def execute(self, task: TeamTask) -> TeamResult:
        evidence = list(task.context.evidence)
        if task.capability not in self.manifest.capabilities:
            return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                next_action=NextAction.ESCALATE, failure_code="unsupported_capability")
        if task.context.degraded:
            return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                next_action=NextAction.ESCALATE, failure_code="degraded_context")

        if task.capability == "catalog.compliance_check":
            evidence.append(self._evidence(
                "catalog.compliance_check",
                "컴플라이언스 데이터가 없어 확인할 수 없음",
                {"available": False, "reason": "compliance_data_unavailable"},
                confidence=1.0,
            ))
            return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                next_action=NextAction.ESCALATE,
                                failure_code="compliance_data_unavailable",
                                warnings=["컴플라이언스 데이터가 아직 없어 확인할 수 없습니다"])

        seen: set[str] = set()
        try:
            if task.capability == "catalog.lookup_sku":
                sku = self._sku(task.context.current_state)
                if sku is None:
                    return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                        next_action=NextAction.ESCALATE, failure_code="sku_missing")
                product = self.tools.call("read.catalog", task.context, {"sku": sku}, task.allowed_tools, seen)
                evidence.append(self._evidence("read.catalog", "tenant-scoped SKU catalog lookup", product))
                if product is None:
                    return self._result(task, outcome="completed", confidence=1.0, evidence=evidence,
                                        answer=f"SKU {sku}를 카탈로그에서 찾을 수 없습니다.",
                                        next_action=NextAction.RESPOND,
                                        decisions=[{"classification": "sku_not_found", "sku": sku}])
                return self._result(task, outcome="completed", confidence=1.0, evidence=evidence,
                                    answer=f"SKU {sku}의 카탈로그 정보를 확인했습니다.",
                                    next_action=NextAction.RESPOND,
                                    decisions=[{"classification": "sku_found", "product": product}])

            state = task.context.current_state
            order_id = state.get("order_id")
            items = self.tools.call("read.order_items", task.context,
                                    {"order_id": str(order_id)} if order_id else {},
                                    task.allowed_tools, seen)
            claimed_sku = self._sku(state)
            claimed_name = self._claimed_name(state)
            evidence.append(self._evidence("read.order_items", "customer-owned order line items", items))
            if not isinstance(items, list) or not items or (claimed_sku is None and claimed_name is None):
                return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                    next_action=NextAction.ESCALATE,
                                    failure_code="listing_verification_evidence_missing")
            matches = [item for item in items if isinstance(item, dict) and
                       (claimed_sku is None or str(item.get("sku")) == claimed_sku) and
                       (claimed_name is None or str(item.get("name")) == claimed_name)]
            decision = {"claimed_sku": claimed_sku, "claimed_name": claimed_name,
                        "matched": bool(matches), "order_items": items}
            if matches:
                return self._result(task, outcome="completed", confidence=1.0, evidence=evidence,
                                    answer="고객이 주장한 상품/SKU가 주문 라인아이템과 일치합니다.",
                                    decisions=[decision], next_action=NextAction.RESPOND)
            return self._result(task, outcome="escalated", confidence=1.0, evidence=evidence,
                                decisions=[decision], next_action=NextAction.ESCALATE,
                                failure_code="listing_mismatch",
                                warnings=["고객 주장과 주문 라인아이템이 일치하지 않아 사람의 확인이 필요합니다"])
        except (ToolLoopExceeded, ToolNotAllowed, ValueError):
            return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                next_action=NextAction.ESCALATE, failure_code="read_tool_failed")


__all__ = ["CatalogVerificationTeam"]
