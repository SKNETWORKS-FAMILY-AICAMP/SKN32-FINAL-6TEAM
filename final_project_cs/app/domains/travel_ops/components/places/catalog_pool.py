# -*- coding: utf-8 -*-
"""활동 대체 후보를 **관광공사 목록에서** 넓힌다 — 일정 짜기와 같은 원천. `[2026-09-29 ui 세션 지적 · 사용자 요구]`

☆왜. 「다른 활동으로 바꿔」가 「10:10에 갈 수 있는 활동이 3km 안에 없어요(살펴본 2곳)」로 끝났다. 바꾸기 계산은 `places` 표만
  봤는데 거기 활동은 서울 전체 12곳뿐이었다(같은 3km 안 관광공사 목록은 1,455곳).
★하는 일: 원래 장소 둘레 반경 안의 목록 활동을 **가까운 순**으로 몇 곳 가져와, **DB 에 읽어 둔 운영시간**을 붙이고
  그 여행 **전용 장소 행**(`trip_scope`, 마이그레이션 029)으로 적는다. 그래야 바꾼 일정 항목이 장소 id 를 가질 수 있다.
★`[2026-09-29 사용자 지시]` **요청 자리에서 관광공사를 부르지 않는다** — 「장소 갱신은 새벽 3시에 한 번, 요청은 DB 만」.
  운영시간은 새벽 작업이 읽어 둔 것(`catalog_hours` 표, 마이그레이션 036)과 다른 여행에서 이미 읽은 장소 행만 쓴다.
  ☆앞 판은 요청마다 관광공사를 최대 10번 불렀다(첫 요청 33초 · 연달아 요청하면 한도) — 백업 `_backup/2026-09-29_catalog_pool_before_dbonly/`.
★운영시간을 모르는 곳은 **적지 않는다**(후보에 안 들어간다) — 모르는 곳을 연다고 하지 않는다. 새벽 작업이 읽으면 다음 요청부터 들어온다.
"""
from __future__ import annotations

import json
import math
import time
from datetime import datetime
from typing import Any, Sequence
from uuid import UUID

from app.domains.travel_ops.components.planning.planner import CONTENT_TYPE_RANK, INDOOR_ASSUMED_BY_CONTENT_TYPE, KIND_BY_CONTENT_TYPE, Cand, _district_of

#: 한 번에 가져오는 목록 활동 수 — ★우리가 고른 값(2026-09-29)
POOL_LIMIT = 10
#: 다른 여행 장소 행에서 읽은 값을 다시 쓰는 기간 — ★우리가 고른 값. 새벽 작업 값(`catalog_hours`)은 목록 수정 시각으로 새로 읽는다
REUSE_DAYS = 14
ACTIVITY_TYPES = [code for code, kind in KIND_BY_CONTENT_TYPE.items() if kind == "activity"]
#: 같은 여행 · 같은 자리를 이미 넓혔나 — (여행 id, 위도, 경도) → 시각. 다시 넓히면 가까운 곳이 이미 적혀 있어 더 먼 10곳을 읽게 된다
_WIDENED: dict[tuple[str, float, float], float] = {}
WIDEN_MEMO_SECONDS = 6 * 3600


def _catalog_tenants(tenant_id: str) -> list[str]:
    """목록은 기본 테넌트에만 있어 그것도 본다."""
    from app.core.settings import get_settings

    return list(dict.fromkeys([tenant_id, get_settings().tenant_id]))


