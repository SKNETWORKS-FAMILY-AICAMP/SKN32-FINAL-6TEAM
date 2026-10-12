"""독립 PostgreSQL + SDK MCP 프로토콜. 업무 DB에서는 명시적으로 건너뛴다."""
import asyncio
import base64
import hashlib
import os
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from mcp.server.auth.provider import AuthorizationParams

from app.core import settings as settings_module
from app.domains.travel_ops.modules.web_account.personal_ai_oauth import Provider, digest
from app.domains.travel_ops.modules.web_account.personal_ai_store import revoke_customer
from app.domains.travel_ops.modules.web_account import web_agent_keys, web_cookie
from app.infrastructure.db.session import get_connection

from .test_mcp_server import _run, _surface, _data, _error_text, api  # noqa: F401

pytestmark = pytest.mark.skipif(os.environ.get("ACOP_OAUTH_TEST_ISOLATED") != "1", reason="독립 시험 DB 전용 실행기 필요")
CALLBACK = "https://client.example.test/callback"


@pytest.fixture
def oauth_db(api, monkeypatch):
    from app.domains.travel_ops.modules.web_account import personal_ai_oauth
    tenant, customer = api["tenant"], api["customer"]
    settings = settings_module.get_settings().model_copy(update={"public_base_url": "https://api.example.test",
            "web_origin": "https://api.example.test", "web_allowed_origins": "https://api.example.test"})
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO web_social_links(tenant_id,customer_id,provider,subject_hash) VALUES(%s,%s,'google',%s)",
                    (tenant, customer, uuid4().hex))
    p = Provider(tenant, settings_module.get_settings().public_base_url)
    p.preregister("personal-ai", "개인 AI", [CALLBACK])
    monkeypatch.setattr(personal_ai_oauth, "configured_provider", lambda: p)
    yield api, p
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM personal_ai_oauth_records WHERE tenant_id=%s", (tenant,))
        cur.execute("DELETE FROM web_social_links WHERE tenant_id=%s", (tenant,))


def issue(p, customer, scopes=None):
    async def go():
        client = await p.get_client("personal-ai")
        target = await p.authorize(client, AuthorizationParams(state="client-state", scopes=scopes or ["travel:read"],
            code_challenge="x" * 43, redirect_uri=CALLBACK, redirect_uri_provided_explicitly=True, resource=p.resource))
        raw = parse_qs(urlsplit(target).query)["request"][0]
        p.consent(raw, customer, "verified-session")
        target = p.consent(raw, customer, "verified-session", approve=True)
        code = parse_qs(urlsplit(target).query)["code"][0]
        loaded = await p.load_authorization_code(client, code)
        return await p.exchange_authorization_code(client, loaded)
    return asyncio.run(go())


def test_postgres_mcp_lists_only_owned_trips_and_denies_foreign_trip(oauth_db):
    api, p = oauth_db
    owned, foreign, other = uuid4(), uuid4(), uuid4()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO customers(customer_id,tenant_id,external_id) VALUES(%s,%s,%s)", (other, api["tenant"], uuid4().hex))
        cur.execute("INSERT INTO trips(trip_id,tenant_id,customer_id,title) VALUES(%s,%s,%s,'서울 여행')", (owned, api["tenant"], api["customer"]))
        cur.execute("INSERT INTO trips(trip_id,tenant_id,customer_id,title) VALUES(%s,%s,%s,'다른 여행')", (foreign, api["tenant"], other))
    token = issue(p, api["customer"])
    async def scenario(session):
        trips = _data(await session.call_tool("tripilot_list_trips", {}))
        denied = await session.call_tool("tripilot_get_trip", {"trip_id": str(foreign)})
        return trips, denied
    trips, denied = _run(_surface(api, write=False), token.access_token, scenario)
    assert str(owned) in str(trips) and str(foreign) not in str(trips)
    assert "404" in _error_text(denied)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM trips WHERE trip_id IN (%s,%s)", (owned, foreign))
        cur.execute("DELETE FROM customers WHERE customer_id=%s", (other,))


def test_mcp_scope_enforced_even_when_write_tools_registered(oauth_db):
    api, p = oauth_db
    token = issue(p, api["customer"])
    owned = uuid4()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO trips(trip_id,tenant_id,customer_id,title) VALUES(%s,%s,%s,'서울 여행')", (owned, api["tenant"], api["customer"]))
    async def scenario(session):
        return await session.call_tool("tripilot_rollback", {"trip_id": str(owned), "to_version": 1})
    result = _run(_surface(api, write=True), token.access_token, scenario)
    assert "403" in _error_text(result) and "agent_scope" in _error_text(result)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM trips WHERE trip_id=%s", (owned,))


def test_mcp_write_switch_keeps_write_tools_unregistered(oauth_db):
    api, p = oauth_db
    token = issue(p, api["customer"], ["travel:read", "travel:write"])
    async def scenario(session):
        names = {tool.name for tool in (await session.list_tools()).tools}
        assert "tripilot_rollback" not in names and "tripilot_get_trip" in names
    _run(_surface(api, write=False), token.access_token, scenario)


