"""여행 승인 제안 — 라우팅 · 대조 · 승인 대기 · **승인 뒤 실행**까지. 실제 Team · 실제 대조 선언 · 실제 DB 예약.

★`[2026-09-17]` 이식 리포트 §6-6 「확인 필요」를 실행으로 가린다. 의심: Team 이 근거 id 로
  `tool:<팀>:<도구>` 를 드는데 Controller 대조는 **ContextPack 근거(정책)만** 센다 — 그러면
  근거가 멀쩡한 승인 제안도 「ContextPack 에 없는 근거」로 막힌다.
★여행 승인 제안을 Controller 로 지나가게 하는 시험이 이 저장소에 없었다(`tests` 에서
  `booking.cancel`·`booking.change`·`activity.change` 검색 0건).
★`[2026-09-18]` 두 구멍을 더 막는다 — ①Booking Handoff 에 `select_capability` 가 없어 준비
  capability 둘에 라우팅으로 닿지 못했다(이 시험은 그래서 전에 선택을 덮어썼다) ②승인하면 Team 을
  다시 부를 뿐 **아무것도 실행되지 않았다.**
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app import composition
from app.application.case_intake import open_case
from app.application.controller import Controller
from app.core.context import PolicyChunk
from app.core.contracts import InvalidTransition
from app.core.registry import TeamRegistry
from app.core.transition import transition_case
from app.domain.events import EventType
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.booking_handoff import BookingHandoffTeam
from app.modules.travel_ops.case_engine import cleanup_tenant
from app.modules.travel_ops.verification_policy import FACT_QUERIES, TRAVEL_OPS_POLICY
from app.tools.read_tools import ReadToolbox

CHUNKS = [PolicyChunk(document_id="doc_booking", chunk_no=1, content="출발 3일 전까지 취소 수수료 없음",
                      score=0.9, scope="booking")]


def _policy(*_args, **_kwargs):
    return list(CHUNKS)


@pytest.fixture()
def world():
    tenant = "apprprop_" + uuid4().hex[:10]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "approval proposal"))
        cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id",
                    (tenant, "c"))
        customer = cur.fetchone()[0]
        cur.execute("INSERT INTO bookings (tenant_id,customer_id,booking_no,kind,status,starts_at,party_size,"
                    "capacity,amount_cents) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING booking_id",
                    (tenant, customer, "BK-1", "activity", "confirmed", datetime.now(UTC) + timedelta(days=5),
                     2, 4, 5000000))
        booking = cur.fetchone()[0]
        cur.execute("INSERT INTO supplier_bookings (tenant_id,booking_id,supplier,supplier_ref,status) "
                    "VALUES (%s,%s,%s,%s,%s)", (tenant, booking, "mock", "SUP-1", "confirmed"))
    yield tenant, customer, booking
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM outbox WHERE tenant_id=%s", (tenant,))
        cur.execute("DELETE FROM supplier_bookings WHERE tenant_id=%s", (tenant,))
        cur.execute("DELETE FROM bookings WHERE tenant_id=%s", (tenant,))
    cleanup_tenant(tenant)


def _controller():
    team = BookingHandoffTeam(ReadToolbox(get_connection, policy_search=_policy))
    return Controller(TeamRegistry([team]), policy_search=_policy, connection_factory=get_connection,
                      repository=repository, verification_policy=TRAVEL_OPS_POLICY, fact_queries=FACT_QUERIES,
                      action_handlers=composition.build_action_handlers())


def _open(tenant, customer, issue_code, request_id="req-1"):
    with get_connection() as conn:
        return open_case(conn, repository=repository, tenant_id=tenant, customer_id=customer,
                         request_id=request_id, message="예약 취소해 주세요", channel="api", actor_type="api",
                         actor_id="test", labels={"intent": "incident_report", "issue_code": issue_code,
                                                  "sentiment": "neutral"}).case_id


def _approve(tenant, case_id):
    """승인 API 가 하는 기록과 전이 — 재검증은 API 시험(`tests/integration/api`)이 본다."""
    with get_connection() as conn, conn.transaction():
        case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
        action_id = case["state_json"]["action_ids"][0]
        repository.create_approval(conn, action_id=action_id, decision="approved", approver_id="ops-1")
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=case["version"],
                        event_type=EventType.APPROVED, payload={"action_id": action_id, "approver_id": "ops-1"},
                        actor_type="human", actor_id="ops-1")
    return action_id


def _state(tenant, case_id, booking):
    with get_connection() as conn, conn.cursor() as cur:
        case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
        cur.execute("SELECT status FROM bookings WHERE booking_id=%s", (booking,))
        ours = cur.fetchone()[0]
        cur.execute("SELECT status FROM supplier_bookings WHERE booking_id=%s", (booking,))
        theirs = cur.fetchone()[0]
        cur.execute("SELECT action_type, status, provider_ref FROM action_requests WHERE case_id=%s "
                    "AND action_type LIKE 'booking.%%'", (case_id,))
        actions = cur.fetchall()
        cur.execute("SELECT event_type, payload_json FROM case_events WHERE case_id=%s ORDER BY aggregate_version",
                    (case_id,))
        events = cur.fetchall()
    return case, ours, theirs, actions, events


def test_a_cancel_request_routes_to_prepare_cancel_and_waits_for_approval(world):
    tenant, customer, booking = world
    case_id = _open(tenant, customer, "booking_cancel_request")
    asyncio.run(_controller().run_case(tenant_id=tenant, case_id=case_id))
    case, ours, theirs, actions, events = _state(tenant, case_id, booking)
    assert str(case["status"]) == "waiting_approval", events[-1]
    routed = next(payload for kind, payload in events if kind == "routed")
    assert routed["capability"] == "booking.prepare_cancel"          # ★전에는 늘 booking.verify
    assert case["state_json"]["wait_reason"] == "human_approval"
    assert actions == [("booking.cancel", "pending_approval", None)] and ours == theirs == "confirmed"


def test_an_approved_cancel_is_executed_once_against_the_mock_supplier(world):
    tenant, customer, booking = world
    controller = _controller()
    case_id = _open(tenant, customer, "booking_cancel_request")
    asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    _approve(tenant, case_id)
    asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    case, ours, theirs, actions, events = _state(tenant, case_id, booking)
    assert str(case["status"]) == "resolved", events[-1]
    assert ours == theirs == "cancelled"
    assert actions == [("booking.cancel", "succeeded", "mock-supplier:mock:SUP-1:cancelled")]
    assert [kind for kind, _ in events][-3:] == ["approved", "resumed", "completed"]
    # 같은 Case 를 다시 돌려도 두 번 실행하지 않는다 — 끝난 Case 는 상태기계가 막는다
    with pytest.raises(InvalidTransition):
        asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    assert _state(tenant, case_id, booking)[3] == actions


def test_an_approved_change_is_handed_off_not_invented(world):
    tenant, customer, booking = world
    controller = _controller()
    case_id = _open(tenant, customer, "booking_change_request")
    asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    assert _state(tenant, case_id, booking)[3] == [("booking.change", "pending_approval", None)]
    _approve(tenant, case_id)
    asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    case, ours, theirs, actions, _ = _state(tenant, case_id, booking)
    assert str(case["status"]) == "resolved"
    assert ours == "change_requested" and theirs == "confirmed"      # ★공급자 쪽은 지어내 바꾸지 않는다
    assert actions == [("booking.change", "succeeded", "handoff:BK-1")]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT payload_json FROM outbox WHERE tenant_id=%s AND topic='booking.handoff'", (tenant,))
        handoffs = [row[0] for row in cur.fetchall()]
    assert len(handoffs) == 1 and handoffs[0]["booking_no"] == "BK-1"


def test_a_booking_that_became_locked_after_approval_is_not_touched(world):
    tenant, customer, booking = world
    controller = _controller()
    case_id = _open(tenant, customer, "booking_cancel_request")
    asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    _approve(tenant, case_id)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE bookings SET locked=true WHERE booking_id=%s", (booking,))
    asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    case, ours, theirs, actions, events = _state(tenant, case_id, booking)
    assert str(case["status"]) == "escalated" and events[-1][1]["guardrail"] == "action_rejected", events[-1]
    assert ours == theirs == "confirmed"                              # ★반쯤 바뀐 것이 없다
    assert actions == [("booking.cancel", "failed", None)]


def test_without_a_handler_the_old_resume_path_is_kept(world):
    """적용기가 없는 조립 — 예전처럼 Team 을 다시 부른다(이 변경이 다른 도메인의 승인 흐름을 안 바꾼다)."""
    from app.core.actions import ActionHandlers

    tenant, customer, booking = world
    team = BookingHandoffTeam(ReadToolbox(get_connection, policy_search=_policy))
    controller = Controller(TeamRegistry([team]), policy_search=_policy, connection_factory=get_connection,
                            repository=repository, verification_policy=TRAVEL_OPS_POLICY,
                            fact_queries=FACT_QUERIES, action_handlers=ActionHandlers())
    case_id = _open(tenant, customer, "booking_cancel_request")
    asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    _approve(tenant, case_id)
    asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    _, ours, theirs, actions, events = _state(tenant, case_id, booking)
    assert ours == theirs == "confirmed" and actions[0][1] == "pending_approval"
    assert "resumed" in [kind for kind, _ in events]


class TwoBookings(BookingHandoffTeam):
    """한 Case 가 서로 다른 예약 둘에 같은 종류의 제안을 낸다."""

    second: str = ""

    def _prepare(self, task, booking, evidence, seen):
        from app.core.contracts import NextAction

        proposals = [self._proposal(task, "booking.cancel", {"booking_id": str(bid), "reason": "둘 다 취소"}, evidence)
                     for bid in (booking["booking_id"], self.second)]
        return self._result(task, outcome="completed", confidence=0.8, evidence=evidence,
                            next_action=NextAction.WAIT_FOR_APPROVAL, answer="두 건 취소를 준비했습니다.",
                            action_proposals=proposals, decisions=[])


def test_two_proposals_for_two_bookings_in_one_case_both_survive(world):
    """★v11 §4-E — 멱등 키의 대상이 Case id 였으면 둘째가 같은 키로 합쳐져 사라진다."""
    tenant, customer, booking = world
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO bookings (tenant_id,customer_id,booking_no,kind,status,starts_at,party_size,"
                    "capacity,amount_cents) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING booking_id",
                    (tenant, customer, "BK-2", "dining", "confirmed", datetime.now(UTC) + timedelta(days=6),
                     2, 4, 3000000))
        second = cur.fetchone()[0]
    team = TwoBookings(ReadToolbox(get_connection, policy_search=_policy))
    team.second = str(second)
    controller = Controller(TeamRegistry([team]), policy_search=_policy, connection_factory=get_connection,
                            repository=repository, verification_policy=TRAVEL_OPS_POLICY,
                            fact_queries=FACT_QUERIES, action_handlers=composition.build_action_handlers())
    case_id = _open(tenant, customer, "booking_cancel_request")
    asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    case, _, _, actions, events = _state(tenant, case_id, booking)
    assert str(case["status"]) == "waiting_approval", events[-1]
    assert len(case["state_json"]["action_ids"]) == 2 and len(set(case["state_json"]["action_ids"])) == 2
    assert sorted(a[1] for a in actions) == ["pending_approval", "pending_approval"]
