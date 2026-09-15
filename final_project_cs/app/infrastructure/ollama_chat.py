# -*- coding: utf-8 -*-
"""Ollama 자체 API(`/api/chat`) 한 번 부르기 — 분류·추출·번역이 같이 쓴다.

실측(2026-09-14, Gemma 4):
    OpenAI 호환 `/v1/chat/completions` → 본문에 생각(thinking)이 섞이거나(토큰 1500)
                                          비어서(토큰 300) 왔다 — **쓰지 않는다**
    자체 `/api/chat` + `think:false` + `format:"json"` → `gemma4:12b` 1.3초, JSON 정확
    모델을 바꿔 부르면 GPU 에서 갈아 끼우느라 첫 호출이 30초를 넘는다 — 한 모델만 쓴다

★실패는 예외(`OllamaError`)로 올린다. 부르는 쪽이 그것을 「모름」으로 바꾼다 —
  여기서 빈 값을 성공처럼 돌려주지 않는다.
"""
from __future__ import annotations

import json
from typing import Any, Callable

import httpx


class OllamaError(RuntimeError):
    """Ollama 를 못 불렀거나 답이 쓸 수 없는 모양이다."""


class OllamaChat:
    def __init__(self, *, base_url: str, model: str, timeout: float = 60.0,
                 transport: Callable[..., httpx.Response] | None = None) -> None:
        if not base_url:
            raise OllamaError("Ollama 주소가 비어 있다")
        self.base_url, self.model, self.timeout = base_url.rstrip("/"), model, timeout
        self._post = transport or (lambda url, payload: httpx.post(url, json=payload,
                                                                  timeout=self.timeout))

    def _chat(self, system: str, user: str, *, json_mode: bool) -> str:
        payload: dict[str, Any] = {
            "model": self.model, "stream": False, "think": False,
            "options": {"temperature": 0},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}]}
        if json_mode:
            payload["format"] = "json"
        try:
            response = self._post(f"{self.base_url}/api/chat", payload)
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama 호출 실패: {type(exc).__name__}: {exc}") from exc
        if response.status_code != 200:
            raise OllamaError(f"Ollama HTTP {response.status_code}: {response.text[:160]}")
        try:
            content = response.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise OllamaError(f"Ollama 응답 모양이 다르다: {response.text[:160]}") from exc
        if not isinstance(content, str) or not content.strip():
            raise OllamaError("Ollama 가 빈 답을 냈다")
        return content.strip()

    def json(self, system: str, user: str) -> dict[str, Any]:
        text = self._chat(system, user, json_mode=True)
        try:
            value = json.loads(text)
        except ValueError as exc:
            raise OllamaError(f"JSON 이 아니다: {text[:160]}") from exc
        if not isinstance(value, dict):
            raise OllamaError("JSON 객체가 아니다")
        return value

    def text(self, system: str, user: str) -> str:
        return self._chat(system, user, json_mode=False)


def from_settings(settings: Any) -> OllamaChat | None:
    """설정에 주소가 있으면 클라이언트, 없으면 `None`."""
    base = (getattr(settings, "ollama_base_url", "") or "").strip()
    if not base:
        return None
    return OllamaChat(base_url=base, model=getattr(settings, "ollama_model", "gemma4:12b"),
                      timeout=float(getattr(settings, "ollama_timeout_seconds", 60.0)))


__all__ = ["OllamaChat", "OllamaError", "from_settings"]
