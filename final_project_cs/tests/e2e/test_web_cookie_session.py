# -*- coding: utf-8 -*-
"""웹 브라우저 세션(HttpOnly 쿠키) — 발급 · 수명 · CSRF · 로그아웃 · 옛 키 옮기기 · 소셜 로그인 교환 · 쿠키와 키 동시. `[2026-10-04 사용자 결정 — D-CS-011]`

계약: `wiki/external/rest-endpoints.md` 「브라우저 세션 쿠키」 · 구현 `app/modules/travel_ops/web_cookie.py` · `web_auth_api.py` · 저장 044 `web_sessions`.

★지키려는 것
 ①게스트 세션은 쿠키로만 간다 — 응답 몸통에 키가 없다. 쿠키는 HttpOnly · SameSite=Lax · Path=/ · **Domain 없음**, 운영(https)은 `__Host-` + Secure, 개발(http)은 접두 없이
 ②쿠키만으로 `/v1/web/*` 가 열린다 · 쿠키와 `X-User-Key` 가 같이 오면 400 · 모르는 쿠키는 401 + 쿠키 지우기
 ③쿠키로 인증된 **쓰기**는 Origin + `X-CSRF-Token` 을 둘 다 통과해야 한다(읽기는 면제). 키 호출은 면제
 ④수명은 쓸 때 계산한다 — 게스트 유휴 · 회원 유휴 · 절대. 줄이면 곧 적용, 만료된 행은 거둔다. 마지막 사용은 한 번 쓰면 한동안 안 쓴다
 ⑤로그아웃은 서버 행을 거둔다 · 옛 키 옮기기(`adopt`)는 키를 거두지 않는다 · 소셜 교환(`session: cookie`)은 키 대신 쿠키를 주고 게스트 쿠키를 거둔다
 ⑥소셜 계정이 붙으면 같은 세션이 회원 수명을 받는다
 ⑦관리 콘솔 설정(`web.guest_idle_hours` …)이 목록에 있고 범위가 있다

재현:

    python -m pytest tests/e2e/test_web_cookie_session.py -v
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.modules.travel_ops import web_cookie, web_guard
from app.modules.travel_ops.trip_api import build_trip_router
from app.modules.travel_ops.web_auth_api import build_auth_router
from app.modules.travel_ops.web_session import issue
from app.presentation.api.app import create_app

from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다

WEB = "https://web.example.test"
NONCE = "n" * 40


class FakeGoogle:
    def __call__(self, provider, *, code, verifier, redirect_uri, nonce):
        return code.removeprefix("sub-")


@pytest.fixture()
def cookies(api, monkeypatch):  # noqa: F811
    """구글이 설정된 서버(웹 출처 · 공개 주소는 http — 개발 모양). 시험이 만든 세션 · 소셜 줄은 끝나고 지운다."""
    settings = settings_module.get_settings()
    monkeypatch.setattr(settings, "google_client_id", "client-id-for-test")
    monkeypatch.setattr(settings, "google_client_secret", "secret-for-test")
    monkeypatch.setattr(settings, "web_origin", WEB)
    monkeypatch.setattr(settings, "web_allowed_origins", WEB)
    monkeypatch.setattr(settings, "public_base_url", "http://api.example.test")
    web_guard.clear_cache()
    client = TestClient(create_app(classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
                                   domain_routers=[build_trip_router(), build_auth_router(exchange=FakeGoogle())]),
                        follow_redirects=False)
    yield {**api, "client": client, "ip": "10.8." + str(uuid4().int % 250) + "." + str(uuid4().int % 250)}
    web_guard.clear_cache()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for table in ("web_oauth_tickets", "web_oauth_states", "web_social_links", "web_sessions"):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id=%s", (api["tenant"],))
        cur.execute("DELETE FROM runtime_limits WHERE tenant_id=%s AND name LIKE 'web.%%_hours'", (api["tenant"],))


def _guest(env) -> tuple[dict, str]:
    """게스트 세션을 만든다 — (몸통, 쿠키 값). 쿠키는 클라이언트의 쿠키 통에도 들어간다."""
    response = env["client"].post("/v1/web/auth/session", headers={"X-Forwarded-For": env["ip"]})
    assert response.status_code == 201, response.text
    return response.json(), env["client"].cookies.get(web_cookie.cookie_name())


def _write(env, path, csrf, **kwargs):
    return env["client"].post(path, headers={"Origin": WEB, "X-CSRF-Token": csrf}, **kwargs)


def _age(env, hours_ago: int, column: str = "last_used_at") -> None:
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute(f"UPDATE web_sessions SET {column} = now() - make_interval(hours => %s) WHERE tenant_id=%s",
                    (hours_ago, env["tenant"]))


# ── ① 발급 ───────────────────────────────────────────────────────
def test_guest_session_sets_http_only_cookie_and_no_key(cookies):
    response = cookies["client"].post("/v1/web/auth/session")
    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "guest" and body["csrf_token"] and "user_key" not in body
    assert body["guest_idle_hours"] == 168
    header = response.headers["set-cookie"]
    assert header.startswith("tripilot_sid_dev=")            # 개발(http) — 접두 없이
    assert "HttpOnly" in header and "SameSite=Lax" in header and "Path=/" in header
    assert "Domain" not in header and "Secure" not in header
    assert response.headers["cache-control"] == "no-store"


def test_https_public_address_uses_host_prefix_and_secure(cookies, monkeypatch):
    monkeypatch.setattr(settings_module.get_settings(), "public_base_url", "https://api.example.test")
    response = cookies["client"].post("/v1/web/auth/session")
    header = response.headers["set-cookie"]
    assert header.startswith("__Host-tripilot_sid=")
    assert "Secure" in header and "HttpOnly" in header and "Path=/" in header and "Domain" not in header


def test_cookie_value_is_stored_only_as_a_hash(cookies):
    _, raw = _guest(cookies)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM web_sessions WHERE session_hash=%s", (raw,))
        assert cur.fetchone()[0] == 0                         # 원문은 어디에도 없다
        cur.execute("SELECT count(*) FROM web_sessions WHERE tenant_id=%s", (cookies["tenant"],))
        assert cur.fetchone()[0] == 1


def test_a_second_session_call_with_a_valid_cookie_returns_the_same_session(cookies):
    first, raw = _guest(cookies)
    again = cookies["client"].post("/v1/web/auth/session")
    assert again.status_code == 200 and again.json()["csrf_token"] == first["csrf_token"]
    assert "set-cookie" not in again.headers
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM web_sessions WHERE tenant_id=%s", (cookies["tenant"],))
        assert cur.fetchone()[0] == 1


# ── ② 쿠키로 열린다 · 쿠키와 키 동시 · 모르는 쿠키 ───────────────────
def test_cookie_opens_web_routes_and_unknown_cookie_is_401_and_cleared(cookies):
    _guest(cookies)
    assert cookies["client"].get("/v1/web/trips").json() == {"trips": []}
    stranger = TestClient(cookies["client"].app, follow_redirects=False)
    stranger.cookies.set(web_cookie.cookie_name(), "x" * 43)
    response = stranger.get("/v1/web/trips")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_cookie_and_key_together_are_refused_not_silently_picked(cookies):
    _guest(cookies)
    with get_connection() as conn, conn.transaction():
        _, key = issue(conn, tenant_id=cookies["tenant"])
    response = cookies["client"].get("/v1/web/trips", headers={"X-User-Key": key})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ambiguous_credentials"


def test_key_only_calls_still_work_without_csrf(cookies):
    with get_connection() as conn, conn.transaction():
        _, key = issue(conn, tenant_id=cookies["tenant"])
    plain = TestClient(cookies["client"].app, follow_redirects=False)
    assert plain.get("/v1/web/trips", headers={"X-User-Key": key}).status_code == 200
    assert plain.post("/v1/web/warmup", headers={"X-User-Key": key}).status_code in (200, 202, 503)   # 쓰기도 CSRF 없이 — 키는 자동으로 안 붙는다


def test_no_credentials_is_401(cookies):
    assert TestClient(cookies["client"].app).get("/v1/web/trips").status_code == 401


# ── ③ CSRF ───────────────────────────────────────────────────────
def test_cookie_writes_need_origin_and_csrf_token(cookies):
    body, _ = _guest(cookies)
    path = "/v1/web/session/rotate"
    cases = {
        "토큰 없음": {"Origin": WEB},
        "틀린 토큰": {"Origin": WEB, "X-CSRF-Token": "0" * 64},
        "남의 출처": {"Origin": "https://evil.example", "X-CSRF-Token": body["csrf_token"]},
        "출처 없음 · 토큰만": {"X-CSRF-Token": body["csrf_token"]},
    }
    for label, headers in cases.items():
        response = cookies["client"].post(path, headers=headers)
        assert response.status_code == 403, label
        assert response.json()["error"]["code"] == "csrf_failed", label
    assert _write(cookies, path, body["csrf_token"]).status_code == 200


def test_fetch_metadata_stands_in_when_origin_is_absent(cookies):
    body, _ = _guest(cookies)
    ok = cookies["client"].post("/v1/web/session/rotate", headers={"Sec-Fetch-Site": "same-origin", "X-CSRF-Token": body["csrf_token"]})
    assert ok.status_code == 200
    cross = cookies["client"].post("/v1/web/session/rotate", headers={"Sec-Fetch-Site": "cross-site", "X-CSRF-Token": body["csrf_token"]})
    assert cross.status_code == 403


def test_reads_are_exempt_from_csrf(cookies):
    _guest(cookies)
    assert cookies["client"].get("/v1/web/trips").status_code == 200            # 머리말 없이


def test_csrf_token_is_bound_to_its_session(cookies):
    first, _ = _guest(cookies)
    other = TestClient(cookies["client"].app, follow_redirects=False)
    second = other.post("/v1/web/auth/session", headers={"X-Forwarded-For": cookies["ip"]}).json()
    assert first["csrf_token"] != second["csrf_token"]
    response = other.post("/v1/web/session/rotate", headers={"Origin": WEB, "X-CSRF-Token": first["csrf_token"]})
    assert response.status_code == 403                                            # 남의 세션 토큰은 안 통한다


# ── ④ 수명 ───────────────────────────────────────────────────────
def test_guest_idle_expiry_revokes_the_row_and_asks_the_browser_to_drop_the_cookie(cookies):
    _guest(cookies)
    _age(cookies, hours_ago=167)
    assert cookies["client"].get("/v1/web/trips").status_code == 200              # 아직 안 지났다
    _age(cookies, hours_ago=169)
    response = cookies["client"].get("/v1/web/trips")
    assert response.status_code == 401 and "Max-Age=0" in response.headers["set-cookie"]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM web_sessions WHERE tenant_id=%s AND revoked_at IS NOT NULL", (cookies["tenant"],))
        assert cur.fetchone()[0] == 1


def test_absolute_lifetime_ends_a_session_that_is_still_in_use(cookies):
    _guest(cookies)
    _age(cookies, hours_ago=721, column="created_at")
    assert cookies["client"].get("/v1/web/trips").status_code == 401


def test_last_use_is_written_at_most_once_per_touch_window(cookies):
    _guest(cookies)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT last_used_at FROM web_sessions WHERE tenant_id=%s", (cookies["tenant"],))
        first = cur.fetchone()[0]
    cookies["client"].get("/v1/web/trips")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT last_used_at FROM web_sessions WHERE tenant_id=%s", (cookies["tenant"],))
        assert cur.fetchone()[0] == first                                           # 60초 안이라 다시 안 썼다
    _age(cookies, hours_ago=1)
    cookies["client"].get("/v1/web/trips")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT last_used_at > now() - interval '1 minute' FROM web_sessions WHERE tenant_id=%s", (cookies["tenant"],))
        assert cur.fetchone()[0] is True                                            # 한 시간 뒤라 갱신했다


def test_an_operator_change_applies_on_the_next_request(cookies):
    """관리 콘솔이 게스트 보존을 줄이면 이미 만든 세션에도 곧 적용된다(만료 시각을 저장하지 않으므로)."""
    _guest(cookies)
    _age(cookies, hours_ago=30)
    assert cookies["client"].get("/v1/web/trips").status_code == 200                # 기본 168시간 — 아직 산다
    _age(cookies, hours_ago=30)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO runtime_limits (tenant_id, name, value, updated_by) VALUES (%s,'web.guest_idle_hours',to_jsonb(24),'test') "
                    "ON CONFLICT (tenant_id, name) DO UPDATE SET value=to_jsonb(24)", (cookies["tenant"],))
    web_guard.clear_cache()
    assert cookies["client"].get("/v1/web/trips").status_code == 401                # 24시간으로 줄이니 30시간 안 쓴 세션이 끝났다


# ── ⑤ 로그아웃 · 옮기기 · 소셜 교환 ───────────────────────────────
def test_logout_revokes_the_row_and_clears_the_cookie(cookies):
    body, _ = _guest(cookies)
    response = _write(cookies, "/v1/web/auth/logout", body["csrf_token"])
    assert response.status_code == 200 and response.json() == {"status": "signed_out"}
    assert "Max-Age=0" in response.headers["set-cookie"]
    cookies["client"].cookies.clear()
    stale = TestClient(cookies["client"].app)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM web_sessions WHERE tenant_id=%s AND revoked_at IS NULL", (cookies["tenant"],))
        assert cur.fetchone()[0] == 0
    assert stale.get("/v1/web/trips").status_code == 401


def test_logout_without_csrf_is_refused_and_leaves_the_session(cookies):
    _guest(cookies)
    assert cookies["client"].post("/v1/web/auth/logout", headers={"Origin": WEB}).status_code == 403
    assert cookies["client"].get("/v1/web/trips").status_code == 200


def test_adopt_turns_an_old_key_into_a_cookie_session_and_keeps_the_key(cookies):
    with get_connection() as conn, conn.transaction():
        customer, key = issue(conn, tenant_id=cookies["tenant"])
    browser = TestClient(cookies["client"].app, follow_redirects=False)
    response = browser.post("/v1/web/auth/adopt", headers={"X-User-Key": key, "X-Forwarded-For": cookies["ip"]})
    assert response.status_code == 201 and response.json()["kind"] == "guest"
    assert browser.get("/v1/web/trips").status_code == 200                           # 쿠키만으로 같은 사용자
    assert TestClient(cookies["client"].app).get("/v1/web/trips", headers={"X-User-Key": key}).status_code == 200   # 키도 그대로
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT customer_id FROM web_sessions WHERE tenant_id=%s", (cookies["tenant"],))
        assert cur.fetchone()[0] == customer


def test_adopt_with_a_wrong_key_is_401_and_with_both_credentials_is_400(cookies):
    plain = TestClient(cookies["client"].app, follow_redirects=False)
    assert plain.post("/v1/web/auth/adopt", headers={"X-User-Key": "acop_u_nope", "X-Forwarded-For": cookies["ip"]}).status_code == 401
    _guest(cookies)
    with get_connection() as conn, conn.transaction():
        _, key = issue(conn, tenant_id=cookies["tenant"])
    assert cookies["client"].post("/v1/web/auth/adopt", headers={"X-User-Key": key, "X-Forwarded-For": cookies["ip"]}).status_code == 400


def test_me_reports_the_session_and_401_without_one(cookies):
    assert TestClient(cookies["client"].app).get("/v1/web/auth/me").status_code == 401
    body, _ = _guest(cookies)
    me = cookies["client"].get("/v1/web/auth/me").json()
    assert me["kind"] == "guest" and me["csrf_token"] == body["csrf_token"] and me["guest_idle_hours"] == 168
    assert me["idle_expires_at"] < me["absolute_expires_at"]


def _login_with_cookie(env, browser, who="alice"):
    start = browser.post("/v1/web/auth/google/start", json={"mode": "login", "client_nonce": NONCE},
                         headers={"X-Forwarded-For": env["ip"]})
    assert start.status_code == 200, start.text
    from urllib.parse import parse_qs, urlparse
    state = parse_qs(urlparse(start.json()["authorize_url"]).query)["state"][0]
    called = browser.get("/v1/web/auth/google/callback", params={"state": state, "code": f"sub-{who}-{env['ip']}"})
    ticket = parse_qs(urlparse(called.headers["location"]).query)["ticket"][0]
    return browser.post("/v1/web/auth/exchange", json={"ticket": ticket, "client_nonce": NONCE, "session": "cookie"},
                        headers={"X-Forwarded-For": env["ip"]})


def test_social_exchange_in_cookie_mode_gives_a_cookie_and_no_key(cookies):
    browser = TestClient(cookies["client"].app, follow_redirects=False)
    response = _login_with_cookie(cookies, browser)
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "created" and body["kind"] == "member" and body["csrf_token"] and "user_key" not in body
    assert "guest_idle_hours" not in body
    assert "HttpOnly" in response.headers["set-cookie"]
    assert browser.get("/v1/web/trips").status_code == 200


def test_social_exchange_revokes_the_guest_cookie_it_arrived_with(cookies):
    browser = TestClient(cookies["client"].app, follow_redirects=False)
    browser.post("/v1/web/auth/session", headers={"X-Forwarded-For": cookies["ip"]})
    guest_cookie = browser.cookies.get(web_cookie.cookie_name())
    assert guest_cookie
    _login_with_cookie(cookies, browser)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FILTER (WHERE revoked_at IS NULL), count(*) FILTER (WHERE revoked_at IS NOT NULL) "
                    "FROM web_sessions WHERE tenant_id=%s", (cookies["tenant"],))
        live, revoked = cur.fetchone()
    assert (live, revoked) == (1, 1)                                                  # 게스트 세션은 거뒀고 새 회원 세션 하나만 산다
    assert browser.cookies.get(web_cookie.cookie_name()) != guest_cookie


def test_default_exchange_mode_still_returns_a_key(cookies):
    browser = TestClient(cookies["client"].app, follow_redirects=False)
    start = browser.post("/v1/web/auth/google/start", json={"mode": "login", "client_nonce": NONCE},
                         headers={"X-Forwarded-For": cookies["ip"]})
    from urllib.parse import parse_qs, urlparse
    state = parse_qs(urlparse(start.json()["authorize_url"]).query)["state"][0]
    called = browser.get("/v1/web/auth/google/callback", params={"state": state, "code": "sub-bob-" + cookies["ip"]})
    ticket = parse_qs(urlparse(called.headers["location"]).query)["ticket"][0]
    exchanged = browser.post("/v1/web/auth/exchange", json={"ticket": ticket, "client_nonce": NONCE}, headers={"X-Forwarded-For": cookies["ip"]})
    assert exchanged.json()["user_key"].startswith("acop_u_") and "set-cookie" not in exchanged.headers


# ── ⑥ 회원 수명 ──────────────────────────────────────────────────
def test_linking_a_social_account_gives_the_same_session_the_member_lifetime(cookies):
    """같은 100시간 안 쓴 세션이라도 — 게스트 설정(24시간)이면 끝나고, 소셜 계정이 붙은 사용자는 회원 설정(200시간)이라 산다."""
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO runtime_limits (tenant_id, name, value, updated_by) VALUES (%s,'web.guest_idle_hours',to_jsonb(24),'test'),"
                    "(%s,'web.member_idle_hours',to_jsonb(200),'test') ON CONFLICT (tenant_id, name) DO UPDATE SET value=EXCLUDED.value",
                    (cookies["tenant"], cookies["tenant"]))
    web_guard.clear_cache()
    _guest(cookies)
    _age(cookies, hours_ago=100)
    assert cookies["client"].get("/v1/web/auth/me").status_code == 401                # 게스트 24시간 — 100시간 안 쓰면 끝

    cookies["client"].cookies.clear()
    _guest(cookies)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT customer_id FROM web_sessions WHERE tenant_id=%s AND revoked_at IS NULL", (cookies["tenant"],))
        customer = cur.fetchone()[0]
        cur.execute("INSERT INTO web_social_links (tenant_id, provider, subject_hash, customer_id) VALUES (%s,'google',%s,%s)",
                    (cookies["tenant"], "h-" + str(uuid4()), customer))
    _age(cookies, hours_ago=100)
    me = cookies["client"].get("/v1/web/auth/me")
    assert me.status_code == 200 and me.json()["kind"] == "member" and "guest_idle_hours" not in me.json()


# ── ⑦ 관리 콘솔 설정 ─────────────────────────────────────────────
def test_operator_settings_are_listed_with_hour_bounds():
    table = web_guard.specs()
    for name in ("web.guest_idle_hours", "web.member_idle_hours", "web.session_max_hours"):
        spec = table[name]
        assert spec.unit == "시간" and spec.type == "int" and spec.min == 1 and spec.max == 8760
    assert table["web.guest_idle_hours"].default == 168
    assert table["web.session_max_hours"].default == 720
    assert table["web.guest_cleanup_enabled"].type == "bool"
    assert table["web.guest_idle_hours"].check(0) == "out_of_range" and table["web.guest_idle_hours"].check(24) is None
