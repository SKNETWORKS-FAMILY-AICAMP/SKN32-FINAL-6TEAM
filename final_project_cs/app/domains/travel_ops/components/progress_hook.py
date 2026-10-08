# -*- coding: utf-8 -*-
"""진행 알림을 화면이 읽는 모양으로 포장하는 **끼움 자리**. `[2026-10-06]` D-CS-013

접수 읽기는 「무엇이 얼마나 됐다」를 만들기만 하고, 그것을 실시간 화면용으로 포장하는 일은
실시간 진행 기능이 맡는다. 꽂히지 않으면 **빈 목록** — 화면이 못 볼 뿐 읽기 자체는 돈다.
"""
from __future__ import annotations

from typing import Any, Callable

#: (이벤트 이름, 본문) -> 화면이 읽는 한 덩어리
Renderer = Callable[[str, dict[str, Any]], str]

_renderer: Renderer | None = None


def register(renderer: Renderer) -> None:
    global _renderer
    _renderer = renderer


def clear() -> None:
    global _renderer
    _renderer = None


def is_registered() -> bool:
    return _renderer is not None


def render(events: list[tuple[str, dict[str, Any]]]) -> list[str]:
    if _renderer is None:
        return []
    return [_renderer(name, body) for name, body in events]
