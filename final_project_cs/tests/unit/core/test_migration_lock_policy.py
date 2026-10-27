"""배포 마이그레이션의 잠금 대기 제한 · 교착 재시도 · 실패 원인 기록 `[2026-10-27 C 전수검사 · 알려진 이슈 (c)]`.

★왜. 2026-10-26 x600 자동 배포 두 번(13:26 · 13:33)이 마이그레이션(111개 SQL 한 트랜잭션)과 실서비스 폴링의 **교착(deadlock)** 으로
  실패했다(`wiki/records/reports/2026-10-26_x600_배포_마이그레이션_교착_수동반영.md`). 마이그레이션 세션에 `lock_timeout` 이 없어
  `trips` 배타 잠금을 끝없이 기다렸고, 실패하면 guard 는 「Migration failed」만 남겨 원인을 DB 로그에서 찾아야 했다.
  아마존 CD(`aws_cd.migration_job`)도 같은 `apply_all` 을 부른다 — 같은 위험이다.

★재시도가 안전한 이유: 교착(40P01) · 잠금 대기 초과(55P03)는 PostgreSQL 이 **그 트랜잭션 전체를 되돌린 것이 확정**된 실패다
  (결과가 불확실한 시간 초과가 아니다). 그래서 정해진 횟수만 다시 한다. 그 밖의 오류는 한 번에 그대로 올라간다.
★값(잠금 대기 · 횟수 · 사이 대기)은 마이그레이션 산출물 `migrations/migration-plan.json` 의 `lock_policy` 한 곳 — 없으면 시작하지 않는다(무음 기본값 없음).
"""
import json
from contextlib import contextmanager
from types import SimpleNamespace

import psycopg
import pytest
from psycopg.pq import TransactionStatus

from app.infrastructure.db import migrate, migration_plan

POLICY = {"lock_timeout_ms": 4000, "attempts": 3, "retry_wait_seconds": [1.5, 4]}


class _Conn:
    def __init__(self, failures, status=TransactionStatus.IDLE):
        self.failures, self.executed, self.transactions = list(failures), [], 0
        self.info = SimpleNamespace(transaction_status=status)

    @contextmanager
    def transaction(self):
        self.transactions += 1
        yield

    def execute(self, sql, params=None):
        self.executed.append(sql)
        if sql == "MIGRATION SQL" and self.failures:
            failure = self.failures.pop(0)
            if failure is not None:
                raise failure


@pytest.fixture
def world(monkeypatch):
    monkeypatch.setattr(migrate, "compiled_sql", lambda: "MIGRATION SQL")
    monkeypatch.setattr(migrate, "lock_policy", lambda directory: POLICY)
    sleeps = []
    return sleeps


