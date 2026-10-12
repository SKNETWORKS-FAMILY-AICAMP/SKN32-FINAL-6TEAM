"""개인 AI OAuth HTTP 경계. 프로토콜 처리는 MCP SDK, 브라우저 동의는 기존 세션/CSRF."""
import asyncio
import html
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from mcp.server.auth.handlers.authorize import AuthorizationHandler
from mcp.server.auth.handlers.token import TokenHandler
from mcp.server.auth.handlers.revoke import RevocationHandler
from mcp.server.auth.middleware.client_auth import ClientAuthenticator
from mcp.server.auth.provider import construct_redirect_uri
from starlette.datastructures import FormData

from . import web_cookie, web_guard
from .personal_ai_oauth import SCOPES, configured_provider
from .personal_ai_views import document

NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer"}


def oauth_error(code="invalid_request", status=400):
    return JSONResponse({"error": code}, status_code=status, headers=NO_STORE)


def member(request, *, optional=False):
    who = web_cookie.authenticate(request, required=not optional)
    if who is None:
        return None
    if optional and who.via == "cookie" and who.session.kind == "guest":
        return None
    if who.via != "cookie" or who.session.kind != "member":
        raise HTTPException(403, {"error": {"code": "member_cookie_required", "message": "브라우저에서 로그인해 주세요."}})
    return who


