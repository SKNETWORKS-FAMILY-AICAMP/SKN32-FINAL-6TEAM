# 구현 지시 — `scripts/seed_demo_cases.py` 를 쇼핑몰 도메인으로 재작성

## 0. 배경 — 왜 이 작업이 필요한가

`scripts/seed_demo_cases.py` 는 발표용 Case 2건을 `demo` tenant 에 만든다(DoD-18).
지금 이 파일은 **옛 구독·청구 도메인**(`intent: "billing_refund"`, `owner_team_id:
"billing_subscription"`, `payment_id`/`subscription_id` 증거)을 그대로 쓰고 있다.

이 team_id 들은 지금 존재하지 않는다. 현재 등록된 Team 은 이 둘뿐이다
(`app/modules/customer_ops/__init__.py`):

| team_id | capabilities | accepted_case_types |
|---|---|---|
| `order_shipping` | `order.investigate`, `refund.propose` | `order`, `shipping` |
| `return_exchange` | `return.diagnose`, `return.propose_action` | `return`, `exchange` |

옆 파일 `scripts/seed.py` 는 **이미 쇼핑몰 도메인으로 마이그레이션돼 있다** — 10명의
고객, 각 3건의 주문(`orders`/`order_items`/`shipments`), 반품 2건(`returns`)을 만든다.
`seed_demo_cases.py` 는 이 데이터를 **가져다 쓰는** 자리이지, 독립적으로 새 고객을
만드는 자리가 아니다(원래도 그랬다 — 지금은 도메인만 안 맞을 뿐 구조는 맞다).

## 1. 소유 범위

```
scripts/seed_demo_cases.py     ← 전면 재작성
wiki/records/reports/                  ← 작업 리포트 제출 (RULE.md §3.4 필수)
```

★금지: `scripts/seed.py`(이미 맞게 돼 있다, 손대지 않는다 — 단, §2-3 의 문서화 오류
1건만 고친다), `app/**`, `config/**`, `tests/**`, `eval/**`, `knowledge/**`.

## 2. 무엇을 어떻게 바꾸는가

### 2-1. 상태 기계(전이 순서)는 바꾸지 않는다

`EventType` 시퀀스는 **그대로 유지**한다 — 이미 검증된 전이다:

- 시나리오 1: `CREATED → CLASSIFIED → ROUTED → APPROVAL_REQUIRED` (여기서 멈춘다,
  더 전이시키지 않는다 — 발표에서 사람이 `/ui/approvals` 에서 승인 버튼을 누른다)
- 시나리오 2: `CREATED → CLASSIFIED → ROUTED → COMPLETED` (종단 `resolved`)

바뀌는 것은 **각 이벤트의 payload 값**뿐이다(intent·issue_code·team_id·capability·
evidence 내용). `_reset`·`_create`·`_step`·`_fixed_case_id` 함수 구조는 그대로 둔다.

### 2-2. 시나리오 1 — 배송완료 미수령 → 환불 제안 (waiting_approval 에서 멈춤)

`scripts/seed.py` 가 이미 만들어 둔 실제 데이터를 쓴다. **하드코딩된 UUID 문자열을
쓰지 않는다** — 아래처럼 실행 시점에 실제 행을 조회한다:

```sql
SELECT o.order_id, o.order_no, o.total_cents, o.item_count, o.status
FROM orders o JOIN customers c USING(customer_id)
WHERE o.tenant_id=%s AND c.external_id='cust_01' AND o.order_no='ORD-0101'
```

`cust_01` 의 `ORD-0101`(그 고객의 첫 주문, seq=1)은 `seed.py` 규칙상 항상
`status='delivered'` 이고 배송(`shipments`)도 `status='delivered'` 로 만들어진다
(★seed.py 의 상태 순환은 `["delivered","shipped","paid"][seq-1]` 이므로 seq=1 은 항상
delivered 다 — 이 조회 결과가 비어 있으면 즉시 예외를 던져라. `scripts.seed` 를
먼저 돌리지 않고 이 스크립트만 돌린 경우이므로 조용히 넘어가면 안 된다).

시나리오 페이로드:

- `CREATED`: `channel: "web"`, `message`: 배송완료 미수령 상황을 자연스러운 한국어로
  (예: "배송완료로 떴는데 상품을 못 받았습니다. 확인 부탁드립니다.")
- `CLASSIFIED`: `intent: "shipping"`, `issue_code: "delivered_but_not_received"`,
  `sentiment: "negative"`
- `ROUTED`: `owner_team_id: "order_shipping"`, `capability: "order.investigate"`
- `action_requests` INSERT: `action_type: "refund.request"`(★점이 있다 — 실제
  `app/modules/customer_ops/order_shipping.py` 의 `ActionProposal.action_type` 과
  동일 문자열이어야 한다), `arguments_json`:
  `{"order_id": "<조회한 실제 order_id>", "seeded_by": "scripts.seed_demo_cases"}`
  (★실제 Team 코드는 `refund_amount` 를 제안에 넣지 않는다 — 지어내지 않는다).
  `idempotency_key`: 기존 패턴 유지(`f"{tenant}:{SCENARIO_1}:refund:{실제 order_no}"`).
  `evidence` 배열은 다음을 담는다(실제 조회한 값만 쓴다):
  - `{"source_type": "policy_chunk", "source_id": "doc_01#환불 금액의 산정", "claim": ..., "observed_at": ...}`
    (`knowledge/documents/01_shipping_delivered-but-not-received.md` 를 열어 그
    섹션이 실제로 존재하고 내용이 이 상황과 맞는지 확인한 뒤 claim 을 쓴다)
  - `{"source_type": "order", "source_id": "<조회한 order_id>", "claim": "order_no=ORD-0101, status=delivered, ...", ...}`
  - `{"source_type": "shipment", "source_id": "<조회한 shipment_id>", "claim": "status=delivered, delivered_at=...", ...}`
