# -*- coding: utf-8 -*-
"""대체 장소 후보 풀 조회 — `read.place_candidates` 의 DB 쪽 구현.

`place_catalog`(011·017)에서 원래 장소 행(origin)과 후보 행들을 읽어
`alternatives.py` 가 읽는 CSV·TourAPI 컬럼명 모양으로 돌려준다.
적재는 `scripts/load_place_catalog_csv.py` 가 한다(지금은 TourAPI 805건).

반환 모양(`ReadToolbox.place_candidates` 계약)::

    {"origin":     {"contentid", "title", "contenttypeid",
                    "lclsSystm1", "lclsSystm2", "lclsSystm3",
                    "sigungucode", "mapx", "mapy",
                    "closed_days", "business_hours"},
     "candidates": [<origin 과 같은 모양의 행>, ...],
     "source": "place_catalog:tour_api", "confirmed_at": "..."}

★후보 풀은 `lclsSystm1` **또는** `sigungucode` 가 원래 장소와 같은 행까지만
  좁힌다. 두 선호도(활동 중요·위치 중요)의 고정값이라 폴백이 필드를 하나씩
  풀어도 결과가 안 바뀐다. 그보다 더 좁히지 않는다.
★원래 장소를 카탈로그에서 못 찾으면 `None`(모름) — 유사도를 잴 기준이 없다.
★좌표는 컬럼(`latitude`·`longitude`) 값을 쓴다. 적재 때 서울 밖 자리표시 좌표는
  NULL 로 넣었으므로 `raw_json` 의 원본 `mapx`·`mapy` 를 되살리지 않는다.
★`confirmed_at` 은 풀에 든 행 중 **가장 오래된** `fetched_at` 이다 — 우리가
  받은 시각이지 공급자가 확인한 시각이 아니다. 가장 낡은 값을 댄다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

#: 기본 출처. `--source` 로 적재한 값과 같아야 한다.
DEFAULT_SOURCE = "tour_api"

_COLUMNS = ("content_id", "content_type_id", "title", "latitude", "longitude",
            "large_class_code", "raw_json", "fetched_at")
_SELECT = ("SELECT content_id, content_type_id, title, latitude, longitude, "
           "large_class_code, raw_json, fetched_at FROM place_catalog "
           "WHERE tenant_id=%s AND source=%s ")

ORIGIN_SQL = _SELECT + "AND content_id=%s"
POOL_SQL = (_SELECT + "AND content_id <> %s "
            "AND (large_class_code = %s OR raw_json->>'sigungucode' = %s) "
            "ORDER BY content_id")


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def to_candidate(record: dict[str, Any]) -> dict[str, Any]:
    """`place_catalog` 한 행 → `alternatives.py` 가 읽는 CSV 컬럼 모양."""
    raw = record.get("raw_json") or {}
    lon, lat = record.get("longitude"), record.get("latitude")
    return {
        "contentid": _text(record.get("content_id")),
        "title": _text(record.get("title")) or _text(raw.get("title")),
        "contenttypeid": _text(record.get("content_type_id")) or _text(raw.get("contenttypeid")),
        "lclsSystm1": _text(record.get("large_class_code")) or _text(raw.get("lclsSystm1")),
        "lclsSystm2": _text(raw.get("lclsSystm2")),
        "lclsSystm3": _text(raw.get("lclsSystm3")),
        "sigungucode": _text(raw.get("sigungucode")),
        "mapx": None if lon is None else str(lon),
        "mapy": None if lat is None else str(lat),
        "closed_days": _text(raw.get("closed_days")),
        "business_hours": _text(raw.get("business_hours")),
    }


def _oldest(records: list[dict[str, Any]]) -> str | None:
    stamps = [r["fetched_at"] for r in records if isinstance(r.get("fetched_at"), datetime)]
    return min(stamps).isoformat() if stamps else None


def find_place_candidates(connection_factory: Callable[[], Any], tenant_id: str,
                          content_id: str | None, *,
                          source: str = DEFAULT_SOURCE) -> dict[str, Any] | None:
    """원래 장소 `content_id` 로 후보 풀을 읽는다. 원래 장소를 모르면 `None`."""
    content_id = _text(content_id)
    if content_id is None:
        return None
    with connection_factory() as conn:
        with conn.cursor() as cur:
            cur.execute(ORIGIN_SQL, (tenant_id, source, content_id))
            row = cur.fetchone()
            if row is None:
                return None
            origin_record = dict(zip(_COLUMNS, row))
            origin = to_candidate(origin_record)
            cur.execute(POOL_SQL, (tenant_id, source, content_id,
                                   origin["lclsSystm1"], origin["sigungucode"]))
            records = [dict(zip(_COLUMNS, r)) for r in cur.fetchall()]
    return {"origin": origin,
            "candidates": [to_candidate(r) for r in records],
            "source": f"place_catalog:{source}",
            "confirmed_at": _oldest([origin_record, *records])}
