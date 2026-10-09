# -*- coding: utf-8 -*-
"""develop 판 활동 팀의 판정 LLM 섀도 — `[2026-10-09]` D-CS-015 단계 B.

★가장 중요한 약속 — **섀도에서 고객 결과는 판정 LLM 이 없을 때와 같다.** LLM 이 모든 판정에서 develop 판과 반대로
  답하게 해 놓고 결과(답변 · decisions · 근거 · 경고 · 실패 코드 · 제안)를 통째로 비교한다.
★섀도 기록의 비교 기준은 develop 판이 실제로 낸 값이다(role-activity 판 규칙이 아니다).
★붙이는 판정은 ① 정기휴무 · ③ 실내외 · ④ 재난문자 · ⑤ 실시간 운영 — ② 운영시간은 붙이지 않는다.
"""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.instances.activity import ActivityTeam

from ..helpers import FakeTools, pack, task
from ._judge_fakes import out

ALLOWED = ActivityTeam.manifest.allowed_tools
KST = timezone(timedelta(hours=9))
TUESDAY = datetime(2026, 11, 10, 14, 0, tzinfo=KST)
WEEK = {day: {"open": "09:00", "close": "18:00"} for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
NOTICE = "https://www.example.go.kr/notice?id=1"
CLEAR = {"verdict": "clear", "disruptions": [], "advisories": [], "checks": [], "failed_categories": [],
         "not_connected": [], "indoor_unknown": False}
QUIET_MESSAGE = {"kind": "기타", "step": "안전안내", "text": "[종로구청] 세종대로 일대 집회로 교통 혼잡이 예상됩니다",
                 "created_at": "2026-11-10T09:00:00+09:00", "regions": ["서울특별시 종로구"], "serial": "7",
                 "weather": False}


class ContraryJudgeLLM:
    """판정 종류마다 develop 판과 **반대로** 답한다 — 섀도가 고객 결과에 새면 시험이 잡는다."""

    def __init__(self):
        self.kinds: list[str] = []

    async def judge(self, prompt_key, payload, *, schema, schema_name, web_search=None,
                    instructions=None, run_id=None):
        from types import SimpleNamespace

        kind = payload["kind"]
        self.kinds.append(kind)
        sources: list[str] = []
        if kind == "closure":
            output = out("not_closed", quotes=[payload["restdate_text"]])
        elif kind == "weather_sensitive":
            output = out("outdoor")
        elif kind == "disaster_effect":
            output = out("blocks", quotes=[payload["messages"][0]["text"]])
        elif kind == "live_status":
            output = out("closed", citations=[{"url": NOTICE, "quote": "임시 휴관", "published_at": "2026-11-01"}])
            sources = [NOTICE]
        else:
            raise AssertionError(f"develop 판은 {kind} 를 부르지 않는다")
        return SimpleNamespace(output=output, sources=sources, search_calls=len(sources), latency_ms=3,
                               input_tokens=1, output_tokens=1, reasoning_tokens=0, model="fake")


class Inline:
    """받은 일을 다른 스레드에서 끝까지 돌리고 기다린다(Team 은 이벤트 루프 안에서 돈다)."""

    def submit(self, work):
        thread = threading.Thread(target=work)
        thread.start()
        thread.join(10)
        return True


def _hours(week=WEEK, restdate=None):
    return {"known": True, "attributes": {"hours_week": week}, "source": "tour_api", "why_unknown": None,
            "conditions": [], "usetime_text": "09:00~18:00", "restdate_text": restdate}


SCENARIOS = {
    # ① 휴무 원문이 그 날을 막는다 → 변경 제안(대체 장소 포함)
    "closed_by_text": dict(hours=_hours(restdate="매주 화요일 휴무")),
    # ① 휴무 원문이 있지만 그 날은 아니다 → 성립
    "open_with_text": dict(hours=_hours(restdate="매주 월요일 휴무")),
    # ③ 실내외를 모르는데 날씨만 → 먼저 묻는다
    "indoor_unknown_weather": dict(sensitive=None, place_class={"content_id": "x", "lcls1": "XX", "lcls2": "XX01",
                                                                 "address": "서울특별시 종로구 사직로 161",
                                                                 "weather_sensitive": None},
                                   report={**CLEAR, "verdict": "disrupted", "indoor_unknown": True,
                                           "disruptions": [{"category": "forecast", "kind": "강수확률 80%"}]}),
    # ④ 정지 대상이 아닌 미분류 문자 + ⑤ 실외 → 성립
    "quiet_message_outdoor": dict(sensitive=True,
                                  report={**CLEAR, "checks": [{"category": "disaster_msg", "status": "ok",
                                                               "unclassified": [QUIET_MESSAGE]}]}),
}


def _values(*, hours=None, sensitive=False, place_class=None, report=CLEAR):
    return {"read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": TUESDAY,
                             "party_size": 2, "capacity": 4},
            "read.policy": [],
            "read.place": {"place_id": "p1", "name": "경복궁", "weather_sensitive": sensitive,
                           "latitude": 37.5796, "longitude": 126.9770, "source_content_id": None},
            "read.place_class": place_class, "read.disruptions": report, "read.place_hours": hours or _hours(),
            "read.place_candidates": None, "read.holiday": None}


