# -*- coding: utf-8 -*-
"""읽기는 접수 행을 잠그지 않는다 · 대안 계산은 한 일정에 하나만. `[2026-10-24 사용자 결정 — ST4F-731]` DB · 모델 · 네트워크를 쓰지 않는다.

☆왜: 검사를 읽는 모든 길(`pipeline._review_of`)이 접수 행을 `FOR UPDATE` 로 잠가, 「전체 자동 추천」 미리 보기(12~29초)가 잠금을 쥔 동안 멈춘 질문의
후보 · 접수 조회가 5~22초 기다렸다. 「바꾸기」 실시간 계산과 접수 뒤 미리 준비는 같은 일정을 따로 계산했다(2026-10-24 로컬 실측 — 작업 기록
`wiki/records/reports/2026-10-24_계획확인_진행표시_후보대기_ST4F-731-732.md`). DB 로 확인하는 쪽은 `tests/e2e/test_intake_read_lock.py`.

재현:

    python -m pytest tests/unit/travel/test_intake_read_lock.py -v
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest

from app.domains.travel_ops.components.intake import pipeline, prepared
from app.domains.travel_ops.components.intake import review as review_module


class Conn:
    @contextmanager
    def transaction(self):
        yield

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture()
def locks(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(review_module, "intake_state", lambda *a: calls.append("lock") or ("review", 1))
    monkeypatch.setattr(review_module, "ensure", lambda conn, **kw: {"revision": kw["revision"], "items": []})
    return calls


def test_reading_the_check_does_not_lock_the_intake(locks):
    found, error = pipeline._review_of(Conn(), "t", "i", 1, [], [])
    assert error is None and found == {"revision": 1, "items": []}
    assert locks == []


def test_working_the_check_out_again_and_storing_it_still_locks_the_intake(locks):
    pipeline._review_of(Conn(), "t", "i", 1, [], [], force=True)
    assert locks == ["lock"]


ITEM = {"id": "0-0", "source_id": "s", "index": 0, "title": "경복궁", "kind": "activity"}


def test_while_change_works_a_stop_out_the_prepare_after_the_intake_passes_it_by(monkeypatch):
    seen = {}

    def gather(conn, **kw):
        seen["busy"] = prepared.prepare_one(lambda: Conn(), tenant_id="t", intake_id="i", review={"revision": 1}, item=ITEM)
        raise RuntimeError("stop here")                    # 계산 도중 — 맡은 채로 끝나도 놓아야 한다

    monkeypatch.setattr(prepared.cand, "is_risk_item", lambda item: False)
    monkeypatch.setattr(prepared, "load", lambda *a: None)
    monkeypatch.setattr(prepared.cand, "gather", gather)
    with pytest.raises(RuntimeError, match="stop here"):
        prepared.stream(lambda: Conn(), tenant_id="t", intake_id="i", review={"revision": 1}, item=ITEM, emit=lambda *a: None)
    assert seen["busy"] == "busy"                          # 「바꾸기」가 맡은 일정 — 미리 준비는 건너뛴다
    assert prepared.wait_preparing("i", ITEM, timeout=0.1) is False      # 끝나면 놓았다


def test_the_prepare_before_the_meal_check_leaves_the_meals_for_after_it(monkeypatch):
    items = [ITEM, {**ITEM, "id": "0-1", "index": 1, "title": "광장시장", "kind": "dining"}]
    asked: list[str] = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, *a):
            pass

        def fetchall(self):
            return []

    class Db(Conn):
        def cursor(self):
            return Cursor()

    monkeypatch.setattr(prepared, "_current", lambda conn, t, i: {"revision": 1, "items": items})
    monkeypatch.setattr(prepared, "needs_alternatives", lambda item: True)
    monkeypatch.setattr(prepared, "prepare_scope", lambda: "problems")
    monkeypatch.setattr(prepared, "prepare_one", lambda connect, **kw: asked.append(kw["item"]["id"]) or "saved")
    prepared.prepare(lambda: Db(), tenant_id="t", intake_id="i", which="not_meals")
    assert asked == ["0-0"]
    prepared.prepare(lambda: Db(), tenant_id="t", intake_id="i", which="meals")     # 요식 판정 뒤 — 식사만(먼저 맡은 일정을 다시 보지 않는다)
    assert asked == ["0-0", "0-1"]
    prepared.prepare(lambda: Db(), tenant_id="t", intake_id="i")
    assert sorted(asked[2:]) == ["0-0", "0-1"]
