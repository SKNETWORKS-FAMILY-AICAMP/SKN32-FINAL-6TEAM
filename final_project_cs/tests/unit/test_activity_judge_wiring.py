"""활동 판정 LLM 배선(D-CS-008) — 조립이 고른 어댑터가 Activity Team 까지 닿는가, 안 쓸 때는 `None` 인가."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

# ★`[2026-10-08]` develop 병합(1번 방안) — 등록된 활동 팀은 develop 의 `team.py` 이고, 조립(`composition.py`)은
#   develop 판이라 판정 LLM 을 넣지 않는다. LLM 판정 실험은 보존한 `team_a.py` 에만 있고, develop 구조 위에
#   다시 설계할 때 이 연결 시험을 되살린다.
pytestmark = pytest.mark.skip(reason="develop 병합 뒤 판정 LLM 배선은 다시 설계 예정(team_a 보존, 등록은 develop team)")

import pytest

import app.composition as composition
from app.infrastructure.llm.openai_responses import OpenAIResponsesJudgeLLM


@pytest.mark.parametrize("settings", [
    SimpleNamespace(activity_judge_mode="rule", openai_api_key="test"),
    SimpleNamespace(activity_judge_mode="shadow", openai_api_key=""),
    # ★칸이 없는 시험용 설정은 rule 과 같다 — 조립을 깨지 않는다
    SimpleNamespace(openai_api_key="test"),
])
def test_no_judge_when_rule_or_no_key(monkeypatch, settings):
    monkeypatch.setattr(composition, "get_settings", lambda: settings)
    assert composition.build_activity_judge_llm() is None


@pytest.mark.parametrize("mode", ["shadow", "llm"])
def test_judge_built_for_shadow_and_llm(monkeypatch, mode):
    monkeypatch.setattr(composition, "get_settings",
                        lambda: SimpleNamespace(activity_judge_mode=mode, openai_api_key="test"))
    assert isinstance(composition.build_activity_judge_llm(), OpenAIResponsesJudgeLLM)


def test_registry_injects_judge_into_activity_team_only(monkeypatch):
    """운영 조립 경로(도구를 직접 만드는 쪽)에서 Activity Team 에만 들어간다."""
    sentinel = object()
    sink = object()
    monkeypatch.setattr(composition, "build_activity_judge_llm", lambda: sentinel)
    monkeypatch.setattr(composition, "build_activity_judge_shadow_sink", lambda: sink)
    monkeypatch.setattr(composition, "ReadToolbox", lambda *a, **k: SimpleNamespace())
    monkeypatch.setattr("app.domains.travel_ops.ports.data_sources.build_travel_sources",
                        lambda *_: SimpleNamespace(limiter=None))
    monkeypatch.setattr(composition, "build_report_extractor", lambda: None)
    monkeypatch.setattr(composition, "build_kakao_local", lambda: None)
    monkeypatch.setattr(composition, "build_google_places", lambda **_: None)
    monkeypatch.setattr("app.domains.travel_ops.instances.mobility.wiring.configure_from_settings", lambda *_: None)
    registry = composition.build_registry()
    activity = registry.get("activity").module
    assert activity.judge_llm is sentinel
    assert activity.judge_shadow_sink is sink     # ★섀도 기록은 표로 간다(A안)
    others = [r.module for r in registry._teams.values() if r.module is not activity]
    assert all(getattr(team, "judge_llm", None) is None for team in others)


def test_injected_tools_path_gets_no_judge(monkeypatch):
    """★도구를 주입한 조립(시험)은 판정 LLM 을 넣지 않는다 — 조용히 네트워크를 타지 않게."""
    monkeypatch.setattr(composition, "build_activity_judge_llm",
                        lambda: pytest.fail("injected-tools path must not build the judge"))
    registry = composition.build_registry(tools=SimpleNamespace())
    assert registry.get("activity").module.judge_llm is None
