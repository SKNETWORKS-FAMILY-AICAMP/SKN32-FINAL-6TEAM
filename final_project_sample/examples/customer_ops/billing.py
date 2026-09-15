"""Billing/Subscription Team: read, explain, and propose only."""
from __future__ import annotations

import json
from typing import Any, Protocol

from acop_basement.core.contracts import ActionProposal, Evidence, NextAction, TeamManifest, TeamModule, TeamResult, TeamTask
from acop_basement.core.idempotency import idempotency_key
from acop_basement.tools.read_tools import ReadToolbox, ToolLoopExceeded


class LLM(Protocol):
    async def complete(self, prompt_key: str, input_text: str, context: dict[str, Any]) -> dict[str, Any]: ...


class BillingSubscriptionTeam:
    manifest = TeamManifest(team_id="billing_subscription", display_name="Billing/Subscription Team", contract_name="a_cop.team_task", supported_contract_versions=["1.0"], capabilities=["billing.investigate", "billing.refund_propose", "subscription.explain"], accepted_case_types=["billing"], required_context=["case_state", "policy", "db_facts", "history"], allowed_tools=["read.subscription", "read.payment_history", "read.policy"], knowledge_scope=["billing", "subscription", "refund"], max_steps=6, active=True, implementation_revision="2026-08-12")

    def __init__(self, tools: ReadToolbox, llm: LLM | None = None) -> None:
        self.tools, self.llm = tools, llm

    def _evidence(self, task: TeamTask, facts: list[Any]) -> list[Evidence]:
        evidence = list(task.context.evidence)
        if facts:
            evidence.append(Evidence(evidence_id="tool:billing", source_type="tool_result", source_id="read.billing", claim="援щ룆 諛?寃곗젣 ?대젰??議고쉶?덈떎", value=facts, confidence=1.0, observed_at=evidence[0].observed_at if evidence else __import__("datetime").datetime.now(__import__("datetime").UTC)))
        return evidence

    async def _llm_answer(self, task: TeamTask, evidence: list[Evidence]) -> str | None:
        context = {"evidence": evidence, "context": task.context.model_dump(mode="json")}
        response = await self.llm.complete("billing.answer", task.input_text, context)
        answer = self._answer_from_response(response)
        if answer is not None:
            return answer
        repaired = await self.llm.complete(
            "billing.answer.repair",
            task.input_text,
            {**context, "invalid_response": response, "repair_instruction": "Return a JSON object with a non-empty string answer field only."},
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
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id, outcome="handoff", confidence=1.0, next_action=NextAction.HANDOFF, handoff_capability="billing.investigate")
        if task.context.degraded:
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id, outcome="escalated", confidence=0.0, next_action=NextAction.ESCALATE, failure_code="degraded_context", warnings=["?뺤콉 洹쇨굅媛 遺덉셿?꾪븯???뺤젙 ?듬???留뚮뱾吏 ?딆쓬"])
        seen: set[str] = set()
        try:
            sub = self.tools.call("read.subscription", task.context, {}, task.allowed_tools, seen)
            payments = self.tools.call("read.payment_history", task.context, {}, task.allowed_tools, seen)
            policy = self.tools.call("read.policy", task.context, {"query": task.input_text}, task.allowed_tools, seen)
        except ToolLoopExceeded:
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id, outcome="escalated", confidence=0.0, next_action=NextAction.ESCALATE, failure_code="tool_loop_guard")
        evidence = self._evidence(task, [sub, payments, policy])
        if not policy:
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id, outcome="escalated", confidence=0.0, evidence=evidence, next_action=NextAction.ESCALATE, failure_code="policy_not_found")
        cancelled = sub and sub.get("status") in {"cancelled", "ended"}
        # ?낅쾭洹몄궗??2026-08-17 ???ш린???대뼡 寃곗젣瑜??섎텋?좎? ?섎굹濡??뺥븳??
        #   ?꾩뿉??"異⑹쟾??寃곗젣媛 ?덈뒗媛"留?蹂닿퀬 ?뺤옉 ?쒖븞?먮뒗 customer_id 留?
        #   ?ｌ뿀?? verification_policy.py 媛 ?議고븯??payment_id/amount 媛
        #   ?쒖븞???꾩삁 ?놁뼱 verify_proposal() ??留ㅻ쾲 "?좎뼵?섏? ?딆? ?꾨뱶"濡?
        #   customer_id 瑜?嫄곕??덈떎 ???섎텋 ?쒖븞???뱀씤 ?湲곗뿉 ?꾨떖???곸씠
        #   ?ㅼ젣濡쒕뒗 ??踰덈룄 ?놁뿀??吏곸젒 ?ы쁽 ?뺤씤). ?議고븷 ???덈뒗 ?꾨뱶瑜??몃떎.
        charged_payment = next((p for p in payments if p.get("status") in {"paid", "succeeded"}), None)
        if cancelled and charged_payment is not None:
            request_id = str(task.context.current_state.get("request_id") or task.case_id)
            proposal = ActionProposal(
                action_type="refund.request",
                arguments={"payment_id": str(charged_payment["payment_id"]),
                          "amount_cents": charged_payment["amount_cents"]},
                idempotency_key=idempotency_key(tenant_id=task.context.tenant_id, request_id=request_id, action_type="refund.request", business_subject=str(task.case_id)), approval_required=True, risk_level="high", rationale_evidence_ids=[e.evidence_id for e in evidence])
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id, outcome="waiting", confidence=0.9, evidence=evidence, next_action=NextAction.WAIT_FOR_APPROVAL, wait_reason="human_approval", action_proposals=[proposal], decisions=[{"classification":"post_cancel_charge"}])
        answer = "援щ룆怨?寃곗젣 ?대젰???뺤씤?덉뒿?덈떎. ?뺤콉 洹쇨굅瑜?諛뷀깢?쇰줈 ?덈궡?????덉뒿?덈떎."
        if self.llm is not None:
            answer = await self._llm_answer(task, evidence)
            if answer is None:
                return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id, outcome="failed", confidence=0.0, evidence=evidence, next_action=NextAction.ESCALATE, failure_code="malformed_llm_response", warnings=["LLM ?묐떟??TeamResult answer ?ㅽ궎留덉? ?쇱튂?섏? ?딆쓬"])
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id, outcome="completed", confidence=0.8, answer=answer, evidence=evidence, next_action=NextAction.RESPOND)


__all__ = ["BillingSubscriptionTeam", "TeamModule"]

