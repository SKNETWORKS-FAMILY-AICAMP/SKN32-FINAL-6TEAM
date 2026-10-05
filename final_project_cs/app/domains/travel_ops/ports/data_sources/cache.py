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

★프로세스 안에서만 산다(속도 제한기와 같은 한계). ★`[2026-10-03]` 그 한계를 푸는 것이 `DbResponseCache` 다 — 일꾼이 회차마다 새 프로세스라 메모리 캐시는 틱 사이에 비고 고객 요청 경로와도 안 나눴다.
  공개 소스 응답을 DB 표(`source_response_cache`, 마이그레이션 042)에도 두어 **어느 프로세스든** 유지 시간 안에서는 다시 안 부른다.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
import logging
import threading
import time
from typing import Any, Callable, Hashable

logger = logging.getLogger(__name__)


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


class DbResponseCache(ResponseCache):
    """`ResponseCache` + **프로세스를 건너 공유하는 DB 층**. 같은 인터페이스(`get` · `put`)라 어댑터는 모른다.

    ★규칙
      - 메모리를 먼저 본다. 없으면 DB(공개 소스만) — 찾으면 메모리에도 채운다(남은 유지 시간만큼).
      - **허용 소스만** DB 에 둔다(`SHARED_SOURCES`). 고객이 쓴 검색어가 담기는 소스(카카오 · 구글 장소 · 관광공사 장소)는 메모리에만 — 사용자 입력이 프로세스를 넘어 퍼지지 않게.
      - 열쇠는 요청 전체의 **해시**다 — 요청 인자에는 서비스 키가 들어 있어 원문을 DB 에 두지 않는다.
      - **DB 가 안 되면 메모리 캐시로 돌아간다 — 소스 호출을 막지 않는다.** 실패는 센다(`db_errors`)고 로그로 남기고, 60초 동안은 DB 를 건너뛴다(연결 실패를 요청마다 기다리지 않게).
      - 재사용한 값의 시각은 **처음 받아 온 시각**이다(DB 에 그대로 둔다) — `stamp()` 가 확인 시각으로 쓴다.
    """

    #: 공개 소스 — 감시가 부르는 것들. 소스 이름은 어댑터의 `name`(열쇠의 첫 칸)이다
    SHARED_SOURCES = frozenset({"open_meteo", "open_meteo_air", "kma", "kma_warning", "kma_earthquake", "airkorea",
                                "disaster_msg", "its", "utic", "kasi_holiday", "airport", "mofa", "khoa"})
    RETRY_AFTER_SECONDS = 60.0
    PURGE_EVERY = 100                                 # 쓰기 이만큼마다 만료된 줄을 지운다

    def __init__(self, ttl_seconds: float, connection_factory: Callable[[], Any], *,
                 shared_sources: frozenset[str] | None = None, **kwargs: Any) -> None:
        super().__init__(ttl_seconds=ttl_seconds, **kwargs)
        self._connect = connection_factory
        self.shared = frozenset(shared_sources) if shared_sources is not None else self.SHARED_SOURCES
        self.db_hits = self.db_stores = self.db_errors = 0
        self._db_down_until = 0.0
        self._writes = 0

    # ── 내부 ────────────────────────────────────────────────────
    def _is_shared(self, key: Hashable) -> bool:
        return isinstance(key, tuple) and bool(key) and key[0] in self.shared

    @staticmethod
    def _hash(key: Hashable) -> str:
        return hashlib.sha256(json.dumps(key, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()

    def _db_usable(self) -> bool:
        return self.clock() >= self._db_down_until

    def _db_failed(self, exc: Exception) -> None:
        self.db_errors += 1
        self._db_down_until = self.clock() + self.RETRY_AFTER_SECONDS
        logger.warning("source response cache: DB 층을 %.0f초 건너뛴다(메모리 캐시로 계속) — %s: %s",
                       self.RETRY_AFTER_SECONDS, type(exc).__name__, str(exc)[:120])

    # ── 인터페이스 ──────────────────────────────────────────────
    def get(self, key: Hashable) -> tuple[Any, datetime] | None:
        found = super().get(key)
        if found is not None or not self._is_shared(key) or not self.ttl_seconds > 0 or not self._db_usable():
            return found
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT payload, fetched_at, extract(epoch FROM (expires_at - now())) "
                            "FROM source_response_cache WHERE key_hash=%s AND expires_at > now()", (self._hash(key),))
                row = cur.fetchone()
        except Exception as exc:                     # noqa: BLE001 — 캐시 때문에 소스 호출이 막히면 안 된다
            self._db_failed(exc)
            return None
        if row is None:
            return None
        value, fetched_at, remaining = row[0], row[1], float(row[2])
        self.db_hits += 1
        super().put(key, value, fetched_at=fetched_at, ttl_seconds=remaining)          # 메모리에도 — 남은 시간만큼
        self.hits += 1
        return copy.deepcopy(value), fetched_at

    def put(self, key: Hashable, value: Any, *, fetched_at: datetime | None = None,
            ttl_seconds: float | None = None) -> None:
        super().put(key, value, fetched_at=fetched_at, ttl_seconds=ttl_seconds)
        ttl = self.ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl <= 0 or not self._is_shared(key) or not self._db_usable():
            return
        from psycopg.types.json import Json

        try:
            with self._connect() as conn, conn.transaction(), conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO source_response_cache (key_hash, source, payload, fetched_at, expires_at) "
                    "VALUES (%s, %s, %s, %s, now() + make_interval(secs => %s)) "
                    "ON CONFLICT (key_hash) DO UPDATE SET payload=EXCLUDED.payload, fetched_at=EXCLUDED.fetched_at, "
                    "expires_at=EXCLUDED.expires_at",
                    (self._hash(key), str(key[0]), Json(value), fetched_at or self.wall(), float(ttl)))
                self._writes += 1
                if self._writes % self.PURGE_EVERY == 0:
                    cur.execute("DELETE FROM source_response_cache WHERE expires_at < now() - interval '1 hour'")
            self.db_stores += 1
        except Exception as exc:                     # noqa: BLE001
            self._db_failed(exc)


__all__ = ["DbResponseCache", "ResponseCache"]
