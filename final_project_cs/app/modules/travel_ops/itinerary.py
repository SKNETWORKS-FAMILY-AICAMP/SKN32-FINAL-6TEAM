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

from .guest_policy import not_guest_sql


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


def _iso(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment else None


def _uuid(value: Any) -> UUID | None:
    return None if value in (None, "") else UUID(str(value))


def item_to_dict(item: Item) -> dict[str, Any]:
    """항목을 JSON 으로 — 읽기 도구의 결과와 제안 인자(`itinerary.apply`)가 이 모양을 쓴다."""
    return {"item_id": str(item.item_id), "seq": item.seq, "kind": item.kind, "title": item.title,
            "place_id": str(item.place_id) if item.place_id else None,
            "starts_at": _iso(item.starts_at), "ends_at": _iso(item.ends_at),
            "locked": item.locked, "booking_id": str(item.booking_id) if item.booking_id else None,
            "replaces_item_id": str(item.replaces_item_id) if item.replaces_item_id else None,
            "detail": item.detail, "place": item.place}


def item_from_dict(data: dict[str, Any]) -> Item:
    """`item_to_dict` 의 반대. ★시각은 오프셋이 붙은 ISO 문자열이어야 한다 — 없으면 거부한다."""
    starts = datetime.fromisoformat(str(data["starts_at"]))
    ends = datetime.fromisoformat(str(data["ends_at"])) if data.get("ends_at") else None
    for moment in (starts, ends):
        if moment is not None and moment.tzinfo is None:
            raise ValueError("itinerary item time must carry a UTC offset")
    return Item(item_id=UUID(str(data["item_id"])), seq=int(data["seq"]), kind=str(data["kind"]),
                title=str(data["title"]), place_id=_uuid(data.get("place_id")), starts_at=starts,
                ends_at=ends, locked=bool(data.get("locked", False)),
                booking_id=_uuid(data.get("booking_id")),
                replaces_item_id=_uuid(data.get("replaces_item_id")),
                detail=dict(data.get("detail") or {}), place=data.get("place"))


PLACE_COLUMNS = ("place_id", "name", "kind", "latitude", "longitude",
                 "weather_sensitive", "attributes")


def _place(row: tuple) -> dict[str, Any]:
    place = dict(zip(PLACE_COLUMNS, row))
    place["place_id"] = str(place["place_id"])
    attributes = place.get("attributes") or {}
    # ★판정이 바로 쓰는 속성은 위로 올린다 — 점검은 `district` 를 장소에서 읽는다.
    return {**attributes, **place, "attributes": attributes}


#: ★`[2026-09-29]` 관광공사 신분류에서 **실내·야외가 확실한 것만**(True = 야외). 대분류 NA(자연)는 통째로 야외,
#:  VE(문화시설)는 **중분류로만** 가른다 — 처음엔 VE 를 통째로 실내로 뒀다가 낙산공원(VE03)이 「야외 아님」이 됐다
#:  (브라우저 시험에서 발견). 로컬 카탈로그를 중분류별로 뽑아 확인한 갈래:
#:    야외  VE01 동상·기념물 · VE03 공원·광장 · VE04 둘레길
#:    실내  VE06 공연장 · VE07 전시관·갤러리·박물관 · VE09 문화원·도서관
#:  섞인 갈래(VE02 테마파크 — 아쿠아리움과 공원 · VE10 체육시설 · 역사 HS · 쇼핑 SH …)는 넣지 않는다 —
#:  분류만으로 정하면 멀쩡한 일정이 바뀐다(코덱스 합의). 남은 모름은 날씨 사건 때 **먼저 묻는다**(`pending.needs_consent`)
WEATHER_BY_LARGE_CLASS = {"NA": True}
WEATHER_BY_MIDDLE_CLASS = {"VE01": True, "VE03": True, "VE04": True,
                           "VE06": False, "VE07": False, "VE09": False}


def weather_case_sql() -> str:
    """분류 → 실내·야외 CASE 식(모르면 NULL). 값은 이 모듈의 상수뿐이다 — 바깥 입력을 끼우지 않는다."""
    large = " ".join(f"WHEN pc.raw_json->>'lclsSystm1' = '{code}' THEN {str(value).lower()}"
                     for code, value in WEATHER_BY_LARGE_CLASS.items())
    middle = " ".join(f"WHEN pc.raw_json->>'lclsSystm2' = '{code}' THEN {str(value).lower()}"
                      for code, value in WEATHER_BY_MIDDLE_CLASS.items())
    return f"CASE {large} {middle} END"


def fill_weather_sensitive(conn, tenant_id: str) -> int:
    """실내·야외를 **모르는**(NULL) 장소를 확실한 관광공사 분류로 채운다. 채운 행 수. ★아는 값은 건드리지 않는다."""
    case = weather_case_sql()
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE places p SET weather_sensitive = {case} "
            "FROM place_catalog pc WHERE p.tenant_id = %s AND p.weather_sensitive IS NULL "
            "AND pc.tenant_id = p.tenant_id AND pc.source = 'tour_api' "
            "AND pc.content_id = COALESCE(p.source_content_id, p.attributes->>'source_content_id') "
            f"AND ({case}) IS NOT NULL", (tenant_id,))
        return cur.rowcount


