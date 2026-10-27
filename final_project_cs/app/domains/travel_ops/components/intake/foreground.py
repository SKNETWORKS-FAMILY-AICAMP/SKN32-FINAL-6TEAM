# -*- coding: utf-8 -*-
"""앞단(고객이 「읽는 중」을 보며 기다리는 접수 처리)과 뒤의 미리 준비를 나눈다. `[2026-10-27 서빙 속도]`

★왜(x600 실측, 2026-10-20~26 채팅 접수 148건): 다른 접수의 대안 미리 준비(`prepared.prepare`)가 도는 동안 읽기가
  p50 12.6초(17건)로, 아무것도 안 돌 때 p50 7.5초(120건)보다 5초 늦었다. 한 GPU 모델 · 한 API 프로세스를 같이 쓴다.
★규칙: 접수 처리(`pipeline.process`)는 받은 뒤 확인 화면으로 넘길 때까지(먼저 채우기 포함) `active()` 안에서 돈다.
  뒤의 미리 준비는 일정 하나를 **맡기 전에** `wait_idle(상한)` 으로 앞단이 빌 때까지 기다린다. 상한은 가드레일
  `travel.candidates.prepare_yield_seconds` — 넘으면 기다림을 로그로 남기고 진행한다(준비가 끝없이 밀리지 않게).
★프로세스 안에서만 센다 — API 는 프로세스 하나(uvicorn 일꾼 1)라 접수 처리와 미리 준비가 같은 곳에서 돈다.
"""
from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from typing import Iterator

log = logging.getLogger(__name__)

_cond = threading.Condition()
_count = 0


@contextmanager
def active() -> Iterator[None]:
    """이 안에서 도는 동안 앞단으로 센다."""
    global _count
    with _cond:
        _count += 1
    try:
        yield
    finally:
        with _cond:
            _count -= 1
            _cond.notify_all()


def busy() -> int:
    """지금 앞단에 있는 접수 처리 수."""
    with _cond:
        return _count


def wait_idle(limit_seconds: float) -> float:
    """앞단이 빌 때까지(최대 `limit_seconds`) 기다린다 — 기다린 초. 상한에 닿으면 경고 로그를 남기고 돌아간다."""
    started = time.monotonic()
    deadline = started + float(limit_seconds)
    with _cond:
        while _count > 0:
            left = deadline - time.monotonic()
            if left <= 0:
                log.warning("background work yielded %.1fs to foreground intake reading (limit) — proceeding, foreground=%d",
                            time.monotonic() - started, _count)
                break
            _cond.wait(left)
    return time.monotonic() - started


__all__ = ["active", "busy", "wait_idle"]