def nearby_activities(conn, tenant_id: str, *, latitude: float, longitude: float, radius_m: float,
                      exclude_names: set[str], limit: int = POOL_LIMIT, types: Sequence[str] | None = None) -> list[Cand]:
    """목록(`place_catalog`)에서 반경 안 활동을 가까운 순으로.

    `types` — 읽을 관광공사 분류 번호. 안 주면 활동 분류(`ACTIVITY_TYPES`)다. ★`[2026-10-07]` 숙소 줄의 후보를 위해 숙박(32)을 읽을 수 있게 열었다
    (전에는 활동 분류만 읽어 「호텔」 줄의 후보가 늘 0 이었다)."""
    dlat = radius_m / 111_000
    dlon = radius_m / (111_000 * max(0.2, math.cos(math.radians(latitude))))
    with conn.cursor() as cur:
        cur.execute(
            "SELECT content_id, content_type_id, title, address, latitude, longitude FROM place_catalog "
            "WHERE tenant_id = ANY(%s) AND source='tour_api' AND content_type_id = ANY(%s) "
            "AND latitude BETWEEN %s AND %s AND longitude BETWEEN %s AND %s "
            "ORDER BY (latitude - %s)^2 + ((longitude - %s) * %s)^2 LIMIT %s",
            (_catalog_tenants(tenant_id), list(types) if types else ACTIVITY_TYPES, latitude - dlat, latitude + dlat, longitude - dlon,
             longitude + dlon, latitude, longitude, math.cos(math.radians(latitude)), limit * 3))
        rows = cur.fetchall()
    out: list[Cand] = []
    for content_id, content_type, title, address, lat, lon in rows:
        if not title or title in exclude_names or any(c.name == title for c in out):
            continue
        out.append(_catalog_cand(content_id, content_type, title, address, lat, lon))
        if len(out) >= limit:
            break
    return out


def _catalog_cand(content_id: Any, content_type: Any, title: str, address: str | None, lat: Any, lon: Any,
                  extra: dict[str, Any] | None = None) -> Cand:
    attributes: dict[str, Any] = {"source": "tour_api", "source_content_id": str(content_id),
                                  "source_content_type_id": str(content_type), "from_catalog": True, **(extra or {})}
    if address:
        attributes["address"] = address
    district = _district_of(address)
    if district:
        attributes["district"] = district
    assumed = INDOOR_ASSUMED_BY_CONTENT_TYPE.get(str(content_type))
    if assumed is not None:
        attributes["indoor_assumed"] = assumed
    return Cand(key=f"tour_{content_id}", name=title, kind="activity", lat=float(lat), lon=float(lon),
                attributes=attributes, origin="place_catalog",
                rank_hint=1 + CONTENT_TYPE_RANK.get(str(content_type), 9))


def nearby_similar(conn, tenant_id: str, *, latitude: float, longitude: float, radius_m: float, lcls: Sequence[str | None],
                   exclude_names: set[str], limit: int = POOL_LIMIT, min_level: int = 1) -> list[Cand]:
    """원래 장소와 **비슷한** 곳을 관광공사 3단계 분류 나무(`raw_json` 의 lclsSystm1·2·3)에서 가까운 순으로. `[2026-10-07 사용자]`

    같은 소분류(3) → 같은 중분류(2) → 같은 대분류(1) 순이다. **그 나무 밖(다른 대분류)은 절대 안 준다** — 분류를 모른다고 약국을 권하지 않는다.
    `lcls` = `(대, 중, 소)` — 뒤쪽이 None 이면(이름이 여러 소분류에 걸침) 아는 단계까지만 쓴다. `min_level` 아래 단계는 안 준다.
    각 후보의 `attributes["similarity"]` = 맞은 단계(3·2·1) · `lcls` = 그 곳의 분류. 단계가 높은 쪽이 앞이고 같은 단계 안에서는 가까운 순이다."""
    depth = sum(1 for _ in __import__("itertools").takewhile(lambda v: v, lcls))
    if depth == 0:
        return []
    dlat = radius_m / 111_000
    dlon = radius_m / (111_000 * max(0.2, math.cos(math.radians(latitude))))
    out: list[Cand] = []
    seen: set[str] = set()
    for level in range(depth, max(min_level, 1) - 1, -1):
        where = " AND ".join(f"raw_json->>'lclsSystm{n}' = %s" for n in range(1, level + 1))
        with conn.cursor() as cur:
            cur.execute(
                "SELECT content_id, content_type_id, title, address, latitude, longitude, "
                "raw_json->>'lclsSystm1', raw_json->>'lclsSystm2', raw_json->>'lclsSystm3' FROM place_catalog "
                f"WHERE tenant_id = ANY(%s) AND source='tour_api' AND {where} "
                "AND latitude BETWEEN %s AND %s AND longitude BETWEEN %s AND %s "
                "ORDER BY (latitude - %s)^2 + ((longitude - %s) * %s)^2 LIMIT %s",
                (_catalog_tenants(tenant_id), *lcls[:level], latitude - dlat, latitude + dlat, longitude - dlon, longitude + dlon,
                 latitude, longitude, math.cos(math.radians(latitude)), limit * 3))
            rows = cur.fetchall()
        for content_id, content_type, title, address, lat, lon, l1, l2, l3 in rows:
            if not title or title in exclude_names or str(content_id) in seen:
                continue
            seen.add(str(content_id))
            out.append(_catalog_cand(content_id, content_type, title, address, lat, lon,
                                     {"similarity": level, "lcls": [l1, l2, l3]}))
        if len(out) >= limit:
            break
    return out[:limit]


