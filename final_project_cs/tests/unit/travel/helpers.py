# -*- coding: utf-8 -*-
"""여행 Team 테스트용 최소 부품.

★`legacy/.../test_team_scenarios.py` 의 `FakeTools` 를 쓰지 않는다. 그쪽은
  `call(..., seen)` 까지만 받아 **`budget=` 을 못 받는다** — 여행 Team 은
  `TravelTeamBase._read()` 가 항상 예산을 넘기므로 그대로 쓰면 TypeError 다.
  여기 것은 예산을 받고 **실제로 강제한다.**
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.core.contracts import ContextPack, TeamTask, ToolNotAllowed
from app.tools.read_tools import ToolBudgetExceeded, ToolLoopExceeded

NOW = datetime.now(UTC)


def pack(team_id: str, *, degraded: bool = False, scope: list[str] | None = None,
         state: dict[str, Any] | None = None) -> ContextPack:
    return ContextPack(
        pack_id=uuid4(), case_id=uuid4(), team_id=team_id,
        tenant_id="travel-test-tenant", knowledge_scope=scope or [team_id],
        current_state={"customer_id": str(uuid4()), "status": "running",
                       **(state or {})},
        estimated_input_tokens=10, degraded=degraded,
        omissions=["fixture"] if degraded else [])


def task(team_id: str, capability: str, context: ContextPack,
         allowed: list[str], *, input_text: str = "고객 요청") -> TeamTask:
    return TeamTask(
        task_id=uuid4(), run_id=uuid4(), case_id=context.case_id, team_id=team_id,
        capability=capability, case_version=1, input_text=input_text,
        context=context, allowed_tools=allowed,
        deadline_at=NOW + timedelta(seconds=90))


class FakeTools:
    """이름 → 값. ★권한·중복·예산을 실제 `ReadToolbox` 와 같은 순서로 본다."""

    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, name, context, arguments, allowed_tools, seen, budget=None):
        if name not in allowed_tools:
            raise ToolNotAllowed(name)
        signature = name + ":" + repr(sorted(arguments.items()))
        if signature in seen:
            raise ToolLoopExceeded(name)
        if budget is not None and len(seen) >= budget:
            raise ToolBudgetExceeded(f"budget {budget} exhausted before {name}")
        seen.add(signature)
        self.calls.append((name, dict(arguments)))
        return self.values.get(name)


def in_hours(hours: float) -> datetime:
    return datetime.now(UTC) + timedelta(hours=hours)
