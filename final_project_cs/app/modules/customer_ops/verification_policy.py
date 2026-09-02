"""쇼핑몰 CS 도메인의 대조 선언 (v7 §9-E).

★basement(`app/core/verification.py`)는 **규칙 엔진**이고, 이 파일이 **어휘**다.
  엔진은 한 줄도 바뀌지 않았다 — 이 저장소가 sample 에서 복사돼 왔다는 증거다
  (`docs/handoff/10_도메인_교체_가이드.md` §1-2).

sample(구독·결제) → 이 저장소(커머스) 대응:

    payment_id      → order_id         금액 상한의 출처
    subscription_id → shipment_id      배송 건
    amount          → refund_amount    환불 금액
    (없음)           → return_quantity  반품 수량

★`opaque` 에 넣는다는 것은 **"확인 못 하니 거부한다"** 는 선언이다.
  귀찮다고 빼면 검사 없이 통과한다 — 조용히 새는 쪽이 더 위험하다.
"""
from __future__ import annotations

from decimal import Decimal

from app.core.verification import QuantityRule, VerificationPolicy

#: 이 도메인이 대조할 수 있는 것들.
CUSTOMER_OPS_POLICY = VerificationPolicy(
    references={
        "order_id": "orders",
        "shipment_id": "shipments",
        "return_id": "returns",
    },
    quantities=(
        # ★환불액은 주문 총액을 넘을 수 없다. 원 단위 → cents 상한이라 100 을 곱한다.
        QuantityRule(field="refund_amount", reference="order_id",
                     limit_key="total_cents", scale=Decimal(100)),
        QuantityRule(field="refund_amount_cents", reference="order_id",
                     limit_key="total_cents", scale=Decimal(1)),
        # ★반품 수량은 주문 수량을 넘을 수 없다. 금액 전용 규칙이 아니다.
        QuantityRule(field="return_quantity", reference="order_id",
                     limit_key="item_count", scale=Decimal(1)),
    ),
    # ★아직 대조 수단이 없는 식별자. 제안에 나오면 거부한다.
    #   쿠폰·적립금 테이블이 생기면 references 로 옮긴다.
    #   ★"changes"(2026-09-03) — `order.modify` 제안이 싣는 **고객이 준 변경 요청
    #     그대로**다(`current_state.order_change` 등). 무엇이 들었는지 정해져 있지
    #     않고 금액·수량이 들어올 수 있는데 대조할 규칙이 없다. `ignored` 로
    #     빼면 검사 없이 실행되므로 여기 둔다 — **막히는 것이 맞다.**
    #     푸는 방법: 변경 내용을 구조화하고(예: {"quantity": n}) 주문 사실과
    #     대조하는 규칙을 만든 뒤 `quantities`/`references` 로 옮긴다.
    opaque=frozenset({"coupon_id", "point_txn_id", "invoice_id", "changes"}),
    # 대조 대상이 아닌 자유 필드
    # ★"evidence" — 2026-08-17 실 브라우저 승인 클릭으로 발견: 운영 UI(`app/presentation
    #   /ui/routes.py::_actions()`)가 `arguments_json.evidence` 를 읽어 근거를 표시하고
    #   승인 버튼 활성화를 결정한다. 이 키는 대조 대상 필드가 아니라 표시용 데이터이므로
    #   선언해 두지 않으면 재검증(`proposal_guard.recheck_before_execution`)이
    #   "선언되지 않은 필드"로 승인 자체를 막는다.
    # ★"calculation_basis" — 2026-09-03 발견. `refund.calculate` 제안이 이 키를
    #   실어 보내는데 어디에도 선언돼 있지 않아, **모든 환불 제안이 승인 직전
    #   재검증에서 "선언되지 않은 필드"로 막히고 있었다.** 옛 구현부터 있던 키인데
    #   아무도 못 잡았다 — 제안 생성과 승인 재검증을 **이어서** 보는 검사가
    #   없었기 때문이다(`evidence` 를 놓쳤던 2026-08-17 과 같은 구멍).
    #   금액 자체는 `refund_amount_cents` 가 `total_cents` 상한 검사를 받는다.
    #   이 키는 그 금액을 **어떻게 구했는지**를 사람에게 보여주는 설명이라 대조
    #   대상이 아니다.
    #   ★아래 다섯(2026-09-03) — Procurement Team 의 `order.create`/`order.modify`/
    #     `order.cancel` 제안이 싣는데 선언이 없어 **셋 다 승인이 막혀 있었다.**
    #     전부 대조 대상이 아니라 승인자에게 상황을 보여주는 값이다:
    #       request            고객 문장 그대로(자유 텍스트, `reason` 과 같은 성격)
    #       fulfillment_status 주문 상태를 읽어 그대로 실은 것(지시가 아니라 맥락)
    #       scope              취소 범위 표시
    #       seller_fault       귀책 표시(bool)
    #       warehouse_handoff  창고 인계 여부(bool)
    #     ★값을 **바꾸는** 것이 아니라 **설명하는** 것만 여기 넣는다. 실제 변경
    #     내용인 `changes` 는 위 `opaque` 로 보냈다.
    ignored=frozenset({"reason", "reason_code", "template", "currency",
                       "rationale", "memo", "seeded_by", "note", "evidence",
                       "calculation_basis",
                       "request", "fulfillment_status", "scope",
                       "seller_fault", "warehouse_handoff"}),
)

#: 사실을 재조회하는 SQL. ★모든 query 에 tenant_id·customer_id 를 건다(설계 원칙 §1).
FACT_QUERIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("orders",
     "SELECT order_id, order_no, total_cents, item_count, status FROM orders "
     "WHERE tenant_id=%s AND customer_id=%s",
     ("order_id", "order_no", "total_cents", "item_count", "status")),
    ("shipments",
     "SELECT shipment_id, order_id, carrier, status FROM shipments "
     "WHERE tenant_id=%s AND customer_id=%s",
     ("shipment_id", "order_id", "carrier", "status")),
    ("returns",
     "SELECT return_id, order_id, quantity, status FROM returns "
     "WHERE tenant_id=%s AND customer_id=%s",
     ("return_id", "order_id", "quantity", "status")),
)
