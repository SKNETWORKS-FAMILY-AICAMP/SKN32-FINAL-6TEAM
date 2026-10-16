# -*- coding: utf-8 -*-
"""`app/domains/travel_ops/instances/activity/db_search/place_candidates.py` — `read.place_candidates` 의 DB 조회.

가짜 연결로 SQL 인자와 행 → 계약 모양 변환을 본다(실 DB 없이).
★`[2026-10-16 사용자 결정]` 활동 원장(`activity.ac_place`)만 읽는다 — `place_catalog` 를 쓰지 않고 테넌트를 나누지 않는다.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.tools.read_tools import ReadToolbox, ToolContext
from app.domains.travel_ops.instances.activity.alternatives import RADIUS_MAX_KM, bounding_box
from app.domains.travel_ops.instances.activity.db_search.place_candidates import (
    DEFAULT_SOURCES, ORIGIN_SQL, POOL_EXCLUDED_CLASSES, POOL_SQL, find_place_candidates)

UTC = timezone.utc
OLD = datetime(2026, 9, 20, tzinfo=UTC)
NEW = datetime(2026, 9, 28, tzinfo=UTC)


def _record(cid, *, title, l1="HS", sgg="23", lon=126.98, lat=37.58,
            closed="연중무휴", fetched=NEW, brand=None):
    # 원장 칸 순서(`_COLUMNS`): content_id · content_type_id · name_ko · lat · lng · lcls1~3 · sigungu_code · brand ·
    #   usetime_text · restdate_text · addr1 · updated_at
    return (cid, "12", title, lat, lon, l1, l1 + "01", l1 + "010100", sgg, brand,
            "09:00~18:00", closed, None, fetched)


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self._result: list = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params):
        self.conn.executed.append((sql, params))
        self._result = self.conn.origin if sql == ORIGIN_SQL else self.conn.pool

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result)


class FakeConnection:
    def __init__(self, origin, pool):
        self.origin, self.pool = origin, pool
        self.executed: list = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self):
        return FakeCursor(self)


ORIGIN = _record("126511", title="창경궁", closed="매주 월요일", fetched=OLD)
NEAR = _record("c1", title="성균관 명륜당")
NO_COORD = _record("c2", title="좌표 없음", lon=None, lat=None)


def test_returns_origin_and_candidates_in_the_csv_shape():
    conn = FakeConnection([ORIGIN], [NEAR, NO_COORD])
    pool = find_place_candidates(lambda: conn, "t1", "126511")

    assert pool["origin"]["contentid"] == "126511"
    assert pool["origin"]["closed_days"] == "매주 월요일"
    assert [c["contentid"] for c in pool["candidates"]] == ["c1", "c2"]
    first = pool["candidates"][0]
    assert first == {"contentid": "c1", "title": "성균관 명륜당", "contenttypeid": "12",
                     "lclsSystm1": "HS", "lclsSystm2": "HS01", "lclsSystm3": "HS010100",
                     "lDongSignguCd": "23", "brand": None, "mapx": "126.98", "mapy": "37.58",
                     "closed_days": "연중무휴", "business_hours": "09:00~18:00",
                     "addr1": None}   # ★`[2026-10-07]` 재난문자를 후보의 구로 거르는 데 쓴다(이 행은 주소 없음)
    assert pool["source"] == "activity.ac_place:" + "+".join(DEFAULT_SOURCES)


def test_brand_comes_from_the_ledger_column():
    rec = _record("OY1", title="올영", brand="올리브영")
    conn = FakeConnection([rec], [rec])
    pool = find_place_candidates(lambda: conn, "t1", "OY1")
    assert pool["origin"]["brand"] == "올리브영" and pool["candidates"][0]["brand"] == "올리브영"


def test_nulled_coordinates_stay_unknown():
    """★적재 때 NULL 로 넣은 좌표는 모름 그대로다."""
    conn = FakeConnection([ORIGIN], [NO_COORD])
    candidate = find_place_candidates(lambda: conn, "t1", "126511")["candidates"][0]
    assert candidate["mapx"] is None and candidate["mapy"] is None


def test_confirmed_at_is_the_oldest_fetch():
    conn = FakeConnection([ORIGIN], [NEAR])
    assert find_place_candidates(lambda: conn, "t1", "126511")["confirmed_at"] == OLD.isoformat()


def test_pool_is_narrowed_by_the_max_radius_bounding_box():
    """★거리 1단계 — SQL 은 원래 장소 좌표 기준 10km 사각형으로만 거른다(분류·시군구로 좁히지 않는다)."""
    conn = FakeConnection([ORIGIN], [])
    find_place_candidates(lambda: conn, "t1", "126511")
    (sql1, p1), (sql2, p2) = conn.executed
    assert (sql1, p1) == (ORIGIN_SQL, (list(DEFAULT_SOURCES), "126511"))
    assert sql2 == POOL_SQL and "sigungu_code =" not in POOL_SQL
    assert p2 == (list(DEFAULT_SOURCES), "126511", list(POOL_EXCLUDED_CLASSES),
                  *bounding_box(37.58, 126.98, RADIUS_MAX_KM))


def test_origin_without_coordinates_reads_no_pool():
    conn = FakeConnection([_record("126511", title="창경궁", lon=None, lat=None)], [NEAR])
    pool = find_place_candidates(lambda: conn, "t1", "126511")
    assert pool["candidates"] == [] and len(conn.executed) == 1


def test_pool_reads_brand_sources_too():
    """★TourAPI 만 보면 브랜드 매장(OY/DS/AB/MS)이 후보에도, 원래 장소에도 못 든다."""
    assert {"tour_api", "oliveyoung", "daiso", "artbox", "musinsa"} <= set(DEFAULT_SOURCES)
    assert ") = ANY(%s)" in ORIGIN_SQL and ") = ANY(%s)" in POOL_SQL


def test_sources_can_be_narrowed():
    conn = FakeConnection([ORIGIN], [])
    pool = find_place_candidates(lambda: conn, "t1", "126511", sources=("tour_api",))
    assert conn.executed[0][1] == (["tour_api"], "126511")
    assert pool["source"] == "activity.ac_place:tour_api"


def test_unknown_origin_is_unknown():
    conn = FakeConnection([], [NEAR])
    assert find_place_candidates(lambda: conn, "t1", "999") is None
    assert len(conn.executed) == 1      # ★후보는 읽지 않는다


def test_no_content_id_does_not_open_a_connection():
    def boom():
        raise AssertionError("열면 안 된다")
    assert find_place_candidates(boom, "t1", "  ") is None


def test_read_tool_reads_the_shared_ledger_whatever_the_tenant():
    """★원장은 공공 장소 자료라 테넌트로 나누지 않는다(`ledger.py` 와 같다) — SQL 인자에 테넌트가 없다."""
    conn = FakeConnection([ORIGIN], [NEAR])
    scope = ToolContext("tenant-x", uuid4(), uuid4(), ["activity"])
    pool = ReadToolbox(lambda: conn).place_candidates(scope, content_id="126511")
    assert pool["origin"]["contentid"] == "126511"
    assert "tenant-x" not in conn.executed[0][1] and "tenant_id" not in ORIGIN_SQL + POOL_SQL


def test_reads_only_the_activity_ledger():
    """★`[2026-10-16 사용자 결정]` 운영시간 기준 표는 원장 하나 — 코어 `place_catalog` 를 읽지 않는다."""
    assert "activity.ac_place" in ORIGIN_SQL and "activity.ac_place" in POOL_SQL
    assert "place_catalog" not in ORIGIN_SQL + POOL_SQL


def test_festivals_and_delisted_places_are_not_candidates():
    """축제 · 행사(EV)는 기간 판정 전이라 후보로 내지 않는다(카탈로그 시절과 같은 동작) · 목록에서 내려간 곳도 뺀다."""
    assert "EV" in POOL_EXCLUDED_CLASSES
    assert "delisted_at IS NULL" in POOL_SQL and "delisted_at" not in ORIGIN_SQL
