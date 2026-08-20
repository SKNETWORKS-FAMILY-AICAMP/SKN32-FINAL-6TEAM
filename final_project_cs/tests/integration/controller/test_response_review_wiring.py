from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.controller import Controller
from app.core.contracts import ContextPack, Evidence, TeamManifest, TeamResult, TeamTask, NextAction
from app.core.project_config import ResponseReviewConfig
from app.core.registry import TeamRegistry


class _Team:
    def __init__(self, manifest, answer, outcome="completed"):
        self.manifest = manifest
        self.answer = answer
        self.outcome = outcome
        self.calls = 0

    async def execute(self, task):
        self.calls += 1
        evidence = [Evidence(evidence_id=f"ev:{task.team_id}", source_type="case_event",
                             source_id=str(task.case_id), claim="fixture", value={}, confidence=1,
                             observed_at=datetime.now(UTC))]
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id,
                          outcome=self.outcome, answer=self.answer if self.outcome == "completed" else None,
                          confidence=1 if self.outcome == "completed" else 0, evidence=evidence,
                          next_action=NextAction.RESPOND if self.outcome == "completed" else NextAction.ESCALATE,
                          failure_code=None if self.outcome == "completed" else "review_rejected")


def _manifest(team_id, capability, accepted):
    return TeamManifest(team_id=team_id, display_name=team_id, contract_name="a_cop.team_task",
                        supported_contract_versions=["1.0"], capabilities=[capability],
                        accepted_case_types=accepted, required_context=["case_state", "policy", "db_facts", "history"],
                        allowed_tools=[], knowledge_scope=["shop"], implementation_revision="test")


def _task(team_id="order_team"):
    case_id = uuid4()
    pack = ContextPack(pack_id=uuid4(), case_id=case_id, team_id=team_id, tenant_id="test",
                       knowledge_scope=["shop"], current_state={"sentiment": "neutral"},
                       evidence=[], estimated_input_tokens=1)
    return TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id=team_id,
                    capability="order.answer", case_version=1, input_text="배송 상태를 알려주세요.",
                    context=pack, allowed_tools=[], deadline_at=datetime.now(UTC) + timedelta(seconds=30))


@pytest.mark.asyncio
async def test_review_disabled_preserves_original_result_and_skips_second_pass():
    primary = _Team(_manifest("order_team", "order.answer", ["order"]), "원래 답변")
    reviewer = _Team(_manifest("response_generation_review", "response.generate_review", []), "검수 답변")
    controller = Controller(TeamRegistry([primary, reviewer]), response_review=ResponseReviewConfig(
        enabled=False, owner_team_id="response_generation_review"))
    result = await controller._maybe_review(_task(), await primary.execute(_task()))
    assert result.answer == "원래 답변"
    assert reviewer.calls == 0


@pytest.mark.asyncio
async def test_review_enabled_executes_second_pass_and_returns_review_outcome():
    primary = _Team(_manifest("order_team", "order.answer", ["order"]), "생성 답변")
    reviewer = _Team(_manifest("response_generation_review", "response.generate_review", []), "검수 완료 답변")
    controller = Controller(TeamRegistry([primary, reviewer]), response_review=ResponseReviewConfig(
        enabled=True, owner_team_id="response_generation_review"))
    task = _task()
    result = await controller._maybe_review(task, await primary.execute(task))
    assert reviewer.calls == 1
    assert result.outcome == "completed"
    assert result.answer == "검수 완료 답변"
