"""실제 PostgreSQL 임시 DB만 사용한다. 실제 이용자 자료는 생성/추출/삭제하지 않는다."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest

from app.core.settings import get_settings
from app.domains.travel_ops.components.customer import consents, service_improvement as improvement
from app.domains.travel_ops.modules.web_account import web_guard
from app.infrastructure.db.migrate import apply_all

NOW = datetime.now(timezone.utc)
WEB_VALUES = web_guard.values


@pytest.fixture(scope="module")
def scratch():
    parts = urlsplit(get_settings().database_url.replace("postgresql+psycopg://", "postgresql://", 1))
    name = "acop_improve_" + uuid4().hex[:10]
    admin = psycopg.connect(urlunsplit(parts._replace(path="/postgres")), autocommit=True, connect_timeout=5)
    admin.execute(f'CREATE DATABASE "{name}"')
    conn = psycopg.connect(urlunsplit(parts._replace(path="/" + name)), autocommit=True)
    try:
        apply_all(conn)
        yield conn
    finally:
        conn.close()
        admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.close()


@pytest.fixture()
def setup(scratch, monkeypatch):
    tenant = "improvement-" + uuid4().hex
    scratch.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,'합성 검증')", (tenant,))
    monkeypatch.setattr(web_guard, "values", lambda _: {"web.guest_idle_hours": 168})
    monkeypatch.setattr(improvement, "_geometric", lambda: 0)
    monkeypatch.setattr(improvement, "policy", lambda: {"max_generations": 4, "candidate_days": 7,
        "approved_days": 1825, "review_days": 365, "synthetic_rows": 50, "noisy_min_count": 1})
    return scratch, tenant


def seed(conn, tenant, *, consent=True, stale=False, idle_days=0, multiple=False):
    user = uuid4()
    conn.execute("INSERT INTO customers (customer_id,tenant_id,external_id) VALUES (%s,%s,%s)", (user, tenant, "web:" + user.hex))
    conn.execute("INSERT INTO web_sessions (session_hash,tenant_id,customer_id,last_used_at) VALUES (%s,%s,%s,%s)",
                 (user.hex, tenant, user, NOW - timedelta(days=idle_days)))
    version = "old-version" if stale else consents.current_version(conn, tenant)
    for code in ("service_terms", "privacy", "service_improvement"):
        conn.execute("INSERT INTO consent_events (tenant_id,user_id,session_kind,code,agreed,terms_version,text_sha256) "
                     "VALUES (%s,%s,'guest',%s,%s,%s,%s)", (tenant, user, code, consent or code != "service_improvement", version, "a" * 64))
    for offset in ([1, 2] if multiple else [1]):
        trip = uuid4()
        conn.execute("INSERT INTO trips (trip_id,tenant_id,customer_id,title,party_size,latest_version,created_at) "
                     "VALUES (%s,%s,%s,'개인 원문 제외 확인',4,1,%s)", (trip, tenant, user, NOW + timedelta(seconds=offset)))
        conn.execute("INSERT INTO itinerary_versions (trip_id,version,tenant_id,reason) VALUES (%s,1,%s,'created')", (trip, tenant))
        conn.execute("INSERT INTO itinerary_items (item_id,trip_id,version,tenant_id,seq,kind,title,starts_at) "
                     "VALUES (%s,%s,1,%s,1,'activity','비공개 제목',%s)", (uuid4(), trip, tenant, NOW))
    return user


def evidence():
    return {"reviewer": "isolated-test-reviewer", **dict.fromkeys(improvement.REVIEW_FIELDS, "b" * 64)}


def test_eligibility_is_current_optional_consent_and_one_latest_trip_even_gate_off(setup, monkeypatch):
    conn, tenant = setup
    monkeypatch.setattr(consents, "gate_enabled", lambda: False)
    seed(conn, tenant, multiple=True)
    seed(conn, tenant, consent=False)
    seed(conn, tenant, stale=True)
    seed(conn, tenant, idle_days=8)
    assert improvement._features(conn, tenant, consents.current_version(conn, tenant), NOW) == [(4, 1, 1)]


def test_pending_not_exportable_review_hash_tampering_and_expiry_enforced(setup):
    conn, tenant = setup
    seed(conn, tenant)
    result = improvement.prepare(conn, tenant, now=NOW)
    with pytest.raises(improvement.ImprovementError, match="approved_current_review_required"):
        improvement.export(conn, tenant, result["batch_id"], now=NOW)
    with pytest.raises(improvement.ImprovementError, match="review_scope_changed"):
        improvement.approve(conn, tenant, result["batch_id"], expected_sha256="0" * 64, review=evidence(), now=NOW)
    improvement.approve(conn, tenant, result["batch_id"], expected_sha256=result["payload_sha256"], review=evidence(), now=NOW)
    assert len(improvement.export(conn, tenant, result["batch_id"], now=NOW)["rows"]) == 50
    with pytest.raises(improvement.ImprovementError, match="approved_current_review_required"):
        improvement.export(conn, tenant, result["batch_id"], now=NOW + timedelta(days=366))


@pytest.mark.parametrize("code", ["service_terms", "privacy", "service_improvement"])
def test_withdrawal_invalidates_pending_in_same_transaction_and_keeps_budget(setup, code):
    conn, tenant = setup
    user = seed(conn, tenant)
    improvement.prepare(conn, tenant, now=NOW)
    state = consents.record(conn, tenant_id=tenant, user_id=user, session_kind="guest", version=consents.current_version(conn, tenant),
                            items=[{"code": code, "agreed": False, "text_sha256": "a" * 64}], ip=None, user_agent=None)
    assert not next(item["agreed"] for item in state["items"] if item["code"] == code)
    assert conn.execute("SELECT count(*) FROM service_improvement_batches WHERE tenant_id=%s", (tenant,)).fetchone()[0] == 0
    assert conn.execute("SELECT generations FROM service_improvement_budget WHERE tenant_id=%s", (tenant,)).fetchone()[0] == 1


def test_failed_generation_and_empty_cohort_still_consume_budget_and_cannot_reset(setup, monkeypatch):
    conn, tenant = setup
    for _ in range(3):
        assert improvement.prepare(conn, tenant, now=NOW)["status"] == "insufficient_noisy_support"
    monkeypatch.setattr(improvement, "synthesize", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("generation failed")))
    with pytest.raises(RuntimeError, match="generation failed"):
        improvement.prepare(conn, tenant, now=NOW)
    with pytest.raises(improvement.ImprovementError, match="privacy_budget_exhausted"):
        improvement.prepare(conn, tenant, now=NOW)
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute("DELETE FROM service_improvement_budget WHERE tenant_id=%s", (tenant,))
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute("UPDATE service_improvement_budget SET generations=0 WHERE tenant_id=%s", (tenant,))


def test_parallel_generation_never_exceeds_lifetime_budget(setup):
    from concurrent.futures import ThreadPoolExecutor
    conn, tenant = setup

    def attempt(_):
        with psycopg.connect(conn.info.dsn, autocommit=True) as other:
            try:
                return improvement.prepare(other, tenant, now=NOW)["status"]
            except improvement.ImprovementError as exc:
                return str(exc)

    with ThreadPoolExecutor(max_workers=6) as workers:
        outcomes = list(workers.map(attempt, range(6)))
    assert outcomes.count("insufficient_noisy_support") == 4
    assert outcomes.count("privacy_budget_exhausted") == 2
    assert conn.execute("SELECT generations FROM service_improvement_budget WHERE tenant_id=%s", (tenant,)).fetchone()[0] == 4


def test_candidate_expiration_prunes_only_synthetic_and_migration_reruns_preserve_budget(setup):
    conn, tenant = setup
    seed(conn, tenant)
    improvement.prepare(conn, tenant, now=NOW)
    assert improvement.prune_expired(conn, tenant, now=NOW + timedelta(days=8)) == 1
    assert conn.execute("SELECT count(*) FROM trips WHERE tenant_id=%s", (tenant,)).fetchone()[0] == 1
    migration = Path(__file__).resolve().parents[3] / "app/infrastructure/db/migrations/229_service_improvement.sql"
    conn.execute(migration.read_text(encoding="utf-8"))
    assert conn.execute("SELECT generations FROM service_improvement_budget WHERE tenant_id=%s", (tenant,)).fetchone()[0] == 1


def test_withdrawal_keeps_approved_unlinked_data_and_excludes_future_source(setup):
    conn, tenant = setup
    user = seed(conn, tenant)
    approved = improvement.prepare(conn, tenant, now=NOW)
    improvement.approve(conn, tenant, approved["batch_id"], expected_sha256=approved["payload_sha256"], review=evidence(), now=NOW)
    improvement.prepare(conn, tenant, now=NOW)
    consents.record(conn, tenant_id=tenant, user_id=user, session_kind="guest", version=consents.current_version(conn, tenant),
                    items=[{"code": "service_improvement", "agreed": False, "text_sha256": "a" * 64}], ip=None, user_agent=None)
    assert len(improvement.export(conn, tenant, approved["batch_id"], now=NOW)["rows"]) == 50
    assert improvement._features(conn, tenant, consents.current_version(conn, tenant), NOW) == []
    assert conn.execute("SELECT state FROM service_improvement_batches WHERE tenant_id=%s", (tenant,)).fetchall() == [("approved",)]


def test_invalidation_failure_rolls_back_withdrawal(setup, monkeypatch):
    conn, tenant = setup
    user = seed(conn, tenant)
    improvement.prepare(conn, tenant, now=NOW)

    def fail(*args):
        raise RuntimeError("invalidation failed")

    monkeypatch.setattr(improvement, "invalidate_pending", fail)
    with pytest.raises(RuntimeError, match="invalidation failed"):
        consents.record(conn, tenant_id=tenant, user_id=user, session_kind="guest", version=consents.current_version(conn, tenant),
                        items=[{"code": "service_improvement", "agreed": False, "text_sha256": "a" * 64}], ip=None, user_agent=None)
    assert consents.has(conn, tenant, user, "service_improvement")
    assert conn.execute("SELECT count(*) FROM service_improvement_batches WHERE tenant_id=%s", (tenant,)).fetchone()[0] == 1


def test_review_requires_actual_evidence_fields_and_scope_and_tenant(setup):
    conn, tenant = setup
    seed(conn, tenant)
    result = improvement.prepare(conn, tenant, now=NOW)
    with pytest.raises(improvement.ImprovementError, match="review_evidence_required"):
        improvement.approve(conn, tenant, result["batch_id"], expected_sha256=result["payload_sha256"], review={}, now=NOW)
    with pytest.raises(improvement.ImprovementError, match="candidate_missing_or_expired"):
        improvement.approve(conn, "other-tenant", result["batch_id"], expected_sha256=result["payload_sha256"], review=evidence(), now=NOW)
    with pytest.raises(improvement.ImprovementError, match="candidate_missing_or_expired"):
        improvement.approve(conn, tenant, result["batch_id"], expected_sha256=result["payload_sha256"], review=evidence(), now=NOW + timedelta(days=8))


def test_real_http_optional_consent_defaults_off_records_hash_and_withdraws(setup, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import app.core.settings as settings_module
    from app.infrastructure.db import session
    from app.domains.travel_ops.modules.web_account.web_auth_api import build_auth_router

    conn, tenant = setup
    settings = get_settings().model_copy(update={"tenant_id": tenant, "database_url": conn.info.dsn,
        "web_origin": "https://web.example.test", "web_allowed_origins": "https://web.example.test",
        "public_base_url": "http://api.example.test"})
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)
    monkeypatch.setattr(session, "get_settings", lambda: settings)
    monkeypatch.setattr(web_guard, "values", WEB_VALUES)
    web_guard.clear_cache()
    app = FastAPI()
    app.include_router(build_auth_router())
    try:
        with TestClient(app) as client:
            response = client.post("/v1/web/auth/session")
            assert response.status_code == 201, response.text
            headers = {"Origin": "https://web.example.test", "X-CSRF-Token": response.json()["csrf_token"]}
            state = client.get("/v1/web/consents").json()
            assert len(state["items"]) == 6
            assert not next(item["agreed"] for item in state["items"] if item["code"] == "service_improvement")
            for agreed in (True, False):
                response = client.post("/v1/web/consents", headers=headers, json={"version": state["current_version"],
                    "items": [{"code": "service_improvement", "agreed": agreed, "text_sha256": "c" * 64}]})
                assert response.status_code == 200, response.text
                assert next(item["agreed"] for item in response.json()["items"] if item["code"] == "service_improvement") == agreed
            assert conn.execute("SELECT agreed,text_sha256 FROM consent_events WHERE tenant_id=%s AND code='service_improvement' "
                                "ORDER BY event_id", (tenant,)).fetchall() == [(True, "c" * 64), (False, "c" * 64)]
    finally:
        web_guard.clear_cache()
