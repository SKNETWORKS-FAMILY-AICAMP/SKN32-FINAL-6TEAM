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


def _production_assembly(monkeypatch, *, judge, sink, settings=None, budget=None):
    monkeypatch.setattr(composition, "build_activity_judge_llm", lambda: judge)
    monkeypatch.setattr(composition, "build_activity_judge_shadow_sink", lambda: sink)
    monkeypatch.setattr(composition, "build_activity_judge_budget", lambda: budget)
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
    budget = object()
    _production_assembly(monkeypatch, judge=sentinel, sink=sink, budget=budget)
    registry = composition.build_registry()
    activity = registry.get("activity").module
    assert activity.judge_llm is sentinel
    assert activity.judge_shadow_sink is sink     # ★섀도 기록은 표로 간다(A안)
    assert activity.judge_budget is budget        # ★`[2026-10-13]` DB 예산 — 프로세스 안 임시 상한(`LocalWebBudget`)보다 앞선다
    others = [r.module for r in registry._teams.values() if r.module is not activity]
    assert all(getattr(team, "judge_llm", None) is None for team in others)
    assert all(getattr(team, "judge_budget", None) is None for team in others)


def test_budget_counts_text_and_web_on_separate_db_lines(monkeypatch):
    """★`[2026-10-13]` 활동 코어 전달 사항 7번 — 원문 해석과 웹 검색을 `external_call_budget` 의 다른 줄로 센다.
    상한은 가드레일 `travel.activity_judge.budget` 그대로다."""
    import app.domains.travel_ops.ports.data_sources.call_budget as call_budget
    from app.core.settings import get_guardrails

    built, reserved = {}, []

    class _Budget:
        def __init__(self, *, connection_factory, caps):
            built.update(caps=caps, connection_factory=connection_factory)

        def try_reserve(self, meter):
            reserved.append(meter)
            return meter != "activity_judge_web"

    monkeypatch.setattr(call_budget, "CallBudget", _Budget)
    allowed = composition.build_activity_judge_budget()
    assert allowed("closure") is True and allowed("live_status") is False
    assert reserved == ["activity_judge", "activity_judge_web"]
    assert built["connection_factory"] is composition.get_connection
    table = get_guardrails().get("travel.activity_judge.budget")
    assert built["caps"] == {"activity_judge": {"day": table["text"]["day"], "month": table["text"]["month"]},
                             "activity_judge_web": {"day": table["web"]["day"], "month": table["web"]["month"]}}


def test_no_budget_is_built_when_the_judge_is_off(monkeypatch):
    """판정 LLM 이 꺼져 있으면(기본 `rule`) 예산도 만들지 않는다 — 부를 일이 없다."""
    _production_assembly(monkeypatch, judge=None, sink=None)
    monkeypatch.setattr(composition, "build_activity_judge_budget",
                        lambda: pytest.fail("budget must not be built without a judge"))
    registry = composition.build_registry()
    assert registry.get("activity").module.judge_budget is None


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
