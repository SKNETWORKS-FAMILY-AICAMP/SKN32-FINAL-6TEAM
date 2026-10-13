"""Opt-in isolated PostgreSQL WASM tests. No configured business DB is opened."""
import json
import os
import re
import subprocess
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application import operations_diagnostics as diag, operations_policy as policy
from app.presentation import admin_api, admin_operations_api as api
from app.presentation.ui import auth


class PG:
    def __init__(self, process): self.process = process
    def request(self, message):
        def encode(value):
            if hasattr(value, "obj"): return json.dumps(value.obj)
            if isinstance(value, (UUID, date, datetime)): return value.isoformat() if hasattr(value, "isoformat") else str(value)
            raise TypeError(type(value).__name__)
        self.process.stdin.write(json.dumps(message, default=encode) + "\n")
        self.process.stdin.flush()
        response = json.loads(self.process.stdout.readline())
        if "error" in response: raise RuntimeError(response["error"])
        return response["result"]
    def execute(self, sql, params=()):
        index = iter(range(1, len(params)+1))
        sql = re.sub(r"%s", lambda _: "$" + str(next(index)), sql)
        result = self.request({"sql": sql, "params": params})
        rows = []
        for row in result.get("rows", []):
            out = []
            for field in result["fields"]:
                value = row[field["name"]]
                if value is not None and field["dataTypeID"] in (1184, 1114): value = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if value is not None and field["dataTypeID"] == 2950: value = UUID(value)
                out.append(value)
            rows.append(tuple(out))
        self.rows, self.rowcount = rows, result.get("affectedRows", len(rows))
        return self
    def fetchone(self): return self.rows[0] if self.rows else None
    def fetchall(self): return self.rows
    @contextmanager
    def cursor(self): yield self
    @contextmanager
    def transaction(self):
        self.execute("BEGIN")
        try: yield self
        except BaseException:
            self.execute("ROLLBACK")
            raise
        else: self.execute("COMMIT")


