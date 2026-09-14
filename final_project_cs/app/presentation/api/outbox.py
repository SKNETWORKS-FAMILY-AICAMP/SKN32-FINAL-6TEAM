from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.infrastructure.db.session import get_connection
from app.presentation.security import Principal, require_scope


class OutboxResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolution: Literal["confirmed_delivered", "confirmed_not_delivered"]
    note: str = Field(min_length=1)
    resolved_by: str = Field(min_length=1)


def build_router() -> APIRouter:
    router = APIRouter()

    @router.post("/v1/outbox/{message_id}/resolve")
    def resolve(message_id: UUID, request: OutboxResolution,
                principal: Principal = Depends(require_scope("action:approve"))):
        note = request.note.strip()
        resolved_by = request.resolved_by.strip()
        if not note:
            raise HTTPException(422, {"error": {"code": "note_required", "message": "resolution note is required"}})
        if not resolved_by:
            raise HTTPException(422, {"error": {"code": "resolved_by_required", "message": "resolved_by is required"}})

        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    # Deliberately update resolution evidence only.  In particular,
                    # status remains unknown and no provider publish is triggered.
                    cur.execute(
                        "UPDATE outbox SET resolved_at=now(), resolved_by=%s, "
                        "resolution_note=%s, resolution=%s "
                        "WHERE message_id=%s AND tenant_id=%s AND status='unknown' AND resolved_at IS NULL "
                        "RETURNING message_id,status,resolved_at,resolved_by,resolution_note,resolution",
                        (resolved_by, note, request.resolution, message_id, principal.tenant_id),
                    )
                    row = cur.fetchone()
                    if row is None:
                        cur.execute("SELECT status FROM outbox WHERE message_id=%s AND tenant_id=%s",
                                    (message_id, principal.tenant_id))
                        existing = cur.fetchone()
        if row is None:
            if existing is not None:
                raise HTTPException(409, {"error": {"code": "invalid_status", "message": "outbox row is not unknown"}})
            raise HTTPException(404, {"error": {"code": "not_found", "message": "resource not found"}})
        return {"message_id": str(row[0]), "status": row[1], "resolved_at": row[2],
                "resolved_by": row[3], "resolution_note": row[4], "resolution": row[5]}

    return router
