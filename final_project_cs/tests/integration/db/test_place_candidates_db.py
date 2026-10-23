# -*- coding: utf-8 -*-
"""`app/domains/travel_ops/instances/activity/db_search/place_candidates.py` 를 **실 PostgreSQL** 로 돌린다.

두 가지를 본다.
  1. 원장에 시험 행 몇 개를 직접 넣고 조회 → SQL 이 실제로 맞는지.
  2. 적재된 실데이터(`scripts/activity/load_places.py`)가 있으면 창경궁(126511)으로 후보가 나오는지. 적재 전이면 건너뛴다.

★`[2026-10-16 사용자 결정]` 활동 원장(`activity.ac_place`)만 읽는다 — 원장은 공용이라 테넌트로 나누지 않는다.
  그래서 시험 행은 **서울 밖(제주 근처) 좌표**에 둔다 — 10km 사각형 안에 서울 실데이터가 섞이지 않게.
★DB 에 못 붙으면 **건너뛴다**(실패가 아니다) — `.env` 의 `ACOP_DATABASE_URL` 로 붙는다.
"""
from __future__ import annotations

import random
from contextlib import nullcontext
from uuid import uuid4

import psycopg
import pytest

from app.infrastructure.db.session import database_dsn, get_connection
from app.domains.travel_ops.instances.activity.alternatives import RADIUS_MAX_KM, bounding_box
from app.domains.travel_ops.instances.activity.db_search.place_candidates import find_place_candidates


def _reachable() -> str | None:
    try:
        with psycopg.connect(database_dsn(), connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass('activity.ac_place')")
            table = cur.fetchone()[0]
    except Exception as exc:  # noqa: BLE001 — 어떤 이유든 못 붙으면 건너뛴다
        return f"DB 에 연결할 수 없다: {type(exc).__name__}"
    if table is None:
        return "activity.ac_place(300) 가 없다 — `python -m app.infrastructure.db.migrate` 먼저"
    return None


_SKIP = _reachable()
pytestmark = pytest.mark.skipif(_SKIP is not None, reason=_SKIP or "")

INSERT = ("INSERT INTO activity.ac_place (content_id, content_type_id, name_ko, name_key, lat, lng, "
          "lcls1, lcls2, lcls3, sigungu_code, usetime_text, restdate_text, load_id) "
          "VALUES (%s,'12',%s,%s,%s,%s,%s,%s,%s,%s,'09:00~18:00',%s,%s)")


@pytest.fixture()
def world():
    """시험 행(제주 근처)을 넣고 이름 → 번호를 돌려준다. 번호 모양이 출처를 정한다(숫자 = 관광공사, OY = 올리브영)."""
    base = str(random.randint(10**9, 10**10 - 1))
    tag = uuid4().hex[:6]
    rows = [
        # key,        cid,              title,          lat,     lon,      l1,   sgg,  closed
        ("o1",        f"{base}1",       "원래 장소",     33.4496, 126.5600, "HS", "23", "매주 화요일"),
        ("same_l1",   f"{base}2",       "같은 대분류",   33.4700, 126.6330, "HS", "1",  "연중무휴"),
        ("same_gu",   f"{base}3",       "같은 자치구",   33.4500, 126.5630, "VE", "23", "연중무휴"),
        ("neither",   f"{base}4",       "둘 다 다름",    33.3700, 126.6830, "SH", "1",  "연중무휴"),   # 경도 약 11km — 사각형 밖
        ("no_xy",     f"{base}5",       "좌표 없음",     None,    None,     "HS", "5",  None),
        ("festival",  f"{base}6",       "근처 축제",     33.4510, 126.5610, "EV", "23", None),          # 축제 · 행사 — 후보 아님
        # 브랜드 — 같은 원장의 다른 출처. 후보에도 원래 장소에도 들어야 한다.
        ("OYtest1",   f"OY{tag}1",      "올영 테스트점", 33.4300, 126.5630, "SH", "23", "연중무휴"),
        ("OYtest2",   f"OY{tag}2",      "올영 다른점",   33.4400, 126.5730, "SH", "23", "연중무휴"),
    ]
    ids = {key: cid for key, cid, *_ in rows}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO activity.ac_load_meta (source_file, file_sha256, row_count) VALUES ('test', %s, %s) "
                    "RETURNING load_id", ("0" * 64, len(rows)))
        load_id = cur.fetchone()[0]
        for _, cid, title, lat, lon, l1, sgg, closed in rows:
            cur.execute(INSERT, (cid, title, title, lat, lon, l1, l1 + "01", l1 + "010100", sgg, closed, load_id))
    try:
        yield ids
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM activity.ac_place WHERE content_id = ANY(%s)", (list(ids.values()),))
            cur.execute("DELETE FROM activity.ac_load_meta WHERE load_id=%s", (load_id,))


