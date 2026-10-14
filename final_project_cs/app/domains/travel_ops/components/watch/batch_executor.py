"""로컬 TeamExecutorPort에 붙이는 여행 묶음 실행기. 새 에이전트 팀이 아니다."""
from __future__ import annotations

from typing import Any

from app.core.remote_team.executor import LocalTeamExecutor, ToolScopeViolation
from app.domains.travel_ops.components.itinerary.itinerary import item_from_dict
from app.domains.travel_ops.components.watch.trip_watch_batch import WatchBatch


class TravelBatchExecutor(LocalTeamExecutor):
    def __init__(self, registry: Any, *, planner=None, diagnostic_recorder=None) -> None:
        super().__init__(registry)
        self.planner = planner
        self.diagnostic_recorder = diagnostic_recorder

    async def execute(self, task):
        state = task.context.current_state
        if state.get("trigger_source") != "schedule" or not (state.get("trigger") or {}).get("batch"):
            return await super().execute(task)
        entry = self.registry.require_runnable(task.team_id, task.capability)
        if not set(task.allowed_tools) <= set(entry.manifest.allowed_tools):
            raise ToolScopeViolation("batch envelope tool scope exceeds manifest")
        work = entry.module
        blocked = work._guard(task)
        if blocked is not None:
            return blocked
        ref = state.get("subject_ref") or {}
        seen: set[str] = set()
        view = work._read(task, "read.itinerary", {"trip_id": ref.get("id")}, seen)
        evidence = work._evidence(task, source_id="read.itinerary", claim="현재 일정 버전", value=view)
        if view is None:
            return work._escalate(task, "fatal_source_failure", evidence,
                warnings=[f"retry:{e['item_id']}" for e in state['trigger']['batch']])
        if (str(view["trip"].get("trip_id")) != str(ref.get("id"))
                or ("customer_id" in view["trip"]
                    and str(view["trip"]["customer_id"]) != str(state.get("customer_id")))):
            return work._escalate(task, "action_target_changed", evidence)
        # read.itinerary는 ToolContext 고객 소유권을 확인하고 고객 id를 생략하는 포트다.
        ctx = {"seen": seen, "evidence": evidence,
               "trip": {**view["trip"], "customer_id": state.get("customer_id")},
               "items": [item_from_dict(i) for i in view["items"]], "ref": ref,
               "request": {}, "at": work._moment((state.get("trigger") or {}).get("at"))}
        return WatchBatch(work, task, ctx, registry=self.registry, planner=self.planner,
                          diagnostic_recorder=self.diagnostic_recorder).run()
