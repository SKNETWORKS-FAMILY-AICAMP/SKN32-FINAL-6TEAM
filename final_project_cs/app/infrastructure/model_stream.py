# -*- coding: utf-8 -*-
"""모델 답을 **조금씩 받으며** 멈춤을 감시하는 장치 — Ollama · OpenAI 가 같이 쓴다. `[2026-10-16 2회차 합의 · 사용자 승인]`

★왜: 계획 읽기의 긴 답(7일치 계획 · 출력 최대 약 1,500토큰)은 로컬에서 12~27초 걸린다. 9초 · 8초 같은 **고정 한도**로는 정상으로 답을 쓰고 있는
  호출도 끊겼다. 그래서 「얼마나 오래」가 아니라 「답 조각이 계속 오나」를 본다(실측 보고서 `wiki/records/reports/2026-10-16_계획읽기_묶음나누기.md`).
★세 가지 시계:
  - `first_wait` — 첫 조각까지. 지시문 읽기 · 모델 준비 · **같은 서버에 먼저 온 요청 뒤에서 기다리는 시간**이 들어 있어 길게 둔다(실측 최대 10.2초).
  - `stall` — 조각 사이. 이만큼 아무 조각도 안 오면 멈춘 것으로 본다(실측 조각 사이 최대 0.7초).
  - `max_seconds` — 맨 위 상한. 모델이 같은 말을 끝없이 되풀이해도 여기서 끝난다.
★멈추면 받는 쪽 연결을 닫고 `OllamaError`(원인 `httpx.ReadTimeout` — 넘김 장치가 「시간 초과」로 센다)를 올린다. 받다 만 답은 버린다.
★받는 일은 따로 실을 돌린다(`threading`) — 연결 라이브러리의 읽기 한도는 「바이트 사이」라 첫 조각 · 조각 사이를 따로 재지 못한다.
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Callable, Iterator

import httpx

from app.infrastructure.ollama_chat import OllamaError

_END = object()


class StreamStalled(OllamaError):
    """조각이 끊겼다(첫 조각 · 조각 사이 · 맨 위 상한 중 하나). `which` = first · stall · max."""

    def __init__(self, message: str, *, which: str) -> None:
        super().__init__(message)
        self.which = which


def collect(pieces: Callable[[], Iterator[str]], *, first_wait: float, stall: float, max_seconds: float,
            on_piece: Callable[[str], None] | None = None, close: Callable[[], None] | None = None,
            clock: Callable[[], float] = time.monotonic) -> str:
    """`pieces()` 가 내는 조각을 모아 돌려준다. 시계 셋 중 하나라도 넘으면 `close()` 를 부르고 `StreamStalled` 를 올린다.
    `on_piece(지금까지 모은 글)` — 조각이 올 때마다(부르는 쪽 실에서). 그 안의 오류는 받기를 막지 않는다."""
    box: queue.Queue = queue.Queue()

    def produce() -> None:
        try:
            for piece in pieces():
                box.put(piece)
        except BaseException as exc:                       # noqa: BLE001 — 받는 쪽 오류는 부르는 쪽 실에서 다시 올린다
            box.put(exc)
        finally:
            box.put(_END)

    worker = threading.Thread(target=produce, name="model-stream", daemon=True)
    started = clock()
    worker.start()
    parts: list[str] = []
    got_first = False
    while True:
        now = clock()
        left_total = max_seconds - (now - started)
        wait = min(first_wait if not got_first else stall, left_total)
        try:
            item = box.get(timeout=max(0.0, wait))
        except queue.Empty:
            which = "max" if left_total <= wait else ("first" if not got_first else "stall")
            if close is not None:
                try:
                    close()
                except Exception:                          # noqa: BLE001 — 닫기 실패는 상관없다(실은 데몬이다)
                    pass
            limit = {"first": first_wait, "stall": stall, "max": max_seconds}[which]
            raise StreamStalled(f"모델 답 조각이 끊겼다({which} {limit:g}초)", which=which) from httpx.ReadTimeout(which)
        if item is _END:
            return "".join(parts)
        if isinstance(item, BaseException):
            raise item
        if not item:
            continue
        got_first = True
        parts.append(item)
        if on_piece is not None:
            try:
                on_piece("".join(parts))
            except Exception:                              # noqa: BLE001 — 진행 알림은 부가 기능이다
                pass


__all__ = ["StreamStalled", "collect"]
