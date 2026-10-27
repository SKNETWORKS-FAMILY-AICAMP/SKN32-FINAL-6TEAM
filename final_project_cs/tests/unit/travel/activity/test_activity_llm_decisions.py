# -*- coding: utf-8 -*-
"""LLM 운영 판정 기록 — 코드 결과 / LLM 원래 답 / 고객에게 나간 결과를 한 줄로 남기고, 보고서가 셋을 나란히 그린다. `[2026-10-24]`

★가짜 모델 · 가짜 기록 함수로(API · DB 없음). 대체 후보 순서의 기존 시험(`test_activity_alternative_order`)과 같은 사례를 쓴다.
"""
from __future__ import annotations

import asyncio
import importlib.util
from datetime import date, datetime, timezone
from pathlib import Path

from app.domains.travel_ops.instances.activity import ActivityTeam

from ..helpers import FakeTools, pack, task
from .test_activity_alternative_order import SURVEY, Inline, OrderLLM, _modes
from .test_activity_closed_alternatives import ALLOWED, CLEAR, PLACE, POOL, TUESDAY, WEEK, _hours
from ._disaster import disaster_from

REASON = "아이와 함께라 체험 프로그램이 있는 덕수궁을 먼저 보여 드려요"


def _run(monkeypatch, llm, *, mode="llm", sink=None):
    _modes(monkeypatch, mode)
    values = {"read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": TUESDAY,
                               "party_size": 2, "capacity": 4},
              "read.policy": [], "read.place": PLACE, "read.disruptions": CLEAR, "read.disaster": disaster_from(CLEAR),
              "read.place_hours": _hours({**WEEK, "tue": "closed"}), "read.place_candidates": POOL}
    team = ActivityTeam(FakeTools(values))
    team.judge_llm, team.judge_runner = llm, Inline()
    rows = []
    team.judge_decision_sink = sink or rows.append
    context = pack("activity", scope=["activity"], state={"survey": SURVEY})
    result = asyncio.run(team.execute(task("activity", "activity.check_feasible", context, ALLOWED,
                                           input_text="아이랑 갈 만한 데로 바꿔 주세요")))
    return result, rows


def test_a_served_llm_order_is_recorded_beside_the_code_order(monkeypatch):
    _, rows = _run(monkeypatch, OrderLLM({"order": ["b", "a"], "used_preference": True, "reason": REASON}))

    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "alternative_order" and row["mode"] == "llm" and row["outcome"] == "llm_served"
    assert row["code_result"] == {"order": ["a", "b"]}                 # 코드가 낸 순서 — LLM 이 없었으면 고객이 받았을 것
    assert row["served_result"] == {"order": ["b", "a"]} and row["changed"] is True
    assert row["llm_result"]["order"] == ["b", "a"] and row["llm_result"]["reason"] == REASON
    assert row["reason"] == REASON and row["model"] == "fake" and row["latency_ms"] >= 0
    assert "아이랑" not in str(row)                                     # 고객 문장은 싣지 않는다


def test_the_raw_answer_keeps_a_made_up_place_the_customer_never_saw(monkeypatch):
    _, rows = _run(monkeypatch, OrderLLM({"order": ["zzz", "b"], "used_preference": True, "reason": "체험형이에요"}))

    assert rows[0]["llm_result"]["order"] == ["zzz", "b"]
    assert rows[0]["served_result"] == {"order": ["b", "a"]}


def test_failures_record_a_fallback_to_the_code_order(monkeypatch):
    _, rows = _run(monkeypatch, OrderLLM(exc=RuntimeError("no active prompt")))
    assert rows[0]["outcome"] == "code_fallback" and rows[0]["failure_code"] == "llm_error"
    assert rows[0]["error"] == "RuntimeError" and rows[0]["changed"] is False
    assert rows[0]["served_result"] == rows[0]["code_result"]

    _, rows = _run(monkeypatch, OrderLLM({"order": ["zzz"], "used_preference": True, "reason": "x"}))
    assert rows[0]["outcome"] == "code_fallback" and rows[0]["failure_code"] == "llm_schema_invalid"
    assert rows[0]["llm_result"]["order"] == ["zzz"]


