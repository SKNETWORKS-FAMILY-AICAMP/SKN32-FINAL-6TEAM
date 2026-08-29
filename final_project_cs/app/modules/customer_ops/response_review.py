"""Response Generation & Review Team: deterministic safety first, then tone review."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Protocol

from app.core.contracts import Evidence, NextAction, TeamManifest, TeamModule, TeamResult, TeamTask
from app.core.verification import Facts, verify_proposal
from app.modules.customer_ops.response_review_policy import (
    CUSTOMER_OPS_POLICY, FORBIDDEN_WORDS, PII_PATTERNS, decide_tone, detect_person_name_pii,
)


class LLM(Protocol):
    async def complete(self, prompt_key: str, input_text: str, context: dict[str, Any]) -> dict[str, Any]: ...


class ResponseGenerationReviewTeam:
    manifest = TeamManifest(
        team_id="response_generation_review",
        display_name="Response Generation & Review Team",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=["response.generate_review"],
        accepted_case_types=[],
        required_context=["case_state", "policy", "db_facts", "history"],
        allowed_tools=["read.policy"],
        knowledge_scope=["response_review"],
        max_steps=4,
        active=True,
        implementation_revision="2026-08-20",
    )

    def __init__(self, llm: LLM | None = None) -> None:
        self.llm = llm

    @staticmethod
    def _evidence(task: TeamTask) -> list[Evidence]:
        if task.context.evidence:
            return list(task.context.evidence)
        return [Evidence(
            evidence_id=f"context:{task.task_id}", source_type="case_event",
            source_id=str(task.case_id), claim="Response review context supplied",
            value=task.context.current_state, confidence=1.0, observed_at=datetime.now(UTC),
        )]

    @staticmethod
    def _facts(task: TeamTask) -> Facts:
        raw = task.context.current_state.get("db_facts", {})
        collections: dict[str, dict[str, dict[str, Any]]] = {}
        if isinstance(raw, dict):
            for name, records in raw.items():
                if isinstance(records, dict):
                    collections[name] = {str(k): v for k, v in records.items() if isinstance(v, dict)}
                elif isinstance(records, list):
                    collections[name] = {
                        str(item.get("order_id") or item.get("payment_id") or item.get("policy_ref") or item.get("id")): item
                        for item in records if isinstance(item, dict)
                    }
        return Facts(collections=collections, evidence_ids=frozenset(e.evidence_id for e in task.context.evidence))

    @staticmethod
    def _decode(value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                return {"final_response_text": value}
            return decoded if isinstance(decoded, dict) else None
        return None

    @staticmethod
    def _claims(response: dict[str, Any]) -> dict[str, Any]:
        claims = response.get("claims")
        return dict(claims) if isinstance(claims, dict) else {
            key: response[key] for key in ("refund_amount", "refund_amount_cents", "order_id", "return_quantity")
            if key in response
        }

    @staticmethod
    def _deterministic(text: str, claims: dict[str, Any], facts: Facts) -> list[str]:
        problems = [f"forbidden_word:{word}" for word in FORBIDDEN_WORDS if word.lower() in text.lower()]
        if any(pattern.search(text) for pattern in PII_PATTERNS) or detect_person_name_pii(text):
            problems.append("pii_detected")
        if claims:
            mismatches = verify_proposal(
                arguments=claims, rationale_evidence_ids=[], facts=facts,
                policy=CUSTOMER_OPS_POLICY,
            )
            problems.extend(f"fact_mismatch:{m.field}" for m in mismatches)
        return problems

    async def _generate(self, task: TeamTask, evidence: list[Evidence], retry: int, tone_profile: str) -> dict[str, Any]:
        if self.llm is None:
            return {"final_response_text": task.input_text, "status": "completed"}
        response = await self.llm.complete(
            "response.generate", task.input_text,
            {"evidence": evidence, "context": task.context.model_dump(mode="json"),
             "retry_count": retry, "tone_profile": tone_profile},
        )
        return self._decode(response) or {}

    async def execute(self, task: TeamTask) -> TeamResult:
        evidence = self._evidence(task)
        facts = self._facts(task)
        tone_profile = decide_tone(task.context.current_state.get("sentiment"))
        decisions: list[dict[str, Any]] = []
        for retry in range(4):
            response = await self._generate(task, evidence, retry, tone_profile)
            text = response.get("final_response_text", response.get("answer", ""))
            text = text.strip() if isinstance(text, str) else ""
            failures = self._deterministic(text, self._claims(response), facts)
            decision = {"retry_count": retry, "review_history": failures, "first_pass": retry == 0, "tone_profile": tone_profile}
            if "pii_detected" in failures:
                decisions.append(decision)
                return self._escalated(task, evidence, decisions, "pii_detected")
            if failures:
                decisions.append(decision)
                continue
            if response.get("escalation") is True or response.get("status") == "escalated":
                decisions.append(decision)
                return self._escalated(task, evidence, decisions, "llm_escalation")
            warnings: list[str] = []
            tone_ok = response.get("tone_ok")
            if self.llm is not None and tone_ok is None:
                tone_result = self._decode(await self.llm.complete(
                    "response.review_tone", text, {"tone_profile": tone_profile, "response": response}
                )) or {}
                tone_ok = tone_result.get("tone_ok", True)
            if tone_ok is False:
                warnings.append("tone_review_failed")
                decision["tone"] = "warning"
            decisions.append(decision)
            return TeamResult(
                task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                outcome="completed", answer=text or None, confidence=0.9 if not warnings else 0.75,
                evidence=evidence, decisions=decisions, next_action=NextAction.RESPOND, warnings=warnings,
            )
        return self._escalated(task, evidence, decisions, "review_retries_exhausted")

    def _escalated(self, task: TeamTask, evidence: list[Evidence], decisions: list[dict[str, Any]], code: str) -> TeamResult:
        reasons = [reason for decision in decisions for reason in decision.get("review_history", []) if isinstance(reason, str)]
        warnings = [code] + [reason for reason in dict.fromkeys(reasons) if reason != code]
        return TeamResult(
            task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
            outcome="escalated", confidence=0.0, evidence=evidence, decisions=decisions,
            next_action=NextAction.ESCALATE, failure_code=code, warnings=warnings,
        )


__all__ = ["LLM", "ResponseGenerationReviewTeam", "TeamModule"]
