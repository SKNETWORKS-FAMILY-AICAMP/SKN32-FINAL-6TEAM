"""관리자 QA 제어와 일회용 고객 로그인 표 교환."""
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.application import admin_service
from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection
from . import qa_account, web_cookie


class OpenIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_revision: int = Field(ge=0, strict=True)
    reason: str = Field(min_length=1, max_length=500, pattern=r"\S")


class ChangeIn(OpenIn):
    enabled: StrictBool
    confirm_customer_id: UUID | None = None


def _error(exc):
    return HTTPException(exc.status_code, exc.detail, headers={"Cache-Control": "no-store"})


def build_admin_router(operator, require):
    router = APIRouter(prefix="/admin/api/qa-account", tags=["operations-admin"])

    @router.get("")
    def read(op=Depends(operator)):
        require(op, "ops:introspect")
        with get_connection() as conn:
            return JSONResponse(qa_account.status(conn, get_settings().tenant_id), headers={"Cache-Control": "no-store"})

    @router.patch("")
    def change(body: ChangeIn, op=Depends(operator)):
        require(op, "limits:write")
        with get_connection() as conn, conn.transaction():
            try:
                data = qa_account.change(conn, get_settings().tenant_id, op.id, **body.model_dump())
            except admin_service.AdminServiceError as exc:
                raise _error(exc) from None
        return JSONResponse(data, headers={"Cache-Control": "no-store"})

    @router.post("/open")
    def open_account(body: OpenIn, op=Depends(operator)):
        require(op, "limits:write")
        settings = get_settings()
        origin = settings.public_base_url.rstrip("/")
        if urlparse(origin).scheme not in ("https", "http") or not urlparse(origin).netloc:
            raise HTTPException(503, "고객 API 주소 설정을 확인해 주세요.")
        with get_connection() as conn, conn.transaction():
            try:
                raw, seconds = qa_account.issue_ticket(conn, settings.tenant_id, op.id, **body.model_dump())
            except admin_service.AdminServiceError as exc:
                raise _error(exc) from None
        return JSONResponse({"url": origin + "/v1/web/auth/qa-session", "ticket": raw,
                             "expires_in_seconds": seconds}, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

    return router


def build_customer_router():
    router = APIRouter()

    @router.post("/v1/web/auth/qa-session")
    def exchange(ticket: str = Form(min_length=40, max_length=100)):
        settings = get_settings()
        origin = (settings.web_origin or "").strip()
        if not origin:
            origin = next((value.strip() for value in settings.web_allowed_origins.split(",") if value.strip()), "")
        origin = origin.rstrip("/")
        if urlparse(origin).scheme not in ("http", "https") or not urlparse(origin).netloc:
            raise HTTPException(503, "고객 웹 주소 설정을 확인해 주세요.")
        with get_connection() as conn, conn.transaction():
            try:
                customer = qa_account.consume_ticket(conn, settings.tenant_id, ticket)
                raw, _session = web_cookie.start(conn, tenant_id=settings.tenant_id, customer_id=customer)
            except admin_service.AdminServiceError as exc:
                raise _error(exc) from None
        response = RedirectResponse(origin + "/trips/new", status_code=303,
                                    headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        response.headers.append("Set-Cookie", web_cookie.cookie_header(raw, tenant_id=settings.tenant_id, persistent=False))
        return response

    return router
