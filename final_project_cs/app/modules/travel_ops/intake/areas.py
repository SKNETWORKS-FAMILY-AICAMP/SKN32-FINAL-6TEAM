# -*- coding: utf-8 -*-
"""**지명 사전** — 계획 글에 적힌 지역 말(성수 · 이촌동 · 서울역 …)을 좌표 중심 + 반경으로 바꾼다. `[2026-10-03 ui 세션 요청서 「장소 해석 개선」]`

★말을 코드에 박지 않는다 — DB 에 이미 있는 데이터로 만든다(어느 것도 새로 받아 오지 않는다):
    hub       요식 원장(`dining.dn_place.hub`)이 모은 사람들이 몰리는 곳 — 성수 · 경복궁 · 잠실 · 서울역. 그 허브 식당들의 **가운데 좌표**
    dong      관광공사 목록(`place_catalog`)의 주소 끝 괄호 「(성수동2가)」 — 같은 동의 장소들의 **가운데 좌표**(성수동1가 · 2가는 「성수동」으로 합친다)
    district  주소의 구 이름(성동구) — 넓다(반경 4km)
  같은 말이 여러 출처에 있으면 표(`place_terms.yaml` areas.priority)의 순서가 이긴다. 이름 끝의 「동 · 구」를 뗀 짧은 말(성수 · 성동)로도 부른다.
★가운데 좌표는 **중앙값**이다 — 평균은 좌표가 틀린 장소 하나(실측: 같은 「신천동」이 다른 도시에 하나 섞여 표준편차 1.37도)에 끌려간다.
★DB 만 읽는다(바깥을 부르지 않는다). 만든 사전은 프로세스 안에 한 시간 기억한다 — 접수마다 8천 행을 다시 읽지 않게. 요식 원장이 없는 DB 면 그 출처만 빠진다.
"""
from __future__ import annotations

import re
import statistics
import threading
import time
from dataclasses import dataclass
from typing import Any, Iterable

from .places import normalize_full
from .terms import Terms, load_terms

#: 사전을 기억하는 시간(초) — ★우리가 고른 값. 목록은 하루 한 번 새벽에 갱신된다
TTL_SECONDS = 3600
#: 출처마다 이만큼은 모여야 지역으로 쓴다(좌표가 틀린 장소 하나로 지역이 생기는 것을 막는다) — ★우리가 고른 값
MIN_PLACES = {"hub": 3, "dong": 3, "district": 5}

_DONG_PIECE = re.compile(r"^(?P<base>[가-힣]+?)(?:\d+가)?$")
_DISTRICT = re.compile(r"^서울(?:특별시)?\s+(?P<name>[가-힣]+구)(?:\s|$)")


@dataclass(frozen=True)
class Area:
    name: str                      # 화면에 보일 지역 이름(성수동 · 서울역 · 성동구)
    kind: str                      # hub · dong · district
    latitude: float
    longitude: float
    radius_m: int

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "latitude": self.latitude, "longitude": self.longitude,
                "radius_m": self.radius_m}


class AreaIndex:
    """정규화한 말 → 지역. `from_rows` 로 만든다."""

    def __init__(self, by_key: dict[str, Area] | None = None) -> None:
        self._by_key = by_key or {}

    @classmethod
    def from_rows(cls, rows: Iterable[tuple[str, str, float, float]], terms: Terms | None = None) -> "AreaIndex":
        """`rows` = (출처 · 이름 · 위도 · 경도). 출처 순서는 표의 `areas.priority` — 앞이 같은 말을 이긴다."""
        terms = terms or load_terms()
        order = {kind: n for n, kind in enumerate(terms.area_priority)}
        by_key: dict[str, Area] = {}
        for kind, name, lat, lon in sorted(rows, key=lambda r: order.get(r[0], len(order))):
            area = Area(name, kind, float(lat), float(lon), int(terms.area_radius_m.get(kind, 1500)))
            names = [name]
            for suffix in terms.area_short_forms:
                if name.endswith(suffix) and len(name) - len(suffix) >= terms.area_min_length:
                    names.append(name[:-len(suffix)])
            for variant in names:
                key = normalize_full(variant)
                if len(key) >= terms.area_min_length:
                    by_key.setdefault(key, area)
        # 다른 말(홍대 → 서교동) — 가리키는 지역이 사전에 있을 때만. 화면에는 고객이 쓴 말을 이름으로 보인다
        for alias, target in terms.area_aliases.items():
            base = by_key.get(normalize_full(target))
            key = normalize_full(alias)
            if base is not None and key not in by_key:
                by_key[key] = Area(alias, base.kind, base.latitude, base.longitude, base.radius_m)
        return cls(by_key)

    def get(self, key: str) -> Area | None:
        return self._by_key.get(key)

    def keys(self) -> set[str]:
        return set(self._by_key)

    def __len__(self) -> int:
        return len(self._by_key)

    def __contains__(self, key: str) -> bool:
        return key in self._by_key


