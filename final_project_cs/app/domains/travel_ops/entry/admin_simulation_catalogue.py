"""재난 시험 여행 목록: 한국 날짜 범위·게스트 분리·DB 페이지 조회."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import HTTPException

from app.domains.travel_ops.components.itinerary.trip_scope import extra_sql
from app.domains.travel_ops.components.watch.simulation import CATEGORIES
from app.domains.travel_ops.modules.web_account.guest_policy import not_guest_sql


def catalogue(conn, tenant: str, *, audience: Literal["monitored", "guest"],
              date_from: date | None, date_to: date | None, page: int, page_size: int) -> dict:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "조회 시작일은 종료일보다 늦을 수 없습니다.")
    filters = ["t.tenant_id=%s"]
    values: list = [tenant]
    guest = not_guest_sql("t")
    if audience == "guest":
        filters.append(f"NOT ({guest})")
    else:
        filters += ["t.status='active'", guest, extra_sql("t"), "period.ends_at>now()"]
    if date_from:
        filters.append("(period.ends_at AT TIME ZONE 'Asia/Seoul')::date >= %s")
        values.append(date_from)
    if date_to:
        filters.append("(period.starts_at AT TIME ZONE 'Asia/Seoul')::date <= %s")
        values.append(date_to)
    source = (
        "FROM trips t CROSS JOIN LATERAL (SELECT min(i.starts_at) AS starts_at, "
        "max(COALESCE(i.ends_at,i.starts_at)) AS ends_at FROM itinerary_items i "
        "WHERE i.tenant_id=t.tenant_id AND i.trip_id=t.trip_id AND i.version=t.latest_version) period "
        "WHERE " + " AND ".join(filters)
    )
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) " + source, values)
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT t.trip_id,t.title,period.starts_at,period.ends_at,t.status, "
            "EXISTS(SELECT 1 FROM trip_safety_pauses p WHERE p.tenant_id=t.tenant_id "
            "AND p.trip_id=t.trip_id AND p.resumed_at IS NULL), "
            "EXISTS(SELECT 1 FROM itinerary_items i JOIN places p ON p.tenant_id=i.tenant_id "
            "AND p.place_id=i.place_id WHERE i.tenant_id=t.tenant_id AND i.trip_id=t.trip_id "
            "AND i.version=t.latest_version AND i.kind IN ('activity','dining') "
            "AND p.latitude IS NOT NULL AND p.longitude IS NOT NULL "
            "AND COALESCE(i.ends_at,i.starts_at)>now()) " + source +
            " ORDER BY t.created_at DESC,t.trip_id DESC LIMIT %s OFFSET %s",
            [*values, page_size, (page - 1) * page_size],
        )
        trips = [{"trip_id": str(identity), "title": title,
                  "starts_at": start.isoformat() if start else None,
                  "ends_at": end.isoformat() if end else None,
                  "paused": paused, "can_simulate": status == "active" and available and not paused}
                 for identity, title, start, end, status, paused, available in cur.fetchall()]
    return {"trips": trips, "categories": [{"key": key, "label": label} for key, label in CATEGORIES.items()],
            "total": total, "page": page, "page_size": page_size, "total_pages": (total + page_size - 1) // page_size}
