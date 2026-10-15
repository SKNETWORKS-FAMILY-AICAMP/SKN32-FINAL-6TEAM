"""Dedicated maintenance APIs; never edits customer trips or runs provider calls."""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.application import admin_service, operations_diagnostics as diagnostics, operations_policy as policy
from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection, get_ops_read_connection


class PolicyChange(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=0)
    policy: policy.SourcePolicy
    reason: str = Field(min_length=1, max_length=500)


class Resolution(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,80}$")
    reason: str = Field(min_length=1, max_length=500)


def build_router(*, operator_dependency, require_permission):
    router = APIRouter(prefix="/admin/api", tags=["unattended-operations"])

    @router.get("/source-policy")
    def source_policy(op=Depends(operator_dependency)):
        require_permission(op, "limits:read")
        try:
            with get_ops_read_connection() as conn:
                return policy.read(conn, get_settings().tenant_id)
        except Exception:
            raise HTTPException(503, "자료 조회 정책을 읽지 못했습니다. 잠시 후 다시 읽어 주세요.") from None

    @router.patch("/source-policy")
    def save_policy(body: PolicyChange, op=Depends(operator_dependency)):
        require_permission(op, "limits:write")
        try:
            with get_connection() as conn, conn.transaction():
                return policy.save(conn, get_settings().tenant_id, expected_revision=body.expected_revision,
                                   policy=body.policy, actor=op.id, reason=body.reason)
        except admin_service.AdminServiceError as exc:
            raise HTTPException(exc.status_code, exc.detail) from None
        except ValueError:
            raise HTTPException(422, "조회 설정 범위와 변경 사유를 확인해 주세요.") from None
        except Exception:
            raise HTTPException(503, "설정을 저장하지 못했습니다. 현재 값을 다시 읽어 주세요.") from None

    @router.get("/diagnostics")
    def defects(limit: Annotated[int, Query(ge=1, le=50)] = 50, before_at: datetime | None = None,
                before_key: Annotated[str | None, Query(pattern=r"^[a-f0-9]{64}$")] = None,
                op=Depends(operator_dependency)):
        require_permission(op, "ops:introspect")
        if bool(before_at) != bool(before_key) or before_at and before_at.tzinfo is None:
            raise HTTPException(422, "다음 페이지의 시각과 식별자를 함께 보내 주세요.")
        try:
            with get_ops_read_connection() as conn:
                return diagnostics.listing(conn, get_settings().tenant_id, limit=limit,
                                           before=(before_at, before_key) if before_at else None)
        except Exception:
            raise HTTPException(503, "진단 기록을 읽지 못했습니다. 정상 운영으로 판단할 수 없습니다.") from None

    @router.get("/diagnostics/{fingerprint}/customers")
    def affected(fingerprint: str,
                 after: str = "00000000-0000-0000-0000-000000000000", op=Depends(operator_dependency)):
        from uuid import UUID
        require_permission(op, "ops:introspect")
        require_permission(op, "case:read")
        try:
            cursor = UUID(after)
        except ValueError:
            raise HTTPException(422, "페이지 식별자가 올바르지 않습니다.") from None
        try:
            with get_ops_read_connection() as conn:
                rows = conn.execute("SELECT customer_id FROM ops_defect_customers WHERE tenant_id=%s AND fingerprint=%s "
                                    "AND expires_at>now() AND customer_id>%s ORDER BY customer_id LIMIT 51",
                                    (get_settings().tenant_id, fingerprint, cursor)).fetchall()
            return {"customers": [str(row[0]) for row in rows[:50]], "next": str(rows[49][0]) if len(rows) > 50 else None}
        except Exception:
            raise HTTPException(503, "영향 고객 연결을 읽지 못했습니다.") from None

    @router.patch("/diagnostics/{fingerprint}/resolution")
    def resolution(fingerprint: str, body: Resolution, op=Depends(operator_dependency)):
        require_permission(op, "ops:introspect")
        require_permission(op, "limits:write")
        if not body.reason.strip():
            raise HTTPException(422, "변경 사유를 입력해 주세요.")
        tenant = get_settings().tenant_id
        try:
            with get_connection() as conn, conn.transaction():
                row = conn.execute("SELECT resolved_version FROM ops_defects WHERE tenant_id=%s AND fingerprint=%s FOR UPDATE", (tenant, fingerprint)).fetchone()
                if not row:
                    raise HTTPException(404, "결함 기록을 찾을 수 없습니다.")
                conn.execute("UPDATE ops_defects SET resolved_version=%s WHERE tenant_id=%s AND fingerprint=%s", (body.version, tenant, fingerprint))
                admin_service.audit(conn, tenant, op.id, "defect-resolution", fingerprint, row[0], body.version, body.reason)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "해결 판을 기록하지 못했습니다. 잠시 후 다시 시도해 주세요.") from None
        return {"ok": True}

    @router.get("/diagnostics/{fingerprint}/events")
    def occurrences(fingerprint: str, after: str = "00000000-0000-0000-0000-000000000000", op=Depends(operator_dependency)):
        from uuid import UUID
        require_permission(op, "ops:introspect")
        require_permission(op, "case:read")
        try:
            cursor = UUID(after)
        except ValueError:
            raise HTTPException(422, "페이지 식별자가 올바르지 않습니다.") from None
        try:
            with get_ops_read_connection() as conn:
                rows = conn.execute("SELECT event_id,case_id,request_id,occurred_at FROM ops_diagnostic_events "
                                    "WHERE tenant_id=%s AND fingerprint=%s AND expires_at>now() AND event_id>%s ORDER BY event_id LIMIT 51",
                                    (get_settings().tenant_id, fingerprint, cursor)).fetchall()
            return {"events": [dict(zip(("event_id", "case_id", "request_id", "occurred_at"), row, strict=True)) for row in rows[:50]],
                    "next": str(rows[49][0]) if len(rows) > 50 else None}
        except Exception:
            raise HTTPException(503, "발생 기록을 읽지 못했습니다.") from None

    return router
