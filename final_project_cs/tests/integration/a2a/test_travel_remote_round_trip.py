"""여행 A2A 실제 왕복 — Place Verification 원격 팀.

★**왜 이 시험이 필요한가.** 2026-09-09 에 등록을 여행으로 갈아끼우면서
  `catalog_verification` 이 미등록이 됐고, A2A 로 부를 대상이 없어졌다.
  엔드포인트 다섯은 남아 있는데 **상대가 없는 상태**였다 —
  "구현이 있다"와 "돈다"는 다르다.

여기서 실제 원격 앱(`create_travel_remote_agent`)에 **HTTP 로** 말한다.

  Card 발견 → submit → working → input-required → 추가 입력 → Artifact 완료

★한계는 정직하게 적는다. `httpx.ASGITransport` 로 in-process 에 붙이므로
  프로세스 경계는 넘지 않는다. **상태코드·헤더·직렬화는 실제로 탄다.**
  네트워크 단절·부분 응답은 여기서 재현되지 않는다.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from app.core.contracts import ContextPack, NextAction, TeamTask
from app.core.remote_team.a2a_executor import A2ATeamExecutor
from app.infrastructure.a2a.http_transport import A2AHttpTransport
from app.presentation.a2a.travel_remote_agent import (
    CARD,
    REMOTE_TOKEN,
    create_travel_remote_agent,
)

BASE = "http://place-remote.test"
TEAM = "place_verification"


def make_task(*, capability: str = "place.verify_hours", seconds: int = 30) -> TeamTask:
    case_id = uuid4()
    context = ContextPack(pack_id=uuid4(), case_id=case_id, team_id=TEAM,
                          tenant_id="a2a-travel-test", knowledge_scope=["place"],
                          current_state={}, estimated_input_tokens=1)
    return TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=case_id,
                    team_id=TEAM, capability=capability, case_version=1,
                    input_text="경복궁이 그 시각에 여는지 확인해 주세요",
                    context=context, allowed_tools=[],
                    deadline_at=datetime.now(UTC) + timedelta(seconds=seconds))


def client(app, *, token: str | None = REMOTE_TOKEN) -> tuple[httpx.AsyncClient, A2AHttpTransport]:
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE)
    return http, A2AHttpTransport(http, token=token)


@pytest.mark.asyncio
async def test_agent_card_advertises_place_verification():
    """★Card 를 **가져온다.** 만들어 두는 것과 가져오는 것은 다르다."""
    http, transport = client(create_travel_remote_agent())
    async with http:
        card = await transport.discover()
    assert card["capabilities"][0]["team_id"] == TEAM
    assert "place.verify_hours" in card["capabilities"][0]["capabilities"]
    assert card == CARD


@pytest.mark.asyncio
async def test_round_trip_reaches_input_required_then_completes():
    """Card 발견 → submit → input-required → 추가 입력 → Artifact 완료."""
    app = create_travel_remote_agent()
    http, transport = client(app)
    executor = A2ATeamExecutor(transport, lambda _c: "/a2a/tasks")
    task = make_task()

    async with http:
        result = await executor.execute(task)
        # ① executor 는 추가 입력을 요구하며 멈춘다 — 값을 지어내지 않는다
        assert result.next_action is NextAction.WAIT_FOR_INPUT
        assert result.outcome == "waiting"
        assert "place_id" in result.required_input_schema["required"]

        # ② 사람(또는 상위 흐름)이 값을 채워 재개한다
        task_id = next(iter(app.state.tasks))
        response = await http.post(f"/a2a/tasks/{task_id}/input",
                                   headers={"Authorization": f"Bearer {REMOTE_TOKEN}"},
                                   json={"place_id": "PLACE-1395", "visit_at": "2026-10-02T10:00:00+09:00"})
        assert response.status_code == 200
        artifact = response.json()["artifact"]

    assert artifact["outcome"] == "completed"
    assert artifact["next_action"] == "respond"
    # ★근거가 붙어야 한다. 원격이라고 근거 의무가 면제되지 않는다
    assert artifact["evidence"], "원격 Artifact 에 근거가 없다"
    evidence = artifact["evidence"][0]
    assert evidence["source_type"] == "remote_agent"
    assert evidence["observed_at"], "확인 시각이 없다"
    assert "현장 관찰이 아니다" in evidence["claim"]


@pytest.mark.asyncio
async def test_missing_place_id_is_rejected():
    """★식별자 없이 「확인했다」고 말하지 않는다. 422 로 거절한다."""
    app = create_travel_remote_agent()
    http, transport = client(app)
    executor = A2ATeamExecutor(transport, lambda _c: "/a2a/tasks")

    async with http:
        await executor.execute(make_task())
        task_id = next(iter(app.state.tasks))
        response = await http.post(f"/a2a/tasks/{task_id}/input",
                                   headers={"Authorization": f"Bearer {REMOTE_TOKEN}"}, json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_wrong_token_is_unauthorized():
    """★원격별 인증이 실제로 걸린다. 커머스 토큰으로는 안 열린다."""
    http, transport = client(create_travel_remote_agent(), token="remote-catalog-token")
    executor = A2ATeamExecutor(transport, lambda _c: "/a2a/tasks")
    async with http:
        result = await executor.execute(make_task())
    assert result.outcome == "failed"
    assert result.failure_code == "remote_unauthorized"


@pytest.mark.asyncio
async def test_remote_failure_maps_to_escalate():
    """원격이 못 하면 실패로 매핑되고 사람에게 넘어간다."""
    http, transport = client(create_travel_remote_agent(behavior="fail_immediately"))
    executor = A2ATeamExecutor(transport, lambda _c: "/a2a/tasks")
    async with http:
        result = await executor.execute(make_task())
    assert result.outcome == "failed"
    assert result.failure_code == "place_registry_unavailable"
    assert result.next_action is NextAction.ESCALATE


@pytest.mark.asyncio
async def test_deadline_stops_a_never_finishing_remote():
    """★원격이 안 끝나도 우리가 멈춘다. deadline 이 실제로 도는지 본다."""
    http, transport = client(create_travel_remote_agent(behavior="never_finishes"))
    executor = A2ATeamExecutor(transport, lambda _c: "/a2a/tasks")
    async with http:
        result = await executor.execute(make_task(seconds=1))
    assert result.outcome == "failed"
    assert result.failure_code == "remote_deadline_exceeded"


@pytest.mark.asyncio
async def test_cancel_is_recorded_apart_from_failure():
    """★취소는 실패가 아니다. 누가 멈췄는지가 남아야 한다."""
    app = create_travel_remote_agent()
    http, transport = client(app)
    executor = A2ATeamExecutor(transport, lambda _c: "/a2a/tasks")

    async with http:
        await executor.execute(make_task())
        task_id = next(iter(app.state.tasks))
        response = await http.post(f"/a2a/tasks/{task_id}/cancel",
                                   headers={"Authorization": f"Bearer {REMOTE_TOKEN}"})
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["failure_code"] == "cancelled_by_caller"
