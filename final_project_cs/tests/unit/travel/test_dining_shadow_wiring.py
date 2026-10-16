# -*- coding: utf-8 -*-
"""판정 에이전트(그림자)의 도구에 바깥 조회를 꽂는다 — 원장이 모를 때 지도(카카오) · 실시간 영업(구글)을 에이전트가 고를 수 있게. `[2026-10-16]`

☆LLM 켜짐 점검(2026-10-16): 스위치를 켜도 그림자 실행기가 `DiningTools(connect)` 기본값으로 도구를 만들어 `kakao` · `google` 이
  None 이었다 — `map_search` 는 「지도 검색을 부를 수 없다」, `live_open_check` 는 늘 `unknown`. 조립이 같은 어댑터를 넘긴다.
★키가 없으면 그 도구만 「모름」으로 남는다(실행기 자체는 만든다) — 어댑터 조립 함수가 None 을 돌려주는 것과 같다.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture()
def shadow_on(monkeypatch):
    from app import composition
    from app.core import settings as settings_module

    monkeypatch.setattr(settings_module, "dining_agent_shadow",
                        lambda: {"model": "openai:gpt-6-luna", "deadline_s": 120.0})
    monkeypatch.setattr(settings_module, "get_settings",
                        lambda: SimpleNamespace(openai_api_key="sk-test", ollama_base_url="", ollama_model=""))
    return composition


def _tools(runner):
    from app.domains.travel_ops.instances.dining.agent_tools import DiningTools

    factory = runner.keywords.get("tools_factory")
    assert factory is not None, "그림자 실행기가 도구 공장을 넘기지 않는다 — 기본 DiningTools(connect) 로 바깥 조회가 빠진다"
    tools = factory(lambda: None)
    assert isinstance(tools, DiningTools)
    return tools


def test_the_shadow_tools_get_the_map_and_live_hours_adapters(shadow_on, monkeypatch):
    kakao, google = object(), object()
    monkeypatch.setattr(shadow_on, "build_kakao_local", lambda: kakao)
    monkeypatch.setattr(shadow_on, "build_google_places", lambda **_: google)
    tools = _tools(shadow_on._dining_agent_shadow())
    assert tools.kakao is kakao and tools.google is google


def test_without_keys_the_shadow_still_runs_and_those_tools_say_unknown(shadow_on, monkeypatch):
    monkeypatch.setattr(shadow_on, "build_kakao_local", lambda: None)
    monkeypatch.setattr(shadow_on, "build_google_places", lambda **_: None)
    tools = _tools(shadow_on._dining_agent_shadow())
    assert tools.kakao is None and tools.google is None
    assert tools.call("map_search", {"query": "하동관"})["hits"] == []
