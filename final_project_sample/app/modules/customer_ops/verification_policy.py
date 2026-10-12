"""구독·결제 도메인의 대조 선언 (v7 §9-E).

★basement(`app/core/verification.py`)는 **규칙 엔진**이고, 이 파일이 **어휘**다.
  쇼핑몰 CS 로 복사하면 이 파일만 갈아 끼운다:

      references = {"order_id": "orders", "shipment_id": "shipments"}
      quantities = (QuantityRule("refund_amount", "order_id", "total_cents", scale=100),)
      opaque     = frozenset({"coupon_id"})     # 아직 대조 수단이 없다면

  basement 는 한 줄도 바뀌지 않는다. 그게 이 분리의 목적이다.

★`opaque` 에 넣는다는 것은 **"확인 못 하니 거부한다"** 는 선언이다.
  귀찮다고 빼면 검사 없이 통과한다 — 조용히 새는 쪽이 더 위험하다.
"""
from __future__ import annotations

from decimal import Decimal

from acop_basement.core.verification import QuantityRule, VerificationPolicy

#: 이 도메인이 대조할 수 있는 것들.
CUSTOMER_OPS_POLICY = VerificationPolicy(
    references={
        "payment_id": "payments",
        "subscription_id": "subscriptions",
        "entitlement_id": "entitlements",
    },
    quantities=(
        # 원 단위 금액 → cents 상한과 비교하므로 100 을 곱한다
        QuantityRule(field="amount", reference="payment_id",
                     limit_key="amount_cents", scale=Decimal(100)),
        # 이미 cents 로 온 값은 그대로 비교한다
        QuantityRule(field="amount_cents", reference="payment_id",
                     limit_key="amount_cents", scale=Decimal(1)),
        QuantityRule(field="refund_amount", reference="payment_id",
                     limit_key="amount_cents", scale=Decimal(100)),
    ),
    # ★이 MVP 에 대응 테이블이 없는 식별자. 제안에 나오면 거부한다.
    opaque=frozenset({"order_id", "line_item_id", "invoice_id"}),
    # 대조 대상이 아닌 자유 필드
    ignored=frozenset({"reason", "template", "currency", "rationale", "seeded_by", "note"}),
)

#: 사실을 재조회하는 SQL. ★모든 query 에 tenant_id·customer_id 를 건다(설계 원칙 §1).
FACT_QUERIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("payments",
     "SELECT payment_id, subscription_id, amount_cents, status FROM payments "
     "WHERE tenant_id=%s AND customer_id=%s",
     ("payment_id", "subscription_id", "amount_cents", "status")),
    ("subscriptions",
     "SELECT subscription_id, plan, status FROM subscriptions "
     "WHERE tenant_id=%s AND customer_id=%s",
     ("subscription_id", "plan", "status")),
    ("entitlements",
     "SELECT entitlement_id, plan, source FROM entitlements "
     "WHERE tenant_id=%s AND customer_id=%s",
     ("entitlement_id", "plan", "source")),
)
