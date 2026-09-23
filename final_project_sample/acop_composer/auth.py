"""Composer 쓰기 채널의 토큰 발급·검증.

★비밀·scope 목록·TTL 은 **호스트가 준다**(`ComposerHost.auth`). 2026-09-06
  이전에는 이 파일이 `acop_basement.core.settings` 를 직접 읽었다 — 그대로
  `final_project_cs` 에 설치하면 cs 의 비밀이 아니라 **sample 의 비밀**로
  토큰을 검증한다. 그러면 둘 중 하나다: 아무 토큰도 안 통하거나(설정이
  없어서), 남의 발급자가 만든 토큰이 통한다. 어느 쪽도 받아들일 수 없다.

★`aud` 도 호스트가 준다. 상수로 박아 두면 sample 용 토큰이 cs 에서 그대로
  통과한다 — 대상 격리는 서명만으로 되는 것이 아니다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from acop_composer.host import ComposerHost, HostIncomplete

ALGORITHM = "HS256"


class TokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sub: str = Field(min_length=1)
    scope: list[str] = Field(min_length=1)


def _auth_error(message: str = "invalid credentials") -> HTTPException:
    return HTTPException(401, {"error": {"code": "unauthenticated", "message": message}})


def _policy(host: ComposerHost):
    if host.auth is None:
        # ★조용히 통과시키지 않는다. 인증 정책이 없는 호스트에 이 라우터를 달면
        #   그건 **인증 없는 쓰기 채널**이다 — 2026-08-18 에 `/ui/composer` 가
        #   그 상태로 발견돼 통째로 제거됐다.
        raise HostIncomplete("호스트가 `auth` 정책을 넘기지 않았다")
    return host.auth


def issue_token(payload: TokenRequest, issuer_authorization: str | None,
                host: ComposerHost) -> dict[str, object]:
    policy = _policy(host)
    expected = policy.issuer_secret()
    if not issuer_authorization or not issuer_authorization.startswith("Bearer "):
        raise _auth_error("issuer authentication required")
    presented = issuer_authorization[7:]
    if not presented or presented != expected:
        raise _auth_error()
    configured = set(policy.configured_scopes())
    if any(scope not in configured for scope in payload.scope):
        raise HTTPException(422, {"error": {"code": "invalid_scope", "message": "scope is not configured"}})
    ttl = int(policy.ttl_minutes())
    if not 15 <= ttl <= 60:
        raise RuntimeError("composer JWT TTL must be between 15 and 60 minutes")
    now = datetime.now(timezone.utc)
    claims = {
        "sub": payload.sub,
        "aud": policy.audience,
        "scope": payload.scope,
        "iat": now,
        "exp": now + timedelta(minutes=ttl),
        "jti": str(uuid4()),
    }
    token = jwt.encode(claims, policy.jwt_secret(), algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "expires_in": ttl * 60}


def authenticate_composer(authorization: str | None, host: ComposerHost) -> dict[str, object]:
    policy = _policy(host)
    if not authorization or not authorization.startswith("Bearer "):
        raise _auth_error("authentication required")
    try:
        claims = jwt.decode(
            authorization[7:], policy.jwt_secret(),
            algorithms=[ALGORITHM], audience=policy.audience,
            options={"require": ["sub", "aud", "scope", "iat", "exp", "jti"]},
        )
    except (jwt.PyJWTError, TypeError, ValueError) as exc:
        raise _auth_error() from exc
    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        raise _auth_error()
    if not isinstance(claims.get("scope"), list) or not all(isinstance(s, str) for s in claims["scope"]):
        raise _auth_error()
    return claims


def require_composer_scope(host: ComposerHost, scope: str):
    def dependency(authorization: str | None = Header(default=None)) -> dict[str, object]:
        claims = authenticate_composer(authorization, host)
        if scope not in claims["scope"]:
            raise HTTPException(403, {"error": {"code": "scope_denied", "message": "scope denied"}})
        return claims
    return dependency


def create_auth_router(host: ComposerHost) -> APIRouter:
    """이 호스트용 `/auth/token` 라우터.

    ★모듈 수준 `router` 를 두지 않는다 — 그러면 어느 호스트의 비밀로 발급하는지가
      import 시점에 정해져 버리고, 한 프로세스에 두 호스트를 달 수 없다.
    """
    router = APIRouter(tags=["authentication"])

    @router.post("/auth/token")
    def token(payload: TokenRequest, authorization: str | None = Header(default=None)):
        return issue_token(payload, authorization, host)

    return router


__all__ = [
    "ALGORITHM", "TokenRequest", "authenticate_composer", "create_auth_router",
    "issue_token", "require_composer_scope",
]
