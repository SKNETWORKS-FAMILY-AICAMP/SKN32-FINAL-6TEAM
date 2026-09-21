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

★적용 순간에 다시 확인한다 — 이 고객의 예약인가 · 잠긴 예약(Lodging/Flight)이 아닌가 ·
  이미 취소된 것을 또 취소하지 않는가.
"""
from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from app.core.actions import ActionConflict, ActionRejected, AppliedAction
from app.core.transition import OutboxMessage

HANDOFF_TOPIC = "booking.handoff"


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
        with conn.cursor() as cur:
            cur.execute("UPDATE supplier_bookings SET status='cancelled' WHERE tenant_id=%s AND booking_id=%s "
                        "RETURNING supplier, supplier_ref", (tenant_id, booking_id))
            supplier = cur.fetchone()
            if supplier is None:
                # ★공급자 원장에 없는 예약을 우리 쪽만 취소하면 두 기록이 어긋난 채 「취소됨」이라 답한다.
                raise ActionRejected("no supplier record for this booking")
            cur.execute("UPDATE bookings SET status='cancelled' WHERE tenant_id=%s AND booking_id=%s",
                        (tenant_id, booking_id))
        return AppliedAction(result_ref=f"mock-supplier:{supplier[0]}:{supplier[1]}:cancelled",
                             summary={"booking_no": booking["booking_no"], "status": "cancelled"})


class BookingChange:
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

__all__ = ["APPROVED_HANDLERS", "BookingCancel", "BookingChange", "HANDOFF_TOPIC"]
