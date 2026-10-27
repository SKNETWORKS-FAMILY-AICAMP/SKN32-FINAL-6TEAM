"""마이그레이션을 **데이터가 있는 DB 에 다시 돌려도** 깨지지 않는다 (2026-10-05).

☆실제 사고: `migrate.py` 는 모든 파일을 번호 순서대로 **매번 전부** 다시 돌린다. 032~035 가 각자 `pending_changes_reason_check`
를 자기 시점의 값 목록으로 다시 걸었고, 뒤 마이그레이션이 값을 넓힌 뒤에 032 가 좁은 목록을 걸다가 이미 들어 있는
`relaxed`·`requested_options`·`other_options` 행에 걸려 `CheckViolation` 으로 전체가 멈췄다. 파일 머리말은 「다시 돌려도 안전하다」고
적고 있었다 — 빈 DB 에서만 돌려 봐서 몰랐다. 이 시험은 **이유마다 행을 넣은 뒤** 다시 돌린다.

임시 DB 를 만들어 쓴다(운영 DB 를 건드리지 않는다). DB 를 만들 권한이 없으면 건너뛴다.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import pytest

from app.core.settings import get_settings
from app.infrastructure.db.migrate import apply_all

#: 가장 넓은 최종 목록 — 마이그레이션이 이유를 더하면 여기에도 더한다(빠지면 시험이 알려 준다)
FINAL_REASONS = {"ask_first", "protected", "safety_alert", "indoor_unknown", "indoor_unknown_options",
                 "relaxed", "requested_options", "other_options", "forecast_advisory", "forecast_advisory_options"}


def _dsn_for(db_name: str) -> str:
    parts = urlsplit(get_settings().database_url.replace("postgresql+psycopg://", "postgresql://", 1))
    return urlunsplit(parts._replace(path="/" + db_name))


@pytest.fixture()
def scratch():
    psycopg = pytest.importorskip("psycopg")
    name = "acop_migtest_" + uuid4().hex[:10]
    try:
        admin = psycopg.connect(_dsn_for("postgres"), autocommit=True, connect_timeout=5)
        admin.execute(f'CREATE DATABASE "{name}"')
    except Exception as exc:                                  # noqa: BLE001
        pytest.skip(f"임시 DB 를 만들 수 없다: {str(exc).splitlines()[0]}")
    conn = psycopg.connect(_dsn_for(name), autocommit=True)
    try:
        yield conn
    finally:
        conn.close()
        admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.close()


def _allowed(conn) -> set[str]:
    definition = conn.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                              "WHERE conname = 'pending_changes_reason_check'").fetchone()[0]
    return set(re.findall(r"'([a-z_]+)'::text", definition))


def test_빈_DB_에서는_번호_순서대로_가장_넓은_목록이_된다(scratch):
    apply_all(scratch)
    assert _allowed(scratch) == FINAL_REASONS


def test_이유마다_행이_있는_DB_에_다시_돌려도_멈추지_않고_좁히지_않는다(scratch):
    apply_all(scratch)
    try:
        scratch.execute("SET session_replication_role = replica")    # 여행 행 없이 넣는다(외래키 검사 끔)
    except Exception as exc:                                         # noqa: BLE001
        pytest.skip(f"외래키 검사를 끌 권한이 없다: {str(exc).splitlines()[0]}")
    for reason in sorted(FINAL_REASONS):
        scratch.execute(
            "INSERT INTO pending_changes (tenant_id, trip_id, item_id, base_version, reason) "
            "VALUES ('migtest', gen_random_uuid(), gen_random_uuid(), 1, %s)", (reason,))
    scratch.execute("SET session_replication_role = DEFAULT")

    apply_all(scratch)       # ★전에는 여기서 CheckViolation — 032 가 좁은 목록을 다시 걸었다
    apply_all(scratch)       # 한 번 더 — 매번 같아야 한다

    assert _allowed(scratch) == FINAL_REASONS
    got = {r[0] for r in scratch.execute("SELECT reason FROM pending_changes").fetchall()}
    assert got == FINAL_REASONS                                     # 행은 하나도 잃지 않았다
    for table in ("orders", "order_items", "shipments", "returns", "products"):
        assert scratch.execute("SELECT to_regclass(%s)", ("public." + table,)).fetchone()[0] is None


def test_옛_DB_도_넓어진다(scratch):
    """제약이 옛 목록(032 이전)인 DB 에서도 번호 순서대로 최종 목록까지 넓어진다."""
    apply_all(scratch)
    scratch.execute("ALTER TABLE pending_changes DROP CONSTRAINT pending_changes_reason_check")
    scratch.execute("ALTER TABLE pending_changes ADD CONSTRAINT pending_changes_reason_check "
                    "CHECK (reason IN ('ask_first', 'protected', 'safety_alert'))")
    assert _allowed(scratch) == {"ask_first", "protected", "safety_alert"}
    apply_all(scratch)
    assert _allowed(scratch) == FINAL_REASONS


def test_fresh_database_has_travel_schema_without_retired_commerce_tables(scratch):
    apply_all(scratch)
    for table in ("orders", "order_items", "shipments", "returns", "products"):
        assert scratch.execute("SELECT to_regclass(%s)", ("public." + table,)).fetchone()[0] is None
    for table in ("trips", "customers", "customer_cases"):
        assert scratch.execute("SELECT to_regclass(%s)", ("public." + table,)).fetchone()[0] is not None


def _plan(tmp_path, monkeypatch, sources):
    import json
    from app.infrastructure.db import migrate
    for name, source in sources.items():
        (tmp_path / name).write_text(source, encoding="utf-8")
    # `[2026-10-27 통합 K]` 계약상 plan 에 잠금 정책(lock_policy)이 반드시 있다(없으면 apply_all 이 시작하지 않는다 — C 전수검사).
    #   임시 plan 도 실제 plan 의 값을 그대로 싣는다(값을 시험에서 새로 만들지 않는다)
    real = json.loads((migrate.MIGRATION_DIR / "migration-plan.json").read_text(encoding="utf-8"))
    (tmp_path / "migration-plan.json").write_text(json.dumps({"version": 1, "historical_files": [],
                                                              "lock_policy": real["lock_policy"]}))
    monkeypatch.setattr(migrate, "MIGRATION_DIR", tmp_path)


def test_forced_failure_rolls_back_earlier_ddl_and_existing_row(scratch, tmp_path, monkeypatch):
    import psycopg
    scratch.execute("CREATE TABLE travel_atomic_probe (id int PRIMARY KEY, value text)")
    scratch.execute("INSERT INTO travel_atomic_probe VALUES (1, 'before')")
    _plan(tmp_path, monkeypatch, {
        "001.sql": "BEGIN; CREATE TABLE new_travel_probe(id int); "
                   "UPDATE travel_atomic_probe SET value='after'; COMMIT;",
        "002.sql": "BEGIN; INSERT INTO new_travel_probe VALUES (7); COMMIT;",
        "003.sql": "SELECT 1/0;",
    })
    with pytest.raises(psycopg.errors.DivisionByZero):
        apply_all(scratch)
    assert scratch.execute("SELECT to_regclass('new_travel_probe')").fetchone()[0] is None
    assert scratch.execute("SELECT value FROM travel_atomic_probe").fetchone()[0] == 'before'


def test_full_plan_nested_success_belongs_to_caller_transaction(scratch):
    class RollBackCaller(Exception):
        pass
    with pytest.raises(RollBackCaller):
        with scratch.transaction():
            apply_all(scratch)
            assert scratch.execute("SELECT to_regclass('trips')").fetchone()[0] == 'trips'
            apply_all(scratch)
            raise RollBackCaller()
    assert scratch.execute("SELECT to_regclass('trips')").fetchone()[0] is None
    assert scratch.execute("SELECT to_regnamespace('dining')").fetchone()[0] is None


def test_nested_failure_keeps_callers_prior_work(scratch, tmp_path, monkeypatch):
    import psycopg
    scratch.execute("CREATE TABLE caller_travel_probe (value text)")
    _plan(tmp_path, monkeypatch, {
        "001.sql": "BEGIN; CREATE TABLE nested_travel_probe(id int); COMMIT;",
        "002.sql": "SELECT 1/0;",
    })
    with scratch.transaction():
        scratch.execute("INSERT INTO caller_travel_probe VALUES ('caller')")
        with pytest.raises(psycopg.errors.DivisionByZero):
            apply_all(scratch)
        assert scratch.execute("SELECT to_regclass('nested_travel_probe')").fetchone()[0] is None
    assert scratch.execute("SELECT value FROM caller_travel_probe").fetchone()[0] == 'caller'


def test_invalid_later_file_is_rejected_before_first_change(scratch, tmp_path, monkeypatch):
    _plan(tmp_path, monkeypatch, {
        "001.sql": "CREATE TABLE never_created_travel_probe(id int);",
        "002.sql": "BEGIN; SELECT 1; COMMIT AND CHAIN;",
    })
    with pytest.raises(ValueError):
        apply_all(scratch)
    assert scratch.execute("SELECT to_regclass('never_created_travel_probe')").fetchone()[0] is None


def test_literals_and_dollar_function_execute_unchanged(scratch, tmp_path, monkeypatch):
    _plan(tmp_path, monkeypatch, {
        "001.sql": """-- 서울 COMMIT;
