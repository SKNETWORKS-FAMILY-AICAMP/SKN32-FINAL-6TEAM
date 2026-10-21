# -*- coding: utf-8 -*-
"""활동 원장 판정(`instances/activity/ledger.state`)의 SQL 을 **실 PostgreSQL** 로 돌린다. DB 에 못 붙으면 건너뛴다."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import psycopg
import pytest

from app.domains.travel_ops.instances.activity import ledger
from app.infrastructure.db.session import database_dsn, get_connection

KST = ZoneInfo("Asia/Seoul")


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


@pytest.fixture()
def seeded():
    """시험 전용 원장 행 둘 + 코어 장소 셋(원장 연결 · 속성으로 연결 · 연결 없음)."""
    tenant, cid, cid2 = "test_" + uuid4().hex, "T" + uuid4().hex[:12], "T" + uuid4().hex[:12]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO activity.ac_load_meta (source_file, file_sha256, row_count) VALUES ('test', %s, 2) "
                    "RETURNING load_id", ("0" * 64,))
        load_id = cur.fetchone()[0]
        for content_id, name in ((cid, "시험궁"), (cid2, "속성궁")):
            cur.execute("INSERT INTO activity.ac_place (content_id, content_type_id, name_ko, name_key, usetime_text, "
                        "restdate_text, load_id) VALUES (%s, '12', %s, %s, '09:00~18:00', '매주 화요일', %s)",
                        (content_id, name, name, load_id))
        cur.execute("INSERT INTO places (tenant_id, name, kind, source_name, source_content_id) "
                    "VALUES (%s, '시험궁', 'activity', 'tour_api', %s) RETURNING place_id", (tenant, cid))
        linked = cur.fetchone()[0]
        cur.execute("INSERT INTO places (tenant_id, name, kind, attributes) VALUES (%s, '속성궁', 'activity', "
                    "jsonb_build_object('source_content_id', %s::text)) RETURNING place_id", (tenant, cid2))
        by_attr = cur.fetchone()[0]
        cur.execute("INSERT INTO places (tenant_id, name, kind) VALUES (%s, '모르는 곳', 'activity') RETURNING place_id",
                    (tenant,))
        unlinked = cur.fetchone()[0]
    try:
        yield tenant, str(linked), str(by_attr), str(unlinked)
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM places WHERE tenant_id = %s", (tenant,))
            cur.execute("DELETE FROM activity.ac_place WHERE content_id IN (%s, %s)", (cid, cid2))
            cur.execute("DELETE FROM activity.ac_load_meta WHERE load_id = %s", (load_id,))


def test_linked_place_is_judged_from_ledger(seeded):
    tenant, linked, _, _ = seeded
    with get_connection() as conn:
        tuesday = ledger.state(conn, tenant, linked, datetime(2026, 10, 13, 10, tzinfo=KST))
        wednesday = ledger.state(conn, tenant, linked, datetime(2026, 10, 14, 10, tzinfo=KST))
    assert tuesday["closed"] is True and tuesday["name"] == "시험궁"
    assert (wednesday["closed"], wednesday["within_hours"]) == (False, True)


def test_content_id_in_attributes_also_links(seeded):
    tenant, _, by_attr, _ = seeded
    with get_connection() as conn:
        out = ledger.state(conn, tenant, by_attr, datetime(2026, 10, 14, 10, tzinfo=KST))
    assert out is not None and out["name"] == "속성궁"


def test_unlinked_place_or_other_tenant_is_unknown(seeded):
    tenant, linked, _, unlinked = seeded
    at = datetime(2026, 10, 14, 10, tzinfo=KST)
    with get_connection() as conn:
        assert ledger.state(conn, tenant, unlinked, at) is None
        assert ledger.state(conn, "other_" + tenant, linked, at) is None


@pytest.mark.parametrize("by_content", [False, True])
def test_a_failed_live_status_read_does_not_break_the_callers_transaction(seeded, monkeypatch, by_content):
    """★`[2026-10-16]` 실시간 운영 상태 읽기가 DB 오류로 실패해도 「모름」으로 싣고, **같은 연결의 다음 쿼리는 그대로 돈다**.

    전에는 예외만 잡아 트랜잭션이 막힌 채(aborted) 돌아와 다음 쿼리가 모두 `InFailedSqlTransaction` 으로 깨졌다
    (로컬 DB 에 304 `ac_live_status` 가 빠졌을 때 확인 화면). 표가 없는 상황을 실패하는 SQL 로 흉내 낸다."""
    from app.domains.travel_ops.instances.activity import live_store
    from app.domains.travel_ops.instances.activity.judge import modes

    def broken(conn, *args):
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM activity.no_such_table_for_test")

    monkeypatch.setattr(live_store, "lookup", broken)
    monkeypatch.setattr(live_store, "read", broken)
    real = modes.kind_mode
    monkeypatch.setattr(modes, "kind_mode", lambda kind, m=None: "shadow" if kind == "live_status" else real(kind, m))
    tenant, linked, _, _ = seeded
    at = datetime(2026, 10, 14, 10, tzinfo=KST)
    with get_connection() as conn, conn.transaction():                       # 확인 화면처럼 바깥 트랜잭션 안에서 부른다
        if by_content:
            with conn.cursor() as cur:
                cur.execute("SELECT source_content_id FROM places WHERE place_id = %s", (linked,))
                out = ledger.state_by_content(conn, cur.fetchone()[0], at)
        else:
            out = ledger.state(conn, tenant, linked, at)
        with conn.cursor() as cur:
            cur.execute("SELECT 1")                                           # ★전에는 여기서 InFailedSqlTransaction
            assert cur.fetchone() == (1,)
    assert out["name"] == "시험궁" and out["closed"] is False
    assert out["live_status"]["value"] == "unknown" and out["live_status"]["why"] == "lookup_failed:UndefinedTable"
