import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.contracts import ContextPack, Evidence, NextAction, TeamResult, TeamTask
from app.core.remote_team.a2a_executor import A2ATeamExecutor
from app.core.remote_team.executor import LocalTeamExecutor, ToolScopeViolation
from app.core.registry import TeamRegistry
from app.presentation.a2a.agent_card import build_agent_card


def make_task() -> TeamTask:
    case_id = uuid4()
    context = ContextPack(pack_id=uuid4(), case_id=case_id, team_id="demo", tenant_id="port-test",
                          knowledge_scope=["test"], current_state={}, estimated_input_tokens=1)
    return TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id="demo", capability="demo.capability",
                    case_version=1, input_text="test", context=context, allowed_tools=[],
                    deadline_at=datetime.now(UTC) + timedelta(seconds=2))


# ★observed_at 을 호출 시각으로 찍으면 안 된다.
#   test_local_executor_is_identical_to_direct_team_call 이 Team 을 **두 번** 실행해
#   model_dump() 를 비교하는데, 두 호출이 클럭 틱을 사이에 두고 갈리면
#   observed_at 만 달라져 실패한다 (2026-08-14: 전체 실행 중 1회 관측, 단독 실행은 통과).
#   그 테스트가 재는 것은 "LocalTeamExecutor 가 통과시키는가" 이지 "시계가 맞는가" 가 아니다.
FIXED_OBSERVED_AT = datetime(2026, 8, 14, 0, 0, 0, tzinfo=UTC)


class Team:
    manifest = type("Manifest", (), {"team_id":"demo", "display_name":"Demo", "capabilities":["demo.capability"],
        "supported_contract_versions":["1.0"], "accepted_case_types":[], "active":True,
        "allowed_tools": ["read.allowed"]})()
    async def execute(self, task):
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id, outcome="completed",
                          answer="ok", confidence=1, evidence=[Evidence(evidence_id="e", source_type="db", source_id="x",
                          claim="x", value={}, confidence=1, observed_at=FIXED_OBSERVED_AT)], next_action=NextAction.RESPOND)


@pytest.mark.asyncio
async def test_local_executor_is_identical_to_direct_team_call():
    task = make_task(); team = Team(); registry = TeamRegistry([team])
    assert (await LocalTeamExecutor(registry).execute(task)).model_dump() == (await team.execute(task)).model_dump()


@pytest.mark.asyncio
async def test_local_executor_rejects_task_tools_outside_manifest():
    task = make_task().model_copy(update={"allowed_tools": ["read.forbidden"]})
    with pytest.raises(ToolScopeViolation, match="read.forbidden"):
        await LocalTeamExecutor(TeamRegistry([Team()])).execute(task)


@pytest.mark.asyncio
async def test_a2a_maps_remote_states_without_exposing_them():
    task = make_task()
    evidence = {"evidence_id":"e", "source_type":"db", "source_id":"x", "claim":"x", "value":{}, "confidence":1, "observed_at":datetime.now(UTC).isoformat()}
    completed = {"status":"completed", "artifact":{"outcome":"completed", "answer":"ok", "confidence":1,
                 "evidence":[evidence], "next_action":"respond"}}
    class Transport:
        def __init__(self, response): self.response = response
        async def submit(self, endpoint, task): return self.response
    for response, outcome, action in [
        ({"status":"input_required", "input_schema":{"type":"object"}}, "waiting", NextAction.WAIT_FOR_INPUT),
        (completed, "completed", NextAction.RESPOND),
        ({"status":"failed", "failure_code":"boom"}, "failed", NextAction.ESCALATE),
    ]:
        result = await A2ATeamExecutor(Transport(response), lambda capability: "endpoint").execute(task)
        assert (result.outcome, result.next_action) == (outcome, action)

    class Running:
        async def submit(self, endpoint, task): return {"status":"running"}
        async def poll(self, remote, task): return {"status":"failed", "failure_code":"done"}
    result = await A2ATeamExecutor(Running(), lambda capability: "endpoint").execute(task)
    assert result.outcome == "failed"


@pytest.mark.asyncio
async def test_a2a_submit_timeout_is_bounded_by_task_deadline():
    task = make_task().model_copy(update={"deadline_at": datetime.now(UTC) + timedelta(milliseconds=30)})

    class HungSubmit:
        async def submit(self, endpoint, task):
            await asyncio.sleep(10)

    started = asyncio.get_running_loop().time()
    result = await A2ATeamExecutor(HungSubmit(), lambda capability: "endpoint").execute(task)

    assert asyncio.get_running_loop().time() - started < 0.5
    assert result.failure_code == "remote_deadline_exceeded"


@pytest.mark.asyncio
async def test_a2a_poll_timeout_is_bounded_and_best_effort_cancels_remote():
    task = make_task().model_copy(update={"deadline_at": datetime.now(UTC) + timedelta(milliseconds=30)})
    cancelled = []

    class HungPoll:
        async def submit(self, endpoint, task):
            return {"status": "running", "task_id": "remote-1"}

        async def poll(self, remote, task):
            await asyncio.sleep(10)

        async def cancel(self, remote):
            cancelled.append(remote["task_id"])

    result = await A2ATeamExecutor(HungPoll(), lambda capability: "endpoint").execute(task)

    assert result.failure_code == "remote_deadline_exceeded"
    assert cancelled == ["remote-1"]


def test_agent_card_reflects_registry_capabilities():
    card = build_agent_card(TeamRegistry([Team()]))
    assert card["capabilities"][0]["capabilities"] == ["demo.capability"]
