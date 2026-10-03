# -*- coding: utf-8 -*-
"""웹 소셜 로그인(구글 먼저) — 시작 → 콜백 → 표 교환 한 바퀴 · 연결 · 해제 · 보안. `[2026-10-03 ui 세션 요청서 「소셜 로그인」 — 1단계는 구글 하나]`

계약: `wiki/records/plans/2026-10-03_1930_소셜_로그인_백엔드_요청.md` · 구현 `app/modules/travel_ops/web_auth_api.py` · `web_auth.py` · `infrastructure/oauth_providers.py`.

★업체(구글)는 **시험용 가짜**다 — 코드를 사용자 고유 번호로 바꾸는 자리(`exchange`)에 꽂는다(코드 `sub-<이름>` → 고유 번호 `<이름>`, `bad-` 로 시작하면 업체 오류). 실제 구글과의 연결은
사용자가 구글 콘솔에서 만든 클라이언트 ID · 비밀값이 있어야 해서 따로 확인한다(`wiki/records/reports/`). ID 토큰 확인 자체는 `tests/unit/travel/test_oauth_providers.py` 가 본다.

★지키려는 것
 ①업체 설정이 둘 다 있어야 `providers` 에 나온다 · 없으면 **빈 목록**(404 가 아니다)
 ②`login` 신규 → `created` + 이 기기용 새 키 · `login` 기존 → `signed_in` + **새 키 하나 더**(다른 기기의 키는 그대로) · `link` → `linked` + 키 없음
 ③같은 표 두 번 · 다른 `client_nonce` · 60초 지난 표 → 410 · **틀린 nonce 로 표를 태울 수 없다**(로그인 CSRF 막기)
 ④`state` 는 한 번만 · 10분 · 업체가 다르면 안 된다 — 모두 `?error=failed`. 취소는 `cancelled`, 그 밖의 업체 오류는 `denied`
 ⑤다른 사용자에게 붙은 계정으로 `link` → `already_linked_elsewhere`(합치지 않는다)
 ⑥저장은 `sub` 의 해시뿐 — 이메일 · 이름 · 사진 칸이 없다. 돌려보낼 웹 주소는 서버 설정이다(요청 값이 아니다)
 ⑦시작 · 교환은 주소당 한 시간 한도가 있고, 키 없는 로그인은 사람 확인을 거친다

재현:

    python -m pytest tests/e2e/test_web_social_login.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.core.settings as settings_module
from app.infrastructure import oauth_providers as oauth
from app.infrastructure.db.session import get_connection
from app.modules.travel_ops import web_guard
from app.modules.travel_ops.trip_api import build_trip_router
from app.modules.travel_ops.web_auth_api import build_auth_router
from app.modules.travel_ops.web_session import add_key, issue, resolve
from app.presentation.api.app import create_app

from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다

WEB = "https://web.example.test"
NONCE = "n" * 40


class FakeGoogle:
    """코드를 고유 번호로 바꾸는 시험용 업체 — 받은 값(PKCE 검증값 · nonce · 콜백 주소)을 기억해 시험이 대조한다."""

    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, provider, *, code, verifier, redirect_uri, nonce):
        self.calls.append({"code": code, "verifier": verifier, "redirect_uri": redirect_uri, "nonce": nonce})
        if code.startswith("bad-"):
            raise oauth.OAuthError("provider refused")
        return code.removeprefix("sub-")


@pytest.fixture()
def social(api, monkeypatch):  # noqa: F811
    """구글이 설정된 서버 + 시험용 가짜 업체. 시험이 만든 소셜 표 줄은 끝나고 지운다(사용자 행을 가리키므로 `api` 의 정리보다 먼저)."""
    settings = settings_module.get_settings()
    monkeypatch.setattr(settings, "google_client_id", "client-id-for-test")
    monkeypatch.setattr(settings, "google_client_secret", "secret-for-test")
    monkeypatch.setattr(settings, "web_origin", WEB)
    monkeypatch.setattr(settings, "public_base_url", "https://api.example.test")
    google = FakeGoogle()
    client = TestClient(create_app(classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
                                   domain_routers=[build_trip_router(), build_auth_router(exchange=google)]),
                        follow_redirects=False)
    yield {**api, "client": client, "google": google, "ip": "10.9." + str(uuid4().int % 250) + "." + str(uuid4().int % 250)}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for table in ("web_oauth_tickets", "web_oauth_states", "web_social_links"):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id=%s", (api["tenant"],))


def _session(client) -> dict:
    response = client.post("/v1/web/session")
    assert response.status_code == 201, response.text
    return {"X-User-Key": response.json()["user_key"]}


def _start(client, mode="login", headers=None, nonce=NONCE, **extra):
    return client.post("/v1/web/auth/google/start", headers=headers or {}, json={"mode": mode, "client_nonce": nonce, **extra})


def _state_of(url: str) -> dict:
    return {key: values[0] for key, values in parse_qs(urlparse(url).query).items()}


def _callback(client, state, code="sub-alice", **extra):
    return client.get("/v1/web/auth/google/callback", params={"state": state, "code": code, **extra})


def _location(response) -> tuple[str, dict]:
    assert response.status_code == 302, response.text
    parsed = urlparse(response.headers["location"])
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}", {key: values[0] for key, values in parse_qs(parsed.query).items()}


def _flow(client, code="sub-alice", mode="login", headers=None, nonce=NONCE):
    """시작 → 콜백 → 돌려받은 표. 콜백이 웹으로 보낸 주소의 쿼리를 돌려준다."""
    started = _start(client, mode, headers=headers, nonce=nonce)
    assert started.status_code == 200, started.text
    state = _state_of(started.json()["authorize_url"])["state"]
    where, query = _location(_callback(client, state, code))
    assert where == f"{WEB}/auth/done"
    return query


def _exchange(client, ticket, nonce=NONCE):
    return client.post("/v1/web/auth/exchange", json={"ticket": ticket, "client_nonce": nonce})


def test_providers_list_only_what_is_set_up_and_is_empty_not_a_404_when_nothing_is(social, monkeypatch):
    client = social["client"]
    assert client.get("/v1/web/auth/providers").json() == {"providers": [{"id": "google"}]}
    settings = settings_module.get_settings()
    monkeypatch.setattr(settings, "google_client_secret", "")                       # 반쯤 설정된 업체는 빠진다
    empty = client.get("/v1/web/auth/providers")
    assert empty.status_code == 200 and empty.json() == {"providers": []}
    assert _start(client).status_code == 404 and _start(client).json()["error"]["code"] == "provider_not_enabled"
    assert client.get("/v1/web/auth/google/callback", params={"state": "x", "code": "y"}).status_code == 302   # 콜백은 늘 웹으로 돌려보낸다


def test_start_builds_the_provider_address_and_validates_the_request(social):
    client = social["client"]
    started = _start(client)
    assert started.status_code == 200 and started.headers["cache-control"] == "no-store"
    url = started.json()["authorize_url"]
    query = _state_of(url)
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert query["redirect_uri"] == "https://api.example.test/v1/web/auth/google/callback"      # 콜백은 서버 설정의 주소다
    assert query["scope"] == "openid" and query["code_challenge_method"] == "S256" and query["client_id"] == "client-id-for-test"
    assert "secret-for-test" not in url and NONCE not in url                                       # 비밀값 · 시작한 브라우저의 nonce 는 주소에 안 실린다
    assert _start(client, nonce="short").status_code == 422
    assert _start(client, nonce="short").json()["error"]["code"] == "invalid_client_nonce"
    assert client.post("/v1/web/auth/google/start", json={"mode": "nope", "client_nonce": NONCE}).status_code == 422
    unauth = _start(client, "link")                                                                # 연결은 키가 필요하다
    assert unauth.status_code == 401 and unauth.json()["error"]["code"] == "unauthenticated"
    assert _start(client, "link", headers={"X-User-Key": "acop_u_nope"}).status_code == 401


def test_login_creates_a_user_once_and_signs_the_same_account_in_with_a_new_key_leaving_the_old_one(social):
    client, google = social["client"], social["google"]
    where, query = _location(_callback(client, _state_of(_start(client).json()["authorize_url"])["state"], "sub-alice"))
    assert where == f"{WEB}/auth/done" and set(query) == {"ticket"}
    # 콜백이 돌려받은 값이 시작할 때 만든 것과 이어진다 — PKCE 검증값 · nonce 는 서버만 알았다가 업체에 갔다
    call = google.calls[0]
    assert call["redirect_uri"] == "https://api.example.test/v1/web/auth/google/callback" and len(call["verifier"]) >= 43
    created = _exchange(client, query["ticket"])
    assert created.status_code == 200 and created.headers["cache-control"] == "no-store"
    body = created.json()
    assert body["outcome"] == "created" and body["provider"] == "google" and body["trips"] == 0 and body["user_key"].startswith("acop_u_")
    key_a = {"X-User-Key": body["user_key"]}
    assert client.get("/v1/web/auth/links", headers=key_a).json()["links"][0]["provider"] == "google"
    assert client.get("/v1/web/trips", headers=key_a).status_code == 200                              # 새 키가 정말 열린다
    # 같은 계정으로 다른 기기에서 로그인 → 같은 사용자, 새 키 하나 더
    again = _exchange(client, _flow(client, "sub-alice")["ticket"]).json()
    assert again["outcome"] == "signed_in" and again["user_key"] != body["user_key"] and "새 키" in again["notice"]
    key_b = {"X-User-Key": again["user_key"]}
    with get_connection() as conn:
        assert resolve(conn, tenant_id=social["tenant"], raw=key_a["X-User-Key"]) == resolve(conn, tenant_id=social["tenant"], raw=key_b["X-User-Key"])
    assert client.get("/v1/web/trips", headers=key_a).status_code == 200                              # ★옛 기기의 키는 그대로다
    # 다른 계정은 다른 사용자
    other = _exchange(client, _flow(client, "sub-bob")["ticket"]).json()
    assert other["outcome"] == "created"
    with get_connection() as conn:
        assert resolve(conn, tenant_id=social["tenant"], raw=other["user_key"]) != resolve(conn, tenant_id=social["tenant"], raw=key_a["X-User-Key"])


def test_link_attaches_the_account_to_the_key_owner_without_changing_the_key(social):
    client = social["client"]
    mine = _session(client)
    query = _flow(client, "sub-carol", mode="link", headers=mine)
    linked = _exchange(client, query["ticket"]).json()
    assert linked["outcome"] == "linked" and "user_key" not in linked and linked["provider"] == "google"        # 키를 바꾸지 않는다
    assert [item["provider"] for item in client.get("/v1/web/auth/links", headers=mine).json()["links"]] == ["google"]
    # 이제 그 계정으로 로그인하면 내 사용자로 들어온다
    signed = _exchange(client, _flow(client, "sub-carol")["ticket"]).json()
    assert signed["outcome"] == "signed_in"
    with get_connection() as conn:
        assert resolve(conn, tenant_id=social["tenant"], raw=signed["user_key"]) == resolve(conn, tenant_id=social["tenant"], raw=mine["X-User-Key"])
    # 같은 계정을 같은 사용자가 다시 연결해도 안 깨진다(멱등)
    assert _exchange(client, _flow(client, "sub-carol", mode="link", headers=mine)["ticket"]).json()["outcome"] == "linked"


def test_an_account_attached_to_someone_else_is_never_merged(social):
    client = social["client"]
    first, second = _session(client), _session(client)
    assert _exchange(client, _flow(client, "sub-dave", mode="link", headers=first)["ticket"]).json()["outcome"] == "linked"
    started = _start(client, "link", headers=second)
    where, query = _location(_callback(client, _state_of(started.json()["authorize_url"])["state"], "sub-dave"))
    assert query == {"error": "already_linked_elsewhere"}
    assert client.get("/v1/web/auth/links", headers=second).json() == {"links": []}                    # 두 번째 사용자에게는 붙지 않았다


def test_a_ticket_works_once_for_the_browser_that_started_it_and_expires(social):
    client = social["client"]
    ticket = _flow(client, "sub-erin")["ticket"]
    wrong = _exchange(client, ticket, nonce="x" * 40)                                                  # 공격자의 브라우저는 nonce 를 모른다
    assert wrong.status_code == 410 and wrong.json()["error"]["code"] == "ticket_invalid"
    assert _exchange(client, ticket, nonce="short").status_code == 410
    assert _exchange(client, ticket).status_code == 200                                                # ★틀린 시도가 진짜 표를 태우지 않았다
    replay = _exchange(client, ticket)
    assert replay.status_code == 410 and replay.json()["error"]["code"] == "ticket_invalid"            # 둘째는 410
    assert _exchange(client, "no-such-ticket").status_code == 410 and _exchange(client, "").status_code == 410
    # 60초가 지난 표
    late = _flow(client, "sub-frank")["ticket"]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE web_oauth_tickets SET created_at = now() - interval '61 seconds' WHERE tenant_id=%s", (social["tenant"],))
    assert _exchange(client, late).status_code == 410


def test_the_start_record_is_used_once_for_ten_minutes_and_only_for_its_own_provider(social):
    client = social["client"]
    state = _state_of(_start(client).json()["authorize_url"])["state"]
    assert _location(_callback(client, state, "sub-g1"))[1].keys() == {"ticket"}
    assert _location(_callback(client, state, "sub-g1"))[1] == {"error": "failed"}                      # 같은 state 로 다시 — 한 번만
    assert _location(_callback(client, "unknown-state"))[1] == {"error": "failed"}
    assert _location(client.get("/v1/web/auth/google/callback", params={"code": "sub-g2"}))[1] == {"error": "failed"}    # state 없음
    old = _state_of(_start(client).json()["authorize_url"])["state"]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE web_oauth_states SET created_at = now() - interval '11 minutes' WHERE tenant_id=%s", (social["tenant"],))
    assert _location(_callback(client, old, "sub-g3"))[1] == {"error": "failed"}                        # 10분이 지났다
    # 다른 업체의 콜백 주소로 온 state 는 받지 않는다
    other = _state_of(_start(client).json()["authorize_url"])["state"]
    assert _location(client.get("/v1/web/auth/kakao/callback", params={"state": other, "code": "sub-g4"}))[1] == {"error": "failed"}


def test_provider_errors_and_cancellation_come_back_to_the_web_as_error_codes(social):
    client = social["client"]
    state = lambda: _state_of(_start(client).json()["authorize_url"])["state"]               # noqa: E731
    assert _location(client.get("/v1/web/auth/google/callback", params={"state": state(), "error": "access_denied"}))[1] == {"error": "cancelled"}
    assert _location(client.get("/v1/web/auth/google/callback", params={"state": state(), "error": "server_error"}))[1] == {"error": "denied"}
    assert _location(_callback(client, state(), "bad-code"))[1] == {"error": "failed"}                   # 업체가 코드를 거절 — 표를 만들지 않는다
    assert _location(client.get("/v1/web/auth/google/callback", params={"state": state()}))[1] == {"error": "failed"}   # 코드 없음
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM web_oauth_tickets WHERE tenant_id=%s", (social["tenant"],))
        assert cur.fetchone()[0] == 0


def test_unlink_removes_only_the_attachment_and_says_not_linked_the_second_time(social):
    client = social["client"]
    mine = _session(client)
    _exchange(client, _flow(client, "sub-hana", mode="link", headers=mine)["ticket"])
    removed = client.delete("/v1/web/auth/google", headers=mine)
    assert removed.status_code == 200 and removed.json() == {"links": []}
    assert client.get("/v1/web/trips", headers=mine).status_code == 200                                 # 키와 여행은 그대로
    again = client.delete("/v1/web/auth/google", headers=mine)
    assert again.status_code == 404 and again.json()["error"]["code"] == "not_linked"
    assert client.delete("/v1/web/auth/google").status_code == 401 and client.get("/v1/web/auth/links").status_code == 401
    # 해제한 계정으로 로그인하면 이제 새 사용자다
    fresh = _exchange(client, _flow(client, "sub-hana")["ticket"]).json()
    assert fresh["outcome"] == "created"


def test_only_a_hash_of_the_subject_is_stored_and_no_email_or_name_column_exists(social):
    client = social["client"]
    _exchange(client, _flow(client, "sub-ivan@example.test")["ticket"])
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT subject_hash FROM web_social_links WHERE tenant_id=%s", (social["tenant"],))
        [(stored,)] = cur.fetchall()
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name IN "
                    "('web_social_links','web_oauth_states','web_oauth_tickets')")
        columns = {name for (name,) in cur.fetchall()}
        cur.execute("SELECT state_hash, client_nonce_hash FROM web_oauth_states WHERE tenant_id=%s", (social["tenant"],))
        hashes = [value for row in cur.fetchall() for value in row]
    assert len(stored) == 64 and "ivan" not in stored and "example.test" not in stored
    assert not {"email", "name", "picture", "display_name", "sub", "subject"} & columns
    assert all(len(value) == 64 and NONCE not in value for value in hashes)                              # 시작한 브라우저의 nonce · state 도 해시뿐


def test_the_return_address_is_a_server_setting_and_a_missing_one_stops_the_callback(social, monkeypatch):
    client = social["client"]
    started = _start(client, headers=None)
    state = _state_of(started.json()["authorize_url"])["state"]
    response = client.get("/v1/web/auth/google/callback", params={"state": state, "code": "sub-x", "return_to": "https://evil.example",
                                                                  "redirect": "https://evil.example"})
    assert urlparse(response.headers["location"]).netloc == "web.example.test"                           # 요청이 주소를 바꾸지 못한다
    assert response.headers["referrer-policy"] == "no-referrer" and response.headers["cache-control"] == "no-store"
    settings = settings_module.get_settings()
    monkeypatch.setattr(settings, "web_origin", "")
    monkeypatch.setattr(settings, "web_allowed_origins", "")
    stopped = client.get("/v1/web/auth/google/callback", params={"state": "x", "code": "y"})
    assert stopped.status_code == 503 and stopped.json()["error"]["code"] == "web_origin_not_configured"
    monkeypatch.setattr(settings, "web_allowed_origins", "http://127.0.0.1:3100, http://other.test")  # 비면 허용 출처의 첫 값
    assert urlparse(client.get("/v1/web/auth/google/callback", params={"state": "x"}).headers["location"]).netloc == "127.0.0.1:3100"


def test_a_login_without_a_key_needs_a_human_check_when_one_is_required_and_a_login_with_a_key_does_not(social, monkeypatch):
    settings = settings_module.get_settings()
    monkeypatch.setattr(settings, "turnstile_secret", "turnstile-secret-for-test")
    passed: list[str] = []

    def verify(*, url, secret, token, remote_ip, timeout):
        passed.append(token)
        return {"success": token == "good", "error-codes": [] if token == "good" else ["invalid-input-response"]}

    client = TestClient(create_app(classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
                                   domain_routers=[build_trip_router(human_verify=verify),
                                                   build_auth_router(exchange=social["google"], human_verify=verify)]),
                        follow_redirects=False)
    needed = _start(client)
    assert needed.status_code == 422 and needed.json()["error"]["code"] == "human_check_required"
    wrong = _start(client, turnstile_token="bad")
    assert wrong.status_code == 403 and wrong.json()["error"]["code"] == "human_check_failed"
    assert _start(client, turnstile_token="good").status_code == 200
    assert _start(client, headers={"X-Turnstile-Token": "good"}).status_code == 200                      # 머리말로도 받는다
    mine = {"X-User-Key": client.post("/v1/web/session", headers={"X-Turnstile-Token": "good"}).json()["user_key"]}
    before = len(passed)
    assert _start(client, headers=mine).status_code == 200 and len(passed) == before                    # 키가 있으면 다시 묻지 않는다


def test_start_and_exchange_have_an_hourly_limit_per_address(social):
    ip = social["ip"]
    cap = int(settings_module.get_guardrails().get("security.web_auth_per_ip_hour"))
    for _ in range(cap):
        web_guard.count_auth(social["tenant"], "auth_start", ip=ip)
    with pytest.raises(web_guard.UsageRefused) as refused:
        web_guard.count_auth(social["tenant"], "auth_start", ip=ip)
    assert refused.value.code == "too_many_auth" and refused.value.status == 429 and refused.value.retry_after >= 1
    web_guard.count_auth(social["tenant"], "auth_exchange", ip=ip)                                      # 시작과 교환은 따로 센다
    web_guard.count_auth(social["tenant"], "auth_start", ip=ip + "9")                                   # 다른 주소는 그대로
    with pytest.raises(ValueError):
        web_guard.count_auth(social["tenant"], "auth_other", ip=ip)


def test_an_over_limit_response_is_429_with_retry_after(social, monkeypatch):
    def refuse(tenant, action, *, ip, now=None):
        raise web_guard.UsageRefused(status=429, code="too_many_auth", limit="per_ip_hour", action=action, used=30, cap=30, retry_after=77)

    monkeypatch.setattr(web_guard, "count_auth", refuse)
    client = social["client"]
    for response in (_start(client), _exchange(client, "t")):
        assert response.status_code == 429 and response.headers["retry-after"] == "77"
        assert response.json()["error"]["code"] == "too_many_auth"


def test_keys_added_by_login_are_capped_by_dropping_the_oldest_and_a_new_user_has_no_key_until_exchange(social):
    tenant = social["tenant"]
    with get_connection() as conn, conn.transaction():
        customer, first = issue(conn, tenant_id=tenant)
        second = add_key(conn, tenant_id=tenant, customer_id=customer)
        third = add_key(conn, tenant_id=tenant, customer_id=customer, keep=2)                          # 유효한 키를 둘로 — 가장 오래된 키가 거둬진다
        assert resolve(conn, tenant_id=tenant, raw=first) is None
        assert resolve(conn, tenant_id=tenant, raw=second) == customer and resolve(conn, tenant_id=tenant, raw=third) == customer
    # 콜백만으로는 키가 생기지 않는다 — 키는 표를 교환할 때만 나온다
    query = _flow(social["client"], "sub-jane")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM web_user_keys k JOIN web_social_links l ON l.customer_id = k.customer_id "
                    "WHERE l.tenant_id=%s", (tenant,))
        assert cur.fetchone()[0] == 0
    assert "user_key" in _exchange(social["client"], query["ticket"]).json()


def test_a_browser_on_another_origin_may_call_delete(social):
    client = TestClient(create_app(classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
                                   domain_routers=[build_trip_router(), build_auth_router(exchange=social["google"])]))
    origin = settings_module.get_settings().web_allowed_origins.split(",")[0].strip()
    preflight = client.options("/v1/web/auth/google", headers={"Origin": origin, "Access-Control-Request-Method": "DELETE",
                                                              "Access-Control-Request-Headers": "x-user-key"})
    assert preflight.status_code == 200 and "DELETE" in preflight.headers["access-control-allow-methods"]


def test_a_user_with_an_attached_account_is_not_swept_up_by_the_idle_key_cleanup(social, monkeypatch):
    """빈 키 정리는 여행 없는 오래된 사용자를 지운다 — 소셜 계정이 붙은 사용자는 사용자 행을 가리키는 외래키 때문에 지워지지 않는다(계정으로 다시 들어올 수 있어야 한다)."""
    client, tenant = social["client"], social["tenant"]
    real = web_guard.values
    monkeypatch.setattr(web_guard, "values", lambda t: {**real(t), "web.idle_key_cleanup_enabled": True, "web.idle_key_days": 30})
    _exchange(client, _flow(client, "sub-kate")["ticket"])
    plain = _session(client)                                                                           # 계정이 안 붙은 빈 사용자 — 정리 대상이 맞는지 같이 본다
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE web_user_keys SET created_at = now() - interval '400 days', last_used_at = NULL WHERE tenant_id=%s", (tenant,))
    with get_connection() as conn:
        result = web_guard.cleanup_idle_keys(conn, tenant, now=datetime.now().astimezone())
    assert result["customers"] == 2 and result["customers_deleted"] == 1 and result["customers_kept"] == 1, result     # 붙은 사용자는 남고 빈 사용자만 지워졌다
    assert client.get("/v1/web/trips", headers=plain).status_code == 401
    signed = _exchange(client, _flow(client, "sub-kate")["ticket"]).json()
    assert signed["outcome"] == "signed_in"                                                            # 같은 사용자가 남아 있다
