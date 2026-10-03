# -*- coding: utf-8 -*-
"""소셜 로그인 업체 — 주소 · 권한 범위 · 코드를 사용자 고유 번호(`sub`)로 바꾸는 일. `[2026-10-03 ui 세션 요청서 「소셜 로그인」 — 1단계는 구글 하나]`

★이 층은 **업체와 말하는 일**만 한다(주소 만들기 · 토큰 받기 · ID 토큰 확인). 누구에게 붙이고 무엇을 저장하는지는 `travel_ops/web_auth.py` 가 정한다.
★구글은 표준 OIDC 다: 스코프 `openid` 하나로 ID 토큰에서 **사용자 고유 번호 `sub`** 를 얻는다(이메일 · 이름은 요청하지 않는다). `state` · PKCE(`S256`) · `nonce` 를 쓴다.
★ID 토큰은 **서명을 업체 공개키(JWKS)로 확인**하고 발급자 · 대상(`aud` = 우리 클라이언트 ID) · 만료 · `nonce` 를 본다 — 토큰 엔드포인트에서 직접 받았어도 확인을 건너뛰지 않는다.
★업체를 더하려면 `configured()` 에 한 줄을 더한다(업체마다 다른 것은 주소 · 권한 범위 · 공개키 주소뿐). 카카오 · 네이버가 OIDC `sub` 를 안 주는 설정이면 사용자 정보 호출로 `id` 를 얻는 길이 따로 필요하다
  (`[미확보]` 우리 앱 종류에서 되는지 — 요청서 「확인하지 못한 것」).
★비밀값은 설정(`ACOP_GOOGLE_CLIENT_SECRET`)에서만 읽고 어디에도 찍지 않는다. 실패 이유는 로그에만 남기고 응답에는 「failed」만 간다.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from typing import Any, Callable, Protocol
from urllib.parse import urlencode

import httpx
import jwt

log = logging.getLogger(__name__)

#: 업체에 묻는 시간 상한(초) — ★우리가 고른 값. 로그인은 사람이 기다리는 일이라 길게 잡지 않는다
HTTP_TIMEOUT = 10.0


class OAuthError(Exception):
    """업체와의 대화가 실패했다 — 이유는 로그에만, 사용자에게는 「failed」."""


@dataclass(frozen=True)
class Provider:
    id: str                              # google | kakao | naver | discord
    authorize_url: str
    token_url: str
    scope: str
    client_id: str
    client_secret: str
    jwks_url: str                        # ID 토큰 서명 확인용 공개키 목록
    issuers: tuple[str, ...]
    #: 로그인 화면 주소에 더 붙일 값 — 구글은 계정 고르기를 늘 보이게(다른 기기의 다른 계정으로 조용히 들어가지 않게)
    extra_authorize: tuple[tuple[str, str], ...] = ()


def configured(settings: Any) -> dict[str, Provider]:
    """**설정이 끝난 업체만**(클라이언트 ID · 비밀값이 둘 다 있어야 한다) — 없는 업체는 `GET /v1/web/auth/providers` 에서 빠진다."""
    out: dict[str, Provider] = {}
    client_id = getattr(settings, "google_client_id", "") or ""
    client_secret = getattr(settings, "google_client_secret", "") or ""
    if client_id and client_secret:
        out["google"] = Provider(
            id="google", authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token", scope="openid", client_id=client_id, client_secret=client_secret,
            jwks_url="https://www.googleapis.com/oauth2/v3/certs",
            issuers=("https://accounts.google.com", "accounts.google.com"),
            extra_authorize=(("prompt", "select_account"),))
    return out


def pkce_challenge(verifier: str) -> str:
    """PKCE `S256` — `BASE64URL(SHA256(verifier))`(채움 `=` 없이)."""
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


def new_verifier() -> str:
    return secrets.token_urlsafe(64)          # 86자 — PKCE 검증값은 43~128자


def authorize_url(provider: Provider, *, redirect_uri: str, state: str, nonce: str, verifier: str) -> str:
    query = [("client_id", provider.client_id), ("redirect_uri", redirect_uri), ("response_type", "code"),
             ("scope", provider.scope), ("state", state), ("nonce", nonce),
             ("code_challenge", pkce_challenge(verifier)), ("code_challenge_method", "S256"), *provider.extra_authorize]
    return f"{provider.authorize_url}?{urlencode(query)}"


class Exchanger(Protocol):
    """코드를 사용자 고유 번호로 바꾸는 것 — 실제는 `exchange_code`, 시험은 가짜 업체를 꽂는다."""

    def __call__(self, provider: Provider, *, code: str, verifier: str, redirect_uri: str, nonce: str) -> str: ...


_jwk_clients: dict[str, Any] = {}


def _signing_key(provider: Provider, id_token: str) -> Any:
    client = _jwk_clients.get(provider.jwks_url)
    if client is None:
        client = _jwk_clients[provider.jwks_url] = jwt.PyJWKClient(provider.jwks_url, timeout=HTTP_TIMEOUT)
    return client.get_signing_key_from_jwt(id_token).key


def exchange_code(provider: Provider, *, code: str, verifier: str, redirect_uri: str, nonce: str,
                  post: Callable[..., Any] | None = None, signing_key: Callable[[Provider, str], Any] | None = None) -> str:
    """업체의 토큰 엔드포인트에 코드를 내고, 받은 ID 토큰을 확인해 **사용자 고유 번호(`sub`)** 를 돌려준다. 어떤 실패든 `OAuthError`."""
    try:
        response = (post or httpx.post)(provider.token_url, data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri, "client_id": provider.client_id,
            "client_secret": provider.client_secret, "code_verifier": verifier}, timeout=HTTP_TIMEOUT)
        if response.status_code != 200:
            raise OAuthError(f"token endpoint HTTP {response.status_code}")
        id_token = response.json().get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise OAuthError("no id_token")
        key = (signing_key or _signing_key)(provider, id_token)
        claims = jwt.decode(id_token, key, algorithms=["RS256"], audience=provider.client_id, issuer=list(provider.issuers),
                            options={"require": ["exp", "iat", "iss", "aud", "sub"]}, leeway=30)
        if not hmac.compare_digest(str(claims.get("nonce") or ""), nonce):
            raise OAuthError("nonce mismatch")
        sub = str(claims["sub"]).strip()
        if not sub:
            raise OAuthError("empty sub")
        return sub
    except OAuthError:
        raise
    except Exception as exc:                              # noqa: BLE001 — 네트워크 · 서명 · 형식 오류 전부 같은 「failed」
        log.warning("oauth exchange failed provider=%s reason=%s", provider.id, type(exc).__name__)
        raise OAuthError(type(exc).__name__) from exc


__all__ = ["Exchanger", "OAuthError", "Provider", "authorize_url", "configured", "exchange_code", "new_verifier", "pkce_challenge"]
