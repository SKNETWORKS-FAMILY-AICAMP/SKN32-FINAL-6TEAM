# -*- coding: utf-8 -*-
"""「디스코드로 연결」 — `POST …/discord/connect/start` → 디스코드 → `GET …/callback`. `[2026-10-05 ui 세션 요청서 · 완료 기준 그대로]`

계약: `wiki/records/plans/2026-10-05_디스코드_연결버튼_백엔드_요청.md` · 구현 `discord_connect.py` · 경로 `trip_api.py`.

★디스코드(토큰 교환)는 **mock 서버**다 — `discord_connect.TRANSPORT` 에 꽂은 가짜 응답이 `webhook.url` 을 싣는다. 실제 디스코드 앱 · 승인 화면 · 웹훅 만들기는
 사용자가 개발자 포털에서 앱을 만든 뒤에야 확인할 수 있어 여기서는 안 한다(보고에 「실서버 확인: 안 했음」으로 적는다).

★지키려는 것
 ①설정(클라이언트 ID · 비밀값)이 없으면 `available` 이 false 이고 `start` 는 404 · 있으면 true
 ②`start` → 디스코드 주소(권한 `webhook.incoming` 하나 · 콜백 주소 · `state`) → `callback` → 저장(조회에는 가린 모양만 · 상태 `untested`) → 웹으로 302 `?discord=connected`
 ③같은 `state` 두 번 · 11분 뒤 · 모르는 `state` · 다른 흐름의 `state` → `expired`(디스코드에 묻지도 않는다) · 취소(`access_denied`) → `cancelled`(저장 없음)
 ④토큰 교환 실패 · `webhook` 없음 · 웹훅 주소가 디스코드 것이 아님 · 연결 오류 → `failed`(저장 없음)
 ⑤`access_token` · `refresh_token` · 웹훅 토큰 · 비밀값이 DB 어느 칸에도 로그 어디에도 없다
 ⑥이미 웹훅이 있어도 연결하면 새 것으로 바뀐다(상태 `untested`) · 남의 `state` 는 남의 프로필에만 쓰인다
 ⑦`start` 는 로그인한 사용자만(쿠키면 CSRF 까지) · 사용자당 한 시간 한도

재현:

    python -m pytest tests/e2e/test_discord_connect.py -v
"""
from __future__ import annotations

import json
import logging
from urllib.parse import parse_qs, parse_qsl, urlparse

import httpx
import pytest

import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.modules.web_account import customer_profile as profile
from app.domains.travel_ops.ports.notify_channels import discord_connect
from app.domains.travel_ops.modules.web_account import web_auth

from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_cookie_session import WEB, _guest, cookies  # noqa: F401
from .test_web_api import _h

CLIENT_ID = "1234567890123456789"
CLIENT_SECRET = "client-secret-for-test-abcdef"
API = "http://api.example.test"                       # `cookies` 픽스처의 공개 주소
CALLBACK = f"{API}/v1/web/profile/discord/connect/callback"
ID_A, TOKEN_A = "111111111111111111", "AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYy0123456789_-aaaa"
ID_B, TOKEN_B = "222222222222222222", "ZzYyXxWwVvUuTtSsRrQqPpOoNnMmLlKkJjIiHhGgFfEeDdCcBbAa9876543210_-bbbb"
URL_A = f"https://discord.com/api/webhooks/{ID_A}/{TOKEN_A}"
URL_B = f"https://discord.com/api/webhooks/{ID_B}/{TOKEN_B}"
ACCESS, REFRESH = "access-token-must-not-be-kept-123456", "refresh-token-must-not-be-kept-654321"


def _grant(url: str, webhook_id: str, token: str) -> dict:
    """디스코드 토큰 교환 응답 모양 — `webhook` 안에 주소가 있다."""
    return {"access_token": ACCESS, "refresh_token": REFRESH, "token_type": "Bearer", "expires_in": 604800, "scope": "webhook.incoming",
            "webhook": {"id": webhook_id, "token": token, "url": url, "channel_id": "333", "guild_id": "444", "name": "triPilot"}}


