# -*- coding: utf-8 -*-
"""관리 콘솔 「모델 경로」 — 상황마다(채팅 · 일정 짚기 · 공지 확인) 로컬 모델 · SSH(런팟 GPU 서버) · 유료 API 중 고른 경로가 먼저 불리고,
「끔」이면 환경 파일(`ACOP_MODEL_ROUTE_<상황>`)을 따른다. `[2026-10-15 · 10-16 사용자 지시]`

★여기 시험은 전부 클라이언트를 **조립만** 해 보거나 mock 서버를 꽂는다 — 실제 Ollama · 실제 유료 API 는 부르지 않는다(키 값도 시험용 글자다).
"""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.domains.travel_ops.components import settings_hook
from app.domains.travel_ops.components.conversation.item_pointer import OllamaItemPointer
from app.domains.travel_ops.modules.web_account import web_guard
from app.infrastructure import ollama_chat
from app.infrastructure.llm_failover import FailoverChat
from app.infrastructure.ollama_chat import OllamaChat, RoutedChat, from_settings, resolve_route, route_base_url

KEY = "sk-test-NOT-A-REAL-KEY-0123456789"
LOCAL = "http://local-ollama.test:11434"
SSH = "http://ssh-tunnel.test:11435"


def settings(**over):
    base = dict(ollama_base_url=LOCAL, ollama_ssh_base_url=SSH, ollama_model="tripilot-pointer:e4b-ft", ollama_timeout_seconds=60.0,
                ollama_keep_alive="", ollama_num_ctx=8192, llm_failover_enabled=False, openai_api_key_server=KEY, llm_model="gpt-4o-mini",
                llm_failover_model="gpt-4.1", llm_failover_primary_timeout_seconds=9.0, llm_failover_api_timeout_seconds=8.0,
                llm_failover_total_seconds=15.0, llm_failover_failures=3, llm_failover_open_seconds=60.0, llm_failover_vision=False,
                ollama_fallback_base_urls="", llm_failover_daily_cap=2000, llm_failover_monthly_cap=30000,
                model_route_chat="local", model_route_pointer="local", model_route_notice="local")
    base.update(over)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _clean():
    ollama_chat.register_route_provider(None)
    settings_hook.clear()
    yield
    ollama_chat.register_route_provider(None)
    settings_hook.clear()


def route(value, purpose=None):
    """콘솔 값 — purpose 를 주면 그 상황만 그 값이고 나머지는 off."""
    ollama_chat.register_route_provider(lambda asked: value if purpose in (None, asked) else "off")


def order(chat):
    """넘김 순서 — (이름, 주소 또는 'api')."""
    return [(b.name, "api" if b.is_api else b.chat.base_url) for b in chat._backends]


# ── 콘솔이 꽂히지 않았을 때 — 환경 파일 경로 ──
def test_without_a_route_provider_the_plain_local_client_is_returned():
    chat = from_settings(settings())
    assert type(chat) is OllamaChat and chat.base_url == LOCAL


def test_without_a_route_provider_the_env_route_is_used():
    assert from_settings(settings(model_route_chat="ssh")).base_url == SSH


def test_no_local_address_still_means_no_chat_whatever_the_route():
    route("api")
    assert from_settings(settings(ollama_base_url="")) is None


# ── 콘솔 「끔」 = 환경 파일 ──
@pytest.mark.parametrize("env, expected", [("local", LOCAL), ("ssh", SSH)])
def test_console_off_follows_the_env_file(env, expected):
    route("off")
    assert from_settings(settings(model_route_chat=env)).target().base_url == expected


def test_console_off_with_env_api_puts_the_api_first():
    route("off")
    assert order(from_settings(settings(model_route_chat="api")).target())[0] == ("openai", "api")


def test_console_value_wins_over_the_env_file():
    route("local")
    assert from_settings(settings(model_route_chat="ssh")).target().base_url == LOCAL


def test_env_value_outside_the_list_means_local():
    assert resolve_route(settings(model_route_pointer="api"), "pointer") == "local"


# ── 고른 경로 ──
def test_local_route_calls_this_machines_ollama():
    route("local")
    chat = from_settings(settings())
    assert isinstance(chat, RoutedChat)
    assert type(chat.target()) is OllamaChat and chat.base_url == LOCAL and chat.model == "tripilot-pointer:e4b-ft"


def test_ssh_route_calls_the_tunnel_entrance_with_the_same_trained_model():
    route("ssh")
    target = from_settings(settings()).target()
    assert type(target) is OllamaChat and target.base_url == SSH and target.model == "tripilot-pointer:e4b-ft"


def test_ssh_route_with_failover_on_falls_back_to_local_then_the_api():
    route("ssh")
    target = from_settings(settings(llm_failover_enabled=True)).target()
    assert isinstance(target, FailoverChat)
    assert order(target) == [("ollama", SSH), ("ollama2", LOCAL), ("openai", "api")]


def test_ssh_route_without_a_tunnel_address_uses_local():
    route("ssh")
    target = from_settings(settings(ollama_ssh_base_url="")).target()
    assert type(target) is OllamaChat and target.base_url == LOCAL


@pytest.mark.parametrize("failover", [False, True])
def test_api_route_puts_the_api_first_and_local_after_even_when_failover_is_off(failover):
    route("api")
    target = from_settings(settings(llm_failover_enabled=failover)).target()
    assert isinstance(target, FailoverChat)
    assert order(target) == [("openai", "api"), ("ollama", LOCAL)]


