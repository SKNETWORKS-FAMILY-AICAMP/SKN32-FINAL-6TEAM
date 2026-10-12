# -*- coding: utf-8 -*-
"""섀도 기록 표(`031_activity_judge_shadow.sql`, A안)를 **실 PostgreSQL** 로 돌린다.

★전부 **롤백되는 트랜잭션** 안에서 한다 — 개발 DB 에 시험 행을 남기지 않는다.
★DB 에 못 붙거나 표가 없으면 **건너뛴다**(실패가 아니다).
"""
from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest

from app.infrastructure.db.repository import create_activity_judge_shadow
from app.infrastructure.db.session import database_dsn, get_connection


def _reachable() -> str | None:
    try:
        with psycopg.connect(database_dsn(), connect_timeout=3) as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass('activity_judge_shadow')")
            table = cur.fetchone()[0]
    except Exception as exc:  # noqa: BLE001 — 어떤 이유든 못 붙으면 건너뛴다
        return f"DB 에 연결할 수 없다: {type(exc).__name__}"
    if table is None:
        return "activity_judge_shadow(031) 가 없다 — `python -m app.infrastructure.db.migrate` 먼저"
    return None


_SKIP = _reachable()
pytestmark = pytest.mark.skipif(_SKIP is not None, reason=_SKIP or "")

RECORD = {"event": "activity_judge_shadow", "tenant_id": "t-shadow", "case_id": str(uuid4()),
          "capability": "activity.check_feasible", "run_id": None, "kind": "disaster_effect",
          "rule": "blocks", "rule_basis": "step_only", "llm": "no_effect", "agree": False, "comparable": True,
          "llm_failure_code": None, "llm_error": None, "llm_confidence": 0.95, "dropped": 0, "quotes": 1,
          "citations": 0, "latency_ms": 2061, "search_calls": 0, "input_tokens": 757, "output_tokens": 199,
          "reasoning_tokens": 40, "undated_citations": None, "model": "gpt-5.4-nano"}


def _roundtrip(record):
    with get_connection() as conn, conn.transaction(force_rollback=True), conn.cursor() as cur:
        shadow_id = create_activity_judge_shadow(conn, record)
        cur.execute("SELECT origin, event, kind, rule_value, llm_value, agree, comparable, latency_ms, model "
                    "FROM activity_judge_shadow WHERE shadow_id=%s", (shadow_id,))
        return cur.fetchone()


def test_shadow_record_roundtrip():
    assert _roundtrip(RECORD) == ("live", "shadow", "disaster_effect", "blocks", "no_effect", False, True,
                                  2061, "gpt-5.4-nano")


def test_unknown_keys_are_not_stored():
    """★표에 없는 키(장소명 등)가 섞여 와도 저장하지 않는다 — 칸을 고정해 쓴다."""
    row = _roundtrip({**RECORD, "place_name": "경복궁", "reason": "이유"})
    assert row[1] == "shadow"


def test_skipped_event_without_llm_fields():
    row = _roundtrip({"event": "activity_judge_shadow_skipped", "kind": "closure", "rule": "closed",
                      "rule_basis": "weekly_pattern", "case_id": None})
    assert row[:5] == ("live", "skipped", "closure", "closed", None)


def test_eval_origin():
    row = _roundtrip({**RECORD, "origin": "eval", "eval_run": "r1", "eval_case": "closure-01", "eval_repeat": 1})
    assert row[0] == "eval"
