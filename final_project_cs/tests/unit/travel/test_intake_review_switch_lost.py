# -*- coding: utf-8 -*-
"""`[2026-10-28 라우팅 전수검사 A17]` 확인 화면 전환(UPDATE … status='review')이 0행이면 — 그 사이 실패로 확정됐다(`reap_stalled`) —
뒤의 일(먼저 채우기 · 해석 답 반영 · 대안 미리 준비(이유 문장 모델) · 요식 판정)을 부르지 않고 물러난다.

☆전에는 0행이어도 계속 불러 실패한 접수에 모델 · 바깥 조회 계산을 낭비했고, 반환값은 「review」였다.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.intake import pipeline

KST = ZoneInfo("Asia/Seoul")


def _run(monkeypatch, *, review_rows: int, prefill: str = "off"):
    calls: list[str] = []

    class Cur:
        rowcount = 1

        def __init__(self):
            self.rows = [(datetime(2030, 1, 1, 9, tzinfo=KST),), ("owner",)]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, params=()):
            self.rowcount = review_rows if "SET status='review'" in sql else 1

        def fetchone(self):
            return self.rows.pop(0) if self.rows else ("owner",)

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        @contextmanager
        def transaction(self):
            yield

        def cursor(self):
            return Cur()

    @contextmanager
    def connect():
        yield Conn()

    class Beat:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    reader = {"mode": "on", "prefill": prefill, "num_predict": 100, "chunk_chars": 1800,
              "external_fallback_enabled": False, "missed_line_passes": 0}
    monkeypatch.setattr(pipeline, "_Heartbeat", Beat)
    monkeypatch.setattr(pipeline, "_sources", lambda conn, tenant_id, intake_id: [
        {"source_id": "s", "position": 0, "transcript": "10:00 경복궁", "differs_json": None, "filename": None}])
    monkeypatch.setattr(pipeline, "_stage", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "with_catalog", lambda tour, connect, tenant_id: tour)
    monkeypatch.setattr(pipeline, "_our_places", lambda conn, tenant_id: [])
    monkeypatch.setattr(pipeline, "load_aliases", lambda conn, tenant_id, owner: {})
    monkeypatch.setattr(pipeline, "areas_for", lambda conn, tenant_id: {})
    monkeypatch.setattr(pipeline, "_hold_reading", lambda cur, tenant_id, intake_id: None)
    monkeypatch.setattr(pipeline, "agent_reader_config", lambda tenant_id: reader)
    monkeypatch.setattr(pipeline, "read_source", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "_claims", lambda *a, **k: [])
    monkeypatch.setattr(pipeline.review_module, "ensure", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "_wholly_past", lambda *a, **k: False)
    monkeypatch.setattr(pipeline, "_has_questions", lambda *a, **k: False)
    for name in ("_prefill", "_apply_interpretations", "_prepare_alternatives", "_dining_judge"):
        monkeypatch.setattr(pipeline, name, lambda *a, _n=name, **k: calls.append(_n))
    out = pipeline.process(connect, tenant_id="unit", intake_id=uuid4(), blobs={}, see=None)
    return out, calls


@pytest.mark.parametrize("prefill", ["off", "on"])
def test_no_follow_up_work_when_the_intake_failed_before_review(monkeypatch, prefill):
    out, calls = _run(monkeypatch, review_rows=0, prefill=prefill)
    assert out == "fatal"
    assert calls == []


def test_the_normal_path_still_prepares_and_judges(monkeypatch):
    out, calls = _run(monkeypatch, review_rows=1)
    assert out == "review"
    assert calls == ["_prepare_alternatives", "_dining_judge", "_prepare_alternatives"]
