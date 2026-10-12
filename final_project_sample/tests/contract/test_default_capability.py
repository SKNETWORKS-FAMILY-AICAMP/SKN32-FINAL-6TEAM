"""intent 가 capability 와 이름 매칭 안 될 때 **무엇을 고르는가** (cs 에서 이식).

★전에는 registry 가 말없이 `capabilities[0]` 을 골랐다. 그 선택이 "왜 그건지"
  아무 데도 안 적혀 있었다 — 팀이 capability 순서를 바꾸면 폴백 동작이 조용히
  달라진다. 이제 팀이 `default_capability` 로 **선언**한다.

  cs 가 먼저 겪고 고친 것이다
  (`docs/reports/debugs/2026-09-01_capability_for_폴백이_근거없이_기능을_고른다.md`).
"""
from __future__ import annotations

from acop_basement.core.contracts import TeamManifest
from acop_basement.core.registry import RegisteredTeam, TeamRegistry


def _manifest(**over) -> TeamManifest:
    base = dict(team_id="t", display_name="T", contract_name="a_cop.team_task",
                supported_contract_versions=["1.0"],
                capabilities=["alpha.check", "beta.act"],
                accepted_case_types=["x"], required_context=["case_state"],
                allowed_tools=[], knowledge_scope=[], max_steps=4, active=True,
                implementation_revision="r1")
    base.update(over)
    return TeamManifest(**base)


class _Team:
    def __init__(self, manifest): self.manifest = manifest
    async def execute(self, task): ...


def _entry(manifest) -> RegisteredTeam:
    return TeamRegistry([_Team(manifest)]).resolve(case_type="x")


def test_a_name_match_still_wins():
    assert TeamRegistry.capability_for(_entry(_manifest()), "beta") == "beta.act"


def test_the_declared_default_is_used_when_nothing_matches():
    entry = _entry(_manifest(default_capability="beta.act"))
    assert TeamRegistry.capability_for(entry, "unrelated") == "beta.act"


def test_without_a_declaration_it_still_falls_back_to_the_first():
    """★선언이 없으면 종전 동작 그대로다 — 이식이 기존 팀을 바꾸지 않는다."""
    assert TeamRegistry.capability_for(_entry(_manifest()), "unrelated") == "alpha.check"