@pytest.fixture(scope="module")
def pg():
    module = os.environ.get("OPS_PGLITE_MODULE")
    if not module: pytest.skip("OPS_PGLITE_MODULE is required; never falls back to business DB")
    process = subprocess.Popen(["node", str(Path(__file__).with_name("operations_pglite.mjs"))], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    assert process.stdout.readline().strip() == "ready"
    database = PG(process)
    database.request({"script": True, "sql": "CREATE TABLE tenants(tenant_id text PRIMARY KEY); CREATE TABLE customers(customer_id uuid PRIMARY KEY,tenant_id text, external_id text); CREATE TABLE trips(trip_id uuid PRIMARY KEY,tenant_id text,customer_id uuid);"})
    root = Path(__file__).resolve().parents[3]
    database.request({"script": True, "sql": (root / "app/infrastructure/db/migrations/226_admin_operations.sql").read_text(encoding="utf-8")})
    sql = (root / "app/infrastructure/db/migrations/902_unattended_operations.sql").read_text(encoding="utf-8")
    database.request({"script": True, "sql": sql})
    database.request({"script": True, "sql": sql})
    yield database
    process.stdin.close()
    process.wait(timeout=15)


@pytest.fixture
def db(pg):
    tenant = "ops_" + uuid4().hex
    customer, trip = uuid4(), uuid4()
    pg.execute("INSERT INTO tenants VALUES(%s)", (tenant,))
    pg.execute("INSERT INTO customers VALUES(%s,%s,%s)", (customer, tenant, "test-traveler"))
    pg.execute("INSERT INTO trips VALUES(%s,%s,%s)", (trip, tenant, customer))
    @contextmanager
    def connection(): yield pg
    return SimpleNamespace(pg=pg, tenant=tenant, customer=customer, trip=trip, connection=connection)


def event(db, **changes):
    return diag.Event(tenant_id=db.tenant, customer_id=db.customer, trip_id=db.trip, kind="processing_error",
                      code="SOURCE_FAILED", deployment="test-deployment", policy_version="v1", **changes)


def test_100_events_one_fault_exact_count_and_unique_customers(db):
    ids = []
    for i in range(100):
        customer, trip = uuid4(), uuid4()
        db.pg.execute("INSERT INTO customers VALUES(%s,%s,%s)", (customer, db.tenant, f"test-traveler-{i}"))
        db.pg.execute("INSERT INTO trips VALUES(%s,%s,%s)", (trip, db.tenant, customer))
        item = event(db).model_copy(update={"customer_id": customer, "trip_id": trip})
        ids.append(item)
        with db.pg.transaction(): assert diag.persist(db.pg, item)
    with db.pg.transaction(): assert not diag.persist(db.pg, ids[0])
    page = diag.listing(db.pg, db.tenant)
    assert len(page["items"]) == 1
    assert page["items"][0]["occurrences"] == 100
    assert page["items"][0]["affected_customers"] == 100


def test_durable_replay_commit_then_retry_is_idempotent(db, tmp_path):
    spool = diag.Spool(tmp_path / "pending.sqlite3")
    item = event(db)
    spool.enqueue(item)
    # Simulate commit followed by crash before deleting the local event.
    with db.pg.transaction(): diag.persist(db.pg, item)
    result = diag.Spool(spool.path).replay(db.connection)
    assert result["processed"] == 1 and result["failed"] == 0 and result["pending"] == 0
    assert diag.listing(db.pg, db.tenant)["items"][0]["occurrences"] == 1


def test_tenant_customer_trip_isolation_and_retention(db):
    stranger = event(db, event_id=uuid4()).model_copy(update={"tenant_id": "wrong_tenant"})
    with pytest.raises(ValueError), db.pg.transaction(): diag.persist(db.pg, stranger)
    with db.pg.transaction(): diag.persist(db.pg, event(db))
    assert diag.listing(db.pg, "wrong_tenant")["items"] == []
    db.pg.execute("UPDATE ops_diagnostic_events SET expires_at=now()-interval '1 second' WHERE tenant_id=%s", (db.tenant,))
    db.pg.execute("UPDATE ops_defect_customers SET expires_at=now()-interval '1 second' WHERE tenant_id=%s", (db.tenant,))
    with db.pg.transaction(): counts = diag.prune(db.pg)
    assert counts["events"] == 1 and counts["customers"] == 1
    item = diag.listing(db.pg, db.tenant)["items"][0]
    assert item["occurrences"] == 1 and item["affected_customers"] == 0


def test_deleted_customer_pending_event_is_rejected_not_resurrected(db, tmp_path):
    spool = diag.Spool(tmp_path / "pending.sqlite3")
    spool.enqueue(event(db))
    db.pg.execute("DELETE FROM customers WHERE customer_id=%s", (db.customer,))
    result = spool.replay(db.connection)
    assert result["rejected"] == 1 and result["failed"] == 0 and result["pending"] == 0
    assert diag.listing(db.pg, db.tenant)["items"] == []


def test_customer_deletion_removes_personal_links_but_keeps_fault_count(db):
    with db.pg.transaction(): diag.persist(db.pg, event(db))
    db.pg.execute("DELETE FROM customers WHERE customer_id=%s", (db.customer,))
    item = diag.listing(db.pg, db.tenant)["items"][0]
    assert item["occurrences"] == 1 and item["affected_customers"] == 0
    assert db.pg.execute("SELECT customer_id FROM ops_diagnostic_events WHERE tenant_id=%s", (db.tenant,)).fetchone()[0] is None


def test_keyset_pages_do_not_repeat_or_cross_tenants(db):
    for i in range(3):
        with db.pg.transaction(): diag.persist(db.pg, event(db, conditions=[f"CONDITION_{i}"]))
    first = diag.listing(db.pg, db.tenant, limit=2)
    second = diag.listing(db.pg, db.tenant, limit=2, before=(first["next"]["at"], first["next"]["fingerprint"]))
    assert len(first["items"]) == 2 and len(second["items"]) == 1 and second["next"] is None
    assert len({x["fingerprint"] for x in first["items"] + second["items"]}) == 3


def test_db_policy_persists_and_cas_audit_are_atomic(db):
    value = policy.SourcePolicy(allow_paid=True, daily_paid_cap=2, trip_paid_cap=1)
    with db.pg.transaction():
        policy.save(db.pg, db.tenant, expected_revision=0, policy=value, actor="qa", reason="bounded test")
    assert policy.read(db.pg, db.tenant)["policy"]["allow_paid"] is True
    with pytest.raises(Exception, match="다시 읽어"), db.pg.transaction():
        policy.save(db.pg, db.tenant, expected_revision=0, policy=value, actor="qa", reason="stale")
    assert policy.read(db.pg, db.tenant)["revision"] == 1
    assert db.pg.execute("SELECT actor,action FROM admin_audit WHERE tenant_id=%s", (db.tenant,)).fetchall() == [("qa", "source-policy")]


def test_settings_change_actual_selection_budget_failure_and_window(db):
    now = datetime.now(UTC).astimezone(policy.ZoneInfo("Asia/Seoul")).replace(hour=4)
    called = []
    def free(): return policy.Verdict(status="unverifiable", source="free", checked_at=now, valid_until=now+timedelta(minutes=1))
    def paid():
        called.append("paid")
        return policy.Verdict(status="closed", source="google", checked_at=now, valid_until=now+timedelta(minutes=1))
    def lookup(**kw):
        return policy.select(connection_factory=db.connection, tenant=db.tenant, customer_id=db.customer, trip_id=db.trip,
                             resource=str(uuid4()), free=free, paid=paid, provider_reserve=lambda: True, now=now, **kw)
    assert lookup(context="dawn")["status"] == "unverifiable" and not called
    value = policy.SourcePolicy(allow_paid=True, daily_paid_cap=1, trip_paid_cap=1)
    with db.pg.transaction(): policy.save(db.pg, db.tenant, expected_revision=0, policy=value, actor="qa", reason="test")
    assert lookup(context="daytime")["reason"] == "paid_window_closed" and not called
    assert lookup(context="dawn")["status"] == "closed" and called == ["paid"]
    assert lookup(context="dawn")["reason"] == "budget_exhausted" and called == ["paid"]


def test_free_first_never_calls_paid_and_failures_are_not_open(db):
    now = datetime.now(UTC)
    common = dict(connection_factory=db.connection, tenant=db.tenant, customer_id=db.customer, trip_id=db.trip, resource="test-resource", now=now)
    free = lambda: policy.Verdict(status="closed", source="public", checked_at=now, valid_until=now+timedelta(minutes=1))
    assert policy.select(**common, free=free, paid=lambda: pytest.fail("paid must not run"))["reason"] == "verified_free"
    assert policy.select(**common, free=lambda: (_ for _ in ()).throw(OSError("offline")))["reason"] == "free_lookup_failed"
    assert policy.select(**{**common, "customer_id": uuid4()}, free=lambda: pytest.fail("ownership before lookup"))["reason"] == "trip_not_owned"


def test_paid_failure_consumes_budget_and_interval_is_persisted(db):
    now = datetime.now(UTC).astimezone(policy.ZoneInfo("Asia/Seoul")).replace(hour=4)
    with db.pg.transaction(): policy.save(db.pg, db.tenant, expected_revision=0, policy=policy.SourcePolicy(allow_paid=True, daily_paid_cap=3, trip_paid_cap=3), actor="qa", reason="test")
    common = dict(connection_factory=db.connection, tenant=db.tenant, customer_id=db.customer, trip_id=db.trip, resource="same-resource", now=now, context="dawn",
                  free=lambda: (_ for _ in ()).throw(OSError()), paid=lambda: (_ for _ in ()).throw(OSError()), provider_reserve=lambda: True)
    assert policy.select(**common)["reason"] == "paid_lookup_failed"
    assert policy.select(**common)["reason"] == "check_interval"
    assert db.pg.execute("SELECT used FROM ops_lookup_usage WHERE tenant_id=%s", (db.tenant,)).fetchone()[0] == 1


def test_authorized_http_save_read_and_resolution_use_real_db(db, monkeypatch):
    monkeypatch.setattr(api, "get_connection", db.connection)
    monkeypatch.setattr(api, "get_ops_read_connection", db.connection)
    monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(tenant_id=db.tenant))
    monkeypatch.setattr(auth, "operators", lambda: {"qa": (auth.hash_password("test-password", iterations=1000), frozenset({"limits:read", "limits:write", "ops:introspect", "case:read"}))})
    app = FastAPI(); app.include_router(admin_api.build_router()); app.include_router(api.build_router(operator_dependency=admin_api.operator, require_permission=admin_api.require))
    with TestClient(app) as client:
        token = client.get("/admin/api/session").json()["csrf"]
        assert client.post("/admin/api/login", json={"operatorId": "qa", "password": "test-password"}, headers={"X-CSRF-Token": token}).status_code == 200
        token = client.get("/admin/api/session").json()["csrf"]
        payload = {"expected_revision": 0, "policy": policy.SourcePolicy().model_dump(), "reason": "QA test"}
        assert client.patch("/admin/api/source-policy", json=payload, headers={"X-CSRF-Token": token}).status_code == 200
        assert client.get("/admin/api/source-policy").json()["revision"] == 1
        item = event(db, request_id=uuid4())
        with db.pg.transaction(): diag.persist(db.pg, item)
        response = client.get("/admin/api/diagnostics").json()
        assert response["items"][0]["occurrences"] == 1
        assert client.get(f"/admin/api/diagnostics/{item.fingerprint()}/customers").json()["customers"] == [str(db.customer)]
        occurrence = client.get(f"/admin/api/diagnostics/{item.fingerprint()}/events").json()["events"][0]
        assert occurrence["event_id"] == str(item.event_id) and occurrence["request_id"] == str(item.request_id)
        assert client.get(f"/admin/api/diagnostics/{item.fingerprint()}/events?after=invalid").status_code == 422
        assert client.patch(f"/admin/api/diagnostics/{item.fingerprint()}/resolution", json={"version": "fixed-v2", "reason": "verified"}, headers={"X-CSRF-Token": token}).status_code == 200
        assert client.get("/admin/api/diagnostics").json()["items"][0]["resolved_version"] == "fixed-v2"


