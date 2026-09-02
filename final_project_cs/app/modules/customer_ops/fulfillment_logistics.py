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
        # ★"shipping" intent 는 이름으로 매칭되는 capability 가 없다 — 셋 다
        #   "shipping." 로 시작하지 않는다(fulfillment./shipment.). 지금 실제
        #   동작(capabilities[0])과 같은 값을 명시적으로 선언한다.
        default_capability="fulfillment.track",
    )

    def __init__(self, tools: ReadToolbox) -> None:
        self.tools = tools

    # ★분실·파손·지연을 분명히 밝히는 문구만 잡는다. 여기서 신호를 놓쳐도
    #   손해가 크지 않다 — execute()의 shipment.exception 경로가 실제 DB
    #   배송 상태(lost/damaged/delayed)와 다시 대조하므로, 문구가 틀리게
    #   잡혀도 근거 없는 제안은 안 나간다(그때는 shipment_exception_unconfirmed
    #   로 escalate).
    _EXCEPTION_MARKERS = (
        "파손", "손상", "훼손", "부서", "분실", "잃어버", "없어졌",
        "안 왔", "안왔", "못 받", "못받", "지연", "늦어",
    )

    # ★**"내 배송이 잘못됐다"와 "그럴 때 규칙이 뭐냐"는 다르다.** 위 낱말은
    #   둘 다에 나온다 — "배송 지연 기준을 알려 주세요"에도 "지연"이 있다.
    #   규칙을 묻는 문의까지 이상 신고로 보면 조회를 원한 고객에게 교체·재배송
    #   제안이 나간다. 2026-09-02 holdout 실측에서 실제로 2건이 그렇게 잘못
    #   잡혔다(h-shipping-02 "배송 지연 기준을 알려 주세요",
    #   h-shipping-05 "늦어질 수 있는지 미리 알고 싶습니다").
    #   애매하면 기존 기본값(fulfillment.track)으로 둔다 — 정보성 응답은
    #   되돌릴 수 있지만 잘못 나간 제안은 승인 큐를 오염시킨다.
    _INQUIRY_MARKERS = ("기준", "알려 주", "알려주", "궁금", "미리 알", "안내해")

    @staticmethod
    def select_capability(intent: str | None, input_text: str) -> str | None:
        """"shipping" intent가 일반 조회인지 배송 이상(분실·파손·지연) 신고인지 가른다.

        ★2026-09-01 — "shipping" intent는 이름으로 매칭되는 capability가
          하나도 없어 늘 fulfillment.track(주문 단위 정보성 응답)으로만
          갔다 — 실제 교체/재배송 제안이 나오는 shipment.exception 경로에
          영원히 도달 못 함
          (docs/reports/debugs/2026-09-01_capability_for_폴백이_근거없이_기능을_고른다.md).
          신호가 없으면 `None`을 돌려줘 기존 규칙(default_capability=
          fulfillment.track)에 그대로 맡긴다 — 기존 동작을 바꾸지 않는다.
        """
        if intent != "shipping":
            return None
        if any(marker in input_text for marker in FulfillmentLogisticsTeam._INQUIRY_MARKERS):
            return None  # 규칙을 묻는 문의 — 이상 신고가 아니다
        if any(marker in input_text for marker in FulfillmentLogisticsTeam._EXCEPTION_MARKERS):
            return "shipment.exception"
        return None

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
