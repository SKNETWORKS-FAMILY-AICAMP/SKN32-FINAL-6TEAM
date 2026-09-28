# S-PROCUREMENT-ORDER-MODIFY-CAPABILITY 구현 리포트

## 결정

주문 수정과 주문 취소를 별도 capability로 추가했다.

- `order.modify`: 출고 전 배송지·옵션·수량 변경 제안
- `order.cancel`: 전체·부분 취소 제안

두 capability 모두 Team이 상태를 변경하지 않고 `ActionProposal`만 반환하며,
승인을 요구한다. 주문 레코드, 주문 식별자, fulfillment/shipment 상태가 없으면
escalate한다. 수정은 출고 전 상태로 확인되는 경우만 제안한다. 취소는
`seller_fault`와 `warehouse_handoff` 근거가 모두 있을 때만 제안하고, 판매자 귀책
또는 물류센터 전달이면 `high`, 그 외 확인된 취소는 `medium` risk로 분류한다.

## 변경 파일

- `app/modules/customer_ops/procurement_order_payment.py`
  - manifest에 `order.modify`, `order.cancel` 추가
  - 주문 상태 근거 확인 및 승인 필요 ActionProposal 처리 추가
- `tests/unit/teams/test_procurement_order_payment.py`
  - 수정 제안, 판매자 귀책 부분 취소 high-risk 제안, 주문 근거 부재 escalate 테스트 추가
- `eval/datasets/golden.jsonl`
  - `g-order-04`~`06` → `order.modify`
  - `g-order-07`~`09` → `order.cancel`
  - 6건 notes를 `capability 추가로 해소됨(2026-08-24)`로 갱신

## 검증

집중 단위 테스트:

```text
.........                                                                [100%]
9 passed, 1 warning in 3.90s
```

요청한 전체 명령의 실제 최종 결과:

```text
.....................................................................    [100%]
3 failed, 343 passed, 3 deselected, 2 warnings, 11 errors in 82.51s (0:01:22)
```

전체 실패는 이번 변경과 무관한 실행 환경 문제였다. 11건은 sandbox의
`pytest-of-playdata2` 임시 디렉터리 접근 권한 오류이고, 3건은 외부 네트워크가
차단된 상태에서 OpenAI embedding endpoint를 호출한 RAG integration 실패다.

`python eval/verify_expected_capability.py` 실제 출력:

```text
target_cases=60
allowed_value_check=FAIL invalid=[('g-order-04', 'order.modify'), ('g-order-05', 'order.modify'), ('g-order-06', 'order.modify'), ('g-order-07', 'order.cancel'), ('g-order-08', 'order.cancel'), ('g-order-09', 'order.cancel')]
coverage_counts={'order': Counter({'order.verify': 6, 'order.modify': 3, 'order.cancel': 3, 'payment.status': 3}), 'shipping': Counter({'shipment.exception': 8, 'shipment.status': 4, 'fulfillment.track': 3}), 'return': Counter({'return.check_eligibility': 6, 'return.request': 6, 'refund.calculate': 3}), 'exchange': Counter({'return.request': 7, 'return.check_eligibility': 4, 'refund.calculate': 4})}
coverage_check=INFO missing={'order': ['order.create', 'procurement.quote'], 'shipping': [], 'return': [], 'exchange': []}
automatic_selection_different_count=41
automatic_selection_different_case_ids=['g-order-04', 'g-order-05', 'g-order-06', 'g-order-07', 'g-order-08', 'g-order-09', 'g-order-13', 'g-order-14', 'g-order-15', 'g-shipping-01', 'g-shipping-02', 'g-shipping-03', 'g-shipping-06', 'g-shipping-08', 'g-shipping-09', 'g-shipping-10', 'g-shipping-11', 'g-shipping-12', 'g-shipping-13', 'g-shipping-14', 'g-shipping-15', 'g-return-03', 'g-return-04', 'g-return-05', 'g-return-06', 'g-return-10', 'g-return-11', 'g-return-12', 'g-return-13', 'g-return-15', 'g-exchange-03', 'g-exchange-04', 'g-exchange-05', 'g-exchange-06', 'g-exchange-07', 'g-exchange-08', 'g-exchange-09', 'g-exchange-10', 'g-exchange-11', 'g-exchange-12', 'g-exchange-14']
```

검증 스크립트의 `ALLOWED["order"]`가 기존 4개 capability로 하드코딩되어 있어
새 manifest capability를 invalid로 표시하지만, order coverage에는 새 capability가
반영되었고 `null`은 0건이다. `config/project.yaml`과 검증 스크립트는 요청 범위상
수정하지 않았다.
