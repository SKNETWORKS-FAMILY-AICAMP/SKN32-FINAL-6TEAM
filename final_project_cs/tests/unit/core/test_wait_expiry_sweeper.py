"""고객 입력 대기 만료 되잡기(`wait_expiry_sweeper`)의 절차를 DB 없이 검증한다 — INV-CS-RT-018.

★전에는 대기 만료가 **재개를 시도할 때만** 기록돼, 고객이 돌아오지 않으면 Case 가 `waiting_input` 에 영원히 남았다.
  되잡기는 `transition_case(WAIT_EXPIRED)` 하나만 한다 — 자동 resolve 없음 · 고객 알림(outbox) 없음 · Case 마다 CAS.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.application import wait_expiry_sweeper as sweeper
from app.core.case_lifecycle.events import EventType
from app.core.contracts import InvalidTransition, StateConflict

NOW = datetime(2026, 10, 26, 6, 0, tzinfo=UTC)


class FakeConn:
    def __init__(self, rows):
        self.rows, self.sql, self.params, self.transactions = rows, "", None, 0

    def transaction(self):
        conn = self

        class _Ctx:
            def __enter__(self):
                conn.transactions += 1

            def __exit__(self, *exc):
                return False
        return _Ctx()

    def cursor(self):
        conn = self

        class _Cur:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def execute(self, sql, params):
                conn.sql, conn.params = sql, params

            def fetchall(self):
                return list(conn.rows)
        return _Cur()


@pytest.fixture
def transitions(monkeypatch):
    calls, failures = [], {}

    def fake(conn, **kw):
        calls.append(kw)
        error = failures.get(kw["case_id"])
        if error is not None:
            raise error
    monkeypatch.setattr(sweeper, "transition_case", fake)
    return calls, failures


def _row(expires, version=4):
    return (uuid4(), version, expires)


def test_expired_wait_escalates_with_cas_system_actor_and_no_customer_notice(transitions):
    calls, _ = transitions
    row = _row((NOW - timedelta(seconds=1)).isoformat(), version=7)
    conn = FakeConn([row])
    counts = sweeper.sweep_expired_waits(conn, tenant_id="demo", actor_id="wait_expiry_sweeper", limit=10, now=NOW)
    assert counts == {"scanned": 1, "expired": 1, "waiting": 0, "invalid_expiry": 0, "conflicted": 0, "errored": 0}
    assert calls == [{"tenant_id": "demo", "case_id": row[0], "expected_version": 7,
                      "event_type": EventType.WAIT_EXPIRED, "payload": {"wait_reason": "customer_input"},
                      "actor_type": "system", "actor_id": "wait_expiry_sweeper"}]
    assert "outbox" not in calls[0]                                   # 고객 알림 없음
    assert conn.transactions == 2                                     # 조회 1 + Case 마다 자기 트랜잭션 1


def test_candidates_are_this_tenants_customer_input_waits_oldest_first(transitions):
    conn = FakeConn([])
    assert sweeper.sweep_expired_waits(conn, tenant_id="demo", actor_id="s", limit=5, now=NOW)["scanned"] == 0
    sql = " ".join(conn.sql.split())
    assert "tenant_id=%s" in sql and "status='waiting_input'" in sql
    assert "state_json->>'wait_reason'=%s" in sql and "ORDER BY updated_at ASC" in sql
    assert conn.params == ("demo", "customer_input", 5)


def test_unexpired_wait_is_left_alone(transitions):
    calls, _ = transitions
    counts = sweeper.sweep_expired_waits(FakeConn([_row((NOW + timedelta(hours=1)).isoformat())]),
                                         tenant_id="demo", actor_id="s", limit=5, now=NOW)
    assert counts["waiting"] == 1 and counts["expired"] == 0 and calls == []


@pytest.mark.parametrize("value", [None, "", "not-a-date", 12345])
def test_unreadable_expiry_is_counted_not_transitioned(transitions, value):
    calls, _ = transitions
    counts = sweeper.sweep_expired_waits(FakeConn([_row(value)]), tenant_id="demo", actor_id="s", limit=5, now=NOW)
    assert counts["invalid_expiry"] == 1 and calls == []


def test_naive_expiry_is_read_as_utc(transitions):
    calls, _ = transitions
    naive = (NOW - timedelta(minutes=1)).replace(tzinfo=None).isoformat()
    assert sweeper.sweep_expired_waits(FakeConn([_row(naive)]), tenant_id="demo", actor_id="s", limit=5,
                                       now=NOW)["expired"] == 1
    assert len(calls) == 1


def test_race_is_conflicted_and_one_failure_does_not_stop_the_rest(transitions):
    calls, failures = transitions
    past = (NOW - timedelta(hours=1)).isoformat()
    raced, invalid, broken, fine = _row(past), _row(past), _row(past), _row(past)
    failures[raced[0]] = StateConflict("customer resumed first")
    failures[invalid[0]] = InvalidTransition("already escalated")
    failures[broken[0]] = RuntimeError("db hiccup")
    counts = sweeper.sweep_expired_waits(FakeConn([raced, invalid, broken, fine]), tenant_id="demo", actor_id="s",
                                         limit=10, now=NOW)
    assert counts == {"scanned": 4, "expired": 1, "waiting": 0, "invalid_expiry": 0, "conflicted": 2, "errored": 1}
    assert [c["case_id"] for c in calls] == [raced[0], invalid[0], broken[0], fine[0]]


def test_limit_comes_from_guardrails(transitions, monkeypatch):
    class Guard:
        def get(self, key):
            assert key == "reliability.wait_expiry_sweep_limit"
            return 3
    monkeypatch.setattr(sweeper, "get_guardrails", lambda: Guard())
    conn = FakeConn([])
    sweeper.sweep_expired_waits(conn, tenant_id="demo", actor_id="s", now=NOW)
    assert conn.params[-1] == 3


def test_run_sweepers_runs_wait_expiry_for_the_process_tenant_by_default(monkeypatch):
    from scripts import run_sweepers

    seen = []

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False
    monkeypatch.setattr(run_sweepers, "get_connection", lambda: Conn())
    monkeypatch.setattr(run_sweepers, "sweep_expired_waits",
                        lambda conn, **kw: seen.append(kw) or {"scanned": 0, "expired": 0})
    result = run_sweepers._run_jobs("demo", "wait_expiry")
    assert result == {"wait_expiry": {"scanned": 0, "expired": 0}}
    assert seen == [{"tenant_id": "demo", "actor_id": "wait_expiry_sweeper"}]
    source = open(run_sweepers.__file__, encoding="utf-8").read()
    assert 'if only in (None, "wait_expiry"):' in source               # `--only` 없는 전체 회차에도 들어간다(기본 켜짐)
