# -*- coding: utf-8 -*-
"""요식 판정 — **늦게 온 판정**은 지금 판에만 합친다 · 고친 뒤에는 새 판을 다시 판정한다. `[2026-10-16 설계 대조 P2]`

☆판정은 확인 화면을 연 **뒤에** 15~30초 돈다. 그 사이 고객이 고치면(새 판) 판정이 늘 1판에 합쳐져 고객이 보는 판에는 안 나왔고,
  등록한 뒤에도 1판 검사를 바꿨다(`wiki/records/reports/2026-10-16_dining-design-assessment-e19e1ea3.md` §2).
"""
from __future__ import annotations

import uuid

from app.domains.travel_ops.components.intake import pipeline
from app.domains.travel_ops.components.intake import review as review_module
from app.domains.travel_ops.components.team_hooks import dining_ledger
from app.domains.travel_ops.instances.dining import judge
from app.domains.travel_ops.instances.dining.agent import AgentResult


class Cur:
    def __init__(self, sink):
        self.sink = sink

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        self.sink.append((sql, params))


class Conn:
    def __init__(self):
        self.sql = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def transaction(self):
        return self

    def cursor(self):
        return Cur(self.sql)


REVIEW = {"ready": True, "items": [{"id": "0-1", "kind": "dining", "date": "2026-10-27", "starts_at": "12:30", "ends_at": "13:30",
                                    "status": "ok", "place": {"name": "순희네빈대떡", "latitude": 37.57, "longitude": 126.99},
                                    "rows": [{"row": "place", "result": "ok"}, {"row": "hours", "result": "unknown"},
                                             {"row": "closed", "result": "unknown"}]}]}
CLOSED = AgentResult(items=[{"item_id": "0-1", "place": None, "checks": [
    {"check": "closed_day", "verdict": "bad", "evidence": [{"call_id": "c1", "path": "verdict", "value": "bad"}]}]}],
    skipped=[], stats={}, tool_calls=[{"id": "c1", "tool": "check_closed_day", "args": {}}])


def _run(monkeypatch, state, revision=1):
    conn, stored = Conn(), []
    monkeypatch.setattr(judge, "judge_day", lambda plan, **kw: CLOSED)
    monkeypatch.setattr(review_module, "load", lambda c, t, i, r: {**REVIEW, "items": [dict(REVIEW["items"][0])]})
    monkeypatch.setattr(review_module, "store", lambda c, t, i, r, payload: stored.append((r, payload)))
    monkeypatch.setattr(review_module, "intake_state", lambda c, t, i: state)
    got = judge.run(lambda: conn, tenant_id="t", intake_id=uuid.uuid4(), revision=revision, review=REVIEW, notes="",
                    chat=None, model="fake", tools_factory=lambda connect: None)
    codes = [params[5] for sql, params in conn.sql if "dn_agent_judge" in sql]
    return got, stored, codes


def test_a_judgment_for_the_current_revision_is_merged(monkeypatch):
    got, stored, codes = _run(monkeypatch, ("review", 1))
    assert got["changed"] == 1 and got["stale"] == 0
    assert stored and stored[0][0] == 1 and stored[0][1]["items"][0]["rows"][2]["result"] == "bad"
    assert "_stale" not in codes


def test_a_late_judgment_after_the_customer_edited_is_recorded_not_merged(monkeypatch):
    got, stored, codes = _run(monkeypatch, ("review", 2))
    assert stored == [] and got["changed"] == 0 and got["stale"] == 1
    assert "_stale" in codes                                                 # 버린 것도 기록에 남는다(조용히 사라지지 않는다)


def test_a_late_judgment_after_registering_is_not_merged(monkeypatch):
    got, stored, _ = _run(monkeypatch, ("confirmed", 1))
    assert stored == [] and got["stale"] == 1


def test_rejudge_runs_the_new_revision_only_while_it_is_current(monkeypatch):
    calls = []
    monkeypatch.setattr(dining_ledger, "agent_judge_runner", lambda: lambda *a, **k: calls.append(k))
    monkeypatch.setattr(review_module, "load", lambda c, t, i, r: {"items": [{"id": "0-1"}]})
    monkeypatch.setattr(pipeline, "_sources", lambda c, t, i: [{"transcript": "12:30 순희네빈대떡 점심"}])
    monkeypatch.setattr(review_module, "intake_state", lambda c, t, i: ("review", 3))
    pipeline.rejudge(lambda: Conn(), "t", uuid.uuid4(), 3)
    assert len(calls) == 1 and calls[0]["revision"] == 3 and calls[0]["notes"] == "12:30 순희네빈대떡 점심"
    pipeline.rejudge(lambda: Conn(), "t", uuid.uuid4(), 2)                  # 그 사이 또 고쳤다(3판) — 돌리지 않는다
    monkeypatch.setattr(review_module, "intake_state", lambda c, t, i: ("confirmed", 3))
    pipeline.rejudge(lambda: Conn(), "t", uuid.uuid4(), 3)                  # 등록했다 — 돌리지 않는다
    assert len(calls) == 1


def test_rejudge_without_a_runner_opens_nothing(monkeypatch):
    monkeypatch.setattr(dining_ledger, "agent_judge_runner", lambda: None)

    def connect():
        raise AssertionError("판정이 꺼져 있으면 DB 도 열지 않는다")
    pipeline.rejudge(connect, "t", uuid.uuid4(), 2)
