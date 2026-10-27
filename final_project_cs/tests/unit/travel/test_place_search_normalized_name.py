"""장소 이름 검색 — 띄어쓰기 · 가운뎃점이 달라도 같은 이름을 찾는다. `[2026-10-27 장소 품질 전수검사]`

☆실측(로컬 acop_cs 읽기 전용, 외부 호출 0): 서울 명소 이름에 띄어쓰기 하나를 넣으면(「도산 공원」) 1/18 = 5.6% 만 찾았고,
  목록 이름의 띄어쓰기를 뺀 검색(「서울명동성당」 ↔ 목록 「서울 명동성당」)은 14/30 = 46.7% 였다(원래 이름 그대로는 19/30 = 63.3%).
  원인: 관광공사 목록 · 요식 원장 이름 검색이 `ILIKE '%검색어%'` 원문 비교뿐이었다.
★두 단계 — 원문 비교로 정규화 이름이 같은 곳을 찾으면 그대로(추가 조회 0), 못 찾았을 때만 정규화 이름 비교를 한 번 더 한다
  (정규화 비교는 8천 행 순차 비교라 매번 하면 한 번에 약 22 ms 가 더 든다 — 같은 날 실측).
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.domains.travel_ops.components.intake import candidates as c


class _Cursor:
    def __init__(self, conn):
        self.conn = conn
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, args=None):
        self.conn.calls.append((sql, list(args or [])))
        self._rows = self.conn.answer(sql, list(args or []))

    def fetchall(self):
        return list(self._rows)


class _Conn:
    """SQL 을 기록하고, 정규화 비교 SQL(`regexp_replace`)이면 `normalized` 행을, 아니면 `plain` 행을 돌려준다."""

    def __init__(self, plain, normalized):
        self.plain, self.normalized, self.calls = plain, normalized, []

    def answer(self, sql, args):
        return self.normalized if "regexp_replace" in sql.split("ORDER BY")[0] else self.plain

    def cursor(self):
        return _Cursor(self)

    def transaction(self):
        class _T:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *exc):
                return False
        return _T()


@pytest.fixture(autouse=True)
def _no_hours(monkeypatch):
    from app.domains.travel_ops.components.places import catalog_pool
    monkeypatch.setattr(catalog_pool, "reuse_hours", lambda *a, **kw: None)


NOW = datetime(2026, 11, 3, 14, 0)
DOSAN = ("126512", "12", "도산공원", "서울특별시 강남구 신사동", 37.524, 127.035)


def test_spaced_query_finds_the_catalog_name_without_spaces():
    conn = _Conn(plain=[], normalized=[DOSAN])
    out = c._db_places_by_name(conn, "demo", "도산 공원", None, NOW)
    assert [p["name"] for p in out] == ["도산공원"]
    sqls = [sql for sql, _ in conn.calls]
    assert len(sqls) == 2 and "regexp_replace" not in sqls[0].split("ORDER BY")[0]
    assert "%도산공원%" in conn.calls[1][1]                    # 정규화한 검색어로 비교했다


def test_unspaced_query_finds_a_catalog_name_with_spaces():
    row = ("126536", "12", "서울 명동성당", "서울특별시 중구 명동길 74", 37.563, 126.987)
    conn = _Conn(plain=[], normalized=[row])
    out = c._db_places_by_name(conn, "demo", "서울명동성당", None, NOW)
    assert [p["name"] for p in out] == ["서울 명동성당"]


def test_exact_plain_hit_needs_no_second_query():
    conn = _Conn(plain=[DOSAN], normalized=[])
    out = c._db_places_by_name(conn, "demo", "도산공원", None, NOW)
    assert [p["name"] for p in out] == ["도산공원"] and len(conn.calls) == 1


def test_second_query_adds_rows_once_and_keeps_plain_rows_first():
    near = ("1", "12", "도산공원 앞 광장", "서울특별시 강남구", 37.52, 127.03)
    conn = _Conn(plain=[near], normalized=[near, DOSAN])
    out = c._db_places_by_name(conn, "demo", "도산 공원", None, NOW)
    assert [p["content_id"] for p in out] == ["1", "126512"]          # 같은 행은 한 번만


def test_ledger_spaced_query_finds_the_restaurant():
    row = ("00000000-0000-0000-0000-000000000001", "진진", 37.55, 126.92, "서울 마포구", None)
    conn = _Conn(plain=[], normalized=[row])
    out = c._ledger_places(conn, "demo", None, query="진 진", radius_m=None)
    assert [p["name"] for p in out] == ["진진"]
    assert len(conn.calls) == 2 and "%진진%" in conn.calls[1][1]


def test_ledger_exact_plain_hit_needs_no_second_query():
    row = ("00000000-0000-0000-0000-000000000001", "진진", 37.55, 126.92, "서울 마포구", None)
    conn = _Conn(plain=[row], normalized=[])
    out = c._ledger_places(conn, "demo", None, query="진진", radius_m=None)
    assert [p["name"] for p in out] == ["진진"] and len(conn.calls) == 1


def test_second_query_prefilters_on_hangul_edge_characters_only():
    """정규화 비교는 행마다 정규식이라 비싸다 — 정규화 검색어의 첫 · 끝 글자가 한글이면 원문 `ILIKE` 로 먼저 줄인다(로컬 실측 28 → 12 ms).
    한글 음절은 NFKC · 대소문자에 바뀌지 않아 줄여도 빠지는 행이 없다. 한글이 아닌 끝 글자(「N서울타워」의 n)는 줄이는 데 쓰지 않는다."""
    conn = _Conn(plain=[], normalized=[DOSAN])
    c._db_places_by_name(conn, "demo", "도산 공원", None, NOW)
    sql, args = conn.calls[1]
    assert "title ILIKE %s AND title ILIKE %s AND regexp_replace" in sql and "%도%" in args and "%원%" in args
    conn = _Conn(plain=[], normalized=[])
    c._db_places_by_name(conn, "demo", "N 서울타워", None, NOW)
    sql, args = conn.calls[1]
    assert "%n%" not in args and "%N%" not in args and "%워%" in args and "%n서울타워%" in args


def _search_with_counted_catalog(monkeypatch, rows):
    calls = []

    def by_name(conn, tenant_id, query, ref, now, *a, **kw):
        calls.append(ref)
        return [dict(r) for r in rows]
    monkeypatch.setattr(c, "_db_places_by_name", by_name)
    monkeypatch.setattr(c, "_ledger_places", lambda *a, **kw: [])
    monkeypatch.setattr(c, "_alias_places", lambda *a, **kw: [])
    monkeypatch.setattr(c, "assess", lambda *a, **kw: {"status": "ok", "fits": True})
    monkeypatch.setattr(c, "_present", lambda p, *a, **kw: {"place": p})
    item = {"id": "i1", "kind": "activity", "parts": {}, "place": {"name": "경복궁", "latitude": 37.58, "longitude": 126.977},
            "date": "2026-11-03"}
    out = c.search(None, tenant_id="demo", review={"items": [item]}, item=item, query="공원", kakao=None,
                   by_relevance=True, around_self=True)
    return out, calls


def test_relevance_list_reuses_a_complete_catalog_answer(monkeypatch):
    """`[2026-10-27]` 거리순으로 받은 관광공사 목록이 한도보다 적으면 이름이 맞는 전부다 — 이름순 목록을 위해 같은 조건을 다시 묻지 않는다(로컬 실측 17~30 ms/회)."""
    rows = [c._place("도산공원", 37.524, 127.035, "tour_api", kind="activity", content_id="1"),
            c._place("공원", 37.50, 127.0, "tour_api", kind="activity", content_id="2")]
    out, calls = _search_with_counted_catalog(monkeypatch, rows)
    assert len(calls) == 1 and calls[0] is not None
    assert [r["place"]["name"] for r in out["relevance"]] == ["공원", "도산공원"]      # 이름순(정확 → 길이)


def test_relevance_list_queries_again_when_the_catalog_answer_was_cut(monkeypatch):
    rows = [c._place(f"공원{i}", 37.5 + i / 1000, 127.0, "tour_api", kind="activity", content_id=str(i))
            for i in range(c.CATALOG_NAME_LIMIT)]
    _out, calls = _search_with_counted_catalog(monkeypatch, rows)
    assert len(calls) == 2 and calls[1] is None                                       # 잘렸으면 이름순으로 다시 묻는다
