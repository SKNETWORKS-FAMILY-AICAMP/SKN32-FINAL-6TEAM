"""SDK OAuth provider: 사전 등록·회원 동의·해시 저장·일회용 교환·갱신 순환."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import secrets
import time
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from mcp.server.auth.provider import (AccessToken, AuthorizationCode, AuthorizationParams,
                                     AuthorizeError, RefreshToken, TokenError, construct_redirect_uri)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core import settings as settings_module
from .personal_ai_store import PostgresStore

SCOPES = ("travel:read", "travel:write")
ACCESS_PREFIX = "acop_o_"


class Policy(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ACOP_PERSONAL_AI_OAUTH_", extra="ignore")
    code_seconds: int = Field(ge=30, le=300)
    consent_seconds: int = Field(ge=60, le=1800)
    access_seconds: int = Field(ge=60, le=3600)
    refresh_idle_seconds: int = Field(ge=3600, le=90 * 86400)
    refresh_max_seconds: int = Field(ge=3600, le=90 * 86400)

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        def policy_file():
            return json.loads((Path(__file__).resolve().parents[5] / "config/personal-ai-oauth.json").read_text(encoding="utf-8"))
        return init_settings, env_settings, policy_file


def digest(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def offload(fn):
    @wraps(fn)
    async def call(*args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)
    return call


class Provider:
    def __init__(self, tenant, public_base, *, store=None, policy=None, clock=time.time):
        self.tenant = tenant
        self.issuer = public_base.rstrip("/") + "/oauth"
        self.resource = public_base.rstrip("/") + "/mcp/"
        self.store = store or PostgresStore(tenant)
        self.policy, self.clock = policy or Policy(), clock

    def preregister(self, client_id, name, redirects, *, scopes=SCOPES):
        """배포자 전용 Python 접합부. 고객 HTTP 등록 경로는 제공하지 않는다."""
        if not client_id or not name or len(name) > 80 or not redirects or not set(scopes) <= set(SCOPES):
            raise ValueError("invalid client")
        for uri in redirects:
            parsed = urlsplit(uri)
            loopback = parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")
            if (parsed.scheme != "https" and not loopback) or not parsed.hostname or parsed.username or parsed.fragment:
                raise ValueError("invalid redirect")
        data = {"client_id": client_id, "client_name": name, "redirect_uris": list(redirects),
                "scope": " ".join(scopes), "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"]}
        OAuthClientInformationFull.model_validate(data)
        with self.store.transaction() as db:
            db.put("client", client_id, data)

    @offload
    def get_client(self, client_id):
        with self.store.transaction() as db:
            row = db.get("client", client_id)
        return OAuthClientInformationFull.model_validate(row) if row else None

    async def register_client(self, client_info):
        raise NotImplementedError("preregistration only")

    @offload
    def redirect_allowed(self, client_id, uri):
        with self.store.transaction() as db:
            registered = db.get("client", client_id)
            return bool(registered and uri in registered["redirect_uris"])

    @offload
    def authorize(self, client, params: AuthorizationParams):
        if params.resource != self.resource or not params.redirect_uri_provided_explicitly:
            raise AuthorizeError("invalid_request", "resource and explicit redirect_uri required")
        if not params.state or len(params.state) > 1024 or not re.fullmatch(r"[A-Za-z0-9_-]{43}", params.code_challenge):
            raise AuthorizeError("invalid_request", "state and S256 PKCE required")
        scopes = params.scopes or ["travel:read"]
        if not scopes or not set(scopes) <= set(SCOPES):
            raise AuthorizeError("invalid_scope")
        raw = secrets.token_urlsafe(32)
        with self.store.transaction() as db:
            db.put("pending", digest(raw), {**params.model_dump(mode="json"), "scopes": scopes,
                   "client_id": client.client_id, "expires": self.clock() + self.policy.consent_seconds})
        return self.issuer + "/consent?request=" + raw

    def consent(self, request_token, customer, session_hash, *, approve=None):
        """GET에서 로그인 세션에 결합, POST에서 같은 세션만 한 번 처리한다."""
        with self.store.transaction() as db:
            row = db.get("pending", digest(request_token))
            if not row or row.get("used") or row["expires"] <= self.clock() or not db.is_member(customer):
                raise ValueError("invalid consent")
            if row.get("session") and (row["session"] != session_hash or row["customer"] != str(customer)):
                raise ValueError("invalid consent")
            if approve is not None and not row.get("session"):
                raise ValueError("consent not displayed")
            row.update(customer=str(customer), session=session_hash)
            if approve is None:
                db.put("pending", digest(request_token), row)
                client = db.get("client", row["client_id"])
                return {"client_name": client["client_name"], "scopes": row["scopes"],
                        "expires_at": self.clock() + self.policy.refresh_max_seconds}
            row["used"] = True
            db.put("pending", digest(request_token), row)
            if not approve:
                return construct_redirect_uri(row["redirect_uri"], error="access_denied", state=row["state"], iss=self.issuer)
            now = self.clock()
            grant = secrets.token_urlsafe(24)
            db.put("grant", grant, {"customer": str(customer), "client_id": row["client_id"],
                   "scopes": row["scopes"], "resource": self.resource, "created": now,
                   "expires": now + self.policy.refresh_max_seconds, "revoked": False})
            code = secrets.token_urlsafe(32)
            db.put("code", digest(code), {**row, "grant": grant, "expires": now + self.policy.code_seconds, "used": False})
            return construct_redirect_uri(row["redirect_uri"], code=code, state=row["state"], iss=self.issuer)

    def _grant(self, db, row):
        grant = db.get("grant", row["grant"])
        if (not grant or grant["revoked"] or grant["expires"] <= self.clock()
                or grant["resource"] != self.resource or row["resource"] != self.resource
                or row["customer"] != grant["customer"] or row["client_id"] != grant["client_id"]
                or not set(row["scopes"]) <= set(grant["scopes"]) or not db.is_member(grant["customer"])):
            return None
        return grant

    @offload
    def load_authorization_code(self, client, authorization_code):
        with self.store.transaction() as db:
            row = db.get("code", digest(authorization_code))
            if not row or row["used"] or row["client_id"] != client.client_id or not self._grant(db, row):
                return None
            return AuthorizationCode(code=authorization_code, scopes=row["scopes"], expires_at=row["expires"],
                    client_id=row["client_id"], code_challenge=row["code_challenge"], redirect_uri=row["redirect_uri"],
                    redirect_uri_provided_explicitly=True, resource=row["resource"], subject=row["customer"])

    def _issue(self, db, grant_key, grant, scopes):
        now = self.clock()
        access, refresh = ACCESS_PREFIX + secrets.token_urlsafe(32), "acop_r_" + secrets.token_urlsafe(32)
        common = {"grant": grant_key, "customer": grant["customer"], "client_id": grant["client_id"],
                  "scopes": scopes, "resource": grant["resource"], "used": False}
        access_expiry = min(now + self.policy.access_seconds, grant["expires"])
        db.put("access", digest(access), {**common, "expires": access_expiry})
        db.put("refresh", digest(refresh), {**common, "access": digest(access),
               "expires": min(now + self.policy.refresh_idle_seconds, grant["expires"])})
        return OAuthToken(access_token=access, token_type="Bearer", expires_in=max(0, int(access_expiry - now)),
                          refresh_token=refresh, scope=" ".join(scopes))

    @offload
    def exchange_authorization_code(self, client, authorization_code):
        result = None
        with self.store.transaction() as db:
            row = db.get("code", digest(authorization_code.code))
            grant = self._grant(db, row) if row else None
            if row and not row["used"] and row["expires"] > self.clock() and row["client_id"] == client.client_id and grant:
                row["used"] = True
                db.put("code", digest(authorization_code.code), row)
                result = self._issue(db, row["grant"], grant, row["scopes"])
        # SDK TokenError는 frozen dataclass다. generator contextmanager를 통과시키지 않는다.
        if result is None:
            raise TokenError("invalid_grant")
        return result

    @offload
    def load_refresh_token(self, client, refresh_token):
        # SDK가 만료 검사로 먼저 거절하기 전에도 이미 쓴 refresh 재사용을 거둔다.
        with self.store.transaction() as db:
            row = db.get("refresh", digest(refresh_token))
            if not row or row["client_id"] != client.client_id or not self._grant(db, row):
                return None
            if row["used"]:
                grant = db.get("grant", row["grant"])
                grant.update(revoked=True, revoked_at=self.clock())
                db.put("grant", row["grant"], grant)
                return None
            return RefreshToken(token=refresh_token, client_id=client.client_id, scopes=row["scopes"],
                                expires_at=int(row["expires"]), subject=row["customer"])

    @offload
    def exchange_refresh_token(self, client, refresh_token, scopes):
        result = None
        with self.store.transaction() as db:
            row = db.get("refresh", digest(refresh_token.token))
            grant = self._grant(db, row) if row else None
            if row and grant and row["client_id"] == client.client_id:
                if row["used"]:
                    grant["revoked"] = True
                    grant["revoked_at"] = self.clock()
                    db.put("grant", row["grant"], grant)
                elif row["expires"] > self.clock() and scopes and set(scopes) <= set(row["scopes"]):
                    row["used"] = True
                    db.put("refresh", digest(refresh_token.token), row)
                    old = db.get("access", row["access"])
                    old["used"] = True
                    db.put("access", row["access"], old)
                    result = self._issue(db, row["grant"], grant, scopes)
        if result is None:
            raise TokenError("invalid_grant")
        return result

    def resolve(self, raw):
        if not raw.startswith(ACCESS_PREFIX) or len(raw) > 200:
            return None
        with self.store.transaction() as db:
            row = db.get("access", digest(raw))
            if not row or row["used"] or row["expires"] <= self.clock() or not self._grant(db, row):
                return None
            return AccessToken(token=raw, client_id=row["client_id"], scopes=row["scopes"],
                    expires_at=int(row["expires"]), resource=row["resource"], subject=row["customer"],
                    claims={"tenant": self.tenant, "grant": row["grant"]})

    @offload
    def load_access_token(self, token):
        return self.resolve(token)

    @offload
    def revoke_token(self, token):
        kind = "access" if isinstance(token, AccessToken) else "refresh"
        with self.store.transaction() as db:
            row = db.get(kind, digest(token.token))
            if row:
                grant = db.get("grant", row["grant"])
                if grant:
                    grant["revoked"] = True
                    grant["revoked_at"] = self.clock()
                    db.put("grant", row["grant"], grant)

    def connections(self, customer, grant_id=None):
        with self.store.transaction() as db:
            rows = db.list_grants(str(customer))
            if grant_id is not None:
                for key, row in rows:
                    if key == grant_id:
                        row["revoked"] = True
                        row["revoked_at"] = self.clock()
                        db.put("grant", key, row)
                        return True
                return False
            return [{"connection_id": key, "client_name": (db.get("client", row["client_id"]) or {}).get("client_name", ""),
                     "scopes": row["scopes"], "expires_at": row["expires"],
                     "status": "revoked" if row["revoked"] else "expired" if row["expires"] <= self.clock() else "active"}
                    for key, row in rows]


def configured_provider():
    settings = settings_module.get_settings()
    return Provider(settings.tenant_id, settings.public_base_url)