def _request():
    return task("activity", "activity.check_feasible", pack("activity", scope=["activity"]), ALLOWED)


def _run(values, *, llm=None, sink=None, request=None):
    team = ActivityTeam(FakeTools(values))
    if llm is not None:
        team.judge_llm = llm
        team.judge_runner = Inline()
        team.judge_shadow_sink = sink
    return asyncio.run(team.execute(request or _request()))


def _customer_view(result):
    """고객에게 닿는 것 전부 — 근거는 관측 시각만 뺀다(두 번 돌리면 시각이 다르다)."""
    view = result.model_dump(mode="json")
    for evidence in view.get("evidence") or []:
        evidence.pop("observed_at", None)
    return view


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_shadow_never_changes_what_the_customer_gets(name):
    values = _values(**SCENARIOS[name])
    llm = ContraryJudgeLLM()

    request = _request()      # ★같은 작업으로 두 번 — 작업 id · 멱등 키까지 같아야 비교가 된다

    assert _customer_view(_run(values, llm=llm, request=request)) == _customer_view(_run(values, request=request))
    assert llm.kinds, "섀도가 판정 LLM 을 한 번도 부르지 않았다 — 시나리오가 판정 지점을 지나지 않는다"


def test_without_a_judge_nothing_is_called():
    llm = ContraryJudgeLLM()
    team = ActivityTeam(FakeTools(_values(**SCENARIOS["quiet_message_outdoor"])))
    asyncio.run(team.execute(task("activity", "activity.check_feasible", pack("activity", scope=["activity"]),
                                  ALLOWED)))

    assert team.judge_llm is None and llm.kinds == []


def _records(name):
    records: list[dict] = []
    llm = ContraryJudgeLLM()
    _run(_values(**SCENARIOS[name]), llm=llm, sink=records.append)
    return {r["kind"]: r for r in records}, llm


def test_closure_shadow_compares_against_the_develop_rule():
    records, _ = _records("closed_by_text")

    closure = records["closure"]
    assert closure["rule"] == "closed" and closure["llm"] == "not_closed" and closure["agree"] is False
    assert closure["comparable"] is True


def test_indoor_shadow_compares_against_unknown_and_live_status_is_not_called_for_unknown_far_off():
    records, llm = _records("indoor_unknown_weather")

    assert records["weather_sensitive"]["rule"] == "unknown" and records["weather_sensitive"]["llm"] == "outdoor"
    assert "operating_hours" not in llm.kinds


def test_quiet_disaster_message_and_live_status_shadows():
    records, llm = _records("quiet_message_outdoor")

    assert records["disaster_effect"]["rule"] == "no_effect" and records["disaster_effect"]["llm"] == "blocks"
    assert records["live_status"]["rule"] == "unknown" and records["live_status"]["llm"] == "closed"
    assert records["live_status"]["citations"] == 1
    assert "operating_hours" not in llm.kinds


def test_live_status_is_skipped_for_a_known_indoor_place_far_off():
    """실내로 알고 72시간보다 먼 일정은 웹 검색을 부르지 않는다(비용)."""
    _, llm = _records("open_with_text")

    assert "live_status" not in llm.kinds and llm.kinds == ["closure"]


def test_shadow_records_carry_no_place_name_or_customer_text():
    records, _ = _records("quiet_message_outdoor")

    for record in records.values():
        assert "경복궁" not in str(record) and "집회" not in str(record)
