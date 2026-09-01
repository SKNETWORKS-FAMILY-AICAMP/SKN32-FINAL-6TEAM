---
type: decision
title: 결제 소유 경계
description: 결제 실행은 검증 쇼핑몰이 소유하고 A-COP은 구성을 읽어 대조만 한다
status: draft
tags: [contract, customer-operations]
owners: [human:미배정]
sources:
  - id: S1
    title: DB 마이그레이션 6개
    resource: ../../../final_project_cs/app/infrastructure/db/migrations/
  - id: S2
    title: payment.status 구현
    resource: ../../../final_project_cs/app/modules/customer_ops/procurement_order_payment.py
  - id: S3
    title: 환불 계산식
    resource: ../../../final_project_cs/app/modules/customer_ops/return_refund.py
  - id: S4
    title: Core 도메인 격리 테스트
    resource: ../../../final_project_cs/tests/architecture/test_basement_is_domain_free.py
---

# D-001 결제 소유 경계

## 맥락

Team 이름에 "Payment"가 들어가 있고 `payment.status` capability가 있어서, 결제를 A-COP이 어디까지 다루는지 불명확했다. 검증 쇼핑몰과 연계하기 전에 경계를 확정해야 했다.

포인트·캐시·쿠폰을 넣을지도 같이 물어봤다.

## 결정

> **결제 실행은 검증 쇼핑몰이 소유한다. A-COP은 결제 구성을 읽어 설명하고 대조만 한다.**

경계선은 읽기냐 쓰기냐가 아니라 **설명이냐 실행이냐**다.

포인트·캐시·쿠폰은 **읽기 도구 하나만** 갖는다. 잔액을 바꾸는 모든 것은 쇼핑몰이다.

## 지금 상태 — 거의 이미 그렇다

`[실측:S1]` DB 마이그레이션 6개 전체에 `payments` 테이블이 없다. 결제 상태는 `orders.status`에 섞여 있는 게 전부다.

```sql
-- 002_domain_commerce.sql:19
status  text NOT NULL,  -- placed / paid / shipped / delivered / cancelled
```

`[실측:S2]` `payment.status`는 DB를 읽지 않는다. 넘겨받은 값을 그대로 돌려주고 없으면 사람에게 넘긴다.

```python
payment = task.context.current_state.get("payment") or task.context.current_state.get("payment_status")
if not payment:
    return self._escalate(task, "payment_status_evidence_missing")
```

`[실측]` Team이 쓸 수 있는 read 도구 7종에 결제용이 없다. **Team 이름이 실제 권한보다 넓다.**

`[실측]` 포인트·캐시·쿠폰은 코드에도 DB에도 전혀 없다.

**즉 이 결정은 새로 만드는 게 아니라 이미 코드에 있는 상태를 문서로 확정하는 것이다.**

## 선택지와 이유

| 안 | 채택 | 이유 |
|---|---|---|
| A-COP이 결제를 소유 | ❌ | 파는 물건의 성격이 바뀐다. PCI-DSS 부담이 고객사가 아니라 우리에게 온다 |
| 잔액만 A-COP이 관리 | ❌ | 도입 기업엔 이미 결제 시스템이 있다. 이중 장부가 된다 |
| **읽기만. 실행은 쇼핑몰** | ✅ | 현재 구조와 일치. 규제 부담 없음 |
| 결제를 아예 안 봄 | ❌ | 환불 금액을 설명할 수 없다. 골든셋 42%가 금액 관련이다 |

### 근거 4가지

**1. 우리가 파는 물건이 그게 아니다.** A-COP은 고객 응대를 구성하는 플랫폼이다. 결제를 가지면 커머스 시스템이 되고 "결제를 우리 것으로 바꾸라"고 요구하는 제품이 된다.

**2. 자체호스팅 목표와 충돌한다.** 고객사 환경에 올려 데이터가 안 나가게 하는 게 차별점인데, 결제를 우리가 들면 규제 부담이 **우리에게** 온다.

**3. 이중 장부가 된다.** 우리가 잔액을 들면 어느 쪽이 진짜인지 판정할 수 없다. "업무 상태는 한 곳에만 둔다"는 원칙과 같은 이유다.

**4. Team은 side effect를 실행하지 않는다.** 이미 정한 원칙이고, **결제는 side effect의 극단이다.** 이 원칙을 결제에 적용하지 않을 근거가 없다.

`[실측:S4]` 그리고 코드가 이미 막고 있다. Core 계층 테스트가 `payment`를 금지어로 걸어 뒀다.

```python
DOMAIN_WORDS = (
    "payment", "subscription", "entitlement", "refund", "invoice",
    "order_id", "line_item", "shipment", "sku", "cart",
)
```

## 경계

