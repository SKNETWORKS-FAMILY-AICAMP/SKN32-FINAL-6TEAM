# -*- coding: utf-8 -*-
"""일정 항목의 **장소 정보** — 주소 · 전화 · 분류 · 요일별 영업시간 · 속성(미쉐린 · 카드 결제 · 주차 …) · 출처. `[2026-09-29]`

★왜. 사용자 지적(ui 세션 전달): 선택 일정 상세에 이름·시각·좌표만 있었고, 채팅의 「주소 알려 줘」는 관광공사에서 이름으로
  다시 찾기만 해서 **요식 원장에 주소가 있는 식당**(예: 무구옥 — 주소·전화·한식·미쉐린 셀렉티드 2026·카드 결제)도 「모름」이었다.
★읽는 곳(우선순위): ① 요식 원장(`dining.dn_place` · `dn_attribute` · `dn_hours_rule`/`dn_hours_interval`) — 장소 속성
  `dining_place_uid`(원장 동기화가 붙인다) 또는 원장의 코어 연결(`dn_core_place_link`) ② 코어 장소 속성(`attributes.address` 등).
★원장은 요식 세션의 표다 — 여기서는 **읽기만** 한다(쓰지 않는다). 원장 표가 없는 DB 면 ②로 간다.
★모르는 값은 None — 「없다」로 읽지 않는다(원장 머리말과 같은 규칙). 출처 표시가 필요한 값은 `source_note` 에 싣는다.
"""
from __future__ import annotations

import re
from typing import Any

#: 월=1 … 일=7(원장 `weekday` — ISO, `scripts/dining/check_dining.py` 가 `isoweekday()` 로 쓴다)
WEEKDAY_KO = {1: "월", 2: "화", 3: "수", 4: "목", 5: "금", 6: "토", 7: "일"}
#: 출처 표시가 필요한 원장 출처 — 값을 보여 줄 때 함께 적는다
SOURCE_NOTES = {"tourapi_kor_food": "ⓒ한국관광공사", "michelin_guide": "미쉐린 가이드 서울"}


def _hm(minutes: int | None) -> str | None:
    if minutes is None:
        return None
    minutes = int(minutes) % 1440
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _ledger_uid(conn, tenant_id: str, place: dict[str, Any]) -> str | None:
    uid = ((place.get("attributes") or {}).get("dining_place_uid") or "").strip()
    if uid:
        return uid
    if not place.get("place_id"):
        return None
    with conn.cursor() as cur:
        cur.execute("SELECT place_uid FROM dining.dn_core_place_link WHERE tenant_id=%s AND core_place_id=%s",
                    (tenant_id, str(place["place_id"])))
        row = cur.fetchone()
    return str(row[0]) if row else None


