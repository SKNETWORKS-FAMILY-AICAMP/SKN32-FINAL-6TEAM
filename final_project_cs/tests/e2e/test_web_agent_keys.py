# -*- coding: utf-8 -*-
"""에이전트 키 — 회원이 브라우저(쿠키)에서 만들고, 에이전트가 머리말로 쓰며, 만료 · 폐기 · 권한 범위가 있다. `[2026-10-04 사용자 결정 — D-CS-012]`

계약: `wiki/external/rest-endpoints.md` 「에이전트 키」 · 구현 `web_agent_keys.py` · `web_agent_keys_api.py` · `web_cookie.py`(키 확인) · 저장 045.

★지키려는 것
 ①만드는 것은 **쿠키 세션의 회원**만 — 게스트 403 `member_only`(`login_required`) · 에이전트 키/옛 키 403 · 쓰기는 CSRF. 원문(`acop_a_…`)은 만든 응답에만 나오고 목록에는 없다(DB 에도 해시만)
 ②키로 `Authorization: Bearer` 또는 `X-User-Key` — 본인 여행만 · `read` 는 GET 만(`agent_scope`) · 계정 관리 경로는 모두 `agent_forbidden` · 쿠키와 같이 오면 400
 ③만료 · 폐기 · 모름은 같은 401 · 개별 폐기(남의 키 404) · 활성 키 상한(409) · 만료 상한 90일(422)
 ④마지막 소셜 연결을 풀면 그 사용자의 에이전트 키가 모두 거둬진다 · 서버용 scope 키를 Bearer 로 보내도 웹 경로는 안 열린다

재현:

    python -m pytest tests/e2e/test_web_agent_keys.py -v
"""
from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.modules.web_account import web_agent_keys

from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_cookie_session import WEB, _guest, cookies  # noqa: F401
from .test_guest_and_trip_delete import _customer_of, _link, _make_trip


def _csrf(client) -> dict:
    return {"Origin": WEB, "X-CSRF-Token": client.get("/v1/web/auth/me").json()["csrf_token"]}


def _member(env) -> TestClient:
    """게스트 세션을 만들고 소셜 계정을 붙여 회원으로 — 쿠키가 든 클라이언트."""
    _guest(env)
    _link(env, _customer_of(env))
    return env["client"]


def _make_key(env, client=None, name="내 에이전트", scope="write", **extra):
    client = client or env["client"]
    return client.post("/v1/web/agent-keys", json={"name": name, "scope": scope, **extra}, headers=_csrf(client))


def _agent(env) -> TestClient:
    """쿠키 없는 클라이언트 — 에이전트가 키만 들고 온다."""
    return TestClient(env["client"].app, follow_redirects=False)


# ── ① 만들기 ─────────────────────────────────────────────────────
def test_a_member_makes_a_key_shown_once_and_stored_only_as_a_hash(cookies):
    _member(cookies)
    response = _make_key(cookies, scope="read", expires_days=30)
    assert response.status_code == 201
    body = response.json()
    assert body["key"].startswith("acop_a_") and body["scope"] == "read" and body["name"] == "내 에이전트"
    assert body["created_at"] < body["expires_at"] and "한 번만" in body["notice"]
    assert response.headers["cache-control"] == "no-store"
    listed = cookies["client"].get("/v1/web/agent-keys").json()["keys"]
    assert len(listed) == 1 and listed[0]["status"] == "active" and listed[0]["last_used_at"] is None
    assert "key" not in listed[0] and body["key"] not in str(listed)                       # 목록에 원문 없음
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM web_agent_keys WHERE tenant_id=%s AND key_hash=%s", (cookies["tenant"], body["key"]))
        assert cur.fetchone()[0] == 0                                                       # 원문은 DB 에 없다
        cur.execute("SELECT count(*) FROM web_agent_keys WHERE tenant_id=%s", (cookies["tenant"],))
        assert cur.fetchone()[0] == 1


def test_a_guest_cannot_make_a_key_and_is_asked_to_log_in(cookies):
    _guest(cookies)
    response = _make_key(cookies)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "member_only" and response.json()["error"]["login_required"] is True
    assert cookies["client"].get("/v1/web/agent-keys").status_code == 403


