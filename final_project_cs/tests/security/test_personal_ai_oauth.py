"""비밀값·외부 호출 없이 실제 SDK HTTP와 권한 경계를 검증한다."""
import asyncio
import base64
import copy
import hashlib
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core import settings as settings_module
from app.domains.travel_ops.modules.web_account import web_cookie, web_guard
from app.domains.travel_ops.modules.web_account.personal_ai_api import build_personal_ai_router
from app.domains.travel_ops.modules.web_account.personal_ai_context import delegated_identity, current_identity
from app.domains.travel_ops.modules.web_account.personal_ai_oauth import Provider, digest

BASE = "https://api.example.test"
CALLBACK = "https://client.example.test/callback"
VERIFIER = "v" * 64
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")


class MemoryStore:
    """시험 대역. 실서비스의 저장 폴백으로 사용하지 않는다."""
    def __init__(self):
        self.rows, self.members, self.lock = {}, set(), threading.RLock()

    @contextmanager
    def transaction(self):
        with self.lock:
            snapshot = copy.deepcopy(self.rows)
            try:
                yield self
            except Exception:
                self.rows = snapshot
                raise

    def get(self, kind, key):
        return copy.deepcopy(self.rows.get((kind, key)))

    def put(self, kind, key, body):
        self.rows[kind, key] = copy.deepcopy(body)

    def is_member(self, customer):
        return str(customer) in self.members

    def list_grants(self, customer):
        return [(key, copy.deepcopy(body)) for (kind, key), body in self.rows.items()
                if kind == "grant" and body["customer"] == str(customer)]


@pytest.fixture
def env(monkeypatch):
    store = MemoryStore()
    customer, stranger = uuid4(), uuid4()
    store.members.update(map(str, (customer, stranger)))
    now = [datetime.now(timezone.utc).timestamp()]
    p = Provider("oauth-test", BASE, store=store, clock=lambda: now[0])
    p.preregister("travel-ai", "개인 AI <script>실행 금지</script>", [CALLBACK])
    p.preregister("other-ai", "다른 개인 AI", [CALLBACK])
    settings = settings_module.get_settings().model_copy(update={"tenant_id": p.tenant, "public_base_url": BASE,
        "web_origin": BASE, "web_allowed_origins": BASE})
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)
    @contextmanager
    def connection():
        yield SimpleNamespace(transaction=lambda: connection())
    monkeypatch.setattr(web_cookie, "get_connection", connection)
    def session(_conn, *, tenant_id, raw):
        if raw not in ("member", "stranger", "guest"):
            return None
        at = datetime.now(timezone.utc) + timedelta(days=1)
        return web_cookie.Session(stranger if raw == "stranger" else customer, digest(raw),
                                  "guest" if raw == "guest" else "member", at, at)
    monkeypatch.setattr(web_cookie, "lookup", session)
    monkeypatch.setattr(web_cookie, "_admin_access", lambda *a: None)
    monkeypatch.setattr(web_cookie, "_consent_gate", lambda *a: None)
    monkeypatch.setattr(web_guard, "count_auth", lambda *a, **k: None)
    app = FastAPI()
    app.include_router(build_personal_ai_router(lambda: p))
    client = TestClient(app, base_url=BASE, follow_redirects=False)
    return SimpleNamespace(p=p, store=store, customer=customer, stranger=stranger, now=now, app=app, client=client)


def begin(env, **changes):
    query = dict(client_id="travel-ai", redirect_uri=CALLBACK, response_type="code", resource=env.p.resource,
                 scope="travel:read", state="opaque-client-state", code_challenge=CHALLENGE, code_challenge_method="S256")
    query.update(changes)
    return env.client.get("/oauth/authorize", params=query)


def pending(env, **changes):
    response = begin(env, **changes)
    assert response.status_code == 302, response.text
    return parse_qs(urlsplit(response.headers["location"]).query)["request"][0]


def consent(env, raw, *, cookie="member", decision="allow", origin=BASE, csrf=None):
    session_hash = digest(cookie)
    return env.client.post("/oauth/consent", headers={"Cookie": f"{web_cookie.cookie_name()}={cookie}", "Origin": origin},
        data={"request_token": raw, "decision": decision, "csrf_token": csrf if csrf is not None else web_cookie.csrf_token(session_hash)})


