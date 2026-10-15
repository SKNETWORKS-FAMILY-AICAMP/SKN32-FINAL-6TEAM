# -*- coding: utf-8 -*-
"""실시간 운영 상태(웹 공지)는 **저장된 값만** 읽는다 — `[2026-10-13 사용자 결정 A안]`.

전에는 규칙이 닫혔다고 못 정하면 고객 요청마다 웹 검색을 불렀다(요청 수에 비례 · p95 40.7초 · 429). 이제 웹 확인은 장소 · 날짜당
한 번 배치(`scripts/activity/check_live_status.py`)가 하고 `activity.ac_live_status` 에 저장하며, 고객 요청은 `live_lookup` 으로
읽기만 한다. 규칙이 막으면 읽지도 않는다. 모드: `rule` 꺼짐 · `shadow` 기록만 · `llm` 「닫혔다」면 대체 장소를 붙여 변경 제안.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.instances.activity import ActivityTeam
from app.domains.travel_ops.instances.activity import failure_codes as fc
from app.domains.travel_ops.instances.activity import live_store

from ..helpers import FakeTools
from ._judge_fakes import FakeJudgeLLM, out
from .test_activity_judge_shadow import NOTICE, SCENARIOS, _request, _values, _with_kind_modes

CHECKED = datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc)
CLOSED_ROW = {"value": "closed", "checked_at": CHECKED,
              "citations": [{"url": NOTICE, "quote": "11월 10일 시설 공사로 임시 휴관", "published_at": "2026-11-01"}]}
OPEN_ROW = {"value": "open", "checked_at": CHECKED, "citations": [{"url": NOTICE, "quote": "정상 개방", "published_at": None}]}
UNKNOWN_ROW = {"value": "unknown", "checked_at": CHECKED, "citations": []}
CLASS = {"content_id": "126508", "lcls1": "HS", "lcls2": "HS01", "address": "서울특별시 종로구 사직로 161",
         "weather_sensitive": True}


def _modes(live_status):
    return {"closure": "rule", "operating_hours": "rule", "weather_sensitive": "rule", "disaster_effect": "rule",
            "live_status": live_status}


def _run(monkeypatch, row, *, mode="llm", scenario="open_with_text", wired=True):
    _with_kind_modes(monkeypatch, **_modes(mode))
    calls: list[tuple] = []
    llm = FakeJudgeLLM(out("closed", citations=CLOSED_ROW["citations"]), sources=[NOTICE])
    team = ActivityTeam(FakeTools(_values(**SCENARIOS[scenario], place_class=CLASS)))
    team.judge_llm = llm
    if wired:
        def stub(tenant_id, place_id, day):
            calls.append((tenant_id, place_id, day))
            if isinstance(row, Exception):
                raise row
            return row
        team.live_lookup = stub
    result = asyncio.run(team.execute(_request()))
    return result, calls, llm


def test_a_stored_closure_proposes_a_change_and_never_calls_the_web(monkeypatch):
    result, calls, llm = _run(monkeypatch, CLOSED_ROW)

    assert llm.calls == [], "고객 요청은 웹 검색을 부르지 않는다"
    assert len(calls) == 1 and isinstance(calls[0][2], date)
    decision = result.decisions[0]
    assert decision["feasible"] is False and decision["reason"] == "live_closed"
    assert decision["failure_code"] == fc.LIVE_CLOSED
    assert decision["live_status"]["citations"][0]["url"] == NOTICE and decision["live_status"]["source"] == "stored"
    assert "임시 휴관" in result.answer
    assert any(e.source_id == "judge.live_status" for e in result.evidence)
    assert result.action_proposals, "닫혔으면 변경 제안(승인 대기)을 만든다"


def test_a_closure_the_rules_already_found_does_not_read_the_store(monkeypatch):
    result, calls, llm = _run(monkeypatch, CLOSED_ROW, scenario="closed_by_text")

    assert calls == [] and llm.calls == []
    assert result.decisions[0]["feasible"] is False and result.decisions[0]["reason"] != "live_closed"


def test_an_open_value_does_not_override_the_rules(monkeypatch):
    result, _, _ = _run(monkeypatch, OPEN_ROW)

    decision = result.decisions[0]
    assert decision["feasible"] is True and decision["live_status"]["value"] == "open"
    assert not any("임시휴무" in w for w in result.warnings)


@pytest.mark.parametrize(("row", "value"), [(None, "unchecked"), (UNKNOWN_ROW, "unknown"),
                                            (RuntimeError("db down"), "unknown")])
def test_unchecked_and_unknown_say_so_instead_of_passing_silently(monkeypatch, row, value):
    result, _, _ = _run(monkeypatch, row)

    decision = result.decisions[0]
    assert decision["feasible"] is True and decision["live_status"]["value"] == value
    assert any("임시휴무 · 폐업은 확인하지 못했다" in w for w in result.warnings)


def test_shadow_records_the_stored_value_but_keeps_the_customer_answer(monkeypatch):
    result, _, llm = _run(monkeypatch, CLOSED_ROW, mode="shadow")

    assert llm.calls == []
    decision = result.decisions[0]
    assert decision["feasible"] is True and decision["live_status"]["value"] == "closed"
    assert not result.action_proposals


def test_rule_mode_or_no_lookup_means_the_check_is_off(monkeypatch):
    off, calls, _ = _run(monkeypatch, CLOSED_ROW, mode="rule")
    assert calls == [] and "live_status" not in off.decisions[0]

    unwired, _, _ = _run(monkeypatch, CLOSED_ROW, wired=False)
    assert "live_status" not in unwired.decisions[0]
    assert not any("임시휴무" in w for w in unwired.warnings), "꺼져 있으면 경고도 없다"


class _NoWriteCursor:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *args, **kwargs):
        raise AssertionError("저장하면 안 된다")


class _NoWriteConn:
    def cursor(self):
        return _NoWriteCursor()


def test_live_store_refuses_a_closure_without_evidence_and_unknown_values():
    with pytest.raises(ValueError):
        live_store.record(_NoWriteConn(), "126508", date(2026, 11, 10), "closed", citations=[])
    with pytest.raises(ValueError):
        live_store.record(_NoWriteConn(), "126508", date(2026, 11, 10), "maybe")


def test_fresh_rows_are_not_asked_again_inside_the_recheck_window():
    now = datetime(2026, 11, 9, 18, 0, tzinfo=timezone.utc)
    assert live_store.fresh({"checked_at": CHECKED}, now) is True                 # 3시간 전
    assert live_store.fresh({"checked_at": CHECKED - timedelta(hours=4)}, now) is False
    assert live_store.fresh(None, now) is False


# ── 배치(`scripts/activity/check_live_status.py`) — 장소 · 날짜당 한 번 ─────────────────

def _batch():
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[4]
    spec = importlib.util.spec_from_file_location("activity_check_live_status",
                                                  root / "scripts" / "activity" / "check_live_status.py")
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = module        # ★`@dataclass` 가 자기 모듈을 `sys.modules` 에서 찾는다
    spec.loader.exec_module(module)
    return module


def _targets(batch, count=3):
    return [batch.Target(str(100 + i), f"장소{i}", None, date(2026, 11, 10), datetime(2026, 11, 10, 9, 0, tzinfo=timezone.utc))
            for i in range(count)]


class _V:
    def __init__(self, value, known=True):
        self.value, self.known = value, known


def test_the_batch_asks_once_per_place_and_date_and_skips_fresh_rows():
    batch = _batch()
    now = datetime(2026, 11, 9, 18, 0, tzinfo=timezone.utc)
    asked, saved = [], []
    rows = {"100": {"checked_at": CHECKED}}                                         # 3시간 전에 확인함
    result = batch.check_targets(
        _targets(batch), read_row=lambda t: rows.get(t.content_id), judge=lambda t: (asked.append(t.content_id), _V("closed"))[1],
        budget=lambda kind: True, record=lambda t, v: saved.append((t.content_id, v.value)), now=now)

    assert asked == ["101", "102"] and saved == [("101", "closed"), ("102", "closed")]
    assert result["fresh"] == 1 and result["checked"] == 2 and result["closed"] == 2


def test_the_batch_stops_at_the_budget_and_reports_what_is_left():
    batch = _batch()
    allowed = iter([True, False])
    asked = []
    result = batch.check_targets(
        _targets(batch), read_row=lambda t: None, judge=lambda t: (asked.append(t.content_id), _V("open"))[1],
        budget=lambda kind: next(allowed), record=lambda t, v: None, now=CHECKED)

    assert asked == ["100"] and result["budget_stop"] == 1 and result["left"] == 2 and result["checked"] == 1


def test_one_failing_place_does_not_stop_the_batch_and_is_counted():
    batch = _batch()

    def judge(target):
        if target.content_id == "100":
            raise RuntimeError("429")
        return _V("unknown", known=False)

    result = batch.check_targets(_targets(batch, 2), read_row=lambda t: None, judge=judge,
                                 budget=lambda kind: True, record=lambda t, v: None, now=CHECKED)

    assert result["failed"] == 1 and result["checked"] == 1 and result["unknown"] == 1


def test_the_batch_respects_the_limit():
    batch = _batch()
    result = batch.check_targets(_targets(batch, 3), read_row=lambda t: None, judge=lambda t: _V("open"),
                                 budget=lambda kind: True, record=lambda t, v: None, now=CHECKED, limit=1)

    assert result["checked"] == 1 and result["left"] == 2
