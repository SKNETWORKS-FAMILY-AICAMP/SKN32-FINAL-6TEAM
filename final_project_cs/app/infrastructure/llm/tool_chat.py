# -*- coding: utf-8 -*-
"""도구를 부르는 모델 한 턴 — OpenAI · Ollama 를 같은 모양으로. `[2026-10-13 · 요식 판정 에이전트]`

에이전트(`instances/dining/agent.py`)는 팀 경계라 이 파일을 import 하지 않는다 — 부르는 쪽이 만들어 넣는다.
메시지는 OpenAI 모양(`role` · `content` · `tool_calls` · `tool_call_id`)으로 주고받고, Ollama 쪽은 여기서 바꿔 보낸다.

    turn = chat.step(messages, tools)      # tools = OpenAI 함수 정의 목록
    turn.tool_calls                        # [{"id", "name", "arguments": dict}] — 비면 turn.content 가 최종 답
    turn.usage                             # {"prompt_tokens", "completion_tokens"}

★실패는 예외(`ToolChatError`)로 올린다 — 빈 답을 성공처럼 돌려주지 않는다(`ollama_chat` 과 같은 원칙).
★Ollama 는 `think:false` · 온도 0. OpenAI 는 온도 0(지원하는 모델만).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx


class ToolChatError(RuntimeError):
    """모델을 못 불렀거나 답이 쓸 수 없는 모양이다."""


@dataclass
class ToolTurn:
    content: str | None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)

    def as_message(self) -> dict[str, Any]:
        """대화에 다시 넣을 assistant 메시지(OpenAI 모양)."""
        message: dict[str, Any] = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            message["tool_calls"] = [{"id": c["id"], "type": "function",
                                      "function": {"name": c["name"], "arguments": json.dumps(c["arguments"], ensure_ascii=False)}}
                                     for c in self.tool_calls]
        return message


class OpenAIToolChat:
    def __init__(self, *, api_key: str, model: str, timeout: float = 60.0, client: Any = None) -> None:
        self.model, self.timeout = model, float(timeout)
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, timeout=self.timeout, max_retries=1)
        self._client = client

    def step(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], *, final_json: bool = False) -> ToolTurn:
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        if final_json:
            kwargs["response_format"] = {"type": "json_object"}
        if not self.model.startswith(("o1", "o3", "o4", "gpt-5", "gpt-6")):
            kwargs["temperature"] = 0
        try:
            response = self._client.chat.completions.create(**kwargs)
            message = response.choices[0].message
        except Exception as exc:                      # noqa: BLE001 — SDK 예외 이름만 남긴다
            raise ToolChatError(f"OpenAI 호출 실패: {type(exc).__name__}: {str(exc)[:160]}") from None
        calls = []
        for call in message.tool_calls or []:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except ValueError:
                arguments = {"_unparsed": call.function.arguments}
            calls.append({"id": call.id, "name": call.function.name, "arguments": arguments})
        usage = getattr(response, "usage", None)
        return ToolTurn(content=message.content, tool_calls=calls,
                        usage={"prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                               "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0)})


class OllamaToolChat:
    def __init__(self, *, base_url: str, model: str, timeout: float = 120.0, keep_alive: str = "30m",
                 post: Callable[..., httpx.Response] | None = None) -> None:
        if not base_url:
            raise ToolChatError("Ollama 주소가 비어 있다")
        self.base_url, self.model, self.timeout, self.keep_alive = base_url.rstrip("/"), model, float(timeout), keep_alive
        self._post = post or (lambda url, payload: httpx.post(url, json=payload,
                                                             timeout=httpx.Timeout(self.timeout, connect=5.0)))

    @staticmethod
    def _messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        names = {}
        out = []
        for m in messages:
            if m["role"] == "assistant" and m.get("tool_calls"):
                for c in m["tool_calls"]:
                    names[c["id"]] = c["function"]["name"]
                out.append({"role": "assistant", "content": m.get("content") or "",
                            "tool_calls": [{"function": {"name": c["function"]["name"],
                                                         "arguments": json.loads(c["function"]["arguments"] or "{}")}}
                                           for c in m["tool_calls"]]})
            elif m["role"] == "tool":
                out.append({"role": "tool", "content": m["content"], "tool_name": names.get(m.get("tool_call_id"), "")})
            else:
                out.append({"role": m["role"], "content": m["content"]})
        return out

    def step(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], *, final_json: bool = False) -> ToolTurn:
        payload: dict[str, Any] = {"model": self.model, "stream": False, "think": False, "options": {"temperature": 0},
                                   "messages": self._messages(messages), "keep_alive": self.keep_alive}
        if tools:
            payload["tools"] = tools
        if final_json:
            payload["format"] = "json"
        try:
            response = self._post(f"{self.base_url}/api/chat", payload)
        except httpx.HTTPError as exc:
            raise ToolChatError(f"Ollama 호출 실패: {type(exc).__name__}: {exc}") from exc
        if response.status_code != 200:
            raise ToolChatError(f"Ollama HTTP {response.status_code}: {response.text[:160]}")
        try:
            body = response.json()
            message = body["message"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ToolChatError(f"Ollama 응답 모양이 다르다: {response.text[:160]}") from exc
        calls = []
        for i, call in enumerate(message.get("tool_calls") or []):
            fn = call.get("function") or {}
            arguments = fn.get("arguments")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except ValueError:
                    arguments = {"_unparsed": arguments}
            calls.append({"id": call.get("id") or f"o{len(messages)}_{i}", "name": fn.get("name"), "arguments": arguments or {}})
        return ToolTurn(content=message.get("content"), tool_calls=calls,
                        usage={"prompt_tokens": int(body.get("prompt_eval_count") or 0),
                               "completion_tokens": int(body.get("eval_count") or 0)})


__all__ = ["OllamaToolChat", "OpenAIToolChat", "ToolChatError", "ToolTurn"]
