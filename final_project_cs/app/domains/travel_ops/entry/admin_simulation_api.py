"""관리자 웹앱의 여행별 재난 시험. 운영 앱에만 등록한다."""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.application.admin_service import AdminServiceError
from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.itinerary.itinerary import TripStore
from app.domains.travel_ops.components.watch import simulation
from app.domains.travel_ops.entry.admin_simulation_catalogue import catalogue


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
        cur.execute("SELECT status,EXISTS(SELECT 1 FROM trip_safety_pauses p WHERE p.tenant_id=t.tenant_id "
                    "AND p.trip_id=t.trip_id AND p.resumed_at IS NULL) FROM trips t WHERE t.tenant_id=%s AND t.trip_id=%s",
                    (tenant, trip_id))
        status, paused = cur.fetchone()
    eligible_items = [i for i in items if i.kind in ("activity", "dining") and i.place
                      and i.place.get("latitude") is not None and i.place.get("longitude") is not None
                      and (i.ends_at or i.starts_at) > now]
    can_simulate = status == "active" and bool(eligible_items) and not paused
    return {"trip_id": str(trip_id), "title": trip["title"], "version": trip["version"], "configuration": current,
            "can_simulate": can_simulate, "paused": paused,
            "unavailable_reason": "재난으로 정지한 여행입니다. 고객 앱에서 다시 시작한 뒤 시험해 주세요." if paused else
                ("시험할 방문 일정이 남아 있지 않습니다. 저장된 여행 조회만 가능합니다." if not can_simulate else None),
            "items": [{"item_id": str(i.item_id), "title": i.title, "starts_at": i.starts_at.isoformat(),
                       "ends_at": i.ends_at.isoformat() if i.ends_at else None,
                       "weather_sensitive": i.place.get("weather_sensitive"), "ongoing": i.starts_at <= now}
                      for i in eligible_items], "notices": notices, "reports": reports}


def build_router(*, operator_dependency, require_permission) -> APIRouter:
    operator, require = operator_dependency, require_permission
    router = APIRouter(prefix="/admin/api/simulations", tags=["operations-travel-simulation"])

    @router.get("")
    def trips(audience: Literal["monitored", "guest"] = "monitored", date_from: date | None = None,
              date_to: date | None = None, page: Annotated[int, Query(ge=1)] = 1,
              page_size: Annotated[int, Query(ge=1, le=50)] = 10, op=Depends(operator)):
        require(op, "ops:introspect")
        tenant = get_settings().tenant_id
        with get_connection() as conn:
            return catalogue(conn, tenant, audience=audience, date_from=date_from, date_to=date_to,
                             page=page, page_size=page_size)

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
