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

import logging
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


def _alias_rows(cur: Any, query: str, sources: tuple[str, ...]) -> list[dict[str, Any]] | None:
    """별칭(시드 파일 + DB 표)이 가리키는 원장 행. 별칭이 아니거나 둘 이상을 가리키면(모호) `None`."""
    key = place_aliases.key_of(query)
    if not key:
        return None
    ids = set(place_aliases.seed_table().content_ids_for(query))
    cur.execute(ALIAS_EXISTS_SQL)
    exists = cur.fetchone()
    if exists and exists[0]:
        cur.execute(SQL_ALIAS_IDS, (key,))
        ids |= {str(r[0]) for r in cur.fetchall()}
    if len(ids) != 1:
        return None                               # 별칭이 아니거나, 둘 이상을 가리키면(모호) 쓰지 않는다
    cur.execute(SQL_BY_ID, (list(sources), next(iter(ids))))
    return [dict(zip(_COLUMNS, r)) for r in cur.fetchall()]


def _find_alias(connection_factory: Callable[[], Any], query: str, sources: tuple[str, ...]) -> dict[str, Any] | None:
    """별칭(시드 파일 + DB 표)이 **한 장소**로 정하는 이름이면 그 장소. 별칭이 아니거나 모호하거나 원장에 없으면(폐지) `None`.

    ★시드 파일은 배포에 실려 DB 적재와 상관없이 늘 적용된다. DB 표는 추가 별칭이다(표가 아직 없으면 시드만).
    """
    with connection_factory() as conn, conn.cursor() as cur:
        rows = _alias_rows(cur, query, sources)
    if not rows or len(rows) != 1:
        return None
    return {"status": "found", "via": "place_catalog", **_hit(rows[0]), "match": "alias",
            "note": f"별칭 「{query}」로 「{rows[0]['title']}」를 찾았다"}


def alias_target(conn: Any | None, name: str | None, *, sources: tuple[str, ...] = DEFAULT_SOURCES) -> dict[str, Any] | None:
    """`[2026-10-22 사용자 지시]` 별칭이 **한 장소**로 정하는 이름이면 그 장소 — 코어의 모든 이름 찾기(계획 읽기 · 확인 화면 검색 · 채팅 고치기)가
    「우리 자료 정확 일치 → **별칭** → … → 카카오」 순서로 이것을 부른다(`components/team_hooks/place_aliases.py`).

    반환 `{"content_id", "title", "content_type_id", "latitude", "longitude", "source"}` · 별칭이 아니거나 모호하거나 폐지면 `None`.
    `conn` 은 셋 중 하나다:
      - 열린 연결 — 시드 + DB 표를 보고 원장 행(좌표)까지 싣는다(확인 화면 검색 · 이름 고치기). 세이브포인트 안에서 읽는다 —
        실패한 읽기가 부르는 쪽 트랜잭션을 막지 않게(`ledger._web_entries` 와 같다).
      - 연결을 여는 함수 — 계획 읽기처럼 모델을 기다리며 연결을 잡지 않는 길. DB 표는 1분 기억한 사본(`_db_alias_snapshot`)을 쓰고 좌표는 비운다.
      - `None` · 원장을 못 읽음 — **시드 파일만** 본다(정식 제목만 · 좌표 없음).
    좌표가 비면 부르는 쪽이 그 정식 제목으로 다시 찾는다."""
    query = (name or "").strip()
    if len(_loose(query)) < 2:
        return None
    if conn is not None and hasattr(conn, "cursor"):
        try:
            with conn.transaction(), conn.cursor() as cur:
                rows = _alias_rows(cur, query, sources)
                if rows and len(rows) == 1:
                    # ★관광공사 목록(`place_catalog`)에 행이 없어도 지역 확인(「서울」)을 통과하게 활동 원장 주소를 싣는다
                    cur.execute("SELECT addr1 FROM activity.ac_place WHERE content_id = %s", (str(rows[0]["content_id"]),))
                    found = cur.fetchone()
                    rows[0]["address"] = found[0] if found else None
        except Exception as exc:  # noqa: BLE001 — 원장 · 별칭 표를 못 읽으면 시드만 본다(별칭이 없는 것과 다르지 않게)
            logging.getLogger(__name__).warning("activity alias_target db read failed reason=%s", type(exc).__name__)
        else:
            if rows is None or len(rows) != 1:
                return None
            r = rows[0]
            return {"content_id": str(r["content_id"]), "title": r["title"], "content_type_id": str(r["content_type_id"] or ""),
                    "latitude": r["latitude"], "longitude": r["longitude"], "source": r["source"], "address": r.get("address")}
        conn = None
    key = place_aliases.key_of(query)
    ids = set(place_aliases.seed_table().content_ids_for(query))
    titles: dict[str, str] = {}
    if callable(conn):
        snapshot = _db_alias_snapshot(conn)
        ids |= set(snapshot.get(key, {}))
        titles = snapshot.get(key, {})
    if len(ids) != 1:
        return None
    content_id = next(iter(ids))
    title = place_aliases.seed_title(content_id) or titles.get(content_id)
    return {"content_id": content_id, "title": title, "content_type_id": None, "latitude": None, "longitude": None,
            "source": "seed"} if title else None


#: DB 별칭 사본을 기억하는 시간(초) — 운영 중에 더한 별칭이 1분 안에 계획 읽기에도 쓰인다. 우리가 고른 값
SNAPSHOT_TTL_S = 60.0
_snapshot: tuple[float, dict[str, dict[str, str]]] | None = None
SQL_ALIAS_SNAPSHOT = ("SELECT a.alias_norm, a.content_id, p.name_ko FROM activity.ac_place_alias a "
                      "JOIN activity.ac_place p ON p.content_id = a.content_id WHERE p.delisted_at IS NULL")


def _db_alias_snapshot(connection_factory: Callable[[], Any]) -> dict[str, dict[str, str]]:
    """DB 별칭 표 전체(정규화한 별칭 → {contentid: 정식 제목}) — 폐지된 곳은 뺀다. 표가 없거나 못 읽으면 빈 dict(시드만 쓴다)."""
    import time

    global _snapshot
    now = time.monotonic()
    if _snapshot is not None and now - _snapshot[0] < SNAPSHOT_TTL_S:
        return _snapshot[1]
    table: dict[str, dict[str, str]] = {}
    try:
        with connection_factory() as conn, conn.cursor() as cur:
            cur.execute(ALIAS_EXISTS_SQL)
            exists = cur.fetchone()
            if exists and exists[0]:
                cur.execute(SQL_ALIAS_SNAPSHOT)
                for alias_norm, content_id, title in cur.fetchall():
                    table.setdefault(str(alias_norm), {})[str(content_id)] = str(title)
    except Exception as exc:  # noqa: BLE001 — 못 읽으면 시드만 쓴다. 다음 부름에 다시 읽게 기억하지 않는다
        logging.getLogger(__name__).warning("activity alias snapshot read failed reason=%s", type(exc).__name__)
        return {}
    _snapshot = (now, table)
    return table


def clear_snapshot() -> None:
    """시험 · 별칭 표를 고친 직후용."""
    global _snapshot
    _snapshot = None


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
