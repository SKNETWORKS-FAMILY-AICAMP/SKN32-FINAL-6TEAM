# -*- coding: utf-8 -*-
"""위임 범위 · 철회 · 실행 기록 · 되돌림 — v11 §12 DoD-18·19·20·21.

    18  위임 범위를 벗어난 자동 실행이 **0건**이다            (측정)
    19  위임을 **철회**하면 진행 중인 자동 실행이 멈춘다       (자동)
    20  자동 실행에 **무엇을·왜·얼마에·되돌림 기한**이 기록된다 (자동)
    21  **되돌림이 실패하면 사람에게** 넘어간다               (자동)

★**「자동 실행」이 무엇인가.** 승인 뒤 적용기가 **공급자 원장을 사람 손 없이 바꾸는
  분기**다. 승인은 여전히 필요하다(v11 §4-C · `auto_apply=False`) — 승인은 "이 변경을
  해도 된다" 이고 위임은 "그 변경을 우리가 업체 원장에 직접 반영해도 된다" 다.

★18 의 **재는 코드는 시험이 아니라 스크립트**다(`scripts/measure_delegation_scope.py`).
  이 파일은 그 스크립트를 **불러** 수를 고정한다 — 재는 코드와 시험하는 코드가 갈라지면
  둘 중 어느 것이 사실인지 알 수 없다. 분모(무엇을 몇 건 흘렸나)는 스크립트가 찍는다.

★DB 를 쓴다. 판정은 **원장을 직접 조회**해서 내린다 — 코드가 돌려준 값을 믿지 않는다.

재현:

    python -m pytest tests/integration/controller/test_delegation_scope.py -v
    python -m scripts.measure_delegation_scope
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from app import composition
from app.application.controller import Controller
from app.core.contracts import NextAction
from app.core.registry import TeamRegistry
from app.core.transition import transition_case
from app.domain.events import EventType
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.modules.travel_ops import delegation
from app.modules.travel_ops.booking_handoff import BookingHandoffTeam
from app.tools.read_tools import ReadToolbox
from scripts import measure_delegation_scope as measure

IN_SCOPE = measure.Case("범위 안", None)


@pytest.fixture()
def world():
    """깨끗한 tenant · 위임 있음 · 범위 안 예약 하나."""
    tenant, customer, booking = measure.make_world(IN_SCOPE)
    yield tenant, customer, booking
    measure.drop_world(tenant)


def _cancel(tenant, customer, *, request_id="cancel-1", revoke_after_approval=False):
    return measure.drive_to_applied(measure.build_controller(), tenant=tenant, customer=customer,
                                    issue_code="booking_cancel_request", request_id=request_id,
                                    revoke_after_approval=revoke_after_approval)


def _revert(tenant, customer, *, request_id="revert-1"):
    return measure.drive_to_applied(measure.build_controller(), tenant=tenant, customer=customer,
                                    issue_code="booking_revert_request", request_id=request_id)


# ─────────────────────────────────────────────────────────────────────────────
# DoD-18 — 범위를 벗어난 자동 실행이 0건
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def flood():
    """★스크립트가 재는 것을 **한 번** 돌린다. 경우마다 Case 를 끝까지 흘리므로 느리다."""
    rows = measure.measure()
    return rows, measure.summary(rows)


# invariant: DoD-18
def test_no_out_of_scope_automatic_execution_in_the_measured_flood(flood):
    """★★분자 0 · 분모는 **범위 밖 시도 건수**다.

    같이 본다 — 범위 안인데 막힌 건수도 0 이어야 한다. 그것이 0 이 아니면 게이트가
    정상 동작을 막는 것이고, 그 상태에서 「범위 밖 0건」은 **아무것도 실행하지 않아서**
    얻은 0 이다(분자만 보면 구분되지 않는다).
    """
    rows, total = flood
    leaked = [row for row in rows if row["expect_limit"] is not None and row["ledger_moved"]]
    assert total["out_of_scope_executions"] == 0, (
        f"위임 범위를 벗어난 자동 실행 {total['out_of_scope_executions']}건 "
        f"/ 범위 밖 시도 {total['out_of_scope_attempts']}건: "
        + "\n".join(f"  {row['name']} — {row['supplier_before']}→{row['supplier_after']}"
                    for row in leaked))
    assert total["in_scope_blocked"] == 0, (
        f"범위 **안**인데 막힌 건수 {total['in_scope_blocked']}/{total['in_scope_attempts']} — "
        f"게이트가 정상 동작을 막고 있다: "
        + str([row["name"] for row in rows if row["expect_limit"] is None and not row["ledger_moved"]]))
    assert total["out_of_scope_attempts"] >= len(delegation.LIMITS), (
        "범위 밖 시도가 한계 수보다 적다 — 안 흘려 본 한계가 있다(분모가 모자라다)")


# invariant: DoD-18
def test_every_limit_actually_blocked_something(flood):
    """★**한 번도 안 걸리는 한계는 막지 않는다.** 선언된 한계마다 실제로 그것이 막은 경우가 있어야 한다.

    DoD-23 의 교훈 — 이 저장소에는 「통과하면서 아무것도 못 잡는 가드」가 실제로 있었다.
    """
    rows, _ = flood
    blocked_by = {row["limit_seen"] for row in rows if not row["ledger_moved"]}
    never = sorted(set(delegation.LIMITS) - blocked_by)
    assert not never, (f"선언만 돼 있고 아무것도 막지 않은 한계: {never} — "
                       f"실제로 막은 것: {sorted(n for n in blocked_by if n)}")
    assert measure.LIMIT_SUPPLIER_TIER in blocked_by, "등급 게이트(017)가 이 흐름에서 안 걸렸다"


# invariant: DoD-18
def test_every_rejection_names_its_gate(flood):
    """★막긴 막았는데 **다른 문**이 막은 것이면 우연이다 — 기대한 문이 막았는지 센다."""
    rows, total = flood
    mismatched = [(row["name"], row["expect_limit"], row["limit_seen"], row["observed"])
                  for row in rows if row["expect_limit"] is not None
                  and row["limit_seen"] != row["expect_limit"]]
    assert total["blocked_for_another_reason"] == 0 and not mismatched, mismatched


# ─────────────────────────────────────────────────────────────────────────────
# DoD-19 — 철회하면 멈춘다
# ─────────────────────────────────────────────────────────────────────────────

# invariant: DoD-19
def test_revoking_after_the_approval_stops_the_execution(world):
    """★승인은 났고 적용은 아직 — 「진행 중」의 유일한 틈이다.

    판정을 **적용 순간에** 하므로 그 틈에 철회하면 원장이 한 글자도 안 바뀌고 사람에게 간다.
    ★적용은 한 트랜잭션이라 「반쯤 나간 자동 실행」이 존재하지 않는다 — 그래서 「진행 중인
      것을 멈춘다」가 「적용 순간에 다시 본다」로 구현된다.
    """
    tenant, customer, booking = world
    outcome = _cancel(tenant, customer, revoke_after_approval=True)
    ours, theirs = measure.ledger_status(tenant, booking)
    assert outcome["reached_approval"] is True                    # 승인까지는 갔다
    assert outcome["status"] == "escalated" and outcome["guardrail"] == "action_rejected"
    assert delegation.LIMIT_DELEGATION_REVOKED in outcome["observed"], outcome["observed"]
    assert ours == theirs == "confirmed"                          # ★한 글자도 안 바뀌었다
    assert outcome["action_status"] == "failed"                   # 시도가 상태로 남는다


# invariant: DoD-19
def test_after_a_revocation_no_new_execution_opens(world):
    """철회 뒤에 들어온 요청은 승인까지 가더라도 원장을 못 바꾼다."""
    tenant, customer, booking = world
    with get_connection() as conn, conn.transaction():
        assert delegation.revoke(conn, tenant_id=tenant, customer_id=customer, by="ops-1") is True
        # ★두 번째 철회는 False — 「이미 철회됐다」를 조용히 True 로 덮지 않는다
        assert delegation.revoke(conn, tenant_id=tenant, customer_id=customer, by="ops-1") is False
    outcome = _cancel(tenant, customer, request_id="after-revoke")
    assert outcome["status"] == "escalated"
    assert measure.ledger_status(tenant, booking) == ("confirmed", "confirmed")


class _TwoProposals(BookingHandoffTeam):
    """한 Case 가 예약 둘에 같은 종류의 제안을 낸다 — 하나는 범위 밖이다."""

    second: str = ""

    def _prepare(self, task, booking, evidence, seen):
        proposals = [self._proposal(task, "booking.cancel",
                                    {"booking_id": str(bid), "reason": "둘 다 취소"}, evidence)
                     for bid in (booking["booking_id"], self.second)]
        return self._result(task, outcome="completed", confidence=0.8, evidence=evidence,
                            next_action=NextAction.WAIT_FOR_APPROVAL, answer="두 건 취소를 준비했습니다.",
                            action_proposals=proposals, decisions=[])


# invariant: DoD-19
def test_one_out_of_scope_proposal_rolls_the_whole_batch_back(world):
    """★**돈이 나가는 쪽으로 실패하지 않는다.** 한 Case 의 제안 둘 중 하나가 범위 밖이면
    범위 안이던 첫째까지 되돌린다 — 위임 밖 상태에서 원장에 한 건이라도 남는 쪽이 더 나쁘다.
    """
    tenant, customer, first = world
    with get_connection() as conn, conn.transaction():
        # 종류가 위임 대상이 아니다(lodging) — 둘째만 범위 밖이다
        second = measure.new_booking(conn, tenant=tenant, customer=customer, no="OUT", kind="lodging")
    team = _TwoProposals(ReadToolbox(get_connection, policy_search=measure._policy))
    team.second = second
    controller = Controller(TeamRegistry([team]), policy_search=measure._policy,
                            connection_factory=get_connection, repository=repository,
                            verification_policy=measure.TRAVEL_OPS_POLICY,
                            fact_queries=measure.FACT_QUERIES,
                            action_handlers=composition.build_action_handlers())
    case_id = measure.open_booking_case(tenant=tenant, customer=customer,
                                        issue_code="booking_cancel_request", request_id="batch")
    asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    with get_connection() as conn, conn.transaction():
        case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
        assert str(case["status"]) == "waiting_approval"
        action_ids = case["state_json"]["action_ids"]
        assert len(action_ids) == 2
        for action_id in action_ids:                       # ★둘 다 승인한다
            repository.create_approval(conn, action_id=action_id, decision="approved",
                                       approver_id="ops-1")
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=case["version"],
                        event_type=EventType.APPROVED,
                        payload={"action_id": action_ids[0], "approver_id": "ops-1"},
                        actor_type="human", actor_id="ops-1")
    asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    with get_connection() as conn:
        case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
    assert str(case["status"]) == "escalated"
    assert measure.ledger_status(tenant, first) == ("confirmed", "confirmed")   # ★첫째도 안 바뀌었다
    assert measure.ledger_status(tenant, second) == ("confirmed", "confirmed")


# ─────────────────────────────────────────────────────────────────────────────
# DoD-20 — 무엇을 · 왜 · 얼마에 · 되돌림 기한
# ─────────────────────────────────────────────────────────────────────────────

# invariant: DoD-20
def test_the_ledger_records_what_why_how_much_and_the_revert_deadline(world):
    """★넷이 다 있어야 한다. 전에는 「무엇을」과 「결과」뿐이었다."""
    tenant, customer, booking = world
    outcome = _cancel(tenant, customer)
    record = outcome["record"]
    assert outcome["status"] == "resolved" and record["status"] == "succeeded", outcome

    # 무엇을 — 작업 종류 + 대상 객체 id(v11 §4-E 의 「대상」)
    assert record["action_type"] == "booking.cancel"
    assert record["arguments"]["booking_id"] == booking
    # 왜 — 고객 문장을 그대로. 지어낸 사유가 아니다
    assert record["reason"] == "예약을 정리해 주세요"
    # 얼마에 — 금액 **과 그 출처**. 출처 없는 금액은 근거 없는 수다
    assert record["amount_cents"] == measure.IN_SCOPE_CENTS
    assert record["amount_source"] == "bookings.amount_cents"
    # 되돌림 기한 — 앞으로의 시각이고, 무료 취소 구간을 넘지 않는다
    deadline = record["revert_deadline"]
    assert deadline is not None and deadline > datetime.now(UTC)
    scope = delegation.Scope.from_guardrails()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT starts_at FROM bookings WHERE booking_id=%s", (booking,))
        starts_at = cur.fetchone()[0]
    assert deadline <= starts_at, "되돌림 기한이 출발 시각을 넘는다"
    # 판정 근거 — 무엇을 무엇과 비교했나
    assert record["delegation"]["allowed"] is True and record["delegation"]["limit"] is None
    assert record["delegation"]["max_per_action_cents"] == scope.max_per_action_cents
    assert record["delegation"]["kinds_allowed"] == list(scope.kinds)
    # 되돌리려면 무엇으로 돌아가야 하나 — 있어야 되돌림이 상태를 지어내지 않는다
    assert record["prior_state"] == {"booking_status": "confirmed", "supplier_status": "confirmed"}


# invariant: DoD-20
def test_an_amount_we_do_not_know_is_left_empty_not_invented(world):
    """★★차액을 모르는 인계(`booking.change`)는 금액 칸을 **비운다.**

    NULL 은 0 이 아니라 「확인되지 않았다」다. 0 으로 적으면 「무료로 바꿨다」가 되고,
    아무 수나 적으면 근거 없는 수가 장부에 남는다(CLAUDE.md §0.1 · §1).
    """
    tenant, customer, _booking = world
    outcome = measure.drive_to_applied(measure.build_controller(), tenant=tenant, customer=customer,
                                       issue_code="booking_change_request", request_id="change-1")
    record = outcome["record"]
    assert outcome["status"] == "resolved" and record["action_type"] == "booking.change"
    assert record["amount_cents"] is None and record["amount_source"] is None
    assert record["reason"] == "예약을 정리해 주세요"          # 왜는 안다
    assert record["revert_deadline"] is None                  # 우리가 원장을 안 바꿨으니 되돌릴 것이 없다
    assert record["delegation"] is None                       # 위임을 쓰지 않았다


# ─────────────────────────────────────────────────────────────────────────────
# DoD-21 — 되돌림이 실패하면 사람에게
# ─────────────────────────────────────────────────────────────────────────────

def _cancel_action_id(tenant: str) -> str:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT action_id FROM action_requests WHERE tenant_id=%s "
                    "AND action_type='booking.cancel' AND status='succeeded'", (tenant,))
        return cur.fetchone()[0]


def test_a_revert_restores_both_ledgers(world):
    """★되돌림이 **되는** 것도 봐야 한다 — 안 되는 것만 보면 늘 실패하는 코드도 초록이다."""
    tenant, customer, booking = world
    _cancel(tenant, customer)
    assert measure.ledger_status(tenant, booking) == ("cancelled", "cancelled")
    outcome = _revert(tenant, customer)
    assert outcome["status"] == "resolved", outcome
    # ★기록된 원래 상태로 돌아간다 — `confirmed` 를 지어낸 것이 아니다
    assert measure.ledger_status(tenant, booking) == ("confirmed", "confirmed")
    assert outcome["record"]["status"] == "succeeded"
    assert outcome["record"]["provider_ref"].endswith(":reverted")


# invariant: DoD-21
def test_a_revert_after_the_deadline_goes_to_a_human(world):
    """★기한이 지난 되돌림은 **조용히 삼키지 않는다** — 시도가 상태로 남고 Case 가 사람에게 간다."""
    tenant, customer, booking = world
    _cancel(tenant, customer)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE action_requests SET revert_deadline = now() - interval '1 hour' "
                    "WHERE tenant_id=%s AND action_type='booking.cancel'", (tenant,))
    outcome = _revert(tenant, customer)
    assert outcome["status"] == "escalated" and outcome["guardrail"] == "action_rejected", outcome
    assert "revert deadline passed" in outcome["observed"], outcome["observed"]
    # 되돌림 **시도**가 상태로 남는다(코어가 savepoint 를 되돌린 **뒤** 적는다)
    assert outcome["record"]["action_type"] == "booking.revert"
    assert outcome["record"]["status"] == "failed"
    # ★원장은 취소된 그대로다 — 반쯤 되돌린 것이 없다
    assert measure.ledger_status(tenant, booking) == ("cancelled", "cancelled")


# invariant: DoD-21
def test_a_revert_without_a_recorded_prior_state_goes_to_a_human(world):
    """★돌아갈 상태를 모르면 **지어내지 않는다.** `confirmed` 를 찍어 넣는 쪽이 더 나쁘다."""
    tenant, customer, booking = world
    _cancel(tenant, customer)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE action_requests SET prior_state_json = NULL WHERE tenant_id=%s "
                    "AND action_type='booking.cancel'", (tenant,))
    outcome = _revert(tenant, customer)
    assert outcome["status"] == "escalated" and outcome["guardrail"] == "action_rejected", outcome
    assert "prior state" in outcome["observed"], outcome["observed"]
    assert outcome["record"]["status"] == "failed"
    assert measure.ledger_status(tenant, booking) == ("cancelled", "cancelled")


# invariant: DoD-21
def test_a_revert_on_a_real_supplier_never_touches_the_ledger(world):
    """되돌림도 공급자 원장을 바꾼다 — 등급 게이트(017)가 여기서도 선다."""
    tenant, customer, booking = world
    _cancel(tenant, customer)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE supplier_bookings SET tier='real' WHERE booking_id=%s", (booking,))
    outcome = _revert(tenant, customer)
    assert outcome["status"] == "escalated" and outcome["guardrail"] == "action_rejected", outcome
    assert measure.ledger_status(tenant, booking) == ("cancelled", "cancelled")


def test_there_is_nothing_to_revert_without_an_automatic_execution(world):
    """자동 실행이 없었으면 되돌릴 것이 없다 — 「성공」이라 답하지 않는다."""
    tenant, customer, booking = world
    outcome = _revert(tenant, customer)
    assert outcome["status"] == "escalated" and outcome["guardrail"] == "action_rejected", outcome
    assert "no automatic execution to revert" in outcome["observed"], outcome["observed"]
    assert measure.ledger_status(tenant, booking) == ("confirmed", "confirmed")