def test_customer_receipt_ownership_masking_pagination_and_idempotency(db, monkeypatch):
    from app.domains.travel_ops.modules.web_account import admin_customer_api as support
    monkeypatch.setattr(support, "get_connection", db.connection)
    identity = SimpleNamespace(tenant_id=db.tenant, customer_id=db.customer)
    app = FastAPI(); app.include_router(support.build_router())
    app.dependency_overrides[support.web_cookie.require_identity] = lambda: identity
    client = TestClient(app)
    draft = {"requestId": str(uuid4()), "title": "여행 장소 오류", "body": "test.person@example.invalid 010-1234-5678", "language": "ko"}
    response = client.post("/v1/web/support/inquiries", json=draft)
    assert response.status_code == 201
    item = response.json()["inquiry"]
    assert item["status"] == "기록 완료" and item["replies"] == []
    assert "1234" not in item["body"] and "test.person" not in item["body"]
    assert client.post("/v1/web/support/inquiries", json=draft).status_code == 201
    assert diag.listing(db.pg, db.tenant)["items"][0]["occurrences"] == 1
    other = {**draft, "requestId": str(uuid4()), "title": "두 번째 건의"}
    assert client.post("/v1/web/support/inquiries", json=other).status_code == 201
    first = client.get("/v1/web/support/inquiries?limit=1").json()
    assert first["next"] and len(first["inquiries"]) == 1
    second = client.get("/v1/web/support/inquiries?limit=1&before=" + first["next"]).json()
    assert len(second["inquiries"]) == 1 and second["next"] is None
    identity.customer_id = uuid4()
    assert client.get("/v1/web/support/inquiries").json()["inquiries"] == []
    assert client.get("/v1/web/support/inquiries?before=" + first["next"]).status_code == 404


