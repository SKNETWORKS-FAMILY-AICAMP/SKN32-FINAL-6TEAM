# -*- coding: utf-8 -*-
"""성립 판정은 시각 · 장소를 모르면 성립을 단정하지 않는다 — `[2026-10-09]` team 통합 ③(role-activity 판의 규칙).

전에 develop 판은 시각을 모르면 사람에게 넘겼고(escalate), 장소를 모르면 「확인한 범위에서는 성립합니다 … 판정하지
않았습니다」로 앞뒤가 어긋난 답을 냈다. 취소 · 변경은 시각이 있어야 계산되므로 그대로 멈춘다.
★`[2026-10-11]` 「정보 부족」(`completed` + `insufficient_info` — 계약 밖 값)을 계약 모양으로 바꿨다(D4 · 수정본 §12):
  시각을 모르면 고객에게 묻고(`waiting` · `customer_input`), 예약의 장소를 못 읽으면 운영 담당자에게 넘긴다(`escalated`).
"""
from __future__ import annotations

import pytest

from app.core.contracts import NextAction
from app.domains.travel_ops.instances.activity import ActivityTeam

from ..helpers import FakeTools, in_hours, pack, task

ALLOWED = ActivityTeam.manifest.allowed_tools
BOOKING = {"booking_id": "b1", "place_id": "p1", "starts_at": in_hours(30), "party_size": 2, "capacity": 4}
PLACE = {"place_id": "p1", "name": "경복궁", "weather_sensitive": False, "latitude": 37.5, "longitude": 127.0}
POLICY = [{"cancel_deadline_hours": 24}]


def _task(capability: str = "activity.check_feasible"):
    return task("activity", capability, pack("activity", scope=["activity"]), ALLOWED)


CLEAR = {"verdict": "clear", "disruptions": [], "advisories": [], "failed_categories": [], "not_connected": [],
         "checks": []}


def _tools(*, booking=BOOKING, place=PLACE):
    return FakeTools({"read.booking": booking, "read.policy": POLICY, "read.place": place,
                      "read.disruptions": CLEAR, "read.place_hours": None})


def _without_time(**changes):
    return {**{k: v for k, v in BOOKING.items() if k != "starts_at"}, **changes}


def _assert_asks_for_time(result):
    assert result.outcome == "waiting" and result.next_action is NextAction.WAIT_FOR_INPUT
    assert result.wait_reason == "customer_input" and result.required_input_schema["required"] == ["starts_at"]
    decision = result.decisions[0]
    assert decision["feasible"] is None and "status" not in decision
    assert decision["failure_code"] == "time_unknown" and decision["reason"] == "time_unknown"
    assert "성립합니다" not in result.answer and "판정하지 않았습니다" in result.answer


@pytest.mark.asyncio
@pytest.mark.parametrize("booking", [_without_time(), {**BOOKING, "starts_at": "모름"}])
async def test_unknown_time_asks_the_customer_not_escalated(booking):
    result = await ActivityTeam(_tools(booking=booking)).execute(_task())

    _assert_asks_for_time(result)


@pytest.mark.asyncio
async def test_unknown_time_does_not_read_the_place():
    tools = _tools(booking=_without_time())
    await ActivityTeam(tools).execute(_task())

    assert "read.place" not in [name for name, _ in tools.calls]


@pytest.mark.asyncio
@pytest.mark.parametrize("capability", ["activity.check_cancelable", "activity.propose_change"])
async def test_other_capabilities_still_escalate_without_a_time(capability):
    result = await ActivityTeam(_tools(booking=_without_time())).execute(_task(capability))

    assert result.outcome == "escalated" and result.failure_code == "unknown_예약 시각"


@pytest.mark.asyncio
async def test_unknown_place_is_escalated_and_skips_the_checks():
    """★예약에 붙은 장소를 못 읽은 것은 고객이 풀 수 없다 — 「없음」으로 단정하지 않고 넘긴다(수정본 UC-A3 `1a`)."""
    tools = _tools(place=None)
    result = await ActivityTeam(tools).execute(_task())

    assert result.outcome == "escalated" and result.failure_code == "place_unknown"
    assert any(w.startswith("장소·운영 정보를 확인하지 못했다") for w in result.warnings)
    called = [name for name, _ in tools.calls]
    assert "read.disruptions" not in called and "read.place_hours" not in called


@pytest.mark.asyncio
async def test_known_time_and_place_still_reach_the_checks():
    tools = _tools()
    result = await ActivityTeam(tools).execute(_task())

    assert result.outcome == "completed" and result.decisions[0]["feasible"] is True
    assert "read.disruptions" in [name for name, _ in tools.calls]


# ── 인원은 성립 판정 항목이 아니다(`[2026-10-12]` D3 · 수정본 §6) ──────────────
#   전에는 정원 초과면 막고, 인원 · 정원을 모르면 「정원 초과 여부는 판정하지 않았다」 경고를 붙였다.

@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [{"party_size": 9}, {"party_size": None}, {"capacity": None},
                                     {"party_size": None, "capacity": None}])
async def test_headcount_neither_blocks_nor_warns(changes):
    result = await ActivityTeam(_tools(booking={**BOOKING, **changes})).execute(_task())

    decision = result.decisions[0]
    assert result.outcome == "completed" and decision["feasible"] is True
    assert "headcount_checked" not in decision
    assert not any("정원" in w for w in result.warnings) and "정원" not in result.answer
