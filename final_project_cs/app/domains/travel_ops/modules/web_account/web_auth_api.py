# -*- coding: utf-8 -*-
"""웹 소셜 로그인 HTTP — 계약은 `wiki/records/plans/2026-10-03_1930_소셜_로그인_백엔드_요청.md`(웹 화면은 이 모양 그대로 이미 연결돼 있다). `[2026-10-03]`

    GET    /v1/web/auth/providers              설정이 끝난 업체만(없으면 빈 목록 — 404 가 아니다)
    POST   /v1/web/auth/{provider}/start       로그인 · 연결 시작 → {authorize_url}
    GET    /v1/web/auth/{provider}/callback    업체가 브라우저를 돌려보내는 곳 → 웹으로 302 (`…/auth/done?ticket=` 또는 `?error=`)
    POST   /v1/web/auth/exchange               일회용 표 → 결과 + (로그인이면) 이 기기용 새 키
    GET    /v1/web/auth/links                  이 키에 붙은 업체
    DELETE /v1/web/auth/{provider}             연결 해제 → 남은 연결

★`web_auth.py`(저장 · 규칙) · `infrastructure/oauth_providers.py`(업체와 말하기). 이 파일은 요청 → 위 둘 → 응답만 잇는다.
★돌려보낼 웹 주소(`web_origin`)는 서버 설정이고 요청 값으로 바꿀 수 없다(열린 리디렉션 금지). `return_to` 는 받지 않는다.
★키가 담긴 응답(`exchange`)과 표가 담긴 주소(`callback` 302)는 저장 · 추천 · 리퍼러 전달을 막는 머리말을 단다.
"""
from __future__ import annotations

from typing import Any, Callable, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

import app.core.settings as settings_module
from app.core.settings import get_guardrails
from app.infrastructure import oauth_providers as oauth
from app.infrastructure.db.session import get_connection

from app.domains.travel_ops.modules.web_account import web_agent_keys
from app.domains.travel_ops.modules.web_account import web_auth
from app.domains.travel_ops.modules.web_account import web_cookie
from app.domains.travel_ops.modules.web_account import web_guard
from app.domains.travel_ops.modules.web_account.web_agent_keys_api import build_agent_keys_router
from app.domains.travel_ops.modules.web_account.consents_api import build_consents_router
from app.domains.travel_ops.modules.web_account.retention_api import build_public_retention_router
from app.domains.travel_ops.modules.web_account.web_session import add_key, new_customer

#: 콜백이 웹으로 돌려보낼 때 쓰는 오류 코드(요청서) — 이 밖의 이유는 전부 `failed`
CALLBACK_ERRORS = ("cancelled", "denied", "already_linked_elsewhere", "failed")


def _error(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status, {"error": {"code": code, "message": message, **extra}})


class AuthStartIn(BaseModel):
    mode: Literal["login", "link"]
    client_nonce: str
    turnstile_token: str | None = None


class AuthExchangeIn(BaseModel):
    ticket: str
    client_nonce: str
    #: `cookie` 면 `signed_in` · `created` 일 때 키 대신 **쿠키 세션**을 준다(D-CS-011). 기본 `key` = 지금까지처럼 `user_key`
    session: Literal["cookie", "key"] = "key"


class SessionIn(BaseModel):
    turnstile_token: str | None = None


