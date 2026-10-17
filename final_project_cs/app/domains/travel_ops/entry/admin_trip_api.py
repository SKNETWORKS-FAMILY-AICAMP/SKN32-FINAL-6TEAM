"""운영자 전용 여행 상세 조회. 저장된 대화·최초/현재 계획을 읽기만 한다."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from app.core.redaction import mask_json
from app.core.settings import get_settings
from app.infrastructure.db.session import get_ops_read_connection as get_connection


def _trip(cur, tenant: str, customer_id: UUID, trip_id: UUID) -> dict:
    cur.execute("SELECT trip_id,customer_id,title,status,locale,party_size,latest_version,created_at "
                "FROM trips WHERE tenant_id=%s AND customer_id=%s AND trip_id=%s",
                (tenant, customer_id, trip_id))
    row = cur.fetchone()
    if row is None:
        raise HTTPException(404, "이 사용자의 여행을 찾을 수 없습니다. 사용자와 여행을 다시 선택해 주세요.")
    return {"trip_id": str(row[0]), "customer_id": str(row[1]), "title": row[2], "status": row[3],
            "locale": row[4], "party_size": row[5], "latest_version": row[6], "created_at": row[7].isoformat()}


def _response(data: dict) -> JSONResponse:
    return JSONResponse(mask_json(data), headers={"Cache-Control": "no-store"})


def _display_detail(value) -> dict:
    details = value if isinstance(value, dict) else {}
    result = {key: details[key] for key in ("mode", "travel_minutes", "price_krw", "route_text")
              if key in details and isinstance(details[key], (str, int, float))}
    route = details.get("route_def")
    if isinstance(route, dict) and isinstance(route.get("options"), list):
        selected = details.get("option") or route.get("planned")
        option = next((row for row in route["options"] if isinstance(row, dict) and row.get("id") == selected), {})
        if isinstance(option.get("label"), str):
            result["mode"] = option["label"]
        if isinstance(option.get("eta_min"), (int, float)):
            result["travel_minutes"] = option["eta_min"]
    planner = details.get("planner")
    if "travel_minutes" not in result and isinstance(planner, dict) and isinstance(planner.get("travel_min"), (int, float)):
        result["travel_minutes"] = planner["travel_min"]
    return result


def build_router(*, operator_dependency, require_permission):
    router = APIRouter(prefix="/admin/api/users/{customer_id}/trips/{trip_id}", tags=["operations-trip-detail"])

    @router.get("")
    def detail(customer_id: UUID, trip_id: UUID, op=Depends(operator_dependency)):
        require_permission(op, "ops:introspect")
        with get_connection() as conn, conn.cursor() as cur:
            trip = _trip(cur, get_settings().tenant_id, customer_id, trip_id)
        return _response({"trip": trip, "as_of": datetime.now(UTC).isoformat()})

    @router.get("/draft")
    def draft(customer_id: UUID, trip_id: UUID, op=Depends(operator_dependency)):
        require_permission(op, "ops:introspect")
        tenant = get_settings().tenant_id
        result = None
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            _trip(cur, tenant, customer_id, trip_id)
            cur.execute("SELECT intake_id,received_at FROM trip_intakes "
                        "WHERE tenant_id=%s AND customer_id=%s AND trip_id=%s "
                        "AND reopen_trip_id IS NULL ORDER BY received_at,intake_id LIMIT 1",
                        (tenant, customer_id, trip_id))
            intake = cur.fetchone()
            if intake:
                cur.execute("SELECT source_id,position,kind,filename,transcript,transcribed "
                            "FROM intake_sources WHERE tenant_id=%s AND intake_id=%s "
                            "ORDER BY position,source_id", (tenant, intake[0]))
                sources = [{"source_id": str(row[0]), "position": row[1], "kind": row[2],
                            "filename": row[3].replace("\\", "/").rsplit("/", 1)[-1] if row[3] else None,
                            "text": row[4], "transcribed": row[5]} for row in cur.fetchall()]
                result = {"intake_id": str(intake[0]), "received_at": intake[1].isoformat(), "sources": sources}
        return _response({"draft": result, "as_of": datetime.now(UTC).isoformat()})

    @router.get("/chat")
    def chat(customer_id: UUID, trip_id: UUID, op=Depends(operator_dependency),
             after: str = Query("0", pattern=r"^(0|[1-9][0-9]{0,18})$"),
             limit: int = Query(100, ge=1, le=200)):
        require_permission(op, "ops:introspect")
        tenant = get_settings().tenant_id
        if int(after) > 9223372036854775807:
            raise HTTPException(422, "대화 위치가 올바르지 않습니다. 처음부터 다시 읽어 주세요.")
        with get_connection() as conn, conn.cursor() as cur:
            _trip(cur, tenant, customer_id, trip_id)
            cur.execute("SELECT turn_id,role,text,case_id,created_at FROM trip_chat_turns "
                        "WHERE tenant_id=%s AND trip_id=%s AND turn_id>%s ORDER BY turn_id LIMIT %s",
                        (tenant, trip_id, int(after), limit + 1))
            rows = cur.fetchall()
        turns = [{"turn_id": str(row[0]), "role": row[1], "text": row[2],
                  "case_id": str(row[3]) if row[3] else None, "at": row[4].isoformat()}
                 for row in rows[:limit]]
        return _response({"turns": turns, "next_after": turns[-1]["turn_id"] if len(rows) > limit else None})

    @router.get("/plans/{view}")
    def plan(customer_id: UUID, trip_id: UUID, view: Literal["initial", "current"],
             op=Depends(operator_dependency)):
        require_permission(op, "ops:introspect")
        tenant = get_settings().tenant_id
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            # 최신 포인터와 해당 판 항목을 같은 조회 시점으로 고정한다.
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            trip = _trip(cur, tenant, customer_id, trip_id)
            version = 1 if view == "initial" else trip["latest_version"]
            cur.execute("SELECT reason,created_at FROM itinerary_versions "
                        "WHERE tenant_id=%s AND trip_id=%s AND version=%s", (tenant, trip_id, version))
            meta = cur.fetchone()
            result = None
            if meta:
                cur.execute("SELECT i.item_id,i.seq,i.kind,i.title,i.starts_at,i.ends_at,i.locked,"
                            "p.name,p.attributes->>'address',i.detail "
                            "FROM itinerary_items i LEFT JOIN places p ON p.place_id=i.place_id AND p.tenant_id=i.tenant_id "
                            "WHERE i.tenant_id=%s AND i.trip_id=%s AND i.version=%s ORDER BY i.seq,i.item_id",
                            (tenant, trip_id, version))
                items = []
                for row in cur.fetchall():
                    items.append({"item_id": str(row[0]), "seq": row[1], "kind": row[2], "title": row[3],
                                  "starts_at": row[4].isoformat(), "ends_at": row[5].isoformat() if row[5] else None,
                                  "locked": row[6], "place_name": row[7], "address": row[8],
                                  "detail": _display_detail(row[9])})
                result = {"version": version, "reason": meta[0], "created_at": meta[1].isoformat(), "items": items}
        return _response({"plan": result, "as_of": datetime.now(UTC).isoformat()})

    return router
