# -*- coding: utf-8 -*-
"""공공 대피 장소(`safety_shelters`)에서 **가까운 곳**을 찾는다. `[결정 2026-10-06 사용자]`

★자료는 `scripts/load_safety_shelters.py` 가 받아 둔 공공 파일(행정안전부 민방위 대피시설 · 지진 옥외대피장소 등)에서 적재한다. 이 파일은 읽기만 한다 — **표에 없는 대피 장소를 만들지 않는다.**
★거리는 **직선거리**다(도보 길이 아니다). 걷는 시간은 직선거리 ÷ 걷는 속도의 **추정**이고, 알림이 「추정」이라고 밝힌다.
★찾는 반경(`travel.safety.shelters.search_radius_km`) 밖은 안 쓴다 — 먼 곳을 가까운 곳처럼 알리지 않는다. 반경 안에 없으면 빈 목록이고, 표가 통째로 비었는지(`has_data`)는 따로 안다
  (비어 있으면 「자료를 아직 못 불러왔어요」, 자료는 있는데 근처에 없으면 「근처에서 찾지 못했어요」 — 둘은 다른 말이다).
"""
from __future__ import annotations

import math
from typing import Any, Iterable
from urllib.parse import urlencode

#: 위도 1도 ≈ 111 km. 경도 1도는 위도에 따라 줄어든다 — 상자(위도·경도 범위)로 먼저 거르고 정확한 거리는 SQL 이 센다
_KM_PER_DEGREE = 111.0


def walk_minutes(distance_m: float, speed_kmh: float) -> int:
    """직선거리 → 걷는 시간(분, 올림) **추정**. 속도가 0 이하면 0 이 아니라 오류다 — 지어낸 시간을 내지 않는다."""
    if speed_kmh <= 0:
        raise ValueError("걷는 속도는 0 보다 커야 한다")
    return max(1, math.ceil(distance_m / (speed_kmh * 1000 / 60)))


def walking_directions_url(origin: tuple[float, float], destination: tuple[float, float]) -> str:
    """구글 지도 **걸어서 길찾기** 링크 — 열면 고객 자기 지도 앱이 길을 안내한다. ★키가 필요 없는 공식 링크 형식이라 서버가 길을 계산하지 않는다(우리 쪽 거짓 길안내가 없다)."""
    return "https://www.google.com/maps/dir/?" + urlencode({"api": 1, "origin": f"{origin[0]},{origin[1]}", "destination": f"{destination[0]},{destination[1]}",
                                                            "travelmode": "walking"})


def has_data(conn, types: Iterable[str]) -> bool:
    """이 종류의 대피 장소 자료가 표에 **한 줄이라도** 있나."""
    with conn.cursor() as cur:
        cur.execute("SELECT EXISTS (SELECT 1 FROM safety_shelters WHERE shelter_type = ANY(%s))", (list(types),))
        return bool(cur.fetchone()[0])


def nearest(conn, *, latitude: float, longitude: float, types: Iterable[str], limit: int, radius_km: float,
            speed_kmh: float) -> list[dict[str, Any]]:
    """`(위도, 경도)` 에서 가까운 대피 장소 — 가까운 순 `limit` 곳. 반경 밖 · 좌표 없는 곳은 안 나온다."""
    delta_lat = radius_km / _KM_PER_DEGREE
    delta_lon = radius_km / (_KM_PER_DEGREE * max(0.01, math.cos(math.radians(latitude))))
    with conn.cursor() as cur:
        cur.execute(
            "SELECT shelter_type, name, address, latitude, longitude, underground, capacity, source, "
            "       6371000 * 2 * asin(sqrt(power(sin(radians(latitude - %(lat)s) / 2), 2) "
            "         + cos(radians(%(lat)s)) * cos(radians(latitude)) * power(sin(radians(longitude - %(lon)s) / 2), 2))) AS distance_m "
            "FROM safety_shelters "
            "WHERE shelter_type = ANY(%(types)s) AND latitude BETWEEN %(lat)s - %(dlat)s AND %(lat)s + %(dlat)s "
            "  AND longitude BETWEEN %(lon)s - %(dlon)s AND %(lon)s + %(dlon)s "
            "ORDER BY distance_m, name LIMIT %(limit)s",
            {"lat": latitude, "lon": longitude, "types": list(types), "dlat": delta_lat, "dlon": delta_lon, "limit": max(1, int(limit)) * 4})
        rows = cur.fetchall()
    out = []
    for kind, name, address, lat, lon, underground, capacity, source, distance in rows:
        if distance > radius_km * 1000:
            continue                                      # 상자의 모서리 — 원 밖이다
        out.append({"type": kind, "name": name, "address": address, "latitude": lat, "longitude": lon, "underground": underground,
                    "capacity": capacity, "source": source, "distance_m": int(round(distance)),
                    "walk_minutes_estimate": walk_minutes(distance, speed_kmh)})
        if len(out) >= limit:
            break
    return out


__all__ = ["has_data", "nearest", "walk_minutes", "walking_directions_url"]
