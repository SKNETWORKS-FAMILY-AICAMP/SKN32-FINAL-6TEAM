# -*- coding: utf-8 -*-
"""check_feasible wiring — read.weather / read.disaster 계약.

[2026-09-28 역복원]
  구: read.place_candidates 배선 + 3분기 status(problem/insufficient_info/ok) 검증
  신: read.disruptions 단일 도구 (develop 병합 — 일시)
  복원: read.weather + read.disaster 개별 도구로 복원 (role-activity 아키텍처)

  장소 후보 DB 조회는 tests/unit/travel/test_db_search_place_candidates.py 담당.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.instances.activity import ActivityTeam

from .helpers import FakeTools, pack, task

UTC = timezone.utc
ALLOWED = ActivityTeam.manifest.allowed_tools

_DISASTER_CRITICAL = {
    "for_region": [{"step": "위급재난", "kind": "지진"}],
    "confirmed_at": "2026-09-28T10:00:00+00:00",
    "source": "disaster_api",
}


def _values(*, starts_at=None, disaster=None, place=True, party=2, capacity=4):
    starts_at = starts_at or datetime.now(UTC) + timedelta(days=30)
    place_val = ({"place_id": "p1", "weather_sensitive": False,
                  "latitude": 37.5796, "longitude": 126.9770} if place else None)
    return {
        "read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": starts_at,
                         "party_size": party, "capacity": capacity},
        "read.policy": [{"cancel_deadline_hours": 24}],
        "read.place": place_val,
        "read.weather": None,
        "read.disaster": disaster,
    }


def _task():
    return task("activity", "activity.check_feasible",
                pack("activity", scope=["activity"]), ALLOWED)


async def _run(values):
    tools = FakeTools(values)
    result = await ActivityTeam(tools).execute(_task())
    return result, [name for name, _ in tools.calls]


# ══════════════════════════════════════════════════════════════════
# 계약
# ══════════════════════════════════════════════════════════════════

def test_disruptions_is_in_allowed_tools():
    """read.disruptions는 handle_trigger에서 사용 — manifest에 선언돼 있어야 한다."""
    assert "read.disruptions" in ALLOWED


def test_weather_and_disaster_are_in_allowed_tools():
    """read.weather / read.disaster — _check_feasible이 쓰는 두 도구."""
    assert "read.weather" in ALLOWED
    assert "read.disaster" in ALLOWED


# ══════════════════════════════════════════════════════════════════
# check_feasible 배선
# ══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ok_report_returns_feasible_true():
    result, _ = await _run(_values())
    assert result.decisions[0]["feasible"] is True


@pytest.mark.asyncio
async def test_critical_disaster_returns_feasible_false():
    result, _ = await _run(_values(disaster=_DISASTER_CRITICAL))
    d = result.decisions[0]
    assert d["feasible"] is False
    assert d["disaster"]["blocks"] is True


@pytest.mark.asyncio
async def test_disrupted_does_not_call_place_candidates():
    """후보 풀 조회는 check_feasible 범위 밖 — 재난 상황에서도 부르지 않는다."""
    _, calls = await _run(_values(disaster=_DISASTER_CRITICAL))
    assert "read.place_candidates" not in calls


@pytest.mark.asyncio
async def test_place_none_returns_infeasible():
    """장소를 모르면 feasible=False + place_confirmed=False — 성립을 단정하지 않는다."""
    result, calls = await _run(_values(place=False))
    assert result.decisions[0]["feasible"] is False
    assert result.decisions[0]["place_confirmed"] is False
    assert "read.disruptions" not in calls


@pytest.mark.asyncio
async def test_capacity_check_happens_before_place_lookup():
    """정원 초과는 read.place 없이 즉시 반환 — 불필요한 도구 호출 없다."""
    result, calls = await _run(_values(party=5, capacity=4))
    assert result.decisions[0]["feasible"] is False
    assert result.decisions[0]["reason"] == "party_over_capacity"
    assert "read.place" not in calls


# ══════════════════════════════════════════════════════════════════
# 예산
# ══════════════════════════════════════════════════════════════════

def test_max_steps_is_twelve():
    assert ActivityTeam.manifest.max_steps == 12


@pytest.mark.asyncio
async def test_ok_path_tool_calls_are_within_budget():
    """정상 경로 도구 호출 수 ≤ max_steps."""
    _, calls = await _run(_values())
    assert len(calls) <= ActivityTeam.manifest.max_steps
