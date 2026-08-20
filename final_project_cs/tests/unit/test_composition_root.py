from __future__ import annotations

from app.composition import _instantiate_team, build_registry
from app.core.contracts import NextAction, TeamManifest, TeamResult
from app.tools.read_tools import ReadToolbox


class ExtraTeam:
    manifest = TeamManifest(
        team_id="demo_team",
        display_name="Demo Team",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=["demo.investigate"],
        accepted_case_types=["demo"],
        required_context=["case_state", "policy", "db_facts", "history"],
        allowed_tools=[], knowledge_scope=["demo"], implementation_revision="test",
    )

    async def execute(self, task):
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                          outcome="completed", confidence=1, next_action=NextAction.RESPOND)


def test_composition_registers_the_builtin_team_and_allows_extension():
    registry = build_registry(tools=ReadToolbox(lambda: None), llm=object())
    assert {manifest.team_id for manifest in registry.manifests()} == {
        "voc_store_manager", "response_generation_review",
        "return_refund", "procurement_order_payment", "fulfillment_logistics",
    }

    registry.register(ExtraTeam())
    assert registry.resolve(case_type="demo", intent="demo").manifest.team_id == "demo_team"


class _SingleToolsArgTeam:
    def __init__(self, tools):
        self.tools = tools


class _SingleLlmArgTeam:
    def __init__(self, llm=None):
        self.llm = llm


class _TwoArgTeam:
    def __init__(self, tools, llm=None):
        self.tools, self.llm = tools, llm


def test_instantiate_team_routes_single_positional_arg_by_name():
    """★2026-08-19 결함 — 개수만 보면 ReadToolbox 가 llm 자리로 잘못 들어간다.

    docs/reports/debugs/2026-08-19_composition_단일인자_Team_llm_오배선.md
    """
    tools_sentinel, llm_sentinel = object(), object()

    tools_team = _instantiate_team(_SingleToolsArgTeam, tools_sentinel, llm_sentinel)
    assert tools_team.tools is tools_sentinel

    llm_team = _instantiate_team(_SingleLlmArgTeam, tools_sentinel, llm_sentinel)
    assert llm_team.llm is llm_sentinel

    both_team = _instantiate_team(_TwoArgTeam, tools_sentinel, llm_sentinel)
    assert both_team.tools is tools_sentinel and both_team.llm is llm_sentinel
