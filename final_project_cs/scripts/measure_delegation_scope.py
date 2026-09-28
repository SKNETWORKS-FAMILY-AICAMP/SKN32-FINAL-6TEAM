# -*- coding: utf-8 -*-
"""위임 범위를 벗어난 자동 실행이 **몇 건인가** — v11 §12 DoD-18 (측정).

    python -m scripts.measure_delegation_scope                 # 표를 찍는다
    python -m scripts.measure_delegation_scope --json out.json # 원값도 남긴다

★**왜 시험이 아니라 스크립트인가.** DoD-18 은 「0건이다」라는 **수**를 요구한다. 시험은
  「막혔다」를 보지만 **분모를 말하지 않는다** — 무엇을 몇 건 흘렸는지가 없으면 0 이
  「막았다」인지 「흘린 게 없었다」인지 구분되지 않는다. 그래서 여기서 **경우를 세어
  흘리고** 표로 분자·분모를 같이 찍는다(CLAUDE.md 보고 형식 · §5).

★**무엇을 「자동 실행」이라 부르는가.** 승인 뒤 적용기가 **공급자 원장을 사람 손 없이
  바꾸는 분기**다(`booking_actions.BookingCancel`·`BookingRevert`). 승인은 여전히
  필요하다(v11 §4-C) — 여기서 재는 것은 「승인이 났을 때 원장이 실제로 바뀌었나」다.

★**세는 방법.** 경우마다 **깨끗한 tenant** 를 만들고 잴 시도를 진짜 경로로 끝까지
  흘린다 — Case 생성 → 라우팅 → Team → 승인 대기 → 승인 → 재개 → 적용. 그 다음
  **공급자 원장을 직접 조회**해서 바뀌었는지 본다. 코드의 판정값을 믿지 않고 DB 를 센다.

    분모  흘린 자동 실행 시도 건수(아래 `CASES`)
    분자  **위임 범위 밖인데 공급자 원장이 바뀐** 건수 ← 0 이어야 한다

★★**흘리지 않고 심는 것이 하나 있다 — 과거 실행 이력**(누적 상한·횟수 상한을 채우는 데
  쓴다). `action_requests` 에 **실제 경로가 쓰는 것과 같은 모양**으로 넣는다. 왜 흘리지
  않나: `read.booking` 은 인자가 없으면 **가장 임박한** 예약을 고르므로, 한 tenant 에 예약을
  여럿 두면 Team 이 어느 것을 집을지 시험이 정하지 못한다. 그래서 tenant 마다 **잴 예약은
  하나**로 두고 이력만 심는다. ☆심은 것은 게이트의 **입력**이고, **판정 자체는 심지 않는다.**

★같이 찍는 둘(0 이 아니면 그것도 결함이다):
    · 범위 안인데 막힌 건수      — 게이트가 정상 동작을 막고 있다
    · 기대와 다른 사유로 막힌 건수 — 막긴 막았는데 다른 이유다(우연히 0 일 수 있다)

★막힌 사유는 `case_events`(append-only)의 `guardrail_escalated.observed` 에서 읽는다.
  적용이 거부되면 savepoint 가 통째로 되돌려지므로 `action_requests.delegation_json` 은
  **성공한 건에만** 남는다 — 거부된 건의 사유가 남는 곳은 이벤트 쪽이다.

☆이 파일의 `CASES`·`run_case_row`·`summary` 를
  `tests/integration/controller/test_delegation_scope.py` 가 그대로 불러 쓴다 —
  재는 코드와 시험하는 코드가 갈라지지 않게.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app import composition
from app.application.case_intake import open_case
from app.application.controller import Controller
from app.core.context import PolicyChunk
from app.core.registry import TeamRegistry
from app.core.transition import transition_case
from app.domain.events import EventType
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.modules.travel_ops import delegation
from app.modules.travel_ops.booking_handoff import BookingHandoffTeam
from app.modules.travel_ops.case_engine import cleanup_tenant
from app.modules.travel_ops.verification_policy import FACT_QUERIES, TRAVEL_OPS_POLICY
from app.tools.read_tools import ReadToolbox

#: ★한계값은 **설정에서 읽는다** — 숫자를 여기 박지 않는다(RULE.md §3.1).
_SCOPE = delegation.Scope.from_guardrails()
IN_SCOPE_CENTS = _SCOPE.max_per_action_cents
IN_SCOPE_KIND = _SCOPE.kinds[0]
#: 무료 취소 구간 안에 넉넉히 들어오는 출발 시각(시간)
IN_SCOPE_LEAD_HOURS = _SCOPE.free_cancellation_lead_hours * 2

#: 등급 게이트(017)가 막은 것. ★위임 한계 이름이 아니라서 따로 둔다 — 같은 분기의 다른 문이다.
LIMIT_SUPPLIER_TIER = "supplier_tier"


@dataclass(frozen=True)
class Case:
    """흘려 볼 한 경우. `expect_limit=None` 이면 **범위 안**(실행돼야 한다)."""

    name: str
    expect_limit: str | None
    kind: str = IN_SCOPE_KIND
    amount_cents: int | None = IN_SCOPE_CENTS
    starts_in_hours: int = IN_SCOPE_LEAD_HOURS
    tier: str = "simulated"
    #: 'granted' · 'revoked' · 'absent'
    grant: str = "granted"
    #: **다른** 예약에 성공해 둔 자동 실행 이력(누적 상한을 채운다). 금액 목록이다
    prior_other_cents: tuple[int, ...] = ()
    #: **같은** 예약에 성공해 둔 자동 실행 이력 건수(횟수 상한을 채운다)
    prior_same_booking: int = 0
    #: 위임을 **승인 뒤**에 거둔다 — 「진행 중인 자동 실행이 멈추나」(DoD-19)
    revoke_after_approval: bool = False


#: ★경우 목록이 곧 분모다. **한계마다 최소 한 경우**를 둔다 — 한 번도 안 걸리는 한계는
#:  「막는다」고 적혀 있을 뿐 아무것도 막지 않는다(DoD-23 의 교훈: 통과하면서 못 잡는 가드).
CASES: tuple[Case, ...] = (
    Case("범위 안 — 실행된다", None),
    Case("범위 안 — 같은 예약 1회째 이력이 있다", None, prior_same_booking=1),
    Case("범위 안 — 누적이 상한에 붙었지만 넘지 않는다", None,
         prior_other_cents=tuple([IN_SCOPE_CENTS]
                                 * (_SCOPE.max_total_cents // IN_SCOPE_CENTS - 1))),
    Case("위임 기록이 없다", delegation.LIMIT_DELEGATION_ABSENT, grant="absent"),
    Case("위임이 철회됐다", delegation.LIMIT_DELEGATION_REVOKED, grant="revoked"),
    Case("승인 뒤에 철회됐다", delegation.LIMIT_DELEGATION_REVOKED, revoke_after_approval=True),
    Case("위임 대상이 아닌 종류", delegation.LIMIT_KIND, kind="lodging"),
    Case("금액을 모른다", delegation.LIMIT_AMOUNT_UNKNOWN, amount_cents=None),
    Case("건당 상한 초과", delegation.LIMIT_PER_ACTION, amount_cents=IN_SCOPE_CENTS + 1),
    Case("누적 상한 초과", delegation.LIMIT_TOTAL,
         prior_other_cents=tuple([IN_SCOPE_CENTS] * (_SCOPE.max_total_cents // IN_SCOPE_CENTS))),
    Case("같은 예약 횟수 초과", delegation.LIMIT_COUNT,
         prior_same_booking=_SCOPE.max_changes_per_booking),
    Case("무료 취소 구간 밖", delegation.LIMIT_FREE_CANCELLATION,
         starts_in_hours=_SCOPE.free_cancellation_lead_hours - 1),
    # ★등급 게이트(017)도 같은 분기의 문이다 — 여기서도 원장이 안 바뀌어야 한다.
    Case("실제 공급자 등급", LIMIT_SUPPLIER_TIER, tier="real"),
)

_CHUNKS = [PolicyChunk(document_id="doc_booking", chunk_no=1, content="출발 3일 전까지 취소 수수료 없음",
                       score=0.9, scope="booking")]


def _policy(*_args: Any, **_kwargs: Any) -> list[PolicyChunk]:
    return list(_CHUNKS)


def build_controller() -> Controller:
    team = BookingHandoffTeam(ReadToolbox(get_connection, policy_search=_policy))
    return Controller(TeamRegistry([team]), policy_search=_policy, connection_factory=get_connection,
                      repository=repository, verification_policy=TRAVEL_OPS_POLICY,
                      fact_queries=FACT_QUERIES, action_handlers=composition.build_action_handlers())


def new_booking(conn: Any, *, tenant: str, customer: UUID, no: str, kind: str = IN_SCOPE_KIND,
                amount_cents: int | None = IN_SCOPE_CENTS,
                starts_in_hours: int = IN_SCOPE_LEAD_HOURS, tier: str = "simulated") -> str:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO bookings (tenant_id,customer_id,booking_no,kind,status,starts_at,"
                    "party_size,capacity,amount_cents) VALUES (%s,%s,%s,%s,'confirmed',%s,2,4,%s) "
                    "RETURNING booking_id",
                    (tenant, customer, no, kind, datetime.now(UTC) + timedelta(hours=starts_in_hours),
                     amount_cents))
        booking = cur.fetchone()[0]
        cur.execute("INSERT INTO supplier_bookings (tenant_id,booking_id,supplier,supplier_ref,status,tier) "
                    "VALUES (%s,%s,'mock',%s,'confirmed',%s)", (tenant, booking, f"SUP-{no}", tier))
    return str(booking)


def seed_past_execution(conn: Any, *, tenant: str, case_id: UUID, booking_id: str,
                        amount_cents: int) -> None:
    """지난 자동 실행 **이력**을 실제 경로와 같은 모양으로 심는다(게이트의 입력).

    ★`delegation_json` 이 「위임을 써서 실행됐다」의 표식이다 — 누적·횟수는 그 표식이 있는
      `succeeded` 행만 센다(`delegation._spent_cents`·`_change_count`).
    """
    action_id = repository.create_action_request(
        conn, tenant_id=tenant, case_id=case_id, action_type="booking.cancel",
        arguments={"booking_id": booking_id, "reason": "심은 이력"},
        idempotency_key="seeded-" + uuid4().hex, status="succeeded",
        provider_ref="mock-supplier:mock:SEED:cancelled")
    repository.set_action_status(
        conn, tenant_id=tenant, action_id=action_id, status="succeeded",
        ledger={"amount_cents": amount_cents, "amount_source": "bookings.amount_cents",
                "reason": "심은 이력", "delegation": {"allowed": True, "seeded": True}})


def ledger_status(tenant: str, booking: str) -> tuple[str, str]:
    """(우리 예약, 공급자 원장) 상태를 **DB 에서** 읽는다."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM bookings WHERE tenant_id=%s AND booking_id=%s", (tenant, booking))
        ours = cur.fetchone()[0]
        cur.execute("SELECT status FROM supplier_bookings WHERE tenant_id=%s AND booking_id=%s",
                    (tenant, booking))
        theirs = cur.fetchone()[0]
    return ours, theirs


