# -*- coding: utf-8 -*-
"""원문 바뀜 알아채기(`scripts/activity/refresh_places.py`) — 가짜 목록 · 상세로(관광공사 안 부름). 실 PostgreSQL. `[2026-10-12]`"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from app.infrastructure.db.session import database_dsn, get_connection

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("activity_refresh_places", ROOT / "scripts" / "activity" / "refresh_places.py")
refresh_places = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(refresh_places)


def _reachable() -> str | None:
    try:
        with psycopg.connect(database_dsn(), connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='activity' "
                        "AND table_name='ac_place' AND column_name='delisted_at'")
            if not cur.fetchone()[0]:
                return "302 · 303 이 안 돌았다 — migrate 먼저"
    except Exception as exc:  # noqa: BLE001
        return f"DB 에 연결할 수 없다: {type(exc).__name__}"
    return None


_SKIP = _reachable()
pytestmark = pytest.mark.skipif(_SKIP is not None, reason=_SKIP or "")
WEEK = json.dumps({"mon": {"open": "09:00", "close": "18:00"}})


@pytest.fixture()
def cid():
    cid = str(9_000_000_000 + uuid4().int % 1_000_000)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO activity.ac_load_meta (source_file, file_sha256, row_count) VALUES ('t', %s, 1) "
                    "RETURNING load_id", ("0" * 64,))
        load_id = cur.fetchone()[0]
        cur.execute("INSERT INTO activity.ac_place (content_id, content_type_id, name_ko, name_key, usetime_text, "
                    "restdate_text, hours_week, hours_read, load_id) VALUES (%s,'12','시험궁','시험궁','09:00~18:00',"
                    "'매주 화요일', %s, '{\"method\": \"rule\"}', %s)", (cid, WEEK, load_id))
    try:
        yield cid
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM activity.ac_place WHERE content_id = %s", (cid,))
            cur.execute("DELETE FROM activity.ac_load_meta WHERE load_id = %s", (load_id,))


def _row(conn, cid):
    with conn.cursor() as cur:
        cur.execute("SELECT source_modified_at, usetime_text, restdate_text, hours_week FROM activity.ac_place "
                    "WHERE content_id = %s", (cid,))
        return cur.fetchone()


def _listed(cid, mod):
    return [{"contentid": cid, "contenttypeid": "12", "modifiedtime": mod},
            {"contentid": "OY12345", "contenttypeid": "38", "modifiedtime": "x"},          # 브랜드 — 보지 않는다
            {"contentid": "9999999999", "contenttypeid": "12", "modifiedtime": "x"}]       # 원장에 없음 — 세기만


def test_first_sight_is_only_a_baseline_and_fetches_nothing(cid):
    calls = []
    with get_connection() as conn, conn.transaction():
        out = refresh_places.refresh(conn, _listed(cid, "20261001000000"), lambda *a: calls.append(a))
        row = _row(conn, cid)
    assert out["baseline"] == 1 and out["not_in_ledger"] == 1 and calls == []
    assert row[0] == "20261001000000" and row[3] is not None          # 요일표 그대로


def test_a_changed_place_is_refetched_and_its_week_cleared_when_the_text_changed(cid):
    with get_connection() as conn, conn.transaction():
        refresh_places.refresh(conn, _listed(cid, "20261001000000"), lambda *a: None)          # 기준점
        out = refresh_places.refresh(conn, _listed(cid, "20261012000000"),
                                     lambda c, t: {"usetime": "10:00~17:00", "restdate": "매주 월요일"})
        row = _row(conn, cid)
    assert (out["changed"], out["refetched"], out["text_changed"]) == (1, 1, 1)
    assert row == ("20261012000000", "10:00~17:00", "매주 월요일", None)   # 요일표를 비웠다 → read_hours 가 다시 편다


def test_a_changed_time_with_the_same_text_keeps_the_week(cid):
    with get_connection() as conn, conn.transaction():
        refresh_places.refresh(conn, _listed(cid, "20261001000000"), lambda *a: None)
        out = refresh_places.refresh(conn, _listed(cid, "20261012000000"),
                                     lambda c, t: {"usetime": "09:00~18:00", "restdate": "매주 화요일"})
        row = _row(conn, cid)
    assert out["text_changed"] == 0 and row[3] is not None


def test_the_call_limit_and_dry_run_write_nothing_beyond(cid):
    with get_connection() as conn, conn.transaction():
        refresh_places.refresh(conn, _listed(cid, "20261001000000"), lambda *a: None)
        limited = refresh_places.refresh(conn, _listed(cid, "20261012000000"), lambda *a: {}, max_calls=0)
        dry = refresh_places.refresh(conn, _listed(cid, "20261012000000"),
                                     lambda c, t: {"usetime": "x", "restdate": "y"}, dry_run=True)
        row = _row(conn, cid)
    assert limited["over_limit"] == 1 and dry["text_changed"] == 1
    assert row[0] == "20261001000000" and row[1] == "09:00~18:00"            # 둘 다 쓰지 않았다


def test_a_place_missing_from_the_full_list_is_marked_and_unmarked_when_it_returns(cid):
    def delisted(conn):
        with conn.cursor() as cur:
            cur.execute("SELECT delisted_at IS NOT NULL FROM activity.ac_place WHERE content_id = %s", (cid,))
            return cur.fetchone()[0]

    with get_connection() as conn:                                     # 끝에서 되돌린다 — 다른 장소 표시를 남기지 않는다
        gone = refresh_places.mark_listing(conn, {"1"})                # 목록에 없다
        assert gone["delisted"] >= 1 and delisted(conn) is True
        back = refresh_places.mark_listing(conn, {cid})                # 다시 나타났다
        assert back["relisted"] >= 1 and delisted(conn) is False
        conn.rollback()


def test_new_rows_are_only_unknown_places_registered_since_the_date(cid):
    listed = [{"contentid": cid, "createdtime": "20261005000000"},          # 이미 원장에 있음
              {"contentid": "9999999998", "createdtime": "20261005000000"},  # 새로 등록
              {"contentid": "9999999997", "createdtime": "20250101000000"}]  # 오래전 등록 — 일부러 뺐을 수 있다
    with get_connection() as conn:
        assert [r["contentid"] for r in refresh_places.new_rows_since(conn, listed, "20260929")] == ["9999999998"]
