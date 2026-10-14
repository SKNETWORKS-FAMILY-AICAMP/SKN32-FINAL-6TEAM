"""Customer support records: cookie authentication and strict ownership."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.application import admin_service
from app.application.operations_diagnostics import Event, deployment_version, persist
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
    def inquiries(before: UUID | None = None, limit: Annotated[int, Query(ge=1, le=50)] = 50, identity=Depends(web_cookie.require_identity)):
        with get_connection() as conn:
            args = [identity.tenant_id, identity.customer_id]
            condition = ""
            if before:
                cursor = conn.execute("SELECT updated_at,id FROM admin_records WHERE tenant_id=%s AND customer_id=%s AND kind='inquiry' AND id=%s",
                                      (*args, str(before))).fetchone()
                if not cursor:
                    raise HTTPException(404, "접수 기록을 찾을 수 없습니다.")
                condition = " AND (updated_at,id)<(%s,%s)"
                args.extend(cursor)
            rows = conn.execute("SELECT id,value FROM admin_records WHERE tenant_id=%s AND customer_id=%s AND kind='inquiry'" + condition +
                                " ORDER BY updated_at DESC,id DESC LIMIT %s", (*args, limit + 1)).fetchall()
        return {"inquiries": [_public({**row[1], "id": row[0]}) for row in rows[:limit]], "next": rows[limit-1][0] if len(rows) > limit else None}

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
                return {"inquiry": _public({**existing, "id": identity_key})}
            admin_service.require_customer(conn, tenant, customer)
            value = {"userId": customer, "title": title, "body": message, "language": body.language, "receivedAt": datetime.now(admin_service.KST).isoformat(), "status": "기록 완료", "recordType": "suggestion", "assignee": "", "replies": [], "history": []}
            admin_service.put(conn, tenant, "inquiry", identity_key, value, actor=customer, action="customer-inquiry", reason="고객 문의 접수")
            persist(conn, Event(event_id=body.requestId, request_id=body.requestId, tenant_id=tenant, customer_id=identity.customer_id,
                                kind="suggestion", code="CUSTOMER_SUGGESTION", deployment=deployment_version(), policy_version="unattended-v1",
                                conditions=["CUSTOMER_SUBMISSION"]))
        return {"inquiry": _public({**value, "id": identity_key})}

    return router


def _public(value: dict) -> dict:
    """Receipt means recorded, never a promise of agent assignment or resolution."""
    return {**{key: value.get(key) for key in ("id", "title", "body", "language", "receivedAt")},
            "status": "기록 완료", "recordType": "suggestion", "replies": [],
            "message": "개선을 위한 기록을 저장했습니다. 여행 문제는 여행 화면에서 다시 요청하거나 장소 정보를 직접 보완해 주세요."}
