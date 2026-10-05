# -*- coding: utf-8 -*-
"""소스별 하루·월 한도를 **프로세스를 건너 DB 로 센다** — env 의 `ACOP_RATE_*_PER_DAY` 를 실제로 지키게 하는 층. `[2026-10-05 사용자 지적 · 지시]`

★왜. `ratelimit.RateLimiter` 는 **프로세스 안에서만** 센다. 일꾼은 1분마다 새 프로세스로 뜨고(감시 작업만 3분 문),
  새 프로세스는 `burst` 만큼 **꽉 찬 채로 시작**한다 — 그래서 하루 한도를 env 에 적어도 일꾼 경로에서는 지켜지지 않았다.
  `call_budget.py`(DB 카운터)가 9/25 에 같은 이유로 만들어졌지만 **구글·카카오에만** 연결돼 있었고, ITS 등은 안 걸려 있었다
  (9/30 · 10/2 에 ITS 한도 초과 응답이 각각 937 · 825건).

★어떻게. 바깥으로 나가기 직전의 단일 지점(`TravelSource._allow` → `limiter.acquire(name)`)에 얹는다 — 어댑터는 안 바뀐다.
  안쪽 제한기를 먼저 통과한 뒤 DB 한 칸을 확보하고(`CallBudget.try_reserve`), 차 있으면 `BudgetExhausted`(= 호출 안 함 · 「모름」).
  하루는 **한국 시각** 자정에 바뀐다. `TravelSource` 를 거치지 않고 직접 부르는 코드(따릉이 실시간 `urllib`)는 `build_gate` 로 같은 문을 쓴다.

★**한도가 차면 바깥으로 안 나간다**(`BudgetExhausted`) — 하루 줄이든 월 줄이든 하나라도 차 있으면 아무것도 올리지 않고 거절한다(한 트랜잭션).
★**예산을 못 읽을 때(DB 오류)의 동작은 가드레일 `travel.source_budget_on_db_error` 가 정한다 — 기본 `allow`**: 안쪽 제한기만으로 나간다(이 층 도입 전과 같다 — 더 나빠지지 않는다).
  `refuse` 로 바꾸면 세지 못하는 호출은 내보내지 않는다(`BudgetUnavailable`). ★**사용자 결정 대기 사항**(2026-10-05): `refuse` 는 「한도를 무조건 넘지 않는다」(9/25 구글 때 지시)와 맞지만
  DB 가 오류를 내는 동안 이 목록의 소스가 전부 「모름」이 돼 도로 사건 감시가 치명(결정 15)으로 번지는 대가가 있다. 이 층은 감시 루프와 **같은 DB** 를 쓰므로 DB 가 아예 죽었으면
  어차피 감시도 못 돈다 — 그래서 의미가 있는 경우는 표 누락 · 잠금 시간 초과 · 연결 부족 같은 부분 장애다. 어느 쪽이든 오류는 센다(`db_errors`)고 경고 로그를 남긴다.
★실패한 호출도 한 칸 쓴 것으로 센다(`CallBudget` 규칙 — 과금·한도 계산을 추측하지 않는다). 거기에 더해 소스(=키)마다 **실패 수**(`record_failure`)와 **거절 수**(한도가 차서 안 부른 수)를
  DB 에 센다(마이그레이션 047) — `scripts/report_source_budget.py` 가 여유율을 보여 준다.
★여유율 단계: 사용 ≥ 80% 면 경보(경고 로그 — 프로세스마다 한 번), ≥ 95% 면 위험 — `essential_only(source)` 가 True 가 되어 **비필수 호출(워밍 · 재확인)** 을 부르는 쪽이 줄일 수 있다.
  `[미구현]` 지금 이 신호를 읽는 호출자는 없다 — 비필수 호출이 어디인지 정해지면 거기서 읽는다.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from .call_budget import CRITICAL_RATIO, UNLIMITED, WARN_RATIO, CallBudget, level_of
from .ratelimit import RateLimited

logger = logging.getLogger(__name__)

#: DB 오류 뒤 이 시간 동안은 DB 를 다시 시도하지 않는다(요청마다 연결 시간 초과를 기다리지 않게).
#:  `refuse` 는 이 동안도 거절이라 DB 가 살아난 뒤에도 그만큼 늦게 풀린다 — 그래서 짧게 둔다.
RETRY_AFTER_SECONDS = {"allow": 60.0, "refuse": 10.0}
DEFAULT_ON_DB_ERROR = "allow"
_ORDER = {"ok": 0, "warn": 1, "critical": 2, "exhausted": 3}


class BudgetExhausted(RateLimited):
    """DB 예산(하루 또는 월)이 찼다. ★`RateLimited` 의 갈래라 어댑터가 같은 자리에서 잡는다 — 이유 이름만 다르다."""

    reason = "budget_exhausted"

    def __init__(self, source: str, wait_seconds: float) -> None:
        RuntimeError.__init__(
            self, f"{source}: 호출 예산이 찼다(프로세스를 건너 센 하루·월 한도) — 약 {wait_seconds / 3600:.1f}시간 뒤 하루 줄이 열린다")
        self.source, self.wait_seconds = source, wait_seconds


class BudgetUnavailable(RateLimited):
    """예산을 읽지 못했다(DB 오류) — `on_db_error="refuse"` 일 때 호출을 내보내지 않는다."""

    reason = "budget_unavailable"

    def __init__(self, source: str, wait_seconds: float) -> None:
        RuntimeError.__init__(self, f"{source}: 호출 예산을 읽지 못해(DB 오류) 호출하지 않는다 — 약 {wait_seconds:.0f}초 뒤 다시 확인")
        self.source, self.wait_seconds = source, wait_seconds


class BudgetedLimiter:
    """`RateLimiter` 와 같은 `acquire(source)` 를 주되, 이름이 `meters` 에 있는 소스는 DB 예산도 확보한다.

    나머지 속성(`intervals` · `refusals` · `snapshot` …)은 안쪽 제한기에 그대로 넘긴다."""

    def __init__(self, inner: Any, budget: Any, meters: frozenset[str] | set[str], *,
                 on_db_error: str = DEFAULT_ON_DB_ERROR, clock: Callable[[], float] = time.monotonic) -> None:
        if on_db_error not in RETRY_AFTER_SECONDS:
            raise ValueError(f"on_db_error 는 allow 또는 refuse 여야 한다: {on_db_error!r}")
        self._inner, self._budget, self.meters = inner, budget, frozenset(meters)
        self._on_db_error = on_db_error
        self._clock = clock
        self._lock = threading.Lock()
        self._db_down_until = 0.0
        self._warned: set[tuple[str, str]] = set()
        self.db_errors = 0
        self.exhausted: dict[str, int] = {}
        #: 이 프로세스가 마지막으로 본 소스별 여유 단계(ok · warn · critical) — `essential_only` 가 읽는다
        self.levels: dict[str, str] = {}

    def acquire(self, source: str) -> None:
        self._inner.acquire(source)
        if source not in self.meters:
            return
        with self._lock:
            down = self._clock() < self._db_down_until
        if down:                                            # DB 오류 직후 — 다시 부르지 않고 같은 규칙을 적용한다
            if self._on_db_error == "refuse":
                raise BudgetUnavailable(source, self._db_down_until - self._clock())
            return
        try:
            granted = self._budget.try_reserve(source)
        except Exception as exc:                            # noqa: BLE001 — DB 계층의 어떤 오류든 아래 규칙대로 처리한다
            wait = RETRY_AFTER_SECONDS[self._on_db_error]
            with self._lock:
                self.db_errors += 1
                self._db_down_until = self._clock() + wait
            logger.warning("source budget unavailable (%s): %s: %s — %s", source, type(exc).__name__, exc,
                           "호출하지 않는다(refuse)" if self._on_db_error == "refuse" else "안쪽 제한기만 적용(allow)")
            if self._on_db_error == "refuse":
                raise BudgetUnavailable(source, wait) from exc
            return
        if not granted:
            with self._lock:
                self.exhausted[source] = self.exhausted.get(source, 0) + 1
                self.levels[source] = "exhausted"
            raise BudgetExhausted(source, self._budget.seconds_to_day_end())
        self._watch(source)

    def _watch(self, source: str) -> None:
        """방금 확보한 줄 값으로 여유 단계를 갱신하고, 경보 · 위험에 처음 들어서면 경고 로그를 한 번 남긴다(프로세스마다)."""
        last = getattr(self._budget, "last", {}).get(source)
        if not last:
            return
        worst, worst_ratio, worst_kind = "ok", None, ""
        for kind in ("day", "month"):
            if kind in last:
                ratio, level = level_of(*last[kind])
                if _ORDER[level] > _ORDER[worst]:
                    worst, worst_ratio, worst_kind = level, ratio, kind
        self.levels[source] = worst
        if worst in ("warn", "critical") and (source, worst) not in self._warned:
            self._warned.add((source, worst))
            used, cap = last[worst_kind]
            logger.warning("source budget %s: %s %s 줄 %d/%d (%.0f%%) — %s", source, worst, "하루" if worst_kind == "day" else "월",
                           used, cap, 100 * (worst_ratio or 0),
                           f"위험(≥{CRITICAL_RATIO:.0%}) — 비필수 호출을 줄인다" if worst == "critical" else f"경보(≥{WARN_RATIO:.0%})")

    def mark_provider_exhausted(self, source: str, scope: str = "day") -> None:
        """제공처가 「한도 초과」를 알렸다(`TravelSource._provider_quota` 가 부른다) — 그 기간 줄에 표시해 이후 호출을 멈춘다(`call_budget.mark_provider_exhausted`)."""
        if source in self.meters:
            self._budget.mark_provider_exhausted(source, scope)
            with self._lock:
                self.levels[source] = "exhausted"

    def record_failure(self, source: str) -> None:
        """부른 뒤 쓸 수 있는 답을 못 받았다 — 이 소스의 실패 수를 DB 에 센다(`TravelSource._miss` 가 부른다). 세지 못해도 흐름을 막지 않는다."""
        if source in self.meters:
            self._budget.record_failure(source)

    def essential_only(self, source: str) -> bool:
        """이 소스의 한도가 위험(≥95%)이거나 찼다 — 비필수 호출(워밍 · 재확인)은 부르지 말라는 신호. ★이 프로세스가 마지막으로 본 값이다(DB 를 다시 읽지 않는다)."""
        return self.levels.get(source, "ok") in ("critical", "exhausted")

    def __getattr__(self, name: str) -> Any:                 # 안쪽 제한기의 나머지 속성
        return getattr(self._inner, name)


def with_db_budget(limiter: Any, limits: dict[str, int], monthly: dict[str, int], names: list[str], *,
                   on_db_error: str = DEFAULT_ON_DB_ERROR) -> Any:
    """안쪽 제한기에 **DB 예산**을 얹는다. 하루 한도를 모르는(env 에 없거나 0) 소스는 세지 않는다. 월 한도를 모르면(0) 월 줄은 세기만 하고 막지 않는다(`UNLIMITED`)."""
    from zoneinfo import ZoneInfo

    from app.infrastructure.db.session import get_connection

    caps = {name: {"day": int(limits[name]), "month": int(monthly.get(name) or UNLIMITED)}
            for name in names if limits.get(name, 0) > 0}
    if not caps:
        return limiter
    budget = CallBudget(connection_factory=get_connection, caps=caps, tz=ZoneInfo("Asia/Seoul"))
    return BudgetedLimiter(limiter, budget, frozenset(caps), on_db_error=on_db_error)


def build_gate(settings: Any, names: list[str], *, on_db_error: str | None = None) -> Any:
    """`TravelSource` 를 거치지 않고 직접 부르는 코드(따릉이 실시간 `urllib` 등)가 쓰는 문 — `gate.acquire(이름)` 이 한도가 차면 `RateLimited`(의 갈래)를 던진다.

    이름은 `settings.source_rate_limits()` 의 이름이어야 한다(하루 한도 env). 한도를 모르는 이름이면 문이 그 이름을 안 센다(= 통과). 호출자는 `RateLimited` 를 잡아 「모름」으로 돌려야 한다."""
    from app.core.settings import get_guardrails

    from .ratelimit import RateLimiter, interval_for

    guardrails = get_guardrails()
    limits = settings.source_rate_limits()
    burst = max(1, int(guardrails.get("travel.rate_burst") or 1))
    inner = RateLimiter(intervals={n: interval_for(limits.get(n, 0), burst=burst) for n in names}, bursts={n: burst for n in names},
                        max_wait_seconds=float(getattr(settings, "rate_max_wait_seconds", 5.0)))
    policy = on_db_error or str(guardrails.get("travel.source_budget_on_db_error") or DEFAULT_ON_DB_ERROR)
    return with_db_budget(inner, limits, settings.source_monthly_limits(), list(names), on_db_error=policy)


__all__ = ["BudgetExhausted", "BudgetUnavailable", "BudgetedLimiter", "DEFAULT_ON_DB_ERROR", "RETRY_AFTER_SECONDS", "build_gate", "with_db_budget"]
