"""실제 SQL 엔진의 트랜잭션으로 ITS 전체·키별 동시 차감과 롤백을 검사한다.

이 단위 시험은 SQLite 호환 어댑터를 쓴다. PostgreSQL 실행 증거를 대신하지 않는다.
"""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from app.domains.travel_ops.ports.data_sources.its_key_budget import ItsKeyBudget, key_meter

NOW = datetime(2026, 10, 18, 4, tzinfo=UTC)


class SqlConnection:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=15, isolation_level=None)
        self.db.create_function("now", 0, lambda: NOW.isoformat())

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    @contextmanager
    def cursor(self):
        yield self

    def execute(self, sql, params):
        if "ANY(%s)" in sql:
            meters, periods = params
            sql = sql.replace("meter = ANY(%s)", "meter IN (" + ",".join("?" for _ in meters) + ")")
            sql = sql.replace("period = ANY(%s)", "period IN (" + ",".join("?" for _ in periods) + ")")
            params = [*meters, *periods]
        self.result = self.db.execute(sql.replace("%s", "?"), params)
        return self

    def fetchone(self):
        return self.result.fetchone()


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "its-transaction-proof.sqlite"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE external_call_budget (meter TEXT NOT NULL, period TEXT NOT NULL, "
                     "used INTEGER NOT NULL, cap INTEGER NOT NULL, updated_at TEXT, exhausted_at TEXT, learned_cap INTEGER, "
                     "failed INTEGER NOT NULL DEFAULT 0, rejected INTEGER NOT NULL DEFAULT 0, "
                     "PRIMARY KEY(meter,period), CHECK(used<=cap))")
    return path


def budget(path, *, day=1000, month=0, key_day=0, key_month=0, now=NOW, share=1.0, override=None):
    return ItsKeyBudget(connection_factory=lambda: SqlConnection(path), day_limit=day, month_limit=month,
                        key_day_limit=key_day, key_month_limit=key_month, clock=lambda: now, share=share,
                        cap_resolver=override or (lambda conn, meter, caps: caps))


def rows(path):
    with sqlite3.connect(path) as conn:
        return {(m, p): (u, c, f, e) for m, p, u, c, f, e in conn.execute(
            "SELECT meter,period,used,cap,failed,exhausted_at FROM external_call_budget")}


def test_key_cap_refusal_rolls_back_total_and_all_four_rows(database):
    reader = budget(database, day=3, key_day=1)
    assert reader.reserve("first") == "allowed"
    before = rows(database)
    assert reader.reserve("first") == "key_exhausted"
    assert rows(database) == before
    assert reader.reserve("second") == "allowed"
    assert rows(database)[("its", "day:2026-10-18")][0] == 2


def test_total_cap_is_shared_between_keys_and_new_process_objects(database):
    assert budget(database, day=2).reserve("first") == "allowed"
    assert budget(database, day=2).reserve("second") == "allowed"
    before = rows(database)
    assert budget(database, day=2).reserve("third") == "total_exhausted"
    assert rows(database) == before


def test_eight_concurrent_callers_cannot_exceed_the_total_or_key_cap(database):
    def worker(index):
        return budget(database, day=20, key_day=12).reserve("first" if index % 2 else "second")
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(worker, range(48)))
    data = rows(database)
    assert outcomes.count("allowed") == 20
    assert data[("its", "day:2026-10-18")][0] == 20
    assert all(data[(key_meter(key), "day:2026-10-18")][0] <= 12 for key in ("first", "second"))
    assert sum(data[(key_meter(key), "day:2026-10-18")][0] for key in ("first", "second")) == 20


def test_monthly_operator_cap_is_also_shared_between_keys(database):
    reader = budget(database, day=10, month=1)
    assert reader.reserve("first") == "allowed"
    before = rows(database)
    assert reader.reserve("second") == "total_exhausted" and rows(database) == before


def test_key_monthly_cap_does_not_increase_total_on_refusal(database):
    reader = budget(database, day=10, key_month=1)
    assert reader.reserve("first") == "allowed"
    before = rows(database)
    assert reader.reserve("first") == "key_exhausted" and rows(database) == before


def test_known_daily_block_skips_key_until_korean_midnight_without_resetting_total(database):
    reader = budget(database, day=3)
    reader.mark_exhausted("first", "day")
    assert reader.reserve("first") == "key_exhausted"
    assert reader.reserve("second") == "allowed"
    tomorrow = datetime(2026, 10, 18, 15, 0, tzinfo=UTC)
    assert budget(database, day=3, now=tomorrow).reserve("first") == "allowed"
    data = rows(database)
    assert data[("its", "day:2026-10-18")][0] == 1
    assert data[("its", "day:2026-10-19")][0] == 1
    assert data[("its", "month:2026-10")][0] == 2


def test_confirmed_monthly_block_survives_midnight_but_not_a_new_month(database):
    reader = budget(database)
    reader.mark_exhausted("first", "month")
    tomorrow = datetime(2026, 10, 18, 15, 0, tzinfo=UTC)
    assert budget(database, now=tomorrow).reserve("first") == "key_exhausted"
    next_month = datetime(2026, 10, 31, 15, 0, tzinfo=UTC)
    assert budget(database, now=next_month).reserve("first") == "allowed"


def test_legacy_provider_mark_does_not_reset_or_replace_global_operator_counter(database):
    reader = budget(database, day=3)
    assert reader.reserve("first") == "allowed"
    with sqlite3.connect(database) as conn:
        conn.execute("UPDATE external_call_budget SET exhausted_at=? WHERE meter='its'", (NOW.isoformat(),))
    reader.mark_exhausted("first", "day")
    assert reader.reserve("first") == "key_exhausted"
    assert reader.reserve("second") == "allowed"
    assert rows(database)[("its", "day:2026-10-18")][0] == 2


def test_failure_increases_both_failed_counters_without_refunding_used(database):
    reader = budget(database)
    reader.reserve("first")
    reader.record_failure("first")
    assert all(data[0] == 1 and data[2] == 1 for data in rows(database).values())


def test_operator_override_and_lower_priority_share_cannot_be_bypassed(database):
    reader = budget(database, day=10, share=0.5, override=lambda conn, meter, caps: {**caps, "day": 4})
    assert [reader.reserve(str(i)) for i in range(3)] == ["allowed", "allowed", "total_exhausted"]


def test_zero_total_daily_cap_blocks_unmetered_traffic(database):
    assert budget(database, day=0).reserve("first") == "total_exhausted"
