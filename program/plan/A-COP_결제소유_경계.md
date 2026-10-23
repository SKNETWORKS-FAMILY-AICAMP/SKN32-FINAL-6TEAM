# A-COP 결제 소유 경계 결정 (초안)

작성 2026-08-31. 상태 **초안 — 검토 대기**.

관련 문서: [`A-COP_페인포인트_페르소나_설계.md`](A-COP_페인포인트_페르소나_설계.md) · [`A-COP_사업성_단위경제.md`](A-COP_사업성_단위경제.md)

## 0. 결정 요약

| 질문 | 결정 |
|---|---|
| 결제를 A-COP이 처리하는가 | **아니다. 검증 쇼핑몰이 소유한다** |
| 지금 들어와 있는가 | **거의 없다.** 상태를 읽기만 하고 그것도 DB가 아니라 넘겨받은 값이다 |
| 포인트·캐시·쿠폰은 | **읽기 하나만.** 잔액을 바꾸는 모든 것은 쇼핑몰 |
| 지금 조치할 것 | **환불 계산식.** 할인이 붙는 순간 고객에게 틀린 금액을 말한다 (§5) |

경계선은 읽기냐 쓰기냐가 아니라 **설명이냐 실행이냐**다. A-COP은 결제를 설명하고 대조한다. 실행하지 않는다.

---

## 1. 지금 실제 상태 — 코드 근거

### 1-1. 결제 테이블이 없다 `[실측]`

DB 마이그레이션 6개 전체에 `payments` 테이블이 없다.

| 파일 | 정의된 테이블 |
|---|---|
| [`001_schema.sql`](../../final_project_cs/app/infrastructure/db/migrations/001_schema.sql) | tenants, customers, customer_cases, case_events, agent_runs, team_tasks, action_requests, action_approvals, outbox, prompts, llm_calls, knowledge_documents, knowledge_chunks, feedback_analytics_reports |
| [`002_domain_commerce.sql`](../../final_project_cs/app/infrastructure/db/migrations/002_domain_commerce.sql) | orders, order_items, shipments, returns |
| [`006_products_catalog.sql`](../../final_project_cs/app/infrastructure/db/migrations/006_products_catalog.sql) | products |

결제 상태는 `orders.status`에 섞여 있는 게 전부다.

```sql
-- 002_domain_commerce.sql:19
status  text NOT NULL,  -- placed / paid / shipped / delivered / cancelled
```

주문 진행 상태와 결제 상태가 한 칸에 들어가 있다. `paid`는 결제 사건인데 주문 상태로 표현된다.

### 1-2. `payment.status`는 DB를 읽지 않는다 `[실측]`

[`procurement_order_payment.py:256`](../../final_project_cs/app/modules/customer_ops/procurement_order_payment.py) 을 보면 이렇다.

```python
payment = task.context.current_state.get("payment") or task.context.current_state.get("payment_status")
...
if not payment:
    return self._escalate(task, "payment_status_evidence_missing")
```

**넘겨받은 값을 그대로 돌려주고, 없으면 사람에게 넘긴다.** 결제 시스템을 조회하지도, 계산하지도 않는다. 근거 문자열도 그렇게 적혀 있다 — `"payment status supplied by the local context/database facts"`.

이미 올바른 방향이다. 이 형태를 유지한다.

### 1-3. 결제 조회 도구가 없다 `[실측]`

Team이 쓸 수 있는 read 도구는 7종이고 결제용은 없다.

| Team | 허용 도구 | 위치 |
|---|---|---|
| Procurement + Order & Payment | `read.order`, `read.account`, `read.policy`, `read.catalog` | [`procurement_order_payment.py:35`](../../final_project_cs/app/modules/customer_ops/procurement_order_payment.py) |
| Return & Refund | `read.order`, `read.return`, `read.policy` | [`return_refund.py:25`](../../final_project_cs/app/modules/customer_ops/return_refund.py) |
| Fulfillment & Logistics | `read.order`, `read.shipment`, `read.policy` | [`fulfillment_logistics.py:19`](../../final_project_cs/app/modules/customer_ops/fulfillment_logistics.py) |
| Catalog & Verification | `read.catalog`, `read.order_items`, `read.policy` | [`catalog_verification.py:21`](../../final_project_cs/app/modules/customer_ops/catalog_verification.py) |
| Response Review | `read.policy` | [`response_review.py:28`](../../final_project_cs/app/modules/customer_ops/response_review.py) |

Team 이름에 "Payment"가 들어 있는데 결제 도구가 없다. **이름이 실제 권한보다 넓다.**

