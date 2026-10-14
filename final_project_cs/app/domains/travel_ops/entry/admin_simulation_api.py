"""관리자 웹앱의 여행별 재난 시험. 운영 앱에만 등록한다."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.application.admin_service import AdminServiceError
from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.itinerary.itinerary import TripStore
from app.domains.travel_ops.components.itinerary.trip_scope import extra_sql as scope_sql
from app.domains.travel_ops.components.watch import simulation


class Configuration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_revision: Annotated[int, Field(strict=True, ge=0)]
    expected_version: Annotated[int, Field(strict=True, ge=1)]
    item_id: UUID | None = None
    categories: Annotated[list[str], Field(max_length=6)]
    duration_minutes: Annotated[int, Field(strict=True, ge=1, le=60)] = 15
    reason: Annotated[str, Field(min_length=1, max_length=500, pattern=r"\S")]


def _view(conn, tenant: str, trip_id: UUID) -> dict:
    store = TripStore(tenant)
    try:
        trip, items = store.latest(conn, trip_id)
    except KeyError:
        raise HTTPException(404, "여행을 찾을 수 없습니다.") from None
    current = simulation.state(conn, tenant, trip_id)
    now = datetime.now(UTC)
    with conn.cursor() as cur:
        cur.execute("SELECT dedupe_key,payload_json,available_at FROM outbox WHERE tenant_id=%s AND topic='trip.notice' "
                    "AND dedupe_key LIKE %s AND payload_json->>'simulation_id'=%s ORDER BY available_at DESC LIMIT 20",
                    (tenant, f"{trip_id}:%", current.get("run_id")))
        notices = [{"key": key, "text": payload.get("text"), "at": at.isoformat()} for key, payload, at in cur.fetchall()]
        cur.execute("SELECT id,value FROM admin_records WHERE tenant_id=%s AND kind='watch_simulation_result' AND id IN (%s,%s)",
                    (tenant, f"{current.get('run_id')}:full", f"{current.get('run_id')}:safety"))
        reports = {key.rsplit(':',1)[-1]: value for key, value in cur.fetchall()}
    return {"trip_id": str(trip_id), "title": trip["title"], "version": trip["version"], "configuration": current,
            "items": [{"item_id": str(i.item_id), "title": i.title, "starts_at": i.starts_at.isoformat(),
                       "ends_at": i.ends_at.isoformat() if i.ends_at else None,
                       "weather_sensitive": i.place.get("weather_sensitive"), "ongoing": i.starts_at <= now}
                      for i in items if i.kind in ("activity", "dining") and i.place
                      and i.place.get("latitude") is not None and i.place.get("longitude") is not None
                      and (i.ends_at or i.starts_at) > now], "notices": notices, "reports": reports}


def build_router(*, operator_dependency, require_permission) -> APIRouter:
    operator, require = operator_dependency, require_permission
    router = APIRouter(prefix="/admin/api/simulations", tags=["operations-travel-simulation"])

    @router.get("")
    def trips(op=Depends(operator)):
        require(op, "ops:introspect")
        tenant = get_settings().tenant_id
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT t.trip_id,t.title FROM trips t WHERE t.tenant_id=%s AND t.status='active' AND " + scope_sql("t") + " "
                        "AND EXISTS (SELECT 1 FROM itinerary_items i WHERE i.tenant_id=t.tenant_id AND i.trip_id=t.trip_id "
                        "AND i.version=t.latest_version AND COALESCE(i.ends_at,i.starts_at)>now()) ORDER BY t.created_at DESC",
                        (tenant,))
            rows = cur.fetchall()
        return {"trips": [{"trip_id": str(identity), "title": title} for identity, title in rows],
                "categories": [{"key": key, "label": label} for key, label in simulation.CATEGORIES.items()]}

    @router.get("/{trip_id}")
    def view(trip_id: UUID, op=Depends(operator)):
        require(op, "ops:introspect")
        with get_connection() as conn:
            return _view(conn, get_settings().tenant_id, trip_id)

    @router.patch("/{trip_id}")
    def configure(trip_id: UUID, body: Configuration, op=Depends(operator)):
        require(op, "limits:write")
        tenant = get_settings().tenant_id
        with get_connection() as conn, conn.transaction():
            try:
                simulation.configure(conn, tenant, trip_id, actor=op.id, **body.model_dump())
            except AdminServiceError as exc:
                raise HTTPException(exc.status_code, exc.detail) from None
            return _view(conn, tenant, trip_id)

    return router
