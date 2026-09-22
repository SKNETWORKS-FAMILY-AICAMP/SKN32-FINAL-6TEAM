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
                     **인계**한다: 예약을 `change_requested` 로 두고 운영 인계 메시지를 바깥함에 넣는다.
                     `[2026-09-22]` 그 메시지에 **변경 링크**(`change_link.change_url`)를 싣는다 —
                     바뀔 항목·대안·차액을 고객이 그 화면에서 보고 업체 쪽에서 직접 진행한다
                     (v11 §4-C · §12 DoD-16·17)

  provider_ref 는 `mock-supplier:` 로 시작한다 — 실제 공급자와 섞어 읽지 않게.

★`[2026-09-22]` **공급자 등급 게이트가 생겼다**(v11 §12 DoD-14·15, 마이그레이션 017).
  전에는 「Mock 공급자 한정」이 **주석에만** 있었고 코드는 등급을 보지 않았다 — 실제 공급자
  행이 한 줄 들어오면 승인 한 번에 그 원장을 고쳤을 것이다. 이제:

    supplier_bookings.tier == 'simulated'   공급자 원장을 바꾼다(시연 자동 실행 분기)
    그 밖(기본값 'real')                    ★원장을 **한 글자도 건드리지 않고** ActionRejected —
                                            코어가 전부 되돌리고 `action_rejected` 로 사람에게 넘긴다

  등급을 모르거나 읽지 못하면 실행하지 않는다. **모름은 'simulated' 가 아니다.**

★`[2026-09-22]` **위임 범위 게이트가 하나 더 생겼다**(v11 §12 DoD-18·19, 마이그레이션 019).
  등급 게이트는 「누구의 원장인가」만 답한다 — 「얼마까지·무엇에·몇 번까지 맡겼나」는 아무 데도
  없었고, 등급이 `simulated` 이면 금액이 얼마든 몇 번이든 원장이 바뀌었다. 이제 문이 둘이다:

    1) `require_simulated_tier(supplier)`   공급자 등급          (017)
    2) `delegation.require(...)`            금액·종류·횟수·되돌림 (019 · `delegation.py`)

★`[2026-09-22]` **실행 장부**를 채운다(DoD-20) — 무엇을(작업 종류·대상 id)·왜(`reason`)·
  얼마에(`amount_cents` + 그 금액을 **어디서 읽었는지**)·되돌림 기한. 모르는 금액은
  **비운다**(NULL = 「확인되지 않았다」). 되돌릴 때 돌아갈 상태(`prior_state`)도 같이 적는다 —
  없으면 되돌림이 상태를 지어내야 한다.

★`[2026-09-22]` **되돌림 적용기**가 생겼다(`BookingRevert`, DoD-21). 되돌림 시도는 자기
  `action_requests` 행으로 상태가 남고, 실패하면 코어가 `escalated` 로 사람에게 넘긴다 —
  조용히 삼키지 않는다.

★적용 순간에 다시 확인한다 — 이 고객의 예약인가 · 잠긴 예약(Lodging/Flight)이 아닌가 ·
  이미 취소된 것을 또 취소하지 않는가 · **공급자가 시뮬레이션 등급인가** · **위임 범위 안인가**.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping
from uuid import UUID

from app.core.actions import ActionConflict, ActionRejected, AppliedAction
from app.core.transition import OutboxMessage

