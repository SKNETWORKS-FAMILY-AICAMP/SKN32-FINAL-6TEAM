"""활동 판정 LLM 배선(D-CS-008 → D-CS-015) — 조립이 고른 어댑터가 develop 판 Activity Team 까지 닿는가, 안 쓸 때는 `None` 인가.

★`[2026-10-09]` develop 판 활동 팀(`team.py`)에 판정 LLM 칸을 다시 만들어(D-CS-015) 이 시험을 되살렸다 — 2026-10-08 병합 뒤
  「다시 설계 예정」으로 꺼 두었다. develop 판은 `rule` · `shadow` 만 받는다(`llm` 은 기동 때 막는다).
"""
from __future__ import annotations

from types import SimpleNamespace

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


def _production_assembly(monkeypatch, *, judge, sink, settings=None):
    monkeypatch.setattr(composition, "build_activity_judge_llm", lambda: judge)
    monkeypatch.setattr(composition, "build_activity_judge_shadow_sink", lambda: sink)
    if settings is not None:
        monkeypatch.setattr(composition, "get_settings", lambda: settings)
    monkeypatch.setattr(composition, "ReadToolbox", lambda *a, **k: SimpleNamespace())
    monkeypatch.setattr("app.domains.travel_ops.ports.data_sources.build_travel_sources",
                        lambda *_: SimpleNamespace(limiter=None))
    monkeypatch.setattr(composition, "build_report_extractor", lambda: None)
    monkeypatch.setattr(composition, "build_kakao_local", lambda: None)
    monkeypatch.setattr(composition, "build_google_places", lambda **_: None)
    monkeypatch.setattr("app.domains.travel_ops.instances.mobility.wiring.configure_from_settings", lambda *_, **__: None)


def test_registry_injects_judge_into_activity_team_only(monkeypatch):
    """운영 조립 경로(도구를 직접 만드는 쪽)에서 Activity Team 에만 들어간다."""
    sentinel = object()
    sink = object()
    _production_assembly(monkeypatch, judge=sentinel, sink=sink)
    registry = composition.build_registry()
    activity = registry.get("activity").module
    assert activity.judge_llm is sentinel
    assert activity.judge_shadow_sink is sink     # ★섀도 기록은 표로 간다(A안)
    others = [r.module for r in registry._teams.values() if r.module is not activity]
    assert all(getattr(team, "judge_llm", None) is None for team in others)


def test_llm_mode_stops_the_assembly_instead_of_running_shadow(monkeypatch):
    """★`[2026-10-09]` develop 판 활동 팀은 `llm` 모드를 받지 않는다(D-CS-015) — 섀도로 조용히 바꾸지 않고 기동을 멈춘다."""
    real = composition.get_settings()
    _production_assembly(monkeypatch, judge=object(), sink=object(),
                         settings=real.model_copy(update={"activity_judge_mode": "llm"}))
    with pytest.raises(composition.CompositionError, match="activity_judge_mode"):
        composition.build_registry()


def test_injected_tools_path_gets_no_judge(monkeypatch):
    """★도구를 주입한 조립(시험)은 판정 LLM 을 넣지 않는다 — 조용히 네트워크를 타지 않게."""
    monkeypatch.setattr(composition, "build_activity_judge_llm",
                        lambda: pytest.fail("injected-tools path must not build the judge"))
    registry = composition.build_registry(tools=SimpleNamespace())
    assert registry.get("activity").module.judge_llm is None
