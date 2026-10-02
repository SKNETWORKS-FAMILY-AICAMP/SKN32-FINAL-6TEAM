# -*- coding: utf-8 -*-
"""감시 Case 의 활동 팀 — 도구 예산이 바닥나도 **예외로 터지지 않는다.** `[2026-10-02 결함 인계 #1]`

☆결함: 활동 팀은 대안 후보마다 `read.disruptions` 를 한 번씩 불러 재점검한다(후보 수만큼). 후보가 많으면 `max_steps`(12)가 바닥나
  `ToolBudgetExceeded` 가 `TeamResult` 로 바뀌지 않고 Controller 까지 올라가 **실행이 실패**했다 — 앞 후보가 이미 통과했어도 변경안을 못 내고,
  감시 반복(`TripWatchCaseOpener.tick`)이 예외를 안 잡아 **그 회차의 남은 Case 실행까지 끊겼다.** 요식 팀은 후보 재점검에
  「못 봤다」 처리(`ToolLedgerView._SKIP` · `safe_check`)가 있었다.

★지키려는 것: ①후보가 예산보다 많아도 **예외 없이** 결과가 나오고 도구 호출은 `max_steps` 를 넘지 않는다 ②재점검은 **앞 순위 몇 곳만**
(`ACTIVITY_RECHECK_LIMIT`) ③예산이 먼저 바닥나도 **못 본 후보는 고르지 않는다**(점검 안 한 곳을 괜찮다고 하지 않는다).

재현:

    python -m pytest tests/unit/travel/activity/test_activity_trigger_budget.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core.contracts import NextAction
from app.modules.travel_ops.activity import ActivityTeam
from app.modules.travel_ops.itinerary import Item, item_to_dict
from app.modules.travel_ops.itinerary_changes import ACTIVITY_RECHECK_LIMIT

from ..helpers import FakeTools, pack, task

KST = ZoneInfo("Asia/Seoul")
ALLOWED = ActivityTeam.manifest.allowed_tools
HOURS = {"hours": ["09:00", "22:00"]}


def _place(name: str, index: int = 0) -> dict:
    # 0.0003° ≈ 33m 씩 — 전부 600m 안
    return {"place_id": str(uuid4()), "name": name, "kind": "activity", "latitude": 37.5 + 0.0003 * index,
            "longitude": 127.0, "weather_sensitive": False, "attributes": dict(HOURS)}


class _Tools(FakeTools):
    """원래 곳은 「깨졌다」, 후보는 `clear`(또는 시험이 정한 판정)."""

    def __init__(self, values, *, original_id: str, verdicts: dict[str, str] | None = None) -> None:
        super().__init__(values)
        self.original_id, self.verdicts = original_id, verdicts or {}

    def call(self, name, context, arguments, allowed_tools, seen, budget=None):
        if name != "read.disruptions":
            return super().call(name, context, arguments, allowed_tools, seen, budget)
        super().call(name, context, arguments, allowed_tools, seen, budget)          # 권한 · 중복 · 예산을 같은 순서로 본다
        if arguments.get("place_id") == self.original_id:
            return {"verdict": "disrupted", "disruptions": [{"category": "disaster", "kind": "fire"}],
                    "checks": [], "advisories": []}
        return {"verdict": self.verdicts.get(arguments.get("place_id"), "clear"), "disruptions": [],
                "checks": [], "advisories": []}


def _setup(candidates: int, *, verdicts_for=None):
    origin = _place("원래 활동")
    starts = (datetime.now(KST) + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
    item = Item(item_id=uuid4(), seq=1, kind="activity", title="원래 활동", place_id=uuid4(),
                starts_at=starts, ends_at=starts + timedelta(minutes=90), place=origin)
    trip = {"trip_id": str(uuid4()), "version": 1, "customer_id": str(uuid4()), "constraints": {}}
    places = [origin] + [_place(f"후보 {i:02d}", i + 1) for i in range(candidates)]
    values = {"read.itinerary": {"trip": trip, "items": [item_to_dict(item)]}, "read.place_catalog": places}
    verdicts = verdicts_for(places) if verdicts_for else None
    tools = _Tools(values, original_id=origin["place_id"], verdicts=verdicts)
    context = pack("activity", state={
        "subject_ref": {"kind": "trip", "id": trip["trip_id"]}, "trigger_source": "schedule",
        "trigger": {"item_id": str(item.item_id), "at": starts.isoformat(), "detected": "place", "categories": ["disaster"]}})
    return tools, task("activity", "activity.itinerary", context, ALLOWED), places


@pytest.mark.asyncio
async def test_more_candidates_than_the_budget_still_gives_a_result_without_an_exception():
    tools, work, _ = _setup(candidates=20)
    result = await ActivityTeam(tools).execute(work)               # ★전에는 ToolBudgetExceeded 가 그대로 올라왔다
    assert result.outcome == "completed" and result.action_proposals, result
    assert result.next_action is NextAction.RESPOND
    assert len(tools.calls) <= ActivityTeam.manifest.max_steps
    rechecks = [call for call in tools.calls if call[0] == "read.disruptions"][1:]        # 첫 번째는 원래 곳 점검
    assert 0 < len(rechecks) <= ACTIVITY_RECHECK_LIMIT


@pytest.mark.asyncio
async def test_only_the_top_ranked_candidates_are_rechecked():
    """재점검은 앞 순위 몇 곳만 — 비용(바깥 호출)을 후보 수에 비례하게 두지 않는다."""
    tools, work, _ = _setup(candidates=20)
    await ActivityTeam(tools).execute(work)
    assert sum(1 for call in tools.calls if call[0] == "read.disruptions") == 1 + ACTIVITY_RECHECK_LIMIT


@pytest.mark.asyncio
async def test_when_the_budget_runs_out_first_a_candidate_not_checked_is_never_chosen(monkeypatch):
    """예산이 후보 점검보다 먼저 바닥나는 경우(한도를 풀어 둔 상태) — 못 본 곳은 **고르지 않는다**.
    전부 못 봤으면 변경안이 아니라 「못 풀었다」(escalate)로 끝난다 — 예외가 아니다."""
    from app.modules.travel_ops.activity import team as team_module

    monkeypatch.setattr(team_module, "ACTIVITY_RECHECK_LIMIT", 50)
    monkeypatch.setattr(ActivityTeam.manifest, "max_steps", 4)      # 읽기 셋(일정 · 점검 · 목록) 뒤 후보 점검 한 번이면 끝
    tools, work, places = _setup(candidates=10, verdicts_for=lambda ps: {p["place_id"]: "disrupted" for p in ps[1:]})
    result = await ActivityTeam(tools).execute(work)
    assert len(tools.calls) <= 4
    assert not result.action_proposals                              # 점검을 통과한 곳이 없다 — 고르지 않는다
    assert result.outcome == "escalated" and result.next_action is NextAction.ESCALATE       # 예외가 아니라 「못 풀었다」
    assert any("unresolved" in warning for warning in result.warnings)
