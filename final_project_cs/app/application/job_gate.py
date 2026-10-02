# -*- coding: utf-8 -*-
"""상시 작업 안의 **주기 문** — 1분마다 도는 일꾼 안에서 어떤 일만 N 분마다 하게 한다. `[2026-10-03 사용자 결정]`

☆왜. 되잡기 일꾼(`scripts/run_sweepers.py`)은 1분마다 도는데 그 안의 **감시**는 팀 결정(D-017 · D-020)이 3분이다 — 1분으로 두면 외부 소스를 3배로 부른다
  (에어코리아 하루 한도 500 에 3분 간격이 이미 480 = 96%). 일꾼을 통째로 3분으로 바꾸면 **일정 출발 안내**(v11 §6-B)가 최대 3분 늦고 멈춘 Case 되잡기도 느려진다.
  그래서 일꾼은 1분 그대로 두고 **감시만** 이 문을 지난다.

★`claim` — 마지막 실행 뒤 `min_seconds` 가 지났을 때만 **참**이고, 그때 마지막 실행 시각을 지금으로 적는다(원자적 — 일꾼 둘이 동시에 떠도 하나만 이긴다).
  스케줄러가 몇 초 늦게 불러도 3분 주기가 4분으로 밀리지 않게, 부르는 쪽이 **주기에서 허용 오차를 뺀 값**을 `min_seconds` 로 준다(`interval_seconds`).
★문을 열었다고 일이 성공한 것은 아니다 — 시각은 **시도 시작**에 적는다. 일이 터져도 다음 시도는 주기 뒤다(터진 일을 1분마다 되풀이해 외부 소스를 때리지 않게).
"""
from __future__ import annotations

from typing import Any

#: 감시 문의 이름 — 점검(`healthcheck`)도 같은 이름으로 마지막 실행을 읽는다
WATCH_GATE = "trip_watch"


def claim(conn: Any, *, tenant_id: str, gate: str, min_seconds: float) -> bool:
    """마지막 실행 뒤 `min_seconds` 이상 지났으면(또는 처음이면) 지금으로 적고 참. 아니면 거짓(아무것도 안 적는다)."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO job_gates (tenant_id, gate, last_run_at) VALUES (%s, %s, now()) "
            "ON CONFLICT (tenant_id, gate) DO UPDATE SET last_run_at = now() "
            "WHERE job_gates.last_run_at <= now() - make_interval(secs => %s) "
            "RETURNING 1", (tenant_id, gate, float(min_seconds)))
        return cur.fetchone() is not None


def last_run_age_seconds(conn: Any, *, tenant_id: str, gate: str) -> float | None:
    """마지막 실행이 몇 초 전인가. 한 번도 안 돌았으면 None."""
    with conn.cursor() as cur:
        cur.execute("SELECT extract(epoch FROM (now() - last_run_at)) FROM job_gates WHERE tenant_id=%s AND gate=%s",
                    (tenant_id, gate))
        row = cur.fetchone()
    return None if row is None else float(row[0])


def interval_seconds(guardrails: Any) -> tuple[float, float]:
    """(주기, 문을 여는 최소 경과). 설정 `reliability.watch_interval_seconds`(180) · `…_tolerance_seconds`(30) — 최소 경과 = 주기 − 허용 오차."""
    interval = float(guardrails.get("reliability.watch_interval_seconds"))
    tolerance = float(guardrails.get("reliability.watch_interval_tolerance_seconds"))
    return interval, max(0.0, interval - tolerance)


__all__ = ["WATCH_GATE", "claim", "interval_seconds", "last_run_age_seconds"]
