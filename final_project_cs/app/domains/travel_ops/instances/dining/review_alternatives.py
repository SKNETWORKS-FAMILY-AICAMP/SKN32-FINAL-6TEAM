# -*- coding: utf-8 -*-
"""확인 화면의 「다른 식당」 후보 — 요식 팀 대체안(`dining.suggest_alternatives`, 마이그레이션 207)을 **등록 전 단계**에서도 부르는 어댑터. `[2026-10-15]`

축마다 한 곳(일정이 덜 밀리는 곳 · 비슷한 곳 · 가까운 곳)을 그 시각 영업 · 식이 조건을 보고 고른다. 채우지 못한 축은 빼고, 고른 식당은
공용 장소 행(요식 원장에서 올린 `places`)과 이어 좌표 · 주소를 붙인다. 원래 식당이 원장에 없으면 `None`(모름)."""
from __future__ import annotations

from datetime import datetime
from typing import Any


def rank(conn: Any, tenant_id: str, place_uid: str, starts_at: datetime, ends_at: datetime | None = None, *,
         next_point: tuple[float, float] | None = None, conditions: tuple[str, ...] = ()) -> dict[str, Any] | None:
    with conn.transaction(), conn.cursor() as cur:            # 세이브포인트 — 원장 오류가 바깥 트랜잭션을 망가뜨리지 않는다
        cur.execute("SELECT 1 FROM dining.dn_place WHERE place_uid = %s", (place_uid,))
        if cur.fetchone() is None:
            return None
        lat, lng = (next_point or (None, None))
        cur.execute("SELECT axis, axis_label, place_uid, name_ko FROM dining.suggest_alternatives(%s, %s, %s, %s, %s, %s) "
                    "WHERE place_uid IS NOT NULL", (place_uid, starts_at, ends_at, list(conditions), lat, lng))
        picked = cur.fetchall()
        uids = [str(row[2]) for row in picked]
        rows: dict[str, tuple[Any, ...]] = {}
        if uids:
            cur.execute("SELECT attributes->>'dining_place_uid', place_id, name, latitude, longitude, attributes->>'address' FROM places "
                        "WHERE tenant_id = %s AND source_name='dining_ledger' AND trip_scope IS NULL AND kind='dining' "
                        "AND attributes->>'dining_place_uid' = ANY(%s)", (tenant_id, uids))
            rows = {str(r[0]): r[1:] for r in cur.fetchall()}
    out: list[dict[str, Any]] = []
    for axis, label, uid, name in picked:
        row = rows.get(str(uid))
        if row is None or row[2] is None or row[3] is None:
            continue                                          # 공용 장소 행이 없는 식당은 좌표를 몰라 화면에 못 올린다
        place_id, place_name, lat, lon, address = row
        out.append({"place_uid": str(uid), "place_id": str(place_id), "name": place_name or name, "latitude": float(lat),
                    "longitude": float(lon), "address": address, "axis": axis, "axis_label": label})
    return {"alternatives": out}
