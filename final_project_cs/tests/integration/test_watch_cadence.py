# -*- coding: utf-8 -*-
"""여행 감시는 **3분 주기**다 — 1분마다 도는 되잡기 일꾼 안의 주기 문(`job_gate`). `[2026-10-03 사용자 결정 — D-017 · D-020]`

☆왜: 일꾼이 1분마다 감시를 돌려 외부 소스를 3배로 불렀다(에어코리아 하루 한도 500 에 3분 간격이 이미 480). 일꾼 전체를 3분으로 바꾸면 일정 출발 안내와 멈춘 Case 되잡기가 늦어져
감시만 막는다. 일꾼은 회차마다 새 프로세스라 마지막 실행 시각은 DB(`job_gates`)에 둔다.

★지키려는 것: ①처음은 열린다 ②한 주기 안의 다음 회차(1분 · 2분 뒤)는 닫힌다 ③주기에서 허용 오차를 뺀 시간(150초)이 지나면 열린다(스케줄러 지연이 3분을 4분으로 밀지 않게)
④동시에 둘이 와도 **하나만** 이긴다 ⑤테넌트마다 따로다 ⑥일꾼이 문이 닫힌 회차에는 감시(외부 소스)를 **아무것도 안 부른다** · `--only trip_cases` 는 문을 안 본다.

재현:

    python -m pytest tests/integration/test_watch_cadence.py -v
"""
from __future__ import annotations

import threading
from uuid import uuid4

import pytest

from app.application import job_gate
from app.core.settings import get_guardrails
from app.infrastructure.db.session import get_connection

GATE = job_gate.WATCH_GATE


@pytest.fixture()
def tenant():
    name = "cadence_" + uuid4().hex[:10]
    yield name
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM job_gates WHERE tenant_id=%s", (name,))


def _claim(tenant: str, min_seconds: float = 150.0) -> bool:
    with get_connection() as conn, conn.transaction():
        return job_gate.claim(conn, tenant_id=tenant, gate=GATE, min_seconds=min_seconds)


def _backdate(tenant: str, seconds: float) -> None:
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE job_gates SET last_run_at = now() - make_interval(secs => %s) WHERE tenant_id=%s AND gate=%s",
                    (seconds, tenant, GATE))


def test_the_interval_comes_from_the_settings_as_three_minutes_minus_a_tolerance():
    interval, opens_after = job_gate.interval_seconds(get_guardrails())
    assert interval == 180 and opens_after == 150            # D-017 의 3분 · 30초 허용 오차


def test_the_first_run_opens_and_the_next_minutes_stay_closed(tenant):
    assert _claim(tenant) is True                            # 처음
    assert _claim(tenant) is False                           # 곧바로 다음 회차(1분 뒤 흉내)
    _backdate(tenant, 60)
    assert _claim(tenant) is False                           # 1분 뒤
    _backdate(tenant, 120)
    assert _claim(tenant) is False                           # 2분 뒤 — 아직 주기 안


def test_after_the_interval_minus_tolerance_it_opens_again_and_restarts_the_clock(tenant):
    assert _claim(tenant) is True
    _backdate(tenant, 151)                                    # 스케줄러가 몇 초 일찍 불렀어도 150초면 열린다
    assert _claim(tenant) is True
    assert _claim(tenant) is False                            # 방금 열었으니 다시 닫힌다(시계가 다시 시작)
    with get_connection() as conn:
        assert 0 <= job_gate.last_run_age_seconds(conn, tenant_id=tenant, gate=GATE) < 5


# invariant: INV-CS-RT-025
def test_two_workers_at_the_same_moment_only_one_wins(tenant):
    assert _claim(tenant) is True
    _backdate(tenant, 200)
    wins: list[bool] = []
    barrier = threading.Barrier(6)

    def worker():
        barrier.wait()
        wins.append(_claim(tenant))

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert wins.count(True) == 1 and len(wins) == 6          # 일꾼이 몇이 떠도 감시는 한 번


def test_tenants_have_their_own_clock(tenant):
    other = tenant + "_other"
    try:
        assert _claim(tenant) is True and _claim(other) is True
        assert _claim(tenant) is False and _claim(other) is False
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM job_gates WHERE tenant_id=%s", (other,))


def test_the_last_run_age_is_none_until_the_first_claim(tenant):
    with get_connection() as conn:
        assert job_gate.last_run_age_seconds(conn, tenant_id=tenant, gate=GATE) is None
    _claim(tenant)
    with get_connection() as conn:
        age = job_gate.last_run_age_seconds(conn, tenant_id=tenant, gate=GATE)
    assert age is not None and 0 <= age < 5


# ── 일꾼 연결 ───────────────────────────────────────────────────────

def test_the_sweeper_skips_the_whole_watch_while_the_gate_is_closed_and_runs_it_when_open(tenant, monkeypatch):
    """문이 닫힌 회차에는 감시를 **아무것도 안 부른다**(외부 소스 포함). 열린 회차에만 한 번 돈다. `--only trip_cases`(손으로 부름)는 문을 안 본다."""
    from scripts import run_sweepers

    calls: list[str] = []
    monkeypatch.setattr(run_sweepers, "_run_trip_watch_cases", lambda tenant_id: calls.append(tenant_id) or {"checked": 0})

    assert run_sweepers._watch_if_due(tenant, forced=False) == {"checked": 0}          # 처음 — 열렸다
    assert run_sweepers._watch_if_due(tenant, forced=False) == {"skipped_until_due": 1}  # 1분 뒤 회차 — 닫혔다
    _backdate(tenant, 60)
    assert run_sweepers._watch_if_due(tenant, forced=False) == {"skipped_until_due": 1}
    assert calls == [tenant]                                                           # 감시는 한 번뿐
    assert run_sweepers._watch_if_due(tenant, forced=True) == {"checked": 0}           # 손으로 부르면 문을 안 본다
    assert calls == [tenant, tenant]
    _backdate(tenant, 151)
    assert run_sweepers._watch_if_due(tenant, forced=False) == {"checked": 0}          # 한 주기가 지나 다시 열렸다
    assert len(calls) == 3


def test_a_skipped_round_is_not_counted_as_an_error_by_the_sweeper():
    """문이 닫혀 건너뛴 회차는 실패가 아니다 — 일꾼의 종료 코드(`_report_errors`)를 1 로 만들면 스케줄러가 매분 실패로 본다."""
    from scripts import run_sweepers

    assert run_sweepers._report_errors({"trip_cases": {"skipped_until_due": 1}}) == 0