BEGIN;
/* BEGIN; /* COMMIT; */ 끝 */
CREATE TABLE travel_phrases(value text);
CREATE FUNCTION travel_phrase() RETURNS text LANGUAGE plpgsql AS $fn$
BEGIN RETURN 'BEGIN; COMMIT; 서울'; END;
$fn$;
INSERT INTO travel_phrases SELECT travel_phrase();
COMMIT;
""",
    })
    apply_all(scratch)
    assert scratch.execute("SELECT value FROM travel_phrases").fetchone()[0] == 'BEGIN; COMMIT; 서울'


def test_old_runner_savepoint_error_and_partial_commit_reproduced(scratch):
    import psycopg
    # 과거 구현과 같은 transaction()+명시적 COMMIT. 새 실행기는 사용하지 않는다.
    with pytest.raises(psycopg.errors.NoActiveSqlTransaction):
        with scratch.transaction():
            with scratch.transaction():
                scratch.execute("BEGIN; CREATE TABLE old_travel_probe(id int); COMMIT;")
    assert scratch.execute("SELECT to_regclass('old_travel_probe')").fetchone()[0] == 'old_travel_probe'


def test_full_plan_forced_failure_rolls_back_all_travel_schema_and_row(scratch, monkeypatch):
    import psycopg
    from app.infrastructure.db import migrate
    scratch.execute("CREATE TABLE existing_travel_probe(value text)")
    scratch.execute("INSERT INTO existing_travel_probe VALUES ('before')")
    full_sql = migrate.compiled_sql()
    monkeypatch.setattr(migrate, 'compiled_sql', lambda: full_sql +
        "\nUPDATE existing_travel_probe SET value='after'; SELECT 1/0;")
    with pytest.raises(psycopg.errors.DivisionByZero):
        migrate.apply_all(scratch)
    assert scratch.execute("SELECT value FROM existing_travel_probe").fetchone()[0] == 'before'
    assert scratch.execute("SELECT to_regclass('trips')").fetchone()[0] is None
    assert scratch.execute("SELECT to_regnamespace('dining')").fetchone()[0] is None