def test_making_a_key_needs_the_csrf_token_and_a_cookie_session(cookies):
    client = _member(cookies)
    assert client.post("/v1/web/agent-keys", json={"name": "x", "scope": "read"}, headers={"Origin": WEB}).status_code == 403   # CSRF 토큰 없음
    old_key = _agent(cookies)
    with get_connection() as conn, conn.transaction():
        from app.domains.travel_ops.modules.web_account.web_session import issue
        customer, raw = issue(conn, tenant_id=cookies["tenant"])
    assert old_key.post("/v1/web/agent-keys", json={"name": "x", "scope": "read"}, headers={"X-User-Key": raw}).status_code == 403   # 옛 키로는 못 만든다
    assert client.get("/v1/web/agent-keys").status_code == 200


def test_input_limits_and_active_key_cap(cookies):
    client = _member(cookies)
    assert _make_key(cookies, name="").status_code == 422
    assert _make_key(cookies, name="가" * 61).status_code == 422
    assert _make_key(cookies, scope="admin").status_code == 422
    assert _make_key(cookies, expires_days=91).status_code == 422                       # 만료 상한 90일
    assert _make_key(cookies, expires_days=0).status_code == 422
    for n in range(10):
        assert _make_key(cookies, name=f"k{n}").status_code == 201
    over = _make_key(cookies, name="열한째")
    assert over.status_code == 409 and over.json()["error"]["code"] == "agent_key_limit"
    first = client.get("/v1/web/agent-keys").json()["keys"][-1]["key_id"]
    assert client.delete(f"/v1/web/agent-keys/{first}", headers=_csrf(client)).status_code == 200
    assert _make_key(cookies, name="열한째").status_code == 201                         # 폐기하면 다시 만들 수 있다


# ── ② 키를 쓰는 법 ───────────────────────────────────────────────
def test_an_agent_key_opens_only_the_owners_trips_by_bearer_or_header(cookies):
    client = _member(cookies)
    assert _make_trip(cookies)[0] == 201
    key = _make_key(cookies, scope="write").json()["key"]
    agent = _agent(cookies)
    for headers in ({"Authorization": f"Bearer {key}"}, {"X-User-Key": key}):
        trips = agent.get("/v1/web/trips", headers=headers)
        assert trips.status_code == 200 and len(trips.json()["trips"]) == 1
    other = TestClient(cookies["client"].app, follow_redirects=False)
    other.post("/v1/web/auth/session", headers={"X-Forwarded-For": cookies["ip"]})
    assert other.get("/v1/web/trips").json()["trips"] == []                              # 남의 여행은 안 보인다(쿠키 사용자는 자기 것만)
    last = client.get("/v1/web/agent-keys").json()["keys"][0]
    assert last["last_used_at"] is not None                                              # 마지막 사용이 찍혔다


def test_a_read_key_cannot_write_and_a_write_key_can(cookies):
    _member(cookies)
    assert _make_trip(cookies)[0] == 201
    read = _make_key(cookies, scope="read", name="읽기").json()["key"]
    write = _make_key(cookies, scope="write", name="쓰기").json()["key"]
    agent = _agent(cookies)
    trip_id = cookies["client"].get("/v1/web/trips").json()["trips"][0]["trip_id"]
    assert agent.get(f"/v1/web/trips/{trip_id}", headers={"Authorization": f"Bearer {read}"}).status_code == 200
    denied = agent.post(f"/v1/web/trips/{trip_id}/delete", headers={"Authorization": f"Bearer {read}"})
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "agent_scope"
    assert agent.get(f"/v1/web/trips/{trip_id}", headers={"Authorization": f"Bearer {write}"}).status_code == 200
    assert agent.post(f"/v1/web/trips/{trip_id}/delete", headers={"Authorization": f"Bearer {write}"}).status_code == 200   # 쓰기 권한 — 여행 작업은 된다


def test_no_agent_key_opens_account_management(cookies):
    _member(cookies)
    key = _make_key(cookies, scope="write").json()["key"]
    agent, headers = _agent(cookies), {"Authorization": f"Bearer {key}"}
    for method, path in (("get", "/v1/web/auth/links"), ("post", "/v1/web/auth/logout"), ("post", "/v1/web/session/rotate"),
                         ("get", "/v1/web/profile"), ("put", "/v1/web/profile"), ("get", "/v1/web/agent-keys"),
                         ("post", "/v1/web/agent-keys"), ("get", "/v1/web/auth/me")):
        response = getattr(agent, method)(path, headers=headers)
        assert response.status_code == 403 and response.json()["error"]["code"] == "agent_forbidden", (method, path, response.status_code)


