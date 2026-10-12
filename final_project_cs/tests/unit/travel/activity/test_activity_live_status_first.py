# -*- coding: utf-8 -*-
"""DB 운영 정보로 규칙이 먼저 보고, 닫혔다고 못 정했을 때 웹 검색 LLM 으로 운영 · 폐업을 본다 — `kind_modes.live_status = llm`.
`[2026-10-12 사용자 결정]` (처음엔 웹을 맨 앞에 두었다가, 실측에서 정기휴무까지 웹이 먼저 정해 규칙 뒤로 옮겼다)

★가짜 모델로(API 없음). 규칙이 막으면 웹을 부르지 않는다. 웹이 「닫혔다」면 대체 장소를 붙여 바꾸자고 제안한다.
  「연다」 · 「모름」 · 실패 · 예산 초과는 규칙 판정 그대로다.
"""
from __future__ import annotations

import asyncio
from datetime import date

from app.domains.travel_ops.instances.activity import ActivityTeam
from app.domains.travel_ops.instances.activity import failure_codes as fc
from app.domains.travel_ops.instances.activity.judge.modes import LocalWebBudget

from ..helpers import FakeTools
from ._judge_fakes import FakeJudgeLLM, out
from .test_activity_judge_shadow import NOTICE, SCENARIOS, _request, _values, _with_kind_modes

CLOSED = out("closed", citations=[{"url": NOTICE, "quote": "11월 10일 시설 공사로 임시 휴관", "published_at": "2026-11-01"}])
LLM_MODES = {"closure": "rule", "operating_hours": "rule", "weather_sensitive": "rule",
             "disaster_effect": "rule", "live_status": "llm"}
CLASS = {"content_id": "126508", "lcls1": "HS", "lcls2": "HS01", "address": "서울특별시 종로구 사직로 161",
         "weather_sensitive": True}


def _run(monkeypatch, llm, *, values=None, budget=None):
    _with_kind_modes(monkeypatch, **LLM_MODES)
    tools = FakeTools(values or _values(**SCENARIOS["open_with_text"], place_class=CLASS))
    team = ActivityTeam(tools)
    team.judge_llm = llm
    team.judge_budget = budget if budget is not None else (lambda _kind: True)
    return asyncio.run(team.execute(_request())), tools


def test_a_closure_the_rules_already_found_never_calls_the_web(monkeypatch):
    llm = FakeJudgeLLM(CLOSED, sources=[NOTICE])
    result, _ = _run(monkeypatch, llm, values=_values(**SCENARIOS["closed_by_text"], place_class=CLASS))
    assert llm.calls == []
    assert result.decisions[0]["feasible"] is False and result.decisions[0]["reason"] != "live_closed"


def test_closed_on_the_web_after_the_rules_proposes_a_change(monkeypatch):
    llm = FakeJudgeLLM(CLOSED, sources=[NOTICE])
    result, tools = _run(monkeypatch, llm)

    called = [name for name, _ in tools.calls]
    assert [c["payload"]["kind"] for c in llm.calls] == ["live_status"]
    assert llm.calls[0]["payload"]["address"] == CLASS["address"]          # 같은 이름의 다른 곳과 가른다
    assert called.index("read.place_hours") < called.index("read.place_class")   # 규칙이 먼저, 웹은 뒤
    assert called.count("read.place_class") == 1
    decision = result.decisions[0]
    assert decision["feasible"] is False and decision["reason"] == "live_closed"
    assert decision["failure_code"] == fc.LIVE_CLOSED
    assert decision["live_status"]["citations"][0]["url"] == NOTICE
    assert "임시 휴관" in result.answer
    assert any(e.source_id == "judge.live_status" for e in result.evidence)
    assert result.action_proposals, "닫혔으면 변경 제안(승인 대기)을 만든다"


def test_open_or_unknown_continues_with_the_usual_checks_and_reads_the_class_once(monkeypatch):
    llm = FakeJudgeLLM(out("open", citations=[{"url": NOTICE, "quote": "정상 개방", "published_at": None}]),
                       sources=[NOTICE])
    values = _values(**SCENARIOS["open_with_text"], place_class=CLASS)
    values["read.place"] = {**values["read.place"], "weather_sensitive": None}     # 실내외도 분류로 정한다
    result, tools = _run(monkeypatch, llm, values=values)

    called = [name for name, _ in tools.calls]
    assert called.count("read.place_class") == 1             # 실내외 판정이 읽은 것을 웹 확인이 다시 쓴다
    assert "read.disruptions" in called and "read.place_hours" in called
    decision = result.decisions[0]
    assert decision["feasible"] is True
    assert decision["live_status"] == {"value": "unknown", "source": "llm"}      # 「연다」는 받지 않는다
    assert decision["indoor"]["source"] == "class"


def test_a_failed_call_or_an_exhausted_budget_is_unknown_not_closed(monkeypatch):
    broken, _ = _run(monkeypatch, FakeJudgeLLM(exc=RuntimeError("down")))
    assert broken.decisions[0]["feasible"] is True

    llm = FakeJudgeLLM(CLOSED, sources=[NOTICE])
    over, _ = _run(monkeypatch, llm, budget=lambda _kind: False)
    assert llm.calls == [] and over.decisions[0]["feasible"] is True


def test_without_a_judge_or_in_rule_mode_nothing_changes(monkeypatch):
    _with_kind_modes(monkeypatch, **LLM_MODES)
    tools = FakeTools(_values(**SCENARIOS["open_with_text"], place_class=CLASS))
    result = asyncio.run(ActivityTeam(tools).execute(_request()))      # 전역 `rule` — 조립이 판정 LLM 을 안 넣는다
    assert "live_status" not in result.decisions[0]
    assert "read.place_class" not in [name for name, _ in tools.calls]


def test_local_web_budget_counts_only_web_calls_per_day_and_month():
    days = iter([date(2026, 11, 10)] * 3 + [date(2026, 11, 11)] * 2 + [date(2026, 12, 1)])
    budget = LocalWebBudget({"activity_judge_web": {"day": 2, "month": 3}, "activity_judge": {"day": 0, "month": 0}},
                            today=lambda: next(days))

    assert budget("closure") is True                                    # 원문 해석은 세지 않는다
    assert [budget("live_status") for _ in range(3)] == [True, True, False]        # 하루 2
    assert [budget("live_status") for _ in range(2)] == [True, False]              # 다음 날 — 월 3 에 걸린다
    assert budget("live_status") is True                                            # 다음 달
