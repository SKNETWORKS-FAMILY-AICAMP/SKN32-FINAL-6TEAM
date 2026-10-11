"""JSON operations gateway; mount only in the isolated operations application."""
from __future__ import annotations

import hmac
import secrets
import httpx
from datetime import datetime
from typing import Annotated, Callable, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.application import admin_service
from app.core.settings import get_guardrails, get_settings
from app.core.redaction import mask_json
from app.infrastructure.db.session import get_connection
from app.presentation.ui import auth
from app.presentation.ui.routes import _api_key, _call_api, _case, _cases

Text = Annotated[str, Field(min_length=1, max_length=5000, pattern=r"\S")]
Count = Annotated[int, Field(strict=True, ge=1, le=100000000)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Block(Input):
    type: Literal["block-user"]
    userId: UUID
    blocked: bool
    reason: Text


class UserLimit(Input):
    type: Literal["user-limit"]
    userId: UUID
    limit: Count | None
    period: Literal["today", "until-cleared"]
    reason: Text


class Rule(Input):
    id: Text
    threshold: Annotated[float, Field(ge=1, le=99)]
    multiplier: Annotated[float, Field(ge=1.1, le=20)]


class Limits(Input):
    type: Literal["save-limits"]
    chatLimit: Count
    rules: Annotated[list[Rule], Field(max_length=5)]
    reason: Text


class ApiCap(Input):
    type: Literal["api-cap"]
    apiId: Text
    daily: Count
    monthly: Count
    reason: Text


class InquiryStatus(Input):
    type: Literal["inquiry-status"]
    inquiryId: UUID
    status: Literal["접수", "처리 중", "답변 완료"]
    assignee: Annotated[str, Field(max_length=100)]
    reason: Text


class Reply(Input):
    type: Literal["reply"]
    inquiryId: UUID
    body: Text


class Template(Input):
    type: Literal["save-template"]
    id: UUID | None = None
    title: Text
    body: Text


Date = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")]


class Maintenance(Input):
    type: Literal["maintenance"]
    enabled: bool
    message: Text
    messageEn: Annotated[str, Field(max_length=5000)]
    endsAt: Date
    reason: Text


class Notice(Input):
    kind: Text
    title: Text
    body: Text
    titleEn: Annotated[str, Field(max_length=5000)]
    bodyEn: Annotated[str, Field(max_length=5000)]
    startsAt: Date
    endsAt: Date


class Publish(Input):
    type: Literal["publish-notice"]
    notice: Notice


class Approval(Input):
    type: Literal["approval"]
    approvalId: Text
    approve: bool
    reason: Text


class Delegation(Input):
    type: Literal["delegation"]
    delegationId: UUID
    active: bool
    reason: Text


class Resolve(Input):
    type: Literal["resolve-outbox"]
    outboxId: UUID
    resolution: Literal["confirmed_delivered", "confirmed_not_delivered"]
    reason: Text


class Check(Input):
    type: Literal["check-server"]


Command = Annotated[Block | UserLimit | Limits | ApiCap | InquiryStatus | Reply | Template | Maintenance | Publish | Approval | Delegation | Resolve | Check, Field(discriminator="type")]
COMMAND = TypeAdapter(Command)
SCOPES = {"approval": "action:approve", "delegation": "delegation:write", "resolve-outbox": "action:approve", "check-server": "ops:introspect"}
PRE_COOKIE = "acop_admin_csrf"


def operator(request: Request) -> auth.Operator:
    op = auth.read(request.cookies.get(auth.COOKIE))
    if op is None:
        raise HTTPException(401, "운영자 로그인이 필요합니다.")
    if request.method != "GET":
        expected = auth.csrf_for(request.cookies[auth.COOKIE])
        if not hmac.compare_digest(expected, request.headers.get("X-CSRF-Token", "")):
            raise HTTPException(403, "폼 확인값이 맞지 않습니다.")
    request.state.operator = op
    return op


def require(op: auth.Operator, scope: str) -> None:
    if not op.can(scope):
        raise HTTPException(403, f"{scope} 권한이 없습니다.")


class Login(Input):
    operatorId: Annotated[str, Field(min_length=1, max_length=200)]
    password: Annotated[str, Field(min_length=1, max_length=1024)]


def build_router(*, snapshot_provider: Callable | None = None) -> APIRouter:
    router = APIRouter(prefix="/admin/api", tags=["operations-admin"])

    def measured_snapshot(conn, tenant, default_limit):
        if snapshot_provider is None:
            raise HTTPException(503, "운영 자료 제공기가 연결되지 않았습니다.")
        return snapshot_provider(conn, tenant, default_limit)

    @router.get("/session")
    def session(request: Request):
        op = auth.read(request.cookies.get(auth.COOKIE))
        token = auth.csrf_for(request.cookies[auth.COOKIE]) if op else secrets.token_urlsafe(32)
        response = JSONResponse({"authenticated": op is not None, "operator": op.id if op else None, "scopes": sorted(op.scopes) if op else [], "csrf": token, "configured": bool(auth.operators())})
        response.headers["Cache-Control"] = "no-store"
        if not op:
            response.set_cookie(PRE_COOKIE, token, httponly=True, samesite="strict", secure=request.url.scheme == "https", path="/admin/api", max_age=900)
        return response

    @router.post("/login")
    def login(body: Login, request: Request):
        expected = request.cookies.get(PRE_COOKIE, "")
        if not expected or not hmac.compare_digest(expected, request.headers.get("X-CSRF-Token", "")):
            raise HTTPException(403, "로그인 화면을 다시 열어 주세요.")
        if auth.locked(body.operatorId):
            raise HTTPException(429, "로그인 실패가 많아 잠시 잠겼습니다.")
        op = auth.authenticate(body.operatorId, body.password)
        if op is None:
            raise HTTPException(401, "ID 또는 비밀번호가 맞지 않습니다.")
        response = JSONResponse({"operator": op.id})
        response.set_cookie(auth.COOKIE, auth.issue(op), httponly=True, samesite="strict", secure=request.url.scheme == "https", path="/", max_age=int(float(get_guardrails().get("security.ui_session_hours"))*3600))
        response.delete_cookie(PRE_COOKIE, path="/admin/api")
        return response

    @router.post("/logout")
    def logout(op=Depends(operator)):
        response = JSONResponse({"ok": True})
        response.delete_cookie(auth.COOKIE, path="/")
        return response

    @router.get("/snapshot")
    def snapshot(op=Depends(operator)):
        require(op, "ops:introspect")
        with get_connection() as conn:
            data = measured_snapshot(conn, get_settings().tenant_id, int(get_guardrails().get("web_guard.limits.message.per_key_day")))
        return JSONResponse(data, headers={"Cache-Control": "no-store"})

    @router.get("/cases")
    def cases(op=Depends(operator)):
        require(op, "case:read")
        return {"cases": mask_json(_cases())}

    @router.get("/cases/{case_id}")
    def case(case_id: UUID, op=Depends(operator)):
        require(op, "case:read")
        value = _case(case_id)
        if value is None:
            raise HTTPException(404, "접수 건을 찾을 수 없습니다.")
        return mask_json(value)

    @router.post("/commands")
    async def commands(body: Command, request: Request, op=Depends(operator)):
        command = body.model_dump(mode="json", exclude_none=False)
        # Templates omit absent ids; null is not a persisted identity.
        if command.get("id") is None:
            command.pop("id", None)
        kind = command["type"]
        require(op, SCOPES.get(kind, "limits:write"))
        for date in (command.get("endsAt"), command.get("notice", {}).get("startsAt"), command.get("notice", {}).get("endsAt")):
            if date:
                try:
                    datetime.fromisoformat(date)
                except ValueError:
                    raise HTTPException(422, "날짜가 올바르지 않습니다.") from None
        tenant = get_settings().tenant_id
        if kind in ("approval", "delegation", "resolve-outbox", "save-limits"):
            if kind == "approval":
                try:
                    case, action = command["approvalId"].split(":")
                    UUID(case), UUID(action)
                except ValueError:
                    raise HTTPException(422, "승인 대상이 올바르지 않습니다.") from None
                path = f"/v1/cases/{case}/actions/{action}/approve"
                payload = {"decision": "approved" if command["approve"] else "rejected", "approver_id": op.id, "note": command["reason"]}
            elif kind == "delegation":
                path = f"/v1/delegations/{command['delegationId']}/{'grant' if command['active'] else 'revoke'}"
                payload = {"actor_id": op.id, "note": command["reason"]}
            elif kind == "resolve-outbox":
                path = f"/v1/outbox/{command['outboxId']}/resolve"
                payload = {"resolved_by": op.id, "note": command["reason"], "resolution": command["resolution"]}
            else:
                # Existing operations limits are mounted on this operations app.
                # Persisted policy is enforced by the customer boundary too.
                path = ""
                payload = {}
            if path:
                response = await _call_api(request, "POST", path, scope=SCOPES[kind], payload=payload)
                if response.is_error:
                    raise HTTPException(response.status_code, response.json())
                with get_connection() as conn, conn.transaction():
                    admin_service.audit(conn, tenant, op.id, kind, path, None, response.json(), command.get("reason", ""))
                return {"ok": True}
        if kind == "check-server":
            with get_connection() as conn:
                measured_snapshot(conn, tenant, int(get_guardrails().get("web_guard.limits.message.per_key_day")))
            return {"ok": True}
        with get_connection() as conn, conn.transaction():
            try:
                admin_service.mutate(conn, tenant, op.id, command)
            except admin_service.AdminServiceError as exc:
                raise HTTPException(exc.status_code, exc.detail) from None
        return {"ok": True}

    @router.api_route("/settings/{kind}", methods=["GET", "PATCH"])
    async def existing_settings(kind: Literal["limits", "retention"], request: Request, op=Depends(operator)):
        scope = "limits:read" if request.method == "GET" else "limits:write"
        require(op, scope)
        key = _api_key(scope)
        if key is None:
            raise HTTPException(503, "운영용 제한 설정 키가 설정되지 않았습니다.")
        payload = None
        if request.method == "PATCH":
            payload = await request.json()
            if not isinstance(payload, dict):
                raise HTTPException(422, "설정 요청은 객체여야 합니다.")
            payload["actor"] = op.id
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=request.app), base_url="http://localhost") as client:
            response = await client.request(request.method, f"/admin/{kind}", json=payload, headers={"Authorization": f"Bearer {key}"})
        if response.is_error:
            raise HTTPException(response.status_code, response.json())
        return response.json()

    return router