@pytest.fixture
def postgres_db():
    """멀티 연결 시험 전용 DB만 허용한다. 업무 설정으로 대체하지 않는다."""
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict

    dsn = os.environ.get("ACOP_INTEGRATION_POSTGRES_TEST_DSN")
    if not dsn:
        pytest.skip("task-owned PostgreSQL opt-in is required")
    info = conninfo_to_dict(dsn)
    assert info.get("host") == "127.0.0.1"
    assert info.get("dbname") == info.get("user") == "integration_test"
    schema = "ops_test_" + uuid4().hex
    tenant, customer, trip = "ops_" + uuid4().hex, uuid4(), uuid4()
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

    @contextmanager
    def connection():
        with psycopg.connect(dsn) as conn:
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            yield conn

    try:
        with connection() as conn:
            conn.execute("CREATE TABLE tenants(tenant_id text PRIMARY KEY); "
                         "CREATE TABLE customers(customer_id uuid PRIMARY KEY,tenant_id text,external_id text); "
                         "CREATE TABLE trips(trip_id uuid PRIMARY KEY,tenant_id text,customer_id uuid)")
            root = Path(__file__).resolve().parents[3]
            for name in ("226_admin_operations.sql", "902_unattended_operations.sql"):
                conn.execute((root / "app/infrastructure/db/migrations" / name).read_text(encoding="utf-8"))
            conn.execute("INSERT INTO tenants VALUES(%s)", (tenant,))
            conn.execute("INSERT INTO customers VALUES(%s,%s,'synthetic')", (customer, tenant))
            conn.execute("INSERT INTO trips VALUES(%s,%s,%s)", (trip, tenant, customer))
        yield SimpleNamespace(tenant=tenant, customer=customer, trip=trip, connection=connection)
    finally:
        # 고정 업무 표가 아니라 이 픽스처가 만든 전용 스키마만 정리한다.
        assert schema.startswith("ops_test_") and len(schema) == 41
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def _concurrent_pair(call):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    start = Barrier(2)

    def run(index):
        start.wait(timeout=10)
        return call(index)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, index) for index in range(2)]
        return [future.result(timeout=20) for future in futures]