### 1-4. `MockProviderPublisher`는 결제 연동이 아니다 `[실측]`

[`app/infrastructure/messaging/mock_payment_publisher.py:18`](../../final_project_cs/app/infrastructure/messaging/mock_payment_publisher.py) 의 `MockProviderPublisher`는 outbox worker가 publisher 경계를 연습하기 위한 테스트 더블이다. 네트워크 I/O가 없다.

**파일명(`mock_payment_publisher.py`)과 클래스명(`MockProviderPublisher`)이 어긋나 있다.** 클래스는 이미 도메인 중립으로 이름을 바꿨는데 파일명이 안 따라왔다. 파일명만 보고 "결제 연동이 있다"고 오해할 여지가 있으므로 정리 대상이다.

### 1-5. 포인트·캐시·쿠폰은 전혀 없다 `[실측]`

코드에도 DB에도 없다. 지금 넣는 게 아니라 **어디까지 넣을지 미리 정하는 것**이 이 문서의 목적이다.

### 1-6. 코드가 이미 결제를 막고 있다 `[실측]`

[`tests/architecture/test_basement_is_domain_free.py:35`](../../final_project_cs/tests/architecture/test_basement_is_domain_free.py) 이 `payment`를 금지어로 걸어 뒀다. `final_project_sample`에도 같은 테스트가 있다.

```python
DOMAIN_WORDS = (
    # 구독·결제 (현재 sample 도메인)
    "payment", "subscription", "entitlement", "refund", "invoice",
    # 커머스 (복사본이 쓸 도메인)
    "order_id", "line_item", "shipment", "sku", "cart",
)
```

**Core(basement)에 결제가 들어오면 이 테스트가 붉어진다.** 예외 목록(`ALLOWED`)에 있는 건 [`app/core/redaction.py`](../../final_project_cs/app/core/redaction.py) 하나인데, 그것도 "결제 식별자 모양을 알아야 가릴 수 있다 — 도메인 로직이 아니라 보안 규칙"이라는 이유가 주석으로 붙어 있다.

즉 **이 결정은 새로 만드는 게 아니라 이미 코드에 있는 규칙을 문서로 확정하는 것**이다.

---

## 2. 왜 쇼핑몰이 소유해야 하는가

### 근거 1 — 우리가 파는 물건이 그게 아니다

A-COP은 고객 응대를 구성하는 플랫폼이다([v8 §1-1](A-COP_구현계획서_v8.md)). 결제를 가지면 커머스 시스템이 되고, 도입 기업에게 "결제를 우리 것으로 바꾸라"고 요구하는 제품이 된다. 훨씬 팔기 어려운 물건이다.

### 근거 2 — 자체 호스팅 목표와 충돌한다

고객사 환경에 올려 데이터가 안 나가게 하는 게 차별점인데, 결제를 우리가 들면 PCI-DSS 같은 규제 부담이 **고객사가 아니라 우리에게** 온다. 파는 물건의 성격이 바뀐다.

### 근거 3 — 이중 장부가 된다

도입 기업엔 이미 결제 시스템이 있다. 우리가 잔액을 들면 어느 쪽이 진짜인지 판정할 수 없다. **"업무 상태는 한 곳에만 둔다"**는 이 프로젝트의 원칙([v8 §11](A-COP_구현계획서_v8.md): PostgreSQL을 단일 원천으로)과 같은 이유다.

### 근거 4 — Team은 side effect를 실행하지 않는다

[v8 §7](A-COP_구현계획서_v8.md)이 못박았다.

> Team은 side effect를 실행하지 않고 `ActionProposal`만 반환한다.

**결제는 side effect의 극단이다.** 이 원칙을 결제에 적용하지 않을 근거가 없다.

---

## 3. 경계선

| 우리(A-COP) | 검증 쇼핑몰 |
|---|---|
| 결제가 **어떻게 구성됐는지 읽기** (카드 얼마 / 포인트 얼마 / 쿠폰 할인 얼마) | 결제 승인·취소·부분취소 **실행** |
| 그 구성으로 환불 금액을 **설명하고 대조** | 환불 **집행** |
| 정책 문서로 "포인트도 돌려받나" **답변** | 잔액 증감·적립·소멸 |
| 불일치 발견 시 **escalate** | 쿠폰 발급·사용처리·복원 |

**우리가 계산하지 않는다.** 쇼핑몰이 계산한 값을 받아서 대조만 한다. 그러면 결제 구성이 아무리 복잡해져도 우리 코드는 안 바뀐다. 지금 `verify_proposal()`이 하는 일이 정확히 대조라서 구조도 이미 맞다.

