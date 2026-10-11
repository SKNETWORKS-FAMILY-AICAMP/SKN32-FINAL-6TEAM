"""Customer credentials cannot cross the operator boundary."""
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application import admin_service
from app.presentation import admin_api
from app.presentation.ui import auth


@pytest.fixture
def client(monkeypatch):
    auth.reset_failures()
    hashed = auth.hash_password("correct-password", iterations=1000)
    monkeypatch.setattr(auth, "operators", lambda: {"operator": (hashed, frozenset({"ops:introspect", "limits:write"}))})
    app = FastAPI()
    app.include_router(admin_api.build_router())
    return TestClient(app)


def login(client):
    session = client.get("/admin/api/session").json()
    response = client.post("/admin/api/login", json={"operatorId": "operator", "password": "correct-password"}, headers={"X-CSRF-Token": session["csrf"]})
    assert response.status_code == 200
    return client.get("/admin/api/session").json()["csrf"]


def test_customer_cookie_and_key_do_not_open_snapshot(client):
    client.cookies.set("tripilot_sid_dev", "customer-session")
    assert client.get("/admin/api/snapshot", headers={"X-User-Key": "acop_u_customer"}).status_code == 401


def test_login_requires_prelogin_csrf_and_setting(client, monkeypatch):
    assert client.post("/admin/api/login", json={"operatorId": "operator", "password": "correct-password"}).status_code == 403
    monkeypatch.setattr(auth, "operators", lambda: {})
    session = client.get("/admin/api/session").json()
    assert session["configured"] is False
    assert client.post("/admin/api/login", json={"operatorId": "operator", "password": "correct-password"}, headers={"X-CSRF-Token": session["csrf"]}).status_code == 401


def test_write_csrf_scope_and_revocation(client, monkeypatch):
    csrf = login(client)
    payload = {"type": "block-user", "userId": str(uuid4()), "blocked": True, "reason": "abuse"}
    assert client.post("/admin/api/commands", json=payload).status_code == 403
    assert client.post("/admin/api/commands", json={"type": "approval", "approvalId": f"{uuid4()}:{uuid4()}", "approve": True, "reason": "checked"}, headers={"X-CSRF-Token": csrf}).status_code == 403
    monkeypatch.setattr(auth, "operators", lambda: {})
    assert client.get("/admin/api/snapshot").status_code == 401


def test_actor_spoofing_and_bad_dates_rejected_before_db(client):
    csrf = login(client)
    payload = {"type": "block-user", "userId": str(uuid4()), "blocked": True, "reason": "abuse", "actor": "someone-else"}
    assert client.post("/admin/api/commands", json=payload, headers={"X-CSRF-Token": csrf}).status_code == 422
    payload = {"type": "maintenance", "enabled": True, "message": "점검", "messageEn": "", "endsAt": "2026-99-99T03:00", "reason": "점검"}
    assert client.post("/admin/api/commands", json=payload, headers={"X-CSRF-Token": csrf}).status_code == 422


def test_logout_requires_csrf_and_drops_session(client):
    csrf = login(client)
    assert client.post("/admin/api/logout").status_code == 403
    assert client.post("/admin/api/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.get("/admin/api/session").json()["authenticated"] is False


def test_signed_operator_controls_audit_actor(client, monkeypatch):
    csrf = login(client)
    observed = []
    @contextmanager
    def connection():
        yield SimpleNamespace(transaction=lambda: connection())
    monkeypatch.setattr(admin_api, "get_connection", connection)
    monkeypatch.setattr(admin_service, "mutate", lambda conn, tenant, actor, command: observed.append((actor, command)))
    payload = {"type": "block-user", "userId": str(uuid4()), "blocked": True, "reason": "abuse"}
    assert client.post("/admin/api/commands", json=payload, headers={"X-CSRF-Token": csrf}).status_code == 200
    assert observed[0][0] == "operator"


def test_limits_never_increase_original_provider_caps():
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, *args): pass
        def fetchone(self): return (900, 9000)
    conn = SimpleNamespace(cursor=Cursor)
    assert admin_service.api_cap(conn, "meter", {"day": 100, "month": 1000}) == {"day": 100, "month": 1000}


def test_customer_support_router_has_no_operator_credentials():
    from app.domains.travel_ops.modules.web_account.admin_customer_api import build_router
    app = FastAPI()
    app.include_router(build_router())
    customer = TestClient(app)
    customer.cookies.set(auth.COOKIE, auth.issue(auth.Operator("operator", frozenset({"ops:introspect"}))))
    assert customer.get("/v1/web/support/inquiries").status_code == 401


def test_repeated_login_failure_is_locked(client):
    for _ in range(5):
        session = client.get("/admin/api/session").json()
        assert client.post("/admin/api/login", json={"operatorId": "operator", "password": "wrong"}, headers={"X-CSRF-Token": session["csrf"]}).status_code == 401
    session = client.get("/admin/api/session").json()
    assert client.post("/admin/api/login", json={"operatorId": "operator", "password": "correct-password"}, headers={"X-CSRF-Token": session["csrf"]}).status_code == 429


def test_settings_actor_is_signed_operator(client, monkeypatch):
    csrf = login(client)
    observed = []
    @client.app.patch("/admin/limits")
    async def existing_limits(request: admin_api.Request):
        observed.append(await request.json())
        assert request.headers["Authorization"] == "Bearer configured-key"
        return {"revision": 2}
    monkeypatch.setattr(admin_api, "_api_key", lambda scope: "configured-key")
    payload = {"expected_revision": 1, "changes": {"web.map_provider": "osm"}, "actor": "spoofed", "reason": "checked"}
    assert client.patch("/admin/api/settings/limits", json=payload, headers={"X-CSRF-Token": csrf}).status_code == 200
    assert observed[0]["actor"] == "operator"


def test_customer_support_ownership_filter(monkeypatch):
    from app.domains.travel_ops.modules.web_account import admin_customer_api
    owner, other = str(uuid4()), str(uuid4())
    @contextmanager
    def connection():
        yield object()
    monkeypatch.setattr(admin_customer_api, "get_connection", connection)
    monkeypatch.setattr(admin_customer_api.web_cookie, "authenticate", lambda request: SimpleNamespace(tenant_id="tenant-a", customer_id=owner))
    observed = []
    def records(conn, tenant, kind):
        observed.append(tenant)
        return [{"id": "mine", "userId": owner}, {"id": "other", "userId": other}]
    monkeypatch.setattr(admin_service, "records", records)
    app = FastAPI()
    app.include_router(admin_customer_api.build_router())
    response = TestClient(app).get("/v1/web/support/inquiries")
    assert response.json() == {"inquiries": [{"id": "mine", "userId": owner}]}
    assert observed == ["tenant-a"]
