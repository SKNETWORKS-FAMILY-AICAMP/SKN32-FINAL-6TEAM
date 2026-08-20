import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from acop_basement.core.contracts import ContextPack, Evidence, NextAction, TeamResult, TeamTask
from acop_basement.core.remote_team.a2a_executor import A2ATeamExecutor
from acop_basement.core.remote_team.executor import LocalTeamExecutor, ToolScopeViolation
from acop_basement.core.registry import TeamRegistry
from acop_basement.presentation.a2a.agent_card import build_agent_card


def make_task(*, allowed_tools: list[str] | None = None) -> TeamTask:
    case_id = uuid4()
    context = ContextPack(pack_id=uuid4(), case_id=case_id, team_id="demo", tenant_id="port-test",
                          knowledge_scope=["test"], current_state={}, estimated_input_tokens=1)
    return TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id="demo", capability="demo.capability",
                    case_version=1, input_text="test", context=context, allowed_tools=allowed_tools or [],
                    deadline_at=datetime.now(UTC) + timedelta(seconds=2))


# ★observed_at 을 호출 시각으로 찍으면 안 된다.
#   test_local_executor_is_identical_to_direct_team_call 이 Team 을 **두 번** 실행해
#   model_dump() 를 비교하는데, 두 호출이 클럭 틱을 사이에 두고 갈리면
#   observed_at 만 달라져 실패한다 (2026-08-14: 전체 실행 중 1회 관측, 단독 실행은 통과).
#   그 테스트가 재는 것은 "LocalTeamExecutor 가 통과시키는가" 이지 "시계가 맞는가" 가 아니다.
FIXED_OBSERVED_AT = datetime(2026, 8, 14, 0, 0, 0, tzinfo=UTC)


class Team:
    manifest = type("Manifest", (), {"team_id":"demo", "display_name":"Demo", "capabilities":["demo.capability"],
        "supported_contract_versions":["1.0"], "accepted_case_types":[], "active":True, "allowed_tools":[]})()
    async def execute(self, task):
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id, outcome="completed",
                          answer="ok", confidence=1, evidence=[Evidence(evidence_id="e", source_type="db", source_id="x",
                          claim="x", value={}, confidence=1, observed_at=FIXED_OBSERVED_AT)], next_action=NextAction.RESPOND)


@pytest.mark.asyncio
async def test_local_executor_is_identical_to_direct_team_call():
    task = make_task(); team = Team(); registry = TeamRegistry([team])
    assert (await LocalTeamExecutor(registry).execute(task)).model_dump() == (await team.execute(task)).model_dump()


@pytest.mark.asyncio
async def test_local_executor_rejects_a_task_claiming_tools_outside_the_manifest():
    """★버그사냥 2026-08-17 — Team 모듈(app/modules/customer_ops/*.py)은
    `task.allowed_tools` 를 그대로 신뢰해서 toolbox 에 넘긴다. 지금 유일한
    프로덕션 경로(Controller)는 항상 manifest 에서 이 값을 채우므로 오늘은
    안 뚫리지만, 이 경계 자체엔 강제가 없었다. "Registry 가 거부한다"
    (CLAUDE.md §2)를 실제로 만든다."""
    task = make_task(allowed_tools=["read.payment_history", "read.entitlement"])  # demo manifest 는 [] 만 허용
    registry = TeamRegistry([Team()])
    with pytest.raises(ToolScopeViolation, match="read.payment_history"):
        await LocalTeamExecutor(registry).execute(task)


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
async def test_hanging_poll_past_deadline_fails_promptly_and_cancels_remote():
    """★버그사냥 2026-08-17 — deadline 검사는 루프 안에서만 돌았다. poll() 하나가
    hang 하면 그 await 이 끝날 때까지 deadline 을 확인할 기회가 없었다. 이제 poll
    은 남은 deadline 으로 직접 감싸고, 포기하면 원격 취소를 시도한다.
    """
    task = make_task()  # deadline_at = now + 2s

    class HangingPollTransport:
        def __init__(self):
            self.cancel_calls: list = []

        async def submit(self, endpoint, task):
            return {"status": "running", "task_id": "remote-1"}

        async def poll(self, remote, task):
            await asyncio.sleep(10)  # ★deadline(2s) 보다 훨씬 오래 hang 한다
            return {"status": "running"}

        async def cancel(self, remote):
            self.cancel_calls.append(remote)
            return {"status": "cancelled"}

    transport = HangingPollTransport()
    executor = A2ATeamExecutor(transport, lambda capability: "endpoint")

    # ★전체 실행이 deadline(2s) 을 크게 넘기지 않고 끝나야 한다 — poll 의
    #   10초 sleep 을 그대로 기다리면 여기서 TimeoutError 로 터진다.
    result = await asyncio.wait_for(executor.execute(task), timeout=3.5)

    assert result.outcome == "failed"
    assert result.failure_code == "remote_deadline_exceeded"
    # ★원격에 취소를 실제로 시도했다 — 그냥 우리 쪽만 포기하고 끝내지 않았다.
    assert transport.cancel_calls == [{"status": "running", "task_id": "remote-1"}]


@pytest.mark.asyncio
async def test_hanging_submit_past_deadline_fails_without_leaking_a_warning():
    """★submit() 자체가 hang 해도 같은 방식으로 잡혀야 한다."""
    task = make_task()

    class HangingSubmitTransport:
        async def submit(self, endpoint, task):
            await asyncio.sleep(10)
            return {"status": "running"}

    executor = A2ATeamExecutor(HangingSubmitTransport(), lambda capability: "endpoint")
    result = await asyncio.wait_for(executor.execute(task), timeout=3.5)

    assert result.outcome == "failed"
    assert result.failure_code == "remote_deadline_exceeded"
    assert any("submit" in w for w in result.warnings)


def test_agent_card_reflects_registry_capabilities():
    card = build_agent_card(TeamRegistry([Team()]))
    assert card["capabilities"][0]["capabilities"] == ["demo.capability"]
