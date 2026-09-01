"""default_capability 선언이 capability_for()의 폴백 근거를 명시적으로 만드는지 확인.

★2026-09-01 — capability_for()가 intent와 이름으로 매칭되는 capability를
  못 찾으면 근거 없이 capabilities[0]을 골랐다. RegistryError로 막는 시도는
  실제 intent 5개 중 3개(shipping·exchange·other)의 정상 라우팅을 깨서
  되돌렸다(docs/reports/debugs/2026-09-01_capability_for_폴백이_근거없이_기능을_고른다.md).
  대신 팀이 그 기본값을 선언하게 하고, 안 적으면 전과 똑같이
  capabilities[0]을 쓴다 — 동작은 그대로, 근거만 명시적으로 남긴다.
"""
from app.core.contracts import TeamManifest
from app.core.registry import TeamRegistry


def _manifest(**overrides):
    base = dict(
        team_id="t", display_name="T", contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"], capabilities=["a.one", "a.two"],
        accepted_case_types=["x"], required_context=[], allowed_tools=[],
        knowledge_scope=[], implementation_revision="test",
    )
    base.update(overrides)
    return TeamManifest(**base)


class _Team:
    def __init__(self, manifest):
        self.manifest = manifest

    async def execute(self, task):
        raise NotImplementedError


def test_unmatched_intent_falls_back_to_declared_default_capability():
    manifest = _manifest(default_capability="a.two")
    registry = TeamRegistry([_Team(manifest)])
    entry = registry.get("t")
    assert registry.capability_for(entry, "no-such-intent") == "a.two"


def test_unmatched_intent_without_declared_default_uses_first_capability():
    manifest = _manifest()  # default_capability 미선언 — 기존 동작 그대로
    registry = TeamRegistry([_Team(manifest)])
    entry = registry.get("t")
    assert registry.capability_for(entry, "no-such-intent") == "a.one"


def test_matched_intent_ignores_declared_default():
    manifest = _manifest(capabilities=["a.one", "a.two"], default_capability="a.two")
    registry = TeamRegistry([_Team(manifest)])
    entry = registry.get("t")
    assert registry.capability_for(entry, "a") == "a.one"
