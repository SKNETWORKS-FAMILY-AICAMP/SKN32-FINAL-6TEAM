# -*- coding: utf-8 -*-
"""운영자 알림 — 고객 통지가 아니다. 바깥함(`outbox`)을 타지 않고 곧장 웹훅으로 보낸다.

★보낼 곳은 `ops_alert_webhook_url`, 비었으면 `discord_webhook_url`(`scripts/ops/guard.py` 와 같은 규칙).
★보낼 곳이 없으면 **보내지 않고 그렇게 돌려준다** — 조용히 성공한 척하지 않는다.
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


def send_ops_alert(text: str) -> str:
    """보낸 결과 한 줄. ★실패해도 예외를 올리지 않는다 — 알림 때문에 본 작업이 멈추면 안 된다."""
    from app.core.settings import get_settings

    settings = get_settings()
    url = getattr(settings, "ops_alert_webhook_url", "") or settings.discord_webhook_url
    if not url:
        logger.warning("ops alert not sent (no webhook): %s", text)
        return "보낼 곳이 없다(ACOP_DISCORD_WEBHOOK_URL 이 비어 있다) — 알리지 않았다"
    try:
        response = httpx.post(url, json={"content": f"[triPilot 운영] {text}"[:2000]}, timeout=8.0)
    except Exception as exc:                      # noqa: BLE001
        logger.warning("ops alert failed: %s", exc)
        return f"알림 실패: {type(exc).__name__}: {exc}"[:160]
    if not 200 <= response.status_code < 300:
        logger.warning("ops alert failed: HTTP %s", response.status_code)
        return f"알림 실패: HTTP {response.status_code}"
    return "알림 보냄"


def google_over_free_alert(meter: str, used: int, free: int) -> str:
    """구글 요금 단위가 이번 달 무료 한도를 넘었다 — `GooglePlaces(on_over_free=...)` 자리에 끼운다."""
    return send_ops_alert(f"구글 **{meter}** 가 이번 달 무료 한도 {free:,}건을 넘었습니다(지금 {used:,}건). "
                          f"식당 가격대 조회는 계속 부르므로 이후 호출은 과금됩니다.")


__all__ = ["google_over_free_alert", "send_ops_alert"]