def code(env, **changes):
    raw = pending(env, **changes)
    display = env.client.get("/oauth/consent", params={"request": raw}, headers={"Cookie": f"{web_cookie.cookie_name()}=member"})
    assert display.status_code == 200, display.text
    response = consent(env, raw)
    assert response.status_code == 303, response.text
    parsed = parse_qs(urlsplit(response.headers["location"]).query)
    assert parsed["state"] == ["opaque-client-state"] and parsed["iss"] == [env.p.issuer]
    return parsed["code"][0]


def exchange(env, raw, **changes):
    form = dict(client_id="travel-ai", grant_type="authorization_code", code=raw,
                redirect_uri=CALLBACK, code_verifier=VERIFIER, resource=env.p.resource)
    form.update(changes)
    return env.client.post("/oauth/token", data=form)


def tokens(env, **changes):
    response = exchange(env, code(env, **changes))
    assert response.status_code == 200, response.text
    return response.json()


def refresh(env, raw, **changes):
    return env.client.post("/oauth/token", data={"client_id": "travel-ai", "grant_type": "refresh_token",
        "refresh_token": raw, "resource": env.p.resource, **changes})


def test_metadata_is_discoverable_and_dcr_disabled(env):
    for path in ("/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/mcp", "/.well-known/oauth-protected-resource/mcp/"):
        body = env.client.get(path).json()
        assert body["resource"] == env.p.resource and body["authorization_servers"] == [env.p.issuer]
        assert body["scopes_supported"] == ["travel:read"]
    metadata = env.client.get("/.well-known/oauth-authorization-server/oauth").json()
    assert metadata["token_endpoint_auth_methods_supported"] == ["none"]
    assert "registration_endpoint" not in metadata
    assert env.client.post("/oauth/register", json={}).status_code == 404


@pytest.mark.parametrize("change", [dict(resource=""), dict(resource=BASE + "/another"), dict(state=""),
    dict(code_challenge="short"), dict(code_challenge_method="plain"), dict(scope="account:write"),
    dict(scope=""), dict(client_id="unknown"), dict(redirect_uri="https://evil.example/callback"),
    dict(redirect_uri="https://CLIENT.example.test/callback"), dict(redirect_uri="")])
def test_bad_authorization_is_never_issued_a_consent_request(env, change):
    response = begin(env, **change)
    assert response.status_code in (302, 400)
    if response.status_code == 302:
        assert "error=" in response.headers["location"] and "request=" not in response.headers["location"]
    assert not any(kind == "pending" for kind, _ in env.store.rows)


def test_login_and_guest_are_given_actual_login_screen(env):
    raw = pending(env)
    for headers in ({}, {"Cookie": f"{web_cookie.cookie_name()}=guest"}):
        response = env.client.get("/oauth/consent", params={"request": raw}, headers=headers)
        assert response.status_code == 200 and "/mypage#accounts" in response.text
        assert "로그인 후 다시 확인" in response.text


def test_consent_is_escaped_and_requires_display_then_same_session_csrf(env):
    raw = pending(env, scope="travel:read travel:write")
    assert consent(env, raw).status_code == 400
    response = env.client.get("/oauth/consent", params={"request": raw}, headers={"Cookie": f"{web_cookie.cookie_name()}=member"})
    assert "<script>" not in response.text and "&lt;script&gt;" in response.text
    assert "일정 변경" in response.text and "계정 연동" in response.text
    assert consent(env, raw, csrf="wrong").status_code == 403
    assert consent(env, raw, origin="https://evil.example").status_code == 403
    assert consent(env, raw, cookie="stranger").status_code == 400
    assert consent(env, raw).status_code == 303
    assert consent(env, raw).status_code == 400


def test_cancel_round_trips_state_without_issuing_code(env):
    raw = pending(env)
    env.client.get("/oauth/consent", params={"request": raw}, headers={"Cookie": f"{web_cookie.cookie_name()}=member"})
    response = consent(env, raw, decision="deny")
    parsed = parse_qs(urlsplit(response.headers["location"]).query)
    assert parsed == {"error": ["access_denied"], "state": ["opaque-client-state"], "iss": [env.p.issuer]}
    assert not any(kind in ("code", "grant") for kind, _ in env.store.rows)


@pytest.mark.parametrize("change", [dict(resource=""), dict(resource=BASE), dict(code_verifier="x" * 64),
    dict(code_verifier="short"), dict(redirect_uri=CALLBACK + "?extra=1"), dict(client_id="other-ai")])
def test_sdk_token_binding_rejects_then_correct_exchange_still_succeeds(env, change):
    raw = code(env)
    assert exchange(env, raw, **change).status_code == 400
    assert exchange(env, raw).status_code == 200