def test_the_lock_policy_is_read_from_the_migration_plan_and_required(tmp_path):
    plan = {"version": 1, "historical_files": []}
    (tmp_path / "migration-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError, match="lock_policy"):
        migration_plan.lock_policy(tmp_path)                       # ★없으면 기본값으로 조용히 돌지 않는다
    for bad in ({"lock_timeout_ms": 0, "attempts": 3, "retry_wait_seconds": [1, 2]},
                {"lock_timeout_ms": 4000, "attempts": 0, "retry_wait_seconds": []},
                {"lock_timeout_ms": 4000, "attempts": 3, "retry_wait_seconds": [1]},     # 사이 대기가 횟수-1 개가 아니다
                {"lock_timeout_ms": "4s", "attempts": 3, "retry_wait_seconds": [1, 2]}):
        (tmp_path / "migration-plan.json").write_text(json.dumps({**plan, "lock_policy": bad}), encoding="utf-8")
        with pytest.raises(ValueError):
            migration_plan.lock_policy(tmp_path)
    (tmp_path / "migration-plan.json").write_text(json.dumps({**plan, "lock_policy": POLICY}), encoding="utf-8")
    assert migration_plan.lock_policy(tmp_path) == POLICY


def test_the_shipped_plan_has_a_lock_policy():
    policy = migration_plan.lock_policy(migrate.MIGRATION_DIR)
    assert policy["lock_timeout_ms"] > 0 and policy["attempts"] >= 2


def test_a_deadlock_is_retried_with_a_lock_timeout_and_logged(world, capsys):
    conn = _Conn([psycopg.errors.DeadlockDetected("deadlock detected relation 17188 secret"), None])
    migrate.apply_all(conn, sleep=world.append)
    # 매 시도가 자기 트랜잭션 안에서 lock_timeout 을 먼저 건다
    assert conn.executed == ["SET LOCAL lock_timeout = '4000ms'", "MIGRATION SQL"] * 2
    assert conn.transactions == 2 and world == [1.5]
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines == [{"migration": "retry", "attempt": 1, "attempts": 3, "error": "DeadlockDetected",
                      "sqlstate": "40P01", "wait_seconds": 1.5}]


def test_lock_waits_that_never_clear_stop_after_the_bounded_attempts(world):
    conn = _Conn([psycopg.errors.LockNotAvailable("x")] * 5)
    with pytest.raises(migrate.MigrationLockFailed) as failed:
        migrate.apply_all(conn, sleep=world.append)
    assert conn.transactions == 3 and world == [1.5, 4]
    assert (failed.value.error, failed.value.sqlstate, failed.value.attempts) == ("LockNotAvailable", "55P03", 3)


@pytest.mark.parametrize("error", [psycopg.errors.UndefinedTable("x"), psycopg.errors.SyntaxError("x"),
                                   psycopg.errors.QueryCanceled("x"), RuntimeError("bug")])
def test_other_failures_are_not_retried(world, error):
    conn = _Conn([error, None])
    with pytest.raises(type(error)):
        migrate.apply_all(conn, sleep=world.append)
    assert conn.transactions == 1 and world == []


def test_a_nested_call_keeps_the_callers_transaction_and_does_not_retry(world):
    # 바깥 트랜잭션 안(시험 · 복원 점검)에서는 savepoint 로 한 번만 — 바깥 잠금을 쥔 채 다시 하지 않는다
    conn = _Conn([psycopg.errors.DeadlockDetected("x")], status=TransactionStatus.INTRANS)
    with pytest.raises(psycopg.errors.DeadlockDetected):
        migrate.apply_all(conn, sleep=world.append)
    assert conn.executed == ["MIGRATION SQL"] and world == []


def test_main_prints_only_the_sanitized_failure_line(monkeypatch, capsys):
    @contextmanager
    def connection():
        yield object()

    def failing(conn):
        raise migrate.MigrationLockFailed(error="DeadlockDetected", sqlstate="40P01", attempts=3)

    monkeypatch.setattr(migrate, "get_connection", connection)
    monkeypatch.setattr(migrate, "apply_all", failing)
    monkeypatch.setattr("sys.argv", ["migrate"])
    with pytest.raises(SystemExit) as stopped:
        migrate.main()
    assert stopped.value.code == 1
    out = capsys.readouterr().out.strip().splitlines()
    assert json.loads(out[-1]) == {"migration": "failed", "error": "DeadlockDetected", "sqlstate": "40P01",
                                   "attempts": 3}


def test_main_reports_other_database_failures_by_kind_only(monkeypatch, capsys):
    @contextmanager
    def connection():
        yield object()

    def failing(conn):
        raise psycopg.errors.UndefinedTable('relation "secret_table" does not exist password=hunter2')

    monkeypatch.setattr(migrate, "get_connection", connection)
    monkeypatch.setattr(migrate, "apply_all", failing)
    monkeypatch.setattr("sys.argv", ["migrate"])
    with pytest.raises(SystemExit):
        migrate.main()
    out = capsys.readouterr().out
    assert json.loads(out.strip().splitlines()[-1]) == {"migration": "failed", "error": "UndefinedTable",
                                                        "sqlstate": "42P01", "attempts": 1}
    assert "hunter2" not in out and "secret_table" not in out
