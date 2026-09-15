# -*- coding: utf-8 -*-
"""바깥 소스 응답을 잠깐 재사용한다 — **같은 요청을 몇 분 안에 다시 내보내지 않는다.**

★왜(2026-09-14 실측). 감시 루프 한 틱이 항목 여럿을 점검하면 **같은 요청**이 연달아
  나간다 — 기상특보(인자 없음)·대기질(시도 단위)·지진(날짜 단위)은 장소가 달라도 인자가
  같다. 그걸 매번 내보내면 하루 한도를 태우고, 속도 제한기가 둘째부터 거부해 「모름」→
  치명이 된다.

★규칙:
    - **성공한 응답만** 담는다. 실패는 담지 않는다 — 실패를 재사용하면 공급자가 살아나도
      몇 분 동안 계속 「모름」이다.
    - 꺼낼 때는 **복사본**을 준다. 어댑터가 고쳐 쓰면 다음 사람이 고친 값을 받는다.
    - **처음 받아 온 시각**을 같이 준다. 재사용한 값에 「지금 확인」을 찍으면 확인 시각을
      속인다(v10 §4-D). `TravelSource.stamp()` 가 이 시각을 `confirmed_at` 으로 쓴다.
    - 유지 시간은 `config/guardrails.yaml` 의 `travel.source_cache_seconds` 한 곳에 둔다.
      0 이면 담지 않는다.

★프로세스 안에서만 산다(속도 제한기와 같은 한계).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
import threading
import time
from typing import Any, Callable, Hashable


@dataclass
class ResponseCache:
    ttl_seconds: float
    #: ★시험이 실제로 기다리지 않도록 시계를 주입한다.
    clock: Callable[[], float] = time.monotonic
    wall: Callable[[], datetime] = lambda: datetime.now(UTC)

    _items: dict[Hashable, tuple[float, datetime, Any]] = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    hits: int = field(default=0, init=False)
    stores: int = field(default=0, init=False)

    def get(self, key: Hashable) -> tuple[Any, datetime] | None:
        """(복사본, 처음 받아 온 시각). 없거나 지났으면 `None`."""
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            expires_at, fetched_at, value = entry
            if self.clock() >= expires_at:
                del self._items[key]
                return None
            self.hits += 1
            return copy.deepcopy(value), fetched_at

    def put(self, key: Hashable, value: Any, *, fetched_at: datetime | None = None,
            ttl_seconds: float | None = None) -> None:
        """★`ttl_seconds` 로 소스별 유지 시간을 준다 — 하루 한도가 낮은 소스(재난문자)는 길게."""
        ttl = self.ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            return
        with self._lock:
            self._items[key] = (self.clock() + ttl, fetched_at or self.wall(),
                                copy.deepcopy(value))
            self.stores += 1


__all__ = ["ResponseCache"]
