"""Current install cannot recreate the retired commerce schema (D-023)."""
import json
import re
from contextlib import contextmanager
from types import SimpleNamespace
import pytest
from psycopg.pq import TransactionStatus
from app.infrastructure.db.migration_plan import migration_files
from app.infrastructure.db import migrate

def test_actual_runner_excludes_historical_tables_and_keeps_travel_schema():
    class Connection:
        # `[2026-10-27]` 맨 바깥 호출인지(`transaction_status`) 보고 잠금 대기 제한 · 재시도를 건다 — 실제 psycopg 연결과 같은 칸
        info = SimpleNamespace(transaction_status=TransactionStatus.IDLE)
        sql = None
        active = False
        @contextmanager
        def transaction(self):
            self.active = True
            yield
            self.active = False
        def execute(self, sql):
            assert self.active
            self.sql = sql
    conn = Connection()
    migrate.apply_all(conn)
    sql = re.sub(r"--[^\n]*", "", conn.sql)
    tables = set(re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-z_]+)", sql, re.I))
    assert tables.isdisjoint({"orders", "order_items", "shipments", "returns", "products"})
    assert {"trips", "customers", "customer_cases"} <= tables
    assert not re.search(r"DROP\s+TABLE[^;]*(?:orders|shipments|products)", sql, re.I)
    current, history = migration_files(migrate.MIGRATION_DIR)
    assert set(current).isdisjoint(history)
    assert len(current) + len(history) == len(list(migrate.MIGRATION_DIR.glob("*.sql")))

@pytest.mark.parametrize("names", [["../outside.sql"], ["missing.sql"], ["old.sql", "old.sql"]])
def test_invalid_exclusion_plan_fails_instead_of_silently_skipping(tmp_path, names):
    (tmp_path / "old.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "migration-plan.json").write_text(json.dumps({"version":1,"historical_files":names}), encoding="utf-8")
    with pytest.raises(ValueError):
        migration_files(tmp_path)
