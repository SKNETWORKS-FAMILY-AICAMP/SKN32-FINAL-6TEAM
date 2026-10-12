"""ActionProposal 근거 대조 (v7 §9-E · DoD-24).

★검사하는 것은 "함수가 돈다" 가 아니라 **"지어낸 값이 막히는가"** 다.
  v7 이 예시로 든 상황을 그대로 넣는다 —
  실제 결제액이 30,000원인데 LLM 이 "50,000원 환불" 을 제안하는 경우.

★과잉 차단도 결함이다. 정상 제안이 막히면 시스템이 아무 일도 못 한다.
  그래서 "막는다" 와 "안 막는다" 를 같이 검사한다.
"""
from __future__ import annotations

from acop_basement.core.verification import Facts, verify_proposal
from app.modules.customer_ops.verification_policy import CUSTOMER_OPS_POLICY

PAYMENT = "11111111-1111-4111-8111-111111111111"
OTHER_PAYMENT = "22222222-2222-4222-8222-222222222222"
SUBSCRIPTION = "33333333-3333-4333-8333-333333333333"

#: ★도메인 선언을 주입한다. basement 는 어휘를 모른다 —
#:  이 테스트가 그 어휘를 쓰는 것은 **도메인 선언을 검사**하기 때문이다.
POLICY = CUSTOMER_OPS_POLICY


def facts(**over) -> Facts:
    collections = {
        "payments": {PAYMENT: {"payment_id": PAYMENT, "amount_cents": 3_000_000,
                               "status": "paid", "subscription_id": SUBSCRIPTION}},
        "subscriptions": {SUBSCRIPTION: {"subscription_id": SUBSCRIPTION, "plan": "pro",
                                         "status": "cancelled"}},
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
def test_amount_larger_than_the_actual_payment_is_rejected():
    """★v7 §9-E 의 예시 — 3만원 결제에 5만원 환불 제안."""
    problems = verify(
        arguments={"payment_id": PAYMENT, "amount": 50_000},
        rationale_evidence_ids=["ev-1"], facts=facts())
    assert "amount" in fields(problems)
    # ★문구도 중립이다 — basement 는 "결제액" 을 모른다
    assert "실제 값보다 큰" in problems[0].reason
    # ★원문 금액이 감사 기록에 남지 않는다
    assert "50000" not in problems[0].actual_digest
    assert "3000000" not in problems[0].expected_digest


def test_nonexistent_payment_id_is_rejected():
    problems = verify(
        arguments={"payment_id": OTHER_PAYMENT, "amount": 100},
        rationale_evidence_ids=["ev-1"], facts=facts())
    assert "payment_id" in fields(problems)


def test_subscription_owned_by_someone_else_is_rejected():
    """★facts 는 tenant/customer 범위로만 조회된다. 없으면 남의 것이다."""
    problems = verify(
        arguments={"subscription_id": "99999999-9999-4999-8999-999999999999"},
        rationale_evidence_ids=["ev-1"], facts=facts())
    assert "subscription_id" in fields(problems)


def test_unverifiable_identifier_is_rejected_not_ignored():
    """★이 MVP 에 orders 테이블이 없다. '확인 못 함' 을 '괜찮음' 으로 바꾸지 않는다."""
    problems = verify(
        arguments={"order_id": "ord-1"}, rationale_evidence_ids=["ev-1"], facts=facts())
    assert "order_id" in fields(problems)
    assert "확인할 수 없다" in problems[0].reason


def test_amount_without_a_target_payment_is_rejected():
    """무엇에 대한 금액인지 모르면 확인할 수 없다."""
    problems = verify(
        arguments={"amount": 10_000}, rationale_evidence_ids=["ev-1"], facts=facts())
    assert "amount" in fields(problems)


def test_evidence_not_in_the_context_pack_is_rejected():
    problems = verify(
        arguments={"payment_id": PAYMENT, "amount": 10_000},
        rationale_evidence_ids=["ev-1", "ev-does-not-exist"], facts=facts())
    assert "evidence_ids" in fields(problems)


def test_failed_fact_lookup_rejects_everything():
    """★사실을 못 읽었으면 통과시키지 않는다. 모르는 것과 괜찮은 것은 다르다."""
    problems = verify(
        arguments={"payment_id": PAYMENT, "amount": 100},
        rationale_evidence_ids=["ev-1"], facts=Facts(loaded=False))
    assert problems and problems[0].field == "__facts__"


def test_zero_or_negative_amount_is_rejected():
    problems = verify(
        arguments={"payment_id": PAYMENT, "amount": 0},
        rationale_evidence_ids=["ev-1"], facts=facts())
    assert "amount" in fields(problems)


def test_non_finite_amount_is_rejected_not_a_crash():
    """★버그사냥 2026-08-17 — "NaN"/"Infinity" 는 `Decimal()` 생성 자체는 성공한다.
    그런데 그 뒤 비교(`>`)나 `int()` 변환에서 각각 InvalidOperation/OverflowError 를
    던진다. 검증 함수가 죽으면 "확인 불가 → 거부" 대신 500 이 나가 방어선이 없어진다."""
    for non_finite in ("NaN", "Infinity", "-Infinity"):
        problems = verify(
            arguments={"payment_id": PAYMENT, "amount": non_finite},
            rationale_evidence_ids=["ev-1"], facts=facts())
        assert "amount" in fields(problems), f"{non_finite} 가 거부되지 않았다"


def test_every_problem_is_reported_not_just_the_first():
    """★첫 번째에서 멈추면 나머지를 다음 라운드에나 발견한다."""
    problems = verify(
        arguments={"payment_id": OTHER_PAYMENT, "order_id": "ord-1",
                   "subscription_id": "99999999-9999-4999-8999-999999999999"},
        rationale_evidence_ids=["nope"], facts=facts())
    assert {"payment_id", "order_id", "subscription_id", "evidence_ids"} <= fields(problems)


# ── 막으면 안 되는 것 ─────────────────────────────────────────────────────────
def test_a_truthful_proposal_passes():
    """★과잉 차단은 결함이다. 30,000원 결제에 30,000원 환불은 정상이다."""
    assert verify(
        arguments={"payment_id": PAYMENT, "amount": 30_000, "currency": "KRW"},
        rationale_evidence_ids=["ev-1", "ev-2"], facts=facts()) == []


def test_partial_refund_passes():
    assert verify(
        arguments={"payment_id": PAYMENT, "amount": 10_000},
        rationale_evidence_ids=["ev-1"], facts=facts()) == []


def test_cents_and_won_are_not_confused():
    """★`amount` 는 원, `amount_cents` 는 cents. 단위를 이름으로 구분한다."""
    assert verify(
        arguments={"payment_id": PAYMENT, "amount_cents": 3_000_000},
        rationale_evidence_ids=["ev-1"], facts=facts()) == []
    # 같은 숫자를 원으로 주면 100배라 실제 결제액을 넘는다
    assert verify(
        arguments={"payment_id": PAYMENT, "amount": 3_000_000},
        rationale_evidence_ids=["ev-1"], facts=facts()) != []


def test_proposal_without_identifiers_or_amounts_passes():
    """식별자도 금액도 없는 제안(예: 안내 발송)은 대조할 것이 없다."""
    assert verify(
        arguments={"template": "apology"}, rationale_evidence_ids=["ev-1"], facts=facts()) == []
