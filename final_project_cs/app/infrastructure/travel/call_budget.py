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

★`[2026-10-05]` 줄마다 **실패 수**(`failed` — 부른 뒤 쓸 수 있는 답을 못 받음 · `used` 의 부분집합)와 **거절 수**(`rejected` — 한도가 차서 **부르지 않음** · `used` 에 안 들어감)도 센다
  (마이그레이션 047). `report()` 가 소스(=키)마다 하루·월 사용 / 상한 / 여유율과 80% 경보 · 95% 위험 단계를 돌려준다(`scripts/report_source_budget.py`).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta, tzinfo
from typing import Any, Callable

logger = logging.getLogger(__name__)

#: 여유율 단계 — 사용 / 상한 이 이 값 이상이면 경보 · 위험. ★우리가 고른 값(이동 세션 제안: 80% 경보, 95% 에서 비필수 호출을 줄인다)
WARN_RATIO = 0.80
CRITICAL_RATIO = 0.95


class CallBudget:
    def __init__(self, *, connection_factory: Callable[[], Any], caps: dict[str, dict[str, int]],
                 clock: Callable[[], datetime] | None = None, tz: tzinfo = UTC) -> None:
        """`caps` — {meter: {"month": n, "day": m}}. 모르는 meter 는 **부르지 않는다**(한도를 모르면 막는다).

        `tz` — 일·월 줄을 가르는 시간대. 기본 UTC(구글·카카오가 그대로 쓰는 값). ★국내 공공 API 의 하루는
        한국 시각 자정에 바뀌므로 그 소스들은 `KST` 를 준다(UTC 로 세면 한국 하루 안에 두 줄이 걸쳐 한도가 두 배로 샌다)."""
        self._connect, self.caps = connection_factory, caps
        self.clock = clock or (lambda: datetime.now(UTC))
        self._tz = tz
        self.refused: dict[str, int] = {}
        #: 마지막으로 확보한 직후의 줄 값 — {meter: {"day": (used, cap), "month": (used, cap)}}. 호출 쪽이 DB 를 다시 안 읽고 여유율을 본다(경보 · 비필수 줄이기)
        self.last: dict[str, dict[str, tuple[int, int]]] = {}

    def seconds_to_day_end(self) -> float:
        """지금부터 다음 하루 줄이 열리기까지(초). 거절된 호출이 「얼마 뒤 다시」를 말할 때 쓴다."""
        now = self.clock().astimezone(self._tz)
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return max(1.0, (tomorrow - now).total_seconds())

    def reserve(self, meter: str) -> bool:
        cap = self.caps.get(meter)
        if not cap:
            self.refused[meter] = self.refused.get(meter, 0) + 1
            return False
        now = self.clock().astimezone(self._tz)
        rows = [(f"month:{now:%Y-%m}", int(cap["month"])), (f"day:{now:%Y-%m-%d}", int(cap["day"]))]
        after: dict[str, tuple[int, int]] = {}
        with self._connect() as conn, conn.transaction(), conn.cursor() as cur:
            for period, limit in rows:
                cur.execute("INSERT INTO external_call_budget (meter, period, used, cap) VALUES (%s,%s,0,%s) "
                            "ON CONFLICT (meter, period) DO NOTHING", (meter, period, limit))
            for period, limit in rows:
                # ★상한은 **지금 설정값**으로 본다 — 줄에 남은 옛 cap 이 더 커도 새 값이 이긴다
                cur.execute("UPDATE external_call_budget SET used = used + 1, cap = %s, updated_at = now() "
                            "WHERE meter=%s AND period=%s AND used < %s RETURNING used",
                            (max(limit, 0), meter, period, limit))
                row = cur.fetchone()
                if row is None:
                    raise _Exhausted(meter, period)      # ★트랜잭션이 되돌린다 — 월 줄만 올라가지 않는다
                after[period.split(":", 1)[0]] = (int(row[0]), int(limit))
        self.last[meter] = after
        return True

    def try_reserve(self, meter: str) -> bool:
        try:
            return self.reserve(meter)
        except _Exhausted:
            self.refused[meter] = self.refused.get(meter, 0) + 1
            self._count(meter, "rejected")                # 한도가 차서 부르지 않은 것도 DB 에 센다(여유 확인용)
            return False

    def record_failure(self, meter: str) -> None:
        """부른 뒤 쓸 수 있는 답을 못 받았다 — 이 소스의 하루·월 줄의 `failed` 를 +1. ★세지 못해도 호출 흐름을 막지 않는다(DB 오류는 로그만)."""
        self._count(meter, "failed")

    def _count(self, meter: str, column: str) -> None:
        assert column in ("failed", "rejected")          # 열 이름은 고정 두 개뿐(문자열을 SQL 에 끼우므로 입력을 받지 않는다)
        now = self.clock().astimezone(self._tz)
        try:
            with self._connect() as conn, conn.transaction(), conn.cursor() as cur:
                cur.execute(f"UPDATE external_call_budget SET {column} = {column} + 1, updated_at = now() "
                            "WHERE meter=%s AND period IN (%s,%s)", (meter, f"month:{now:%Y-%m}", f"day:{now:%Y-%m-%d}"))
        except Exception as exc:                          # noqa: BLE001 — 세는 일이 호출을 막으면 안 된다
            logger.warning("call budget %s count failed (%s): %s: %s", column, meter, type(exc).__name__, exc)

    def used(self, meter: str) -> dict[str, int]:
        now = self.clock().astimezone(self._tz)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT period, used FROM external_call_budget WHERE meter=%s AND period IN (%s,%s)",
                        (meter, f"month:{now:%Y-%m}", f"day:{now:%Y-%m-%d}"))
            found = dict(cur.fetchall())
        return {"month": found.get(f"month:{now:%Y-%m}", 0), "day": found.get(f"day:{now:%Y-%m-%d}", 0)}


    def report(self, meters: list[str] | None = None) -> list[dict[str, Any]]:
        """소스(=키)마다 지금 하루 · 이번 달 줄의 사용 / 상한 / 여유율 — `meters` 를 주면 그 목록(오늘 줄이 아직 없으면 0 으로, 상한은 설정값), 없으면 줄이 있는 전부.

        항목: `{"meter", "day": {"used","cap","failed","rejected","ratio","level"}, "month": {…}, "level"}` — `ratio` 는 used/cap(상한을 모르면 None),
        `level` 은 ok · warn(≥80%) · critical(≥95%) · exhausted(used≥cap). 맨 바깥 `level` 은 두 줄 중 나쁜 쪽."""
        return usage_report(self._connect, now=self.clock().astimezone(self._tz), meters=meters, caps=self.caps)


