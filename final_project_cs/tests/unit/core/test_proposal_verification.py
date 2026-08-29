"""ActionProposal 근거 대조 (v7 §9-E · DoD-24) — 커머스 도메인.

★검사하는 것은 "함수가 돈다" 가 아니라 **"지어낸 값이 막히는가"** 다.
  5만원 주문에 7만원 환불을 제안하는 경우를 그대로 넣는다.

★과잉 차단도 결함이다. 정상 제안이 막히면 시스템이 아무 일도 못 한다.
  그래서 "막는다" 와 "안 막는다" 를 같이 검사한다.

★엔진(`app/core/verification.py`)은 sample 에서 **한 줄도 안 바뀌었다.**
  바뀐 것은 이 파일이 주입하는 **선언**뿐이다.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.verification import Facts, verify_proposal
from app.modules.customer_ops.verification_policy import CUSTOMER_OPS_POLICY

ORDER = "11111111-1111-4111-8111-111111111111"
OTHER_ORDER = "22222222-2222-4222-8222-222222222222"
SHIPMENT = "33333333-3333-4333-8333-333333333333"

POLICY = CUSTOMER_OPS_POLICY


def facts(**over) -> Facts:
    collections = {
        "orders": {ORDER: {"order_id": ORDER, "order_no": "ORD-1001",
                           "total_cents": 5_000_000, "item_count": 3, "status": "delivered"}},
        "shipments": {SHIPMENT: {"shipment_id": SHIPMENT, "order_id": ORDER,
                                 "carrier": "CJ", "status": "delivered"}},
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
def test_refund_larger_than_the_order_total_is_rejected():
    """★5만원 주문에 7만원 환불 제안."""
    problems = verify(
        arguments={"order_id": ORDER, "refund_amount": 70_000},
        rationale_evidence_ids=["ev-1"], facts=facts())
    assert "refund_amount" in fields(problems)
    assert "실제 값보다 큰" in problems[0].reason
    # ★원문 금액이 감사 기록에 남지 않는다
    assert "70000" not in problems[0].actual_digest
    assert "5000000" not in problems[0].expected_digest


def test_nonexistent_order_id_is_rejected():
    problems = verify(
        arguments={"order_id": OTHER_ORDER, "refund_amount": 100},
        rationale_evidence_ids=["ev-1"], facts=facts())
    assert "order_id" in fields(problems)


def test_shipment_owned_by_someone_else_is_rejected():
    """★facts 는 tenant/customer 범위로만 조회된다. 없으면 남의 것이다."""
    problems = verify(
        arguments={"shipment_id": "99999999-9999-4999-8999-999999999999"},
        rationale_evidence_ids=["ev-1"], facts=facts())
    assert "shipment_id" in fields(problems)


def test_return_quantity_over_the_order_is_rejected():
    """★수량 규칙이 금액 전용이 아니다 — 3개 주문에 5개 반품."""
    problems = verify(
        arguments={"order_id": ORDER, "return_quantity": 5},
        rationale_evidence_ids=["ev-1"], facts=facts())
    assert "return_quantity" in fields(problems)


def test_unverifiable_identifier_is_rejected_not_ignored():
    """★쿠폰 테이블이 아직 없다. '확인 못 함' 을 '괜찮음' 으로 바꾸지 않는다."""
    problems = verify(
        arguments={"coupon_id": "CPN-1"}, rationale_evidence_ids=["ev-1"], facts=facts())
    assert "coupon_id" in fields(problems)
    assert "확인할 수 없다" in problems[0].reason


def test_refund_without_a_target_order_is_rejected():
    """무엇에 대한 환불인지 모르면 확인할 수 없다."""
    problems = verify(
        arguments={"refund_amount": 10_000}, rationale_evidence_ids=["ev-1"], facts=facts())
    assert "refund_amount" in fields(problems)


def test_evidence_not_in_the_context_pack_is_rejected():
    problems = verify(
        arguments={"order_id": ORDER, "refund_amount": 10_000},
        rationale_evidence_ids=["ev-1", "ev-does-not-exist"], facts=facts())
    assert "evidence_ids" in fields(problems)


def test_failed_fact_lookup_rejects_everything():
    """★사실을 못 읽었으면 통과시키지 않는다. 모르는 것과 괜찮은 것은 다르다."""
    problems = verify(
        arguments={"order_id": ORDER, "refund_amount": 100},
        rationale_evidence_ids=["ev-1"], facts=Facts(loaded=False))
    assert problems and problems[0].field == "__facts__"


def test_zero_or_negative_refund_is_rejected():
    problems = verify(
        arguments={"order_id": ORDER, "refund_amount": 0},
        rationale_evidence_ids=["ev-1"], facts=facts())
    assert "refund_amount" in fields(problems)


@pytest.mark.parametrize("amount", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_refund_amount_is_rejected_without_crashing(amount):
    problems = verify(
        arguments={"order_id": ORDER, "refund_amount": amount},
        rationale_evidence_ids=["ev-1"], facts=facts())

    assert "refund_amount" in fields(problems)


def test_subscription_vocabulary_is_not_silently_accepted():
    """★sample 의 어휘(`payment_id`)는 여기서 '선언되지 않은 필드' 로 거부된다.

    엔진이 구독 어휘를 알고 있었다면 이게 조용히 통과했을 것이다.
    """
    problems = verify(
        arguments={"payment_id": "pay-1"}, rationale_evidence_ids=["ev-1"], facts=facts())
    assert "payment_id" in fields(problems)
    assert any("선언되지 않은" in p.reason for p in problems)


def test_every_problem_is_reported_not_just_the_first():
    """★첫 번째에서 멈추면 나머지를 다음 라운드에나 발견한다."""
    problems = verify(
        arguments={"order_id": OTHER_ORDER, "coupon_id": "CPN-1",
                   "shipment_id": "99999999-9999-4999-8999-999999999999"},
        rationale_evidence_ids=["nope"], facts=facts())
    assert {"order_id", "coupon_id", "shipment_id", "evidence_ids"} <= fields(problems)


# ── 막으면 안 되는 것 ─────────────────────────────────────────────────────────
def test_a_truthful_refund_passes():
    """★과잉 차단은 결함이다. 5만원 주문에 5만원 환불은 정상이다."""
    assert verify(
        arguments={"order_id": ORDER, "refund_amount": 50_000, "currency": "KRW"},
        rationale_evidence_ids=["ev-1", "ev-2"], facts=facts()) == []


def test_partial_refund_passes():
    assert verify(
        arguments={"order_id": ORDER, "refund_amount": 10_000},
        rationale_evidence_ids=["ev-1"], facts=facts()) == []


def test_return_within_the_ordered_quantity_passes():
    assert verify(
        arguments={"order_id": ORDER, "return_quantity": 2},
        rationale_evidence_ids=["ev-1"], facts=facts()) == []


def test_cents_and_won_are_not_confused():
    """★`refund_amount` 는 원, `refund_amount_cents` 는 cents."""
    assert verify(
        arguments={"order_id": ORDER, "refund_amount_cents": 5_000_000},
        rationale_evidence_ids=["ev-1"], facts=facts()) == []
    # 같은 숫자를 원으로 주면 100배라 주문 총액을 넘는다
    assert verify(
        arguments={"order_id": ORDER, "refund_amount": 5_000_000},
        rationale_evidence_ids=["ev-1"], facts=facts()) != []


def test_proposal_without_identifiers_or_amounts_passes():
    """식별자도 금액도 없는 제안(예: 안내 발송)은 대조할 것이 없다."""
    assert verify(
        arguments={"template": "apology"}, rationale_evidence_ids=["ev-1"], facts=facts()) == []