@pytest.fixture()
def hook(cookies, monkeypatch):  # noqa: F811
    """디스코드 앱이 설정된 서버 + 토큰 교환 mock 서버. `box["response"]` 로 디스코드의 답을 정하고 `box["requests"]` 에 받은 요청이 쌓인다."""
    settings = settings_module.get_settings()
    monkeypatch.setattr(settings, "discord_client_id", CLIENT_ID)
    monkeypatch.setattr(settings, "discord_client_secret", CLIENT_SECRET)
    box: dict = {"requests": [], "response": lambda: httpx.Response(200, json=_grant(URL_A, ID_A, TOKEN_A))}

    def handler(request: httpx.Request) -> httpx.Response:
        box["requests"].append(request)
        return box["response"]()

    monkeypatch.setattr(discord_connect, "TRANSPORT", httpx.MockTransport(handler))
    return {**cookies, "box": box}


def _key(env) -> dict:
    """키로 인증하는 사용자 하나 — 머리말."""
    response = env["client"].post("/v1/web/session")
    assert response.status_code == 201, response.text
    return _h(response.json()["user_key"])


def _start(env, headers):
    return env["client"].post("/v1/web/profile/discord/connect/start", headers=headers)


def _state(started) -> str:
    assert started.status_code == 200, started.text
    return parse_qs(urlparse(started.json()["authorize_url"]).query)["state"][0]


def _callback(env, **params):
    return env["client"].get("/v1/web/profile/discord/connect/callback", params=params)        # ★인증 없음 — 브라우저 이동

def _result(response) -> str:
    assert response.status_code == 302, response.text
    parsed = urlparse(response.headers["location"])
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == f"{WEB}/mypage"
    return parse_qs(parsed.query)["discord"][0]


def _profile(env, headers) -> dict:
    return env["client"].get("/v1/web/profile", headers=headers).json()


def _connect(env, headers, code="the-code") -> str:
    return _result(_callback(env, code=code, state=_state(_start(env, headers))))


# ── ① 설정 ──────────────────────────────────────────────────────
def test_without_a_discord_app_the_button_is_hidden_and_start_is_404(cookies):  # noqa: F811
    headers = _key(cookies)
    assert _profile(cookies, headers)["discord_connect"] == {"available": False}
    refused = _start(cookies, headers)
    assert refused.status_code == 404 and refused.json()["error"]["code"] == "not_found"


def test_half_configured_app_is_not_available(cookies, monkeypatch):  # noqa: F811
    """클라이언트 ID 만 있고 비밀값이 없으면 켜지지 않는다 — 반쯤 켜진 채 뜨지 않게."""
    monkeypatch.setattr(settings_module.get_settings(), "discord_client_id", CLIENT_ID)
    assert _profile(cookies, _key(cookies))["discord_connect"] == {"available": False}


def test_without_a_web_origin_it_is_not_available(hook, monkeypatch):
    """돌아갈 웹 주소를 모르면 단추를 보이지 않는다 — 콜백이 갈 곳이 없다."""
    settings = settings_module.get_settings()
    monkeypatch.setattr(settings, "web_origin", "")
    monkeypatch.setattr(settings, "web_allowed_origins", "")
    assert _profile(hook, _key(hook))["discord_connect"] == {"available": False}
    assert _callback(hook, code="x", state="y").status_code == 503


def test_every_profile_response_carries_the_flag(hook, monkeypatch):
    """조회 · 갱신 · 시험 발송 응답 모두 같은 칸을 싣는다 — 웹이 응답마다 같은 모양으로 읽는다(저장 직후 단추가 사라지지 않게)."""
    monkeypatch.setattr(profile, "TRANSPORT", httpx.MockTransport(lambda _request: httpx.Response(204)))      # 시험 발송이 실제 디스코드로 나가지 않게
    headers = _key(hook)
    assert _profile(hook, headers)["discord_connect"] == {"available": True}
    saved = hook["client"].put("/v1/web/profile", headers=headers, json={"recovery_email": "me@example.com"})
    assert saved.json()["discord_connect"] == {"available": True}
    hook["client"].put("/v1/web/profile", headers=headers, json={"discord_webhook_url": URL_A})
    tested = hook["client"].post("/v1/web/profile/discord/test", headers=headers)
    assert tested.status_code == 200 and tested.json()["profile"]["discord_connect"] == {"available": True}