def test_api_route_without_the_server_key_uses_local():
    route("api")
    target = from_settings(settings(openai_api_key_server="")).target()
    assert type(target) is OllamaChat and target.base_url == LOCAL


@pytest.mark.parametrize("value", ["gpu", "", None])
def test_unknown_console_value_means_the_env_file(value):
    route(value)
    assert from_settings(settings(model_route_chat="ssh")).target().base_url == SSH


def test_unreadable_console_value_means_the_env_file():
    def broken(purpose):
        raise RuntimeError("settings table down")

    ollama_chat.register_route_provider(broken)
    assert ollama_chat.console_choice("chat") == "off"
    assert from_settings(settings()).target().base_url == LOCAL


def test_a_held_client_follows_a_later_console_change_without_restart():
    chosen = {"value": "off"}
    ollama_chat.register_route_provider(lambda purpose: chosen["value"])
    chat = from_settings(settings())                      # 조립 때 한 번 만들어 오래 들고 있는 자리
    assert chat.base_url == LOCAL
    chosen["value"] = "ssh"
    assert chat.base_url == SSH
    chosen["value"] = "api"
    assert order(chat.target())[0] == ("openai", "api")


# ── 상황마다 따로 ──
def test_each_situation_reads_its_own_console_value():
    route("ssh", purpose="pointer")
    assert from_settings(settings()).target().base_url == LOCAL               # 채팅은 off → 환경 파일 local
    assert route_base_url(settings(), "pointer") == SSH
    assert route_base_url(settings(), "notice") == LOCAL


def test_trained_model_seats_cannot_take_the_api():
    route("api")                                                              # 채팅만 api 를 받는다
    assert route_base_url(settings(model_route_pointer="ssh"), "pointer") == SSH      # 목록 밖 콘솔 값 → 환경 파일
    assert route_base_url(settings(), "notice") == LOCAL


@pytest.mark.parametrize("chosen, expected", [("local", LOCAL), ("ssh", SSH), ("api", LOCAL)])
def test_trained_model_seats_follow_local_or_ssh_and_stay_local_for_api(chosen, expected):
    assert route_base_url(settings(), "pointer", chosen) == expected


def test_trained_model_seats_use_local_when_the_tunnel_address_is_empty():
    assert route_base_url(settings(ollama_ssh_base_url=""), "notice", "ssh") == LOCAL


def test_item_pointer_calls_the_address_chosen_at_call_time():
    seen: list[str] = []

    def post(url, payload, timeout):
        seen.append(url)
        return httpx.Response(200, json={"message": {"content": '{"n": 1}'}}, request=httpx.Request("POST", url))

    pointer = OllamaItemPointer(base_url=LOCAL, model="tripilot-pointer:e4b-ft", post=post)
    chosen = {"value": LOCAL}
    pointer.base_url_for = lambda: chosen["value"]
    pointer._ask("prompt")
    chosen["value"] = SSH
    pointer._ask("prompt")
    assert seen == [f"{LOCAL}/api/chat", f"{SSH}/api/chat"]


@pytest.mark.parametrize("resolver", [lambda: "", lambda: (_ for _ in ()).throw(RuntimeError("down"))])
def test_item_pointer_keeps_its_fixed_address_when_the_resolver_is_empty_or_broken(resolver):
    pointer = OllamaItemPointer(base_url=LOCAL, model="m", post=lambda *a: None)
    pointer.base_url_for = resolver
    assert pointer.current_base_url() == LOCAL


# ── 관리 콘솔 값 ──
@pytest.mark.parametrize("purpose, choices", [("chat", ("off", "local", "ssh", "api")), ("pointer", ("off", "local", "ssh")),
                                              ("notice", ("off", "local", "ssh"))])
def test_each_situation_is_listed_for_the_admin_console_and_off_by_default(purpose, choices):
    spec = web_guard.specs()[settings_hook.MODEL_ROUTE_KEYS[purpose]]
    assert spec.type == "choice" and spec.default == "off" and spec.choices == choices
    assert spec.check("gpu") == "not_a_choice"
    shown = spec.as_dict()
    assert set(shown["choice_labels_ko"]) == set(choices) and "환경 파일" in shown["choice_labels_ko"]["off"]
    assert "환경 파일" in shown["text_ko"] and KEY not in shown["text_ko"]


def test_chat_keeps_the_first_key_so_an_already_saved_value_still_applies():
    assert settings_hook.MODEL_ROUTE_KEYS["chat"] == "llm.model_route"


def test_without_console_value_the_choice_is_off():
    assert settings_hook.model_route_choice("t1", "chat") == "off"


@pytest.mark.parametrize("stored", ["off", "local", "ssh", "api"])
def test_console_value_is_returned(stored):
    settings_hook.register(lambda tenant, name: stored if name == settings_hook.MODEL_ROUTE else None)
    assert settings_hook.model_route_choice("t1", "chat") == stored


@pytest.mark.parametrize("stored", ["api", "gpu", 1, None, True])
def test_value_outside_the_situations_list_is_off(stored):
    settings_hook.register(lambda tenant, name: stored)
    assert settings_hook.model_route_choice("t1", "pointer") == "off"