---

## 4. 포인트·캐시·쿠폰 — 어디까지

세 단계로 나눈다.

### 단계 1 — 지금 필요한 것 (10주 안)

**결제 구성 스냅샷 읽기 도구 하나.** `read.payment` 추가로 끝난다.

환불 금액을 말하려면 무엇으로 얼마 냈는지 알아야 한다. 30,000원을 포인트 5,000 + 카드 25,000으로 냈으면 환불도 그렇게 쪼개진다. 고객이 가장 많이 묻는 게 이것이다.

골든셋 근거도 있다. `refund.calculate` 7건 + `return.request` 13건 + `return.check_eligibility` 10건 = **30건(42%)이 금액이 걸린 케이스**다. `[실측]` [`eval/datasets/golden.jsonl`](../../final_project_cs/eval/datasets/golden.jsonl)

### 단계 2 — 확장 범위

**잔액 조회.** "내 포인트 얼마 남았어요"는 쇼핑몰 마이페이지가 답하는 게 자연스럽다. 개인 AI가 MCP로 물어볼 때 필요해진다([v8 §9](A-COP_구현계획서_v8.md)).

### 단계 3 — 절대 갖지 않는 것

**잔액을 바꾸는 모든 것.** 적립, 차감, 소멸, 쿠폰 발급. 하나라도 가지면 이중 장부다(근거 3).

---

## 5. ★ 지금 환불 계산식이 이미 위험하다

### 문제

[`return_refund.py:139-144`](../../final_project_cs/app/modules/customer_ops/return_refund.py) `[실측]`

```python
total = order.get("total_cents")
item_count = order.get("item_count")
if not isinstance(total, int) or not isinstance(item_count, int) or item_count <= 0:
    ...
amount = total * int(quantity) // item_count
```

두 가지를 가정한다.

1. **모든 품목의 값이 같다** (`item_count`로 균등 분할)
2. **할인이 없다** (`total_cents` 한 칸뿐이라 정가·실결제액 구분 없음)

[`002_domain_commerce.sql:17`](../../final_project_cs/app/infrastructure/db/migrations/002_domain_commerce.sql) 을 보면 `orders`에 금액 칸이 `total_cents` 하나다. 할인·포인트·쿠폰이 들어갈 자리가 없다.

### 터지는 방식

```
30,000원 주문 · 5,000원 쿠폰 사용 → 실결제 25,000원
2개 중 1개 반품

우리 안내:  30,000 × 1 ÷ 2 = 15,000원   ← 고객에게 이렇게 말한다
실제 입금:  25,000 × 1 ÷ 2 = 12,500원   ← 실제로는 이만큼 온다
                              ─────────
                              차액 2,500원
```

**금액을 잘못 말하는 것은 이 프로젝트가 가장 경계하는 상황이다.** 그리고 이건 할루시네이션이 아니라 **결정론적 코드의 계산 오류**라서 [v8 §9-E](A-COP_구현계획서_v8.md)의 근거 대조로도 안 잡힌다. 대조 대상 자체가 틀렸기 때문이다.

지금은 포인트·쿠폰이 없어서 안 터진다. **검증 쇼핑몰에 할인이 하나라도 붙으면 그날 터진다.**

### 사업적 크기

[`A-COP_사업성_단위경제.md`](A-COP_사업성_단위경제.md) §4-4의 축 2(오류 비용)가 추상적 우려가 아니라는 증거가 이 사례다. 직접 손실은 2,500원이지만 재처리(재문의→확인→정정→사과)가 얹히면 1건이 3만원 규모가 된다.

---

## 6. 조치안

| # | 조치 | 소유 | 성격 |
|---|---|---|---|
| 1 | 환불 금액을 **쇼핑몰이 계산한 값을 받아 대조**하는 구조로 변경 | `final_project_cs` (서유현) | **계약 변경** |
| 2 | `read.payment` 도구 추가 (결제 구성 스냅샷) | 동 | 신규 |
| 3 | `orders`에서 결제 상태를 분리할지 판단 | 스키마 (최연우와 합의) | 스키마 |
| 4 | `mock_payment_publisher.py` → 도메인 중립 파일명으로 변경 | `final_project_cs` | 정리 |
| 5 | 검증 쇼핑몰에 **필요한 응답 필드** 전달 | 검증 쇼핑몰 팀 | **계약 협의** |

