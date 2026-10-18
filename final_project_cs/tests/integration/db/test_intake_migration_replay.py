"""합성 접수 자료로 후속 방법 값이 있는 DB의 SQL 재실행을 검증한다."""
import os
from pathlib import Path
import subprocess

import pytest

from tests.integration.db.test_unattended_operations import PG


def test_reopen_migration_preserves_agent_claims_on_replay():
    if not os.environ.get("OPS_PGLITE_MODULE"):
        pytest.skip("OPS_PGLITE_MODULE 필요: 실제 고객 DB에는 연결하지 않는다")
    process = subprocess.Popen(
        ["node", str(Path(__file__).with_name("operations_pglite.mjs"))],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8",
    )
    assert process.stdout.readline().strip() == "ready"
    pg = PG(process)
    try:
        pg.request({"script": True, "sql": """
            CREATE TABLE trip_intakes (tenant_id text, status text);
            CREATE TABLE intake_claims (method text);
            INSERT INTO trip_intakes VALUES ('synthetic-travel', 'closed');
            INSERT INTO intake_claims VALUES ('llm_agent'), ('trip');
        """})
        migrations = Path(__file__).resolve().parents[3] / "app/infrastructure/db/migrations"
        for _ in range(2):
            for name in ("905_intake_claims_llm_agent.sql", "232_intake_reopen.sql"):
                pg.request({"script": True, "sql": (migrations / name).read_text(encoding="utf-8")})
        assert pg.execute("SELECT method FROM intake_claims ORDER BY method").fetchall() == [("llm_agent",), ("trip",)]
        assert pg.execute("SELECT status FROM trip_intakes").fetchone() == ("closed",)
        with pytest.raises(RuntimeError, match="23514"):
            pg.execute("INSERT INTO intake_claims VALUES ('unsupported')")
    finally:
        process.stdin.close()
        process.wait(timeout=15)
