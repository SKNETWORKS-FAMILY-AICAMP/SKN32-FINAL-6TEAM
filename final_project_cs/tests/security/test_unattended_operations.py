from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.presentation import admin_api, admin_operations_api as api
from app.presentation.ui import auth


@pytest.fixture
def client(monkeypatch):
    auth.reset_failures()
    scopes = {"limits:read", "limits:write", "ops:introspect", "case:read"}
    monkeypatch.setattr(auth, "operators", lambda: {"qa": (auth.hash_password("test-password", iterations=1000), frozenset(scopes))})
    app = FastAPI()
    app.include_router(admin_api.build_router())
    app.include_router(api.build_router(operator_dependency=admin_api.operator, require_permission=admin_api.require))
    return TestClient(app), scopes


def login(client):
    csrf = client.get("/admin/api/session").json()["csrf"]
    assert client.post("/admin/api/login", json={"operatorId": "qa", "password": "test-password"}, headers={"X-CSRF-Token": csrf}).status_code == 200
    return client.get("/admin/api/session").json()["csrf"]


@pytest.mark.parametrize("path", ["/source-policy", "/diagnostics", "/diagnostics/key/customers", "/diagnostics/key/events"])
def test_customer_cannot_open_maintenance_data(client, path):
    c, _ = client
    c.cookies.set("tripilot_sid_dev", "customer-session")
    assert c.get("/admin/api" + path, headers={"X-User-Key": "customer-key"}).status_code == 401


def test_write_requires_csrf_and_permission(client):
    c, scopes = client
    csrf = login(c)
    payload = {"expected_revision": 0, "policy": {"allow_paid": False, "daily_paid_cap": 0, "trip_paid_cap": 0, "check_interval_seconds": 180}, "reason": "test"}
    assert c.patch("/admin/api/source-policy", json=payload).status_code == 403
    scopes.remove("limits:write")
    assert c.patch("/admin/api/source-policy", json=payload, headers={"X-CSRF-Token": csrf}).status_code == 403


def test_read_failures_are_not_empty_normal_results(client, monkeypatch):
    c, _ = client
    login(c)
    @contextmanager
    def fail():
        raise OSError("private connection detail")
        yield
    monkeypatch.setattr(api, "get_ops_read_connection", fail)
    for path in ("source-policy", "diagnostics"):
        response = c.get("/admin/api/" + path)
        assert response.status_code == 503
        assert "private connection" not in response.text


def test_affected_customer_requires_both_scopes(client):
    c, scopes = client
    login(c)
    scopes.remove("case:read")
    assert c.get("/admin/api/diagnostics/key/customers").status_code == 403
    assert c.get("/admin/api/diagnostics/key/events").status_code == 403


def test_resolution_requires_write_permission_and_reports_storage_failure(client, monkeypatch):
    c, scopes = client
    csrf = login(c)
    body = {"version": "fixed-v2", "reason": "verified"}
    @contextmanager
    def fail():
        raise OSError("private connection detail")
        yield
    monkeypatch.setattr(api, "get_connection", fail)
    response = c.patch("/admin/api/diagnostics/key/resolution", json=body, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 503 and "private connection" not in response.text
    scopes.remove("limits:write")
    assert c.patch("/admin/api/diagnostics/key/resolution", json=body, headers={"X-CSRF-Token": csrf}).status_code == 403


def test_signed_actor_and_tenant_cannot_be_spoofed(client, monkeypatch):
    c, _ = client
    csrf = login(c)
    seen = []
    @contextmanager
    def connection():
        yield SimpleNamespace(transaction=connection)
    monkeypatch.setattr(api, "get_connection", connection)
    monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(tenant_id="test_operations"))
    monkeypatch.setattr(api.policy, "save", lambda conn, tenant, **kw: seen.append((tenant, kw)) or {"revision": 1})
    payload = {"expected_revision": 0, "policy": {"allow_paid": False, "daily_paid_cap": 0, "trip_paid_cap": 0, "check_interval_seconds": 180}, "reason": "test"}
    assert c.patch("/admin/api/source-policy", json={**payload, "actor": "other"}, headers={"X-CSRF-Token": csrf}).status_code == 422
    assert c.patch("/admin/api/source-policy", json=payload, headers={"X-CSRF-Token": csrf}).status_code == 200
    assert seen[0][0] == "test_operations" and seen[0][1]["actor"] == "qa"


def test_cursor_pair_is_validated(client):
    c, _ = client
    login(c)
    assert c.get("/admin/api/diagnostics?before_at=2026-10-12T00:00:00Z").status_code == 422