# ── DB 에서 만들기 ────────────────────────────────────────────────
def _median_rows(kind: str, groups: dict[str, list[tuple[float, float]]]) -> list[tuple[str, str, float, float]]:
    out = []
    for name, points in groups.items():
        if len(points) >= MIN_PLACES[kind]:
            out.append((kind, name, statistics.median(p[0] for p in points), statistics.median(p[1] for p in points)))
    return out


def load_rows(conn, tenant_id: str) -> list[tuple[str, str, float, float]]:
    from .hours import _tenants

    dongs: dict[str, list[tuple[float, float]]] = {}
    districts: dict[str, list[tuple[float, float]]] = {}
    with conn.cursor() as cur:
        cur.execute("SELECT address, latitude, longitude FROM place_catalog WHERE tenant_id = ANY(%s) AND source='tour_api' "
                    "AND address LIKE '서울%%' AND latitude IS NOT NULL AND longitude IS NOT NULL", (_tenants(tenant_id),))
        for address, lat, lon in cur.fetchall():
            point = (float(lat), float(lon))
            district = _DISTRICT.match(address or "")
            if district:
                districts.setdefault(district.group("name"), []).append(point)
            for group in re.findall(r"\(([^)]*)\)", address or ""):
                for piece in (p.strip() for p in group.split(",")):
                    match = _DONG_PIECE.match(piece)
                    base = match.group("base") if match else ""
                    # 동 · 로 로 끝나는 것만 — 건물 이름(「롯데타워」)이 지역이 되지 않게
                    if len(base) >= 2 and base.endswith(("동", "로")):
                        dongs.setdefault(base, []).append(point)
    rows = _median_rows("dong", dongs) + _median_rows("district", districts)
    rows += _hub_rows(conn)
    return rows


def _hub_rows(conn) -> list[tuple[str, str, float, float]]:
    """요식 원장의 허브 — 원장이 없는 DB(시험 · 다른 조립)면 빈 목록."""
    groups: dict[str, list[tuple[float, float]]] = {}
    try:
        with conn.transaction(), conn.cursor() as cur:       # 세이브포인트 — DB 오류가 바깥 트랜잭션을 망가뜨리지 않는다
            cur.execute("SELECT hub, lat, lng FROM dining.dn_place WHERE hub IS NOT NULL AND lat IS NOT NULL AND lng IS NOT NULL")
            for hub, lat, lng in cur.fetchall():
                groups.setdefault(str(hub), []).append((float(lat), float(lng)))
    except Exception as exc:                                  # noqa: BLE001
        if type(exc).__name__ not in ("UndefinedTable", "UndefinedColumn", "InvalidSchemaName", "InsufficientPrivilege"):
            raise
        return []
    return _median_rows("hub", groups)


_lock = threading.Lock()
_cache: dict[tuple[str, ...], tuple[float, AreaIndex]] = {}


def areas_for(conn, tenant_id: str, terms: Terms | None = None) -> AreaIndex:
    """이 테넌트가 보는 지명 사전 — 한 시간 기억한다. 만들다 실패하면 **빈 사전**이다(지역 말을 못 알아볼 뿐 읽기는 계속된다)."""
    from .hours import _tenants

    key = tuple(_tenants(tenant_id))
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < TTL_SECONDS:
            return hit[1]
    try:
        index = AreaIndex.from_rows(load_rows(conn, tenant_id), terms)
    except Exception:                                       # noqa: BLE001 — 사전 장애가 계획 읽기를 막지 않는다
        import logging

        logging.getLogger(__name__).warning("area index build failed tenant=%s", tenant_id, exc_info=True)
        return AreaIndex()
    with _lock:
        _cache[key] = (now, index)
    return index


def reset() -> None:
    """시험용 — 기억한 사전을 비운다."""
    with _lock:
        _cache.clear()


__all__ = ["Area", "AreaIndex", "MIN_PLACES", "TTL_SECONDS", "areas_for", "load_rows", "reset"]
