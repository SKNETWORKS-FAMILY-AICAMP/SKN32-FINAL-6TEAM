# -*- coding: utf-8 -*-
"""텔레그램 봇 — 메시지 한 건 보내기. `[2026-10-05 사용자 지시 「텔레그램만 붙여 · 알림만」 — ui 세션 요청서]`

★이 층은 **텔레그램과 말하는 일**만 한다(`sendMessage`). 누구에게 무엇을 보내는지는 `travel_ops/notice_routing.py` · `telegram_connect.py` 가 정한다.
★실패의 모양은 `DiscordWebhook` 의 규칙을 그대로 따른다(바깥함 일꾼이 읽는 예외):

    전송 성공(2xx)                       → 반환
    시간 초과 · 연결 끊김                 → TimeoutError / ConnectionError → 일꾼이 `unknown`(갔는지 모른다 — 자동 재전송 없음)
    너무 자주 보냄(429)                  → `RetryAfter` → 일꾼이 **텔레그램이 말한 시각**에 다시(헤더 `Retry-After` 또는 본문 `parameters.retry_after`)
    대화를 쓸 수 없음(403 · 400 chat not found) → `ChatUnavailable` — 고객이 봇을 차단했거나 대화가 없다. ★재시도해도 소용없다(호출한 쪽이 「막힘」으로 표시한다)
    그 밖(401 토큰 틀림 · 5xx …)          → RuntimeError → 일꾼이 재시도, 한도 넘으면 `dead_letter`

★본문은 **평문**이다(`parse_mode` 없음 — 특수문자로 깨지지 않게). 한 건 **4,096자** 이하(공식 문서 `sendMessage` 「1-4096 characters after entities parsing」 확인 2026-10-05) — 넘으면 자르되 잘랐다는 표시를 남긴다.
★★**봇 토큰은 요청 주소에 들어간다**(`/bot<토큰>/sendMessage`) — `httpx` 가 요청 주소를 INFO 로 찍으므로 그 기록은 **걸러낸다**(`_DropTokenRecords`). 오류 문구에도 주소 · 토큰 · 대화 번호를 싣지 않는다.
★`[미확인]` 429 응답의 대기 시간 칸 이름(`parameters.retry_after` 로 알려져 있다 — 공식 문서 페이지 요약에서 확인 못 함 → 헤더와 본문 둘 다 본다) · 차단된 대화의 정확한 오류 문구(상태 코드로 판정한다).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from .discord import RetryAfter

API = "https://api.telegram.org"
MAX_TEXT = 4096
#: 공급자가 말한 대기 시간을 받아들일 상한(초) — `discord.py` 와 같은 규칙(15분을 넘으면 안 믿고 우리 기본 간격)
MAX_RETRY_AFTER_SECONDS = 900.0
#: 시험이 바깥 호출을 가로채는 자리 — 실제 운영에서는 비어 있어 진짜 HTTP 로 간다
TRANSPORT: httpx.BaseTransport | None = None

logger = logging.getLogger(__name__)


class ChatUnavailable(RuntimeError):
    """그 대화로 보낼 수 없다(고객이 봇을 차단 · 대화 없음). ★메시지에 대화 번호 · 토큰을 싣지 않는다."""


class _DropTokenRecords(logging.Filter):
    """`httpx` 가 요청 주소를 INFO 로 찍는다(「HTTP Request: POST https://api.telegram.org/bot<토큰>/…」) — 봇 토큰이 든 기록은 버린다."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            return "api.telegram.org/bot" not in record.getMessage()
        except Exception:                                   # noqa: BLE001 — 문구를 못 만들면 그대로 둔다
            return True


for _name in ("httpx", "httpcore"):
    _logger = logging.getLogger(_name)
    if not any(isinstance(f, _DropTokenRecords) for f in _logger.filters):
        _logger.addFilter(_DropTokenRecords())


def cut(text: str) -> str:
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT - 12] + "\n…(잘림)"


def _retry_after(response: httpx.Response) -> float | None:
    raw: Any = response.headers.get("Retry-After")
    if raw is None:
        try:
            raw = ((response.json() or {}).get("parameters") or {}).get("retry_after")
        except Exception:                                   # noqa: BLE001
            raw = None
    try:
        seconds = float(raw)
    except (TypeError, ValueError):
        return None
    return None if seconds < 0 or seconds > MAX_RETRY_AFTER_SECONDS else seconds


def _chat_gone(response: httpx.Response) -> bool:
    """403(차단 · 탈퇴) 또는 400 「chat not found」 — 이 대화로는 더 못 보낸다. ★그 밖의 400 은 우리 쪽 잘못일 수 있어 「막힘」으로 보지 않는다."""
    if response.status_code == 403:
        return True
    if response.status_code == 400:
        try:
            return "chat not found" in str((response.json() or {}).get("description", "")).lower()
        except Exception:                                   # noqa: BLE001
            return False
    return False


def send_message(token: str, chat_id: int | str, text: str, *, timeout: float = 8.0, transport: httpx.BaseTransport | None = None) -> None:
    """`sendMessage` 한 번. 위 규칙대로 반환하거나 예외를 올린다. 토큰 · 대화 번호 · 본문은 어떤 예외 문구에도 싣지 않는다."""
    if not token:
        raise RuntimeError("telegram bot token is not configured")
    body = cut(text)
    if not body.strip():
        raise ValueError("빈 텔레그램 메시지를 보내지 않는다")
    try:
        with httpx.Client(transport=transport or TRANSPORT, timeout=httpx.Timeout(timeout), follow_redirects=False) as client:
            response = client.post(f"{API}/bot{token}/sendMessage", json={"chat_id": chat_id, "text": body})
    except httpx.TimeoutException as exc:
        raise TimeoutError(f"telegram timeout: {type(exc).__name__}") from None
    except httpx.TransportError as exc:
        raise ConnectionError(f"telegram transport: {type(exc).__name__}") from None
    if 200 <= response.status_code < 300:
        return
    if response.status_code == 429:
        seconds = _retry_after(response)
        raise RetryAfter("telegram 429 — %s 뒤에 다시 보낸다" % ("%.0f초" % seconds if seconds is not None else "기본 간격"), seconds)
    if _chat_gone(response):
        raise ChatUnavailable(f"telegram chat unavailable (HTTP {response.status_code})")
    raise RuntimeError(f"telegram HTTP {response.status_code}")


__all__ = ["API", "ChatUnavailable", "MAX_TEXT", "cut", "send_message"]
