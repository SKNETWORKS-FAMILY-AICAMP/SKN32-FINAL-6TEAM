# -*- coding: utf-8 -*-
"""소스별 호출 속도 제한 — **하루 한도를 하루에 걸쳐 쓴다.**

★왜 (2026-09-10 사용자 지시). 시험한다고 빨리 두들기면 **차단당한다.**
  공공데이터포털 개발계정은 하루 한도가 낮고(서비스에 따라 500~10,000),
  한도를 넘기면 그날치가 막힌다. 개발 중에 그걸 태우면 시연이 못 돈다.

★환산 규칙은 하나다 — **하루 한도를 24시간에 고르게 편다.**

      최소 간격(초) = 86400 / 하루 한도

      10,000/일 →  8.64초      1,000/일 → 86.4초      500/일 → 172.8초

★★**간격이 안 찼다고 무한정 기다리지 않는다.** 고객 요청 경로에서 86초를
  자는 것은 실패보다 나쁘다. `max_wait_seconds` 까지만 기다리고, 그래도
  모자라면 **거부하고 「모름」으로 넘긴다** — 그편이 정직하다. 거부는
  `rate_limited` 로 **세어서** 남는다(조용한 스킵 금지, `CLAUDE.md` §3).

★프로세스 안에서만 센다. 여러 프로세스가 같은 키를 쓰면 합계가 한도를
  넘을 수 있다 — 그때는 중앙 카운터가 필요하고, 그건 아직 없다.
  **이 한계를 알고 쓴다.**
"""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 86_400

#: 간격이 안 찼을 때 기다려 볼 최대 시간(초). ★고객 요청이 여기서 멈춘다는 뜻이라
#:  작게 잡는다. 넘으면 기다리지 않고 거부한다.
DEFAULT_MAX_WAIT_SECONDS = 5.0


def interval_for(calls_per_day: int | float) -> float:
    """하루 한도 → 호출 사이 최소 간격(초). 0 이하면 제한 없음(0.0)."""
    if not calls_per_day or calls_per_day <= 0:
        return 0.0
    return SECONDS_PER_DAY / float(calls_per_day)


class RateLimited(RuntimeError):
    """간격이 안 찼고 기다릴 수 있는 시간도 넘었다. ★예외지만 **정상 갈래**다 —
    어댑터가 잡아서 `None`(모름)으로 바꾼다. 위로 던지지 않는다."""

    def __init__(self, source: str, wait_seconds: float) -> None:
        super().__init__(
            f"{source}: 다음 호출까지 {wait_seconds:.1f}초 남았다 "
            f"(하루 한도를 하루에 걸쳐 쓰는 중)")
        self.source, self.wait_seconds = source, wait_seconds


@dataclass
class RateLimiter:
    """소스 이름 → 마지막 호출 시각. 스레드 안전하다."""

    #: 소스 이름 → 최소 간격(초)
    intervals: dict[str, float] = field(default_factory=dict)
    max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS
    #: ★시험이 실제로 자지 않도록 시계와 잠을 주입한다.
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep

    _last: dict[str, float] = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    #: 거부 횟수 — 세지 않으면 한도에 눌리고 있다는 걸 아무도 모른다.
    refusals: dict[str, int] = field(default_factory=dict, init=False)

    def acquire(self, source: str) -> None:
        """호출 직전에 부른다. 간격이 찼으면 바로, 아니면 잠깐 기다리거나 거부."""
        interval = self.intervals.get(source, 0.0)
        if interval <= 0:
            return

        with self._lock:
            now = self.clock()
            last = self._last.get(source)
            if last is not None:
                remaining = interval - (now - last)
                if remaining > 0:
                    if remaining > self.max_wait_seconds:
                        self.refusals[source] = self.refusals.get(source, 0) + 1
                        logger.warning("rate limit refused: %s (%.1fs 남음)",
                                       source, remaining)
                        raise RateLimited(source, remaining)
                    self.sleep(remaining)
                    now = self.clock()
            # ★기다린 뒤의 시각으로 찍는다. 기다리기 전 시각으로 찍으면
            #   간격이 조금씩 짧아져 결국 한도를 넘는다.
            self._last[source] = now

    def snapshot(self) -> dict[str, dict[str, float]]:
        """운영 화면이 읽을 상태. ★값을 지어내지 않고 있는 것만 준다."""
        with self._lock:
            return {
                name: {
                    "interval_seconds": round(interval, 2),
                    "calls_per_day": (round(SECONDS_PER_DAY / interval, 1)
                                      if interval > 0 else 0),
                    "refusals": self.refusals.get(name, 0),
                }
                for name, interval in sorted(self.intervals.items())
            }


__all__ = ["DEFAULT_MAX_WAIT_SECONDS", "RateLimited", "RateLimiter",
           "SECONDS_PER_DAY", "interval_for"]
