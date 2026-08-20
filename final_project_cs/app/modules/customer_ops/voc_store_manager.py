"""VOC & Store Manager Team: acknowledge feedback and escalate repeated complaints."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.contracts import ActionProposal, Evidence, NextAction, TeamManifest, TeamResult, TeamTask
from app.core.idempotency import idempotency_key
from app.tools.read_tools import ReadToolbox, ToolLoopExceeded


class VocStoreManagerTeam:
    manifest = TeamManifest(
        team_id="voc_store_manager", display_name="VOC & Store Manager Team",
        contract_name="a_cop.team_task", supported_contract_versions=["1.0"],
        capabilities=["voc.aggregate", "voc.escalate"],
        accepted_case_types=["other"],
        required_context=["case_state", "policy", "db_facts", "history"],
        allowed_tools=["read.policy"],
        knowledge_scope=["order", "shipping", "return", "exchange"],
        max_steps=6, active=True, implementation_revision="2026-08-19",
    )

    def __init__(self, tools: ReadToolbox, llm: Any | None = None) -> None:
        self.tools, self.llm = tools, llm

    @staticmethod
    def _evidence(task: TeamTask, policy: Any) -> list[Evidence]:
        evidence = list(task.context.evidence)
        if policy:
            evidence.append(Evidence(
                evidence_id="tool:voc_store_manager", source_type="tool_result",
                source_id="read.policy", claim="VOC 운영 정책을 조회했습니다.", value=policy,
                confidence=1.0,
                observed_at=evidence[0].observed_at if evidence else datetime.now(UTC),
            ))
        return evidence

    async def execute(self, task: TeamTask) -> TeamResult:
        if task.context.degraded:
            return TeamResult(
                task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                outcome="escalated", confidence=0.0, next_action=NextAction.ESCALATE,
                failure_code="degraded_context",
            )

        seen: set[str] = set()
        try:
            policy = self.tools.call(
                "read.policy", task.context, {"query": task.input_text}, task.allowed_tools, seen,
            )
        except ToolLoopExceeded:
            return TeamResult(
                task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                outcome="escalated", confidence=0.0, next_action=NextAction.ESCALATE,
                failure_code="tool_loop_guard",
            )

        evidence = self._evidence(task, policy)
        if not policy:
            return TeamResult(
                task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                outcome="escalated", confidence=0.0, evidence=evidence,
                next_action=NextAction.ESCALATE, failure_code="policy_not_found",
            )

        similar_case_count = len(task.context.similar_cases)
        if similar_case_count >= 2:
            action_type = "voc.escalate"
            proposal = ActionProposal(
                action_type=action_type, arguments={},
                idempotency_key=idempotency_key(
                    tenant_id=task.context.tenant_id,
                    request_id=str(task.context.current_state.get("request_id") or task.case_id),
                    action_type=action_type, business_subject=str(task.case_id),
                ),
                approval_required=True, risk_level="low",
                rationale_evidence_ids=[item.evidence_id for item in evidence],
            )
            return TeamResult(
                task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                outcome="waiting", confidence=0.8, evidence=evidence,
                next_action=NextAction.WAIT_FOR_APPROVAL, wait_reason="human_approval",
                action_proposals=[proposal],
                decisions=[{"classification": "repeated_complaint_escalation",
                            "similar_case_count": similar_case_count}],
            )

        return TeamResult(
            task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
            outcome="completed", confidence=0.7,
            answer="피드백을 확인했습니다. 접수된 의견은 운영 개선에 반영됩니다.",
            evidence=evidence, next_action=NextAction.RESPOND,
        )


__all__ = ["VocStoreManagerTeam"]