def test_code_is_single_use_and_storage_never_contains_raw_credentials(env):
    raw = code(env)
    response = exchange(env, raw)
    assert response.status_code == 200
    result = response.json()
    assert exchange(env, raw).status_code == 400
    persisted = repr(env.store.rows)
    assert all(value not in persisted for value in (raw, result["access_token"], result["refresh_token"]))
    assert env.p.resolve(result["access_token"]).subject == str(env.customer)
    assert response.headers["cache-control"] == "no-store"


def test_code_expiry(env):
    raw = code(env)
    env.now[0] += env.p.policy.code_seconds + 1
    assert exchange(env, raw).status_code == 400


def test_pending_expiry(env):
    raw = pending(env)
    env.now[0] += env.p.policy.consent_seconds + 1
    assert env.client.get("/oauth/consent", params={"request": raw}, headers={"Cookie": f"{web_cookie.cookie_name()}=member"}).status_code == 400


def test_native_consent_origin_works_when_customer_frontend_is_a_different_origin(env, monkeypatch):
    settings = settings_module.get_settings().model_copy(update={"web_origin": "https://web.example.test",
                                                               "web_allowed_origins": "https://web.example.test"})
    monkeypatch.setattr(settings_module, 'get_settings', lambda: settings)
    raw = pending(env)
    assert env.client.get('/oauth/consent', params={'request': raw},
                          headers={'Cookie': f'{web_cookie.cookie_name()}=member'}).status_code == 200
    assert consent(env, raw, origin='https://attacker.example.test').status_code == 403
    assert consent(env, raw, origin=BASE).status_code == 303


def test_login_link_uses_existing_allowed_origin_default(env, monkeypatch):
    settings = settings_module.get_settings().model_copy(update={"web_origin": "", "web_allowed_origins": "https://web.example.test"})
    monkeypatch.setattr(settings_module, 'get_settings', lambda: settings)
    response = env.client.get('/oauth/consent', params={'request': pending(env)})
    assert response.status_code == 200
    assert 'https://web.example.test/mypage#accounts' in response.text


def test_access_expiry_refresh_rotation_and_replay_revoke_family(env):
    first = tokens(env)
    env.now[0] += env.p.policy.access_seconds + 1
    assert env.p.resolve(first["access_token"]) is None
    rotated = refresh(env, first["refresh_token"])
    assert rotated.status_code == 200, rotated.text
    second = rotated.json()
    assert env.p.resolve(second["access_token"])
    assert refresh(env, first["refresh_token"]).status_code == 400
    assert env.p.resolve(second["access_token"]) is None
    assert refresh(env, second["refresh_token"]).status_code == 400


def test_refresh_cannot_expand_scope_or_resource_or_change_client(env):
    first = tokens(env)
    assert refresh(env, first["refresh_token"], scope="travel:write").status_code == 400
    assert refresh(env, first["refresh_token"], resource=BASE).status_code == 400
    assert refresh(env, first["refresh_token"], client_id="other-ai").status_code == 400
    assert refresh(env, first["refresh_token"]).status_code == 200


def test_expired_used_refresh_still_revokes_an_active_rotated_connection(env):
    first = tokens(env)
    env.now[0] += 20 * 86400
    second = refresh(env, first['refresh_token']).json()
    env.now[0] += 11 * 86400
    third = refresh(env, second['refresh_token']).json()
    assert env.p.resolve(third['access_token'])
    assert refresh(env, first['refresh_token']).status_code == 400
    assert env.p.resolve(third['access_token']) is None


@pytest.mark.parametrize("seconds", [30 * 86400 + 1, 90 * 86400 + 1])
def test_refresh_idle_or_absolute_expiry(env, seconds):
    first = tokens(env)
    env.now[0] += seconds
    assert refresh(env, first["refresh_token"]).status_code == 400


def test_disconnect_and_last_social_unlink_disable_tokens(env):
    first = tokens(env)
    env.store.members.remove(str(env.customer))
    assert env.p.resolve(first["access_token"]) is None
    assert refresh(env, first["refresh_token"]).status_code == 400