def open_booking_case(*, tenant: str, customer: UUID, issue_code: str, request_id: str) -> UUID:
    with get_connection() as conn:
        return open_case(conn, repository=repository, tenant_id=tenant, customer_id=customer,
                         request_id=request_id, message="예약을 정리해 주세요", channel="api",
                         actor_type="api", actor_id="measure",
                         labels={"intent": "incident_report", "issue_code": issue_code,
                                 "sentiment": "neutral"}).case_id


def last_guardrail(case_id: UUID) -> tuple[str | None, str]:
    """마지막 이벤트가 가드레일이면 (이름, 관측 문장). 아니면 (None, "")."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT event_type, payload_json FROM case_events WHERE case_id=%s "
                    "ORDER BY aggregate_version DESC LIMIT 1", (case_id,))
        row = cur.fetchone()
    if row and row[0] == "guardrail_escalated":
        observed = row[1].get("observed") or []
        return row[1].get("guardrail"), (observed[0] if observed else "")
    return None, ""


def limit_from(observed: str) -> str | None:
    """거부 문장에서 **어느 문이 막았는지**를 뽑는다.

    ★문장을 세지 않고 **이름**을 센다. 적용기의 거부 문구가 이 접두를 유지해야 한다 —
      시험 `test_every_rejection_names_its_gate` 가 그것을 고정한다.
    """
    if observed.startswith("delegation "):
        return observed[len("delegation "):].split(":", 1)[0].strip()
    if observed.startswith("supplier tier "):
        return LIMIT_SUPPLIER_TIER
    return None


def drive_to_applied(controller: Controller, *, tenant: str, customer: UUID, issue_code: str,
                     request_id: str, revoke_after_approval: bool = False) -> dict[str, Any]:
    """Case 하나를 승인까지 끌고 가 적용시킨다. 실패해도 예외를 내지 않고 상태를 돌려준다."""
    case_id = open_booking_case(tenant=tenant, customer=customer, issue_code=issue_code,
                                request_id=request_id)
    asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    with get_connection() as conn, conn.transaction():
        case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
        if str(case["status"]) != "waiting_approval":
            guardrail, observed = last_guardrail(case_id)
            return {"case_id": case_id, "status": str(case["status"]), "action_id": None,
                    "action_status": None, "record": None, "guardrail": guardrail,
                    "observed": observed, "reached_approval": False}
        action_id = case["state_json"]["action_ids"][0]
        repository.create_approval(conn, action_id=action_id, decision="approved", approver_id="ops-measure")
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=case["version"],
                        event_type=EventType.APPROVED,
                        payload={"action_id": action_id, "approver_id": "ops-measure"},
                        actor_type="human", actor_id="ops-measure")
    if revoke_after_approval:
        # ★승인은 났고 적용은 아직 — 「진행 중」의 유일한 틈이다(DoD-19).
        with get_connection() as conn, conn.transaction():
            delegation.revoke(conn, tenant_id=tenant, customer_id=customer, by="ops-measure")
    asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    with get_connection() as conn:
        case = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
        record = repository.action_execution_record(conn, tenant_id=tenant, action_id=action_id)
    guardrail, observed = last_guardrail(case_id)
    return {"case_id": case_id, "status": str(case["status"]), "action_id": action_id,
            "action_status": record["status"], "record": record, "guardrail": guardrail,
            "observed": observed, "reached_approval": True}


def make_world(case: Case) -> tuple[str, UUID, str]:
    """깨끗한 tenant · 고객 · **잴 예약 하나**를 만들고 이력을 심는다."""
    tenant = "deleg_" + uuid4().hex[:10]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "delegation scope"))
        cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,'c') RETURNING customer_id",
                    (tenant,))
        customer = cur.fetchone()[0]
    with get_connection() as conn, conn.transaction():
        if case.grant in ("granted", "revoked"):
            delegation.grant(conn, tenant_id=tenant, customer_id=customer, by="measure")
        if case.grant == "revoked":
            delegation.revoke(conn, tenant_id=tenant, customer_id=customer, by="measure")
        booking = new_booking(conn, tenant=tenant, customer=customer, no="TGT", kind=case.kind,
                              amount_cents=case.amount_cents, starts_in_hours=case.starts_in_hours,
                              tier=case.tier)
    if case.prior_other_cents or case.prior_same_booking:
        history_case = open_booking_case(tenant=tenant, customer=customer,
                                         issue_code="booking_other", request_id="history")
        with get_connection() as conn, conn.transaction():
            for amount in case.prior_other_cents:
                seed_past_execution(conn, tenant=tenant, case_id=history_case,
                                    booking_id=str(uuid4()), amount_cents=amount)
            for _ in range(case.prior_same_booking):
                seed_past_execution(conn, tenant=tenant, case_id=history_case,
                                    booking_id=booking, amount_cents=IN_SCOPE_CENTS)
    return tenant, customer, booking


def drop_world(tenant: str) -> None:
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM delegations WHERE tenant_id=%s", (tenant,))
        cur.execute("DELETE FROM outbox WHERE tenant_id=%s", (tenant,))
        cur.execute("DELETE FROM supplier_bookings WHERE tenant_id=%s", (tenant,))
        cur.execute("DELETE FROM bookings WHERE tenant_id=%s", (tenant,))
    cleanup_tenant(tenant)


def run_case_row(case: Case) -> dict[str, Any]:
    """한 경우를 깨끗한 tenant 에서 끝까지 흘리고 **DB 에서 읽은** 결과를 돌려준다."""
    tenant, customer, booking = make_world(case)
    try:
        controller = build_controller()
        before = ledger_status(tenant, booking)
        outcome = drive_to_applied(controller, tenant=tenant, customer=customer,
                                   issue_code="booking_cancel_request", request_id="target",
                                   revoke_after_approval=case.revoke_after_approval)
        after = ledger_status(tenant, booking)
        return {
            "name": case.name, "expect_limit": case.expect_limit,
            "case_status": outcome["status"], "action_status": outcome["action_status"],
            "guardrail": outcome["guardrail"], "observed": outcome["observed"],
            "limit_seen": limit_from(outcome["observed"]),
            "ours_before": before[0], "ours_after": after[0],
            "supplier_before": before[1], "supplier_after": after[1],
            "ledger_moved": before[1] != after[1],
            "record": _plain(outcome["record"]),
        }
    finally:
        drop_world(tenant)


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (datetime, UUID)):
        return str(value)
    return value


def measure(cases: tuple[Case, ...] = CASES) -> list[dict[str, Any]]:
    return [run_case_row(case) for case in cases]


def summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    """분자·분모. ★수를 세는 자리를 한 곳에 둔다 — 시험과 스크립트가 같은 수를 본다."""
    out_of_scope = [row for row in rows if row["expect_limit"] is not None]
    in_scope = [row for row in rows if row["expect_limit"] is None]
    return {
        "attempts": len(rows),
        "out_of_scope_attempts": len(out_of_scope),
        "in_scope_attempts": len(in_scope),
        # ★★DoD-18 의 수 — 범위 밖인데 공급자 원장이 바뀐 건수
        "out_of_scope_executions": sum(1 for row in out_of_scope if row["ledger_moved"]),
        # 같이 봐야 하는 둘
        "in_scope_blocked": sum(1 for row in in_scope if not row["ledger_moved"]),
        "blocked_for_another_reason": sum(1 for row in out_of_scope
                                          if not row["ledger_moved"]
                                          and row["limit_seen"] != row["expect_limit"]),
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", help="원값을 이 경로에 JSON 으로 남긴다")
    args = parser.parse_args()

    print("=" * 100)
    print("위임 범위를 벗어난 자동 실행 건수 — v11 §12 DoD-18 (측정)")
    print(f"한계(설정 `travel.delegation`): 건당 {IN_SCOPE_CENTS}전 · 누적 {_SCOPE.max_total_cents}전 · "
          f"같은 예약 {_SCOPE.max_changes_per_booking}회 · 종류 {list(_SCOPE.kinds)} · "
          f"무료취소 {_SCOPE.free_cancellation_lead_hours}h 전 · 되돌림창 {_SCOPE.revert_window_hours}h")
    print("=" * 100)
    rows = measure()
    print(f"{'경우':<34} {'기대 사유':<33} {'막은 문':<33} {'원장':<16} 판정")
    for row in rows:
        moved = f"{row['supplier_before']}→{row['supplier_after']}"
        verdict = ("실행됨" if row["ledger_moved"] else "안 바뀜")
        if row["expect_limit"] is None:
            verdict += " (범위 안)" if row["ledger_moved"] else " ★범위 안인데 막혔다"
        else:
            verdict += " ★★범위 밖인데 실행됐다" if row["ledger_moved"] else ""
        print(f"{row['name']:<34} {str(row['expect_limit']):<33} {str(row['limit_seen']):<33} "
              f"{moved:<16} {verdict}")
    total = summary(rows)
    print("-" * 100)
    print(f"분모 — 흘린 자동 실행 시도 {total['attempts']}건 "
          f"(범위 밖 {total['out_of_scope_attempts']} · 범위 안 {total['in_scope_attempts']})")
    print(f"★분자 — 위임 범위를 벗어난 자동 실행 {total['out_of_scope_executions']}건 "
          f"= {total['out_of_scope_executions'] / total['out_of_scope_attempts']:.0%} "
          f"(분모는 범위 밖 시도 {total['out_of_scope_attempts']}건)")
    print(f"같이 본 것 — 범위 안인데 막힌 건수 {total['in_scope_blocked']}/"
          f"{total['in_scope_attempts']} · 기대와 다른 사유로 막힌 건수 "
          f"{total['blocked_for_another_reason']}/{total['out_of_scope_attempts']}")
    print("☆표본은 위 경우 목록뿐이다 — 한계마다 한 경우씩이며, 실제 운영 분포를 대표하지 않는다.")
    if args.json:
        payload = {"measured_at": datetime.now(UTC).isoformat(), "scope": vars(_SCOPE),
                   "summary": total, "rows": rows}
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(_plain(payload), handle, ensure_ascii=False, indent=2)
        print(f"원값: {args.json}")
    bad = (total["out_of_scope_executions"] or total["in_scope_blocked"]
           or total["blocked_for_another_reason"])
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
