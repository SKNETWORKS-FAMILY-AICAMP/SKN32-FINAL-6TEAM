"""Guards the RAG-integration wiring added 2026-08-30: build_controller()
must select LocalFTTeamLLM when settings.llm_provider == "local_ft", and
OpenAITeamLLM otherwise (the pre-existing default). See
wiki/records/plans/2026-08-30_DoD28-FT-RAG통합_설계.md.

★2026-09-09 — 대상 Team 을 `response_generation_review` 로 박아 뒀는데,
  도메인이 여행으로 바뀌며 그 팀이 등록에서 빠져 셋이 한꺼번에 죽었다.
  지금은 `tests/registered_teams.LLM_WIRED_TEAM_ID` 하나만 고치면 된다.
  ★이 검사가 보는 것은 **배선**이다 — 그 팀이 LLM 을 실제로 부르는지가
  아니라, 조립이 고른 LLM 이 Team 까지 닿는지를 본다.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.composition import CompositionError, build_controller
from app.infrastructure.llm.local_ft import LocalFTTeamLLM
from app.infrastructure.llm.openai import OpenAITeamLLM

from tests.registered_teams import LLM_WIRED_TEAM_ID


def _settings(**overrides):
    base = dict(llm_provider="openai", local_ft_base_url="", openai_api_key="test")
    base.update(overrides)
    return SimpleNamespace(**base)


def test_defaults_to_openai_team_llm(monkeypatch):
    monkeypatch.setattr("app.composition.get_settings", lambda: _settings())
    controller = build_controller()
    llm = controller.registry.get(LLM_WIRED_TEAM_ID).module.llm
    assert isinstance(llm, OpenAITeamLLM)


def test_local_ft_provider_selects_local_ft_team_llm(monkeypatch):
    monkeypatch.setattr("app.composition.get_settings", lambda: _settings(
        llm_provider="local_ft", local_ft_base_url="http://x600:8100"))
    controller = build_controller()
    llm = controller.registry.get(LLM_WIRED_TEAM_ID).module.llm
    assert isinstance(llm, LocalFTTeamLLM)
    assert llm.base_url == "http://x600:8100"


def test_local_ft_provider_without_base_url_fails_closed(monkeypatch):
    monkeypatch.setattr("app.composition.get_settings", lambda: _settings(llm_provider="local_ft"))
    with pytest.raises(CompositionError, match="ACOP_LOCAL_FT_BASE_URL"):
        build_controller()


def test_explicit_llm_argument_bypasses_provider_selection(monkeypatch):
    monkeypatch.setattr("app.composition.get_settings", lambda: _settings())
    sentinel = object()
    controller = build_controller(llm=sentinel)
    assert controller.registry.get(LLM_WIRED_TEAM_ID).module.llm is sentinel
