# -*- coding: utf-8 -*-
"""**승인된** 예약 제안의 적용기 — Booking Handoff 가 낸 `booking.cancel` · `booking.change`.

★`[2026-09-18]` 전에는 승인 뒤 실행하는 코드가 **없었다.** 사람이 승인하면 Case 가 `resuming` 으로
  가서 Team 을 다시 부를 뿐이었고, Team 은 side effect 를 실행하지 않으니 아무것도 안 일어났다.
  이제 코어가 승인된 제안을 이 적용기로 실행한다(`controller._apply_approved`).

★`auto_apply = False` — 승인 없이는 절대 적용되지 않는다(코어가 `action_requires_approval` 로 막는다).

★실제 업체 예약을 바꾸는 것은 **시연용 Mock 공급자 한정**이다(v10 §5 「Handoff」). 지금 공급자
  원장은 우리 DB 의 `supplier_bookings` 다(`read_tools.supplier`). 그래서:

    booking.cancel   Mock 공급자 원장과 우리 예약을 `cancelled` 로 — 같은 트랜잭션
    booking.change   ★바꿀 내용이 인자에 없다(Team 은 사유만 정리한다). 지어내지 않는다 —
                     **인계**한다: 예약을 `change_requested` 로 두고 운영 인계 메시지를 바깥함에 넣는다

  provider_ref 는 `mock-supplier:` 로 시작한다 — 실제 공급자와 섞어 읽지 않게.

★`[2026-09-22]` **공급자 등급 게이트가 생겼다**(v11 §12 DoD-14·15, 마이그레이션 017).
  전에는 「Mock 공급자 한정」이 **주석에만** 있었고 코드는 등급을 보지 않았다 — 실제 공급자
  행이 한 줄 들어오면 승인 한 번에 그 원장을 고쳤을 것이다. 이제:

    supplier_bookings.tier == 'simulated'   공급자 원장을 바꾼다(시연 자동 실행 분기)
    그 밖(기본값 'real')                    ★원장을 **한 글자도 건드리지 않고** ActionRejected —
                                            코어가 전부 되돌리고 `action_rejected` 로 사람에게 넘긴다

  등급을 모르거나 읽지 못하면 실행하지 않는다. **모름은 'simulated' 가 아니다.**

★적용 순간에 다시 확인한다 — 이 고객의 예약인가 · 잠긴 예약(Lodging/Flight)이 아닌가 ·
  이미 취소된 것을 또 취소하지 않는가 · **공급자가 시뮬레이션 등급인가**.
"""
from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from app.core.actions import ActionConflict, ActionRejected, AppliedAction
from app.core.transition import OutboxMessage

HANDOFF_TOPIC = "booking.handoff"

#: ★자동 실행 분기가 열리는 **유일한** 공급자 등급(v11 §12 DoD-15). 마이그레이션 017 의
#:  `supplier_bookings.tier` 가 이 값이거나 `'real'` 이다(DB CHECK 제약이 둘로 묶는다).
SIMULATED_TIER = "simulated"


def require_simulated_tier(supplier: Mapping[str, Any]) -> None:
    """공급자 원장을 바꾸기 전에 **반드시** 지나는 문(v11 §12 DoD-14·15).

    ★등급이 `simulated` 가 **아닌 경우 전부** 거부한다 — `real` 만 막는 게 아니다.
      `None`(등급 칸을 안 읽었다)·`''`·오타도 거부한다. **모름은 시뮬레이션이 아니다.**
      반대로 썼다면(「`real` 이면 막는다」) 등급을 못 읽은 행이 자동 실행 대상이 된다.
    ★`ActionRejected` 라 코어가 savepoint 를 통째로 되돌리고 `action_rejected` 로
      `escalated` 시킨다 — 원장도 우리 예약도 **반쯤 바뀐 채 남지 않는다**
      (wiki `actions/approval.md` 「승인 뒤 실행」).
    ★이 문은 **승인 뒤**에도 선다. 승인은 "이 변경을 해도 된다" 이지 "실제 업체에
      직접 질러도 된다" 가 아니다 — 실제 업체 건은 변경 링크로 인계한다(v11 §4-C).
    """
    tier = supplier.get("tier")
    if tier != SIMULATED_TIER:
        raise ActionRejected(
            f"supplier tier {tier!r} is not {SIMULATED_TIER!r} — a real supplier ledger is never "
            f"changed by the automatic branch; this booking goes to a human (v11 §4-C, DoD-14)")


