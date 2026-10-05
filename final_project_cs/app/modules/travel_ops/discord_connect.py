# -*- coding: utf-8 -*-
"""「디스코드로 연결」 단추 — 고객이 디스코드 창에서 서버·채널을 고르면 **디스코드가 웹훅 주소를 서버에 직접 돌려준다**. `[2026-10-05 ui 세션 요청서 · 사용자 「ㄱㄱ」]`

계약 `wiki/records/plans/2026-10-05_디스코드_연결버튼_백엔드_요청.md` · HTTP 는 `trip_api.py` 의 `/v1/web/profile/discord/connect/*`.

★한 바퀴: `start`(시작 기록 저장 → 디스코드 승인 주소) → 디스코드 창(서버·채널 고르고 승인) → `callback`(기록을 한 번만 꺼내 코드를 웹훅 주소로 바꾼다 → **붙여넣은 주소와 같은 경로로 저장**) → 웹으로 302.
  디스코드 OAuth2 의 `webhook.incoming` 권한을 쓴다 — 토큰 응답의 `webhook.url` 이 곧 고객 채널의 웹훅 주소다. 알림을 보내는 코드는 바뀌지 않는다.

★보안(요청서 「보안」):
  ①`state` 는 서버가 만들고 해시만 저장(사용자에 묶음) · 10분 · 한 번만. 콜백은 `state` 만으로 사용자를 정한다(쿠키에 기대지 않는다 — 다른 사이트에서 오는 이동).
     공격자가 자기 `code` 를 피해자에게 보내도 **공격자 자신의 `state`** 에 묶여 있어 공격자 계정에 공격자 채널이 저장될 뿐이다.
  ②돌아갈 웹 주소(`web_origin`)·콜백 주소는 서버 설정이고 요청 값으로 바꿀 수 없다(열린 리디렉션 금지).
  ③받은 것 중 **저장하는 것은 웹훅 주소 하나뿐**이다 — `access_token` · `refresh_token` 은 저장도 로그도 없이 버린다. 응답 본문 · `webhook.token` 은 어디에도 찍지 않는다
     (실패 이유는 **예외 종류 이름만** 로그에 남긴다).
  ④디스코드가 준 주소도 `customer_profile.parse_webhook` 검사를 통과해야 저장한다(통과 못 하면 `failed`).
  ⑤`start` 에 사용자 단위 한도(`security.discord_connect_start_per_hour`) — 콜백은 `state` 가 곧 한도다.
★기존 로그인 시작 기록 표(`web_oauth_states`)를 **그대로 쓴다**(마이그레이션 없음) — `provider` 를 `discord_webhook` 으로 달리해 디스코드 **로그인**(나중에 생길 `discord`)과 섞이지 않는다.
  PKCE 검증값 · OIDC nonce · 브라우저 nonce 칸은 이 흐름에 쓰이지 않아 빈 문자열이다(비밀값 클라이언트라 PKCE 가 필요 없고, 이 흐름은 ID 토큰을 안 받는다).
★`[미확보]` 고객이 고른 채널에서 **웹훅 관리 권한**이 있어야 하는지는 디스코드 문서에서 확인하지 못했다 — 권한이 없으면 디스코드 창이나 토큰 교환이 실패하고 우리는 `failed` 로 돌려보낸다.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx

import app.core.settings as settings_module
from app.core.settings import get_guardrails

from . import customer_profile, web_auth

log = logging.getLogger(__name__)

#: `web_oauth_states.provider` 에 넣는 값 — 디스코드 「로그인」과 구분한다
PROVIDER = "discord_webhook"
AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
TOKEN_URL = "https://discord.com/api/oauth2/token"
#: 이 권한 하나만 요청한다 — 고객 계정의 다른 것(이메일 · 서버 목록 · 이름)은 요청하지 않는다
SCOPE = "webhook.incoming"
#: 디스코드에 묻는 시간 상한(초) — ★우리가 고른 값. 사람이 기다리는 일이라 길게 잡지 않는다
HTTP_TIMEOUT = 10.0
#: 웹이 읽는 결과 낱말(`?discord=`) — 이 밖은 만들지 않는다(웹은 모르는 낱말을 `failed` 로 읽는다)
RESULTS = ("connected", "cancelled", "expired", "failed")
MAX_CODE = 512

#: 시험이 바깥 호출을 가로채는 자리 — 실제 운영에서는 비어 있어 진짜 HTTP 로 간다(`customer_profile.TRANSPORT` 와 같은 방식)
TRANSPORT: httpx.BaseTransport | None = None


class DiscordConnectError(Exception):
    """디스코드와의 대화가 실패했다 — 이유는 로그에 종류만, 사용자에게는 `failed`."""


def _h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── 설정 ────────────────────────────────────────────────────────
def client_pair() -> tuple[str, str] | None:
    """디스코드 앱의 (클라이언트 ID, 비밀값) — **둘 다** 있어야 켜진다. 반쯤 켜진 채 뜨지 않게."""
    settings = settings_module.get_settings()
    client_id = (getattr(settings, "discord_client_id", "") or "").strip()
    secret = (getattr(settings, "discord_client_secret", "") or "").strip()
    return (client_id, secret) if client_id and secret else None


def web_origin() -> str:
    """돌아갈 웹 주소(출처만). ★서버 설정이다. 비어 있으면 `web_allowed_origins` 의 첫 값(소셜 로그인과 같은 규칙)."""
    settings = settings_module.get_settings()
    origin = (settings.web_origin or "").strip()
    if not origin:
        origin = next((o.strip() for o in settings.web_allowed_origins.split(",") if o.strip()), "")
    return origin.rstrip("/")


def available() -> bool:
    """단추를 보일 수 있나 — 디스코드 앱 설정이 있고 돌아갈 웹 주소가 있을 때만(가짜 단추를 두지 않는다)."""
    return client_pair() is not None and bool(web_origin())


def redirect_uri() -> str:
    """디스코드 앱 설정(OAuth2 → Redirects)에 **같은 값을 등록**해야 한다 — 안 맞으면 디스코드가 거부한다."""
    return f"{settings_module.get_settings().public_base_url.rstrip('/')}/v1/web/profile/discord/connect/callback"


# ── 시작 ────────────────────────────────────────────────────────
def begin(conn, *, tenant_id: str, customer_id: UUID) -> str:
    """시작 기록을 저장하고 `state` 원문을 돌려준다(저장은 해시뿐). 지나간 기록은 이따금 치운다(한 시간 — 수명보다 한참 길다)."""
    state = secrets.token_urlsafe(32)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO web_oauth_states (state_hash, tenant_id, provider, mode, customer_id, code_verifier, nonce, "
                    "client_nonce_hash) VALUES (%s,%s,%s,'link',%s,'','','')", (_h(state), tenant_id, PROVIDER, customer_id))
        cur.execute("DELETE FROM web_oauth_states WHERE created_at < now() - interval '1 hour'")
    return state


def authorize_url(state: str) -> str:
    pair = client_pair()
    if pair is None:
        raise DiscordConnectError("not configured")
    query = [("client_id", pair[0]), ("response_type", "code"), ("scope", SCOPE), ("redirect_uri", redirect_uri()), ("state", state)]
    return f"{AUTHORIZE_URL}?{urlencode(query)}"


# ── 콜백 ────────────────────────────────────────────────────────
def exchange_webhook_url(code: str) -> str:
    """디스코드 토큰 엔드포인트에 코드를 내고 응답의 **`webhook.url` 하나만** 돌려준다. 어떤 실패든 `DiscordConnectError`.

    ★`access_token` · `refresh_token` 은 읽지도 않는다(이 함수를 벗어나지 못한다). 응답 본문 · 웹훅 토큰은 로그에 안 남긴다."""
    pair = client_pair()
    if pair is None:
        raise DiscordConnectError("not configured")
    try:
        with httpx.Client(transport=TRANSPORT, timeout=httpx.Timeout(HTTP_TIMEOUT), follow_redirects=False) as client:
            response = client.post(TOKEN_URL, data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri(),
                                                    "client_id": pair[0], "client_secret": pair[1]},
                                   headers={"Accept": "application/json"})
        if response.status_code != 200:
            raise DiscordConnectError(f"token endpoint HTTP {response.status_code}")
        webhook = response.json().get("webhook")
        url = webhook.get("url") if isinstance(webhook, dict) else None
        if not isinstance(url, str) or not url:
            raise DiscordConnectError("no webhook in token response")
        return url
    except DiscordConnectError:
        raise
    except Exception as exc:                              # noqa: BLE001 — 네트워크 · 형식 오류 전부 같은 「failed」
        log.warning("discord connect exchange failed reason=%s", type(exc).__name__)
        raise DiscordConnectError(type(exc).__name__) from exc


def finish(conn, *, tenant_id: str, state: str | None, code: str | None, error: str | None) -> str:
    """콜백 한 건을 처리하고 웹이 읽을 결과 낱말(`RESULTS` 중 하나)을 돌려준다. **어떤 경우에도 예외를 내지 않는다**(브라우저 이동이라 JSON 오류를 못 읽는다).

    ★`state` 는 무엇보다 먼저 한 번만 꺼낸다 — 취소 · 실패여도 다시 쓰지 못하게(코드 재사용 · 재전송 공격을 막는다).
    ★고객이 취소했으면(`error=access_denied`) `state` 가 낡았어도 `cancelled` 다 — 고객의 뜻이 분명하고 저장되는 것이 없다."""
    started = None
    if state and len(state) <= 200:
        with conn.transaction():
            started = web_auth.take_state(conn, tenant_id=tenant_id, state=state)
    if error == "access_denied":
        return "cancelled"
    if started is None or started["provider"] != PROVIDER or started["customer_id"] is None:
        return "expired"
    if error or not code or len(code) > MAX_CODE:
        return "failed"
    from . import consents

    try:
        consents.require(conn, tenant_id, started["customer_id"], "alert_channel")           # 게이트가 켜져 있으면 알림 채널 동의 없이는 저장하지 않는다
    except consents.ConsentError:
        return "failed"
    try:
        url = exchange_webhook_url(code)
        customer_profile.update(conn, tenant_id, started["customer_id"], {"discord_webhook_url": url})     # 붙여넣은 주소와 같은 경로 — 검사 · 암호화 · 가림 · untested
    except (DiscordConnectError, customer_profile.ProfileError):
        return "failed"
    except Exception as exc:                              # noqa: BLE001 — 저장 실패도 사용자에게는 `failed`(이유는 종류만 로그)
        log.warning("discord connect save failed reason=%s", type(exc).__name__)
        return "failed"
    return "connected"


def count_start(tenant_id: str, customer_id: UUID | str) -> None:
    """`start` 를 사용자당 한 시간에 몇 번까지만(`security.discord_connect_start_per_hour`). 막히면 `web_guard.UsageRefused`(429)."""
    from . import web_guard

    cap = int(get_guardrails().get("security.discord_connect_start_per_hour"))
    web_guard.count_per_key_hour(tenant_id, "discord_connect_start", customer_id=customer_id, cap=cap)


def public_state() -> dict[str, Any]:
    """`GET /v1/web/profile` 에 싣는 모양 — 디스코드 앱이 설정돼 있을 때만 `available: true`."""
    return {"available": available()}


__all__ = ["DiscordConnectError", "PROVIDER", "RESULTS", "authorize_url", "available", "begin", "count_start", "exchange_webhook_url",
           "finish", "public_state", "redirect_uri", "web_origin"]
