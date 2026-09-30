# -*- coding: utf-8 -*-
"""Ollama 자체 API — 생각 끄기·JSON 강제로 부르고, 쓸 수 없는 답은 **실패로** 올린다."""
from __future__ import annotations

import httpx
import pytest

from app.infrastructure.ollama_chat import OllamaChat, OllamaError


def _chat(status=200, body=None, text=None):
    seen = {}

    def transport(url, payload):
        seen.update(url=url, payload=payload)
        request = httpx.Request("POST", url)
        if text is not None:
            return httpx.Response(status, text=text, request=request)
        return httpx.Response(status, json=body, request=request)
    return OllamaChat(base_url="http://127.0.0.1:11434/", model="gemma4:12b",
                      transport=transport), seen


def test_json_mode_turns_thinking_off_and_asks_for_json():
    chat, seen = _chat(body={"message": {"content": '{"type": "delay", "minutes": 70}'}})
    assert chat.json("sys", "user") == {"type": "delay", "minutes": 70}
    assert seen["url"] == "http://127.0.0.1:11434/api/chat"
    assert seen["payload"]["think"] is False and seen["payload"]["format"] == "json"
    assert seen["payload"]["model"] == "gemma4:12b"


@pytest.mark.parametrize("kwargs", [
    {"body": {"message": {"content": ""}}},                 # ☆실측: 생각에 토큰을 다 쓰면 빈 답
    {"body": {"message": {"content": "not json"}}},
    {"body": {"message": {"content": "[1, 2]"}}},
    {"status": 500, "text": "boom"},
    {"body": {"unexpected": True}},
])
def test_unusable_answers_raise(kwargs):
    chat, _ = _chat(**kwargs)
    with pytest.raises(OllamaError):
        chat.json("sys", "user")


def test_an_empty_base_url_is_refused():
    with pytest.raises(OllamaError):
        OllamaChat(base_url="", model="m")


def test_keep_alive_is_sent_only_when_set():
    """★`[2026-09-29]` 잠든 모델의 첫 호출이 30초 가까이 걸렸다(ui 세션 실측) — 붙잡아 둘 시간을 설정으로 싣는다.
    비우면 싣지 않는다(Ollama 기본 5분 — 원격 GPU 메모리를 더 잡지 않는다)."""
    chat, seen = _chat(body={"message": {"content": "{}"}})
    chat.json("sys", "user")
    assert "keep_alive" not in seen["payload"]
    chat.keep_alive = "30m"
    chat.json("sys", "user")
    assert seen["payload"]["keep_alive"] == "30m"
    chat.see("읽어 주세요", b"\x89PNG")
    assert seen["payload"]["keep_alive"] == "30m"