def _lock_supplier(conn: Any, *, tenant_id: str, booking_id: str) -> dict[str, Any]:
    """공급자 원장 한 줄을 **등급까지** 읽어 잠근다.

    ★등급을 판정 시점이 아니라 **적용 시점에** 읽는다. 제안을 만든 뒤 등급이
      `simulated` → `real` 로 바뀌었을 수 있고, 그 사이 값으로 실행하면 게이트가
      한 틱 뒤처진다. `FOR UPDATE` 라 읽은 뒤 같은 트랜잭션 안에서 안 바뀐다.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT supplier, supplier_ref, status, tier FROM supplier_bookings "
                    "WHERE tenant_id=%s AND booking_id=%s FOR UPDATE", (tenant_id, booking_id))
        row = cur.fetchone()
    if row is None:
        # ★공급자 원장에 없는 예약을 우리 쪽만 취소하면 두 기록이 어긋난 채 「취소됨」이라 답한다.
        raise ActionRejected("no supplier record for this booking")
    return dict(zip(("supplier", "supplier_ref", "status", "tier"), row))


def _booking_id(arguments: Mapping[str, Any]) -> str:
    raw = arguments.get("booking_id")
    if not raw:
        raise ActionRejected("booking action needs booking_id")
    try:
        return str(UUID(str(raw)))
    except (TypeError, ValueError) as exc:
        raise ActionRejected(f"booking_id is malformed: {exc}") from exc


def _lock_booking(conn: Any, *, tenant_id: str, customer_id: UUID, booking_id: str) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute("SELECT booking_no, status, locked FROM bookings WHERE tenant_id=%s AND customer_id=%s "
                    "AND booking_id=%s FOR UPDATE", (tenant_id, customer_id, booking_id))
        row = cur.fetchone()
    if row is None:
        raise ActionRejected("booking not found for this customer")
    booking = dict(zip(("booking_no", "status", "locked"), row))
    if booking["locked"]:
        raise ActionRejected("locked booking (lodging/flight) is not changed here")
    return booking


class BookingCancel:
    action_type = "booking.cancel"
    auto_apply = False

    def subject(self, arguments: Mapping[str, Any]) -> str:
        return _booking_id(arguments)

    def apply(self, conn: Any, *, tenant_id: str, customer_id: UUID, case_id: UUID,
              arguments: Mapping[str, Any]) -> AppliedAction:
        booking_id = _booking_id(arguments)
        booking = _lock_booking(conn, tenant_id=tenant_id, customer_id=customer_id, booking_id=booking_id)
        if booking["status"] == "cancelled":
            raise ActionConflict("booking is already cancelled")
        supplier = _lock_supplier(conn, tenant_id=tenant_id, booking_id=booking_id)
        # ★게이트가 먼저다. 이 줄 아래로만 공급자 원장을 바꾸는 SQL 이 올 수 있고,
        #   `tests/architecture/test_supplier_tier_gate.py` 가 순서까지 센다.
        require_simulated_tier(supplier)
        with conn.cursor() as cur:
            cur.execute("UPDATE supplier_bookings SET status='cancelled' WHERE tenant_id=%s AND booking_id=%s",
                        (tenant_id, booking_id))
            cur.execute("UPDATE bookings SET status='cancelled' WHERE tenant_id=%s AND booking_id=%s",
                        (tenant_id, booking_id))
        return AppliedAction(result_ref=f"mock-supplier:{supplier['supplier']}:{supplier['supplier_ref']}:cancelled",
                             summary={"booking_no": booking["booking_no"], "status": "cancelled",
                                      "supplier_tier": supplier["tier"]})


class BookingChange:
    """★공급자 원장을 **어느 등급에서도** 건드리지 않는다 — 그래서 등급 게이트가 없다.

    바꿀 내용이 인자에 없어 지어낼 수 없고, 하는 일은 우리 예약을 `change_requested` 로
    두고 사람에게 넘기는 것뿐이다. `tests/architecture/test_supplier_tier_gate.py` 는
    「공급자 원장을 바꾸는 SQL」이 있는 자리에만 게이트를 요구한다 — 여기엔 그 SQL 이 없다.
    """

    action_type = "booking.change"
    auto_apply = False

    def subject(self, arguments: Mapping[str, Any]) -> str:
        return _booking_id(arguments)

    def apply(self, conn: Any, *, tenant_id: str, customer_id: UUID, case_id: UUID,
              arguments: Mapping[str, Any]) -> AppliedAction:
        booking_id = _booking_id(arguments)
        booking = _lock_booking(conn, tenant_id=tenant_id, customer_id=customer_id, booking_id=booking_id)
        if booking["status"] == "cancelled":
            raise ActionConflict("booking is cancelled — nothing to change")
        with conn.cursor() as cur:
            cur.execute("UPDATE bookings SET status='change_requested' WHERE tenant_id=%s AND booking_id=%s",
                        (tenant_id, booking_id))
        handoff = OutboxMessage(topic=HANDOFF_TOPIC, dedupe_key=f"{booking_id}:{case_id}",
                                payload={"booking_id": booking_id, "booking_no": booking["booking_no"],
                                         "case_id": str(case_id), "reason": arguments.get("reason")})
        return AppliedAction(result_ref=f"handoff:{booking['booking_no']}",
                             summary={"booking_no": booking["booking_no"], "status": "change_requested"},
                             outbox=[handoff])


APPROVED_HANDLERS = (BookingCancel(), BookingChange())

__all__ = ["APPROVED_HANDLERS", "BookingCancel", "BookingChange", "HANDOFF_TOPIC",
           "SIMULATED_TIER", "require_simulated_tier"]