def weather_from_class(lcls1: str | None, lcls2: str | None) -> bool | None:
    """`weather_case_sql` 과 같은 규칙의 파이썬 판. 모르면 None."""
    if lcls1 in WEATHER_BY_LARGE_CLASS:
        return WEATHER_BY_LARGE_CLASS[lcls1]
    return WEATHER_BY_MIDDLE_CLASS.get(lcls2 or "")


#: 대체 활동 후보로 쓰지 않는 관광공사 대분류 — 음식(FD)·숙박(AC)
_NOT_ACTIVITY = ("FD", "AC")


def catalog_activity_places(conn, tenant_id: str, trip_id: UUID, *, near: dict[str, Any], radius_m: int,
                            exclude_names: set[str], limit: int = 200) -> list[dict[str, Any]]:
    """★`[2026-09-29]` 관광공사 장소 목록에서 **가까운 활동 후보** — 아직 우리 장소가 아니다(가상 행).

    ☆왜 — 비 올 때 대체 후보가 등록된 장소(공용 소수 + 이 여행 것)에서만 나와, 경복궁 600m 안 후보가 0이었다(브라우저 시험).
    ★`place_id` 는 (테넌트·여행·관광공사 id) 로 정해지는 UUID 다 — 고객이 고르면 **그때** 이 id 로 그 여행 전용 행을
      등록한다(`TripStore.add_catalog_place`). 미리 등록하지 않는다(코덱스 합의 — 고아 행을 만들지 않는다).
    ★영업시간·가격은 목록에 없다 — 모른다. 제안(고객이 고른다)에만 경고와 함께 쓰고 자동 적용에는 쓰지 않는다.
    ★이미 우리 장소에 같은 이름이 있으면 뺀다(`exclude_names`) — 같은 곳을 두 행으로 만들지 않는다.
    """
    import math
    from uuid import NAMESPACE_URL, uuid5

    lat, lon = near.get("latitude"), near.get("longitude")
    if lat is None or lon is None:
        return []
    dlat = radius_m / 111_000
    dlon = radius_m / (111_000 * max(0.1, math.cos(math.radians(float(lat)))))
    with conn.cursor() as cur:
        cur.execute(
            "SELECT content_id, content_type_id, title, latitude, longitude, raw_json->>'lclsSystm1', "
            "raw_json->>'lclsSystm2', raw_json->>'lclsSystm3', raw_json->>'sigungucode' FROM place_catalog "
            "WHERE tenant_id=%s AND source='tour_api' AND latitude BETWEEN %s AND %s "
            "AND longitude BETWEEN %s AND %s AND COALESCE(raw_json->>'lclsSystm1','') <> ALL(%s) "
            "ORDER BY content_id LIMIT %s",
            (tenant_id, float(lat) - dlat, float(lat) + dlat, float(lon) - dlon, float(lon) + dlon,
             list(_NOT_ACTIVITY), limit))
        rows = cur.fetchall()
    out = []
    for content_id, type_id, title, plat, plon, l1, l2, l3, sgg in rows:
        if not title or title in exclude_names or plat is None or plon is None:
            continue
        pid = uuid5(NAMESPACE_URL, f"tripilot:catalog:{tenant_id}:{trip_id}:tour_api:{content_id}")
        out.append({"place_id": str(pid), "name": title, "kind": "activity",
                    "latitude": float(plat), "longitude": float(plon),
                    "weather_sensitive": weather_from_class(l1, l2),
                    "attributes": {"source": "tour_api", "source_content_id": str(content_id),
                                   **({"source_content_type_id": str(type_id)} if type_id else {}),
                                   "catalog_pending": True},
                    "catalog_class": _catalog_class((l1, l2, l3, sgg)), "trip_scope": str(trip_id)})
    return out


