"""운영 조립이 여행 Team 에 신고 추출기를 넣는가 — `[2026-09-17]` 빠져 있던 자리.

★시험·시나리오는 조립기(`case_engine`)에 직접 넣어 돌았고 운영 조립(`build_registry`)만 안 넣었다.
  그러면 실제 `/v1/cases` 로 온 「점심에 70분 늦어요」가 Team 에서 「신고 내용 모름」으로 사람에게 간다.
"""
from __future__ import annotations

import app.composition as composition
import app.core.settings as settings_module


def _registry_with(monkeypatch, **update):
    settings = settings_module.get_settings().model_copy(update=update)
    monkeypatch.setattr(composition, "get_settings", lambda: settings)
    return composition.build_registry()


def test_the_production_registry_gives_teams_a_report_extractor_when_ollama_is_set(monkeypatch):
    registry = _registry_with(monkeypatch, ollama_base_url="http://127.0.0.1:11434")
    for team_id in ("activity", "dining", "mobility"):
        assert registry.get(team_id).module.tools.report_extractor is not None, team_id


def test_without_ollama_there_is_no_extractor_and_nothing_is_made_up(monkeypatch):
    registry = _registry_with(monkeypatch, ollama_base_url="")
    assert registry.get("dining").module.tools.report_extractor is None