def test_revoke_only_own_client_and_browser_only_own_connection(env):
    first = tokens(env)
    assert env.client.post("/oauth/revoke", data={"client_id": "other-ai", "token": first["access_token"]}).status_code == 200
    assert env.p.resolve(first["access_token"])
    cookie = {"Cookie": f"{web_cookie.cookie_name()}=member"}
    listed = env.client.get("/v1/web/agent-connections", headers=cookie).json()["connections"]
    connection = listed[0]["connection_id"]
    assert env.client.delete("/v1/web/agent-connections/" + connection, headers={"Cookie": f"{web_cookie.cookie_name()}=stranger", "Origin": BASE,
         "X-CSRF-Token": web_cookie.csrf_token(digest("stranger"))}).status_code == 404
    assert env.client.delete("/v1/web/agent-connections/" + connection, headers={**cookie, "Origin": BASE,
        "X-CSRF-Token": web_cookie.csrf_token(digest("member"))}).status_code == 200
    assert env.p.resolve(first["access_token"]) is None


def test_sdk_revoke_refresh_disables_access(env):
    first = tokens(env)
    assert env.client.post("/oauth/revoke", data={"client_id": "travel-ai", "token": first["refresh_token"]}).status_code == 200
    assert env.p.resolve(first["access_token"]) is None


@pytest.mark.parametrize("method", ["GET", "DELETE"])
@pytest.mark.parametrize("credential,expected", [("missing", 401), ("guest", 403), ("key", 403)])
def test_connection_management_requires_member_cookie(env, monkeypatch, method, credential, expected):
    first = tokens(env)
    grant = env.p.connections(env.customer)[0]["connection_id"]
    monkeypatch.setattr(web_cookie, "resolve_key", lambda *a, **k: env.customer if k.get("raw") == "legacy-user-key" else None)
    headers = {"Origin": BASE, "X-CSRF-Token": web_cookie.csrf_token(digest("guest"))}
    if credential == "guest":
        headers["Cookie"] = f"{web_cookie.cookie_name()}=guest"
    elif credential == "key":
        headers["X-User-Key"] = "legacy-user-key"
    path = "/v1/web/agent-connections" + ("/" + grant if method == "DELETE" else "")
    assert env.client.request(method, path, headers=headers).status_code == expected
    assert env.p.resolve(first["access_token"]) is not None


@pytest.mark.parametrize("origin,csrf", [(BASE, ""), (BASE, "wrong"), ("https://other.example.test", "valid")])
def test_rest_disconnect_rejects_invalid_origin_or_csrf(env, origin, csrf):
    first = tokens(env)
    grant = env.p.connections(env.customer)[0]["connection_id"]
    headers = {"Cookie": f"{web_cookie.cookie_name()}=member", "Origin": origin}
    if csrf:
        headers["X-CSRF-Token"] = web_cookie.csrf_token(digest("member")) if csrf == "valid" else csrf
    assert env.client.delete("/v1/web/agent-connections/" + grant, headers=headers).status_code == 403
    assert env.p.resolve(first["access_token"]) is not None


def test_browser_disconnect_confirmation_names_own_client_and_requires_csrf(env):
    first = tokens(env)
    grant = env.p.connections(env.customer)[0]['connection_id']
    url = '/oauth/connections/' + grant + '/disconnect'
    member_cookie = {"Cookie": f"{web_cookie.cookie_name()}=member"}
    assert env.client.get(url, headers={"Cookie": f"{web_cookie.cookie_name()}=stranger"}).status_code == 404
    shown = env.client.get(url, headers=member_cookie)
    assert shown.status_code == 200 and '&lt;script&gt;' in shown.text
    assert env.p.resolve(first['access_token'])
    assert env.client.post('/oauth/disconnect', headers={**member_cookie, 'Origin': BASE},
                           data={'connection_id': grant, 'csrf_token': 'wrong'}).status_code == 403
    assert env.client.post('/oauth/disconnect', headers={**member_cookie, 'Origin': BASE},
                           data={'connection_id': grant, 'csrf_token': web_cookie.csrf_token(digest('member'))}).status_code == 303
    assert env.p.resolve(first['access_token']) is None


def test_duplicate_parameters_and_cookie_on_token_endpoint_rejected(env):
    assert env.client.get("/oauth/authorize?resource=x&resource=y").status_code == 400
    raw = code(env)
    assert env.client.post("/oauth/token", headers={"Cookie": "arbitrary=value"}, data=dict(resource=env.p.resource)).status_code == 400
    assert exchange(env, raw).status_code == 200


