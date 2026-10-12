"""Customer support records: cookie authentication and strict ownership."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.application import admin_service
from app.core.redaction import masked
from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.modules.web_account import web_cookie


class Inquiry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: Annotated[str, Field(min_length=1, max_length=200, pattern=r"\S")]
    body: Annotated[str, Field(min_length=1, max_length=5000, pattern=r"\S")]
    language: Annotated[str, Field(max_length=30)] = "ko"
    requestId: UUID


def build_router() -> APIRouter:
    router = APIRouter(prefix="/v1/web/support", tags=["customer-support"])

    @router.get("/notices")
    def notices():
        tenant = get_settings().tenant_id
        now = datetime.now(admin_service.KST)
        with get_connection() as conn:
            items = admin_service.records(conn, tenant, "notice")
            maintenance = admin_service.record(conn, tenant, "settings", "maintenance") or {"enabled": False, "message": "", "messageEn": "", "endsAt": ""}
        active = [n for n in items if datetime.fromisoformat(n["startsAt"]).replace(tzinfo=admin_service.KST) <= now < datetime.fromisoformat(n["endsAt"]).replace(tzinfo=admin_service.KST)]
        if maintenance["enabled"] and datetime.fromisoformat(maintenance["endsAt"]).replace(tzinfo=admin_service.KST) <= now:
            maintenance["enabled"] = False
        # Operator identity belongs in the audit, not in the public notice.
        return {"notices": [{k:v for k,v in n.items() if k != "author"} for n in active], "maintenance": maintenance}

    @router.get("/inquiries")
    def inquiries(identity=Depends(web_cookie.require_identity)):
        with get_connection() as conn:
            items = admin_service.records(conn, identity.tenant_id, "inquiry")
        return {"inquiries": [n for n in items if n["userId"] == str(identity.customer_id)]}

    @router.post("/inquiries", status_code=201)
    def create(body: Inquiry, identity=Depends(web_cookie.require_identity)):
        tenant, customer = identity.tenant_id, str(identity.customer_id)
        identity_key = str(body.requestId)
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"admin:{tenant}:inquiry:{identity_key}",))
            existing = admin_service.record(conn, tenant, "inquiry", identity_key, lock=True)
            title, message = masked(body.title), masked(body.body)
            if existing:
                if existing["userId"] != customer or existing["title"] != title or existing["body"] != message:
                    raise HTTPException(409, "이미 사용한 요청 번호입니다.")
                return {"inquiry": {**existing, "id": identity_key}}
            admin_service.require_customer(conn, tenant, customer)
            value = {"userId": customer, "title": title, "body": message, "language": body.language, "receivedAt": datetime.now(admin_service.KST).isoformat(), "status": "접수", "assignee": "", "replies": [], "history": []}
            admin_service.put(conn, tenant, "inquiry", identity_key, value, actor=customer, action="customer-inquiry", reason="고객 문의 접수")
        return {"inquiry": {**value, "id": identity_key}}

    return router
