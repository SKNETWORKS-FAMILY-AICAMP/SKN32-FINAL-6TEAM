"""선언형 Team — 계획서(2026-08-28) §4 완료 기준을 증명한다.

★핵심 증명은 "같은 구현체를 두 번 써도 capability 가 다르면 둘 다 조립된다"
  이다. 지금까지 인스턴스 복제가 안 됐던 이유가 바로 capability 충돌이었다
  (`app/composition.py` 의 duplicate capability 검사).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import yaml

from acop_basement.core.contracts import ContextPack, NextAction, TeamTask
from acop_basement.core.project_config import (
    DECLARATIVE_TEAM_REF,
    DeclarativeTeamParameters,
    ProjectConfigError,
    load_project_config,
)
from acop_basement.teams.declarative import DeclarativeTeamRuntime
from acop_basement.tools.read_tools import ReadToolbox


def _params(**overrides):
    base = {
        "display_name": "선언형 검토",
        "capabilities": ["demo.review"],
        "accepted_case_types": ["demo"],
        "required_context": ["case_state", "policy"],
        "allowed_tools": ["read.policy"],
        "knowledge_scope": ["demo"],
        "max_steps": 3,
        "prompt_key": "declarative.demo",
    }
    base.update(overrides)
    return base


def _task(team_id: str = "demo_team") -> TeamTask:
    case_id = uuid4()
    pack = ContextPack(pack_id=uuid4(), case_id=case_id, team_id=team_id, tenant_id="t1",
                       knowledge_scope=["demo"],
                       # ★read tool 은 current_state.customer_id 를 UUID 로 요구한다
                       #   (`ToolContext.from_pack`).
                       current_state={"customer_id": str(uuid4())}, evidence=[],
                       estimated_input_tokens=1)
    return TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id=team_id,
                    capability="demo.review", case_version=1, input_text="문의합니다",
                    context=pack, allowed_tools=["read.policy"],
                    deadline_at=datetime.now(UTC) + timedelta(seconds=30))


def _toolbox(value="정책 본문"):
    return ReadToolbox(tool_functions={"read.policy": lambda _ctx, **_kw: value})


# ── grant ceiling ────────────────────────────────────────────────────
def test_tool_outside_read_prefix_is_rejected_at_validation():
    with pytest.raises(ValueError, match="읽기 전용"):
        DeclarativeTeamParameters.model_validate(_params(allowed_tools=["write.refund"]))


def test_declaration_with_forbidden_tool_fails_to_load(tmp_path):
    """★런타임이 아니라 로드 시점에 막혀야 한다."""
    declaration = {
        "modules": {"vector_rag": {"enabled": True}},
        "ports": {"team_executor": "local", "message_broker": "outbox", "graph_store": "sql"},
        "teams": [{"team_id": "bad", "active": True,
                   "implementation_ref": DECLARATIVE_TEAM_REF,
                   "parameters": _params(allowed_tools=["read.policy", "payments.refund"])}],
    }
    path = tmp_path / "project.yaml"
    path.write_text(yaml.safe_dump(declaration, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ProjectConfigError, match="읽기 전용"):
        load_project_config(path)


# ── parameters 는 선언형에만 ─────────────────────────────────────────
def test_code_team_with_parameters_is_rejected(tmp_path):
    """조용히 무시하면 사용자는 설정이 먹은 줄 안다."""
    declaration = {
        "modules": {"vector_rag": {"enabled": True}},
        "ports": {"team_executor": "local", "message_broker": "outbox", "graph_store": "sql"},
        "teams": [{"team_id": "code", "active": False,
                   "implementation_ref": "app.modules.placeholder:PlaceholderTeam",
                   "parameters": _params()}],
    }
    path = tmp_path / "project.yaml"
    path.write_text(yaml.safe_dump(declaration, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ProjectConfigError, match="선언형 Team 에만"):
        load_project_config(path)


def test_existing_repository_declaration_still_loads():
    """★하위호환 — parameters 없는 기존 선언이 그대로 로드돼야 한다."""
    config = load_project_config()
    assert config.teams
    assert all(team.parameters is None for team in config.teams)


# ── 실행 ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_escalates_when_no_evidence_instead_of_inventing_an_answer():
    team = DeclarativeTeamRuntime(ReadToolbox(tool_functions={"read.policy": lambda _c, **_k: None}),
                                  parameters=_params(), team_id="demo_team")
    result = await team.execute(_task())
    assert result.outcome == "escalated"
    assert result.failure_code == "no_evidence"
    assert result.answer is None
    assert result.warnings, "빈 결과를 조용히 넘기지 않고 보고해야 한다"


@pytest.mark.asyncio
async def test_escalates_when_llm_is_absent_but_keeps_the_evidence():
    team = DeclarativeTeamRuntime(_toolbox(), parameters=_params(), team_id="demo_team")
    result = await team.execute(_task())
    assert result.outcome == "escalated"
    assert result.failure_code == "no_draft"
    assert [e.source_id for e in result.evidence] == ["read.policy"]


@pytest.mark.asyncio
async def test_completes_with_llm_draft_and_cites_the_tool_evidence():
    class _LLM:
        async def complete(self, prompt_key, input_text, context):
            assert prompt_key == "declarative.demo"
            return {"answer": "정책에 따르면 가능합니다"}

    team = DeclarativeTeamRuntime(_toolbox(), llm=_LLM(), parameters=_params(),
                                  team_id="demo_team")
    result = await team.execute(_task())
    assert result.outcome == "completed"
    assert result.next_action is NextAction.RESPOND
    assert result.answer == "정책에 따르면 가능합니다"
    assert result.evidence, "근거 없이 완료로 끝나면 안 된다"


@pytest.mark.asyncio
async def test_llm_failure_is_not_disguised_as_success():
    class _Broken:
        async def complete(self, *_a, **_k):
            raise RuntimeError("provider down")

    team = DeclarativeTeamRuntime(_toolbox(), llm=_Broken(), parameters=_params(),
                                  team_id="demo_team")
    result = await team.execute(_task())
    assert result.outcome == "escalated"
    assert result.failure_code == "draft_failed"


@pytest.mark.asyncio
async def test_never_emits_action_proposals():
    """1차 범위 — 선언형은 side effect 를 제안하지 않는다."""
    class _LLM:
        async def complete(self, *_a, **_k):
            return {"answer": "확인했습니다"}

    team = DeclarativeTeamRuntime(_toolbox(), llm=_LLM(), parameters=_params(),
                                  team_id="demo_team")
    result = await team.execute(_task())
    assert result.action_proposals == []
