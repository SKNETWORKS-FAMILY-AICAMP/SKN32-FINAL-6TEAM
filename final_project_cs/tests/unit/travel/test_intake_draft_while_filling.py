# -*- coding: utf-8 -*-
"""`[2026-10-27 A 접수·읽기 전수검사 A14]` 먼저 채우기 · 해석 답 반영이 도는 동안(`status: review` · `stage: checking`) 고객에게는 아직
「읽는 중」이다(`pipeline.public_status`). 그런데 등록 준비(`pipeline.draft` — `/confirm` · `/plan` · 채팅 고치기의 입구)는 `status` 만 보고
그 판으로 등록을 허락했다 — 일꾼이 곧 새 판을 쓰는 사이 고객 요청이 1판으로 여행을 만들 수 있었다. 공개 상태와 같은 기준으로 막는다(409 `intake_not_ready`).
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.domains.travel_ops.components.intake import pipeline


class Cursor:
    """접수 행 하나(상태 · 판 · 여행 · 단계)를 돌려주는 대역 — 고른 칸만큼만 돌려준다(단계를 안 고르면 단계를 모른다)."""

    def __init__(self, row):
        self.row, self.sql = row, []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.sql.append(sql)

    def fetchone(self):
        status, revision, trip_id, stage = self.row
        return (status, revision, trip_id, stage) if "stage" in self.sql[-1].split("FROM")[0] else (status, revision, trip_id)

    def fetchall(self):
        return []


class Conn:
    def __init__(self, row):
        self.cur = Cursor(row)

    def cursor(self):
        return self.cur


def test_draft_refuses_while_the_worker_is_still_filling_in(monkeypatch):
    monkeypatch.setattr(pipeline, "_sources", lambda *a: [])
    conn = Conn(("review", 1, None, "checking"))
    with pytest.raises(pipeline.IntakeConflict) as caught:
        pipeline.draft(conn, tenant_id="t", customer_id=uuid4(), intake_id=uuid4(), revision=1)
    assert caught.value.code == "intake_not_ready"
    assert caught.value.detail.get("status") == "reading", "고객에게 보이는 상태와 같은 말로 막는다"


def test_draft_still_builds_once_the_intake_is_on_the_review_screen(monkeypatch):
    monkeypatch.setattr(pipeline, "_sources", lambda *a: [])
    conn = Conn(("review", 1, None, "review"))
    status, trip_id, built = pipeline.draft(conn, tenant_id="t", customer_id=uuid4(), intake_id=uuid4(), revision=1)
    assert (status, trip_id) == ("review", None) and built is not None
