# -*- coding: utf-8 -*-
"""Activity 의 규정 검색(RAG) 끄기 — `[2026-10-16]` 멘토링 결론(핵심 플로우 집중).

꺼진 상태(`_RAG_OFF = True`, 운영 기본값)에서
- `read.policy` 를 **부르지 않는다**.
- 성립 판정(`check_feasible`)은 그대로 된다 — 규정을 쓰지 않는 길이다.
- 취소·변경 판정은 「취소·환급 규정」을 모른다고 멈춘다(지어내지 않는다).
- 선언에서 `policy` 가 빠져 Controller 도 이 팀의 RAG 를 돌지 않는다. 코어와 다른 팀은 그대로다.
"""
from __future__ import annotations

import pytest

from app.core.context import PolicyChunk
from app.domains.travel_ops.instances.activity import ActivityTeam
from app.domains.travel_ops.instances.dining.team import DiningTeam

from ..helpers import FakeTools, in_hours, pack, task

ALLOWED = ActivityTeam.manifest.allowed_tools


def _task(capability):
    return task("activity", capability, pack("activity", scope=["travel_activity"]), ALLOWED)


def _values():
    return {
        "read.booking": {"booking_id": "b1", "place_id": "p1", "kind": "activity",
                         "starts_at": in_hours(30), "party_size": 2, "capacity": 4},
        "read.policy": [PolicyChunk(document_id="d", chunk_no=1, scope="travel_activity", score=0.7,
                                    content="취소는 시작 전까지 접수한다.")],
        "read.booking_terms": {"booking_id": "b1", "matched_scope": "booking", "cancel_deadline_hours": 24,
                               "penalty_by_hours": {"24": 0.5}, "source": "seed:mock",
                               "observed_at": "2026-09-23T00:00:00+00:00"},
    }


def test_it_is_off_by_default():
    assert ActivityTeam._RAG_OFF is True


def test_policy_is_no_longer_declared_for_activity_only():
    assert "policy" not in ActivityTeam.manifest.required_context
    assert "policy" in DiningTeam.manifest.required_context        # 다른 팀은 그대로


@pytest.mark.asyncio
@pytest.mark.parametrize("capability", ["activity.check_cancelable", "activity.propose_change"])
async def test_cancel_and_change_stop_as_unknown_without_calling_the_search(capability):
    tools = FakeTools(_values())
    result = await ActivityTeam(tools).execute(_task(capability))

    assert result.outcome == "escalated" and result.failure_code == "unknown_취소·환급 규정"
    assert "read.policy" not in [name for name, _ in tools.calls]


@pytest.mark.asyncio
async def test_feasibility_still_works_and_never_calls_the_search():
    values = {**_values(),
              "read.place": {"place_id": "p1", "name": "경복궁", "weather_sensitive": False, "latitude": 37.5, "longitude": 127.0},
              "read.disruptions": {"verdict": "clear", "disruptions": [], "advisories": [], "failed_categories": [],
                                   "not_connected": [], "checks": []},
              "read.place_hours": None}
    tools = FakeTools(values)
    result = await ActivityTeam(tools).execute(_task("activity.check_feasible"))

    assert result.outcome == "completed"
    assert "read.policy" not in [name for name, _ in tools.calls]