from . import delegation
from .change_link import change_url

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
    """★`[2026-09-22]` `kind`·`starts_at`·`amount_cents` 를 **같은 잠금 안에서** 함께 읽는다.
    위임 범위 판정(종류·금액·무료 취소 구간)이 쓰는 값이라, 따로 읽으면 판정과 적용 사이에
    바뀔 수 있다."""
    with conn.cursor() as cur:
        cur.execute("SELECT booking_no, status, locked, kind, starts_at, amount_cents FROM bookings "
                    "WHERE tenant_id=%s AND customer_id=%s AND booking_id=%s FOR UPDATE",
                    (tenant_id, customer_id, booking_id))
        row = cur.fetchone()
    if row is None:
        raise ActionRejected("booking not found for this customer")
    booking = dict(zip(("booking_no", "status", "locked", "kind", "starts_at", "amount_cents"), row))
    booking["booking_id"] = booking_id
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
        # ★`[2026-09-22]` 두 번째 문 — 위임 범위(v11 §12 DoD-18·19). 등급이 「누구의 원장인가」
        #   라면 이쪽은 「얼마까지·무엇에·몇 번까지 맡겼나」다. 범위 밖이면 `ActionRejected` 라
        #   코어가 전부 되돌리고 사람에게 넘긴다. ★**철회도 여기서 걸린다** — 판정을 적용
        #   순간에 하므로 승인과 적용 사이에 철회된 건은 열리지 않는다.
        scope = delegation.require(conn, tenant_id=tenant_id, customer_id=customer_id, booking=booking)
        with conn.cursor() as cur:
            cur.execute("UPDATE supplier_bookings SET status='cancelled' WHERE tenant_id=%s AND booking_id=%s",
                        (tenant_id, booking_id))
            cur.execute("UPDATE bookings SET status='cancelled' WHERE tenant_id=%s AND booking_id=%s",
                        (tenant_id, booking_id))
        return AppliedAction(
            result_ref=f"mock-supplier:{supplier['supplier']}:{supplier['supplier_ref']}:cancelled",
            summary={"booking_no": booking["booking_no"], "status": "cancelled",
                     "supplier_tier": supplier["tier"]},
            # ── 실행 장부(DoD-20) — 무엇을(작업 종류·booking_id) 외의 셋 ──────────────
            #   ★금액은 예약 금액이고 출처를 함께 적는다. 위약금은 우리가 모른다 —
            #     모르는 것을 「0원」이라고 적지 않는다(비우는 것이 사실이다).
            amount_cents=scope.amount_cents, amount_source=scope.amount_source,
            reason=arguments.get("reason"), revert_deadline=scope.revert_deadline,
            delegation=scope.record(),
            # ★되돌릴 때 **무엇으로** 돌아가야 하나. 지금 값을 적어 둔다 — 안 적으면
            #   되돌림이 `confirmed` 를 지어내야 한다(`requested`·`changed` 일 수도 있다).
            prior_state={"booking_status": booking["status"], "supplier_status": supplier["status"]})


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
        # ★`[2026-09-22]` **변경 링크를 함께 싣는다**(v11 §12 DoD-16). 전에는 인계 메시지가
        #   「이 예약을 바꿔야 한다」까지만 말하고 고객이 무엇을 보고 어디서 진행하는지가 없었다.
        #   링크는 비밀 키로 **계산**한 것이라 이 트랜잭션이 DB 를 더 읽지 않는다 — 화면이 열릴 때
        #   그때의 최신 값을 읽는다(계획서 링크와 같은 규칙, v11 §6-A 「상태의 정본은 링크」).
        #   ☆무엇을 왜 넘겼는지의 기록이 이 한 줄이다 — 업체 예약을 우리가 바꾸지 않으므로
        #     남는 것은 예약 상태(`change_requested`)와 이 메시지뿐이다.
        url = change_url(tenant_id, booking_id)
        handoff = OutboxMessage(topic=HANDOFF_TOPIC, dedupe_key=f"{booking_id}:{case_id}",
                                payload={"booking_id": booking_id, "booking_no": booking["booking_no"],
                                         "case_id": str(case_id), "reason": arguments.get("reason"),
                                         "change_url": url,
                                         "text": f"{booking['booking_no']} 예약은 업체에서 직접 "
                                                 f"변경해 주세요. 바뀔 항목·대안·차액: {url}"})
        return AppliedAction(result_ref=f"handoff:{booking['booking_no']}",
                             summary={"booking_no": booking["booking_no"], "status": "change_requested",
                                      "change_url": url},
                             outbox=[handoff],
                             # ★장부의 「왜」는 적는다. 「얼마에」는 **비운다** — 차액은 업체가 정하고
                             #   우리는 아직 모른다(NULL = 「확인되지 않았다」). 되돌림 기한도 없다 —
                             #   우리가 원장을 바꾸지 않았으므로 우리가 되돌릴 것이 없다.
                             reason=arguments.get("reason"))


