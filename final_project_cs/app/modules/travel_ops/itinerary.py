# -*- coding: utf-8 -*-
"""여행 일정 저장소 — Trip · 일정 버전 · 항목 (v11 §7-B · §6-C-6·7).

★**일정은 버전으로 쌓는다.** 바꿀 때 항목을 고치지 않고 새 버전을 통째로 쓴다.
  되돌림은 옛 버전을 다시 쓰는 것이다.

★★**낡은 쓰기를 거부한다**(§6-C-7). 새 버전은 `trips.latest_version = 기준 버전`
  조건으로만 올린다. 그 사이 다른 쪽이 먼저 올렸으면 `StaleItinerary` 다 —
  옛 기준으로 계산한 후보를 그대로 밀어 넣지 않는다.

★**저장과 통지를 같은 트랜잭션에 넣는다**(§6-C-6). 버전·포인터·바깥함 삽입을 함께
  커밋한다. 호출자가 트랜잭션을 쥔다 — `transition_case()` 와 같은 모양이다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from typing import Any
from uuid import UUID, uuid4


class StaleItinerary(RuntimeError):
    """기준 버전이 낡았다 — 다른 쪽이 먼저 일정을 바꿨다."""


@dataclass
class Item:
    item_id: UUID
    seq: int
    kind: str
    title: str
    place_id: UUID | None
    starts_at: datetime
    ends_at: datetime | None
    locked: bool = False
    booking_id: UUID | None = None
    replaces_item_id: UUID | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    place: dict[str, Any] | None = None      # 읽을 때 붙는 장소(판정용)

    def replaced_by(self, *, place: dict[str, Any] | None, title: str,
                    detail: dict[str, Any] | None = None, starts_at: datetime | None = None,
                    ends_at: datetime | None = None) -> "Item":
        """★같은 순서의 대체 항목. **원래 항목을 가리킨다**(§6-C-2 — 편법 방지).

        장소가 없으면(이동 항목) 원래 장소 칸을 그대로 둔다. 시각을 안 주면 그대로다.
        """
        return Item(item_id=uuid4(), seq=self.seq, kind=self.kind, title=title,
                    place_id=UUID(str(place["place_id"])) if place else self.place_id,
                    starts_at=starts_at or self.starts_at,
                    ends_at=ends_at if ends_at is not None else self.ends_at,
                    locked=False, booking_id=None, replaces_item_id=self.item_id,
                    detail=detail if detail is not None else dict(self.detail),
                    place=place if place else self.place)


PLACE_COLUMNS = ("place_id", "name", "kind", "latitude", "longitude",
                 "weather_sensitive", "attributes")


def _place(row: tuple) -> dict[str, Any]:
    place = dict(zip(PLACE_COLUMNS, row))
    place["place_id"] = str(place["place_id"])
    attributes = place.get("attributes") or {}
    # ★판정이 바로 쓰는 속성은 위로 올린다 — 점검은 `district` 를 장소에서 읽는다.
    return {**attributes, **place, "attributes": attributes}


class TripStore:
    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id

    # ── 만들기 ──────────────────────────────────────────────────
    def create_trip(self, conn, *, customer_id: UUID, title: str, locale: str | None,
                    party_size: int | None, items: list[Item],
                    constraints: dict[str, Any] | None = None) -> tuple[UUID, int]:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO trips (tenant_id, customer_id, title, locale, party_size, constraints) "
                "VALUES (%s,%s,%s,%s,%s,%s) RETURNING trip_id",
                (self.tenant_id, customer_id, title, locale, party_size,
                 json.dumps(constraints or {}, ensure_ascii=False)))
            trip_id = cur.fetchone()[0]
        version = self.append_version(conn, trip_id=trip_id, base_version=0, items=items,
                                      reason="created", causes=[])
        return trip_id, version

    # ── 읽기 ────────────────────────────────────────────────────
    def latest(self, conn, trip_id: UUID) -> tuple[dict[str, Any], list[Item]]:
        with conn.cursor() as cur:
            cur.execute("SELECT trip_id, customer_id, title, locale, party_size, latest_version, "
                        "constraints FROM trips WHERE tenant_id=%s AND trip_id=%s",
                        (self.tenant_id, trip_id))
            row = cur.fetchone()
        if row is None:
            raise KeyError(f"trip {trip_id} 없음")
        trip = dict(zip(("trip_id", "customer_id", "title", "locale", "party_size",
                         "version", "constraints"), row))
        return trip, self.items(conn, trip_id, trip["version"])

    def items(self, conn, trip_id: UUID, version: int) -> list[Item]:
        select = ", ".join(f"p.{c}" for c in PLACE_COLUMNS)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT i.item_id, i.seq, i.kind, i.title, i.place_id, i.starts_at, i.ends_at, "
                "i.locked, i.booking_id, i.replaces_item_id, i.detail, " + select + " "
                "FROM itinerary_items i LEFT JOIN places p ON p.place_id = i.place_id "
                "AND p.tenant_id = i.tenant_id "
                "WHERE i.tenant_id=%s AND i.trip_id=%s AND i.version=%s ORDER BY i.seq",
                (self.tenant_id, trip_id, version))
            rows = cur.fetchall()
        out = []
        for row in rows:
            item = Item(*row[:11])
            item.place = _place(row[11:]) if row[11] is not None else None
            out.append(item)
        return out

    def due(self, conn, *, start: datetime, end: datetime) -> list[tuple[UUID, Item]]:
        """최신 버전에서 `[start, end)` 에 시작하는 항목. 감시 루프가 읽는다."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT t.trip_id, t.latest_version FROM trips t "
                "WHERE t.tenant_id=%s AND t.status='active'", (self.tenant_id,))
            trips = cur.fetchall()
        found = []
        for trip_id, version in trips:
            for item in self.items(conn, trip_id, version):
                if start <= item.starts_at < end:
                    found.append((trip_id, item))
        return found

    def places(self, conn) -> list[dict[str, Any]]:
        with conn.cursor() as cur:
            cur.execute("SELECT " + ", ".join(PLACE_COLUMNS) + " FROM places WHERE tenant_id=%s",
                        (self.tenant_id,))
            return [_place(row) for row in cur.fetchall()]

    # ── 쓰기 ────────────────────────────────────────────────────
    def append_version(self, conn, *, trip_id: UUID, base_version: int, items: list[Item],
                       reason: str, causes: list[dict[str, Any]],
                       case_id: UUID | None = None) -> int:
        """`base_version` 위에 새 버전을 쓴다. ★기준이 낡았으면 `StaleItinerary`."""
        new_version = base_version + 1
        with conn.cursor() as cur:
            cur.execute("UPDATE trips SET latest_version=%s WHERE tenant_id=%s AND trip_id=%s "
                        "AND latest_version=%s RETURNING trip_id",
                        (new_version, self.tenant_id, trip_id, base_version))
            if cur.fetchone() is None:
                raise StaleItinerary(f"trip {trip_id}: 기준 버전 {base_version} 이 낡았다")
            cur.execute("INSERT INTO itinerary_versions (trip_id, version, tenant_id, reason, "
                        "cause_json, case_id) VALUES (%s,%s,%s,%s,%s,%s)",
                        (trip_id, new_version, self.tenant_id, reason,
                         json.dumps(causes, ensure_ascii=False, default=str), case_id))
            for item in items:
                cur.execute(
                    "INSERT INTO itinerary_items (item_id, trip_id, version, tenant_id, seq, kind, "
                    "title, place_id, starts_at, ends_at, locked, booking_id, replaces_item_id, "
                    "detail) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (item.item_id, trip_id, new_version, self.tenant_id, item.seq, item.kind,
                     item.title, item.place_id, item.starts_at, item.ends_at, item.locked,
                     item.booking_id, item.replaces_item_id,
                     json.dumps(item.detail, ensure_ascii=False, default=str)))
        return new_version

    def enqueue_notice(self, conn, *, trip_id: UUID, version: int,
                       payload: dict[str, Any]) -> None:
        """★적용된 일정 버전당 통지 하나(§6-C-6). 같은 버전을 두 번 넣으면 막힌다."""
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO outbox (tenant_id, topic, dedupe_key, payload_json) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT (tenant_id, topic, dedupe_key) DO NOTHING",
                (self.tenant_id, "trip.notice", f"{trip_id}:v{version}",
                 json.dumps(payload, ensure_ascii=False, default=str)))


__all__ = ["Item", "StaleItinerary", "TripStore"]
