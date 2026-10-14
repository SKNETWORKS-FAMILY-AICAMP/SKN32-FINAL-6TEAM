from __future__ import annotations

import asyncio
import inspect
import logging
import math
from datetime import UTC, datetime
from typing import Any

from app.core.contracts import NextAction, TeamResult, TeamTask
from app.core.team_availability import TeamContractViolation, TeamUnavailable
from app.core.remote_team.executor import ToolScopeViolation
from app.core.settings import get_guardrails

logger = logging.getLogger(__name__)


class A2ATeamExecutor:
    """Delegates a TeamTask to an injected A2A transport; no network is owned here."""

    def __init__(self, transport, capability_resolver, *, registry=None, cancel_timeout_seconds=None) -> None:
        self.transport = transport
        self.capability_resolver = capability_resolver
        self.registry = registry
        self.cancel_timeout_seconds = float(
            get_guardrails().get("reliability.a2a_cancel_timeout_seconds")
            if cancel_timeout_seconds is None else cancel_timeout_seconds)
        if not math.isfinite(self.cancel_timeout_seconds) or self.cancel_timeout_seconds <= 0:
            raise ValueError("A2A cancel timeout must be finite and positive")

    async def execute(self, task: TeamTask) -> TeamResult:
        if self.registry is None:
            raise TeamUnavailable(task.team_id, "not_installed")
        entry = self.registry.require_runnable(task.team_id, task.capability)
        if not set(task.allowed_tools) <= set(entry.manifest.allowed_tools):
            raise ToolScopeViolation(f"{task.team_id}: task.allowed_tools is outside the manifest")
        self._transport_method(("submit", "send"))
        self._transport_method(("poll", "get_status"), required=False)
        self._transport_method(("cancel",), required=False)
        # The resolver is captured with this generation's registry. String
        # endpoints remain supported; structured endpoints can assert ownership.
        expired = object()
        endpoint = await self._call_within_deadline(lambda: self._resolve(task), task, timeout_value=expired)
        if endpoint is expired:
            return self._failed(task, "remote_deadline_exceeded")
        if endpoint is None:
            raise TeamUnavailable(task.team_id, "remote_unavailable")
        for field, expected in (("team_id", task.team_id), ("capability", task.capability)):
            actual = endpoint.get(field) if isinstance(endpoint, dict) else getattr(endpoint, field, None)
            if actual is not None and actual != expected:
                raise TeamContractViolation(f"A2A endpoint {field} does not match the task")
        remote = await self._call_within_deadline(lambda: self._submit(endpoint, task), task)
        if remote is None:
            return self._failed(task, "remote_deadline_exceeded")
        while self._status(remote) in {"running", "submitted", "working", "in_progress"}:
            if datetime.now(UTC) >= task.deadline_at:
                await self._cancel_best_effort(remote, task)
                return self._failed(task, "remote_deadline_exceeded")
            next_remote = await self._call_within_deadline(lambda: self._poll(remote, task), task)
            if next_remote is None:
                await self._cancel_best_effort(remote, task)
                return self._failed(task, "remote_deadline_exceeded")
            remote = next_remote
        return self._map(task, remote)

    @staticmethod
    async def _call_within_deadline(make_awaitable, task: TeamTask, *, timeout_value=None):
        remaining = (task.deadline_at - datetime.now(UTC)).total_seconds()
        if remaining <= 0:
            return timeout_value
        try:
            return await asyncio.wait_for(make_awaitable(), timeout=remaining)
        except asyncio.TimeoutError:
            return timeout_value

    async def _cancel_best_effort(self, remote, task: TeamTask) -> bool:
        try:
            cancel = self._transport_method(("cancel",), required=False)
            if cancel is None:
                return False
            await asyncio.wait_for(cancel(remote), timeout=self.cancel_timeout_seconds)
            return True
        except Exception as exc:
            logger.warning("a2a_cancel_failed", extra={
                "error_type": type(exc).__name__, "team_id": task.team_id,
                "task_id": str(task.task_id), "run_id": str(task.run_id),
            })
            return False

    async def _submit(self, endpoint, task):
        return await self._transport_method(("submit", "send"))(endpoint, task)

    async def _resolve(self, task):
        resolver = self.capability_resolver
        if self._is_async_callable(resolver):
            value = await resolver(task.capability)
        else:
            # Only pure lookup is permitted here. Cancellation stops waiting,
            # not the worker thread; no remote submission occurs in that thread.
            worker = asyncio.create_task(asyncio.to_thread(resolver, task.capability))
            try:
                value = await asyncio.shield(worker)
            except asyncio.CancelledError:
                worker.add_done_callback(self._discard_resolution)
                raise
        return await value if inspect.isawaitable(value) else value

    @staticmethod
    def _discard_resolution(worker):
        """Consume a late pure lookup; never execute its returned coroutine."""
        if worker.cancelled():
            return
        try:
            value = worker.result()
        except Exception as exc:
            logger.warning("a2a_late_resolver_failed", extra={"error_type": type(exc).__name__})
            return
        if inspect.iscoroutine(value):
            value.close()
        elif asyncio.isfuture(value):
            value.cancel()

    async def _poll(self, remote, task):
        return await self._transport_method(("poll", "get_status"))(remote, task)

    @staticmethod
    def _is_async_callable(value):
        return inspect.iscoroutinefunction(value) or inspect.iscoroutinefunction(getattr(value, "__call__", None))

    def _transport_method(self, names, *, required=True):
        for name in names:
            method = getattr(self.transport, name, None)
            if method is not None:
                if not callable(method) or not self._is_async_callable(method):
                    raise TeamContractViolation(f"A2A transport {name} must be an async function")
                return method
        if required:
            raise TeamContractViolation(f"A2A transport requires async {names[0]}")
        return None

    @staticmethod
    def _status(remote: Any) -> str:
        value = remote.get("status") if isinstance(remote, dict) else getattr(remote, "status", remote)
        return str(value).lower().replace("-", "_")

    def _map(self, task: TeamTask, remote: Any) -> TeamResult:
        status = self._status(remote)
        failure_code = remote.get("failure_code") if isinstance(remote, dict) else getattr(remote, "failure_code", None)
        if status in {"unavailable", "service_unavailable"} or failure_code == "team_unavailable":
            raise TeamUnavailable(task.team_id, "remote_unavailable")
        data = remote.get("artifact") if isinstance(remote, dict) else getattr(remote, "artifact", None)
        if data is None:
            data = remote.get("result") if isinstance(remote, dict) else getattr(remote, "result", None)
        if data is not None:
            self._validate_result_identity(task, data)
            code = data.get("failure_code") if isinstance(data, dict) else getattr(data, "failure_code", None)
            if code == "team_unavailable":
                raise TeamUnavailable(task.team_id, "remote_unavailable")
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
        if status not in {"completed", "succeeded", "done"}:
            raise TeamContractViolation(f"A2A result has unsupported status: {status}")
        if isinstance(data, TeamResult):
            return data
        if isinstance(data, dict):
            payload = dict(data)
            payload.setdefault("outcome", "completed")
            return TeamResult.model_validate(payload)
        return self._failed(task, "remote_artifact_missing")

    @staticmethod
    def _validate_result_identity(task: TeamTask, result: Any) -> None:
        for field in ("team_id", "task_id", "run_id"):
            value = result.get(field) if isinstance(result, dict) else getattr(result, field, None)
            if value is None or str(value) != str(getattr(task, field)):
                raise TeamContractViolation(f"A2A result {field} does not match the task")

    @staticmethod
    def _failed(task: TeamTask, code: str) -> TeamResult:
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id, outcome="failed",
                          confidence=0.0, next_action=NextAction.ESCALATE, failure_code=code)
