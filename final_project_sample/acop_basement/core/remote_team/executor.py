from __future__ import annotations

from typing import Protocol

from acop_basement.core.contracts import TeamResult, TeamTask


class TeamExecutorPort(Protocol):
    async def execute(self, task: TeamTask) -> TeamResult: ...


class ToolScopeViolation(ValueError):
    """`task.allowed_tools` 가 등록된 manifest 의 목록을 벗어난다."""


class LocalTeamExecutor:
    """Adapter preserving the existing in-process TeamModule behaviour."""

    def __init__(self, registry) -> None:
        self.registry = registry

    async def execute(self, task: TeamTask) -> TeamResult:
        entry = self.registry.get(task.team_id)
        # ★버그사냥 2026-08-17 — Team 모듈은 `task.allowed_tools` 를 그대로
        #   신뢰해서 toolbox 에 넘긴다(app/modules/customer_ops/*.py). 지금
        #   유일한 프로덕션 경로(Controller)는 항상 manifest 에서 이 값을
        #   채우므로 오늘은 뚫리지 않는다 — 그런데 이 경계에 강제가 없었다.
        #   "Registry 가 거부한다"(CLAUDE.md §2)는 문장을 실제로 만든다:
        #   task 가 manifest 밖의 tool 을 주장하면 여기서 막는다.
        allowed = set(entry.manifest.allowed_tools)
        claimed = set(task.allowed_tools)
        if not claimed <= allowed:
            raise ToolScopeViolation(
                f"{task.team_id}: task.allowed_tools 가 manifest 밖이다 — "
                f"{sorted(claimed - allowed)}")
        return await entry.module.execute(task)