@pytest.mark.parametrize("repeat", range(3))
def test_postgres_concurrent_policy_cas_has_one_winner_and_one_audit(postgres_db, repeat):
    db = postgres_db

    def save(index):
        try:
            with db.connection() as conn, conn.transaction():
                policy.save(conn, db.tenant, expected_revision=0, policy=policy.SourcePolicy(),
                            actor=f"qa-{index}", reason="concurrent CAS")
            return "saved"
        except api.admin_service.AdminServiceError as exc:
            assert exc.status_code == 409
            return "conflict"

    assert sorted(_concurrent_pair(save)) == ["conflict", "saved"]
    with db.connection() as conn:
        assert policy.read(conn, db.tenant)["revision"] == 1
        assert conn.execute("SELECT count(*) FROM admin_audit WHERE tenant_id=%s", (db.tenant,)).fetchone()[0] == 1


@pytest.mark.parametrize("repeat", range(3))
def test_postgres_concurrent_paid_lookups_cannot_exceed_one_attempt(postgres_db, repeat):
    from threading import Lock
    db = postgres_db
    now = datetime.now(UTC).astimezone(policy.ZoneInfo("Asia/Seoul")).replace(hour=4)
    with db.connection() as conn, conn.transaction():
        policy.save(conn, db.tenant, expected_revision=0,
                    policy=policy.SourcePolicy(allow_paid=True, daily_paid_cap=1, trip_paid_cap=1),
                    actor="qa", reason="one logical attempt")
    calls, mutex = [], Lock()

    def paid():
        with mutex:
            calls.append("paid")
        return policy.Verdict(status="closed", source="test", checked_at=now, valid_until=now+timedelta(minutes=1))

    def lookup(index):
        return policy.select(connection_factory=db.connection, tenant=db.tenant, customer_id=db.customer,
            trip_id=db.trip, resource=f"resource-{index}", now=now, context="dawn",
            free=lambda: policy.Verdict(status="unverifiable", source="test", checked_at=now, valid_until=now),
            paid=paid, provider_reserve=lambda: True)["reason"]

    assert sorted(_concurrent_pair(lookup)) == ["budget_exhausted", "verified_paid"]
    assert calls == ["paid"]
    with db.connection() as conn:
        assert conn.execute("SELECT sum(used) FROM ops_lookup_usage WHERE tenant_id=%s", (db.tenant,)).fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM ops_lookup_checks WHERE tenant_id=%s", (db.tenant,)).fetchone()[0] == 1


def test_postgres_commit_before_spool_ack_keeps_exactly_one_occurrence(postgres_db, tmp_path):
    db = postgres_db
    item = event(db)
    spool = diag.Spool(tmp_path / "pending.sqlite3")
    assert spool.enqueue(item) == "spooled"
    with db.connection() as conn, conn.transaction():
        assert diag.persist(conn, item)
    result = diag.Spool(spool.path).replay(db.connection)
    assert result == {"processed": 1, "failed": 0, "expired": 0, "rejected": 0, "pending": 0, "bytes": 0, "lost": 0}
    with db.connection() as conn:
        assert diag.listing(conn, db.tenant)["items"][0]["occurrences"] == 1


def test_postgres_trip_deleted_between_scope_check_and_reservation_prevents_paid_call(postgres_db):
    db = postgres_db
    now = datetime.now(UTC).astimezone(policy.ZoneInfo("Asia/Seoul")).replace(hour=4)
    with db.connection() as conn, conn.transaction():
        policy.save(conn, db.tenant, expected_revision=0,
                    policy=policy.SourcePolicy(allow_paid=True, daily_paid_cap=1, trip_paid_cap=1),
                    actor="qa", reason="deletion race")

    def free():
        with db.connection() as conn:
            conn.execute("DELETE FROM trips WHERE trip_id=%s", (db.trip,))
        return policy.Verdict(status="unverifiable", source="test", checked_at=now, valid_until=now)

    result = policy.select(connection_factory=db.connection, tenant=db.tenant, customer_id=db.customer,
        trip_id=db.trip, resource="deleted-resource", now=now, context="dawn", free=free,
        paid=lambda: pytest.fail("deleted trip must never call a paid provider"), provider_reserve=lambda: True)
    assert result["reason"] == "reservation_failed"
    assert result["diagnostic"]["status"] == "rejected"
    with db.connection() as conn:
        assert conn.execute("SELECT count(*) FROM ops_lookup_usage WHERE tenant_id=%s", (db.tenant,)).fetchone()[0] == 0
