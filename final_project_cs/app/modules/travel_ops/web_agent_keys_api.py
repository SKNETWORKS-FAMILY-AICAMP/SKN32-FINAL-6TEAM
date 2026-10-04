# -*- coding: utf-8 -*-
"""에이전트 키 HTTP — 계약은 `wiki/external/rest-endpoints.md` 「에이전트 키」. `[2026-10-04 사용자 결정]` D-CS-012

    GET    /v1/web/agent-keys               내 키 목록(원문 없음)
    POST   /v1/web/agent-keys               새 키 — 원문은 이 응답에만(201)
    DELETE /v1/web/agent-keys/{key_id}      개별 폐기

★**쿠키 세션으로 로그인한 회원만** 부른다 — 에이전트 키 · 옛 사용자 키로는 못 만들고(`403 cookie_required`), 게스트는 못 만든다(`403 member_only` + `login_required`).
  쓰기 두 경로는 쿠키 인증의 Origin + CSRF 를 거친다(`web_cookie.authenticate`).
"""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.infrastructure.db.session import get_connection

from . import web_agent_keys, web_cookie


class AgentKeyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=60)
    scope: Literal["read", "write"]
    expires_days: int | None = Field(default=None, ge=1)


def _member_by_cookie(who: web_cookie.Identity = Depends(web_cookie.require_identity)) -> web_cookie.Identity:
    """쿠키 세션 + 회원 — 아니면 403. (에이전트 키는 경로 때문에 `agent_forbidden` 이 먼저 난다.)"""
    if who.via != "cookie" or who.session is None:
        raise web_cookie.refuse(403, "cookie_required", "에이전트 키는 브라우저 로그인에서만 만들고 관리한다")
    if who.session.kind != "member":
        raise web_cookie.refuse(403, "member_only", "로그인하면 에이전트를 연결할 수 있어요", login_required=True)
    return who


def _body(row: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"key_id": str(row["key_id"]), "name": row["name"], "scope": row["scope"],
            "created_at": web_agent_keys.iso(row["created_at"]), "expires_at": web_agent_keys.iso(row["expires_at"]), **extra}


def build_agent_keys_router() -> APIRouter:
    router = APIRouter()

    @router.get("/v1/web/agent-keys")
    def list_agent_keys(who: web_cookie.Identity = Depends(_member_by_cookie)):
        with get_connection() as conn:
            rows = web_agent_keys.list_keys(conn, tenant_id=who.tenant_id, customer_id=who.customer_id)
        return JSONResponse({"keys": [{**_body(r), "last_used_at": web_agent_keys.iso(r["last_used_at"]), "status": r["status"]} for r in rows]},
                            headers={"Cache-Control": "no-store"})

    @router.post("/v1/web/agent-keys", status_code=201)
    def create_agent_key(body: AgentKeyIn = Body(...), who: web_cookie.Identity = Depends(_member_by_cookie)):
        try:
            with get_connection() as conn, conn.transaction():
                made = web_agent_keys.create(conn, tenant_id=who.tenant_id, customer_id=who.customer_id, name=body.name.strip(),
                                             scope=body.scope, expires_days=body.expires_days)
        except web_agent_keys.AgentKeyLimit:
            raise web_cookie.refuse(409, "agent_key_limit", "에이전트 키를 더 만들 수 없어요 — 안 쓰는 키를 폐기한 뒤 다시 만들어 주세요") from None
        except web_agent_keys.NotMember:
            raise web_cookie.refuse(403, "member_only", "로그인하면 에이전트를 연결할 수 있어요", login_required=True) from None
        except ValueError:
            raise web_cookie.refuse(422, "invalid_agent_key", "이름(1~60자) · 권한(read/write) · 만료일수(1~최대)를 확인해 주세요") from None
        return JSONResponse({**_body(made), "key": made["key"],
                             "notice": "이 키는 지금 한 번만 보여 드려요. 다시 볼 수 없으니 에이전트에 바로 붙여 넣어 주세요."},
                            status_code=201, headers={"Cache-Control": "no-store"})

    @router.delete("/v1/web/agent-keys/{key_id}")
    def revoke_agent_key(key_id: UUID, who: web_cookie.Identity = Depends(_member_by_cookie)):
        with get_connection() as conn, conn.transaction():
            done = web_agent_keys.revoke(conn, tenant_id=who.tenant_id, customer_id=who.customer_id, key_id=key_id)
        if not done:
            raise web_cookie.refuse(404, "not_found", "resource not found")
        return JSONResponse({"key_id": str(key_id), "status": "revoked"}, headers={"Cache-Control": "no-store"})

    return router


__all__ = ["build_agent_keys_router"]
