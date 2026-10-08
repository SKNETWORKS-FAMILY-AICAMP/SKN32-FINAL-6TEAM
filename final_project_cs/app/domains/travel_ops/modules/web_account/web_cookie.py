# -*- coding: utf-8 -*-
"""웹 브라우저 세션(HttpOnly 쿠키) — 저장 · 수명 · CSRF · 「누구인지」 가르기. `[2026-10-04 사용자 결정]` D-CS-011 · 마이그레이션 044

계약 `wiki/external/rest-endpoints.md` 「브라우저 세션 쿠키」. 이 파일이 `/v1/web/*` 의 **사용자 확인을 한 곳에서** 한다(`authenticate`) — 쿠키 세션과 옛 키(`X-User-Key`, 에이전트용)를 함께 받는다.

★지키는 것
  - 쿠키 값은 무작위 256비트 — 서버에는 **SHA-256 해시만**. 브라우저의 스크립트는 읽지 못한다(HttpOnly).
  - 쿠키와 키가 **같이 오면 거부**한다(`ambiguous_credentials`) — 어느 쪽 사용자로 볼지 조용히 고르지 않는다.
  - 만료 시각은 **저장하지 않고 쓸 때 계산**한다(`web.*` 설정 — 관리 콘솔이 바꾼 값이 곧 적용). 게스트 · 회원(소셜 계정이 붙은 사용자)의 유휴 수명이 다르다.
  - 쿠키로 인증된 **쓰기** 요청은 `Origin` 허용 목록 + 세션에 묶인 `X-CSRF-Token`(저장하지 않고 HMAC 으로 다시 계산)을 모두 통과해야 한다. 읽기는 면제.
  - 만료·거둠·모름은 모두 같은 401(어느 쪽인지 알려 주지 않는다) — 쿠키가 왔다면 지우라는 머리말을 함께 보낸다.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

import app.core.settings as settings_module
from app.core.settings import get_guardrails
from app.infrastructure.db.session import get_connection

from app.domains.travel_ops.modules.web_account import web_agent_keys
from app.domains.travel_ops.modules.web_account import web_guard
from app.domains.travel_ops.modules.web_account.web_session import resolve as resolve_key

#: 운영(공개 주소가 https)이면 `__Host-` 접두 — `Secure` · `Path=/` · `Domain` 없음이어야 브라우저가 받는다. 개발(http)은 접두 없이.
SECURE_COOKIE = "__Host-tripilot_sid"
PLAIN_COOKIE = "tripilot_sid_dev"
CSRF_HEADER = "x-csrf-token"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
#: ★`[2026-10-04 D-CS-012]` 에이전트 키로는 **계정 관리 경로를 못 연다** — 로그인 · 연동 · 키 만들기 · 연락처는 브라우저 로그인에서만
AGENT_FORBIDDEN_PREFIXES = ("/v1/web/auth", "/v1/web/session", "/v1/web/profile", "/v1/web/agent-keys", "/v1/web/consents")
#: 쿠키 원문 길이 상한(`token_urlsafe(32)` = 43자) — 터무니없이 긴 값은 해시하지 않고 버린다
MAX_COOKIE_CHARS = 200


def refuse(status: int, code: str, message: str, *, headers: dict[str, str] | None = None, **extra: Any) -> HTTPException:
    return HTTPException(status, {"error": {"code": code, "message": message, **extra}}, headers=headers)


# ── 쿠키 속성 ───────────────────────────────────────────────────
def cookie_secure() -> bool:
    return settings_module.get_settings().public_base_url.strip().lower().startswith("https://")


def cookie_name() -> str:
    return SECURE_COOKIE if cookie_secure() else PLAIN_COOKIE


def _attrs(*, max_age: int | None) -> str:
    """`max_age` 가 None 이면 `Max-Age` 를 안 붙인다 — **브라우저 세션 쿠키**(브라우저를 닫으면 브라우저가 지운다)."""
    age = "" if max_age is None else f"Max-Age={max_age}; "
    return f"{age}Path=/; HttpOnly; SameSite=Lax" + ("; Secure" if cookie_secure() else "")


def cookie_header(raw: str, *, tenant_id: str, persistent: bool = True) -> str:
    """`Set-Cookie` 한 줄. `persistent` 면 절대 수명이 쿠키 수명이다(유휴 수명은 서버가 쓸 때 본다). `Domain` 은 붙이지 않는다.
    ★`[2026-10-04 사용자 결정]` **게스트(로그인 안 한 사용자)의 쿠키는 `persistent=False`** — 브라우저를 닫으면 사라진다(ChatGPT 로그아웃 상태와 같은 모양).
      게스트가 구글 계정을 `link` 하는 순간 같은 값을 `persistent=True` 로 다시 내려 오래가게 한다."""
    max_age = int(web_guard.values(tenant_id)["web.session_max_hours"]) * 3600 if persistent else None
    return f"{cookie_name()}={raw}; {_attrs(max_age=max_age)}"


def clear_header() -> str:
    return f"{cookie_name()}=; {_attrs(max_age=0)}"


# ── 저장 ────────────────────────────────────────────────────────
def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def csrf_token(session_hash: str) -> str:
    """세션에 묶인 CSRF 토큰 — 저장하지 않고 다시 계산한다."""
    key = settings_module.get_settings().secret_key.encode("utf-8")
    return hmac.new(key, f"csrf|{session_hash}".encode("utf-8"), hashlib.sha256).hexdigest()


def create(conn, *, tenant_id: str, customer_id: UUID) -> str:
    """새 세션 — ★원문은 여기서만 나온다(쿠키로만 간다)."""
    raw = secrets.token_urlsafe(32)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO web_sessions (session_hash, tenant_id, customer_id) VALUES (%s,%s,%s)",
                    (_hash(raw), tenant_id, customer_id))
    return raw


def revoke(conn, *, tenant_id: str, raw: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("UPDATE web_sessions SET revoked_at=now() WHERE tenant_id=%s AND session_hash=%s AND revoked_at IS NULL",
                    (tenant_id, _hash(raw)))
        return cur.rowcount > 0


def revoke_all(conn, *, tenant_id: str, customer_id: UUID) -> int:
    with conn.cursor() as cur:
        cur.execute("UPDATE web_sessions SET revoked_at=now() WHERE tenant_id=%s AND customer_id=%s AND revoked_at IS NULL",
                    (tenant_id, customer_id))
        return cur.rowcount


@dataclass(frozen=True)
class Session:
    customer_id: UUID
    session_hash: str
    kind: Literal["guest", "member"]
    idle_expires_at: datetime
    absolute_expires_at: datetime

    @property
    def csrf(self) -> str:
        return csrf_token(self.session_hash)


def lookup(conn, *, tenant_id: str, raw: str | None) -> Session | None:
    """쿠키 → 세션. 모르거나 거뒀거나 **만료**면 None. ★만료된 행은 이때 거둔다. 마지막 사용은 `web.session_touch_seconds` 보다 잦게 쓰지 않는다."""
    if not raw or len(raw) > MAX_COOKIE_CHARS:
        return None
    digest = _hash(raw)
    limits = web_guard.values(tenant_id)
    with conn.cursor() as cur:
        cur.execute("SELECT s.customer_id, s.created_at, s.last_used_at, now(), "
                    "EXISTS (SELECT 1 FROM web_social_links l WHERE l.tenant_id=s.tenant_id AND l.customer_id=s.customer_id) "
                    "FROM web_sessions s WHERE s.tenant_id=%s AND s.session_hash=%s AND s.revoked_at IS NULL",
                    (tenant_id, digest))
        row = cur.fetchone()
        if row is None:
            return None
        customer, created, last, now, member = row
        kind: Literal["guest", "member"] = "member" if member else "guest"
        idle = timedelta(hours=int(limits["web.member_idle_hours" if member else "web.guest_idle_hours"]))
        idle_expires, absolute_expires = last + idle, created + timedelta(hours=int(limits["web.session_max_hours"]))
        if now >= idle_expires or now >= absolute_expires:
            cur.execute("UPDATE web_sessions SET revoked_at=now() WHERE session_hash=%s AND revoked_at IS NULL", (digest,))
            return None
        if (now - last).total_seconds() >= float(get_guardrails().get("web_guard.session_touch_seconds")):
            cur.execute("UPDATE web_sessions SET last_used_at=now() WHERE session_hash=%s", (digest,))
            idle_expires = now + idle
    return Session(customer_id=customer, session_hash=digest, kind=kind,
                   idle_expires_at=idle_expires, absolute_expires_at=absolute_expires)


# ── 누구인지 가르기 ────────────────────────────────────────────
@dataclass(frozen=True)
class Identity:
    tenant_id: str
    customer_id: UUID
    via: Literal["cookie", "key", "agent"]
    session: Session | None = None
    scope: str | None = None                 # 에이전트 키의 권한 범위(read · write)
    key_id: UUID | None = None


def _allowed_origins() -> set[str]:
    settings = settings_module.get_settings()
    found = {o.strip().rstrip("/") for o in settings.web_allowed_origins.split(",") if o.strip()}
    if (settings.web_origin or "").strip():
        found.add(settings.web_origin.strip().rstrip("/"))
    return found


def _check_csrf(request: Request, session: Session) -> None:
    """쿠키로 인증된 쓰기 요청 — `Origin`(없으면 `Sec-Fetch-Site`)과 `X-CSRF-Token` 을 **둘 다** 본다."""
    origin = (request.headers.get("origin") or "").strip().rstrip("/")
    if origin:
        origin_ok = origin in _allowed_origins()
    else:
        origin_ok = (request.headers.get("sec-fetch-site") or "").lower() in ("same-origin", "same-site")
    provided = request.headers.get(CSRF_HEADER) or ""
    token_ok = bool(provided) and hmac.compare_digest(provided, session.csrf)
    if not (origin_ok and token_ok):
        raise refuse(403, "csrf_failed", "요청을 확인하지 못했다 — 화면을 새로 고친 뒤 다시 한다")


def _presented_key(request: Request) -> str | None:
    """`X-User-Key`, 없으면 `Authorization: Bearer <우리 키>`. ★우리 키 접두어(`acop_a_` · `acop_u_`)가 아니면 무시한다 — 서버용 scope 키를 Bearer 로 보내도 웹 경로는 안 열린다."""
    raw = (request.headers.get("x-user-key") or "").strip()
    if raw:
        return raw
    auth = (request.headers.get("authorization") or "").strip()
    if auth[:7].lower() == "bearer ":
        token = auth[7:].strip()
        if token.startswith((web_agent_keys.PREFIX, "acop_u_")):
            return token
    return None


def _check_agent(request: Request, agent: web_agent_keys.AgentKey) -> None:
    """에이전트 키의 권한 — 계정 관리 경로는 막고, `read` 키는 쓰기를 막는다."""
    path = request.url.path
    if any(path == prefix or path.startswith(prefix + "/") for prefix in AGENT_FORBIDDEN_PREFIXES):
        raise refuse(403, "agent_forbidden", "에이전트 키로는 계정 관리를 할 수 없다 — 브라우저에서 로그인해서 한다")
    if request.method.upper() in UNSAFE_METHODS and agent.scope != "write":
        raise refuse(403, "agent_scope", "이 키는 읽기 전용이다 — 쓰기 권한으로 만든 키가 필요하다")


def authenticate(request: Request, *, required: bool = True, csrf: bool = True) -> Identity | None:
    """누구인지 가린 뒤(`_identify`) **약관 동의 게이트**(`consents.gate_check`)를 건다 — `[2026-10-05]` 설정 `consent.gate_enabled` 가 켜져 있고 이 길이 면제(동의 · 로그인 · 세션 만들기)가 아니면,
    필수 동의가 지금 약관 버전으로 없는 사용자는 403 `consent_required`. 게스트 · 회원 · 옛 키 · 에이전트 키(키 주인의 동의) 모두 같다. 꺼져 있으면(기본) 아무것도 안 바뀐다."""
    identity = _identify(request, required=required, csrf=csrf)
    if identity is not None:
        _consent_gate(request, identity)
    return identity


def _consent_gate(request: Request, identity: Identity) -> None:
    from app.domains.travel_ops.components.customer import consents

    if not consents.gate_enabled():
        return
    try:
        with get_connection() as conn:
            consents.gate_check(conn, tenant_id=identity.tenant_id, user_id=identity.customer_id, path=request.url.path)
    except consents.ConsentError as refused:
        raise refuse(refused.status, refused.code, refused.message, **refused.extra) from None


def _identify(request: Request, *, required: bool = True, csrf: bool = True) -> Identity | None:
    """① 쿠키와 키가 같이 오면 400 `ambiguous_credentials` ② 쿠키만 → 세션(만료·거둠·모름 = 401 + 쿠키 지우기, 쓰기는 CSRF) ③ 키만 → 지금까지처럼(CSRF 면제)
    ④ 둘 다 없음 → 401. `required=False`(로그인 시작처럼 인증 없이도 되는 자리)이면 ④와 무효 자격은 None — **단 ①은 그래도 거부**한다."""
    tenant = settings_module.get_settings().tenant_id
    raw_cookie = request.cookies.get(cookie_name())
    raw_key = _presented_key(request)
    if raw_cookie and raw_key:
        raise refuse(400, "ambiguous_credentials", "쿠키와 사용자 키가 함께 왔다 — 하나만 보낸다")
    if raw_cookie:
        with get_connection() as conn, conn.transaction():
            session = lookup(conn, tenant_id=tenant, raw=raw_cookie)
        if session is None:
            if not required:
                return None
            raise refuse(401, "unauthenticated", "로그인 상태가 없거나 끝났다", headers={"Set-Cookie": clear_header()})
        if csrf and request.method.upper() in UNSAFE_METHODS:
            _check_csrf(request, session)
        return Identity(tenant, session.customer_id, "cookie", session)
    if raw_key and raw_key.startswith(web_agent_keys.PREFIX):                         # 에이전트 키 — 만료 · 폐기 · 권한 범위
        with get_connection() as conn, conn.transaction():
            agent = web_agent_keys.resolve(conn, tenant_id=tenant, raw=raw_key)
        if agent is None:
            if not required:
                return None
            raise refuse(401, "unauthenticated", "사용자 키가 없거나 맞지 않는다")
        _check_agent(request, agent)
        return Identity(tenant, agent.customer_id, "agent", None, agent.scope, agent.key_id)
    with get_connection() as conn, conn.transaction():
        customer = resolve_key(conn, tenant_id=tenant, raw=raw_key)
    if customer is None:
        if not required:
            return None
        raise refuse(401, "unauthenticated", "사용자 키가 없거나 맞지 않는다")
    return Identity(tenant, customer, "key")


def require_identity(request: Request) -> Identity:
    """FastAPI 의존성 — 쿠키 세션 또는 키로 확인한 사용자(없으면 401). 정적 검사(`tests/integration/api/test_openapi_surface.py`)가 이 이름으로 「인증 있는 쓰기 경로」를 알아본다."""
    identity = authenticate(request)
    assert identity is not None
    return identity


# ── 응답 ────────────────────────────────────────────────────────
def session_body(session: Session, *, tenant_id: str, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"kind": session.kind, "csrf_token": session.csrf,
                            "idle_expires_at": session.idle_expires_at.isoformat(),
                            "absolute_expires_at": session.absolute_expires_at.isoformat(), **extra}
    if session.kind == "guest":
        body["guest_idle_hours"] = int(web_guard.values(tenant_id)["web.guest_idle_hours"])
    return body


def start(conn, *, tenant_id: str, customer_id: UUID) -> tuple[str, Session]:
    """세션을 만들고 곧바로 읽어 온다 — (쿠키 원문, 세션)."""
    raw = create(conn, tenant_id=tenant_id, customer_id=customer_id)
    session = lookup(conn, tenant_id=tenant_id, raw=raw)
    assert session is not None
    return raw, session


def json_with_cookie(body: dict[str, Any], *, raw: str, tenant_id: str, status: int = 200, persistent: bool = True) -> JSONResponse:
    return JSONResponse(body, status_code=status, headers={"Set-Cookie": cookie_header(raw, tenant_id=tenant_id, persistent=persistent),
                                                           "Cache-Control": "no-store"})


__all__ = ["CSRF_HEADER", "Identity", "Session", "authenticate", "clear_header", "cookie_header", "cookie_name",
           "cookie_secure", "create", "csrf_token", "json_with_cookie", "lookup", "refuse", "require_identity", "revoke",
           "revoke_all", "session_body", "start"]
