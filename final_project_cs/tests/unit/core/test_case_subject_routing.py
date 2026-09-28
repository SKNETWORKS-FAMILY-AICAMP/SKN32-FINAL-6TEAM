"""Case 가 가리키는 대상으로 팀을 고르는 규칙 · capability 선택에 상태 · 정책 선언 존중.

★`[결정 2026-09-17]` wiki `external/rest-endpoints.md` 「subject_ref」 ·
  `teams/team-contract/index.md` 「계약 밖에서 코어가 Team 에 대해 쓰는 것 둘」 ·
  `context/context-broker.md` 「정책 근거가 필요 없는 Team」.
"""
from __future__ import annotations

from uuid import uuid4

from app.application.routing import case_type_of
from app.core.context import ContextBroker, ContextInputs
from app.core.contracts import TeamManifest
from app.core.registry import TeamRegistry


# ── 라우팅 힌트 ────────────────────────────────────────────────
def test_the_classification_prefix_beats_a_guessed_hint():
    assert case_type_of("dining_hours", fallback="incident_report", hint="activity") == "dining"


def test_a_guessed_hint_fills_only_a_missing_prefix():
    assert case_type_of("other", fallback="adjust_reject", hint="dining") == "dining"
    assert case_type_of("other", fallback="adjust_reject") == "other"     # 힌트가 없으면 전처럼 실패로 간다


def test_a_verified_hint_beats_the_classification():
    """화면 버튼이 지정하고 서버가 확인한 항목의 종류는 사실이다."""
    assert case_type_of("activity_other", fallback="adjust_reject", hint="dining", hint_wins=True) == "dining"


def test_without_a_code_the_hint_comes_before_the_fallback():
    assert case_type_of(None, fallback="incident_report", hint="mobility") == "mobility"
    assert case_type_of(None, fallback="incident_report") == "incident_report"


# ── capability 선택에 상태 ─────────────────────────────────────
def _manifest(team_id: str, capabilities: list[str]) -> TeamManifest:
    return TeamManifest(team_id=team_id, display_name=team_id, contract_name="a_cop.team_task",
                        supported_contract_versions=["1.0"], capabilities=capabilities,
                        accepted_case_types=[team_id], required_context=["case_state"],
                        allowed_tools=[], knowledge_scope=[team_id], implementation_revision="test")


class StatefulTeam:
    manifest = _manifest("alpha", ["alpha.default", "alpha.subject"])
    seen: list = []

    @staticmethod
    def select_capability(intent, input_text, state=None):
        StatefulTeam.seen.append(state)
        return "alpha.subject" if (state or {}).get("subject_ref") else None

    async def execute(self, task):  # pragma: no cover — 선택만 본다
        raise NotImplementedError


class TwoArgumentTeam:
    manifest = _manifest("beta", ["beta.default", "beta.marker"])

    @staticmethod
    def select_capability(intent, input_text):
        return "beta.marker" if "표시" in input_text else None

    async def execute(self, task):  # pragma: no cover
        raise NotImplementedError


def test_state_reaches_a_team_that_declares_it():
    registry = TeamRegistry([StatefulTeam(), TwoArgumentTeam()])
    entry = registry.get("alpha")
    assert registry.capability_for(entry, "x", input_text="", state={"subject_ref": {"kind": "k"}}) == "alpha.subject"
    assert registry.capability_for(entry, "x", input_text="", state={}) == "alpha.default"
    assert StatefulTeam.seen[-1] == {}


def test_a_two_argument_selector_keeps_working():
    registry = TeamRegistry([TwoArgumentTeam()])
    entry = registry.get("beta")
    assert registry.capability_for(entry, "x", input_text="표시가 있다", state={"subject_ref": {}}) == "beta.marker"


# ── 정책 선언 존중 ─────────────────────────────────────────────
def _inputs(**kwargs) -> ContextInputs:
    return ContextInputs(case_id=uuid4(), tenant_id="t", team_id="alpha", knowledge_scope=["alpha"],
                         system_instruction="x", current_state={"customer_id": str(uuid4())}, **kwargs)


def test_no_policy_is_not_degraded_when_the_team_does_not_need_policy():
    pack = ContextBroker().build(_inputs(policy_required=False))
    assert pack.degraded is False and "policy_rag:no_results" not in pack.omissions


def test_no_policy_is_still_degraded_when_the_team_needs_policy():
    pack = ContextBroker().build(_inputs())
    assert pack.degraded is True and "policy_rag:no_results" in pack.omissions


def test_a_failed_retrieval_is_degraded_even_when_policy_is_not_required():
    """★모르는 것과 필요 없는 것은 다르다."""
    pack = ContextBroker().build(_inputs(policy_required=False, retrieval_failed=True))
    assert pack.degraded is True and "policy_rag:retrieval_failed" in pack.omissions
