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
                 transport: Callable[..., httpx.Response] | None = None, keep_alive: str = "") -> None:
        if not base_url:
            raise OllamaError("Ollama 주소가 비어 있다")
        self.base_url, self.model, self.timeout = base_url.rstrip("/"), model, timeout
        #: ★`[2026-09-29]` 모델을 메모리에 붙잡아 둘 시간(Ollama `keep_alive`, 예 "30m"). 비우면 Ollama 기본(5분) —
        #:  5분 안 쓰이면 내려가서 다음 첫 호출이 30초 가까이 걸렸다(ui 세션 실측 29.8초). 원격 GPU 메모리를 그만큼 잡는다
        self.keep_alive = keep_alive
        self._injected = transport is not None      # 시험이 넣은 가짜 — 받아쓰기도 이것을 쓴다
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
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive
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

    def structured(self, system: str, user: str, schema: dict[str, Any], *, num_predict: int = 160) -> dict[str, Any]:
        """★`[2026-09-29]` 결정 단위 — Ollama `format` 에 **JSON 스키마**를 준다(enum 밖 값을 못 낸다). `think:false` ·
        temperature 0 · 짧은 답(`num_predict`). 실측(화면 세션, gemma4:12b): 25문장 중 24 맞음, 2.0~3.2초."""
        payload: dict[str, Any] = {
            "model": self.model, "stream": False, "think": False, "format": schema,
            "options": {"temperature": 0, "num_predict": int(num_predict)},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive
        try:
            response = self._post(f"{self.base_url}/api/chat", payload)
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama 호출 실패: {type(exc).__name__}: {exc}") from exc
        if response.status_code != 200:
            raise OllamaError(f"Ollama HTTP {response.status_code}: {response.text[:160]}")
        try:
            value = json.loads(response.json()["message"]["content"])
        except (ValueError, KeyError, TypeError) as exc:
            raise OllamaError(f"구조화 답이 JSON 이 아니다: {response.text[:160]}") from exc
        if not isinstance(value, dict):
            raise OllamaError("구조화 답이 JSON 객체가 아니다")
        return value

    # ── 예열 `[2026-09-29]` — 식은 모델의 첫 호출이 30초 넘게 걸렸다(ui 세션 실측). 화면이 채팅을 열 때 미리 깨운다 ──
    def loaded(self, *, timeout: float = 5.0) -> bool:
        """이 모델이 지금 메모리에 올라가 있나(`/api/ps`). 못 물으면 `OllamaError`."""
        try:
            response = httpx.get(f"{self.base_url}/api/ps", timeout=timeout)
            models = response.json().get("models") or []
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError(f"Ollama 상태 조회 실패: {type(exc).__name__}: {exc}") from exc
        return any(m.get("name") == self.model or m.get("model") == self.model for m in models)

    def warm(self) -> None:
        """아주 짧은 생성 한 번(한 토큰)으로 모델을 올린다. 실패하면 `OllamaError`(모델 서버가 준 이유 그대로)."""
        payload: dict[str, Any] = {"model": self.model, "stream": False, "think": False,
                                   "options": {"temperature": 0, "num_predict": 1},
                                   "messages": [{"role": "user", "content": "."}]}
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive
        try:
            response = self._post(f"{self.base_url}/api/chat", payload)
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama 호출 실패: {type(exc).__name__}: {exc}") from exc
        if response.status_code != 200:
            raise OllamaError(f"Ollama HTTP {response.status_code}: {response.text[:200]}")

    def see(self, prompt: str, image: bytes, *, timeout: float = 240.0) -> str:
        """이미지 한 장을 보고 글로 답한다(비전). `[2026-09-27]` 계획 읽기의 **받아쓰기** 전용.

        ★실측(2026-09-26, triPilot : RAG): 「사진 → 일정 JSON」을 한 번에 시키면 6항목 중 3을 잃었고,
          「한 줄씩 그대로 받아 적어라」만 시키면 6/6 을 그대로 적었다(쪽당 약 45초). 그래서 구조화를 시키지 않는다.
        ★실패는 예외(`OllamaError`) — 빈 받아쓰기를 성공처럼 돌려주지 않는다.
        """
        import base64

        payload: dict[str, Any] = {
            "model": self.model, "stream": False, "think": False, "options": {"temperature": 0},
            "messages": [{"role": "user", "content": prompt,
                          "images": [base64.b64encode(image).decode("ascii")]}]}
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive
        try:
            if self._injected:
                response = self._post(f"{self.base_url}/api/chat", payload)
            else:                                       # ★받아쓰기는 쪽당 45초 안팎 — 긴 제한시간
                response = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=timeout)
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama 호출 실패: {type(exc).__name__}: {exc}") from exc
        if response.status_code != 200:
            raise OllamaError(f"Ollama HTTP {response.status_code}: {response.text[:160]}")
        try:
            content = response.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise OllamaError(f"Ollama 응답 모양이 다르다: {response.text[:160]}") from exc
        if not isinstance(content, str) or not content.strip():
            raise OllamaError("Ollama 가 빈 받아쓰기를 냈다")
        return content.strip()


def from_settings(settings: Any) -> OllamaChat | None:
    """설정에 주소가 있으면 클라이언트, 없으면 `None`."""
    base = (getattr(settings, "ollama_base_url", "") or "").strip()
    if not base:
        return None
    return OllamaChat(base_url=base, model=getattr(settings, "ollama_model", "gemma4:12b"),
                      timeout=float(getattr(settings, "ollama_timeout_seconds", 60.0)),
                      keep_alive=str(getattr(settings, "ollama_keep_alive", "") or ""))


__all__ = ["OllamaChat", "OllamaError", "from_settings"]
