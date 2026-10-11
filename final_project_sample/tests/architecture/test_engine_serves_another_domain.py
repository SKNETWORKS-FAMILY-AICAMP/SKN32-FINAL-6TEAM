"""★basement 주장을 **실제로** 검증한다 — 같은 엔진에 다른 도메인을 물린다.

이 저장소의 목표는 "어떤 CS 플랫폼 요청이 와도 대응 가능한 범용 basement" 다.
그 주장은 **선언만으로는 증명되지 않는다.** 여기서 쇼핑몰 도메인 선언을 만들어
`app/core/verification.py` 를 **한 줄도 고치지 않고** 돌린다.

★이 테스트가 깨지면 basement 가 특정 도메인에 묶였다는 뜻이다.
  실제로 2026-08-16 이전 버전은 `order_id` 를 basement 의 "확인 불가 → 거부" 목록에
  박아 둬서, 쇼핑몰의 **가장 중요한 식별자가 자동 거부**됐다.
"""
from __future__ import annotations

from decimal import Decimal

from acop_basement.core.verification import (Facts, QuantityRule, VerificationPolicy,
                                   verify_proposal)

# ── 쇼핑몰 CS 도메인 선언 (basement 는 이걸 모른다) ───────────────────────────
MALL_POLICY = VerificationPolicy(
    references={"order_id": "orders", "shipment_id": "shipments"},
    quantities=(
        QuantityRule(field="refund_amount", reference="order_id",
                     limit_key="total_cents", scale=Decimal(100)),
        QuantityRule(field="return_quantity", reference="order_id",
                     limit_key="item_count", scale=Decimal(1)),
    ),
    opaque=frozenset({"coupon_id"}),          # 아직 대조 수단이 없다
    ignored=frozenset({"reason", "memo"}),
)

ORDER = "ord-1001"
SHIPMENT = "shp-77"


def mall_facts(**over) -> Facts:
    base = dict(
        collections={
            "orders": {ORDER: {"order_id": ORDER, "total_cents": 5_000_000, "item_count": 3}},
            "shipments": {SHIPMENT: {"shipment_id": SHIPMENT, "status": "delivered"}},
        },
        evidence_ids=frozenset({"mev-1"}),
    )
    base.update(over)
    return Facts(**base)


def check(**kwargs):
    kwargs.setdefault("policy", MALL_POLICY)
    kwargs.setdefault("rationale_evidence_ids", ["mev-1"])
    kwargs.setdefault("facts", mall_facts())
    return verify_proposal(**kwargs)


def fields(problems) -> set[str]:
    return {p.field for p in problems}


# ── ★쇼핑몰의 핵심 식별자가 통과해야 한다 ─────────────────────────────────────
def test_order_id_is_verifiable_here_not_auto_rejected():
    """★예전 basement 는 `order_id` 를 무조건 거부했다. 지금은 선언에 따라 대조한다."""
    assert check(arguments={"order_id": ORDER}) == []


def test_unknown_order_is_rejected():
    assert "order_id" in fields(check(arguments={"order_id": "ord-does-not-exist"}))


def test_refund_over_the_order_total_is_rejected():
    """5만원 주문에 7만원 환불 — 도메인만 바뀌고 규칙은 같다."""
    problems = check(arguments={"order_id": ORDER, "refund_amount": 70_000})
    assert "refund_amount" in fields(problems)


def test_partial_refund_passes():
    assert check(arguments={"order_id": ORDER, "refund_amount": 20_000}) == []


def test_return_quantity_over_the_item_count_is_rejected():
    """★수량 규칙이 금액 전용이 아니다 — 같은 엔진이 개수도 잰다."""
    assert "return_quantity" in fields(
        check(arguments={"order_id": ORDER, "return_quantity": 5}))


def test_return_quantity_within_the_order_passes():
    assert check(arguments={"order_id": ORDER, "return_quantity": 2}) == []


def test_shipment_ownership_is_checked():
    assert check(arguments={"shipment_id": SHIPMENT}) == []
    assert "shipment_id" in fields(check(arguments={"shipment_id": "shp-other"}))


def test_this_domains_opaque_field_is_rejected():
    """쇼핑몰에서는 `coupon_id` 가 대조 불가다 — 도메인마다 다르다."""
    assert "coupon_id" in fields(check(arguments={"coupon_id": "CPN-1"}))


def test_subscription_vocabulary_is_meaningless_here():
    """★다른 도메인의 어휘는 여기서 '선언되지 않은 필드' 로 거부된다.

    basement 가 구독 어휘를 알고 있었다면 이게 조용히 통과했을 것이다.
    """
    problems = check(arguments={"payment_id": "pay-1", "amount": 1000})
    assert "payment_id" in fields(problems)
    assert any("선언되지 않은" in p.reason for p in problems)


def test_engine_source_has_no_domain_vocabulary():
    """★엔진 파일 자체를 읽어 확인한다. 두 도메인이 다 도는 것만으로는
    '두 도메인을 다 하드코딩했을' 가능성이 남는다."""
    from pathlib import Path
    source = Path("acop_basement/core/verification.py").read_text(encoding="utf-8")
    for word in ("payment_id", "subscription_id", "order_id", "amount_cents", "total_cents"):
        # 주석·docstring 제외한 실행부에 없어야 한다
        code = "\n".join(line for line in source.splitlines()
                         if not line.strip().startswith(("#", "★", '"""')))
        assert word not in code, f"엔진에 도메인 어휘 '{word}' 가 있다"
