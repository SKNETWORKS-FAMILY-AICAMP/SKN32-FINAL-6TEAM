# -*- coding: utf-8 -*-
"""접수 → 요식 판정 연결(`pipeline._dining_judge`) — 꽂히지 않으면 아무것도 안 하고, 실패해도 접수를 건드리지 않는다. `[2026-10-13]`"""
from __future__ import annotations

import uuid

from app.domains.travel_ops.components.intake import pipeline
from app.domains.travel_ops.components.team_hooks import dining_ledger


def test_without_a_runner_nothing_is_called(monkeypatch):
    monkeypatch.setattr(dining_ledger, "agent_judge_runner", lambda: None)

    def connect():
        raise AssertionError("판정이 꺼져 있으면 DB 도 열지 않는다")
    pipeline._dining_judge(connect, "t", uuid.uuid4(), [])


def test_a_failing_judge_does_not_raise(monkeypatch):
    calls = []
    monkeypatch.setattr(dining_ledger, "agent_judge_runner", lambda: lambda *a, **k: calls.append(k) or 1 / 0)
    monkeypatch.setattr(pipeline.review_module, "load", lambda conn, t, i, r: {"items": [{"id": "0-0"}]})

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False
    pipeline._dining_judge(lambda: Conn(), "t", uuid.uuid4(), [{"transcript": "점심 하동관"}])
    assert calls and calls[0]["notes"] == "점심 하동관" and calls[0]["revision"] == 1


def test_the_switch_is_on_by_default():
    """`[2026-10-16 사용자 지시]` 기본 켜짐 — 가드레일 값."""
    from app.core.settings import dining_agent_judge

    assert dining_agent_judge() == {"model": "openai:gpt-6-luna", "deadline_s": 120.0}


def test_composition_builds_the_runner_only_when_switched_on(monkeypatch):
    from types import SimpleNamespace

    import app.core.settings as settings_module
    from app import composition
    from app.infrastructure.llm.tool_chat import OllamaToolChat, OpenAIToolChat

    monkeypatch.setattr(settings_module, "dining_agent_judge", lambda: None)
    assert composition._dining_agent_judge() is None                                 # 끄면 만들지 않는다
    stub = SimpleNamespace(openai_api_key="sk-test", ollama_base_url="", ollama_model="gemma4:12b", llm_provider="mock")
    monkeypatch.setattr(settings_module, "get_settings", lambda: stub)
    monkeypatch.setattr(settings_module, "dining_agent_judge", lambda: {"model": "openai:gpt-4o-mini", "deadline_s": 30.0})
    assert composition._dining_agent_judge() is None                                 # 모의 모델(시험 · CI)이면 만들지 않는다
    stub.llm_provider = "openai"
    monkeypatch.setattr(settings_module, "dining_agent_judge", lambda: {"model": "openai:gpt-4o-mini", "deadline_s": 30.0})
    runner = composition._dining_agent_judge()
    assert isinstance(runner.keywords["chat"], OpenAIToolChat) and runner.keywords["deadline_s"] == 30.0
    monkeypatch.setattr(settings_module, "dining_agent_judge", lambda: {"model": "ollama:gemma4:12b", "deadline_s": 30.0})
    assert composition._dining_agent_judge() is None                                 # 모델 서버 주소가 없으면 만들지 않는다
    stub.ollama_base_url = "http://model-server.test:11434"
    assert isinstance(composition._dining_agent_judge().keywords["chat"], OllamaToolChat)


def test_luna_tool_calls_turn_reasoning_off():
    """`[2026-10-15]` gpt-6-luna 는 chat completions 에서 도구와 추론을 함께 못 쓴다(400) — 추론을 끄고 보낸다. 다른 모델에는 넣지 않는다."""
    from types import SimpleNamespace

    from app.infrastructure.llm.tool_chat import OpenAIToolChat

    sent = []
    reply = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}", tool_calls=None))],
                            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1))
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: sent.append(kw) or reply)))
    for model in ("gpt-6-luna", "gpt-4o-mini"):
        OpenAIToolChat(api_key="sk-test", model=model, client=client).step([{"role": "user", "content": "hi"}], [])
    assert sent[0].get("reasoning_effort") == "none" and "reasoning_effort" not in sent[1]