def level_of(used: int, cap: int) -> tuple[float | None, str]:
    """(사용률, 단계). 상한이 `UNLIMITED` 이상(= 모름)이면 사용률 None · 단계 ok — 막지도 경보하지도 않는다."""
    if cap >= UNLIMITED:
        return None, "ok"
    if cap <= 0:
        return None, "exhausted"
    ratio = used / cap
    if used >= cap:
        return ratio, "exhausted"
    if ratio >= CRITICAL_RATIO:
        return ratio, "critical"
    if ratio >= WARN_RATIO:
        return ratio, "warn"
    return ratio, "ok"


_ORDER = {"ok": 0, "warn": 1, "critical": 2, "exhausted": 3}


def usage_report(connection_factory: Callable[[], Any], *, now: datetime, meters: list[str] | None = None,
                 caps: dict[str, dict[str, int]] | None = None) -> list[dict[str, Any]]:
    """`CallBudget.report` 의 본체 — `now` 는 줄을 가르는 시간대의 현재 시각(그 시간대의 일 · 월 줄을 읽는다)."""
    periods = {"month": f"month:{now:%Y-%m}", "day": f"day:{now:%Y-%m-%d}"}
    sql = "SELECT meter, period, used, cap, failed, rejected FROM external_call_budget WHERE period IN (%s,%s)"
    params: list[Any] = [periods["month"], periods["day"]]
    if meters:
        sql += " AND meter = ANY(%s)"
        params.append(list(meters))
    with connection_factory() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        found = {(row[0], row[1]): row[2:] for row in cur.fetchall()}
    names = list(meters) if meters else sorted({meter for meter, _ in found})
    out: list[dict[str, Any]] = []
    for meter in names:
        item: dict[str, Any] = {"meter": meter}
        worst = "ok"
        for kind, period in periods.items():
            default_cap = int(((caps or {}).get(meter) or {}).get(kind, UNLIMITED))
            used, cap, failed, rejected = found.get((meter, period), (0, default_cap, 0, 0))
            ratio, level = level_of(int(used), int(cap))
            item[kind] = {"used": int(used), "cap": int(cap), "failed": int(failed), "rejected": int(rejected),
                          "ratio": None if ratio is None else round(ratio, 4), "level": level}
            if _ORDER[level] > _ORDER[worst]:
                worst = level
        item["level"] = worst
        out.append(item)
    return out


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


def kakao_caps() -> dict[str, dict[str, int]]:
    """가드레일 `travel.kakao_budget` — 월·하루 상한을 그대로 쓴다(무료 한도가 아니라 우리 상한이다)."""
    from app.core.settings import get_guardrails

    budget = get_guardrails().get("travel.kakao_budget")
    return {meter: {"month": int(v["month"]), "day": int(v["day"])} for meter, v in budget.items()}


__all__ = ["CRITICAL_RATIO", "CallBudget", "UNLIMITED", "WARN_RATIO", "caps_from_free", "google_caps", "kakao_caps", "level_of", "usage_report"]
