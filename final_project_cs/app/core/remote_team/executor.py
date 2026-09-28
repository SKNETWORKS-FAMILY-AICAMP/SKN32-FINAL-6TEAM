from __future__ import annotations

from typing import Protocol

from app.core.contracts import TeamResult, TeamTask


class TeamExecutorPort(Protocol):
    async def execute(self, task: TeamTask) -> TeamResult: ...


class ToolScopeViolation(ValueError):
    """`task.allowed_tools`가 등록된 Team manifest의 scope를 벗어난다."""


class LocalTeamExecutor:
    """Adapter preserving the existing in-process TeamModule behaviour."""

    def __init__(self, registry) -> None:
        self.registry = registry

    async def execute(self, task: TeamTask) -> TeamResult:
        entry = self.registry.get(task.team_id)
        manifest_tools = set(getattr(entry.manifest, "allowed_tools", []))
        claimed_tools = set(task.allowed_tools)
        if not claimed_tools <= manifest_tools:
            raise ToolScopeViolation(
                f"{task.team_id}: task.allowed_tools가 manifest 밖이다 — "
                f"{sorted(claimed_tools - manifest_tools)}"
            )
        return await entry.module.execute(task)