def build_personal_ai_router(provider_factory=configured_provider):
    router = APIRouter()

    async def require_member(request: Request):
        return await asyncio.to_thread(member, request)

    def provider():
        return provider_factory()

    def count(request, action, tenant):
        ip = web_guard.client_ip(request.client.host if request.client else None, request.headers.get("x-forwarded-for"))
        try:
            # 기존의 동일한 인증 예산을 공유한다. 새 비용 한도를 만들지 않는다.
            budget = {"personal_ai_authorize": "auth_start", "personal_ai_token": "auth_exchange", "personal_ai_revoke": "auth_adopt"}[action]
            web_guard.count_auth(tenant, budget, ip=ip)
        except web_guard.UsageRefused as refused:
            raise HTTPException(429, "too_many_auth", headers={"Retry-After": str(refused.retry_after)}) from None

    @router.get("/.well-known/oauth-protected-resource/mcp")
    @router.get("/.well-known/oauth-protected-resource/mcp/")
    @router.get("/.well-known/oauth-protected-resource")
    def resource_metadata():
        p = provider()
        return JSONResponse({"resource": p.resource, "authorization_servers": [p.issuer],
                             "scopes_supported": ["travel:read"], "bearer_methods_supported": ["header"]}, headers=NO_STORE)

    @router.get("/.well-known/oauth-authorization-server/oauth")
    def authorization_metadata():
        p = provider()
        return JSONResponse({"issuer": p.issuer, "authorization_endpoint": p.issuer + "/authorize",
                  "token_endpoint": p.issuer + "/token", "revocation_endpoint": p.issuer + "/revoke",
                  "response_types_supported": ["code"], "grant_types_supported": ["authorization_code", "refresh_token"],
                  "code_challenge_methods_supported": ["S256"], "token_endpoint_auth_methods_supported": ["none"],
                  "revocation_endpoint_auth_methods_supported": ["none"], "scopes_supported": list(SCOPES),
                  "authorization_response_iss_parameter_supported": True}, headers=NO_STORE)

    async def fields(request):
        values = request.query_params if request.method == "GET" else await request.form()
        if any(len(values.getlist(key)) != 1 for key in values):
            return None
        return values

    @router.get("/oauth/authorize", operation_id="personal_ai_authorize_get")
    @router.post("/oauth/authorize", operation_id="personal_ai_authorize_post")
    async def authorize(request: Request):
        p = provider()
        await asyncio.to_thread(count, request, "personal_ai_authorize", p.tenant)
        values = await fields(request)
        if values is None or values.get("resource") != p.resource or not values.get("scope"):
            return oauth_error()
        client = await p.get_client(values.get("client_id", ""))
        # SDK AnyUrl 비교 전에 원문 exact match를 검사한다(정규화로 다른 URI를 허용하지 않음).
        if (not client or not await p.redirect_allowed(values.get("client_id", ""), values.get("redirect_uri"))
                or values.get("code_challenge_method") != "S256"):
            return oauth_error()
        response = await AuthorizationHandler(p).handle(request)
        if response.headers.get("location"):
            response.headers["location"] = construct_redirect_uri(response.headers["location"], iss=p.issuer)
        response.headers.update(NO_STORE)
        return response

    @router.post("/oauth/token")
    async def token(request: Request):
        p = provider()
        await asyncio.to_thread(count, request, "personal_ai_token", p.tenant)
        values = await fields(request)
        if values is None or values.get("resource") != p.resource:
            return oauth_error()
        if values.get("grant_type") == "authorization_code" and not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", values.get("code_verifier", "")):
            return oauth_error()
        if request.headers.get("cookie"):
            return oauth_error()
        return await TokenHandler(p, ClientAuthenticator(p)).handle(request)

    @router.post("/oauth/revoke")
    async def revoke(request: Request):
        p = provider()
        await asyncio.to_thread(count, request, "personal_ai_revoke", p.tenant)
        if request.headers.get("cookie") or await fields(request) is None:
            return oauth_error()
        form = await request.form()
        if "client_secret" not in form:
            # SDK 1.28.1의 nullable/required 모델 차이. 공개 클라이언트에는 secret이 없다.
            request._form = FormData([*form.multi_items(), ("client_secret", "")])
        return await RevocationHandler(p, ClientAuthenticator(p)).handle(request)

    @router.get("/oauth/consent", response_class=HTMLResponse)
    async def consent_screen(request: Request):
        who = await asyncio.to_thread(member, request, optional=True)
        raw = request.query_params.get("request", "")
        if not raw or len(raw) > 200:
            return oauth_error()
        if who is None:
            from app.core.settings import get_settings
            settings = get_settings()
            origin = (settings.web_origin or next((o.strip() for o in settings.web_allowed_origins.split(",") if o.strip()), "")).rstrip("/")
            if not origin:
                return oauth_error("login_unavailable", 503)
            return document("개인 AI 연결 로그인", "<h1>개인 AI를 연결하려면 로그인해 주세요</h1><p>로그인 화면을 새 탭에서 연 뒤 이 화면으로 돌아와 확인해 주세요.</p>"
                f"<p><a target='_blank' rel='noopener noreferrer' href='{html.escape(origin + '/mypage#accounts')}'>로그인 화면 열기</a></p>"
                f"<form method='get' action='/oauth/consent'><input type='hidden' name='request' value='{html.escape(raw)}'>"
                "<button>로그인 후 다시 확인</button></form>")
        p = provider()
        try:
            row = await asyncio.to_thread(p.consent, raw, who.customer_id, who.session.session_hash)
        except ValueError:
            return oauth_error()
        from app.core.settings import get_guardrails
        writing = bool(get_guardrails().get("travel.mcp.write_enabled"))
        operations = "여행 조회" + (" · 일정 변경" if "travel:write" in row["scopes"] else "")
        expiry = datetime.fromtimestamp(row["expires_at"], ZoneInfo("Asia/Seoul")).strftime("%Y년 %m월 %d일 %H:%M (한국 시간)")
        safe = html.escape
        body = f'''<h1>개인 AI 연결 허용</h1>
<p>등록된 이름: <strong>{safe(row['client_name'])}</strong> (업체 신원 보증이 아닙니다.)</p>
<p>현재 로그인한 계정의 본인 여행 전체에 다음 작업을 허용합니다: {safe(operations)}.</p>
<p>MCP 일정 변경 활성: {'켜짐' if writing else '꺼짐'}. 연결 만료: {safe(expiry)}.</p>
<p>계정 연동·연락처 변경·키 생성·예약·결제 승인 권한은 없습니다. 연결 목록에서 언제든 폐기할 수 있습니다.</p>
<form method="post" action="/oauth/consent"><input type="hidden" name="request_token" value="{safe(raw)}">
<input type="hidden" name="csrf_token" value="{safe(who.session.csrf)}">
<button name="decision" value="allow">연결 허용</button> <button name="decision" value="deny">연결 취소</button></form>
<p><a href="/oauth/connections">연결 목록 열기</a></p>'''
        return document("개인 AI 연결 허용", body)

    @router.post("/oauth/consent")
    async def consent_post(request: Request):
        values = await fields(request)
        if values is None or values.get("decision") not in ("allow", "deny") or len(values.get("request_token", "")) > 200:
            return oauth_error()
        # HTML 폼은 헤더를 붙이지 못하므로 같은 세션 CSRF를 헤더 검사에 전달한다.
        headers = [(k, v) for k, v in request.scope["headers"] if k.lower() != b"x-csrf-token"]
        request.scope["headers"] = headers + [(b"x-csrf-token", values.get("csrf_token", "").encode())]
        # 새 Request로 기존 Origin+CSRF 검사 규칙을 그대로 적용한다.
        who = await asyncio.to_thread(member, Request(request.scope))
        try:
            target = await asyncio.to_thread(provider().consent, values.get("request_token", ""), who.customer_id,
                                             who.session.session_hash, approve=values["decision"] == "allow")
        except ValueError:
            return oauth_error()
        return RedirectResponse(target, status_code=303, headers=NO_STORE)

    @router.get("/v1/web/agent-connections")
    async def connections(request: Request, who=Depends(require_member)):
        rows = await asyncio.to_thread(provider().connections, who.customer_id)
        return JSONResponse({"connections": rows}, headers=NO_STORE)

    @router.delete("/v1/web/agent-connections/{connection_id}")
    async def disconnect(connection_id: str, request: Request, who=Depends(require_member)):
        found = await asyncio.to_thread(provider().connections, who.customer_id, connection_id)
        return JSONResponse({"revoked": True}, headers=NO_STORE) if found else oauth_error("not_found", 404)

    @router.get("/oauth/connections", response_class=HTMLResponse)
    async def connections_screen(request: Request):
        who = await asyncio.to_thread(member, request)
        rows = await asyncio.to_thread(provider().connections, who.customer_id)
        states = {"active": "연결됨", "expired": "만료됨", "revoked": "폐기됨"}
        query = request.query_params.get("q", "")[:80]
        status = request.query_params.get("status", "")
        filtered = [row for row in rows if query.casefold() in row["client_name"].casefold()
                    and (not status or row["status"] == status)]
        try:
            page = max(1, min(int(request.query_params.get("page", "1")), max(1, (len(filtered) + 19) // 20)))
        except ValueError:
            return oauth_error()
        sections = "".join(f"<li><strong>{html.escape(row['client_name'])}</strong><p>{states[row['status']]}</p>"
                           + (f"<a class='action' href='/oauth/connections/{row['connection_id']}/disconnect'>연결 폐기 확인</a>"
                              if row['status'] == 'active' else "") + "</li>" for row in filtered[(page-1)*20:page*20])
        options = "<option value=''>전체 상태</option>" + "".join(
            f"<option value='{key}'{' selected' if key == status else ''}>{value}</option>" for key, value in states.items())
        empty = ("검색 조건에 맞는 연결이 없습니다. <a href='/oauth/connections'>검색 조건 지우기</a>" if rows else
                 "아직 연결한 개인 AI가 없습니다. 개인 AI에서 triPilot 연결을 시작해 주세요.")
        nav = []
        for label, target, available in (("이전 페이지", page-1, page > 1), ("다음 페이지", page+1, page*20 < len(filtered))):
            href = "/oauth/connections?" + urlencode({"q": query, "status": status, "page": target})
            nav.append(f"<a class='action' href='{html.escape(href)}'>{label}</a>" if available else
                       f"<span class='action muted' aria-disabled='true'>{label}</span>")
        return document("개인 AI 연결", "<h1>개인 AI 연결</h1><p>내 여행에 접근할 수 있는 개인 AI를 확인하고 연결을 폐기합니다.</p>"
                        f"<form method='get' action='/oauth/connections'><label>이름으로 검색<input name='q' value='{html.escape(query)}' maxlength='80'></label>"
                        f"<label>연결 상태<select name='status'>{options}</select></label><button>연결 검색</button></form>"
                        f"<div class='list-frame'><ul>{sections or '<li>' + empty + '</li>'}</ul></div>"
                        f"<p class='muted'>{len(filtered)}개 중 {(page-1)*20+1 if filtered else 0}–{min(page*20,len(filtered))}개</p>"
                        "<nav aria-label='연결 목록 페이지'>" + " ".join(nav) + "</nav>")

    @router.get("/oauth/connections/{connection_id}/disconnect", response_class=HTMLResponse)
    async def disconnect_screen(connection_id: str, request: Request):
        who = await asyncio.to_thread(member, request)
        rows = await asyncio.to_thread(provider().connections, who.customer_id)
        row = next((row for row in rows if row['connection_id'] == connection_id), None)
        if not row:
            return oauth_error("not_found", 404)
        return document("개인 AI 연결 폐기 확인", "<h1>개인 AI 연결 폐기 확인</h1>"
                        f"<p><strong>{html.escape(row['client_name'])}</strong>의 여행 조회·변경 접근을 중단합니다. 다시 사용하려면 새로 연결해야 합니다.</p>"
                        "<p><a autofocus href='/oauth/connections'>연결 목록으로 돌아가기</a></p>"
                        f"<form method='post' action='/oauth/disconnect'><input type='hidden' name='connection_id' value='{html.escape(connection_id)}'>"
                        f"<input type='hidden' name='csrf_token' value='{html.escape(who.session.csrf)}'><button class='danger'>연결 폐기</button></form>"
                        )

    @router.post("/oauth/disconnect")
    async def disconnect_form(request: Request):
        values = await fields(request)
        if values is None:
            return oauth_error()
        scope = {**request.scope, "headers": [(k, v) for k, v in request.scope["headers"] if k.lower() != b"x-csrf-token"]
                 + [(b"x-csrf-token", values.get("csrf_token", "").encode())]}
        who = await asyncio.to_thread(member, Request(scope))
        found = await asyncio.to_thread(provider().connections, who.customer_id, values.get("connection_id", ""))
        return RedirectResponse("/oauth/connections", status_code=303, headers=NO_STORE) if found else oauth_error("not_found", 404)

    return router