def test_direct_rest_tokens_shared_link_and_context_reset(env):
    first = tokens(env)
    for raw in (first["access_token"], "shared-plan-link-token"):
        scope = {"type": "http", "method": "GET", "path": "/v1/web/trips", "headers": [(b"authorization", ("Bearer " + raw).encode())]}
        if raw.startswith("acop_o_"):
            with pytest.raises(Exception) as exc:
                web_cookie._identify(Request(scope))
            assert exc.value.status_code == 401
        assert env.p.resolve(raw) is None if not raw.startswith("acop_o_") else env.p.resolve(raw) is not None
    identity = web_cookie.Identity(env.p.tenant, env.customer, "oauth", scope="read")
    with delegated_identity(identity):
        req = Request({"type": "http", "method": "GET", "path": "/v1/web/trips", "headers": []})
        assert web_cookie._identify(req) == identity
    assert current_identity() is None


@pytest.mark.parametrize("method,path,status", [("POST", "/v1/web/trips", 403), ("GET", "/v1/web/profile", 403),
    ("GET", "/v1/web/agent-connections", 403), ("POST", "/v1/web/moves/judge", 200), ("GET", "/v1/web/trips", 200)])
def test_internal_read_scope_uses_existing_account_and_write_guards(env, method, path, status):
    identity = web_cookie.Identity(env.p.tenant, env.customer, "oauth", scope="read")
    with delegated_identity(identity):
        req = Request({"type": "http", "method": method, "path": path, "headers": []})
        if status == 200:
            assert web_cookie._identify(req) == identity
        else:
            with pytest.raises(Exception) as exc:
                web_cookie._identify(req)
            assert exc.value.status_code == status


def test_concurrent_code_exchange_has_only_one_winner(env):
    raw = code(env)
    async def go():
        client = await env.p.get_client("travel-ai")
        loaded = await env.p.load_authorization_code(client, raw)
        results = await asyncio.gather(*(env.p.exchange_authorization_code(client, loaded) for _ in range(8)), return_exceptions=True)
        assert sum(not isinstance(r, Exception) for r in results) == 1
    asyncio.run(go())


@pytest.mark.parametrize("field,value", [("resource", BASE + "/different"), ("customer", str(uuid4())),
                                        ("client_id", "other-ai"), ("scopes", ["travel:write"])])
def test_access_record_must_match_its_grant_audience_owner_client_and_scope(env, field, value):
    first = tokens(env)
    row = env.store.get("access", digest(first["access_token"]))
    row[field] = value
    env.store.put("access", digest(first["access_token"]), row)
    assert env.p.resolve(first["access_token"]) is None


def test_mcp_transport_rejects_ambiguous_credentials_and_token_in_wrong_location(env):
    from app.domains.travel_ops.modules.mcp.mcp_server import McpGate
    first = tokens(env)
    identity = web_cookie.Identity(env.p.tenant, env.customer, "oauth", scope="read")
    inner = FastAPI()
    @inner.get("/")
    def read(request: Request):
        assert request.scope["tripilot.oauth_identity"] == identity
        return {"ok": True}
    gate = McpGate(inner, enabled=lambda: True, authenticate=lambda raw: identity if env.p.resolve(raw) else None)
    client = TestClient(gate)
    bearer = {"Authorization": "Bearer " + first["access_token"]}
    assert client.get("/", headers=bearer).status_code == 200
    assert client.get("/", params={"access_token": first["access_token"]}).status_code == 401
    assert client.get("/", headers={"X-User-Key": first["access_token"]}).status_code == 401
    assert client.get("/", headers={**bearer, "X-User-Key": "acop_u_other"}).status_code == 400
    assert client.get("/", headers={**bearer, "Cookie": f"{web_cookie.cookie_name()}=member"}).status_code == 400
    assert client.get("/", headers=[("Authorization", bearer["Authorization"]), ("Authorization", bearer["Authorization"])]).status_code == 400
    challenge = client.get("/").headers["www-authenticate"]
    assert "resource_metadata=" in challenge and 'scope="travel:read"' in challenge


def test_internal_backend_passes_identity_without_forwarding_oauth_token_and_clears_context(env):
    from app.domains.travel_ops.modules.mcp.mcp_server import AsgiBackend, Caller
    app = FastAPI()
    identity = web_cookie.Identity(env.p.tenant, env.customer, "oauth", scope="read")
    @app.get("/v1/web/trips")
    def read(request: Request):
        assert "authorization" not in request.headers and "x-user-key" not in request.headers
        assert web_cookie._identify(request) == identity
        return {"ok": True}
    async def go():
        result = await AsgiBackend(lambda: app).request("GET", "/v1/web/trips", caller=Caller("", identity=identity))
        assert result == {"ok": True} and current_identity() is None
    asyncio.run(go())
