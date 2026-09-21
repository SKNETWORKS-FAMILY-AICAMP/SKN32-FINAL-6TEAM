# -*- coding: utf-8 -*-
"""디스코드 웹훅 — v11 §6-A 의 알림 채널(무료 채널 중 가장 간단한 것 하나).

★바깥함 일꾼(`OutboxWorker`)의 발행자 자리에 끼운다. 일꾼의 규칙을 그대로 따른다:

    전송 성공(2xx)                   → 반환 → 일꾼이 `delivered`
    타임아웃·연결 끊김                → TimeoutError / ConnectionError
                                       → 일꾼이 **`unknown`** — 갔는지 모른다.
                                         성공으로 추정하지 않고 자동 재전송도 안 한다
                                         (CLAUDE.md §0.2). 같은 알림이 두 번 가는 것도
                                         사고다.
    그 밖의 실패(429·5xx·4xx)         → RuntimeError → 일꾼이 재시도, 한도 넘으면
                                         `dead_letter`

★★**웹훅이 설정돼 있지 않으면 실패로 올린다**(`NoticeNotConfigured`). 조용히 반환하면
  일꾼이 `delivered` 로 찍는다 — **보내지 않은 알림이 보낸 것으로 기록된다.** 그게
  이 저장소가 여러 번 데인 「조용한 성공 위장」이다.

★재생 통지에는 **`[재생]` 을 앞에 붙인다**(v11 §8-A). 시연 알림을 실제 사건 알림으로
  읽지 않게 한다.

★디스코드 메시지 본문 한도는 2,000자다. 넘으면 자르되 잘랐다는 표시를 남긴다.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

import httpx

logger = logging.getLogger(__name__)

MAX_CONTENT = 2000


class NoticeNotConfigured(RuntimeError):
    """보낼 곳이 설정되지 않았다. ★보낸 것으로 기록되면 안 된다."""


def render(payload: dict[str, Any]) -> str:
    """통지 payload → 사람에게 보일 한 덩어리 글."""
    text = str(payload.get("text") or "").strip()
    if not text:
        raise ValueError("통지 본문이 비어 있다 — 빈 알림을 보내지 않는다")
    lines = [("[재생] " if payload.get("replay") else "") + text]
    others = payload.get("other_options") or []
    if others and "다른 안" not in text:
        lines.append("다른 안: " + ", ".join(map(str, others)))
    if payload.get("version") is not None:
        lines.append(f"(일정 버전 {payload['version']})")
    if payload.get("plan_url"):
        # ★상태의 정본은 링크다(v11 §6-A) — 안내에는 늘 붙인다.
        lines.append(str(payload["plan_url"]))
    content = "\n".join(lines)
    if len(content) > MAX_CONTENT:
        content = content[:MAX_CONTENT - 12] + "\n…(잘림)"
    return content


class DiscordWebhook:
    """`OutboxWorker` 의 발행자. 다룰 주제만 보내고 나머지는 넘긴다."""

    TOPICS = frozenset({"trip.notice"})

    def __init__(self, url: str, *, timeout: float = 8.0,
                 transport: Callable[..., httpx.Response] | None = None,
                 fallback: Callable[[dict[str, Any]], Any] | None = None,
                 translator: Callable[[str, str], str] | None = None) -> None:
        self.url = url
        self._timeout = timeout
        self._post = transport or self._http_post
        # ★다른 주제는 원래 발행자에게 넘긴다. 이 파일이 모든 주제를 삼키지 않는다.
        self._fallback = fallback
        # ★보낼 때 고객 언어로 옮긴다(결정 14). 없으면 한국어 원문 그대로.
        self._translator = translator
        self.translation_failures = 0

    def _localize(self, content: str, locale: str | None) -> str:
        """★번역이 실패해도 알림은 보낸다 — 원문에 실패 표시를 붙인다(안 보내는 것보다 낫다).
        실패는 세어 둔다(조용한 스킵 금지)."""
        from .translate import is_korean

        if self._translator is None or is_korean(locale):
            return content
        try:
            return self._translator(content, str(locale))
        except Exception as exc:
            self.translation_failures += 1
            logger.warning("notice translation failed (%s): %s", locale, exc)
            return f"[번역 실패 — 한국어 원문] {content}"

    def _http_post(self, url: str, json: dict[str, Any]) -> httpx.Response:
        return httpx.post(url, json=json, timeout=self._timeout)

    def __call__(self, message: dict[str, Any]) -> None:
        if message.get("topic") not in self.TOPICS:
            if self._fallback is not None:
                return self._fallback(message)
            return None
        if not self.url:
            raise NoticeNotConfigured(
                "ACOP_DISCORD_WEBHOOK_URL 이 비어 있다 — 알림을 보내지 않았다")
        payload = message.get("payload") or {}
        content = self._localize(render(payload), payload.get("locale"))
        if len(content) > MAX_CONTENT:
            content = content[:MAX_CONTENT - 12] + "\n…(잘림)"
        try:
            response = self._post(self.url, json={"content": content})
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"discord webhook timeout: {exc}") from exc
        except httpx.TransportError as exc:
            raise ConnectionError(f"discord webhook transport: {exc}") from exc
        if not 200 <= response.status_code < 300:
            raise RuntimeError(f"discord webhook HTTP {response.status_code}: "
                               f"{response.text[:200]}")
        return None


__all__ = ["DiscordWebhook", "MAX_CONTENT", "NoticeNotConfigured", "render"]