**1번과 5번이 짝이다.** 우리가 계산을 그만두려면 쇼핑몰이 계산 결과를 줘야 한다. 그래서 이건 우리 저장소만의 일이 아니라 **저장소 간 계약**이고, 검증 쇼핑몰 일정과 맞물린다.

**3번은 서두르지 않아도 된다.** `orders.status`에 `paid`가 섞여 있는 건 지저분하지만 지금 당장 틀린 답을 만들지는 않는다. 1·2번이 먼저다.

### 쇼핑몰에 요청할 필드 (초안)

환불 금액을 대조하려면 최소한 이만큼이 필요하다.

| 필드 | 왜 필요한가 |
|---|---|
| 실결제 금액 (정가 아님) | 환불 기준액 |
| 결제수단별 분해 (카드 / 포인트 / 캐시 / 쿠폰) | "포인트도 돌려받나"에 답하기 위해 |
| 품목별 배분 금액 | 균등 분할 가정을 버리기 위해 |
| 쇼핑몰이 계산한 환불 예정액 | **대조 대상** |
| 환불 수단별 분해 | 고객에게 설명할 내용 |

`[추정]` 이 목록은 우리 쪽 필요 기준이다. 쇼핑몰 쪽 스키마를 보고 조정해야 한다.

---

## 7. v8 병합 위치

| 이 문서 | v8 |
|---|---|
| §0 결정 요약 | §5 시스템 범위 — Out of Scope에 "결제 실행" 명시 |
| §2 근거 | §18-A 결정사항의 주의점 |
| §3 경계선 | §8-B Team 경계 |
| §4 포인트·쿠폰 3단계 | §6 타깃 도메인 (커머스로 갱신 시 함께) |
| §5 계산식 결함 | §20 동시성·정합성·Action 구현 명세 |
| §6 조치안 | §25 공식 일정 계획 |

---

## 8. 남은 결정

| 항목 | 필요한 판단 |
|---|---|
| 조치 1의 착수 시점 | 중간발표(2026-09-15) 전 / 후 |
| 검증 쇼핑몰과의 계약 협의 창구 | 누가 언제 |
| `orders` 스키마 분리 여부 | 최연우와 합의 |

---

## 근거 목록

전부 이 저장소의 파일이다. 외부 인용 없음.

### 코드

- [`app/infrastructure/db/migrations/001_schema.sql`](../../final_project_cs/app/infrastructure/db/migrations/001_schema.sql) — Core 테이블 14종, 결제 없음
- [`app/infrastructure/db/migrations/002_domain_commerce.sql`](../../final_project_cs/app/infrastructure/db/migrations/002_domain_commerce.sql) — `orders.total_cents` 단일 금액 칸(17행), `orders.status` 주석(19행)
- [`app/modules/customer_ops/procurement_order_payment.py`](../../final_project_cs/app/modules/customer_ops/procurement_order_payment.py) — capability 목록(31행), `payment.status` 구현(256~268행), 허용 도구(35행)
- [`app/modules/customer_ops/return_refund.py`](../../final_project_cs/app/modules/customer_ops/return_refund.py) — 허용 도구(25행), **환불 계산식(139~148행)**
- [`app/modules/customer_ops/fulfillment_logistics.py`](../../final_project_cs/app/modules/customer_ops/fulfillment_logistics.py) — 허용 도구(19행)
- [`app/modules/customer_ops/catalog_verification.py`](../../final_project_cs/app/modules/customer_ops/catalog_verification.py) — 허용 도구(21행)
- [`app/modules/customer_ops/response_review.py`](../../final_project_cs/app/modules/customer_ops/response_review.py) — 허용 도구(28행)
- [`app/infrastructure/messaging/mock_payment_publisher.py`](../../final_project_cs/app/infrastructure/messaging/mock_payment_publisher.py) — `MockProviderPublisher`(18행), 파일명 불일치

### 테스트

- [`tests/architecture/test_basement_is_domain_free.py`](../../final_project_cs/tests/architecture/test_basement_is_domain_free.py) — `DOMAIN_WORDS`에 `payment` 포함(35~40행), 예외 목록과 이유(44행~)
- `final_project_sample/tests/architecture/test_basement_is_domain_free.py` — 같은 규칙

### 데이터

- [`eval/datasets/golden.jsonl`](../../final_project_cs/eval/datasets/golden.jsonl) — 72건. 금액 관련 capability 30건(42%)

### 계획서

- [`A-COP_구현계획서_v8.md`](A-COP_구현계획서_v8.md) — §1-1 포지셔닝, §5 시스템 범위, §7 Team 원칙(side effect 금지), §9-E 근거 대조, §11 단일 원천
