"""JWT issuance and authentication for the Composer write channel."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from acop_basement.core.settings import get_guardrails, get_settings

AUDIENCE = "final_project_sample"
ALGORITHM = "HS256"


class TokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sub: str = Field(min_length=1)
    scope: list[str] = Field(min_length=1)


def _auth_error(message: str = "invalid credentials") -> HTTPException:
    return HTTPException(401, {"error": {"code": "unauthenticated", "message": message}})


def issue_token(payload: TokenRequest, issuer_authorization: str | None) -> dict[str, object]:
    expected = get_settings().composer_issuer_secret
    if not issuer_authorization or not issuer_authorization.startswith("Bearer "):
        raise _auth_error("issuer authentication required")
    presented = issuer_authorization[7:]
    if not presented or presented != expected:
        raise _auth_error()
    configured = set(get_guardrails().get("security.scopes"))
    if any(scope not in configured for scope in payload.scope):
        raise HTTPException(422, {"error": {"code": "invalid_scope", "message": "scope is not configured"}})
    ttl = int(get_guardrails().get("security.composer_jwt_ttl_minutes"))
    if not 15 <= ttl <= 60:
        raise RuntimeError("security.composer_jwt_ttl_minutes must be between 15 and 60")
    now = datetime.now(timezone.utc)
    claims = {
        "sub": payload.sub,
        "aud": AUDIENCE,
        "scope": payload.scope,
        "iat": now,
        "exp": now + timedelta(minutes=ttl),
        "jti": str(uuid4()),
    }
    token = jwt.encode(claims, get_settings().composer_jwt_secret, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "expires_in": ttl * 60}


def authenticate_composer(authorization: str | None) -> dict[str, object]:
    if not authorization or not authorization.startswith("Bearer "):
        raise _auth_error("authentication required")
    try:
        claims = jwt.decode(
            authorization[7:], get_settings().composer_jwt_secret,
            algorithms=[ALGORITHM], audience=AUDIENCE,
            options={"require": ["sub", "aud", "scope", "iat", "exp", "jti"]},
        )
    except (jwt.PyJWTError, TypeError, ValueError) as exc:
        raise _auth_error() from exc
    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        raise _auth_error()
    if not isinstance(claims.get("scope"), list) or not all(isinstance(s, str) for s in claims["scope"]):
        raise _auth_error()
    return claims


def require_composer_scope(scope: str):
    def dependency(authorization: str | None = Header(default=None)) -> dict[str, object]:
        claims = authenticate_composer(authorization)
        if scope not in claims["scope"]:
            raise HTTPException(403, {"error": {"code": "scope_denied", "message": "scope denied"}})
        return claims
    return dependency


router = APIRouter(tags=["authentication"])


@router.post("/auth/token")
def token(payload: TokenRequest, authorization: str | None = Header(default=None)):
    return issue_token(payload, authorization)