def _keys(world, pool):
    back = {cid: key for key, cid in world.items()}
    return sorted(back[c["contentid"]] for c in pool["candidates"])


def test_pool_is_within_the_10km_bounding_box(world):
    """★분류와 무관하게 10km 사각형 안만 — `neither`(약 11km)와 좌표 없는 `no_xy`, 축제(EV)는 빠진다."""
    pool = find_place_candidates(get_connection, "any", world["o1"])

    assert pool["origin"]["title"] == "원래 장소"
    assert pool["origin"]["closed_days"] == "매주 화요일" and pool["origin"]["business_hours"] == "09:00~18:00"
    assert _keys(world, pool) == ["OYtest1", "OYtest2", "same_gu", "same_l1"]
    assert pool["source"].startswith("activity.ac_place:tour_api")
    assert pool["confirmed_at"]


def test_brand_store_as_origin_finds_brand_candidates(world):
    pool = find_place_candidates(get_connection, "any", world["OYtest1"])
    assert pool["origin"]["title"] == "올영 테스트점"
    assert world["OYtest2"] in [c["contentid"] for c in pool["candidates"]]


def test_a_festival_can_still_be_the_origin(world):
    """축제는 후보로 내지 않을 뿐, 고객이 고른 원래 장소로는 읽는다."""
    pool = find_place_candidates(get_connection, "any", world["festival"])
    assert pool["origin"]["lclsSystm1"] == "EV" and world["o1"] in [c["contentid"] for c in pool["candidates"]]


def test_null_coordinates_are_not_in_the_pool(world):
    """좌표가 없으면 근처인지 모른다 — 범위 비교에서 빠진다."""
    pool = find_place_candidates(get_connection, "any", world["o1"])
    assert world["no_xy"] not in [c["contentid"] for c in pool["candidates"]]


def test_unknown_origin_is_unknown_and_the_ledger_is_shared_across_tenants(world):
    assert find_place_candidates(get_connection, "any", "없는ID") is None
    other = find_place_candidates(get_connection, "other_" + uuid4().hex, world["o1"])
    assert _keys(world, other) == _keys(world, find_place_candidates(get_connection, "any", world["o1"]))


def test_loaded_ledger_finds_alternatives_for_changgyeonggung():
    """적재된 실데이터 확인. wiki/teams/activity.md 실측: 창경궁(126511)."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM activity.ac_place WHERE content_id ~ '^[0-9]+$'")
        loaded = cur.fetchone()[0]
    if not loaded:
        pytest.skip("원장에 적재된 데이터가 없다 — scripts/activity/load_places.py 먼저")

    pool = find_place_candidates(get_connection, "demo", "126511")
    assert pool is not None, "창경궁(126511)이 원장에 없다"
    assert pool["origin"]["lclsSystm1"] == "HS"
    assert pool["candidates"], "후보가 0건이다"
    lat0, lat1, lng0, lng1 = bounding_box(float(pool["origin"]["mapy"]), float(pool["origin"]["mapx"]),
                                          RADIUS_MAX_KM)
    assert all(lat0 <= float(c["mapy"]) <= lat1 and lng0 <= float(c["mapx"]) <= lng1
               for c in pool["candidates"])
    assert all(c["lclsSystm1"] != "EV" for c in pool["candidates"])


def test_delisted_places_are_not_candidates(world):
    """`[2026-10-12]` 관광공사 목록에서 내려간 곳(끝난 축제 · 폐업)은 대체 후보로 내지 않는다(303)."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE activity.ac_place SET delisted_at = now() WHERE content_id=%s", (world["same_l1"],))
        try:
            pool = find_place_candidates(lambda: nullcontext(conn), "any", world["o1"])      # 같은 연결 — 되돌릴 수 있게
            assert world["same_l1"] not in [c["contentid"] for c in pool["candidates"]]
        finally:
            conn.rollback()