def _catalog_class(values: tuple) -> dict[str, str] | None:
    """관광공사 분류 네 값 → `{"lcls1", "lcls2", "lcls3", "sigungu"}`. 넷 다 없으면 None(모름)."""
    keys = ("lcls1", "lcls2", "lcls3", "sigungu")
    found = {key: str(value) for key, value in zip(keys, values) if value}
    return found or None


#: 시연 대본 장소 표시 — 장소 `attributes.scenario_seed`. ★`[2026-09-29 ui 세션 지적]` 대본 여행을 실서비스 테넌트에
#:  등록하자 대본의 가짜 지점(「명동 대형마트(시나리오 지점)」 · 「잠실 스카이타워」)이 공용 장소 행으로 남아, 실제 고객의
#:  「다른 데로 바꿔」와 일정 짜기에 뽑혔다. 실서비스 테넌트(`settings.tenant_id`)에서는 **대본 여행**(처음 등록한 판이
#:  시연 장소를 쓴 여행)과 **그 장소를 이미 일정에 넣은 여행**에만 보인다 — 다른 고객 여행의 후보·일정 짜기에는 안 나온다.
#:  시나리오 모드(`scenario-live-*`)와 시험 테넌트는 그대로 쓴다.
SCENARIO_SEED = "scenario_seed"
_SEED = "COALESCE((q.attributes->>'scenario_seed')::boolean, false)"
#: 대본 여행 id — 처음 등록한 판(1판)이 시연 장소를 쓴 여행. ★일정 짜기가 넣은 항목(`detail.planner`)은 치지 않는다 —
#:  ☆`[2026-09-29 ui 세션]` 일정 짜기가 시연 장소(「롯데마트 서울역점」)를 넣은 고객 여행이 대본 여행으로 잡혀 시연 장소가 다시 열렸다
_SCENARIO_TRIPS = ("SELECT DISTINCT ii.trip_id FROM itinerary_items ii JOIN places q ON q.place_id = ii.place_id"
                   " WHERE ii.tenant_id = %s AND ii.version = 1 AND NOT (ii.detail ? 'planner') AND " + _SEED)


def hides_scenario_places(tenant_id: str) -> bool:
    from app.core.settings import get_settings

    return tenant_id == get_settings().tenant_id


def visible_to(places: list[dict[str, Any]], trip_id: Any) -> list[dict[str, Any]]:
    """`places(every_trip=True)` 에서 한 여행이 볼 수 있는 것 — 공용 + 그 여행 전용.
    ★시연 장소(`SCENARIO_SEED`)는 `seed_trips` 에 든 여행에만(`TripStore.places` 가 붙인다)."""
    return [p for p in places if p.get("trip_scope") in (None, str(trip_id))
            and ("seed_trips" not in p or str(trip_id) in p["seed_trips"])]


