from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from fastapi import Header, HTTPException

# ★다시 내보내는 import 다 — 이 모듈을 거쳐 가져다 쓰는 곳이 있다.
#   여기서 직접 쓰지 않아 안 쓰는 import 로 보이지만 지우면 그쪽이 깨진다.
from app.core.redaction import mask_json, masked  # noqa: F401

from app.core.settings import get_guardrails, get_settings


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    scopes: frozenset[str]
    key_id: str


def _configured_keys() -> list[tuple[str, str, frozenset[str]]]:
    settings = get_settings()
    tenant = settings.tenant_id
    allowed = set(get_guardrails().get("security.scopes"))
    return [
        (hashlib.sha256(_development_key(scope, settings.secret_key).encode()).hexdigest(), tenant, frozenset({scope}))
        for scope in sorted(allowed)
    ]


def _development_key(scope: str, secret_key: str | None = None) -> str:
    secret = secret_key if secret_key is not None else get_settings().secret_key
    return hmac.new(secret.encode(), scope.encode(), hashlib.sha256).hexdigest()


def authenticate(authorization: str | None) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, {"error": {"code": "unauthenticated", "message": "authentication required"}})
    presented = authorization[7:].encode()
    digest = hashlib.sha256(presented).hexdigest()
    for index, (expected, tenant, scopes) in enumerate(_configured_keys()):
        if hmac.compare_digest(digest, expected):
            return Principal(tenant, scopes, f"key-{index}")
    raise HTTPException(401, {"error": {"code": "unauthenticated", "message": "invalid credentials"}})


def require_scope(scope: str):
    configured = set(get_guardrails().get("security.scopes"))
    if scope not in configured:
        raise RuntimeError(f"scope is not configured: {scope}")

    def dependency(authorization: str | None = Header(default=None)) -> Principal:
        principal = authenticate(authorization)
        if scope not in principal.scopes:
            raise HTTPException(403, {"error": {"code": "scope_denied", "message": "scope denied"}})
        return principal

    return dependency
