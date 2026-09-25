# -*- coding: utf-8 -*-
"""유료 API 호출 예산 — **부르기 전에** DB 에서 한 칸을 확보한다. `[2026-09-25]` 사용자 지시 · 마이그레이션 027

★사용자 지시: 구글 무료 한도를 **무조건** 넘지 않게.
★프로세스 안 제한기(`ratelimit.py`)로는 못 지킨다 — 프로세스마다 새로 세고, 되잡기는 매분 새 프로세스다.
  그래서 월·일 사용량을 DB 에 두고 **모든 프로세스가 같은 줄을 센다.**

    reserve(meter)   월 줄과 일 줄을 **둘 다** `used < cap` 일 때만 +1 — 한 트랜잭션. 하나라도 차 있으면
                   아무것도 올리지 않고 False(부르지 않는다)

★실패한 호출도 한 칸 쓴 것으로 센다(과금 여부를 추측하지 않는다 — 보수적).
★월 경계 시간대를 구글이 적어 두지 않았다 `[확인 2026-09-25, 요금표]`. 그래서 **UTC 월**로 세고
  월 상한을 무료 한도보다 작게 둔다 — 시간대가 어긋나 두 달에 걸쳐 세어져도 넘지 않게
  (여유 = 월 상한과 무료 한도의 차 ≥ 하루 상한). 무료 한도 표는 가드레일 `travel.google_budget.free_monthly`,
  상한은 `caps_from_free` 한 규칙으로 계산한다.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable


class CallBudget:
    def __init__(self, *, connection_factory: Callable[[], Any], caps: dict[str, dict[str, int]],
                 clock: Callable[[], datetime] | None = None) -> None:
        """`caps` — {meter: {"month": n, "day": m}}. 모르는 meter 는 **부르지 않는다**(한도를 모르면 막는다)."""
        self._connect, self.caps = connection_factory, caps
        self.clock = clock or (lambda: datetime.now(UTC))
        self.refused: dict[str, int] = {}

    def reserve(self, meter: str) -> bool:
        cap = self.caps.get(meter)
        if not cap:
            self.refused[meter] = self.refused.get(meter, 0) + 1
            return False
        now = self.clock().astimezone(UTC)
        rows = [(f"month:{now:%Y-%m}", int(cap["month"])), (f"day:{now:%Y-%m-%d}", int(cap["day"]))]
        with self._connect() as conn, conn.transaction(), conn.cursor() as cur:
            for period, limit in rows:
                cur.execute("INSERT INTO external_call_budget (meter, period, used, cap) VALUES (%s,%s,0,%s) "
                            "ON CONFLICT (meter, period) DO NOTHING", (meter, period, limit))
            for period, limit in rows:
                # ★상한은 **지금 설정값**으로 본다 — 줄에 남은 옛 cap 이 더 커도 새 값이 이긴다
                cur.execute("UPDATE external_call_budget SET used = used + 1, cap = %s, updated_at = now() "
                            "WHERE meter=%s AND period=%s AND used < %s RETURNING used",
                            (max(limit, 0), meter, period, limit))
                if cur.fetchone() is None:
                    raise _Exhausted(meter, period)      # ★트랜잭션이 되돌린다 — 월 줄만 올라가지 않는다
        return True

    def try_reserve(self, meter: str) -> bool:
        try:
            return self.reserve(meter)
        except _Exhausted:
            self.refused[meter] = self.refused.get(meter, 0) + 1
            return False

    def used(self, meter: str) -> dict[str, int]:
        now = self.clock().astimezone(UTC)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT period, used FROM external_call_budget WHERE meter=%s AND period IN (%s,%s)",
                        (meter, f"month:{now:%Y-%m}", f"day:{now:%Y-%m-%d}"))
            found = dict(cur.fetchall())
        return {"month": found.get(f"month:{now:%Y-%m}", 0), "day": found.get(f"day:{now:%Y-%m-%d}", 0)}


class _Exhausted(Exception):
    """예산이 찼다 — 트랜잭션을 되돌려 월·일 어느 줄도 올리지 않는다."""


#: 무료 한도가 「무제한」인 요금 단위의 상한 — 세기만 하고 막지는 않는다
UNLIMITED = 2_000_000_000


def caps_from_free(free: int | None) -> dict[str, int]:
    """월 무료 한도 → {월, 하루} 상한. ★하루 = 무료 ÷ 32(내림), 월 = 무료 − 하루 → 월 + 하루 ≤ 무료."""
    if free is None:
        return {"month": UNLIMITED, "day": UNLIMITED}
    day = int(free) // 32
    return {"month": int(free) - day, "day": day}


def google_caps() -> dict[str, dict[str, int]]:
    """가드레일의 무료 한도 표(`travel.google_budget.free_monthly`)에서 요금 단위마다 상한을 만든다."""
    from app.core.settings import get_guardrails

    free = get_guardrails().get("travel.google_budget.free_monthly")
    return {meter: caps_from_free(value) for meter, value in free.items()}


__all__ = ["CallBudget", "UNLIMITED", "caps_from_free", "google_caps"]
