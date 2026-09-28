"""A2A 실제 왕복 (v7 DoD-26·27).

★지금까지의 A2A 검증은 **고정 dict 를 돌려주는 더미 Transport** 였다.
  "상태 매핑이 맞다" 와 "원격과 주고받는다" 는 다른 주장이다.

여기서는 실제 원격 앱(`create_remote_agent`)에 **HTTP 로** 말한다:
  Card 발견 → submit → working → input-required → 추가 입력 → Artifact 완료

★한계는 정직하게: `httpx.ASGITransport` 로 in-process 에 붙인다.
  프로세스 경계는 넘지 않지만 **상태코드·헤더·직렬화는 실제로 탄다.**
  네트워크 단절·부분 응답은 여기서 재현되지 않는다.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from acop_basement.core.contracts import ContextPack, NextAction, TeamTask
from acop_basement.core.remote_team.a2a_executor import A2ATeamExecutor
from acop_basement.infrastructure.a2a.http_transport import A2AHttpTransport
from acop_basement.presentation.a2a.remote_agent import REMOTE_TOKEN, create_remote_agent

BASE = "http://remote.test"


def make_task(*, seconds: int = 30) -> TeamTask:
    case_id = uuid4()
    context = ContextPack(pack_id=uuid4(), case_id=case_id, team_id="catalog_verification",
                          tenant_id="a2a-test", knowledge_scope=["catalog"],
                          current_state={}, estimated_input_tokens=1)
    return TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=case_id,
                    team_id="catalog_verification", capability="order.verify",
                    case_version=1, input_text="주문을 확인해 주세요", context=context,
                    allowed_tools=[], deadline_at=datetime.now(UTC) + timedelta(seconds=seconds))


def client_for(app, token: str | None = REMOTE_TOKEN) -> tuple[httpx.AsyncClient, A2AHttpTransport]:
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE)
    return client, A2AHttpTransport(client, token=token)


# ── DoD-26 왕복 ──────────────────────────────────────────────────────────────
def test_agent_card_is_discovered_not_assumed():
    """★Card 를 **가져온다.** 만들어 두는 것과 가져오는 것은 다르다."""
    async def run():
        client, transport = client_for(create_remote_agent())
        async with client:
            return await transport.discover()

    card = asyncio.run(run())
    assert card["name"] == "Catalog & Verification Remote Team"
    caps = {c for entry in card["capabilities"] for c in entry["capabilities"]}
    assert {"catalog.lookup", "order.verify"} <= caps
    assert card["authentication"]["scheme"] == "bearer"


def test_full_round_trip_working_input_required_then_artifact():
    """★v7 DoD-26 이 지정한 왕복 전 단계."""
    async def run():
        app = create_remote_agent()
        client, transport = client_for(app)
        async with client:
            card = await transport.discover()
            assert "order.verify" in {c for e in card["capabilities"] for c in e["capabilities"]}

            task = make_task()
            executor = A2ATeamExecutor(transport, lambda capability: "/a2a/tasks")

            # 1) submit → working, 폴링하면 input-required 로 넘어간다
            first = await executor.execute(task)
            assert first.next_action is NextAction.WAIT_FOR_INPUT, first
            assert first.required_input_schema["required"] == ["order_id"]

            # 2) ★추가 입력을 실제로 보내 원격을 재개시킨다
            remote = list(app.state.tasks.values())[0]
            assert remote["status"] == "input-required"
            resumed = await transport.provide_input(remote, {"order_id": "ORD-42"})
            assert resumed["status"] == "completed"

            # 3) Artifact 가 TeamResult 로 정규화된다
            done = executor._map(task, resumed)
            return done

    result = asyncio.run(run())
    assert result.outcome == "completed"
    assert result.next_action is NextAction.RESPOND
    assert "ORD-42" in result.answer
    assert result.evidence[0].source_type == "remote_agent"


def test_missing_input_is_rejected_by_the_remote():
    """원격이 스키마를 강제한다 — 우리가 아무거나 보내면 안 된다."""
    async def run():
        app = create_remote_agent()
        client, transport = client_for(app)
        async with client:
            task = make_task()
            executor = A2ATeamExecutor(transport, lambda c: "/a2a/tasks")
            await executor.execute(task)
            remote = list(app.state.tasks.values())[0]
            with pytest.raises(httpx.HTTPStatusError) as exc:
                await transport.provide_input(remote, {})
            return exc.value.response.status_code

    assert asyncio.run(run()) == 422


# ── DoD-27 실패·타임아웃·취소·인증 ─────────────────────────────────────────────
def test_remote_failure_becomes_escalate():
    async def run():
        client, transport = client_for(create_remote_agent(behavior="fail_immediately"))
        async with client:
            executor = A2ATeamExecutor(transport, lambda c: "/a2a/tasks")
            return await executor.execute(make_task())

    result = asyncio.run(run())
    assert result.outcome == "failed"
    assert result.next_action is NextAction.ESCALATE
    assert result.failure_code == "catalog_unavailable"


def test_remote_that_never_finishes_hits_the_deadline():
    """★끝나지 않는 원격에서 **우리 쪽 deadline** 이 동작한다."""
    async def run():
        client, transport = client_for(create_remote_agent(behavior="never_finishes"))
        async with client:
            executor = A2ATeamExecutor(transport, lambda c: "/a2a/tasks")
            # 이미 지난 deadline → 첫 폴링에서 걸린다
            return await executor.execute(make_task(seconds=-1))

    result = asyncio.run(run())
    assert result.outcome == "failed"
    assert result.failure_code == "remote_deadline_exceeded"


def test_cancel_is_recorded_and_is_not_a_failure():
    """★취소는 실패와 다른 사건이다 (v7 DoD-27).

    전에는 둘을 `remote_task_failed` 로 뭉갰다 — **누가 멈췄는지**가 사라졌다.
    """
    async def run():
        app = create_remote_agent(behavior="never_finishes")
        client, transport = client_for(app)
        async with client:
            task = make_task()
            remote = await transport.submit("/a2a/tasks", task)
            cancelled = await transport.cancel(remote)
            assert cancelled["status"] == "cancelled"
            executor = A2ATeamExecutor(transport, lambda c: "/a2a/tasks")
            return executor._map(task, cancelled)

    result = asyncio.run(run())
    assert result.failure_code == "cancelled_by_caller"
    assert result.failure_code != "remote_task_failed"
    assert any("취소" in w for w in result.warnings)


def test_finished_task_cannot_be_cancelled():
    async def run():
        app = create_remote_agent(behavior="complete_immediately")
        client, transport = client_for(app)
        async with client:
            remote = await transport.submit("/a2a/tasks", make_task())
            with pytest.raises(httpx.HTTPStatusError) as exc:
                await transport.cancel(remote)
            return exc.value.response.status_code

    assert asyncio.run(run()) == 409


def test_missing_credential_is_rejected():
    """★인증 — 자격 없이 부르면 원격이 거부한다."""
    async def run():
        client, transport = client_for(create_remote_agent(), token=None)
        async with client:
            executor = A2ATeamExecutor(transport, lambda c: "/a2a/tasks")
            return await executor.execute(make_task())

    result = asyncio.run(run())
    assert result.outcome == "failed"
    assert result.failure_code == "remote_unauthorized"


def test_wrong_credential_is_rejected():
    async def run():
        client, transport = client_for(create_remote_agent(), token="not-the-token")
        async with client:
            executor = A2ATeamExecutor(transport, lambda c: "/a2a/tasks")
            return await executor.execute(make_task())

    assert asyncio.run(run()).failure_code == "remote_unauthorized"


def test_agent_card_is_public_but_tasks_are_not():
    """Card 는 열려 있고 Task 는 잠겨 있다."""
    async def run():
        client, transport = client_for(create_remote_agent(), token=None)
        async with client:
            card = await transport.discover()          # 인증 없이 성공
            submitted = await transport.submit("/a2a/tasks", make_task())
            return card, submitted

    card, submitted = asyncio.run(run())
    assert card["name"]
    assert submitted["failure_code"] == "remote_unauthorized"
