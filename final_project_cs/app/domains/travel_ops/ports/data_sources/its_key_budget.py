"""ITS 전체·키별 상한을 같은 DB 트랜잭션으로 확보한다."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .call_budget import UNLIMITED

KST = ZoneInfo("Asia/Seoul")


def key_meter(key: str, *, total_meter: str = "its") -> str:
    """키 실값을 저장하지 않는 고정 사용량 식별자. 등록 순서는 정체에 영향을 주지 않는다."""
    return f"{total_meter}:key:{hashlib.sha256(key.encode()).hexdigest()}"


class ItsKeyBudget:
    """예약 결과는 allowed·key_exhausted·total_exhausted. DB 오류는 호출자가 차단한다."""

    def __init__(self, *, connection_factory: Callable[[], Any], day_limit: int, month_limit: int = 0,
                 key_day_limit: int = 0, key_month_limit: int = 0, share: float = 1.0,
                 clock: Callable[[], datetime] | None = None, total_meter: str = "its",
                 cap_resolver: Callable | None = None) -> None:
        if min(day_limit, month_limit, key_day_limit, key_month_limit) < 0 or not 0 < share <= 1:
            raise ValueError("ITS 호출 상한은 0 이상, 호출 몫은 0 초과 1 이하여야 합니다")
        self._connect = connection_factory
        self.total_meter, self.share = total_meter, share
        self.total_caps = {"day": day_limit, "month": month_limit or UNLIMITED}
        self.key_caps = {"day": key_day_limit or day_limit,
                         "month": key_month_limit or month_limit or UNLIMITED}
        self.clock = clock or (lambda: datetime.now(UTC))
        self._cap_resolver = cap_resolver

    def reserve(self, key: str) -> str:
        """바깥 요청 한 번의 네 줄을 모두 확보한다. 거절되면 네 줄 모두 그대로다."""
        now = self.clock().astimezone(KST)
        credential = key_meter(key, total_meter=self.total_meter)
        periods = {"month": f"month:{now:%Y-%m}", "day": f"day:{now:%Y-%m-%d}"}
        try:
            with self._connect() as conn, conn.transaction(), conn.cursor() as cur:
                resolver = self._cap_resolver
                if resolver is None:
                    from app.application.admin_service import api_cap
                    resolver = api_cap
                total = resolver(conn, self.total_meter, dict(self.total_caps))
                # 모든 호출은 전체 월→일→키 월→일 순서로 잠근다.
                # 다른 프로세스·키도 같은 전체 줄을 먼저 차감하므로 합계 상한을 넘지 않는다.
                for meter, caps in ((self.total_meter, total), (credential, self.key_caps)):
                    for kind, period in periods.items():
                        limit = max(0, int(caps[kind]))
                        cur.execute("INSERT INTO external_call_budget (meter, period, used, cap) VALUES (%s,%s,0,%s) "
                                    "ON CONFLICT (meter, period) DO NOTHING", (meter, period, limit))
                        allowed = limit if limit >= UNLIMITED else int(limit * self.share)
                        # 旧 전체 줄의 제공처 소진은 특정 키의 관측이다. 합계 used/cap은 그대로 적용한다.
                        credential_guard = " AND exhausted_at IS NULL" if meter == credential else ""
                        cur.execute("UPDATE external_call_budget SET used=used+1, cap=%s, updated_at=now() "
                                    "WHERE meter=%s AND period=%s AND used < %s" + credential_guard + " RETURNING used",
                                    (limit, meter, period, allowed))
                        if cur.fetchone() is None:
                            raise _Refused("key_exhausted" if meter == credential else "total_exhausted")
            return "allowed"
        except _Refused as exc:
            return exc.reason

    def mark_exhausted(self, key: str, scope: str = "month") -> None:
        """알려진 제공처 소진을 해당 키·기간에만 기록한다. 확인 호출은 하지 않는다."""
        if scope not in ("day", "month"):
            raise ValueError("ITS 제공처 소진 기간은 day 또는 month여야 합니다")
        now = self.clock().astimezone(KST)
        period = f"month:{now:%Y-%m}" if scope == "month" else f"day:{now:%Y-%m-%d}"
        with self._connect() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO external_call_budget (meter, period, used, cap, exhausted_at, learned_cap) "
                        "VALUES (%s,%s,0,%s,%s,0) ON CONFLICT (meter, period) DO UPDATE SET "
                        "exhausted_at=%s, learned_cap=external_call_budget.used, updated_at=now()",
                        (key_meter(key, total_meter=self.total_meter), period, self.key_caps[scope], now, now))

    def record_failure(self, key: str) -> None:
        """실패 요청도 사용량으로 남겨 두고 전체·해당 키 실패 수만 더한다."""
        now = self.clock().astimezone(KST)
        with self._connect() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("UPDATE external_call_budget SET failed=failed+1, updated_at=now() "
                        "WHERE meter = ANY(%s) AND period = ANY(%s)",
                        ([self.total_meter, key_meter(key, total_meter=self.total_meter)],
                         [f"month:{now:%Y-%m}", f"day:{now:%Y-%m-%d}"]))


class _Refused(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)
