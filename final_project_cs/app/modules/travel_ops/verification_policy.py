# -*- coding: utf-8 -*-
"""여행 도메인의 대조 선언 (v7 §9-E 의 할루시네이션 방어).

★basement(`app/core/verification.py`)는 **규칙 엔진**이고 이 파일이 **어휘**다.
  엔진은 한 줄도 바뀌지 않는다 — 도메인을 갈아끼워도 코어가 그대로라는 주장을
  실제로 시험하는 자리다. 커머스판은 `app/modules/customer_ops/
  verification_policy.py` 였다.

커머스 → 여행 대응:

    order_id    → booking_id           금액·인원 상한의 출처
    shipment_id → supplier_booking_id  공급자 원장 쪽 식별자
    return_id   → (없음)                반품 개념이 없다

★**빈 정책은 「전부 통과」가 아니라 「전부 거부」다.** `app/composition.py` 의
  `build_verification_policy()` 는 선언을 못 찾으면 빈 `VerificationPolicy()` 를
  주는데, 그러면 재검증이 모든 키를 "선언되지 않은 필드" 로 막는다. 즉 이
  파일이 없으면 **여행 제안은 하나도 승인되지 않는다.** 조용히 새는 것보다
  낫다는 판단이지만, 그래서 도메인 교체 때 이 파일을 빠뜨리면 안 된다.

★이 저장소가 같은 자리에서 **두 번** 데였다. 제안이 싣는데 선언에 없던 키
  때문에 승인이 통째로 막혔다 — `evidence`(2026-08-17, 실 브라우저 클릭으로
  발견) 와 `calculation_basis`(2026-09-03, 모든 환불 제안이 막혀 있었다).
  둘 다 **제안 생성과 승인 재검증을 이어서 보는 검사가 없어서** 늦게 잡혔다.
  그래서 여기 선언은 `tests/unit/travel/test_travel_proposals_pass_verification.py`
  가 **여행 Team 이 실제로 만든 제안**을 넣어 검사한다 — 손으로 적은 목록이
  아니라.
"""
from __future__ import annotations

from decimal import Decimal

from app.core.verification import QuantityRule, VerificationPolicy

#: 이 도메인이 대조할 수 있는 것들. 값은 `FACT_QUERIES` 의 컬렉션 이름이다.
TRAVEL_OPS_POLICY = VerificationPolicy(
    references={
        "booking_id": "bookings",
        "supplier_booking_id": "supplier_bookings",
        # ★`[결정 2026-09-17]` Case 버전의 일정 적용(`itinerary.apply`) — 이 고객의 여행이어야 한다.
        "trip_id": "trips",
    },
    quantities=(
        # ★인원은 정원을 넘을 수 없다. 금액 전용 규칙이 아니다.
        QuantityRule(field="party_size", reference="booking_id",
                     limit_key="capacity", scale=Decimal(1)),
        # ★환불·차액은 예약 금액을 넘을 수 없다. 원 단위 → cents 라 100 을 곱한다.
        QuantityRule(field="refund_amount", reference="booking_id",
                     limit_key="amount_cents", scale=Decimal(100)),
        QuantityRule(field="refund_amount_cents", reference="booking_id",
                     limit_key="amount_cents", scale=Decimal(1)),
    ),
    # ★대조 수단이 **아직 없는** 식별자. 제안에 나오면 거부한다.
    #   ☆`place_id` 를 여기 두지 않은 이유: 장소는 금액·인원의 상한을 갖지
    #     않아서 대조할 것이 없고, 제안 인자로도 나가지 않는다. 나가기
    #     시작하면 `references` 에 `places` 로 넣는다(테이블은 이미 있다).
    opaque=frozenset({"voucher_id", "supplier_invoice_id", "payment_ref"}),
    # 대조 대상이 아닌 자유 필드 — **값을 바꾸는 것이 아니라 설명하는 것**만 넣는다
    ignored=frozenset({
        # 옛 커머스 선언에서 그대로 살아남은 것들. 성격이 도메인 무관이다
        "reason", "reason_code", "template", "currency", "rationale", "memo",
        "seeded_by", "note",
        # ★`evidence` — 운영 UI(`app/presentation/ui/routes.py::_actions()`)가
        #   `arguments_json.evidence` 를 읽어 근거를 보여주고 승인 버튼 활성화를
        #   정한다. 표시용이지 대조 대상이 아니다. 빠뜨리면 승인 자체가 막힌다.
        "evidence",
        # 여행 제안이 싣는 설명값
        "change_fields",      # 무엇을 바꾸는지 **이름만**. 값은 근거로 간다
        "supplier",           # 어느 업체에 인계되는지 (표시)
        "starts_at_current",  # 지금 시각 (표시)
        "starts_at_proposed", # 바꾸려는 시각 — ★대조 대상이 아니다.
                              #   시각의 타당성은 Team 이 근거와 함께 판정하고,
                              #   승인자가 사람 눈으로 본다
        "penalty_rate",       # 규정에서 읽은 위약율 (표시)
        "policy_ref",         # 근거 문서 참조 (표시)
        # ★`[결정 2026-09-17]` `itinerary.apply` 가 싣는 값. **대조는 적용기가 적용 순간에 한다**
        #   (`itinerary_actions.py` — 기준 버전 · 항목 실재 · 장소 실재). 여기서 모양만 허락한다.
        "base_version", "causes", "notice", "summary", "replacements", "full_items",
    }),
)

#: 사실을 재조회하는 SQL. ★모든 query 에 tenant_id·customer_id 를 건다(설계 원칙 §1).
#:  ☆`supplier_bookings` 에는 `customer_id` 컬럼이 없다 — `bookings` 를 거쳐
#:    같은 고객의 것만 나오게 조인한다. 조인을 빼면 **남의 예약이 보인다.**
FACT_QUERIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("bookings",
     "SELECT booking_id, booking_no, kind, status, party_size, capacity, "
     "amount_cents, locked FROM bookings "
     "WHERE tenant_id=%s AND customer_id=%s",
     ("booking_id", "booking_no", "kind", "status", "party_size", "capacity",
      "amount_cents", "locked")),
    ("supplier_bookings",
     "SELECT sb.supplier_booking_id, sb.booking_id, sb.supplier, sb.supplier_ref, "
     "sb.status, sb.confirmed_at FROM supplier_bookings sb "
     "JOIN bookings b ON b.booking_id = sb.booking_id AND b.tenant_id = sb.tenant_id "
     "WHERE sb.tenant_id=%s AND b.customer_id=%s",
     ("supplier_booking_id", "booking_id", "supplier", "supplier_ref",
      "status", "confirmed_at")),
    ("trips",
     "SELECT trip_id, status, latest_version FROM trips WHERE tenant_id=%s AND customer_id=%s",
     ("trip_id", "status", "latest_version")),
)

__all__ = ["FACT_QUERIES", "TRAVEL_OPS_POLICY"]