def nearby_in_classes(conn, tenant_id: str, *, latitude: float, longitude: float, radius_m: float, lcls2: Sequence[str],
                      exclude_names: set[str], limit: int = POOL_LIMIT) -> list[Cand]:
    """관광공사 **중분류**(`lclsSystm2`)가 주어진 목록 안인 곳을 가까운 순으로 — 「비슷한 경험」 단계가 쓴다(궁궐 · 유적 → 공원 · 둘레길 같은 갈래). `[2026-10-07]`
    각 후보의 `attributes["lcls"]` = 그 곳의 분류. 어느 대분류든 중분류 번호가 목록에 있으면 받는다."""
    if not lcls2:
        return []
    dlat = radius_m / 111_000
    dlon = radius_m / (111_000 * max(0.2, math.cos(math.radians(latitude))))
    with conn.cursor() as cur:
        cur.execute(
            "SELECT content_id, content_type_id, title, address, latitude, longitude, "
            "raw_json->>'lclsSystm1', raw_json->>'lclsSystm2', raw_json->>'lclsSystm3' FROM place_catalog "
            "WHERE tenant_id = ANY(%s) AND source='tour_api' AND raw_json->>'lclsSystm2' = ANY(%s) "
            "AND latitude BETWEEN %s AND %s AND longitude BETWEEN %s AND %s "
            "ORDER BY (latitude - %s)^2 + ((longitude - %s) * %s)^2 LIMIT %s",
            (_catalog_tenants(tenant_id), list(lcls2), latitude - dlat, latitude + dlat, longitude - dlon, longitude + dlon,
             latitude, longitude, math.cos(math.radians(latitude)), limit * 3))
        rows = cur.fetchall()
    out: list[Cand] = []
    for content_id, content_type, title, address, lat, lon, l1, l2, l3 in rows:
        if not title or title in exclude_names or any(c.name == title for c in out):
            continue
        out.append(_catalog_cand(content_id, content_type, title, address, lat, lon, {"lcls": [l1, l2, l3]}))
        if len(out) >= limit:
            break
    return out