- `APPROVAL_REQUIRED`: `action_id`(방금 만든 action), `action_type: "refund.request"`,
  `reason`: 위 분류·근거를 요약한 한국어 문장

### 2-3. 시나리오 2 — 교환 기한 문의 (완료·resolved 종단)

★`cust_03`(`ORD-0301`)·`cust_04`(`ORD-0401`) 는 `seed.py` 가 이미 반품(`returns`)을
심어 둔 고객이다 — 이 스크립트가 그 고객을 쓰면 `return_exchange` Team 의 실제 로직상
(`pending and order` 분기) 항상 승인 대기로 빠지므로, **시나리오 2 처럼 스스로
완결되는 답변형 시나리오에는 쓰지 않는다.** 반품 이력이 없는 다른 고객(`cust_02`)의
주문을 쓴다:

```sql
SELECT o.order_id, o.order_no, o.total_cents, o.item_count, o.status, o.ordered_at
FROM orders o JOIN customers c USING(customer_id)
WHERE o.tenant_id=%s AND c.external_id='cust_02' AND o.order_no='ORD-0201'
```

시나리오 페이로드:

- `CREATED`: `channel: "chat"`, `message`: 교환 기한을 묻는 자연스러운 한국어
  (예: "받은 상품 사이즈가 안 맞아서 교환하고 싶은데 기한이 어떻게 되나요?")
- `CLASSIFIED`: `intent: "exchange"`, `issue_code: "exchange_period_question"`,
  `sentiment: "neutral"`
- `ROUTED`: `owner_team_id: "return_exchange"`, `capability: "return.diagnose"`
- `COMPLETED`: `answer_ref`(seed 식별자), `resolution`: 교환 기한 안내 요약(한국어,
  `knowledge/documents/15_exchange_period.md` 의 실제 내용 — 청약철회 기한과 동일한
  원칙을 따른다는 사실 — 을 근거로 쓴다. **7일이라는 숫자를 실제로 그 문서에서
  확인한 뒤에만 쓴다**), `evidence`: `{"source_type": "policy_chunk",
  "source_id": "doc_15#교환 기한의 원칙", "claim": ..., "observed_at": ...}` +
  주문 사실 1건(`source_type: "order"`)

### 2-4. `scripts/seed.py` 문서 오류 1건 수정 (허용된 유일한 seed.py 변경)

`scripts/seed.py` 파일 맨 위 docstring 의 `"1. 배송 완료로 찍혔는데 고객은 못 받았다
(cust_01, ORD-0103)"` 를 `"(cust_01, ORD-0101)"` 로 고친다. 실제로 그 스크립트가
만드는 `ORD-0103`(cust_01 의 3번째 주문, seq=3)은 상태 순환 규칙상 `status='paid'`
이고 배송(shipment) 자체가 생성되지 않는다(`if status == "paid": continue`) — "배송
완료" 시나리오에 쓸 수 없다. seq=1 인 `ORD-0101` 이 맞다. **주석만 고친다. 다른
줄은 건드리지 않는다.**

## 3. 검증 — 실행해서 통과해야 한다

```powershell
python -m scripts.seed
python -m scripts.seed_demo_cases
```

두 번째 명령이 예외 없이 끝나고, 마지막 JSON 출력의 `observed` 배열에서
`scenario_1` 의 status 가 `waiting_approval`, `scenario_2` 의 status 가 `resolved`
여야 한다(정확한 status 문자열은 `app/core/contracts.py` 의 CaseStatus 값을 실제
확인한다 — 추측하지 않는다). 두 번 연속 돌려도 `cases_in_tenant` 이 늘어나지
않아야 한다(재실행 안전, 원래 설계 그대로).

## 4. 완료 조건

- [ ] `python -m scripts.seed && python -m scripts.seed_demo_cases` 예외 없이 종료
- [ ] 시나리오 1: `order_shipping` Team, `waiting_approval` 종단, evidence 가 실제
      조회한 order/shipment 값과 실제 존재하는 doc_01 섹션을 인용
- [ ] 시나리오 2: `return_exchange` Team, `resolved` 종단, evidence 가 실제 존재하는
      doc_15 섹션을 인용
- [ ] `billing`/`technical`/`entitlement`/`subscription`/`payment_id` 등 옛 어휘 0건
- [ ] 두 번 실행해도 `cases_in_tenant` 불변(재실행 안전 유지)
- [ ] `wiki/records/reports/2026-08-17_S-SEED-DEMO_리포트.md` 제출 — 실행 로그 원문 포함
