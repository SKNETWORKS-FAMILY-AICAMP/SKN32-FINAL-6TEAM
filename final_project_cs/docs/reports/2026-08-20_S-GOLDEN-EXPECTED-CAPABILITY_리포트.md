# S-GOLDEN-EXPECTED-CAPABILITY 작업 리포트

## 변경 내용

- `eval/datasets/golden.jsonl`의 `g-order`, `g-shipping`, `g-return`, `g-exchange` 60건에 `expected_capability`를 추가했다.
- 기존 72건의 case 수와 case ID는 유지했고, 기존 필드 값은 변경하지 않았다.
- `g-response-review` 12건은 변경하지 않았다.
- `eval/datasets/holdout.jsonl`은 변경하지 않았다.
- capability는 `message`, `expected_issue_code`, `notes`의 업무 동작을 기준으로 지정했다. 자동 선택값을 정답으로 복사하지 않았다.

## 라벨 분포

| intent | capability 분포 |
|---|---|
| order | `order.verify` 6, `order.create` 6, `payment.status` 3 |
| shipping | `shipment.status` 4, `fulfillment.track` 3, `shipment.exception` 8 |
| return | `return.check_eligibility` 6, `return.request` 6, `refund.calculate` 3 |
| exchange | `return.check_eligibility` 4, `return.request` 7, `refund.calculate` 4 |

주문 15건에는 견적(`procurement.quote`)을 요구하는 message/issue_code/notes가 없었다. 주소 변경·취소·상태 조회·결제 상태를 견적 capability로 라벨링하는 것은 case 내용과 불일치하므로 억지로 배정하지 않았다. 이에 따라 독립 검증의 coverage 검사는 이 한 항목을 실패로 보고한다.

## 독립 검증

실행 명령:

```text
python eval/verify_expected_capability.py
```

실제 출력:

```text
target_cases=60
allowed_value_check=PASS invalid=[]
coverage_counts={'order': Counter({'order.verify': 6, 'order.create': 6, 'payment.status': 3}), 'shipping': Counter({'shipment.exception': 8, 'shipment.status': 4, 'fulfillment.track': 3}), 'return': Counter({'return.check_eligibility': 6, 'return.request': 6, 'refund.calculate': 3}), 'exchange': Counter({'return.request': 7, 'return.check_eligibility': 4, 'refund.calculate': 4})}
coverage_check=FAIL missing={'order': ['procurement.quote'], 'shipping': [], 'return': [], 'exchange': []}
automatic_selection_different_count=41
automatic_selection_different_case_ids=['g-order-04', 'g-order-05', 'g-order-06', 'g-order-07', 'g-order-08', 'g-order-09', 'g-order-13', 'g-order-14', 'g-order-15', 'g-shipping-01', 'g-shipping-02', 'g-shipping-03', 'g-shipping-06', 'g-shipping-08', 'g-shipping-09', 'g-shipping-10', 'g-shipping-11', 'g-shipping-12', 'g-shipping-13', 'g-shipping-14', 'g-shipping-15', 'g-return-03', 'g-return-04', 'g-return-05', 'g-return-06', 'g-return-10', 'g-return-11', 'g-return-12', 'g-return-13', 'g-return-15', 'g-exchange-03', 'g-exchange-04', 'g-exchange-05', 'g-exchange-06', 'g-exchange-07', 'g-exchange-08', 'g-exchange-09', 'g-exchange-10', 'g-exchange-11', 'g-exchange-12', 'g-exchange-14']
```

허용 capability 값 검사는 통과했다. 자동 선택 결과와 다른 case는 41건이다. coverage 실패는 데이터 내용상 존재하지 않는 `procurement.quote`를 정답으로 만들지 않은 결과다.

## 기존 테스트

실행 명령:

```text
python -m pytest -q -m "not live"
```

실제 종료 요약:

```text
3 failed, 340 passed, 3 deselected, 2 warnings, 11 errors in 30.41s
```

실패/오류는 이번 JSON 필드 추가와 무관했다. 주요 원인은 pytest 임시 디렉터리 접근 거부(`PermissionError: [WinError 5]`)와 RAG 통합 테스트의 외부 OpenAI embeddings 연결 차단(`WinError 10013`, `openai.APIConnectionError`)이다. 기존 데이터셋 스키마를 확인하는 테스트는 통과했다. 기존 테스트를 수정하지 않았다.
