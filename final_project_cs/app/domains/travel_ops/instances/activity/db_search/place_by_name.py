# -*- coding: utf-8 -*-
"""고객이 말한 이름 → 활동 원장(`activity.ac_place`)에서 장소 **하나** 찾기 (`read.place_lookup` 의 1단계).

`[2026-10-16 사용자 결정]` 전에는 코어 `place_catalog` 를 읽었다 — 활동 팀은 원장만 읽는다(`place_candidates.py` 메모).
원장은 공용이라 테넌트를 나누지 않는다. 결과의 `via` 는 부르는 쪽 계약이라 `"place_catalog"` 그대로 둔다(「우리 목록」이라는 뜻).

반환 `status`:
  - `found`      — 이름이 정확히 한 곳을 가리킨다
  - `ambiguous`  — 둘 이상이다(후보 이름 몇 개를 같이 낸다 — 고객이 고른다)
  - `not_found`  — 없다

★이름 비교는 둘을 **순서대로** 본다. ① 띄어쓰기·기호만 무시한 **완전 일치**가 정확히 한 곳이면 그곳.
  ② 아니면 지점 접미어·괄호까지 뗀 일치(`intake.places.normalize`)가 한 곳이면 그곳. 둘 이상이면 `ambiguous` —
  「다이소」처럼 지점이 수백 곳인 이름을 한 곳으로 찍지 않는다.
★후보 선별은 SQL(포함 검색)이 하고 정확 비교는 파이썬이 한다. SQL 은 띄어쓰기를 뗀 제목이 질의를 **포함**하는
  행만 가져오므로, 괄호가 **가운데** 끼어 정규화로만 같아지는 제목(「A(x)B」 = 「AB」)은 놓친다. 그 경우는 `not_found`
  쪽으로 기운다 — 없는 곳을 있다고 하지 않는 방향이다.
★카카오 같은 바깥 값은 여기 없다. 우리 원장의 행만 읽는다.
★`[2026-10-19]` `fuzzy=True` 면 위 둘이 못 찾았을 때 **어순이 다른 이름 · 오타**로 한 번 더 찾는다(`name_match`). 기본은 꺼짐 —
  짐작한 장소라 결과에 `needs_review` · `match` · `note` 가 붙고, 부르는 쪽이 확인 필요로 다뤄야 한다. 원장 전체 이름을 읽으므로(약 6천 행)
  못 찾았을 때만 부른다. 폐지된 곳(`delisted_at`)은 짐작 대상에서 뺀다.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable

from app.domains.travel_ops.components.intake.places import normalize

from .. import place_aliases
from ..name_match import TypoIndex, word_set
from .place_candidates import ALIAS_EXISTS_SQL, DEFAULT_SOURCES, SOURCE_SQL

#: ambiguous 일 때 같이 내는 후보 이름 수(고객에게 보여 줄 만큼만)
SHOW_LIMIT = 5
#: SQL 이 가져오는 행 수 상한 — 「다이소」 같은 이름이 수백 곳을 끌어오지 않게
FETCH_LIMIT = 200

_COLUMNS = ("content_id", "content_type_id", "title", "latitude", "longitude", "source")
SQL = ("SELECT content_id, content_type_id, name_ko, lat, lng, source FROM "
       f"(SELECT *, {SOURCE_SQL} AS source FROM activity.ac_place) a "
       "WHERE source = ANY(%s) "
       # ★지우는 문자가 `_loose` 와 같아야 한다(공백·`·`·`-`·`_`·`/`) — 다르면 SQL 이 제목을 놓친다
       "AND regexp_replace(name_ko, '[[:space:]·_/-]+', '', 'g') ILIKE %s "
       "ORDER BY content_id LIMIT %s")
#: 별칭으로 찾은 장소 한 곳 — 같은 열 순서. 폐지된 곳은 뺀다
SQL_BY_ID = ("SELECT content_id, content_type_id, name_ko, lat, lng, source FROM "
             f"(SELECT *, {SOURCE_SQL} AS source FROM activity.ac_place WHERE delisted_at IS NULL) a "
             "WHERE source = ANY(%s) AND content_id = %s LIMIT 1")
#: 별칭(정규화한 키)이 가리키는 장소들 — 마이그레이션 306
SQL_ALIAS_IDS = "SELECT content_id FROM activity.ac_place_alias WHERE alias_norm = %s"
#: `fuzzy` 용 — 이름 조건 없이 원장 전체(같은 열 순서). 폐지된 곳은 뺀다
SQL_ALL = ("SELECT content_id, content_type_id, name_ko, lat, lng, source FROM "
           f"(SELECT *, {SOURCE_SQL} AS source FROM activity.ac_place WHERE delisted_at IS NULL) a "
           "WHERE source = ANY(%s) ORDER BY content_id")


def _loose(text: str) -> str:
    """띄어쓰기·기호만 지운 비교 키. 지점 접미어·괄호는 **떼지 않는다**."""
    return re.sub(r"[\s·\-_/]+", "", unicodedata.normalize("NFKC", text or "")).lower()


def _like(pattern: str) -> str:
    escaped = pattern.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _hit(row: dict[str, Any]) -> dict[str, Any]:
    return {"content_id": row["content_id"], "content_type_id": row["content_type_id"],
            "matched_title": row["title"], "latitude": row["latitude"], "longitude": row["longitude"],
            "source": row["source"]}


def _fuzzy_hit(rows: list[dict[str, Any]], match: str, note: str) -> dict[str, Any]:
    if len(rows) == 1:
        return {"status": "found", "via": "place_catalog", **_hit(rows[0]), "match": match, "needs_review": True, "note": note}
    return {"status": "ambiguous", "via": "place_catalog", "match_count": len(rows), "match": match,
            "candidates": [{"content_id": r["content_id"], "title": r["title"]} for r in rows[:SHOW_LIMIT]]}


def _find_fuzzy(connection_factory: Callable[[], Any], query: str, key: str, sources: tuple[str, ...]) -> dict[str, Any] | None:
    """어순이 다른 이름 → 오타 순서로 하나를 찾는다. 못 찾으면 `None`."""
    with connection_factory() as conn, conn.cursor() as cur:
        cur.execute(SQL_ALL, (list(sources),))
        rows = [dict(zip(_COLUMNS, r)) for r in cur.fetchall()]
    words = word_set(query)
    if len(words) >= 2:
        same = [r for r in rows if word_set(r["title"]) == words]
        if same:
            return _fuzzy_hit(same, "word_order", "단어 순서가 달라도 같은 이름으로 보고 찾았다")
    by_key: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_key.setdefault(_loose(r["title"]), []).append(r)
    typo = TypoIndex(by_key.items()).best(key)
    if typo is None:
        return None
    matched, ratio = typo
    return _fuzzy_hit(matched, "typo", f"오타로 보고 「{matched[0]['title']}」로 찾았다(자모 거리 비율 {ratio:.2f})")


def _find_alias(connection_factory: Callable[[], Any], query: str, sources: tuple[str, ...]) -> dict[str, Any] | None:
    """별칭(시드 파일 + DB 표)이 **한 장소**로 정하는 이름이면 그 장소. 별칭이 아니거나 모호하거나 원장에 없으면(폐지) `None`.

    ★시드 파일은 배포에 실려 DB 적재와 상관없이 늘 적용된다. DB 표는 추가 별칭이다(표가 아직 없으면 시드만).
    """
    key = place_aliases.key_of(query)
    ids = set(place_aliases.seed_table().content_ids_for(query))
    if not key:
        return None
    with connection_factory() as conn, conn.cursor() as cur:
        cur.execute(ALIAS_EXISTS_SQL)
        exists = cur.fetchone()
        if exists and exists[0]:
            cur.execute(SQL_ALIAS_IDS, (key,))
            ids |= {str(r[0]) for r in cur.fetchall()}
        if len(ids) != 1:
            return None                           # 별칭이 아니거나, 둘 이상을 가리키면(모호) 쓰지 않는다
        cur.execute(SQL_BY_ID, (list(sources), next(iter(ids))))
        rows = [dict(zip(_COLUMNS, r)) for r in cur.fetchall()]
    if len(rows) != 1:
        return None
    return {"status": "found", "via": "place_catalog", **_hit(rows[0]), "match": "alias",
            "note": f"별칭 「{query}」로 「{rows[0]['title']}」를 찾았다"}


def find_place_by_name(connection_factory: Callable[[], Any], tenant_id: str, name: str | None, *,
                       sources: tuple[str, ...] = DEFAULT_SOURCES, fuzzy: bool = False) -> dict[str, Any]:
    """이름으로 원장에서 찾는다. 항상 `status` 가 있는 dict 를 준다(모름이 아니라 **없음**을 말할 수 있다). `tenant_id` 는 쓰지 않는다."""
    query = (name or "").strip()
    key = _loose(query)
    if len(key) < 2:
        return {"status": "not_found", "via": "place_catalog", "reason": "name_too_short"}
    with connection_factory() as conn, conn.cursor() as cur:
        cur.execute(SQL, (list(sources), _like(key), FETCH_LIMIT))
        rows = [dict(zip(_COLUMNS, r)) for r in cur.fetchall()]

    exact = [r for r in rows if _loose(r["title"]) == key]
    pool = exact or [r for r in rows if normalize(r["title"]) == normalize(query)]
    if not pool:
        # ★`[2026-10-19]` 사람이 확인한 별칭(「남산타워」 → 「남산서울타워」) — 글자가 달라 위 비교가 못 찾은 이름. `fuzzy` 와 상관없이 확정이다
        by_alias = _find_alias(connection_factory, query, sources)
        if by_alias is not None:
            return by_alias
        if fuzzy:
            guessed = _find_fuzzy(connection_factory, query, key, sources)
            if guessed is not None:
                return guessed
        return {"status": "not_found", "via": "place_catalog"}
    if len(pool) == 1:
        return {"status": "found", "via": "place_catalog", **_hit(pool[0])}
    return {"status": "ambiguous", "via": "place_catalog", "match_count": len(pool),
            "candidates": [{"content_id": r["content_id"], "title": r["title"]} for r in pool[:SHOW_LIMIT]]}