def test_postgres_store_tenant_isolation_revocation_and_hashes(oauth_db):
    api, p = oauth_db
    token = issue(p, api["customer"])
    assert Provider("other-tenant", settings_module.get_settings().public_base_url).resolve(token.access_token) is None
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT record_key,body FROM personal_ai_oauth_records WHERE tenant_id=%s", (api["tenant"],))
        saved = repr(cur.fetchall())
        assert token.access_token not in saved and token.refresh_token not in saved
    with get_connection() as conn, conn.transaction():
        revoke_customer(conn, api["tenant"], api["customer"])
    assert p.resolve(token.access_token) is None


def test_postgres_concurrent_exchange_exactly_once(oauth_db):
    api, p = oauth_db
    async def scenario():
        client = await p.get_client("personal-ai")
        target = await p.authorize(client, AuthorizationParams(state="client-state", scopes=["travel:read"], code_challenge="x" * 43,
            redirect_uri=CALLBACK, redirect_uri_provided_explicitly=True, resource=p.resource))
        raw = parse_qs(urlsplit(target).query)["request"][0]
        p.consent(raw, api["customer"], "session")
        target = p.consent(raw, api["customer"], "session", approve=True)
        raw_code = parse_qs(urlsplit(target).query)["code"][0]
        loaded = await p.load_authorization_code(client, raw_code)
        results = await asyncio.gather(*(p.exchange_authorization_code(client, loaded) for _ in range(6)), return_exceptions=True)
        assert sum(not isinstance(result, Exception) for result in results) == 1
    asyncio.run(scenario())


def test_agent_key_can_initialize_mcp_after_gate_fix(oauth_db):
    api, p = oauth_db
    with get_connection() as conn, conn.transaction():
        key = web_agent_keys.create(conn, tenant_id=api["tenant"], customer_id=api["customer"], name="개인 AI", scope="read")
    async def scenario(session):
        assert (await session.list_tools()).tools
    _run(_surface(api, write=False), key["key"], scenario)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM web_agent_keys WHERE key_id=%s", (key["key_id"],))


def test_cookie_consent_sdk_exchange_mcp_read_and_revoke_end_to_end(oauth_db):
    from app.domains.travel_ops.modules.web_account.personal_ai_api import build_personal_ai_router
    api, p = oauth_db
    app = api["client"].app
    app.include_router(build_personal_ai_router(lambda: p))
    client = TestClient(app, base_url="https://api.example.test", follow_redirects=False)
    verifier = "end-to-end-verifier" * 4
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    with get_connection() as conn, conn.transaction():
        session_raw = web_cookie.create(conn, tenant_id=api["tenant"], customer_id=api["customer"])
    client.cookies.set(web_cookie.cookie_name(), session_raw)
    start = client.get("/oauth/authorize", params={"client_id": "personal-ai", "redirect_uri": CALLBACK,
        "response_type": "code", "resource": p.resource, "state": "end-to-end-state", "scope": "travel:read",
        "code_challenge": challenge, "code_challenge_method": "S256"})
    assert start.status_code == 302, start.text
    raw = parse_qs(urlsplit(start.headers["location"]).query)["request"][0]
    assert client.get("/oauth/consent", params={"request": raw}).status_code == 200
    approval = client.post("/oauth/consent", headers={"Origin": "https://api.example.test"},
        data={"request_token": raw, "decision": "allow", "csrf_token": web_cookie.csrf_token(digest(session_raw))})
    assert approval.status_code == 303, approval.text
    returned = parse_qs(urlsplit(approval.headers["location"]).query)
    assert returned["state"] == ["end-to-end-state"] and returned["iss"] == [p.issuer]
    client.cookies.clear()
    exchanged = client.post("/oauth/token", data={"client_id": "personal-ai", "grant_type": "authorization_code",
        "redirect_uri": CALLBACK, "code": returned["code"][0], "code_verifier": verifier, "resource": p.resource})
    assert exchanged.status_code == 200, exchanged.text
    token = exchanged.json()
    async def scenario(session):
        assert not (await session.call_tool("tripilot_list_trips", {})).isError
    _run(_surface(api, write=False), token["access_token"], scenario)
    assert client.post("/oauth/revoke", data={"client_id": "personal-ai", "token": token["refresh_token"]}).status_code == 200
    assert p.resolve(token["access_token"]) is None
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM web_sessions WHERE tenant_id=%s", (api["tenant"],))


def test_oauth_storage_rejects_customer_from_another_tenant(oauth_db):
    import psycopg
    api, p = oauth_db
    tenant, other = "oauth_foreign_" + uuid4().hex[:10], uuid4()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants(tenant_id,name) VALUES(%s,'분리 시험')", (tenant,))
        cur.execute("INSERT INTO customers(customer_id,tenant_id,external_id) VALUES(%s,%s,'other')", (other, tenant))
    try:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with p.store.transaction() as db:
                db.put("grant", "wrong-owner", {"customer": str(other)})
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM customers WHERE customer_id=%s", (other,))
            cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (tenant,))
