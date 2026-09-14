# -*- coding: utf-8 -*-
"""도구를 **여럿** 부른 Team 은 근거를 **전부** 남겨야 한다.

★★2026-09-09 결함의 회귀 테스트. `_evidence()` 가 매번
  `task.context.evidence` 에서 다시 시작해서 **두 번째 호출이 첫 번째를
  덮었다.** 실 DB 종단 실행에서 예약·규정·장소·기상을 다 읽은 Case 의 근거가
  `['read.weather']` 하나뿐이었다.

★**왜 단위 테스트가 못 잡았나.** 있던 검사들이 전부 도구를 **한 개만** 쓰는
  경로를 봤다. 하나짜리 경로에서는 덮어써도 결과가 같다. 그래서 여기서는
  **여러 개**를 부르는 경로만 본다.

★근거는 이 제품의 첫째 규칙이다 — 근거 없는 문장은 답변에 넣지 않는다
  (`CLAUDE.md` §0.1). 근거가 조용히 사라지면 그 규칙이 무너진다.
"""
from __future__ import annotations

import pytest

from app.modules.travel_ops.activity import ActivityTeam
from app.modules.travel_ops.booking_handoff import BookingHandoffTeam
from app.modules.travel_ops.dining import DiningTeam

from .helpers import FakeTools, in_hours, pack, task


def _sources(result) -> list[str]:
    return [item.source_id for item in result.evidence]


@pytest.mark.asyncio
async def test_activity_keeps_every_source_it_read():
    context = pack("activity", scope=["activity", "weather"])
    request = task("activity", "activity.check_feasible", context,
                   ActivityTeam.manifest.allowed_tools)
    result = await ActivityTeam(FakeTools({
        "read.booking": {"booking_id": "b1", "place_id": "p1",
                         "starts_at": in_hours(30), "party_size": 2, "capacity": 4},
        "read.policy": [{"cancel_deadline_hours": 24}],
        "read.place": {"place_id": "p1", "weather_sensitive": True,
                       "latitude": 37.5, "longitude": 127.0},
        "read.disruptions": {"verdict": "clear", "disruptions": [], "advisories": [],
                             "failed_categories": [], "not_connected": [],
                             "checks": [{"category": "forecast", "status": "ok", "value": {
                                 "matched_hour": "2026-09-10T14:00",
                                 "precipitation_probability": 10, "wind_speed_kmh": 5.0}}]},
    })).execute(request)

    assert _sources(result) == ["read.booking", "read.policy", "read.place", "read.disruptions"]


@pytest.mark.asyncio
async def test_booking_handoff_keeps_both_sides_of_the_comparison():
    """★대조한 **두 쪽**이 다 근거로 남아야 한다. 한쪽만 남으면
    "공급자 기록과 다릅니다" 라는 문장의 근거가 반쪽이 된다."""
    context = pack("booking_handoff", scope=["booking"])
    request = task("booking_handoff", "booking.verify", context,
                   BookingHandoffTeam.manifest.allowed_tools)
    result = await BookingHandoffTeam(FakeTools({
        "read.booking": {"booking_id": "b1", "status": "confirmed"},
        "read.supplier": {"status": "cancelled"},
    })).execute(request)

    assert result.decisions[0]["matches_supplier"] is False
    assert _sources(result) == ["read.booking", "read.supplier"]


@pytest.mark.asyncio
async def test_dining_reads_the_booking_before_the_place():
    """★★2026-09-09 결함. Dining 은 `read.place` 를 **`case_id`** 로 불렀다.

    장소 조회의 열쇠는 `place_id` 이고 그건 예약에 들어 있다 — Case 번호로는
    어느 장소인지 알 수 없다. 실 DB 에서 Dining 이 **항상** 「모름」으로
    떨어졌다. Activity 는 처음부터 예약을 먼저 읽고 있었다 — 같은 규율이
    팀마다 갈렸고, 그것을 종단 실행이 잡았다.
    """
    context = pack("dining", scope=["dining"])
    request = task("dining", "dining.check_open", context,
                   DiningTeam.manifest.allowed_tools)
    tools = FakeTools({
        "read.booking": {"booking_id": "b1", "place_id": "p9"},
        "read.place": {"place_id": "p9", "confirmed_at": "2026-09-09T12:00:00+00:00",
                       "open_at_slot": True},
    })
    result = await DiningTeam(tools).execute(request)

    assert result.outcome == "completed"
    assert _sources(result) == ["read.booking", "read.place"]
    # ★장소를 **place_id 로** 물었는지 본다. case_id 로 물으면 DB 가 못 찾는다.
    assert dict(tools.calls)["read.place"] == {"place_id": "p9"}


@pytest.mark.asyncio
async def test_a_missing_value_adds_no_evidence_but_keeps_the_earlier_ones():
    """★빈 근거는 근거가 아니다. 그렇다고 앞의 것을 지우면 안 된다."""
    context = pack("activity", scope=["activity"])
    request = task("activity", "activity.check_feasible", context,
                   ActivityTeam.manifest.allowed_tools)
    result = await ActivityTeam(FakeTools({
        "read.booking": {"booking_id": "b1", "place_id": "p1",
                         "starts_at": in_hours(30), "party_size": 2, "capacity": 4},
        "read.policy": [{"cancel_deadline_hours": 24}],
        "read.place": None,          # ★장소를 모른다
    })).execute(request)

    assert result.outcome == "completed"
    assert _sources(result) == ["read.booking", "read.policy"]
    assert "확인되지 않아" in result.answer
