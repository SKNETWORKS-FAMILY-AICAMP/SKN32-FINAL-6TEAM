from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from acop_basement.core.contracts import Evidence, NextAction, TeamResult, TeamTask


class A2ATeamExecutor:
    """Delegates a TeamTask to an injected A2A transport; no network is owned here."""

    def __init__(self, transport, capability_resolver) -> None:
        self.transport = transport
        self.capability_resolver = capability_resolver

    async def execute(self, task: TeamTask) -> TeamResult:
        # ★버그사냥 2026-08-17 — deadline 검사는 루프 안에서만 돌았다. submit()
        #   이 응답하지 않거나 poll() 하나가 hang 하면 그 await 이 끝날 때까지
        #   deadline 을 확인할 기회 자체가 없었다 — 재현: 만료된 deadline +
        #   1초 sleep transport 를 0.05초 wait_for 로 감쌌더니 executor 의 실패
        #   결과보다 외부 TimeoutError 가 먼저 났다. 이제 각 원격 호출을
        #   남은 deadline 으로 직접 감싼다. 포기할 땐 원격도 취소를 시도한다
        #   — 안 그러면 우리는 실패로 기록하는데 원격은 계속 도는 채로 남는다.
        endpoint = self.capability_resolver(task.capability)
        if hasattr(endpoint, "__await__"):
            endpoint = await endpoint
        remote = await self._call_within_deadline(lambda: self._submit(endpoint, task), task)
        if remote is None:
            return self._failed(task, "remote_deadline_exceeded",
                                warnings=["submit 이 deadline 안에 응답하지 않았다"])
        while self._status(remote) in {"running", "submitted", "working", "in_progress"}:
            if datetime.now(UTC) >= task.deadline_at:
                cancelled = await self._cancel_best_effort(remote)
                return self._failed(task, "remote_deadline_exceeded",
                                    warnings=[] if cancelled else ["원격 취소 시도가 실패했다 — 원격이 계속 실행 중일 수 있다"])
            next_remote = await self._call_within_deadline(lambda r=remote: self._poll(r, task), task)
            if next_remote is None:
                cancelled = await self._cancel_best_effort(remote)
                return self._failed(task, "remote_deadline_exceeded",
                                    warnings=[] if cancelled else ["원격 취소 시도가 실패했다 — 원격이 계속 실행 중일 수 있다"])
            remote = next_remote
        return self._map(task, remote)

    @staticmethod
    async def _call_within_deadline(make_awaitable, task: TeamTask):
        """남은 deadline 으로 개별 원격 호출을 직접 감싼다. 이미 지났거나
        시간 안에 안 끝나면 `None` — 예외를 밖으로 흘리지 않는다.

        ★`make_awaitable` 은 코루틴이 아니라 **코루틴을 만드는 0-인자 콜러블**이다
        — 미리 만든 코루틴을 넘기면 deadline 이 이미 지나 그냥 버릴 때
        "코루틴이 await 되지 않았다" 경고가 난다(실측: 2026-08-17). 실제로
        await 할 때만 만든다."""
        remaining = (task.deadline_at - datetime.now(UTC)).total_seconds()
        if remaining <= 0:
            return None
        try:
            return await asyncio.wait_for(make_awaitable(), timeout=remaining)
        except asyncio.TimeoutError:
            return None

    async def _cancel_best_effort(self, remote) -> bool:
        """★취소가 없는 transport(테스트 더블 등)도 있다 — 있으면 시도하고,
        실패해도 우리 쪽 실패 처리는 그대로 진행한다(취소 실패로 결과 자체를
        막지 않는다). 실패했다는 사실은 호출부가 warnings 로 남긴다."""
        cancel = getattr(self.transport, "cancel", None)
        if cancel is None:
            return False
        try:
            await cancel(remote)
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
    def _failed(task: TeamTask, code: str, *, warnings: list[str] | None = None) -> TeamResult:
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id, outcome="failed",
                          confidence=0.0, next_action=NextAction.ESCALATE, failure_code=code,
                          warnings=warnings or [])
