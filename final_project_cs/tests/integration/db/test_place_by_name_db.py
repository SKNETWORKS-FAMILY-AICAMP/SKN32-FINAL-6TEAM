# -*- coding: utf-8 -*-
"""`db_search/place_by_name.py` 의 SQL 을 **실 PostgreSQL** 로 돌린다. DB 에 못 붙으면 건너뛴다.

★`[2026-10-16 사용자 결정]` 활동 원장(`activity.ac_place`)을 읽는다 — 원장은 공용이라 테넌트로 나누지 않는다.
  실데이터(서울 6천여 곳)와 이름이 겹치지 않게 시험 행 이름 앞에 시험마다 다른 표시(`T`)를 붙인다.
"""
from __future__ import annotations

import random
from uuid import uuid4

import psycopg
import pytest

from app.infrastructure.db.session import database_dsn, get_connection
from app.domains.travel_ops.instances.activity.db_search.place_by_name import find_place_by_name


def _reachable() -> str | None:
    try:
        with psycopg.connect(database_dsn(), connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass('activity.ac_place')")
            if cur.fetchone()[0] is None:
                return "activity.ac_place 가 없다 — migrate 먼저"
    except Exception as exc:  # noqa: BLE001
        return f"DB 에 연결할 수 없다: {type(exc).__name__}"
    return None


_SKIP = _reachable()
pytestmark = pytest.mark.skipif(_SKIP is not None, reason=_SKIP or "")

INSERT = ("INSERT INTO activity.ac_place (content_id, content_type_id, name_ko, name_key, lat, lng, lcls1, load_id) "
          "VALUES (%s,'12',%s,%s,33.45,126.56,'HS',%s)")


@pytest.fixture()
def world():
    """시험 행을 넣고 표시(`T`) · 번호를 돌려준다. 번호는 출처를 가르는 모양(숫자 = 관광공사, DS = 다이소)을 지킨다."""
    tag = "zq" + uuid4().hex[:6]
    base = str(random.randint(10**9, 10**10 - 1))
    rows = [(f"{base}1", "경복궁"), (f"{base}2", "서울숲"), (f"{base}3", "서울 숲(북쪽)"),
            (f"DS{tag}1", "다이소 강남점"), (f"DS{tag}2", "다이소 홍대점"),
            (f"{base}4", "100%_할인 마켓"), (f"{base}5", "롯데-월드")]
    ids = {title: cid for cid, title in rows}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO activity.ac_load_meta (source_file, file_sha256, row_count) VALUES ('test', %s, %s) "
                    "RETURNING load_id", ("0" * 64, len(rows)))
        load_id = cur.fetchone()[0]
        for cid, title in rows:
            cur.execute(INSERT, (cid, tag + title, tag + title, load_id))
    try:
        yield {"tag": tag, "ids": ids}
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM activity.ac_place WHERE content_id = ANY(%s)", ([cid for cid, _ in rows],))
            cur.execute("DELETE FROM activity.ac_load_meta WHERE load_id=%s", (load_id,))


def _find(world, name, tenant="any"):
    return find_place_by_name(get_connection, tenant, world["tag"] + name)


def test_exact_name_is_found(world):
    out = _find(world, "경복궁")
    assert out["status"] == "found" and out["content_id"] == world["ids"]["경복궁"]
    assert out["matched_title"] == world["tag"] + "경복궁" and out["source"] == "tour_api"


def test_spacing_is_ignored(world):
    assert _find(world, "서울  숲")["content_id"] == world["ids"]["서울숲"]


def test_branch_stores_with_same_base_name_are_ambiguous(world):
    out = _find(world, "다이소")
    assert out["status"] == "ambiguous" and out["match_count"] == 2


def test_specific_branch_is_found(world):
    out = _find(world, "다이소 강남점")
    assert out["content_id"] == world["ids"]["다이소 강남점"] and out["source"] == "daiso"


def test_unknown_name_is_not_found(world):
    assert _find(world, "듣도보도못한곳")["status"] == "not_found"


def test_like_wildcards_in_the_name_are_literal(world):
    assert _find(world, "100%_할인 마켓")["content_id"] == world["ids"]["100%_할인 마켓"]
    assert find_place_by_name(get_connection, "any", "%%")["status"] == "not_found"


def test_hyphen_and_slash_in_title_are_ignored(world):
    assert _find(world, "롯데월드")["content_id"] == world["ids"]["롯데-월드"]


def test_the_shared_ledger_answers_the_same_for_any_tenant(world):
    """★원장은 공용이다 — 테넌트가 달라도 같은 답이다(전에는 카탈로그의 테넌트별 행이라 다른 테넌트는 못 찾았다)."""
    assert _find(world, "경복궁", tenant="other_" + uuid4().hex) == _find(world, "경복궁")