| A-COP | 검증 쇼핑몰 |
|---|---|
| 결제 구성 **읽기** (카드 얼마 / 포인트 얼마 / 쿠폰 얼마) | 승인·취소·부분취소 **실행** |
| 환불 금액 **설명·대조** | 환불 **집행** |
| "포인트도 돌려받나" 정책 **답변** | 잔액 증감·적립·소멸 |
| 불일치 시 **escalate** | 쿠폰 발급·사용처리·복원 |

**우리가 계산하지 않는다.** 쇼핑몰이 계산한 값을 받아 대조만 한다. 그러면 결제 구성이 복잡해져도 우리 코드는 안 바뀐다.

## 포인트·캐시·쿠폰 3단계

**단계 1 (10주 안).** 결제 구성 스냅샷 읽기 도구 하나. `read.payment` 추가로 끝난다.

`[실측]` 골든셋 근거가 있다. `refund.calculate` 7건 + `return.request` 13건 + `return.check_eligibility` 10건 = **30건(42%)이 금액이 걸린 케이스**다.

**단계 2 (확장).** 잔액 조회. 개인 AI가 MCP로 물어볼 때 필요해진다.

**단계 3 (절대 안 함).** 잔액을 바꾸는 모든 것. 적립·차감·소멸·쿠폰 발급.

## ★ 결과 — 환불 계산식을 고쳐야 한다

이 결정의 직접 결과다.

`[실측:S3]` 현재 계산식.

```python
total = order.get("total_cents")
item_count = order.get("item_count")
amount = total * int(quantity) // item_count
```

두 가지를 가정한다. **모든 품목 값이 같고, 할인이 없다.** `[실측:S1]` `orders`에 금액 칸이 `total_cents` 하나뿐이라 정가·실결제액 구분이 없다.

```
30,000원 주문 · 5,000원 쿠폰 → 실결제 25,000원
2개 중 1개 반품

우리 안내: 30,000 × 1 ÷ 2 = 15,000원
실제 입금: 25,000 × 1 ÷ 2 = 12,500원
                            차액 2,500원
```

**이건 할루시네이션이 아니라 결정론적 코드의 계산 오류다.** 그래서 근거 대조로도 안 잡힌다 — 대조 대상 자체가 틀렸기 때문이다.

지금은 포인트·쿠폰이 없어서 안 터진다. **검증 쇼핑몰에 할인이 하나라도 붙으면 그날 터진다.**

## 못 하게 되는 것

- 결제 관련 질문에 A-COP 단독으로 답할 수 없다. 쇼핑몰 응답이 필요하다
- 쇼핑몰이 필드를 안 주면 환불 금액을 말할 수 없고 escalate해야 한다
- 포인트 잔액 조회를 우리가 캐시할 수 없다

## 조치안

| # | 조치 | 소유 | 성격 |
|---|---|---|---|
| 1 | 환불 금액을 **쇼핑몰 계산값 대조** 구조로 변경 | cs | **계약 변경** |
| 2 | `read.payment` 도구 추가 | cs | 신규 |
| 3 | `orders`에서 결제 상태 분리 판단 | 스키마 | 스키마 |
| 4 | `mock_payment_publisher.py` 파일명 정리 | cs | 정리 |
| 5 | 검증 쇼핑몰에 필요 응답 필드 전달 | 검증 쇼핑몰 | **계약 협의** |

**1번과 5번이 짝이다.** 우리가 계산을 그만두려면 쇼핑몰이 계산 결과를 줘야 한다. 저장소 간 계약이라 검증 쇼핑몰 일정과 맞물린다.

**3번은 서두르지 않아도 된다.** 지저분하지만 지금 당장 틀린 답을 만들지는 않는다.

### 쇼핑몰에 요청할 필드 `[추정]`

| 필드 | 왜 |
|---|---|
| 실결제 금액 (정가 아님) | 환불 기준액 |
| 결제수단별 분해 (카드/포인트/캐시/쿠폰) | "포인트도 돌려받나" |
| 품목별 배분 금액 | 균등 분할 가정 폐기 |
| **쇼핑몰이 계산한 환불 예정액** | **대조 대상** |
| 환불 수단별 분해 | 고객 설명용 |

쇼핑몰 스키마를 보고 조정해야 한다.

## 남은 결정

| 항목 | 필요한 판단 |
|---|---|
| 조치 1 착수 시점 | 중간발표(2026-09-15) 전 / 후 |
| 검증 쇼핑몰 협의 창구 | 누가 언제 |
| `orders` 스키마 분리 | 스키마 담당과 합의 |

## 관계

- [../product/scope.md](../product/scope.md) — 결제 실행은 Out of Scope
- [../product/problem.md](../product/problem.md) — 이 결함이 층 1 페인의 실례
- [../business/unit-economics.md](../business/unit-economics.md) — 오류 비용의 구체 사례
- [`return-refund.md`](../../final_project_cs/wiki/teams/return-refund.md) — 구현
