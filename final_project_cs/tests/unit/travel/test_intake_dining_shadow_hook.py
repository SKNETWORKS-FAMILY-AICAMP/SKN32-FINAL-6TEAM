# -*- coding: utf-8 -*-
"""접수 → 요식 그림자 연결(`pipeline._dining_shadow`) — 꽂히지 않으면 아무것도 안 하고, 실패해도 접수를 건드리지 않는다. `[2026-10-13]`"""
from __future__ import annotations

import uuid

from app.domains.travel_ops.components.intake import pipeline
from app.domains.travel_ops.components.team_hooks import dining_ledger


def test_without_a_runner_nothing_is_called(monkeypatch):
    monkeypatch.setattr(dining_ledger, "agent_shadow_runner", lambda: None)

    def connect():
        raise AssertionError("그림자가 꺼져 있으면 DB 도 열지 않는다")
    pipeline._dining_shadow(connect, "t", uuid.uuid4(), [])


def test_a_failing_shadow_does_not_raise(monkeypatch):
    calls = []
    monkeypatch.setattr(dining_ledger, "agent_shadow_runner", lambda: lambda *a, **k: calls.append(k) or 1 / 0)
    monkeypatch.setattr(pipeline.review_module, "load", lambda conn, t, i, r: {"items": [{"id": "0-0"}]})

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False
    pipeline._dining_shadow(lambda: Conn(), "t", uuid.uuid4(), [{"transcript": "점심 하동관"}])
    assert calls and calls[0]["notes"] == "점심 하동관" and calls[0]["revision"] == 1


def test_the_switch_is_off_by_default():
    from app.core.settings import dining_agent_shadow

    assert dining_agent_shadow() is None


def test_composition_builds_the_runner_only_when_switched_on(monkeypatch):
    from types import SimpleNamespace

    import app.core.settings as settings_module
    from app import composition
    from app.infrastructure.llm.tool_chat import OllamaToolChat, OpenAIToolChat

    assert composition._dining_agent_shadow() is None                                 # 기본 꺼짐
    stub = SimpleNamespace(openai_api_key="sk-test", ollama_base_url="", ollama_model="gemma4:12b")
    monkeypatch.setattr(settings_module, "get_settings", lambda: stub)
    monkeypatch.setattr(settings_module, "dining_agent_shadow", lambda: {"model": "openai:gpt-4o-mini", "deadline_s": 30.0})
    runner = composition._dining_agent_shadow()
    assert isinstance(runner.keywords["chat"], OpenAIToolChat) and runner.keywords["deadline_s"] == 30.0
    monkeypatch.setattr(settings_module, "dining_agent_shadow", lambda: {"model": "ollama:gemma4:12b", "deadline_s": 30.0})
    assert composition._dining_agent_shadow() is None                                 # 모델 서버 주소가 없으면 만들지 않는다
    stub.ollama_base_url = "http://model-server.test:11434"
    assert isinstance(composition._dining_agent_shadow().keywords["chat"], OllamaToolChat)
