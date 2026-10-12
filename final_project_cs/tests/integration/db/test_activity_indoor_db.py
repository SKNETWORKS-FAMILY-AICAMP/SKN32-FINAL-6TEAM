# -*- coding: utf-8 -*-
"""실내외 저장(`activity.ac_indoor`, 301) — 우선순위 · 갱신 · 모델 판정 저장 조건. 실 PostgreSQL, 못 붙으면 건너뛴다. `[2026-10-12]`"""
from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest

from app.domains.travel_ops.instances.activity import indoor_store, ledger
from app.domains.travel_ops.instances.activity.notices import INDOOR_AUTO
from app.infrastructure.db.session import database_dsn, get_connection


def _reachable() -> str | None:
    try:
        with psycopg.connect(database_dsn(), connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass('activity.ac_indoor')")
            if cur.fetchone()[0] is None:
                return "activity.ac_indoor 가 없다 — migrate 먼저"
    except Exception as exc:  # noqa: BLE001
        return f"DB 에 연결할 수 없다: {type(exc).__name__}"
    return None


_SKIP = _reachable()
pytestmark = pytest.mark.skipif(_SKIP is not None, reason=_SKIP or "")


@pytest.fixture()
def place():
    cid, tenant = "T" + uuid4().hex[:12], "test_" + uuid4().hex
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO activity.ac_load_meta (source_file, file_sha256, row_count) VALUES ('t', %s, 1) "
                    "RETURNING load_id", ("0" * 64,))
        load_id = cur.fetchone()[0]
        cur.execute("INSERT INTO activity.ac_place (content_id, content_type_id, name_ko, name_key, lcls1, lcls2, load_id) "
                    "VALUES (%s, '12', '시험궁', '시험궁', 'HS', 'HS01', %s)", (cid, load_id))
        cur.execute("INSERT INTO places (tenant_id, name, kind, source_name, source_content_id) "
                    "VALUES (%s, '시험궁', 'activity', 'tour_api', %s) RETURNING place_id", (tenant, cid))
        place_id = str(cur.fetchone()[0])
    try:
        yield cid, tenant, place_id
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM places WHERE tenant_id = %s", (tenant,))
            cur.execute("DELETE FROM activity.ac_place WHERE content_id = %s", (cid,))
            cur.execute("DELETE FROM activity.ac_load_meta WHERE load_id = %s", (load_id,))


def _judge(outdoor=True, quote="야외 정원", model="fake-nano"):
    return lambda _name, _lcls2: {"outdoor": outdoor, "quote": quote, "model": model, "prompt_version": "activity_judge.weather_sensitive"}


def test_class_unknown_then_model_once_and_stored(place):
    cid, _, _ = place
    calls = []

    def judge(name, lcls2):
        calls.append(name)
        return _judge()(name, lcls2)

    with get_connection() as conn, conn.transaction():
        first = indoor_store.decide(conn, cid, name="시험궁", lcls1="HS", lcls2="HS01", judge=judge)   # HS01 은 분류로 못 정한다
        again = indoor_store.decide(conn, cid, name="시험궁", lcls1="HS", lcls2="HS01", judge=judge)
    assert (first["outdoor"], first["decided_by"], first["quote"]) == (True, "llm", "야외 정원")
    assert again["decided_by"] == "llm" and calls == ["시험궁"]          # 두 번째는 저장값 — 모델을 다시 부르지 않는다


def test_a_model_answer_without_a_quote_is_not_stored(place):
    cid, _, _ = place
    with get_connection() as conn, conn.transaction():
        assert indoor_store.decide(conn, cid, name="시험궁", lcls1="HS", lcls2="HS01", judge=_judge(quote="")) is None
        assert indoor_store.read(conn, cid) is None


def test_higher_priority_wins_and_lower_rows_are_kept(place):
    cid, _, _ = place
    with get_connection() as conn, conn.transaction():
        indoor_store.record(conn, cid, True, "llm", model="fake", quote="야외")
        indoor_store.record(conn, cid, False, "customer")
        assert indoor_store.read(conn, cid)["decided_by"] == "customer"
        indoor_store.record(conn, cid, True, "llm", model="fake2", quote="야외 다시")     # 낮은 값이 새로 와도
        assert indoor_store.read(conn, cid)["outdoor"] is False                         # 고객 값이 그대로 이긴다
        indoor_store.record(conn, cid, True, "operator")
        assert indoor_store.read(conn, cid)["decided_by"] == "operator"


def test_a_class_change_forgets_only_derived_rows(place):
    cid, _, _ = place
    with get_connection() as conn, conn.transaction():
        indoor_store.record(conn, cid, True, "class")
        indoor_store.record(conn, cid, True, "llm", model="fake", quote="야외")
        indoor_store.record(conn, cid, False, "customer")
        assert indoor_store.forget_derived(conn, cid) == 2
        assert indoor_store.read(conn, cid)["decided_by"] == "customer"


def test_unknown_is_never_stored(place):
    cid, _, _ = place
    with get_connection() as conn, conn.transaction(), pytest.raises(ValueError):
        indoor_store.record(conn, cid, None, "llm", model="fake", quote="?")


def test_the_ledger_reads_the_winner_and_adds_the_notice_only_for_model_values(place):
    cid, tenant, place_id = place
    with get_connection() as conn, conn.transaction():
        assert ledger.indoor(conn, tenant, place_id) is None                 # 아직 모름
        indoor_store.record(conn, cid, True, "llm", model="fake", quote="야외")
        by_model = ledger.indoor(conn, tenant, place_id)
        indoor_store.record(conn, cid, False, "customer")
        by_customer = ledger.indoor(conn, tenant, place_id)
    assert (by_model["outdoor"], by_model["notice"]) == (True, INDOOR_AUTO)
    assert (by_customer["outdoor"], by_customer["notice"]) == (False, None)
