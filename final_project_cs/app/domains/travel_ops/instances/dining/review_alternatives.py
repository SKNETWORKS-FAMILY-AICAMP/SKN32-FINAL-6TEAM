# -*- coding: utf-8 -*-
"""확인 화면의 「다른 식당」 후보 — 요식 팀 대체안(`dining.suggest_alternatives`, 마이그레이션 207)을 **등록 전 단계**에서도 부르는 어댑터. `[2026-10-15]`

축마다 한 곳(일정이 덜 밀리는 곳 · 비슷한 곳 · 가까운 곳)을 그 시각 영업 · 식이 조건을 보고 고른다. 채우지 못한 축은 빼고, 고른 식당은
공용 장소 행(요식 원장에서 올린 `places`)과 이어 좌표 · 주소를 붙인다. 원래 식당이 원장에 없으면 `None`(모름).

`[2026-10-18 사용자 지시]` **가게 이름 없는 식사**(「점심」 · 「ㅇㅇ 근처 점심」)는 원래 식당이 없다 — `rank_near` 가 한 지점(줄에 적은 지역 ·
앞뒤 일정) 둘레의 원장 식당에서 고른다. 끼니면 요리 갈래 「카페디저트」를 뺀다(카페 · 디저트는 밥이 아니다 — 실측: 점심에 디저트카페)."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

#: 끼니 식사에서 빼는 원장 요리 갈래(`dn_place.category`, 마이그레이션 214)
NOT_A_MEAL_CATEGORIES = ("카페디저트",)
#: 넓혀 가는 반경(미터) — 이 안에 셋이 있으면 더 넓히지 않는다(가까운 대안이 아니게 되지 않게 — 207 의 사다리와 같은 생각)
NEAR_LADDER_M = (500, 1000, 2000)
#: 한 번에 내는 식당 수 — 축마다 한 곳(덜 밀리는 곳 · 가까운 곳 · 그다음 가까운 곳)
NEAR_TOP = 3


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
        rows = _core_rows(cur, tenant_id, [str(row[2]) for row in picked])
    return {"alternatives": _with_coordinates(picked, rows)}


def near_pool(conn: Any, point: tuple[float, float], starts_at: datetime, ends_at: datetime | None = None, *,
              conditions: tuple[str, ...] = (), meal: bool = True, radius_m: int = 2000, limit: int = 40) -> list[dict[str, Any]]:
    """한 지점 둘레의 원장 식당 — 폐업 아님 · 그 시각 닫힘으로 확인되지 않음 · 식이 조건 어긋남으로 확인되지 않음 · (끼니면) 카페디저트 아님.
    영업이 확인된 곳이 먼저, 그다음 가까운 순. 영업시간을 모르면(`open_state` None) 빼지 않고 뒤에 둔다 — 모르는 것을 닫힘으로 짓지 않는다."""
    with conn.cursor() as cur:
        cur.execute(
            "WITH near AS ("
            "  SELECT p.place_uid, p.name_ko, dining.distance_m(%s::float8, %s::float8, p.lat, p.lng) AS d"
            "    FROM dining.dn_place p"
            "   WHERE p.lat IS NOT NULL AND p.lng IS NOT NULL AND p.record_status <> 'closed'"
            "     AND (NOT %s OR p.category IS NULL OR NOT (p.category = ANY(%s::text[])))"
            "), judged AS ("
            "  SELECT n.place_uid, n.name_ko, n.d,"
            "         dining.open_at_slot(n.place_uid, %s::timestamptz, %s::timestamptz) AS open_state,"
            "         (SELECT CASE WHEN bool_or(dining.meets_condition(n.place_uid, code) IS FALSE) THEN false"
            "                      WHEN bool_or(dining.meets_condition(n.place_uid, code) IS NULL) THEN NULL ELSE true END"
            "            FROM unnest(%s::text[]) AS code) AS cond_state"
            "    FROM near n WHERE n.d <= %s"
            ")"
            " SELECT place_uid::text, name_ko, d, open_state FROM judged"
            "  WHERE open_state IS NOT FALSE AND cond_state IS NOT FALSE"
            "  ORDER BY (open_state IS TRUE) DESC, d LIMIT %s",
            (point[0], point[1], meal, list(NOT_A_MEAL_CATEGORIES), starts_at, ends_at, list(conditions), radius_m, limit))
        return [{"place_uid": uid, "name": name, "distance_m": float(d), "open_state": state}
                for uid, name, d, state in cur.fetchall()]


def rank_near(conn: Any, tenant_id: str, point: tuple[float, float], starts_at: datetime, ends_at: datetime | None = None, *,
              next_point: tuple[float, float] | None = None, conditions: tuple[str, ...] = (), meal: bool = True,
              radius_m: int = 2000) -> dict[str, Any] | None:
    """가게 이름 없는 식사 — 그 지점 둘레 원장 식당에서 축마다 한 곳: 일정이 가장 덜 밀리는 곳(다음 일정이 있을 때) · 가장 가까운 곳 · 그다음 가까운 곳.
    반경은 500m → 1km → 2km(`radius_m` 까지)로 넓히다 셋이 차면 멈춘다. 둘레에 없으면 빈 목록(답했다 — 지어내지 않는다)."""
    with conn.transaction():                                  # 세이브포인트 — 원장 오류가 바깥 트랜잭션을 망가뜨리지 않는다
        pool = near_pool(conn, point, starts_at, ends_at, conditions=conditions, meal=meal, radius_m=radius_m)
        ladder = [m for m in NEAR_LADDER_M if m < radius_m] + [radius_m]
        reach = next((m for m in ladder if sum(1 for row in pool if row["distance_m"] <= m) >= NEAR_TOP), radius_m)
        pool = [row for row in pool if row["distance_m"] <= reach]
        with conn.cursor() as cur:
            rows = _core_rows(cur, tenant_id, [row["place_uid"] for row in pool])
    usable = [row for row in pool if row["place_uid"] in rows and rows[row["place_uid"]][2] is not None]
    confirmed = [row for row in usable if row["open_state"] is True] or usable
    picked: list[tuple[str, str, str, str]] = []
    if next_point is not None and confirmed:
        def detour(row: dict[str, Any]) -> float:
            _, _, lat, lon, _ = rows[row["place_uid"]]
            return row["distance_m"] + _metres(float(lat), float(lon), next_point[0], next_point[1])
        best = min(confirmed, key=detour)
        picked.append(("impact", "일정이 가장 덜 밀리는 곳", best["place_uid"], best["name"]))
    for row in usable:                                        # 영업 확인 → 모름, 그 안에서 가까운 순(near_pool 의 순서)
        if len(picked) >= NEAR_TOP:
            break
        if all(row["place_uid"] != p[2] for p in picked):
            axis = ("nearest", "가장 가까운 곳") if not any(p[0] == "nearest" for p in picked) else ("nearby", "가까운 다른 곳")
            picked.append((*axis, row["place_uid"], row["name"]))
    return {"alternatives": _with_coordinates(picked, rows)}


def _metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 점 사이 직선거리(미터, 하버사인) — 원장 `dining.distance_m` 과 같은 식."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    return 2 * 6_371_000 * math.asin(math.sqrt(math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))


def _core_rows(cur: Any, tenant_id: str, uids: list[str]) -> dict[str, tuple[Any, ...]]:
    """원장 식당 번호 → 공용 장소 행(place_id · 이름 · 좌표 · 주소)."""
    if not uids:
        return {}
    cur.execute("SELECT attributes->>'dining_place_uid', place_id, name, latitude, longitude, attributes->>'address' FROM places "
                "WHERE tenant_id = %s AND source_name='dining_ledger' AND trip_scope IS NULL AND kind='dining' "
                "AND attributes->>'dining_place_uid' = ANY(%s)", (tenant_id, uids))
    return {str(r[0]): r[1:] for r in cur.fetchall()}


def _with_coordinates(picked: list[tuple[Any, ...]], rows: dict[str, tuple[Any, ...]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for axis, label, uid, name in picked:
        row = rows.get(str(uid))
        if row is None or row[2] is None or row[3] is None:
            continue                                          # 공용 장소 행이 없는 식당은 좌표를 몰라 화면에 못 올린다
        place_id, place_name, lat, lon, address = row
        out.append({"place_uid": str(uid), "place_id": str(place_id), "name": place_name or name, "latitude": float(lat),
                    "longitude": float(lon), "address": address, "axis": axis, "axis_label": label})
    return out
