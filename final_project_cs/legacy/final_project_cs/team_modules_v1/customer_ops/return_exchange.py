"""Return/Exchange Team: diagnose and propose return handling only.

★sample(구독·결제) 의 `TechnicalEntitlementTeam` 을 커머스로 갈아 끼운 것이다.
  시나리오2 — 주문 수량보다 많은 반품 요청.

★이 Team 은 수량이 상한을 넘는지 **스스로 판단해 막지 않는다.** 요청을 있는 그대로
  제안하고, 실재·수량 대조는 Controller(`app/application/proposal_guard.py`)가
  실행 직전에 한다 (v7 §9-E, DoD-24). 방어를 Team 의 선의에 맡기지 않는다 —
  Team 이 검사를 빼먹어도 Controller 가 막는다는 것이 이 시스템의 설계다.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.core.contracts import ActionProposal, Evidence, NextAction, TeamManifest, TeamResult, TeamTask
from app.core.idempotency import idempotency_key
from app.tools.read_tools import ReadToolbox, ToolLoopExceeded


EXCHANGE_REASON_CODES = frozenset({"size_mismatch", "color_mismatch", "wrong_option"})


class ReturnExchangeTeam:
    manifest = TeamManifest(
        team_id="return_exchange", display_name="Return/Exchange Team", contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=["return.diagnose", "return.propose_action"],
        accepted_case_types=["return", "exchange"],
        required_context=["case_state", "policy", "db_facts", "history"],
        allowed_tools=["read.order", "read.return", "read.policy"],
        knowledge_scope=["return", "exchange", "order"],
        max_steps=6, active=True, implementation_revision="2026-08-17",
    )

    def __init__(self, tools: ReadToolbox, llm: Any | None = None) -> None:
        self.tools, self.llm = tools, llm

    async def _llm_answer(self, task: TeamTask, evidence: list[Evidence]) -> str | None:
        context = {"evidence": evidence, "context": task.context.model_dump(mode="json")}
        response = await self.llm.complete("return_exchange.answer", task.input_text, context, run_id=task.run_id)
        answer = self._answer_from_response(response)
        if answer is not None:
            return answer
        repaired = await self.llm.complete(
            "return_exchange.answer.repair", task.input_text,
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
        if task.context.degraded:
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                              outcome="escalated", confidence=0.0, next_action=NextAction.ESCALATE,
                              failure_code="degraded_context",
                              warnings=["정책 근거가 불완전하여 확정 답변을 만들지 않음"])
        seen: set[str] = set()
        try:
            order = self.tools.call("read.order", task.context, {}, task.allowed_tools, seen)
            returns = self.tools.call("read.return", task.context, {}, task.allowed_tools, seen)
            policy = self.tools.call("read.policy", task.context, {"query": task.input_text}, task.allowed_tools, seen)
        except ToolLoopExceeded:
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                              outcome="escalated", confidence=0.0, next_action=NextAction.ESCALATE,
                              failure_code="tool_loop_guard")
        evidence = list(task.context.evidence)
        if not policy:
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                              outcome="escalated", confidence=0.0, evidence=evidence,
                              next_action=NextAction.ESCALATE, failure_code="policy_not_found")
        evidence.append(Evidence(
            evidence_id="tool:return_exchange", source_type="tool_result", source_id="read.return_exchange",
            claim="주문과 반품 요청 이력을 대조했다", value={"order": order, "returns": returns, "policy": policy},
            confidence=1.0,
            observed_at=evidence[0].observed_at if evidence
            else __import__("datetime").datetime.now(__import__("datetime").UTC)))

        pending = [r for r in returns if r.get("status") == "requested"]
        # ★수량이 주문을 넘는지는 여기서 참고만 한다 — **차단은 Controller 가 한다.**
        over_requested = order and pending and any(
            (r.get("quantity") or 0) > (order.get("item_count") or 0) for r in pending)

        if pending and order:
            latest = pending[0]
            ordered_at = order.get("ordered_at")
            if isinstance(ordered_at, str):
                try:
                    ordered_at = datetime.fromisoformat(ordered_at.replace("Z", "+00:00"))
                except ValueError:
                    ordered_at = None
            if isinstance(ordered_at, datetime) and ordered_at.tzinfo is not None:
                elapsed_days = (datetime.now(UTC) - ordered_at.astimezone(UTC)).days
                period_days = 90 if latest.get("reason_code") == "defective" else 7
                if elapsed_days > period_days:
                    return TeamResult(
                        task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                        outcome="escalated", confidence=0.85, evidence=evidence,
                        next_action=NextAction.ESCALATE, failure_code="return_period_expired",
                        warnings=["반품 기한(7일/하자 90일)을 넘겨 접수됨 — 고지 누락 등 예외 사유 확인이 먼저 필요함"],
                    )
            request_id = str(task.context.current_state.get("request_id") or task.case_id)
            is_exchange = latest.get("reason_code") in EXCHANGE_REASON_CODES
            action_type = "exchange.request" if is_exchange else "return.accept"
            classification = (
                "exchange_requested" if is_exchange
                else ("return_quantity_exceeds_order" if over_requested else "return_requested")
            )
            if is_exchange:
                evidence.append(Evidence(
                    evidence_id="policy:exchange_stock_unverified", source_type="policy",
                    source_id="doc_15#재고 확인의 선행",
                    claim="이 시스템은 실시간 재고 데이터가 없어 교환 대상 옵션의 재고를 자동으로 확인하지 못한다 — 승인자가 재고를 직접 확인해야 한다",
                    value={}, confidence=1.0,
                    observed_at=evidence[0].observed_at if evidence
                    else __import__("datetime").datetime.now(__import__("datetime").UTC)))
            proposal = ActionProposal(
                action_type=action_type,
                # ★필드 이름이 verification_policy.CUSTOMER_OPS_POLICY 의 quantities 규칙과
                #   일치해야 Controller 가 주문 수량 상한을 대조할 수 있다.
                arguments={"order_id": str(order["order_id"]), "return_quantity": latest.get("quantity")},
                idempotency_key=idempotency_key(tenant_id=task.context.tenant_id, request_id=request_id,
                                                action_type=action_type, business_subject=str(task.case_id)),
                approval_required=True, risk_level="high" if (is_exchange or over_requested) else "medium",
                rationale_evidence_ids=[e.evidence_id for e in evidence],
            )
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                              outcome="waiting", confidence=0.85, evidence=evidence,
                              next_action=NextAction.WAIT_FOR_APPROVAL, wait_reason="human_approval",
                              action_proposals=[proposal],
                              decisions=[{"classification": classification}])

        answer = "주문과 반품 요청 이력을 확인했고 정책 근거에 따라 절차를 안내합니다."
        if self.llm is not None:
            answer = await self._llm_answer(task, evidence)
            if answer is None:
                return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                                  outcome="failed", confidence=0.0, evidence=evidence,
                                  next_action=NextAction.ESCALATE, failure_code="malformed_llm_response",
                                  warnings=["LLM 응답이 TeamResult answer 스키마와 일치하지 않음"])
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                          outcome="completed", confidence=0.8, answer=answer, evidence=evidence,
                          next_action=NextAction.RESPOND, decisions=[{"side_effects": []}])


__all__ = ["ReturnExchangeTeam"]