class TripStore:
    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id

    # ── 만들기 ──────────────────────────────────────────────────
    def create_trip(self, conn, *, customer_id: UUID, title: str, locale: str | None,
                    party_size: int | None, items: list[Item],
                    constraints: dict[str, Any] | None = None,
                    request_key: str | None = None,
                    request_sha256: str | None = None,
                    trip_id: UUID | None = None) -> tuple[UUID, int]:
        """★`trip_id` 를 미리 정해 넘길 수 있다 — 그 여행 전용 장소 행을 여행보다 먼저 넣을 때(029)."""
        # ★`[2026-09-29]` 방금 넣은 장소의 실내·야외 모름을 확실한 분류로 먼저 채운다(같은 트랜잭션)
        fill_weather_sensitive(conn, self.tenant_id)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO trips (trip_id, tenant_id, customer_id, title, locale, party_size, constraints, "
                "request_key, request_sha256) VALUES (COALESCE(%s, gen_random_uuid()),%s,%s,%s,%s,%s,%s,%s,%s) "
                "RETURNING trip_id",
                (trip_id, self.tenant_id, customer_id, title, locale, party_size,
                 json.dumps(constraints or {}, ensure_ascii=False), request_key, request_sha256))
            trip_id = cur.fetchone()[0]
        version = self.append_version(conn, trip_id=trip_id, base_version=0, items=items,
                                      reason="created", causes=[])
        return trip_id, version

    def by_request_key(self, conn, request_key: str) -> tuple[UUID, str | None] | None:
        """같은 등록 요청으로 이미 만든 여행 — `(trip_id, 몸통 지문)`."""
        with conn.cursor() as cur:
            cur.execute("SELECT trip_id, request_sha256 FROM trips WHERE tenant_id=%s "
                        "AND request_key=%s", (self.tenant_id, request_key))
            row = cur.fetchone()
        return (row[0], row[1]) if row else None

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

    def active_trip_ids(self, conn) -> list[UUID]:
        """진행 중인 여행. 안내 되잡기 작업이 읽는다."""
        with conn.cursor() as cur:
            # ★`[2026-10-04 D-CS-011]` 게스트(로그인 안 한 웹 사용자)의 여행은 안내 · 감시 대상이 아니다 — 외부 호출 비용을 안 쓴다
            cur.execute("SELECT t.trip_id FROM trips t WHERE t.tenant_id=%s AND t.status='active' AND " + not_guest_sql("t")
                        + " ORDER BY t.trip_id", (self.tenant_id,))
            return [row[0] for row in cur.fetchall()]

    def due(self, conn, *, start: datetime, end: datetime) -> list[tuple[UUID, Item]]:
        """최신 버전에서 `[start, end)` 에 시작하는 항목. 감시 루프가 읽는다."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT t.trip_id, t.latest_version FROM trips t "
                "WHERE t.tenant_id=%s AND t.status='active' AND " + not_guest_sql("t"), (self.tenant_id,))
            trips = cur.fetchall()
        found = []
        for trip_id, version in trips:
            for item in self.items(conn, trip_id, version):
                if start <= item.starts_at < end:
                    found.append((trip_id, item))
        return found

    def versions(self, conn, trip_id: UUID) -> list[dict[str, Any]]:
        """버전 이력 — 무엇이 왜 바뀌었나. 계획서 링크와 되돌림이 읽는다."""
        with conn.cursor() as cur:
            cur.execute("SELECT version, reason, cause_json, created_at FROM itinerary_versions "
                        "WHERE tenant_id=%s AND trip_id=%s ORDER BY version",
                        (self.tenant_id, trip_id))
            return [dict(zip(("version", "reason", "causes", "created_at"), row))
                    for row in cur.fetchall()]

    def version_for_request(self, conn, trip_id: UUID, request_id: str) -> int | None:
        """★이 요청으로 이미 올린 버전. 같은 신고를 두 번 받아 두 번 고치지 않게 한다.

        ☆같은 「70분 늦음」을 다시 적용하면 이미 옮긴 점심을 **또** 70분 민다 —
          재시도가 일정을 망가뜨린다. 원인 칸에 요청 id 를 남기고 여기서 찾는다.
        """
        with conn.cursor() as cur:
            cur.execute("SELECT version FROM itinerary_versions WHERE tenant_id=%s AND trip_id=%s "
                        "AND cause_json @> %s::jsonb ORDER BY version LIMIT 1",
                        (self.tenant_id, trip_id, json.dumps([{"request_id": request_id}])))
            row = cur.fetchone()
        return row[0] if row else None

    def add_catalog_place(self, conn, trip_id: UUID, place: dict[str, Any]) -> dict[str, Any]:
        """★`[2026-09-29]` 고객이 고른 관광공사 목록 후보를 **그 여행 전용 장소**로 등록한다(`catalog_activity_places`).

        id 는 후보에 이미 정해져 있다(같은 곳을 두 번 골라도 한 행). 같은 여행에 같은 이름·종류 행이 이미 있으면
        (다른 경로로 먼저 들어왔으면) 그 행을 돌려준다 — 부르는 쪽은 돌려받은 `place_id` 를 쓴다.
        """
        attributes = {k: v for k, v in dict(place.get("attributes") or {}).items() if k != "catalog_pending"}
        with conn.cursor() as cur:
            cur.execute("SELECT place_id FROM places WHERE tenant_id=%s AND trip_scope=%s AND name=%s AND kind=%s",
                        (self.tenant_id, trip_id, place["name"], place["kind"]))
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "INSERT INTO places (place_id, tenant_id, name, kind, latitude, longitude, weather_sensitive, "
                    "attributes, trip_scope) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (place_id) DO NOTHING RETURNING place_id",
                    (UUID(str(place["place_id"])), self.tenant_id, place["name"], place["kind"],
                     place["latitude"], place["longitude"], place.get("weather_sensitive"),
                     json.dumps(attributes, ensure_ascii=False), trip_id))
                row = cur.fetchone() or (UUID(str(place["place_id"])),)
        return {**place, "place_id": str(row[0]), "attributes": attributes}

    def places(self, conn, trip_id: UUID | None = None, *, every_trip: bool = False) -> list[dict[str, Any]]:
        """장소 목록. ★`[2026-09-27]` 외부 서비스에서 온 장소는 **그 여행 전용 행**이다(`trip_scope`, 마이그레이션 029).

        - `trip_id` 없음 → 공용 행만(일정 생성기 후보 · 에이전트 도구의 장소 목록)
        - `trip_id` 있음 → 공용 + 그 여행 전용
        - `every_trip=True` → 전부(여러 여행을 한꺼번에 도는 감시). 여행마다 `visible_to` 로 거른다
        ★다른 여행의 전용 행을 대체 후보로 쓰면 외부 값을 다른 고객에게 재사용하는 것이다(약관 — 마이그레이션 029 머리).
        """
        where, params = "", [self.tenant_id]
        if not every_trip:
            where = " AND (p.trip_scope IS NULL OR p.trip_scope = %s)" if trip_id else " AND p.trip_scope IS NULL"
            params += [trip_id] if trip_id else []
        hide = hides_scenario_places(self.tenant_id)
        if hide and not every_trip:
            # ★시연 대본 장소는 대본 여행 · 이미 그 장소를 일정에 넣은 여행에만(`SCENARIO_SEED`)
            where += " AND (COALESCE((p.attributes->>'scenario_seed')::boolean, false) = false"
            if trip_id:
                where += (" OR %s IN (" + _SCENARIO_TRIPS + ")"
                          " OR p.place_id IN (SELECT ii.place_id FROM itinerary_items ii"
                          " WHERE ii.tenant_id = p.tenant_id AND ii.trip_id = %s AND ii.place_id IS NOT NULL)")
                params += [trip_id, self.tenant_id, trip_id]
            where += ")"
        # ★`[2026-09-29]` 관광공사 분류(신분류 대·중·소 · 시군구)를 장소 목록에서 이어 붙인다 — 대체 활동을
        #   「비슷한 곳」부터 고르는 재료다(`activity/similarity.py`). 장소가 관광공사 id 를 모르거나 목록에 없으면
        #   `catalog_class=None`(모름) — 지어내지 않는다. 카탈로그는 (tenant, source, content_id) UNIQUE 라 행이 늘지 않는다.
        with conn.cursor() as cur:
            cur.execute("SELECT " + ", ".join("p." + column for column in PLACE_COLUMNS)
                        + ", p.trip_scope, pc.raw_json->>'lclsSystm1', pc.raw_json->>'lclsSystm2',"
                        " pc.raw_json->>'lclsSystm3', pc.raw_json->>'sigungucode'"
                        " FROM places p LEFT JOIN place_catalog pc ON pc.tenant_id = p.tenant_id"
                        " AND pc.source = 'tour_api'"
                        " AND pc.content_id = COALESCE(p.source_content_id, p.attributes->>'source_content_id')"
                        " WHERE p.tenant_id=%s" + where, params)
            width = len(PLACE_COLUMNS)
            rows = [{**_place(row[:width]), "trip_scope": str(row[width]) if row[width] else None,
                     "catalog_class": _catalog_class(row[width + 1:])}
                    for row in cur.fetchall()]
            if hide and every_trip:
                # 여러 여행을 한꺼번에 볼 때 — 시연 장소마다 볼 수 있는 여행을 붙인다(`visible_to` 가 거른다)
                cur.execute(_SCENARIO_TRIPS, (self.tenant_id,))
                seeded = {str(r[0]) for r in cur.fetchall()}
                cur.execute("SELECT DISTINCT place_id::text, trip_id::text FROM itinerary_items"
                            " WHERE tenant_id = %s AND place_id IS NOT NULL", (self.tenant_id,))
                using: dict[str, set[str]] = {}
                for place_id, trip in cur.fetchall():
                    using.setdefault(place_id, set()).add(trip)
                for row in rows:
                    if (row.get("attributes") or {}).get(SCENARIO_SEED):
                        row["seed_trips"] = seeded | using.get(row["place_id"], set())
            return rows

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

    def enqueue_message(self, conn, *, trip_id: UUID, key: str,
                        payload: dict[str, Any]) -> bool:
        """일정 버전에 딸리지 않은 안내(하루 시작·출발·하루 정리 — v11 §6-B 의 ②·③).

        ★같은 `key` 는 두 번 들어가지 않는다(`outbox` UNIQUE). 버전 통지와 키가 겹치지
          않게 `{trip_id}:{key}` 로 둔다.
        ★`[2026-09-22]` 부르는 쪽이 안 넣었으면 **계획서 링크를 여기서 붙인다** — 시나리오 모드의
          안내가 링크 없이 나가고 있었다(되잡기 작업은 넣어 주고 있었다).
        """
        if "plan_url" not in payload:
            from .plan_link import plan_url

            payload = {**payload, "plan_url": plan_url(self.tenant_id, trip_id)}
        with conn.cursor() as cur:
            cur.execute("SELECT locale FROM trips WHERE tenant_id=%s AND trip_id=%s",
                        (self.tenant_id, trip_id))
            row = cur.fetchone()
            cur.execute(
                "INSERT INTO outbox (tenant_id, topic, dedupe_key, payload_json) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT (tenant_id, topic, dedupe_key) DO NOTHING",
                (self.tenant_id, "trip.notice", f"{trip_id}:{key}",
                 json.dumps({"locale": row[0] if row else None, **payload},
                            ensure_ascii=False, default=str)))
            # ★새로 넣었으면 True. 이미 있던 키면 False — 되잡기 작업이 「보냄」과 「이미 보냄」을 가른다.
            return cur.rowcount == 1

    def enqueue_notice(self, conn, *, trip_id: UUID, version: int,
                       payload: dict[str, Any]) -> None:
        """★적용된 일정 버전당 통지 하나(§6-C-6). 같은 버전을 두 번 넣으면 막힌다.

        ★여행의 언어(`locale`)를 싣는다 — 보낼 때 그 언어로 옮긴다(결정 14).
        ★`[2026-09-20]` **계획서 링크도 싣는다.** 상태의 정본은 링크인데(v11 §6-A) 변경 통지에만
          링크가 없었다 — 일정 안내(②·③)에는 붙고 ①에는 안 붙는 상태였다.
        """
        if "plan_url" not in payload:
            from .plan_link import plan_url

            payload = {**payload, "plan_url": plan_url(self.tenant_id, trip_id)}
        if "locale" not in payload:
            with conn.cursor() as cur:
                cur.execute("SELECT locale FROM trips WHERE tenant_id=%s AND trip_id=%s",
                            (self.tenant_id, trip_id))
                row = cur.fetchone()
            payload = {**payload, "locale": row[0] if row else None}
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO outbox (tenant_id, topic, dedupe_key, payload_json) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT (tenant_id, topic, dedupe_key) DO NOTHING",
                (self.tenant_id, "trip.notice", f"{trip_id}:v{version}",
                 json.dumps(payload, ensure_ascii=False, default=str)))


__all__ = ["Item", "StaleItinerary", "TripStore"]
