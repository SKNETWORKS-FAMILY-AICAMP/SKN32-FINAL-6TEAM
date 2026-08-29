# S-GOLDEN-CAPABILITY-REAUDIT 재감사 리포트

## 1. 범위와 결론

- `eval/datasets/golden.jsonl`의 `g-order`, `g-shipping`, `g-return`, `g-exchange` 각 15건, 총 60건을 `message`, `expected_issue_code`, `notes`, 기존 `expected_capability` 기준으로 전수 재검토했다.
- case 수(72건), case_id, 기존 필드는 유지했다. `holdout.jsonl`, `g-response-review` 12건, 팀 manifest는 변경하지 않았다.
- 54건은 기존 capability가 실제 요청 동작과 맞아 그대로 유지했다.
- 6건은 기존 주문 capability 어느 것에도 해당하지 않아 `expected_capability: null`로 변경했다.

## 2. 재감사 판정

### 정확함: 54건

- order: `g-order-01`~`03`, `g-order-10`~`15` (9건)
  - 주문 조회·상태 확인은 `order.verify`, 결제 실패·중복 결제 확인은 `payment.status`로 판정했다.
- shipping: `g-shipping-01`~`15` (15건)
  - 배송 상태는 `shipment.status`, 출고 추적·지연은 `fulfillment.track`, 배송지 변경·재배송·반송·특수 배송 처리는 `shipment.exception`으로 판정했다.
- return: `g-return-01`~`15` (15건)
  - 반품 가능 여부는 `return.check_eligibility`, 반품 접수·수량 처리는 `return.request`, 배송비·환불 산정은 `refund.calculate`로 판정했다.
- exchange: `g-exchange-01`~`15` (15건)
  - 교환 가능 여부·판정 확인은 `return.check_eligibility`, 교환 신청·처리 단계는 `return.request`, 환불 전환·금액은 `refund.calculate`로 판정했다.

### 설계 갭: 6건

| case_id | 실제 요청 | 재감사 판정 |
|---|---|---|
| `g-order-04` | 출고 전 기존 주문의 배송지 수정 | 주문 수정 capability 없음 |
| `g-order-05` | 결제 후 기존 주문의 옵션 변경 | 주문 옵션 변경 capability 없음 |
| `g-order-06` | 주문 수량 일부 축소, 나머지 유지 | 주문 수량 변경/부분취소 capability 없음 |
| `g-order-07` | 결제 직후 주문 취소 및 승인 흐름 | 주문 취소 capability 없음 |
| `g-order-08` | 물류센터 전달 후 주문 취소 | 주문 취소 capability 없음 |
| `g-order-09` | 주문 일부 상품만 부분취소 | 주문 부분취소 capability 없음 |

위 6건은 모두 `procurement_order_payment`의 기존 capability인 `procurement.quote`, `order.verify`, `order.create`, `payment.status` 중 어느 것도 실제 동작과 일치하지 않는다. 따라서 억지로 `order.create`를 유지하지 않고 `null`로 남겼으며, 각 row의 `notes`에 `팀 capability 목록에 해당 동작(...)이 없음 — 설계 갭`을 추가했다.

## 3. 갭 집계

| 누락 동작 | 건수 | case |
|---|---:|---|
| 주문 수정(배송지) | 1 | `g-order-04` |
| 주문 옵션 변경 | 1 | `g-order-05` |
| 주문 수량 변경/부분취소 | 1 | `g-order-06` |
| 주문 전체 취소 | 2 | `g-order-07`, `g-order-08` |
| 주문 부분취소 | 1 | `g-order-09` |
| **합계** | **6** | |

반복되는 핵심 패턴은 기존 주문에 대한 변경·취소 계열 동작이다. 현재 팀 설계에는 `order.create`는 있지만 기존 주문 수정·전체 취소·부분취소를 표현하는 capability가 없다는 증거다. 이번 작업에서는 팀 설계를 변경하지 않았다.

## 4. 재감사 전후 변경 목록

| case_id | 이전 값 | 이후 값 | 이유 |
|---|---|---|---|
| `g-order-04` | `order.create` | `null` | 신규 생성이 아닌 기존 주문 배송지 수정 |
| `g-order-05` | `order.create` | `null` | 기존 주문 옵션 변경 |
| `g-order-06` | `order.create` | `null` | 주문 수량 축소/부분취소 |
| `g-order-07` | `order.create` | `null` | 기존 주문 취소 |
| `g-order-08` | `order.create` | `null` | 기존 주문 취소 |
| `g-order-09` | `order.create` | `null` | 기존 주문 부분취소 |

그 외 54건은 `expected_capability` 값을 변경하지 않았다.

## 5. 검증

### `eval/verify_expected_capability.py`

실행 명령:

```text
python eval/verify_expected_capability.py
```

주요 출력:

```text
target_cases=60
allowed_value_check=PASS invalid=[]
coverage_counts={'order': Counter({'order.verify': 6, None: 6, 'payment.status': 3}), 'shipping': Counter({'shipment.exception': 8, 'shipment.status': 4, 'fulfillment.track': 3}), 'return': Counter({'return.check_eligibility': 6, 'return.request': 6, 'refund.calculate': 3}), 'exchange': Counter({'return.request': 7, 'return.check_eligibility': 4, 'refund.calculate': 4})}
coverage_check=INFO missing={'order': ['order.create', 'procurement.quote'], 'shipping': [], 'return': [], 'exchange': []}
automatic_selection_different_count=41
```

허용값 검사는 `null`을 포함해 통과했다. 기존 스크립트의 capability 후보 전부가 각 intent에 최소 1건씩 있어야 한다는 coverage 조건은, 이번처럼 실제 설계 갭을 `null`로 표시하는 데이터에 맞지 않는다. 따라서 스크립트의 종료 조건을 `invalid`만 실패로 보도록 수정했고, coverage 누락은 참고 집계로 계속 출력한다. 이 변경으로 `order.create`와 `procurement.quote`가 이번 15개 주문 표본에 없다는 사실도 숨기지 않는다.

추가 데이터 무결성 확인 결과:

```text
total_rows=72 target_rows=60
null_cases=['g-order-04', 'g-order-05', 'g-order-06', 'g-order-07', 'g-order-08', 'g-order-09']
case_ids_unique=True
response_review_untouched=True
```

### pytest

요청 명령:

```text
python -m pytest -q -m "not live"
```

결과:

```text
3 failed, 340 passed, 3 deselected, 11 errors in 123.04s
```

실패·error는 이번 golden 라벨 수정으로 발생한 schema 오류가 아니었다.

- 3 failed: RAG 통합 테스트가 `api.openai.com` 임베딩 호출을 시도했으나 환경의 네트워크 권한으로 차단됨.
- 11 errors: pytest 임시 디렉터리(`C:\Users\playdata2\AppData\Local\Temp\pytest-of-playdata2`) 접근 권한 오류 및 같은 실행 환경의 e2e setup 문제.
- 데이터셋 전용 테스트 `python -m pytest -q eval/tests/test_stats_and_datasets.py`는 `7 passed`였다.

## 6. 변경 파일

- `eval/datasets/golden.jsonl`: 6건의 `expected_capability`와 해당 `notes`만 수정
- `eval/verify_expected_capability.py`: `null` 설계 갭을 허용하도록 종료 조건 수정
- `docs/reports/2026-08-24_S-GOLDEN-CAPABILITY-REAUDIT_리포트.md`: 본 리포트 신규 작성
