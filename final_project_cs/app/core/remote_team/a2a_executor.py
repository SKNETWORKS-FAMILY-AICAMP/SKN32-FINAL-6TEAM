from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from app.core.contracts import Evidence, NextAction, TeamResult, TeamTask


class A2ATeamExecutor:
    """Delegates a TeamTask to an injected A2A transport; no network is owned here."""

    def __init__(self, transport, capability_resolver) -> None:
        self.transport = transport
        self.capability_resolver = capability_resolver

    async def execute(self, task: TeamTask) -> TeamResult:
        endpoint = self.capability_resolver(task.capability)
        if hasattr(endpoint, "__await__"):
            endpoint = await endpoint
        remote = await self._call_within_deadline(lambda: self._submit(endpoint, task), task)
        if remote is None:
            return self._failed(task, "remote_deadline_exceeded")
        while self._status(remote) in {"running", "submitted", "working", "in_progress"}:
            if datetime.now(UTC) >= task.deadline_at:
                await self._cancel_best_effort(remote)
                return self._failed(task, "remote_deadline_exceeded")
            next_remote = await self._call_within_deadline(lambda: self._poll(remote, task), task)
            if next_remote is None:
                await self._cancel_best_effort(remote)
                return self._failed(task, "remote_deadline_exceeded")
            remote = next_remote
        return self._map(task, remote)

    @staticmethod
    async def _call_within_deadline(make_awaitable, task: TeamTask):
        remaining = (task.deadline_at - datetime.now(UTC)).total_seconds()
        if remaining <= 0:
            return None
        try:
            return await asyncio.wait_for(make_awaitable(), timeout=remaining)
        except asyncio.TimeoutError:
            return None

    async def _cancel_best_effort(self, remote) -> bool:
        cancel = getattr(self.transport, "cancel", None)
        if cancel is None:
            return False
        try:
            value = cancel(remote)
            if hasattr(value, "__await__"):
                await value
            return True
        except Exception:
            return False

    async def _submit(self, endpoint, task):
        method = getattr(self.transport, "submit", None) or getattr(self.transport, "send")
        value = method(endpoint, task)
        return await value if hasattr(value, "__await__") else value

    async def _poll(self, remote, task):
        method = getattr(self.transport, "poll", None) or getattr(self.transport, "get_status")
        value = method(remote, task)
        if hasattr(value, "__await__"):
            return await value
        await asyncio.sleep(0)
        return value

    @staticmethod
    def _status(remote: Any) -> str:
        value = remote.get("status") if isinstance(remote, dict) else getattr(remote, "status", remote)
        return str(value).lower().replace("-", "_")

    def _map(self, task: TeamTask, remote: Any) -> TeamResult:
        status = self._status(remote)
        data = remote.get("artifact") if isinstance(remote, dict) else getattr(remote, "artifact", None)
        if data is None:
            data = remote.get("result") if isinstance(remote, dict) else getattr(remote, "result", None)
        if status in {"input_required", "input_needed", "requires_input", "waiting_for_input"}:
            schema = (remote.get("input_schema") if isinstance(remote, dict) else getattr(remote, "input_schema", None)) or {}
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id, outcome="waiting",
                              confidence=0.0, next_action=NextAction.WAIT_FOR_INPUT, wait_reason="customer_input",
                              required_input_schema=schema)
        # ★취소는 실패가 아니다 (v7 DoD-27). 전에는 둘을 같이 묶어
        #   `remote_task_failed` 로 뭉갰다 — **누가 멈췄는지**가 사라진다.
        #   실패는 원격이 못 한 것이고, 취소는 우리가 그만둔 것이다.
        # ★`outcome` 에 "cancelled" 를 넣지 않는다 — 계약 Literal 을 늘리면
        #   전이표·리듀서·저장까지 파급된다. 대신 **원인을 failure_code 로 보존**한다.
        #   v7 이 요구하는 것은 "취소로 **기록**되는가" 이지 새 outcome 값이 아니다.
        if status in {"cancelled", "canceled"}:
            code = (remote.get("failure_code") if isinstance(remote, dict) else getattr(remote, "failure_code", None)) or "cancelled_by_caller"
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id,
                              outcome="escalated", confidence=0.0,
                              next_action=NextAction.ESCALATE, failure_code=code,
                              warnings=["원격 Task 가 취소됐다 — 실패와 구분해서 읽어야 한다"])
        if status in {"failed", "error"}:
            code = (remote.get("failure_code") if isinstance(remote, dict) else getattr(remote, "failure_code", None)) or "remote_task_failed"
            return self._failed(task, code)
        if isinstance(data, TeamResult):
            return data
        if isinstance(data, dict):
            payload = dict(data)
            payload.setdefault("task_id", task.task_id)
            payload.setdefault("run_id", task.run_id)
            payload.setdefault("team_id", task.team_id)
            payload.setdefault("outcome", "completed")
            return TeamResult.model_validate(payload)
        return self._failed(task, "remote_artifact_missing")

    @staticmethod
    def _failed(task: TeamTask, code: str) -> TeamResult:
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id, outcome="failed",
                          confidence=0.0, next_action=NextAction.ESCALATE, failure_code=code)