def test_shadow_records_the_llm_order_but_serves_the_code_order(monkeypatch):
    _, rows = _run(monkeypatch, OrderLLM({"order": ["b", "a"], "used_preference": True, "reason": REASON}), mode="shadow")

    assert rows[0]["mode"] == "shadow" and rows[0]["outcome"] == "shadow"
    assert rows[0]["served_result"] == rows[0]["code_result"] == {"order": ["a", "b"]} and rows[0]["changed"] is False
    assert rows[0]["llm_result"]["order"] == ["b", "a"]


def test_rule_mode_records_nothing(monkeypatch):
    _, rows = _run(monkeypatch, OrderLLM({"order": ["b", "a"], "used_preference": True, "reason": REASON}), mode="rule")
    assert rows == []


def test_a_broken_sink_does_not_change_the_customer_answer(monkeypatch):
    def broken(_row):
        raise RuntimeError("db down")

    result, _ = _run(monkeypatch, OrderLLM({"order": ["b", "a"], "used_preference": True, "reason": REASON}), sink=broken)
    titles = [a["title"] for a in result.decisions[0]["alternatives"]["alternatives"] if a["revalidated"]]
    assert titles == ["덕수궁", "창덕궁"]


# ── 보고서 ─────────────────────────────────────────────────────────
def _report():
    path = Path(__file__).resolve().parents[4] / "scripts" / "activity" / "llm_decision_report.py"
    spec = importlib.util.spec_from_file_location("llm_decision_report", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AT = datetime(2026, 10, 24, 3, 0, tzinfo=timezone.utc)
TITLES = {"a": "창덕궁", "b": "덕수궁"}


def _render(decisions, shadows=()):
    return _report().render(list(decisions), list(shadows), TITLES, since=date(2026, 10, 24), until=date(2026, 10, 25),
                            generated_at=AT, source="127.0.0.1/acop_cs")


def _order_row(**overrides):
    row = {"decided_at": AT, "case_id": "9f1c2d3e-0000-0000-0000-000000000000", "kind": "alternative_order", "mode": "llm",
           "outcome": "llm_served", "code_result": {"order": ["a", "b"]},
           "llm_result": {"order": ["zzz", "b"], "used_preference": True, "reason": "체험형이에요"},
           "served_result": {"order": ["b", "a"]}, "changed": True, "reason": "체험형이에요", "reason_guard": None,
           "failure_code": None, "error": None, "latency_ms": 1900, "model": "gpt-5.4-nano"}
    return {**row, **overrides}


def test_the_report_puts_code_llm_and_served_side_by_side():
    text = _render([_order_row(), _order_row(outcome="code_fallback", served_result={"order": ["a", "b"]},
                                             changed=False, failure_code="llm_timeout", llm_result=None)])

    assert "## 대체 후보 순서 — 코드 결과 / LLM 재정의 결과" in text
    assert "| 코드 순서 | LLM 원래 답 | 고객에게 나간 순서 | 바뀜 |" in text
    assert "1. 창덕궁 → 2. 덕수궁" in text and "1. 덕수궁 → 2. 창덕궁" in text
    assert "#zzz (목록 밖)" in text and "예 ★" in text and "llm_timeout" in text
    assert "| 대체 후보 순서 | `llm` | 2 | 1/2 = 50.0% | 1/1 = 100.0% | 1/2 = 50.0% |" in text


def test_the_report_says_plainly_when_there_is_nothing():
    text = _render([])
    assert "운영 LLM 판정 기록이 없습니다" in text and "| 코드 순서 |" not in text


def test_the_report_lists_rule_first_and_shadow_judgments():
    rule_first = _order_row(kind="closure", code_result={"value": "unknown", "basis": None},
                            llm_result={"value": "closed"}, served_result={"value": "closed"})
    shadow = {"created_at": AT, "case_id": None, "kind": "disaster_effect", "event": "shadow", "rule_value": "blocks",
              "llm_value": "no_effect", "agree": False, "comparable": True, "llm_failure_code": None}
    text = _render([rule_first], [shadow])

    assert "| 휴무 | LLM 결과 사용 | unknown | closed | closed | 예 ★ |" in text
    assert "| 재난 영향 | blocks | no_effect | 불일치 ★ |" in text
    assert "섀도 판정 일치율(둘 다 「모름」이 아닌 줄): 0/1 = 0.0%" in text