def test_a_key_and_a_cookie_together_are_refused_and_a_server_scope_key_does_not_open_web_paths(cookies, api):
    _member(cookies)
    key = _make_key(cookies).json()["key"]
    both = cookies["client"].get("/v1/web/trips", headers={"Authorization": f"Bearer {key}"})
    assert both.status_code == 400 and both.json()["error"]["code"] == "ambiguous_credentials"
    scope_key = api["auth"]("trip:write")["Authorization"]
    assert _agent(cookies).get("/v1/web/trips", headers={"Authorization": scope_key}).status_code == 401


# ── ③ 만료 · 폐기 ────────────────────────────────────────────────
def test_expired_revoked_and_unknown_keys_are_the_same_401(cookies):
    client = _member(cookies)
    key = _make_key(cookies, name="곧 만료").json()
    agent = _agent(cookies)
    headers = {"Authorization": f"Bearer {key['key']}"}
    assert agent.get("/v1/web/trips", headers=headers).status_code == 200
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:                # 만료시킨다
        cur.execute("UPDATE web_agent_keys SET expires_at = now() - interval '1 minute' WHERE key_id=%s", (key["key_id"],))
    expired = agent.get("/v1/web/trips", headers=headers)
    assert expired.status_code == 401 and expired.json()["error"]["code"] == "unauthenticated"
    assert client.get("/v1/web/agent-keys").json()["keys"][0]["status"] == "expired"
    unknown = agent.get("/v1/web/trips", headers={"Authorization": "Bearer acop_a_" + "x" * 43})
    assert unknown.status_code == 401 and unknown.json() == expired.json()                   # 어느 쪽인지 알려 주지 않는다
    revoked_key = _make_key(cookies, name="폐기").json()
    assert client.delete(f"/v1/web/agent-keys/{revoked_key['key_id']}", headers=_csrf(client)).status_code == 200
    gone = agent.get("/v1/web/trips", headers={"Authorization": f"Bearer {revoked_key['key']}"})
    assert gone.status_code == 401 and gone.json() == expired.json()
    assert client.get("/v1/web/agent-keys").json()["keys"][0]["status"] == "revoked"


def test_revoking_someone_elses_or_a_missing_key_is_the_same_404(cookies):
    client = _member(cookies)
    mine = _make_key(cookies).json()["key_id"]
    stranger = TestClient(cookies["client"].app, follow_redirects=False)
    stranger.post("/v1/web/auth/session", headers={"X-Forwarded-For": cookies["ip"]})
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT customer_id FROM web_sessions WHERE tenant_id=%s AND revoked_at IS NULL ORDER BY created_at DESC LIMIT 1", (cookies["tenant"],))
        _link(cookies, cur.fetchone()[0])
    foreign = stranger.delete(f"/v1/web/agent-keys/{mine}", headers=_csrf(stranger))
    missing = client.delete(f"/v1/web/agent-keys/{uuid4()}", headers=_csrf(client))
    assert foreign.status_code == missing.status_code == 404 and foreign.json() == missing.json()
    assert client.get("/v1/web/agent-keys").json()["keys"][0]["status"] == "active"           # 남의 폐기 요청은 안 먹었다


def test_unlinking_the_last_social_account_revokes_every_agent_key(cookies):
    client = _member(cookies)
    _make_key(cookies, name="a")
    _make_key(cookies, name="b")
    assert [k["status"] for k in client.get("/v1/web/agent-keys").json()["keys"]] == ["active", "active"]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT provider FROM web_social_links WHERE tenant_id=%s", (cookies["tenant"],))
        provider = cur.fetchone()[0]
    assert client.delete(f"/v1/web/auth/{provider}", headers=_csrf(client)).status_code == 200
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FILTER (WHERE revoked_at IS NULL) FROM web_agent_keys WHERE tenant_id=%s", (cookies["tenant"],))
        assert cur.fetchone()[0] == 0                                                           # 게스트가 됐으니 키가 모두 거둬졌다
    assert client.get("/v1/web/agent-keys").status_code == 403                                  # 이제 회원이 아니라 목록도 못 본다


def test_the_resolver_only_knows_agent_keys_and_stays_none_for_other_prefixes(cookies):
    _member(cookies)
    made = _make_key(cookies).json()
    with get_connection() as conn:
        assert web_agent_keys.resolve(conn, tenant_id=cookies["tenant"], raw=made["key"]) is not None
        assert web_agent_keys.resolve(conn, tenant_id=cookies["tenant"], raw="acop_u_" + made["key"][7:]) is None
        assert web_agent_keys.resolve(conn, tenant_id=cookies["tenant"], raw=None) is None
        assert web_agent_keys.resolve(conn, tenant_id="other-tenant", raw=made["key"]) is None  # 다른 테넌트의 키로는 안 열린다
