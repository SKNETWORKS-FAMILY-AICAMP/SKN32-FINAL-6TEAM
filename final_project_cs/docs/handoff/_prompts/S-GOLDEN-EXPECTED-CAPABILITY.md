# S-GOLDEN-EXPECTED-CAPABILITY — golden.jsonl 에 expected_capability 라벨 추가

## 0. 배경 (읽기만)

- `docs/reports/2026-08-20_golden데이터셋_재작업_codex논의.md` — 이 작업의
  근거가 된 논의 문서(Claude·Codex 교차검증 완료). **결론과 방법을 그대로
  따른다** — 재설계하지 마라.
- 문제: `eval/datasets/golden.jsonl` 72건이 `expected_intent`(order/
  shipping/return/exchange/response-review) 만 갖고 있는데, 지금 팀
  구조에서 `capability_for()` 가 같은 intent 안 여러 case 를 전부 같은
  capability 하나로 뭉갠다:
  - `g-order` 18건 전부 → `order.verify` (실제로는 `order.create`,
    `payment.status` 시나리오가 섞여 있을 수 있음)
  - `g-return`+`g-exchange` 36건 전부 → `return.check_eligibility` (실제로는
    `return.request`, `refund.calculate` 시나리오가 섞여 있을 수 있음)
  - `g-shipping` 18건 → `fulfillment.track` (`shipment.status`,
    `shipment.exception` 시나리오가 섞여 있을 수 있음)

## 1. 절대 하지 말아야 할 것 — 가장 중요

**지금 자동 선택된 capability 를 그대로 정답으로 복사하지 마라.** 그러면
지금 있는 결함(뭉뚱그려짐)을 "정답"으로 굳혀버리는 것이다. **각 case 의
`message`·`expected_issue_code`·`notes` 필드를 실제로 읽고, 그 내용이
어떤 업무 동작을 요구하는지 판단해서** `expected_capability` 를 정해라.

예시(이미 확인함, 참고만 해라 — 다른 71건은 네가 직접 판단해라):
- `g-order-01`("주문번호를 잊어버렸는데... 조회") → 조회 시나리오이므로
  `order.verify` 가 맞다(이 케이스는 자동 선택과 우연히 일치함)
- 하지만 만약 어떤 g-order case 가 "새로 주문하고 싶은데" 류라면
  `order.create` 여야 하고, "결제가 됐는지 궁금하다" 류라면
  `payment.status` 여야 한다 — **자동으로 order.verify 를 넣으면 안 된다.**

## 2. 각 intent 그룹의 capability 후보 (팀별 확정 스펙에서)

```
order      → procurement_order_payment: order.verify | order.create | payment.status | procurement.quote
shipping   → fulfillment_logistics: fulfillment.track | shipment.status | shipment.exception
return     → return_refund: return.check_eligibility | return.request | refund.calculate
exchange   → return_refund: return.check_eligibility | return.request | refund.calculate
```
(`response-review` case 들은 이번 작업 대상 아니다 — `response.generate_review`
capability 하나뿐이라 뭉뚱그려짐 문제가 없다. 건드리지 마라.)

## 3. 할 일

1. golden.jsonl 의 g-order/g-shipping/g-return/g-exchange 60건(각 15건)을
   전부 읽고, 실제 시나리오에 맞는 `expected_capability` 필드를 추가한다.
2. 판단이 애매한 case(여러 capability 에 걸치거나 순수 대화형이라 특정
   동작이 없는 경우)는 억지로 하나를 고르지 말고 `expected_capability: null`
   로 남기고 왜 애매한지 `notes` 필드에 한 줄 덧붙여라(기존 notes 내용은
   보존하고 이어 붙여라, 지우지 마라).
3. 작업 후 검증 스크립트를 별도로 작성해 실행해라(라벨링 스크립트 자신이
   스스로를 검증하면 안 된다):
   - 각 case 의 `expected_capability` 가 §2 표에서 그 intent 에 허용된
     값 중 하나이거나 `null` 인지 전수 검사
   - intent 별로 4개 capability 후보 중 최소 1건씩은 실제로 배정됐는지
     확인(전부 하나로 쏠리면 이번 작업이 실패한 것 — 뭉뚱그려짐을
     반복한 것이다)
   - **자동 선택 결과와 다른 case 가 몇 건인지** 세어서 리포트에 남겨라
     (몇 건이 바뀌었는지가 이 작업이 실제로 뭔가 했다는 증거다)

## 4. 쓰기 대상

- `eval/datasets/golden.jsonl` (필드 추가만 — 기존 필드 값·순서·case 수
  변경 금지)
- 검증 스크립트(위치는 `eval/` 아래 기존 관례를 따르되, 일회성이면
  `docs/reports/` 옆에 결과만 남기고 스크립트는 리포트에 인라인으로
  붙여도 된다 — 판단해서 정해라)
- `docs/reports/2026-08-20_S-GOLDEN-EXPECTED-CAPABILITY_리포트.md` (신규)

## 5. 하지 말 것

- **`eval/datasets/holdout.jsonl` 은 절대 건드리지 마라** — 이 작업의
  근거 문서(§0) 가 명시적으로 holdout 은 그대로 둔다고 결론냈다.
- `expected_intent`, `case_id`, `message`, `expected_issue_code`,
  `expected_sentiment`, `expected_next_action`, `doc_ref` 등 기존 필드
  변경 금지 — `expected_capability` 추가만 한다(notes 에 애매함 사유
  덧붙이는 것 제외).
- `app/core/registry.py` 의 `capability_for()` 로직 수정 금지(이번 작업은
  데이터 라벨링이지 코드 변경이 아니다).
- g-response-review 12건 건드리지 마라.

## 6. 검증

- §3 의 검증 스크립트 실행 결과를 리포트에 실제 출력 그대로 붙여라.
- `python -m pytest -q -m "not live"` 도 실행해서 golden.jsonl 스키마를
  읽는 기존 테스트(`eval/tests/test_stats_and_datasets.py` 등)가 안
  깨지는지 확인해라(현재 354 passed 기준 변화 명시). 필드 추가만이라
  깨지면 안 되는데, 만약 깨지면 원인을 리포트에 정직하게 적어라 —
  임의로 기존 테스트를 고치지 마라(그건 Claude 가 판단한다).
