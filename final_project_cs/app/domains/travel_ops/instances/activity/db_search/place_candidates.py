# -*- coding: utf-8 -*-
"""대체 장소 후보 풀 조회 — `read.place_candidates` 의 DB 쪽 구현.

활동 원장(`activity.ac_place`, 300)에서 원래 장소 행(origin)과 후보 행들을 읽어
`alternatives.py` 가 읽는 CSV·TourAPI 컬럼명 모양으로 돌려준다.
적재는 `scripts/activity/load_places.py`, 운영시간 갱신은 `scripts/activity/refresh_places.py` 가 한다.
`[2026-10-16]` 전에는 코어 `place_catalog` 를 읽었다 — 아래 `_COLUMNS` 위 메모.

반환 모양(`ReadToolbox.place_candidates` 계약)::

    {"origin":     {"contentid", "title", "contenttypeid",
                    "lclsSystm1", "lclsSystm2", "lclsSystm3",
                    "lDongSignguCd", "brand", "mapx", "mapy",
                    "closed_days", "business_hours"},
     "candidates": [<origin 과 같은 모양의 행>, ...],
     "source": "activity.ac_place:tour_api+oliveyoung+...", "confirmed_at": "..."}

★`[2026-10-02]` 후보 풀은 원래 장소 좌표 기준 **최대 반경(`RADIUS_MAX_KM`)의 바운딩 박스**
  안의 행까지만 좁힌다(거리 계산 1단계 — 사각형이라 인덱스 범위 비교로 끝난다). 정확한
  거리(하버사인)와 반경 넓히기는 `alternatives.py` 가 한다. 분류로는 좁히지 않는다 —
  이동 중요는 대분류까지 풀 수 있어야 한다. 좌표가 없는 행은 범위 비교에서 빠진다. 축제 · 행사(EV)와 목록에서 내려간 곳은 뺀다.
★원래 장소를 원장에서 못 찾으면 `None`(모름) — 유사도를 잴 기준이 없다.
★원래 장소 좌표가 없으면 박스를 그릴 수 없어 후보를 읽지 않고 빈 목록을 준다 —
  `alternatives.rank_alternatives` 가 `origin_no_coordinates` 로 답한다.
★좌표는 원장의 `lat`·`lng` 이다(적재 때 못 읽거나 0 인 좌표는 NULL — `load_places._coord`).
★`confirmed_at` 은 풀에 든 행 중 **가장 오래된** `updated_at`(원장 적재 시각)이다 — 우리가
  받은 시각이지 공급자가 확인한 시각이 아니다. 가장 낡은 값을 댄다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from ..alternatives import RADIUS_MAX_KM, bounding_box

#: 후보 풀에 넣는 출처 전부. 원장에는 출처 칸이 없어 `content_id` 로 가른다(`SOURCE_SQL`) —
#:  TourAPI 는 숫자, 브랜드 매장(올리브영·다이소·아트박스·무신사)은 OY/DS/AB/MS 접두어라 겹치지 않는다.
DEFAULT_SOURCES = ("tour_api", "oliveyoung", "daiso", "artbox", "musinsa")
#: `content_id` → 출처 이름. `scripts/load_place_catalog_csv.py` 의 가르는 법과 같다.
SOURCE_SQL = ("CASE WHEN content_id ~ '^[0-9]+$' THEN 'tour_api' WHEN content_id LIKE 'OY%%' THEN 'oliveyoung' "
              "WHEN content_id LIKE 'DS%%' THEN 'daiso' WHEN content_id LIKE 'AB%%' THEN 'artbox' "
              "WHEN content_id LIKE 'MS%%' THEN 'musinsa' END")
#: ★후보로 내지 않는 대분류 — 축제 · 공연 · 행사(EV). 기간이 있는 일이라 「그 시각에 하는가」를 아직 판정하지 않는다.
#:  카탈로그 시절(`load_place_catalog_csv --exclude-codes FD AC EV`)과 같은 동작을 지킨다. 원래 장소로는 읽는다.
POOL_EXCLUDED_CLASSES = ("EV",)

#: ★`[2026-10-16 사용자 결정]` **활동 원장(`activity.ac_place`)만 읽는다 — `place_catalog` 는 쓰지 않는다.**
#:  전에는 후보 풀을 코어 `place_catalog`(`raw_json` 의 운영시간 · 휴무 글)에서 읽고 원래 장소 판정(`ledger.py`)은 원장에서 읽어,
#:  같은 장소가 원래 장소일 때와 후보일 때 다른 표로 판정됐다(10-16 로컬 실측 운영시간 글 17곳 · 휴무 글 13곳 다름 —
#:  두 표를 같이 적재하는 길이 없고 야간 갱신 `refresh_places.py` 는 원장만 고친다). 10-12 결정(활동은 자기 원장으로 판정)과 맞춘다.
#: ★원장은 공공 장소 자료라 **테넌트를 나누지 않는다**(`ledger.py` 와 같다). `tenant_id` 인자는 호출 계약 때문에 받기만 한다.
_COLUMNS = ("content_id", "content_type_id", "title", "latitude", "longitude", "lcls1", "lcls2", "lcls3",
            "sigungu_code", "brand", "usetime_text", "restdate_text", "addr1", "updated_at")
_SELECT = ("SELECT content_id, content_type_id, name_ko, lat, lng, lcls1, lcls2, lcls3, sigungu_code, brand, "
           "usetime_text, restdate_text, addr1, updated_at FROM activity.ac_place "
           f"WHERE ({SOURCE_SQL}) = ANY(%s) ")

ORIGIN_SQL = _SELECT + "AND content_id=%s LIMIT 1"
#: ★`[2026-10-12]` 관광공사 목록에서 내려간 장소(끝난 축제 · 폐업 · 비공개 — `delisted_at`, 303)는 후보로 내지 않는다.
#:  원래 장소(ORIGIN)는 거르지 않는다 — 고객이 이미 고른 곳이다.
POOL_SQL = (_SELECT + "AND content_id <> %s AND delisted_at IS NULL "
            "AND NOT (coalesce(lcls1, '') = ANY(%s)) "
            "AND lat BETWEEN %s AND %s AND lng BETWEEN %s AND %s "
            "ORDER BY content_id")


#: ★`[2026-10-19]` 활동 장소 별칭(마이그레이션 306) — 표가 있을 때만 읽는다(없으면 별칭 없음). 후보 풀과 같이 싣는다(`aliases`).
ALIAS_EXISTS_SQL = "SELECT to_regclass('activity.ac_place_alias') IS NOT NULL"
ALIAS_SQL = "SELECT alias, content_id FROM activity.ac_place_alias ORDER BY alias_norm, content_id"


def _read_aliases(cur: Any) -> list[dict[str, str]]:
    """별칭 표 전체(수백 행) — 표가 아직 없으면 빈 목록. 이 별칭이 이름 · 거리와 상관없이 「같은 곳」을 정한다(`place_identity`)."""
    cur.execute(ALIAS_EXISTS_SQL)
    row = cur.fetchone()
    if not row or not row[0]:
        return []
    cur.execute(ALIAS_SQL)
    return [{"alias": str(a), "content_id": str(c)} for a, c in cur.fetchall()]


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def to_candidate(record: dict[str, Any]) -> dict[str, Any]:
    """원장 한 행 → `alternatives.py` 가 읽는 CSV 컬럼 모양. 운영시간 · 휴무는 원장의 원문(`usetime_text` · `restdate_text`)이다."""
    lon, lat = record.get("longitude"), record.get("latitude")
    return {
        "contentid": _text(record.get("content_id")),
        "title": _text(record.get("title")),
        "contenttypeid": _text(record.get("content_type_id")),
        "lclsSystm1": _text(record.get("lcls1")),
        "lclsSystm2": _text(record.get("lcls2")),
        "lclsSystm3": _text(record.get("lcls3")),
        "lDongSignguCd": _text(record.get("sigungu_code")),
        "brand": _text(record.get("brand")),
        "mapx": None if lon is None else str(lon),
        "mapy": None if lat is None else str(lat),
        "closed_days": _text(record.get("restdate_text")),
        "business_hours": _text(record.get("usetime_text")),
        # ★`[2026-10-07]` 재난문자를 후보의 자치구로 거르는 데 쓴다(`replacement._recheck_disaster`).
        "addr1": _text(record.get("addr1")),
    }


def _oldest(records: list[dict[str, Any]]) -> str | None:
    """★원장에 적재된 시각(`updated_at`) 중 가장 오래된 것 — 우리가 받은 시각이지 공급자가 확인한 시각이 아니다."""
    stamps = [r["updated_at"] for r in records if isinstance(r.get("updated_at"), datetime)]
    return min(stamps).isoformat() if stamps else None


def find_place_candidates(connection_factory: Callable[[], Any], tenant_id: str,
                          content_id: str | None, *,
                          sources: tuple[str, ...] = DEFAULT_SOURCES) -> dict[str, Any] | None:
    """원래 장소 `content_id` 로 후보 풀을 읽는다. 원래 장소를 모르면 `None`. `tenant_id` 는 쓰지 않는다(원장은 공용)."""
    content_id = _text(content_id)
    if content_id is None:
        return None
    with connection_factory() as conn:
        with conn.cursor() as cur:
            cur.execute(ORIGIN_SQL, (list(sources), content_id))
            row = cur.fetchone()
            if row is None:
                return None
            origin_record = dict(zip(_COLUMNS, row))
            origin = to_candidate(origin_record)
            lat, lng = origin_record.get("latitude"), origin_record.get("longitude")
            records: list[dict[str, Any]] = []
            if lat is not None and lng is not None:
                cur.execute(POOL_SQL, (list(sources), content_id, list(POOL_EXCLUDED_CLASSES),
                                       *bounding_box(float(lat), float(lng), RADIUS_MAX_KM)))
                records = [dict(zip(_COLUMNS, r)) for r in cur.fetchall()]
            aliases = _read_aliases(cur)
    return {"origin": origin,
            "candidates": [to_candidate(r) for r in records],
            "aliases": aliases,
            "source": "activity.ac_place:" + "+".join(sources),
            "confirmed_at": _oldest([origin_record, *records])}
