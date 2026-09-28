# -*- coding: utf-8 -*-
"""ActionProposal 근거 대조 (v7 §9-E · DoD-24) — 여행 도메인.

★검사하는 것은 "함수가 돈다" 가 아니라 **"지어낸 값이 막히는가"** 다.
  5만원 예약에 7만원 환불을 제안하는 경우를 그대로 넣는다.

★과잉 차단도 결함이다. 정상 제안이 막히면 시스템이 아무 일도 못 한다.
  그래서 "막는다" 와 "안 막는다" 를 같이 검사한다.

★엔진(`app/core/verification.py`)은 **한 줄도 안 바뀌었다.** 커머스 →  여행
  교체로 바뀐 것은 이 파일이 주입하는 **선언**뿐이다
  (`app/modules/travel_ops/verification_policy.py`). 코어가 도메인을 모른다는
  주장을 실제로 시험하는 자리다 — 커머스판은 같은 엔진에 `orders`·`shipments`
  를 주입했었다.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.verification import Facts, verify_proposal
from app.modules.travel_ops.verification_policy import TRAVEL_OPS_POLICY

BOOKING = "11111111-1111-4111-8111-111111111111"
OTHER_BOOKING = "22222222-2222-4222-8222-222222222222"
SUPPLIER_BOOKING = "33333333-3333-4333-8333-333333333333"

POLICY = TRAVEL_OPS_POLICY


def facts(**over) -> Facts:
    collections = {
        "bookings": {BOOKING: {"booking_id": BOOKING, "booking_no": "BK-1001",
                               "kind": "activity", "status": "confirmed",
                               "party_size": 2, "capacity": 3,
                               "amount_cents": 5_000_000, "locked": False}},
        "supplier_bookings": {SUPPLIER_BOOKING: {
            "supplier_booking_id": SUPPLIER_BOOKING, "booking_id": BOOKING,
            "supplier": "S", "supplier_ref": "SR-1", "status": "confirmed"}},
    }
    base = dict(collections=collections, evidence_ids=frozenset({"ev-1", "ev-2"}))
    base.update(over)
    return Facts(**base)


def verify(**kwargs):
    kwargs.setdefault("policy", POLICY)
    return verify_proposal(**kwargs)


def fields(problems) -> set[str]:
    return {p.field for p in problems}


# ── 막아야 하는 것 ────────────────────────────────────────────────────────────
def test_refund_larger_than_the_booking_amount_is_rejected():
    """★5만원 예약에 7만원 환불 제안."""
    problems = verify(
        arguments={"booking_id": BOOKING, "refund_amount": 70_000},
        rationale_evidence_ids=["ev-1"], facts=facts())
    assert "refund_amount" in fields(problems)
    assert "실제 값보다 큰" in problems[0].reason
    # ★원문 금액이 감사 기록에 남지 않는다
    assert "70000" not in problems[0].actual_digest
    assert "5000000" not in problems[0].expected_digest


def test_nonexistent_booking_id_is_rejected():
    problems = verify(
        arguments={"booking_id": OTHER_BOOKING, "refund_amount": 100},
        rationale_evidence_ids=["ev-1"], facts=facts())
    assert "booking_id" in fields(problems)


def test_supplier_booking_owned_by_someone_else_is_rejected():
    """★facts 는 tenant/customer 범위로만 조회된다. 없으면 남의 것이다."""
    problems = verify(
        arguments={"supplier_booking_id": "99999999-9999-4999-8999-999999999999"},
        rationale_evidence_ids=["ev-1"], facts=facts())
    assert "supplier_booking_id" in fields(problems)


def test_party_size_over_the_capacity_is_rejected():
    """★수량 규칙이 금액 전용이 아니다 — 정원 3인 예약에 5인 제안."""
    problems = verify(
        arguments={"booking_id": BOOKING, "party_size": 5},
        rationale_evidence_ids=["ev-1"], facts=facts())
    assert "party_size" in fields(problems)


def test_unverifiable_identifier_is_rejected_not_ignored():
    """★바우처 테이블이 아직 없다. '확인 못 함' 을 '괜찮음' 으로 바꾸지 않는다."""
    problems = verify(
        arguments={"voucher_id": "VCH-1"}, rationale_evidence_ids=["ev-1"], facts=facts())
    assert "voucher_id" in fields(problems)
    assert "확인할 수 없다" in problems[0].reason


def test_refund_without_a_target_booking_is_rejected():
    """무엇에 대한 환불인지 모르면 확인할 수 없다."""
    problems = verify(
        arguments={"refund_amount": 10_000}, rationale_evidence_ids=["ev-1"], facts=facts())
    assert "refund_amount" in fields(problems)


def test_evidence_not_in_the_context_pack_is_rejected():
    problems = verify(
        arguments={"booking_id": BOOKING, "refund_amount": 10_000},
        rationale_evidence_ids=["ev-1", "ev-does-not-exist"], facts=facts())
    assert "evidence_ids" in fields(problems)


def test_failed_fact_lookup_rejects_everything():
    """★사실을 못 읽었으면 통과시키지 않는다. 모르는 것과 괜찮은 것은 다르다."""
    problems = verify(
        arguments={"booking_id": BOOKING, "refund_amount": 100},
        rationale_evidence_ids=["ev-1"], facts=Facts(loaded=False))
    assert problems and problems[0].field == "__facts__"


def test_zero_or_negative_refund_is_rejected():
    problems = verify(
        arguments={"booking_id": BOOKING, "refund_amount": 0},
        rationale_evidence_ids=["ev-1"], facts=facts())
    assert "refund_amount" in fields(problems)


@pytest.mark.parametrize("amount", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_refund_amount_is_rejected_without_crashing(amount):
    problems = verify(
        arguments={"booking_id": BOOKING, "refund_amount": amount},
        rationale_evidence_ids=["ev-1"], facts=facts())

    assert "refund_amount" in fields(problems)


def test_commerce_vocabulary_is_not_silently_accepted():
    """★옛 커머스 어휘(`order_id`)는 여기서 '선언되지 않은 필드' 로 거부된다.

    엔진이 커머스 어휘를 알고 있었다면 이게 조용히 통과했을 것이다. 도메인을
    갈아끼웠는데 옛 어휘가 그대로 도는지 보는 검사이기도 하다.
    """
    problems = verify(
        arguments={"order_id": "ord-1"}, rationale_evidence_ids=["ev-1"], facts=facts())
    assert "order_id" in fields(problems)
    assert any("선언되지 않은" in p.reason for p in problems)


def test_every_problem_is_reported_not_just_the_first():
    """★첫 번째에서 멈추면 나머지를 다음 라운드에나 발견한다."""
    problems = verify(
        arguments={"booking_id": OTHER_BOOKING, "voucher_id": "VCH-1",
                   "supplier_booking_id": "99999999-9999-4999-8999-999999999999"},
        rationale_evidence_ids=["nope"], facts=facts())
    assert {"booking_id", "voucher_id", "supplier_booking_id",
            "evidence_ids"} <= fields(problems)


# ── 막으면 안 되는 것 ─────────────────────────────────────────────────────────
def test_a_truthful_refund_passes():
    """★과잉 차단은 결함이다. 5만원 예약에 5만원 환불은 정상이다."""
    assert verify(
        arguments={"booking_id": BOOKING, "refund_amount": 50_000, "currency": "KRW"},
        rationale_evidence_ids=["ev-1", "ev-2"], facts=facts()) == []


def test_partial_refund_passes():
    assert verify(
        arguments={"booking_id": BOOKING, "refund_amount": 10_000},
        rationale_evidence_ids=["ev-1"], facts=facts()) == []


def test_party_size_within_the_capacity_passes():
    assert verify(
        arguments={"booking_id": BOOKING, "party_size": 2},
        rationale_evidence_ids=["ev-1"], facts=facts()) == []


def test_cents_and_won_are_not_confused():
    """★`refund_amount` 는 원, `refund_amount_cents` 는 cents."""
    assert verify(
        arguments={"booking_id": BOOKING, "refund_amount_cents": 5_000_000},
        rationale_evidence_ids=["ev-1"], facts=facts()) == []
    # 같은 숫자를 원으로 주면 100배라 예약 금액을 넘는다
    assert verify(
        arguments={"booking_id": BOOKING, "refund_amount": 5_000_000},
        rationale_evidence_ids=["ev-1"], facts=facts()) != []


def test_proposal_without_identifiers_or_amounts_passes():
    """식별자도 금액도 없는 제안(예: 안내 발송)은 대조할 것이 없다."""
    assert verify(
        arguments={"template": "apology"}, rationale_evidence_ids=["ev-1"], facts=facts()) == []
