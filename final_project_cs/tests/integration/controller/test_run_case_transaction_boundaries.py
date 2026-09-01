"""`run_case()` 가 Team 을 부르는 동안 트랜잭션을 열어 두지 않는다는 것을 실측한다.

★"트랜잭션을 좁혔다" 는 주장은 코드를 읽어서 판정하지 않는다.
  **다른 커넥션이 그 시간 동안 같은 Case 를 실제로 쓸 수 있는가**,
  **Team 이 터져도 실행 시작 기록이 남는가** 로 판정한다.

  이 프로젝트에서 "코드는 있는데 안 불린다" 로 여러 번 당했다. 경계 변경은
  그보다 더 조용히 되돌아간다 — 누가 `with conn.transaction():` 하나를
  바깥으로 옮기면 끝이다. 그래서 결과가 아니라 **경계 자체**를 잰다.

근거: docs/reports/2026-09-01_S-RUNCASE-TX-NARROWING_리포트.md
"""
from __future__ import annotations

import asyncio

import pytest

from app.application.controller import Controller
from app.core.registry import TeamRegistry
from app.core.transition import transition_case
from app.domain.events import EventType
from app.infrastructure.db.repository import get_case_events
from app.infrastructure.db.session import get_connection

from .test_controller_integration import (db, seed_case, fake_policy,  # noqa: F401
                                          FakeContextBroker, FakeTeam)


class ExplodingTeam(FakeTeam):
    """★Team 실행이 실패하는 경우. LLM provider 예외가 이 모양으로 올라온다."""

    async def execute(self, task):
        raise RuntimeError("team blew up")


class ConcurrentWriterTeam(FakeTeam):
    """Team 이 도는 동안 **다른 커넥션**이 같은 Case 를 escalate 한다.

    운영에서 이 자리에 오는 것은 운영자 개입·가드레일 배치·`resume()` 이다.
    여기서는 그중 하나를 고정값으로 재현한다.
    """

    def __init__(self) -> None:
        super().__init__()
        self.write_error: BaseException | None = None

    async def execute(self, task):
        try:
            with get_connection() as writer:
                with writer.cursor() as cur:
                    # ★막히면 매달리지 않고 곧바로 실패한다. 트랜잭션을 다시 넓히는
                    #   회귀가 나면 이 테스트는 무한 대기가 아니라 lock timeout 으로
                    #   떨어져야 한다 — 매달리는 테스트는 원인을 알려주지 않는다.
                    cur.execute("SET lock_timeout = '3s'")
                with writer.transaction():
                    transition_case(writer, tenant_id=task.context.tenant_id, case_id=task.case_id,
                                    expected_version=task.case_version,
                                    event_type=EventType.GUARDRAIL_ESCALATED,
                                    payload={"guardrail": "operator_escalation",
                                             "observed": ["Team 실행 중 운영자가 끼어들었다"]},
                                    actor_type="test")
                writer.commit()
        except BaseException as exc:  # noqa: BLE001 - 원인을 테스트가 읽을 수 있게 붙잡는다
            self.write_error = exc
            raise
        return await super().execute(task)


def _runs(conn, tenant, case_id):
    with conn.cursor() as cur:
        cur.execute("SELECT status, started_at IS NOT NULL, finished_at IS NOT NULL "
                    "FROM agent_runs WHERE tenant_id=%s AND case_id=%s ORDER BY started_at",
                    (tenant, case_id))
        return cur.fetchall()


def _events(conn, tenant, case_id) -> list[str]:
    return [e["event_type"] for e in get_case_events(conn, tenant_id=tenant, case_id=case_id)]


def test_team_failure_keeps_the_run_start_record(db):  # noqa: F811
    """★Team 이 터져도 '시도했다' 는 기록이 남는다.

    전에는 `start_run()` 부터 결과 반영까지가 한 트랜잭션이어서 Team 예외가
    **실행 시작 기록과 routed 이벤트까지 함께 롤백**했다 — 실행을 시도했다는
    사실 자체가 사라졌다(`agent_runs` 0행). 지금은 A 단계를 Team 호출 전에
    커밋하므로 둘 다 남는다.
    """
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    controller = Controller(TeamRegistry([ExplodingTeam()]), policy_search=fake_policy,
                            context_broker=FakeContextBroker())

    with pytest.raises(RuntimeError, match="team blew up"):
        asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))

    assert _runs(conn, tenant, case_id) == [("failed", True, True)], "실행 시작 기록이 롤백됐다"
    assert _events(conn, tenant, case_id) == ["created", "classified", "routed"]


def test_failed_run_does_not_wedge_the_case_forever(db):  # noqa: F811
    """★기록을 남기는 대가로 생긴 책임 — 남은 실행을 반드시 닫는다.

    시작 기록이 살아남는다는 것은 그 행을 `active` 로 두고 나가면 활성 실행
    유일성(INV-CS-RT-011)이 이 Case 를 영원히 막는다는 뜻이다. 그래서 예외
    경로가 실행을 `failed` 로 닫는다. 닫혔는지는 말이 아니라 **다시 돌려서**
    확인한다.
    """
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    with pytest.raises(RuntimeError):
        asyncio.run(Controller(TeamRegistry([ExplodingTeam()]), policy_search=fake_policy,
                               context_broker=FakeContextBroker()).run_case(tenant_id=tenant, case_id=case_id))

    retry = asyncio.run(Controller(TeamRegistry([FakeTeam()]), policy_search=fake_policy,
                                   context_broker=FakeContextBroker()).run_case(tenant_id=tenant, case_id=case_id))

    assert retry["status"] == "resolved"
    assert [row[0] for row in _runs(conn, tenant, case_id)] == ["failed", "succeeded"]


def test_case_row_is_not_locked_while_the_team_runs(db):  # noqa: F811
    """★Team 실행 중에는 Case 행이 잠겨 있지 않다 — 이 파일의 핵심 주장.

    전에는 ROUTED 전이의 UPDATE 잠금이 Team 응답을 기다리는 내내 걸려 있어서
    다른 커넥션의 쓰기가 통째로 막혔다. 지금은 A 단계가 커밋된 뒤라 다른
    쓰기가 통과한다. 그 대가로 **경합이 실제로 일어날 수 있게 됐다** —
    그 경합을 어떻게 다루는지도 여기서 함께 고정한다.
    """
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    team = ConcurrentWriterTeam()
    outcome = asyncio.run(Controller(TeamRegistry([team]), policy_search=fake_policy,
                                     context_broker=FakeContextBroker()).run_case(tenant_id=tenant, case_id=case_id))

    assert team.write_error is None, f"Team 실행 중 Case 행이 잠겨 있었다: {team.write_error}"
    # ★진 쪽은 재시도하지 않는다. 이긴 쪽 상태를 그대로 두고 물러난다 —
    #   답변은 밀려난 version 의 스냅샷을 근거로 만들어진 것이기 때문이다.
    assert outcome["stale"] is True
    assert (outcome["status"], outcome["version"]) == ("escalated", 4)
    assert _events(conn, tenant, case_id) == ["created", "classified", "routed", "guardrail_escalated"]
    assert _runs(conn, tenant, case_id) == [("failed", True, True)]
