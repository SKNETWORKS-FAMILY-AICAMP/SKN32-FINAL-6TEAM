# -*- coding: utf-8 -*-
"""활동 팀 develop 의 팀 코드(10/1~10/2)에서 우리 설계에 맞춰 가져온 둘. `[2026-10-05]` — 점검표 `02_activity.md` 의 「일부 반영」.

① 성립 판정(`check_feasible`)은 취소·환급 규정이 필요 없다 — 규정 검색이 0건이어도 멈추지 않는다.
② 실패·예외 코드와 한 줄 로그 — 정상 응답으로 끝나는 실패(이미 시작됨 · 정원 초과)와 도구 예외만(`failure_codes.py`).
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

import pytest

from app.core.contracts import NextAction
from app.domains.travel_ops.instances.activity import ActivityTeam
from app.domains.travel_ops.instances.activity import failure_codes as fc

from ..helpers import FakeTools, in_hours, pack, task

ALLOWED = ActivityTeam.manifest.allowed_tools
CLEAR = {"verdict": "clear", "disruptions": [], "advisories": [], "checks": [], "failed_categories": [],
         "not_connected": []}


def _values(starts_at, *, policy, party=2, capacity=4, report=CLEAR):
    return {"read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": starts_at,
                             "party_size": party, "capacity": capacity},
            "read.policy": policy,
            "read.place": {"place_id": "p1", "weather_sensitive": True, "latitude": 37.5, "longitude": 127.0},
            "read.disruptions": report}


def _run(values, capability="activity.check_feasible"):
    import asyncio

    context = pack("activity", scope=["activity"])
    return asyncio.run(ActivityTeam(FakeTools(values)).execute(task("activity", capability, context, ALLOWED)))


# ── ① 성립 판정은 규정이 필요 없다 ───────────────────────────────
@pytest.mark.parametrize("policy", [None, []])
def test_feasibility_does_not_stop_when_no_cancellation_policy_was_found(policy):
    result = _run(_values(in_hours(30), policy=policy))
    assert result.outcome == "completed" and result.next_action is NextAction.RESPOND
    assert result.decisions[0]["feasible"] is True


@pytest.mark.parametrize("capability", ["activity.check_cancelable", "activity.propose_change"])
def test_the_other_capabilities_still_stop_without_a_policy(capability):
    """규정이 꼭 필요한 일은 그대로 모른다고 멈춘다 — 규정 없이 취소 가능 여부를 지어내지 않는다."""
    result = _run(_values(in_hours(30), policy=None), capability)
    assert result.outcome == "escalated" and "취소·환급 규정" in str(result.failure_code)


# ── ② 실패 코드 · 한 줄 로그 ───────────────────────────────────
def test_codes_and_descriptions_match():
    codes = {value for name, value in vars(fc).items() if name.isupper() and name != "LOGGER_NAME"
             and name != "DESCRIPTIONS"}
    assert codes == set(fc.DESCRIPTIONS)


def test_already_started_leaves_a_code_and_a_log_line(caplog):
    with caplog.at_level(logging.WARNING, logger=fc.LOGGER_NAME):
        result = _run(_values(datetime.now(UTC) - timedelta(hours=3), policy=[object()]))
    assert result.decisions[0]["failure_code"] == fc.ALREADY_STARTED
    [record] = [r for r in caplog.records if r.name == fc.LOGGER_NAME]
    line = json.loads(record.getMessage())
    assert line["code"] == fc.ALREADY_STARTED and line["capability"] == "activity.check_feasible"
    assert set(line) == {"event", "code", "team", "case_id", "capability"}        # 좌표·장소명·문장 없음


def test_party_over_capacity_leaves_a_code():
    result = _run(_values(in_hours(30), policy=[object()], party=9, capacity=4))
    assert result.decisions[0]["reason"] == "party_over_capacity"
    assert result.decisions[0]["failure_code"] == fc.PARTY_OVER_CAPACITY


def test_a_tool_exception_is_logged_and_rethrown_not_swallowed(caplog):
    class Broken(FakeTools):
        def call(self, name, context, arguments, allowed_tools, seen, budget=None):
            if name == "read.place":
                raise RuntimeError("secret 37.5,127.0 경복궁")
            return super().call(name, context, arguments, allowed_tools, seen, budget)

    import asyncio

    context = pack("activity", scope=["activity"])
    team = ActivityTeam(Broken(_values(in_hours(30), policy=[object()])))
    with caplog.at_level(logging.WARNING, logger=fc.LOGGER_NAME), pytest.raises(RuntimeError):
        asyncio.run(team.execute(task("activity", "activity.check_feasible", context, ALLOWED)))
    [record] = [r for r in caplog.records if r.name == fc.LOGGER_NAME]
    line = json.loads(record.getMessage())
    assert line["code"] == fc.TOOL_ERROR and line["tool"] == "read.place" and line["error"] == "RuntimeError"
    assert "경복궁" not in record.getMessage() and "secret" not in record.getMessage()    # 예외 문구는 싣지 않는다
