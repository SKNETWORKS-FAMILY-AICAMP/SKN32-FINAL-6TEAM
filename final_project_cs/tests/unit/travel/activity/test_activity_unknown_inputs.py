# -*- coding: utf-8 -*-
"""성립 판정은 시각 · 장소를 모르면 「정보 부족」으로 답한다 — `[2026-10-09]` team 통합 ③(role-activity 판의 규칙).

전에 develop 판은 시각을 모르면 사람에게 넘겼고(escalate), 장소를 모르면 「확인한 범위에서는 성립합니다 … 판정하지
않았습니다」로 앞뒤가 어긋난 답을 냈다. 취소 · 변경은 시각이 있어야 계산되므로 그대로 멈춘다.
"""
from __future__ import annotations

import pytest

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


def _assert_insufficient(result, code):
    assert result.outcome == "completed"
    decision = result.decisions[0]
    assert decision["status"] == "insufficient_info" and decision["feasible"] is False
    assert decision["failure_code"] == code
    assert "성립합니다" not in result.answer and "판정하지 않았습니다" in result.answer


@pytest.mark.asyncio
@pytest.mark.parametrize("booking", [_without_time(), {**BOOKING, "starts_at": "모름"}])
async def test_unknown_time_is_insufficient_info_not_escalated(booking):
    result = await ActivityTeam(_tools(booking=booking)).execute(_task())

    _assert_insufficient(result, "time_unknown")
    assert result.decisions[0]["reason"] == "time_unknown"


@pytest.mark.asyncio
async def test_unknown_time_does_not_read_the_place():
    tools = _tools(booking=_without_time())
    await ActivityTeam(tools).execute(_task())

    assert "read.place" not in [name for name, _ in tools.calls]


@pytest.mark.asyncio
async def test_unknown_time_does_not_hide_a_party_over_capacity():
    result = await ActivityTeam(_tools(booking=_without_time(party_size=9))).execute(_task())

    assert result.decisions[0]["reason"] == "party_over_capacity"


@pytest.mark.asyncio
@pytest.mark.parametrize("capability", ["activity.check_cancelable", "activity.propose_change"])
async def test_other_capabilities_still_escalate_without_a_time(capability):
    result = await ActivityTeam(_tools(booking=_without_time())).execute(_task(capability))

    assert result.outcome == "escalated" and result.failure_code == "unknown_예약 시각"


@pytest.mark.asyncio
async def test_unknown_place_is_insufficient_info_and_skips_the_checks():
    tools = _tools(place=None)
    result = await ActivityTeam(tools).execute(_task())

    _assert_insufficient(result, "place_unknown")
    assert result.decisions[0]["place_confirmed"] is False
    assert "장소·운영 정보를 확인하지 못했다" in result.warnings
    called = [name for name, _ in tools.calls]
    assert "read.disruptions" not in called and "read.place_hours" not in called


@pytest.mark.asyncio
async def test_known_time_and_place_still_reach_the_checks():
    tools = _tools()
    result = await ActivityTeam(tools).execute(_task())

    assert result.outcome == "completed" and result.decisions[0]["feasible"] is True
    assert "read.disruptions" in [name for name, _ in tools.calls]


# ── 인원 · 정원 모름 — 막지 않고 경고로 남긴다(`[2026-10-09]` 사용자 결정) ──────────────

@pytest.mark.asyncio
@pytest.mark.parametrize(("drop", "label"), [(("party_size",), "신청 인원을"), (("capacity",), "정원을"),
                                             (("party_size", "capacity"), "신청 인원 · 정원을")])
async def test_unknown_headcount_is_warned_not_blocked(drop, label):
    booking = {k: v for k, v in BOOKING.items() if k not in drop}
    result = await ActivityTeam(_tools(booking=booking)).execute(_task())

    decision = result.decisions[0]
    assert result.outcome == "completed" and decision["feasible"] is True
    assert decision["headcount_checked"] is False
    assert any(w.startswith(label) and "정원 초과 여부는 판정하지 않았다" in w for w in result.warnings)
    assert "정원 초과 여부는 판정하지 않았습니다" in result.answer


@pytest.mark.asyncio
async def test_known_headcount_adds_no_warning():
    result = await ActivityTeam(_tools()).execute(_task())

    assert result.decisions[0]["headcount_checked"] is True
    assert not any("정원 초과" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_unknown_headcount_is_also_warned_when_time_or_place_is_unknown():
    no_time = await ActivityTeam(_tools(booking=_without_time(party_size=None))).execute(_task())
    no_place = await ActivityTeam(_tools(booking={**BOOKING, "capacity": None}, place=None)).execute(_task())

    for result in (no_time, no_place):
        assert result.decisions[0]["status"] == "insufficient_info"
        assert any("정원 초과 여부는 판정하지 않았다" in w for w in result.warnings)