# ── ② 한 바퀴 ───────────────────────────────────────────────────
def test_start_gives_the_discord_address_with_one_scope_and_our_callback(hook):
    started = _start(hook, _key(hook))
    assert started.status_code == 200 and started.headers["cache-control"] == "no-store"
    url = urlparse(started.json()["authorize_url"])
    assert f"{url.scheme}://{url.netloc}{url.path}" == "https://discord.com/oauth2/authorize"
    query = dict(parse_qsl(url.query))
    assert query["client_id"] == CLIENT_ID and query["response_type"] == "code"
    assert query["scope"] == "webhook.incoming"                          # 이 권한 하나뿐 — 이메일 · 서버 목록은 안 묻는다
    assert query["redirect_uri"] == CALLBACK and len(query["state"]) >= 40
    assert CLIENT_SECRET not in started.text                            # 비밀값은 주소에 없다


def test_a_full_round_trip_saves_the_webhook_like_a_pasted_one(hook, caplog):
    caplog.set_level(logging.DEBUG)
    headers = _key(hook)
    state = _state(_start(hook, headers))
    response = _callback(hook, code="the-code", state=state)
    assert _result(response) == "connected"
    assert response.headers["cache-control"] == "no-store" and response.headers["referrer-policy"] == "no-referrer"

    [sent] = hook["box"]["requests"]                                   # 디스코드에는 딱 한 번 묻는다
    assert str(sent.url) == "https://discord.com/api/oauth2/token"
    form = dict(parse_qsl(sent.content.decode()))
    assert form == {"grant_type": "authorization_code", "code": "the-code", "redirect_uri": CALLBACK,
                    "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET}

    body = _profile(hook, headers)
    assert body["discord_webhook"] == {"set": True, "masked": f"https://discord.com/api/webhooks/{ID_A[:4]}…/••••", "status": "untested",
                                       "checked_at": None}
    assert TOKEN_A not in json.dumps(body) and ID_A not in json.dumps(body)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT discord_webhook_enc FROM customer_profiles WHERE tenant_id=%s", (hook["tenant"],))
        [(stored,)] = cur.fetchall()
    assert stored.startswith("v1:") and profile.decrypt(stored) == URL_A                    # 붙여넣은 주소와 같은 저장(암호화)


# ── ③ 만료 · 재사용 · 취소 ───────────────────────────────────────
def test_the_same_state_twice_is_expired_and_discord_is_not_asked_again(hook):
    state = _state(_start(hook, _key(hook)))
    assert _result(_callback(hook, code="c1", state=state)) == "connected"
    assert _result(_callback(hook, code="c2", state=state)) == "expired"
    assert len(hook["box"]["requests"]) == 1


def test_an_unknown_state_or_a_missing_state_is_expired(hook):
    assert _result(_callback(hook, code="c", state="never-issued")) == "expired"
    assert _result(_callback(hook, code="c")) == "expired"
    assert hook["box"]["requests"] == []


def test_a_state_older_than_ten_minutes_is_expired(hook):
    headers = _key(hook)
    state = _state(_start(hook, headers))
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE web_oauth_states SET created_at = now() - interval '11 minutes' WHERE tenant_id=%s", (hook["tenant"],))
    assert _result(_callback(hook, code="c", state=state)) == "expired"
    assert hook["box"]["requests"] == [] and _profile(hook, headers)["discord_webhook"]["set"] is False


def test_a_state_from_another_flow_is_not_accepted_here(hook):
    """구글 로그인 시작 기록으로는 디스코드 연결을 못 끝낸다 — 같은 표를 쓰지만 `provider` 가 다르다."""
    with get_connection() as conn, conn.transaction():
        state, _nonce = web_auth.begin(conn, tenant_id=hook["tenant"], provider="google", mode="login", customer_id=None,
                                       client_nonce="n" * 40, verifier="v")
    assert _result(_callback(hook, code="c", state=state)) == "expired"
    assert hook["box"]["requests"] == []


def test_cancel_is_cancelled_saves_nothing_and_burns_the_state(hook):
    headers = _key(hook)
    state = _state(_start(hook, headers))
    assert _result(_callback(hook, error="access_denied", error_description="The resource owner denied", state=state)) == "cancelled"
    assert hook["box"]["requests"] == [] and _profile(hook, headers)["discord_webhook"]["set"] is False
    assert _result(_callback(hook, code="late", state=state)) == "expired"                    # 취소한 state 로 뒤늦게 코드를 넣을 수 없다


def test_cancel_wins_even_if_the_state_is_old(hook):
    assert _result(_callback(hook, error="access_denied", state="gone")) == "cancelled"


def test_any_other_discord_error_is_failed(hook):
    state = _state(_start(hook, _key(hook)))
    assert _result(_callback(hook, error="server_error", state=state)) == "failed"
    assert hook["box"]["requests"] == []


# ── ④ 실패 ──────────────────────────────────────────────────────
def _no_webhook() -> httpx.Response:
    return httpx.Response(200, json={"access_token": ACCESS, "refresh_token": REFRESH, "scope": "identify"})


def _foreign_webhook() -> httpx.Response:
    return httpx.Response(200, json=_grant(f"https://evil.example/api/webhooks/{ID_A}/{TOKEN_A}", ID_A, TOKEN_A))


def _redirected() -> httpx.Response:
    return httpx.Response(302, headers={"location": "https://evil.example/x"})


def _boom() -> httpx.Response:
    raise httpx.ConnectError("no route")


@pytest.mark.parametrize("answer", [lambda: httpx.Response(400, json={"error": "invalid_grant"}), lambda: httpx.Response(401),
                                    lambda: httpx.Response(500, text="oops"), lambda: httpx.Response(200, text="not json"),
                                    lambda: httpx.Response(200, json=["list"]), _no_webhook, _foreign_webhook, _redirected, _boom],
                         ids=["400", "401", "500", "not-json", "json-list", "no-webhook", "foreign-host", "redirect", "connect-error"])
def test_a_bad_token_exchange_is_failed_and_nothing_is_saved(hook, answer):
    headers = _key(hook)
    hook["client"].put("/v1/web/profile", headers=headers, json={"discord_webhook_url": URL_B})        # 이미 있던 주소는 실패해도 그대로다
    hook["box"]["response"] = answer
    assert _connect(hook, headers) == "failed"
    view = _profile(hook, headers)["discord_webhook"]
    assert view["set"] is True and view["masked"] == f"https://discord.com/api/webhooks/{ID_B[:4]}…/••••"


# ── ⑤ 비밀값은 어디에도 ──────────────────────────────────────────
def test_no_token_or_secret_is_stored_or_logged(hook, caplog):
    caplog.set_level(logging.DEBUG)
    headers = _key(hook)
    assert _connect(hook, headers) == "connected"
    hook["box"]["response"] = lambda: httpx.Response(400, json={"error": "invalid_grant", "access_token": ACCESS})
    assert _connect(hook, headers) == "failed"
    secrets_ = (ACCESS, REFRESH, TOKEN_A, CLIENT_SECRET)
    logged = "\n".join(f"{record.getMessage()} {record.exc_text or ''}" for record in caplog.records)
    for secret in secrets_:
        assert secret not in logged, "로그에 비밀값이 있다"
    with get_connection() as conn, conn.cursor() as cur:
        for table in ("customer_profiles", "web_oauth_states", "web_oauth_tickets"):
            cur.execute(f"SELECT t::text FROM {table} t WHERE tenant_id=%s", (hook["tenant"],))
            dump = "\n".join(row[0] for row in cur.fetchall())
            for secret in secrets_:
                assert secret not in dump, f"{table} 에 비밀값이 있다"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='customer_profiles' ORDER BY 1")
        columns = {row[0] for row in cur.fetchall()}
    assert not {"access_token", "refresh_token", "webhook_token"} & columns                # 토큰을 둘 칸이 아예 없다


# ── ⑥ 바꿔 끼우기 · 남의 state ───────────────────────────────────
def test_connecting_again_replaces_the_old_webhook_and_resets_its_status(hook):
    headers = _key(hook)
    hook["client"].put("/v1/web/profile", headers=headers, json={"discord_webhook_url": URL_B})
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE customer_profiles SET discord_status='ok', discord_checked_at=now() WHERE tenant_id=%s", (hook["tenant"],))
    assert _profile(hook, headers)["discord_webhook"]["status"] == "ok"
    assert _connect(hook, headers) == "connected"
    view = _profile(hook, headers)["discord_webhook"]
    assert view["masked"] == f"https://discord.com/api/webhooks/{ID_A[:4]}…/••••" and view["status"] == "untested" and view["checked_at"] is None
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT discord_webhook_enc FROM customer_profiles WHERE tenant_id=%s", (hook["tenant"],))
        [(stored,)] = cur.fetchall()
    assert profile.decrypt(stored) == URL_A


def test_a_state_only_ever_saves_to_the_user_who_started_it(hook):
    """공격자가 자기 코드를 피해자에게 보내도 공격자 자신의 `state` 에 묶여 있어 **공격자 계정**에만 저장된다 — 피해자 프로필은 안 바뀐다."""
    victim, attacker = _key(hook), _key(hook)
    hook["client"].put("/v1/web/profile", headers=victim, json={"discord_webhook_url": URL_B})
    attacker_state = _state(_start(hook, attacker))
    # 피해자의 브라우저가 (쿠키가 있어도 없어도) 공격자의 state 로 콜백을 연다
    assert _result(hook["client"].get("/v1/web/profile/discord/connect/callback", params={"code": "c", "state": attacker_state},
                                       headers=victim)) == "connected"
    assert _profile(hook, attacker)["discord_webhook"]["masked"].endswith(f"{ID_A[:4]}…/••••")
    assert _profile(hook, victim)["discord_webhook"]["masked"].endswith(f"{ID_B[:4]}…/••••")


# ── ⑦ 인증 · 한도 ───────────────────────────────────────────────
def test_start_needs_a_logged_in_user(hook):
    assert hook["client"].post("/v1/web/profile/discord/connect/start").status_code == 401
    assert hook["client"].post("/v1/web/profile/discord/connect/start", headers=_h("not-a-real-key")).status_code == 401


def test_start_with_a_cookie_session_needs_the_csrf_token(hook):
    body, _raw = _guest(hook)
    client = hook["client"]
    assert client.post("/v1/web/profile/discord/connect/start", headers={"Origin": WEB}).status_code == 403            # CSRF 토큰 없음
    assert client.post("/v1/web/profile/discord/connect/start", headers={"Origin": "https://evil.example",
                                                                         "X-CSRF-Token": body["csrf_token"]}).status_code == 403
    ok = client.post("/v1/web/profile/discord/connect/start", headers={"Origin": WEB, "X-CSRF-Token": body["csrf_token"]})
    assert ok.status_code == 200 and ok.json()["authorize_url"].startswith("https://discord.com/oauth2/authorize?")


def test_start_is_limited_per_user_per_hour(hook):
    cap = int(settings_module.get_guardrails().get("security.discord_connect_start_per_hour"))
    one, other = _key(hook), _key(hook)
    for _ in range(cap):
        assert _start(hook, one).status_code == 200
    refused = _start(hook, one)
    assert refused.status_code == 429 and refused.json()["error"]["code"] == "too_many_requests"
    assert int(refused.headers["retry-after"]) >= 1
    assert _start(hook, other).status_code == 200                      # 다른 사용자는 그대로
