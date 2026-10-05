# -*- coding: utf-8 -*-
"""운영자가 화면에서 바꾼 값을 읽는 **끼움 자리**. `[2026-10-06]` D-CS-013

★왜 있나. 전에는 대화 부품이 웹 남용 방어 모듈의 설정 표를 직접 읽었다(`web_guard.values`).
  채팅 동작 하나가 「끌 수 있는 기능」의 저장소 모양에 묶여 있었던 셈이다.

지금은 이렇게 돈다.

    부품            "이 값 운영자가 바꿨나?"  →  여기(`operator_setting`)
    설정 화면 기능  "내가 그 표를 들고 있다"  →  조립 때 `register()`

  아무도 꽂지 않으면 `None` 을 돌려준다 — 부르는 쪽이 가드레일 기본값을 쓴다.
  **값을 지어내지 않는다.** 표를 못 읽는 상황과 「조정값이 없다」를 같은 `None` 으로 돌려주는 것은
  의도한 것이다. 둘 다 「기본값으로 간다」가 정답이고, 그 사실은 부르는 쪽 주석이 적는다.
"""
from __future__ import annotations

from typing import Any, Callable

#: (tenant_id, 이름) -> 값 또는 None
Reader = Callable[[str, str], Any]

_reader: Reader | None = None


def register(reader: Reader) -> None:
    """조립 때 한 번. 다시 부르면 교체한다(재조립 대비)."""
    global _reader
    _reader = reader


def clear() -> None:
    global _reader
    _reader = None


def is_registered() -> bool:
    return _reader is not None


def operator_setting(tenant_id: str, name: str) -> Any:
    if _reader is None:
        return None
    try:
        return _reader(tenant_id, name)
    except Exception:                                   # noqa: BLE001 — 표를 못 읽으면 기본값으로 간다
        return None