def build_auth_router(*, exchange: oauth.Exchanger | None = None, human_verify: Callable[..., dict[str, Any]] | None = None) -> APIRouter:
    """`exchange` — 코드를 사용자 고유 번호로 바꾸는 것(시험이 가짜 업체를 꽂는다). 없으면 업체에 실제로 묻는다.
    `human_verify` — 사람 확인(Turnstile)을 갈아 끼우는 자리(시험)."""
    router = APIRouter()
    router.include_router(build_agent_keys_router())        # `[2026-10-04 D-CS-012]` 에이전트 키(쿠키 로그인한 회원만)
    router.include_router(build_consents_router())          # `[2026-10-05]` 약관 동의 기록 · 사용 조건(게이트는 `web_cookie.authenticate`)
    router.include_router(build_public_retention_router())  # `[2026-10-07]` 약관 보관 기간 공개 읽기(키 없음 · 개인 정보 없음)

    def _tenant() -> str:
        return settings_module.get_settings().tenant_id

    def _providers() -> dict[str, oauth.Provider]:
        return oauth.configured(settings_module.get_settings())

    def _ip(http: Request) -> str:
        return web_guard.client_ip(http.client.host if http.client else None, http.headers.get("x-forwarded-for"))

    def _web_origin() -> str:
        settings = settings_module.get_settings()
        origin = (settings.web_origin or "").strip()
        if not origin:
            origin = next((o.strip() for o in settings.web_allowed_origins.split(",") if o.strip()), "")
        return origin.rstrip("/")

    def _redirect_uri(provider: str) -> str:
        return f"{settings_module.get_settings().public_base_url.rstrip('/')}/v1/web/auth/{provider}/callback"

    def _count(action: str, http: Request) -> None:
        """로그인 시작 · 표 교환을 주소당 한 시간에 몇 번까지만 — 남용을 막는다(늘 켜져 있다)."""
        try:
            web_guard.count_auth(_tenant(), action, ip=_ip(http))
        except web_guard.UsageRefused as refused:
            error = _error(429, "too_many_auth", "로그인을 너무 자주 시도했다 — 잠시 뒤에 다시 한다",
                           retry_after_seconds=refused.retry_after)
            error.headers = {"Retry-After": str(refused.retry_after)}
            raise error from None

    def _customer(http: Request) -> UUID:
        """쿠키 세션 또는 키로 확인한 사용자 — 없으면 401. ★쿠키로 인증된 쓰기(`link` 시작 · 연결 해제)는 Origin + CSRF 를 거친다."""
        return web_cookie.authenticate(http).customer_id

    def _human(token: str | None, http: Request) -> None:
        """키 없이 시작하는 로그인은 새 사용자를 만들 수 있다 — 사람 확인을 요구한다. 토큰이 없으면 422 `human_check_required`(화면이 확인을 띄우고 다시 부른다)."""
        try:
            web_guard.human_check(token, ip=_ip(http), verify=human_verify)
        except web_guard.HumanCheckFailed as exc:
            if "missing-input-response" in exc.reasons:
                raise _error(422, "human_check_required", "사람 확인이 필요하다 — 화면에서 확인한 뒤 다시 한다") from None
            raise _error(403, "human_check_failed", "사람 확인을 통과하지 못했다 — 화면에서 다시 확인한다", reasons=exc.reasons) from None
        except web_guard.HumanCheckUnavailable:
            error = _error(503, "human_check_unavailable", "지금은 사람 확인을 할 수 없다 — 잠시 뒤 다시 한다", retry_after_seconds=30)
            error.headers = {"Retry-After": "30"}
            raise error from None

    def _done(origin: str, **query: str) -> RedirectResponse:
        """웹의 마무리 화면으로 302. ★표가 주소에 실리므로 리퍼러로 새지 않게 하고 저장하지 않게 한다."""
        suffix = "&".join(f"{key}={quote(value, safe='')}" for key, value in query.items())
        return RedirectResponse(f"{origin}/auth/done?{suffix}", status_code=302,
                                headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

    @router.get("/v1/web/auth/providers")
    def auth_providers():
        """서버에 **설정이 끝난 업체만**. 하나도 없으면 빈 목록(웹이 「설정된 로그인 방법이 없어요」라고 말한다)."""
        return {"providers": [{"id": provider_id} for provider_id in _providers()]}

    @router.post("/v1/web/auth/exchange")
    def auth_exchange(http: Request, body: AuthExchangeIn):
        """일회용 표 → 결과. `signed_in` · `created` 이면 **이 기기용 새 키**(다른 기기의 키는 그대로), `linked` 면 키를 바꾸지 않는다.
        만료 · 재사용 · nonce 불일치는 모두 410 `ticket_invalid` — 어느 쪽인지 가르지 않는다."""
        _count("auth_exchange", http)
        if not web_auth.valid_client_nonce(body.client_nonce) or not body.ticket or len(body.ticket) > 200:
            raise _error(410, "ticket_invalid", "이 로그인 표를 쓸 수 없다 — 처음부터 다시 한다")
        tenant = _tenant()
        with get_connection() as conn, conn.transaction():
            got = web_auth.exchange(conn, tenant_id=tenant, ticket=body.ticket, client_nonce=body.client_nonce)
            if got is None:
                raise _error(410, "ticket_invalid", "이 로그인 표를 쓸 수 없다 — 처음부터 다시 한다")
            out: dict[str, Any] = {"outcome": got["outcome"], "provider": got["provider"],
                                   "trips": web_auth.trip_count(conn, tenant_id=tenant, customer_id=got["customer_id"])}
            if got["outcome"] == "linked" and body.session == "cookie":
                # ★게스트가 구글 계정을 연결했다 — 같은 세션이 이제 회원이다. 브라우저 세션 쿠키였던 같은 값을 **오래가는 쿠키로 다시** 내린다(안 그러면 창을 닫을 때 회원 세션도 사라진다)
                existing = http.cookies.get(web_cookie.cookie_name())
                session = web_cookie.lookup(conn, tenant_id=tenant, raw=existing)
                if session is not None and session.customer_id == got["customer_id"]:
                    out.update(web_cookie.session_body(session, tenant_id=tenant))
                    return web_cookie.json_with_cookie(out, raw=existing, tenant_id=tenant, persistent=True)
            if got["outcome"] in ("signed_in", "created") and body.session == "cookie":
                # ★로그인하는 순간 **세션을 새로 만든다**(세션 고정 공격 방지) — 요청에 딸려 온 옛 쿠키(게스트 세션)는 거둔다. 키는 안 준다
                old = http.cookies.get(web_cookie.cookie_name())
                if old:
                    web_cookie.revoke(conn, tenant_id=tenant, raw=old)
                raw, session = web_cookie.start(conn, tenant_id=tenant, customer_id=got["customer_id"])
                out.update(web_cookie.session_body(session, tenant_id=tenant))
                return web_cookie.json_with_cookie(out, raw=raw, tenant_id=tenant)
            if got["outcome"] in ("signed_in", "created"):
                out["user_key"] = add_key(conn, tenant_id=tenant, customer_id=got["customer_id"],
                                          keep=int(get_guardrails().get("security.web_auth_keys_per_user")))
                out["notice"] = ("이 기기에서 쓸 새 키예요. 다른 기기의 키는 그대로예요 — 이 키도 따로 잘 보관해 주세요."
                                 if got["outcome"] == "signed_in"
                                 else "새 사용자를 만들었어요. 이 기기에서 쓸 키예요 — 따로 잘 보관해 주세요.")
        return JSONResponse(out, headers={"Cache-Control": "no-store"})

    # ── 브라우저 세션(쿠키) — D-CS-011 ───────────────────────────────────────────────
    @router.post("/v1/web/auth/session")
    def auth_session(http: Request, x_turnstile_token: str | None = Header(default=None),
                     body: SessionIn | None = Body(default=None)):
        """게스트 세션 — 쿠키를 내려준다. ★이미 유효한 쿠키가 있으면 새로 안 만들고 현재 세션을 돌려준다. 사람 확인 · 주소당 한 시간 발급 한도는 `POST /v1/web/session` 과 같다."""
        tenant = _tenant()
        current = web_cookie.authenticate(http, required=False, csrf=False)
        if current is not None and current.session is not None:
            return JSONResponse(web_cookie.session_body(current.session, tenant_id=tenant), headers={"Cache-Control": "no-store"})
        if current is not None:                                  # 키만 온 호출 — 쿠키로 옮기려면 `adopt` 다
            raise _error(409, "use_adopt", "이미 사용자 키가 있다 — `/v1/web/auth/adopt` 로 쿠키로 옮긴다")
        _human((body.turnstile_token if body else None) or x_turnstile_token, http)
        try:
            web_guard.count_session(tenant, ip=_ip(http))
        except web_guard.UsageRefused as refused:
            error = _error(429, "too_many_sessions", "새 세션을 너무 많이 받았다 — 잠시 뒤에 다시 한다",
                           retry_after_seconds=refused.retry_after)
            error.headers = {"Retry-After": str(refused.retry_after)}
            raise error from None
        with get_connection() as conn, conn.transaction():
            raw, session = web_cookie.start(conn, tenant_id=tenant, customer_id=new_customer(conn, tenant_id=tenant))
        return web_cookie.json_with_cookie(web_cookie.session_body(session, tenant_id=tenant), raw=raw, tenant_id=tenant, status=201,
                                           persistent=False)       # ★게스트 쿠키는 브라우저를 닫으면 사라진다(D-CS-011 정정 2026-10-04)

    @router.post("/v1/web/auth/adopt")
    def auth_adopt(http: Request):
        """옛 키 사용자를 **쿠키 세션으로 옮긴다**(키는 거두지 않는다 — 에이전트가 쓸 수 있다). 웹은 성공하면 저장소의 키를 지운다."""
        tenant = _tenant()
        _count("auth_adopt", http)
        who = web_cookie.authenticate(http, csrf=False)           # 둘 다 오면 400, 키가 틀리면 401
        if who.session is not None:                               # 이미 쿠키 세션이다 — 옮길 것이 없다
            return JSONResponse(web_cookie.session_body(who.session, tenant_id=tenant), headers={"Cache-Control": "no-store"})
        with get_connection() as conn, conn.transaction():
            raw, session = web_cookie.start(conn, tenant_id=tenant, customer_id=who.customer_id)
        return web_cookie.json_with_cookie(web_cookie.session_body(session, tenant_id=tenant), raw=raw, tenant_id=tenant, status=201,
                                           persistent=session.kind == "member")

    @router.get("/v1/web/auth/me")
    def auth_me(who: web_cookie.Identity = Depends(web_cookie.require_identity)):
        if who.session is None:                                   # 키로 부른 호출 — 세션이 아니다
            return JSONResponse({"kind": "key"}, headers={"Cache-Control": "no-store"})
        return JSONResponse(web_cookie.session_body(who.session, tenant_id=who.tenant_id), headers={"Cache-Control": "no-store"})

    @router.post("/v1/web/auth/logout")
    def auth_logout(http: Request, who: web_cookie.Identity = Depends(web_cookie.require_identity)):
        """서버의 세션 행을 거두고 쿠키를 지운다. ★게스트가 로그아웃하면 그 여행은 다시 열 수 없다(보존 시간이 지나면 지워진다). 쿠키로는 CSRF 까지 본다(의존성)."""
        if who.session is None:
            raise _error(400, "no_cookie_session", "쿠키 세션으로 부른 호출만 로그아웃한다")
        raw = http.cookies.get(web_cookie.cookie_name())
        with get_connection() as conn, conn.transaction():
            web_cookie.revoke(conn, tenant_id=who.tenant_id, raw=raw or "")
        return JSONResponse({"status": "signed_out"}, headers={"Set-Cookie": web_cookie.clear_header(), "Cache-Control": "no-store"})

    @router.get("/v1/web/auth/links")
    def auth_links(who: web_cookie.Identity = Depends(web_cookie.require_identity)):
        with get_connection() as conn:
            return {"links": web_auth.links(conn, tenant_id=_tenant(), customer_id=who.customer_id)}

    @router.post("/v1/web/auth/{provider}/start")
    def auth_start(provider: str, http: Request, body: AuthStartIn = Body(...),
                   x_turnstile_token: str | None = Header(default=None)):
        spec = _providers().get(provider)
        if spec is None:
            raise _error(404, "provider_not_enabled", "이 로그인 방법은 아직 쓸 수 없다")
        if not web_auth.valid_client_nonce(body.client_nonce):
            raise _error(422, "invalid_client_nonce", f"client_nonce 는 무작위 {web_auth.MIN_CLIENT_NONCE}자 이상이어야 한다")
        _count("auth_start", http)
        customer: UUID | None = None
        if body.mode == "link":
            customer = _customer(http)                          # 연결은 로그인 상태(쿠키 세션 또는 키)가 있어야 한다(없으면 401 `unauthenticated`)
        else:
            # 로그인 시작은 인증 없이도 열린다 — 이미 로그인 상태가 있으면 사람 확인을 건너뛴다(CSRF 는 이 자리에서 안 본다: 상태를 안 바꾼다)
            if web_cookie.authenticate(http, required=False, csrf=False) is None:
                _human(body.turnstile_token or x_turnstile_token, http)
        verifier = oauth.new_verifier()
        with get_connection() as conn, conn.transaction():
            state, nonce = web_auth.begin(conn, tenant_id=_tenant(), provider=provider, mode=body.mode, customer_id=customer,
                                          client_nonce=body.client_nonce, verifier=verifier)
        return JSONResponse({"authorize_url": oauth.authorize_url(spec, redirect_uri=_redirect_uri(provider), state=state,
                                                                   nonce=nonce, verifier=verifier)},
                            headers={"Cache-Control": "no-store"})

    @router.get("/v1/web/auth/{provider}/callback")
    def auth_callback(provider: str, http: Request, code: str | None = Query(default=None), state: str | None = Query(default=None),
                      error: str | None = Query(default=None)):
        """업체가 브라우저를 돌려보내는 곳. 어떤 실패든 **웹으로 302 + `?error=`** 다(브라우저 이동이라 JSON 오류를 못 읽는다)."""
        origin = _web_origin()
        if not origin:
            raise _error(503, "web_origin_not_configured", "로그인 뒤 돌아갈 웹 주소가 설정되지 않았다")
        tenant = _tenant()
        started = None
        if state:
            with get_connection() as conn, conn.transaction():
                started = web_auth.take_state(conn, tenant_id=tenant, state=state)        # ★한 번만 — 여기서 쓴 것으로 친다
        spec = _providers().get(provider)
        if started is None or spec is None or started["provider"] != provider:
            return _done(origin, error="failed")
        if error:
            return _done(origin, error="cancelled" if error == "access_denied" else "denied")
        if not code:
            return _done(origin, error="failed")
        try:
            subject = (exchange or oauth.exchange_code)(spec, code=code, verifier=started["verifier"],
                                                        redirect_uri=_redirect_uri(provider), nonce=started["nonce"])
        except oauth.OAuthError:
            return _done(origin, error="failed")

        def create_customer(conn):
            web_guard.count_session(tenant, ip=_ip(http))        # 새 사용자 한도(`too_many_sessions`)를 그대로 — 가입 폭주의 입구가 여기도 된다
            return new_customer(conn, tenant_id=tenant)

        try:
            with get_connection() as conn, conn.transaction():
                ticket, failure = web_auth.complete(conn, tenant_id=tenant, started=started, subject=subject,
                                                    create_customer=create_customer)
        except web_guard.UsageRefused:
            return _done(origin, error="failed")
        if failure is not None:
            return _done(origin, error=failure if failure in CALLBACK_ERRORS else "failed")
        return _done(origin, ticket=ticket or "")

    @router.delete("/v1/web/auth/{provider}")
    def auth_unlink(provider: str, who: web_cookie.Identity = Depends(web_cookie.require_identity)):
        """연결 해제 — 키와 여행은 그대로. 남은 연결을 돌려준다(웹의 호출 도우미가 본문 없는 204 를 못 읽는다)."""
        customer = who.customer_id
        tenant = _tenant()
        with get_connection() as conn, conn.transaction():
            if not web_auth.unlink(conn, tenant_id=tenant, customer_id=customer, provider=provider):
                raise _error(404, "not_linked", "이 로그인 방법은 연결돼 있지 않다")
            remaining = web_auth.links(conn, tenant_id=tenant, customer_id=customer)
            if not remaining:        # ★마지막 연결을 풀면 게스트가 된다 — 복구 불가능한 계정에 강한 에이전트 키만 남지 않게 거둔다(D-CS-012)
                web_agent_keys.revoke_all(conn, tenant_id=tenant, customer_id=customer)
            return {"links": remaining}

    return router


__all__ = ["CALLBACK_ERRORS", "build_auth_router"]
