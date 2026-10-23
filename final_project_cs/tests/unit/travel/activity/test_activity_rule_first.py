# -*- coding: utf-8 -*-
"""규칙이 모를 때만 LLM, 휴무 · 재난은 조심하는 쪽만 — D-CS-015 개정 2. 가짜 모델로(API 없음). `[2026-10-12]`"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.instances.activity import ActivityTeam
from app.domains.travel_ops.instances.activity import team as team_module
from app.domains.travel_ops.instances.activity.judge import JudgeContext, LLMJudge, requests
from app.domains.travel_ops.instances.activity.judge.modes import kind_mode, rule_first
from app.domains.travel_ops.instances.activity.judge.types import Verdict
from app.domains.travel_ops.instances.activity.notices import HOURS_AUTO_READ

from ..helpers import FakeTools, pack, task
from ._judge_fakes import FakeJudgeLLM, out

KST = timezone(timedelta(hours=9))
FRIDAY = datetime(2026, 11, 13, 14, 0, tzinfo=KST)
CTX = JudgeContext()
ODD = "평일 (학생 안전강화로 인해 주말에만 개방)"     # 규칙이 못 읽는 휴무 원문(실제 데이터)


def _unknown(kind):
    return Verdict(kind, "unknown", "rule", basis="unparsed")


def test_a_known_rule_answer_never_calls_the_model():
    llm = FakeJudgeLLM(out("not_closed", quotes=[ODD]))
    rule = Verdict("closure", "closed", "rule", basis="weekly")
    assert rule_first(CTX, requests.closure(ODD, FRIDAY), rule, LLMJudge(llm)).value == "closed"
    assert llm.calls == []


@pytest.mark.parametrize("kind_request, value, expected", [
    (lambda: requests.closure(ODD, FRIDAY), "closed", "closed"),            # 조심하는 쪽 — 받는다
    (lambda: requests.closure(ODD, FRIDAY), "not_closed", "unknown"),       # 풀어 주는 쪽 — 모름으로
])
def test_closure_accepts_only_closed(kind_request, value, expected):
    llm = LLMJudge(FakeJudgeLLM(out(value, quotes=[ODD])))
    verdict = rule_first(CTX, kind_request(), _unknown("closure"), llm)
    assert verdict.value == expected
    if expected == "unknown":
        assert any("llm_relaxing_not_accepted" in d for d in verdict.dropped)


@pytest.mark.parametrize("value, expected", [("blocks", "blocks"), ("no_effect", "unknown")])
def test_disaster_accepts_only_blocks(value, expected):
    text = "[종로구] 사직로 일대 행사로 보행 통제"
    message = {"kind": "행사", "step": "안전안내", "text": text, "regions": ["서울특별시 종로구"],
               "created_at": "2026-11-13T09:00:00+09:00"}
    llm = LLMJudge(FakeJudgeLLM(out(value, quotes=[text])))
    request = requests.disaster_effect("경복궁", "activity", [message], FRIDAY)
    assert rule_first(CTX, request, _unknown("disaster_effect"), llm).value == expected


def test_over_budget_or_failed_call_stays_unknown():
    llm = LLMJudge(FakeJudgeLLM(out("closed", quotes=[ODD])))
    assert rule_first(CTX, requests.closure(ODD, FRIDAY), _unknown("closure"), llm, budget=lambda _k: False).value == "unknown"
    broken = LLMJudge(FakeJudgeLLM(exc=RuntimeError("down")))
    assert rule_first(CTX, requests.closure(ODD, FRIDAY), _unknown("closure"), broken).value == "unknown"


def test_live_status_takes_llm_mode_and_accepts_only_closed():
    """`[2026-10-12 사용자 결정]` 실시간 운영도 `llm` 을 받는다 — 규칙 뒤 웹 확인. 라벨이 없어 「닫혔다」만 받는다."""
    assert kind_mode("live_status", {"live_status": "llm"}) == "llm"
    assert kind_mode("closure", {"closure": "llm"}) == "llm"
    request = requests.live_status("경복궁", "activity", None, FRIDAY)
    opened = LLMJudge(FakeJudgeLLM(out("open", citations=[{"url": "https://a.go.kr", "quote": "정상 개방",
                                                           "published_at": None}]), sources=["https://a.go.kr"]))
    assert rule_first(CTX, request, _unknown("live_status"), opened).value == "unknown"


# ── 팀 경로 ──────────────────────────────────────────────────────────

WEEK = {d: {"open": "09:00", "close": "18:00"} for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
CLEAR = {"verdict": "clear", "disruptions": [], "advisories": [], "checks": [], "failed_categories": [],
         "not_connected": []}


def _run(monkeypatch, llm_value, *, mode="llm"):
    from app.domains.travel_ops.instances.activity.judge.modes import kind_mode as real

    monkeypatch.setattr(team_module, "kind_mode", lambda kind, _m=None: real(kind, {"closure": mode}))
    values = {"read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": FRIDAY, "party_size": 2, "capacity": 4},
              "read.policy": [], "read.disruptions": CLEAR, "read.disaster": None, "read.holiday": None,
              "read.place": {"place_id": "p1", "name": "어느 공방", "weather_sensitive": False, "latitude": 37.57,
                             "longitude": 126.98, "source_content_id": None},
              # 요일표 없음 — 휴무를 정할 것이 휴무 원문뿐이다(규칙이 못 읽는 상황)
              "read.place_hours": {"known": False, "attributes": {}, "source": "tour_api",
                                   "why_unknown": None, "conditions": [], "usetime_text": "주말 10:00~17:00",
                                   "restdate_text": ODD},
              "read.place_candidates": None}
    team = ActivityTeam(FakeTools(values))
    team.judge_llm = FakeJudgeLLM(out(llm_value, quotes=[ODD]))
    result = asyncio.run(team.execute(task("activity", "activity.check_feasible", pack("activity", scope=["activity"]),
                                           list(ActivityTeam.manifest.allowed_tools))))
    return result, team.judge_llm


def test_team_closes_the_day_when_the_model_reads_a_closure(monkeypatch):
    result, llm = _run(monkeypatch, "closed")
    decision = result.decisions[0]
    assert decision["reason"] == "closed_weekday" and decision["hours"]["closure_reason"] == "llm"
    assert HOURS_AUTO_READ in result.answer and llm.calls


def test_team_does_not_open_the_day_on_the_models_word(monkeypatch):
    result, _ = _run(monkeypatch, "not_closed")
    assert result.decisions[0].get("reason") != "closed_weekday"
    assert result.decisions[0]["hours"]["closed"] is None            # 모름 그대로 — 「휴무 아님」으로 확정하지 않았다


def test_without_llm_mode_the_model_is_not_asked(monkeypatch):
    _, llm = _run(monkeypatch, "closed", mode="rule")
    assert llm.calls == []


def _run_disaster(monkeypatch, llm_value):
    from app.domains.travel_ops.instances.activity.judge.modes import kind_mode as real

    from ._disaster import disaster_from

    monkeypatch.setattr(team_module, "kind_mode", lambda kind, _m=None: real(kind, {"disaster_effect": "llm"}))
    text = "[종로구] 사직로 일대 행사로 보행 통제"
    message = {"kind": "행사", "step": "안전안내", "text": text, "regions": ["서울특별시 종로구"],
               "created_at": "2026-11-13T09:00:00+09:00", "serial": "9", "weather": False}
    report = {**CLEAR, "checks": [{"category": "disaster_msg", "status": "ok", "unclassified": [message]}]}
    values = {"read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": FRIDAY, "party_size": 2, "capacity": 4},
              "read.policy": [], "read.disruptions": report, "read.disaster": disaster_from(report), "read.holiday": None,
              "read.place": {"place_id": "p1", "name": "경복궁", "weather_sensitive": False, "latitude": 37.5796,
                             "longitude": 126.9770, "source_content_id": None},
              "read.place_hours": {"known": True, "attributes": {"hours_week": WEEK}, "source": "tour_api",
                                   "why_unknown": None, "conditions": [], "usetime_text": "09:00~18:00",
                                   "restdate_text": None},
              "read.place_candidates": None}
    team = ActivityTeam(FakeTools(values))
    team.judge_llm = FakeJudgeLLM(out(llm_value, quotes=[text]))
    return asyncio.run(team.execute(task("activity", "activity.check_feasible", pack("activity", scope=["activity"]),
                                         list(ActivityTeam.manifest.allowed_tools))))


def test_team_blocks_on_an_unclassified_message_when_the_model_says_blocks(monkeypatch):
    assert _run_disaster(monkeypatch, "blocks").decisions[0]["reason"] == "disaster_blocks"


def test_team_keeps_going_when_the_model_says_no_effect(monkeypatch):
    assert _run_disaster(monkeypatch, "no_effect").decisions[0].get("reason") != "disaster_blocks"
