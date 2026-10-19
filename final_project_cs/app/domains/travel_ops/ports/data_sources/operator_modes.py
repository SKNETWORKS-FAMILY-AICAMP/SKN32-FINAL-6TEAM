# -*- coding: utf-8 -*-
"""관리 콘솔의 두 모드를 바깥 호출 문이 읽는 **끼움 자리**. `[2026-10-19 사용자 결정]`

- 언리미티드 모드(`unlimited()`) — 켜면 바깥 API 호출 한도를 풀고 세기만 한다. 읽는 곳: `RateLimiter.acquire`(호출 간격) ·
  `CallBudget.reserve`(하루 · 월 줄 · 운영자 상한 · 몫) · 유료 대체 모델 넘김 예산.
- 숙소 모드(`lodging_mode()`) — "demo" · "test" · "off". 읽는 곳: 구글 호텔 어댑터의 호출 문(`LodgingModeLimiter`).

★ports 는 운영 설정 표를 모른다 — 조립(`app.composition.wire_optional_features`)이 `settings_hook` 을 읽는 함수를 꽂는다.
  아무도 꽂지 않으면(시험 · 도구) 기본값이다: 언리미티드 꺼짐 · 숙소 모드 off. 읽다가 오류가 나도 같은 기본값이다 —
  한도를 푸는 것과 유료 호출을 켜는 것은 **명시한 경우뿐**이다.
"""
from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)

LODGING_MODES = ("demo", "test", "off")

_unlimited: Callable[[], bool] | None = None
_lodging: Callable[[], str] | None = None


def register(*, unlimited: Callable[[], bool] | None = None, lodging_mode: Callable[[], str] | None = None) -> None:
    """조립 때 한 번. 다시 부르면 준 것만 교체한다."""
    global _unlimited, _lodging
    if unlimited is not None:
        _unlimited = unlimited
    if lodging_mode is not None:
        _lodging = lodging_mode


def clear() -> None:
    global _unlimited, _lodging
    _unlimited = None
    _lodging = None


def unlimited() -> bool:
    """언리미티드 모드가 켜져 있나. 안 꽂혔거나 못 읽으면 False."""
    if _unlimited is None:
        return False
    try:
        return _unlimited() is True
    except Exception as exc:                            # noqa: BLE001 — 못 읽으면 한도를 지킨다
        logger.warning("unlimited mode unreadable — limits kept: %s: %s", type(exc).__name__, exc)
        return False


def lodging_mode() -> str:
    """숙소 모드. 안 꽂혔거나 못 읽거나 목록 밖이면 "off"(구글 호텔을 부르지 않는다)."""
    if _lodging is None:
        return "off"
    try:
        value = _lodging()
    except Exception as exc:                            # noqa: BLE001 — 못 읽으면 부르지 않는다
        logger.warning("lodging mode unreadable — treated as off: %s: %s", type(exc).__name__, exc)
        return "off"
    return value if value in LODGING_MODES else "off"


__all__ = ["LODGING_MODES", "clear", "lodging_mode", "register", "unlimited"]