def _last_automatic_cancel(conn: Any, *, tenant_id: str, booking_id: str) -> dict[str, Any] | None:
    """이 예약에 **성공한** 자동 취소의 장부 한 줄. 되돌림이 무엇을 되돌리는지의 근거다.

    ★`action_requests` 는 코어의 표지만 이 파일은 Team 이 아니라 **적용기**다 — 이미
      `bookings`·`supplier_bookings` 에 직접 SQL 을 쓴다(Team 규율 검사는 manifest 가 있는
      파일만 본다). 되돌림 기한과 돌아갈 상태가 그 표에 있어서 여기서 읽는다.
    ★`delegation_json IS NOT NULL` — 위임을 써서 실행된 건만 되돌림 대상이다.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT action_id, revert_deadline, prior_state_json, amount_cents, amount_source "
                    "FROM action_requests WHERE tenant_id=%s AND action_type='booking.cancel' "
                    "AND status='succeeded' AND delegation_json IS NOT NULL "
                    "AND arguments_json->>'booking_id' = %s "
                    "ORDER BY created_at DESC LIMIT 1", (tenant_id, str(booking_id)))
        row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(("action_id", "revert_deadline", "prior_state", "amount_cents", "amount_source"), row))


class BookingRevert:
    """자동 실행을 **되돌린다** — v11 §12 DoD-21 · wiki `teams/booking-handoff.md` 「되돌림」.

    ★왜 위임 범위 게이트를 다시 세우지 않나. 되돌림은 위임을 **쓰는** 것이 아니라 위임으로
      한 일을 **무르는** 것이다. 철회했다고 되돌림까지 막으면, 철회한 순간 이미 나간 변경을
      원상복구할 길이 사라진다 — 돈이 나가는 방향이 아니라 되돌리는 방향이므로 연다.
      대신 **되돌림 기한**만 본다(장부에 적힌 그 건의 기한이다. 지금 설정으로 다시 계산하지
      않는다 — 설정을 바꿔 지난 건의 기한을 늘리거나 줄이면 장부가 거짓이 된다).
    ★공급자 원장을 바꾸므로 **등급 게이트는 그대로 선다.**
    ★되돌림 실패는 조용히 삼키지 않는다. `ActionRejected` → 코어가 이 되돌림 요청의
      `action_requests` 행을 `failed` 로 적고 Case 를 `escalated` 로 보낸다(사유는
      `case_events` 에 append-only 로 남는다). **되돌림 시도가 상태로 남는다.**
    """

    action_type = "booking.revert"
    auto_apply = False

    def subject(self, arguments: Mapping[str, Any]) -> str:
        return _booking_id(arguments)

    def apply(self, conn: Any, *, tenant_id: str, customer_id: UUID, case_id: UUID,
              arguments: Mapping[str, Any]) -> AppliedAction:
        booking_id = _booking_id(arguments)
        booking = _lock_booking(conn, tenant_id=tenant_id, customer_id=customer_id, booking_id=booking_id)
        original = _last_automatic_cancel(conn, tenant_id=tenant_id, booking_id=booking_id)
        if original is None:
            raise ActionRejected("no automatic execution to revert for this booking")
        if booking["status"] != "cancelled":
            # 되돌릴 대상이 그새 다른 상태가 됐다 — 재계산 없이 다시 밀지 않는다.
            raise ActionConflict(f"booking is {booking['status']!r}, not 'cancelled' — nothing to revert")
        prior = original["prior_state"] or {}
        if not prior.get("booking_status") or not prior.get("supplier_status"):
            # ★돌아갈 상태를 모른다. **지어내지 않는다** — 사람이 업체와 맞춘다.
            raise ActionRejected("the prior state of this booking was not recorded — a human must "
                                 "restore it with the supplier (v11 §12 DoD-21)")
        deadline, now = original["revert_deadline"], datetime.now(UTC)
        if deadline is None or deadline <= now:
            raise ActionRejected(
                f"revert deadline passed: deadline={deadline.isoformat() if deadline else 'not recorded'} "
                f"now={now.isoformat()} — a human must handle this with the supplier (DoD-21)")
        supplier = _lock_supplier(conn, tenant_id=tenant_id, booking_id=booking_id)
        # ★등급 게이트가 먼저다 — 되돌림도 공급자 원장을 바꾼다.
        require_simulated_tier(supplier)
        with conn.cursor() as cur:
            cur.execute("UPDATE supplier_bookings SET status=%s WHERE tenant_id=%s AND booking_id=%s",
                        (prior["supplier_status"], tenant_id, booking_id))
            cur.execute("UPDATE bookings SET status=%s WHERE tenant_id=%s AND booking_id=%s",
                        (prior["booking_status"], tenant_id, booking_id))
        return AppliedAction(
            result_ref=f"mock-supplier:{supplier['supplier']}:{supplier['supplier_ref']}:reverted",
            summary={"booking_no": booking["booking_no"], "status": prior["booking_status"],
                     "reverted_action_id": str(original["action_id"])},
            # ★금액은 원래 건의 금액을 **그대로** 옮긴다(새로 계산하지 않는다).
            #   `delegation` 은 비운다 — 되돌림은 위임 한도를 쓰지 않으므로 누적 합에 들어가면
            #   「취소 → 되돌림」을 반복해 한도를 두 배로 쓰게 된다(`delegation._spent_cents` 참고).
            amount_cents=original["amount_cents"], amount_source=original["amount_source"],
            reason=arguments.get("reason"),
            prior_state={"booking_status": "cancelled", "supplier_status": "cancelled",
                         "reverted_action_id": str(original["action_id"])})


APPROVED_HANDLERS = (BookingCancel(), BookingChange(), BookingRevert())

__all__ = ["APPROVED_HANDLERS", "BookingCancel", "BookingChange", "BookingRevert", "HANDOFF_TOPIC",
           "SIMULATED_TIER", "require_simulated_tier"]