def _plain(text: str | None) -> str | None:
    """관광공사 원문의 줄바꿈 태그를 「 / 」로 — 화면에 한 줄로 보인다(채팅 답 `trip_facts._clean` 과 같은 규칙)."""
    if not text:
        return None
    text = re.sub(r"<br\s*/?>", " / ", str(text), flags=re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip(" /") or None


def _michelin(detail: str | None) -> dict[str, Any] | None:
    if not detail:
        return None
    year = re.search(r"(20\d\d)", detail)
    level = re.sub(r"\s*\(?20\d\d\)?\s*", "", detail).strip() or None
    return {"level": level, "year": int(year.group(1)) if year else None}


def ledger_info(conn, place_uid: str) -> dict[str, Any] | None:
    """요식 원장 한 곳의 정보. 없는 곳이면 None."""
    with conn.cursor() as cur:
        cur.execute("SELECT road_address, jibun_address, phone, category FROM dining.dn_place WHERE place_uid=%s",
                    (place_uid,))
        row = cur.fetchone()
        if row is None:
            return None
        address, jibun, phone, category = row
        cur.execute("SELECT attr_code, value_detail, source_code FROM dining.dn_attribute "
                    "WHERE place_uid=%s AND value_state='yes' AND retired_at IS NULL ORDER BY attr_code", (place_uid,))
        attributes = cur.fetchall()
        cur.execute("SELECT r.weekday, i.seq, i.open_min, i.close_min, i.last_order_min, r.source_code "
                    "FROM dining.dn_hours_rule r JOIN dining.dn_hours_interval i USING (rule_id) "
                    "WHERE r.place_uid=%s AND r.rule_kind='weekly' AND r.retired_at IS NULL "
                    "ORDER BY r.weekday, i.seq", (place_uid,))
        intervals = cur.fetchall()
    tags = sorted({code for code, _, _ in attributes})
    michelin = next((_michelin(detail) for code, detail, _ in attributes if code == "michelin"), None)
    hours = [{"day": WEEKDAY_KO.get(int(day), str(day)), "weekday": int(day), "open": _hm(open_min),
              "close": _hm(close_min), "last_order": _hm(last_order)}
             for day, _, open_min, close_min, last_order, _ in intervals] or None
    sources = sorted({source for _, _, source in attributes} | {source for *_, source in intervals})
    notes = [SOURCE_NOTES[s] for s in sources if s in SOURCE_NOTES]
    return {"address": address or jibun, "phone": phone, "category": category, "hours": hours,
            "hours_source": sorted({source for *_, source in intervals}) or None,
            "tags": tags, "michelin": michelin, "source": "dining_ledger",
            "source_note": " · ".join(notes) or None}


def place_info(conn, tenant_id: str, place: dict[str, Any] | None) -> dict[str, Any] | None:
    """일정 항목 장소의 정보 — 원장에 있으면 원장, 없으면 코어 장소 속성. 장소가 없으면 None."""
    if not place:
        return None
    try:
        uid = _ledger_uid(conn, tenant_id, place)
        found = ledger_info(conn, uid) if uid else None
    except Exception as exc:                     # noqa: BLE001 — 원장 표가 없는 DB(시험 · 다른 조립)면 코어 값으로
        if type(exc).__name__ not in ("UndefinedTable", "InvalidSchemaName", "InvalidTextRepresentation"):
            raise
        conn.rollback()
        found = None
    if found is not None:
        return found
    attributes = place.get("attributes") or {}
    source = attributes.get("source") or "places"
    catalog = _catalog_row(conn, tenant_id, place)
    hours, hours_source = _week_hours(attributes)
    read = attributes.get("hours_read") or {}
    raw = (catalog or {}).get("raw") or {}
    from_tour = source == "tour_api" or catalog is not None or read.get("source") == "tour_api"
    return {"address": attributes.get("address") or (catalog or {}).get("address"),
            "phone": attributes.get("phone") or (raw.get("tel") or "").strip() or None,
            "category": None, "hours": hours, "hours_source": hours_source,
            # ★운영시간 **원문**(관광공사 `usetime` 에서 인용한 줄)과 휴무 조건 원문 — 요일표로 못 편 것까지 보이게
            "hours_text": list(read.get("quotes") or []) or [
                _plain(text) for text in ((attributes.get("hours_origin") or {}).get("usetime"),
                                         (attributes.get("hours_origin") or {}).get("restdate")) if _plain(text)] or None,
            "hours_conditions": list(read.get("conditions") or []) or None,
            "tags": [], "michelin": None, "source": "tour_api" if from_tour else source,
            "source_note": "ⓒ한국관광공사" if from_tour else None}


#: 관광공사 목록에서 이름으로 찾을 때 좌표가 이만큼 안이어야 같은 곳으로 본다 — 운영시간 읽기(`place_hours.py`)와 같은 값
CATALOG_MATCH_M = 500
_WEEK_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _catalog_row(conn, tenant_id: str, place: dict[str, Any]) -> dict[str, Any] | None:
    """관광공사 목록(`place_catalog`)의 그 장소 — ①관광공사 식별자 ②같은 이름이고 좌표가 500m 안. 없으면 None.

    ★`[2026-09-29 ui 세션 지적]` 활동의 장소 행에는 관광공사 식별자·운영시간만 있고 **주소는 목록 표에만** 있어,
      일정 상세의 주소가 비었다(경복궁 · 창덕궁). 목록은 공공데이터 사실 정보라 저장해 쓴다(루트 사실표 2026-09-28).
    ★목록은 기본 테넌트에만 적재돼 있다 — 그 테넌트 것도 본다(시험·시나리오 테넌트의 여행도 같은 목록을 쓴다).
    """
    from app.core.settings import get_settings

    attributes = place.get("attributes") or {}
    tenants = list(dict.fromkeys([tenant_id, get_settings().tenant_id]))
    content_id = str(attributes.get("source_content_id") or "").strip()
    try:
        with conn.cursor() as cur:
            if content_id:
                cur.execute("SELECT address, raw_json, latitude, longitude FROM place_catalog "
                            "WHERE tenant_id = ANY(%s) AND source='tour_api' AND content_id=%s LIMIT 1",
                            (tenants, content_id))
            else:
                cur.execute("SELECT address, raw_json, latitude, longitude FROM place_catalog "
                            "WHERE tenant_id = ANY(%s) AND source='tour_api' AND title=%s LIMIT 5",
                            (tenants, place.get("name")))
            rows = cur.fetchall()
    except Exception as exc:                     # noqa: BLE001 — 목록 표가 없는 DB 면 목록 없이
        if type(exc).__name__ != "UndefinedTable":
            raise
        conn.rollback()
        return None
    for address, raw, lat, lon in rows:
        if not content_id and None not in (lat, lon, place.get("latitude"), place.get("longitude")):
            from app.domains.travel_ops.components.planning.replan import distance_m

            if distance_m({"latitude": float(lat), "longitude": float(lon)},
                          {"latitude": float(place["latitude"]), "longitude": float(place["longitude"])}) \
                    > CATALOG_MATCH_M:
                continue
        extra = ((raw or {}).get("addr2") or "").strip()
        if address and extra and extra not in address:
            address = f"{address} {extra}"
        return {"address": address or None, "raw": raw or {}}
    return None


def _week_hours(attributes: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, list[str] | None]:
    """관광공사 운영시간을 요일별로 옮긴 값(`attributes.hours_week`, `place_hours.py`) → 원장과 같은 모양.
    쉬는 날은 `closed: true`(열고 닫는 시각 null). 활동은 `last_order` 대신 `last_entry`(입장 마감)."""
    week = attributes.get("hours_week") or {}
    if not isinstance(week, dict) or not week:
        return None, None
    rows = []
    for number, key in enumerate(_WEEK_KEYS, start=1):
        value = week.get(key)
        if value is None:
            continue
        base = {"day": WEEKDAY_KO[number], "weekday": number, "last_order": None}
        if value == "closed":
            rows.append({**base, "open": None, "close": None, "last_entry": None, "closed": True})
        elif isinstance(value, dict):
            rows.append({**base, "open": value.get("open"), "close": value.get("close"),
                         "last_entry": value.get("last_entry"), "closed": False})
    source = (attributes.get("hours_read") or {}).get("source") or attributes.get("source") or "places"
    return rows or None, [source]


#: 한 번 도는 동안 채우는 장소 수 — ★우리가 고른 값. 1분마다 돌아도 관광공사 개발 키 하루 한도(1,000건)를 넘지 않게
#:  (장소 하나에 많아야 2건 — 이름으로 찾기 · 운영정보). 새 장소만 읽으므로 평소에는 0건이다
FILL_PER_TICK = 10
#: 읽기에 실패한 장소를 다시 보는 간격 — 속도 한도로 못 받았을 수 있다(영영 「모름」으로 굳지 않게)
RETRY_HOURS = 6


def fill_missing_facts(conn, tenant_id: str, *, source: Any, chat: Any, now: Any,
                       limit: int = FILL_PER_TICK) -> dict[str, Any]:
    """진행 중인 여행에 들어간 장소 중 **운영시간을 아직 안 읽은 곳**을 관광공사에서 한 번 읽어 장소 행에 적는다.

    ★`[2026-09-29 ui 세션 지적]` 등록으로 들어온 활동(「경복궁」)은 장소 행이 비어 있어 일정 상세에 전화·운영시간이
      안 나왔다 — 일정 생성기는 고른 장소만 읽고(`planner.enrich_hours`), 등록 경로는 읽지 않았다.
    ★화면이 열릴 때 부르지 않는다(12곳이면 12번 기다린다). 1분 작업(`run_sweepers`)이 새 장소만 읽어 적는다.
    ★적는 것: `hours_week`(요일별 — 옮길 수 있을 때만) · `hours_read`(읽은 방법·인용·조건·시각) · `hours_origin`
      (관광공사 원문 `usetime`·`restdate` — 사실 정보) · `phone`(문의 전화, 없을 때만). 식당 원장에 이어진 곳은 원장이 답하므로 뺀다.
    ★못 읽으면 `hours_read.method = "none"` 과 이유를 적고 `RETRY_HOURS` 뒤에 다시 본다.
    """
    import json
    from datetime import timedelta

    from app.domains.travel_ops.components.places.place_hours import find_tour_id, read_hours

    if source is None or not hasattr(source, "operating"):
        return {"skipped": "관광공사 조회가 연결돼 있지 않다"}
    retry_before = (now - timedelta(hours=RETRY_HOURS)).isoformat()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT p.place_id, p.name, p.kind, p.latitude, p.longitude, p.attributes "
            "FROM trips t JOIN itinerary_items i ON i.tenant_id=t.tenant_id AND i.trip_id=t.trip_id "
            "  AND i.version=t.latest_version "
            "JOIN places p ON p.place_id=i.place_id AND p.tenant_id=i.tenant_id "
            "WHERE t.tenant_id=%s AND i.kind IN ('activity','dining') AND i.ends_at > %s "
            "AND NOT (p.attributes ? 'dining_place_uid') "
            "AND (NOT (p.attributes ? 'hours_read') OR (p.attributes->'hours_read'->>'method' = 'none' "
            "     AND p.attributes->'hours_read'->>'read_at' < %s)) "
            "LIMIT %s", (tenant_id, now, retry_before, limit))
        rows = cur.fetchall()
    out: dict[str, Any] = {"asked": len(rows), "read": 0, "unknown": 0, "phone": 0, "failed": []}
    for place_id, name, kind, lat, lon, attributes in rows:
        attributes = attributes or {}
        content_id = str(attributes.get("source_content_id") or "")
        type_id = str(attributes.get("source_content_type_id") or "")
        patch: dict[str, Any] = {}
        try:
            if not content_id or not type_id:
                ids, why, _ = find_tour_id(name=name, kind=kind, latitude=lat, longitude=lon, source=source)
                if ids is None:
                    raise LookupError(why)
                content_id, type_id = ids
                patch.update(source_content_id=content_id, source_content_type_id=type_id)
            intro = source.operating(content_id, type_id)
            if not intro:
                raise LookupError("운영정보를 받지 못했다")
            usetime, restdate = intro.get("usetime_text"), intro.get("restdate_text")
            read = read_hours(usetime, restdate, chat)
            patch["hours_read"] = read.as_record(source="tour_api", read_at=now.isoformat())
            patch["hours_origin"] = {"usetime": usetime, "restdate": restdate}
            if read.week:
                patch["hours_week"] = read.week
                out["read"] += 1
            else:
                out["unknown"] += 1
            if intro.get("info_phone") and not attributes.get("phone"):
                patch["phone"] = intro["info_phone"]
                out["phone"] += 1
        except Exception as exc:                 # noqa: BLE001 — 장소 하나의 실패가 나머지를 막지 않는다(세어 보고)
            patch = {"hours_read": {"source": "tour_api", "method": "none", "read_at": now.isoformat(),
                                    "dropped": [str(exc) if isinstance(exc, LookupError)
                                                else f"조회 오류 {type(exc).__name__}"]}}
            out["unknown"] += 1
            out["failed"].append(f"{name}: {patch['hours_read']['dropped'][0]}")
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("UPDATE places SET attributes = coalesce(attributes, '{}'::jsonb) || %s::jsonb "
                        "WHERE tenant_id=%s AND place_id=%s",
                        (json.dumps(patch, ensure_ascii=False), tenant_id, place_id))
    return out


__all__ = ["FILL_PER_TICK", "SOURCE_NOTES", "WEEKDAY_KO", "fill_missing_facts", "ledger_info", "place_info"]