def reuse_hours(conn, tenant_id: str, cands: list[Cand], now: datetime) -> dict[str, int]:
    """DB 에 읽어 둔 운영시간을 관광공사 id 로 찾아 붙인다 — ①새벽 작업 표(`catalog_hours`) ②다른 여행의 장소 행."""
    ids = [c.attributes["source_content_id"] for c in cands if c.attributes.get("source_content_id")]
    if not ids:
        return {"nightly": 0, "places": 0}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT content_id, hours_week, hours_read, phone FROM catalog_hours "
            "WHERE tenant_id = ANY(%s) AND source='tour_api' AND content_id = ANY(%s) AND hours_week IS NOT NULL",
            (_catalog_tenants(tenant_id), ids))
        nightly = {row[0]: row[1:] for row in cur.fetchall()}
        cur.execute(
            "SELECT DISTINCT ON (cid) cid, attributes->'hours_week', attributes->'hours_read' FROM ("
            " SELECT COALESCE(source_content_id, attributes->>'source_content_id') AS cid, attributes FROM places"
            " WHERE tenant_id=%s AND attributes ? 'hours_week' AND attributes->'hours_week' <> '{}'::jsonb) p"
            " WHERE cid = ANY(%s) AND (attributes->'hours_read'->>'read_at')::timestamptz > %s - make_interval(days => %s)"
            " ORDER BY cid, attributes->'hours_read'->>'read_at' DESC",
            (tenant_id, ids, now, REUSE_DAYS))
        placed = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
    counts = {"nightly": 0, "places": 0}
    for cand in cands:
        cid = cand.attributes.get("source_content_id")
        if cid in nightly:
            week, read, phone = nightly[cid]
            cand.attributes["hours_week"] = week
            cand.attributes["hours_read"] = {**(read or {}), "from": "catalog_hours"}
            if phone:
                cand.attributes.setdefault("phone", phone)
            counts["nightly"] += 1
        elif cid in placed:
            cand.attributes["hours_week"] = placed[cid][0]
            cand.attributes["hours_read"] = {**(placed[cid][1] or {}), "reused": True}
            counts["places"] += 1
    return counts


def widen_activity_pool(conn, *, tenant_id: str, trip_id: UUID, place: dict[str, Any], known_names: set[str],
                        radius_m: float, now: datetime, memo: bool = True) -> dict[str, Any]:
    """원래 장소 둘레 목록 활동에 DB 의 운영시간을 붙여, 아는 곳만 그 여행 전용 장소 행으로 적는다. **바깥을 부르지 않는다.**
    ★같은 여행 · 같은 자리는 `WIDEN_MEMO_SECONDS` 동안 다시 넓히지 않는다(`_WIDENED`)."""
    if place.get("latitude") is None or place.get("longitude") is None:
        return {"added": 0, "reason": "원래 장소 좌표 없음"}
    if memo:
        # ★`memo=False` — 고객의 **현재 위치**를 출발지로 넓힐 때(`trip_here`). 그 좌표를 프로세스 메모리에도 남기지 않는다
        key = (str(trip_id), round(float(place["latitude"]), 4), round(float(place["longitude"]), 4))
        if time.time() - _WIDENED.get(key, 0.0) < WIDEN_MEMO_SECONDS:
            return {"added": 0, "reason": "이미 넓혔다"}
        _WIDENED[key] = time.time()
    cands = nearby_activities(conn, tenant_id, latitude=float(place["latitude"]), longitude=float(place["longitude"]),
                              radius_m=radius_m, exclude_names=known_names)
    reused = reuse_hours(conn, tenant_id, cands, now)
    known = [c for c in cands if c.attributes.get("hours_week")]
    with conn.transaction(), conn.cursor() as cur:
        for cand in known:
            cur.execute(
                "INSERT INTO places (tenant_id,name,kind,latitude,longitude,weather_sensitive,attributes,trip_scope) "
                "VALUES (%s,%s,'activity',%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id, trip_scope, name, kind) WHERE trip_scope IS NOT NULL "
                "DO UPDATE SET attributes = EXCLUDED.attributes || places.attributes",
                (tenant_id, cand.name, cand.lat, cand.lon, cand.weather_sensitive,
                 json.dumps(cand.attributes, ensure_ascii=False, default=str), trip_id))
    return {"seen": len(cands), "added": len(known), **reused, "unknown_hours": len(cands) - len(known)}


__all__ = ["ACTIVITY_TYPES", "POOL_LIMIT", "REUSE_DAYS", "WIDEN_MEMO_SECONDS", "nearby_activities", "reuse_hours",
           "widen_activity_pool"]
