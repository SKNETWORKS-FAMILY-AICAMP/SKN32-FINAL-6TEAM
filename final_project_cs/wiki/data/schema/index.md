---
type: contract
title: 스키마
description: 테이블 관계와 의미. DDL 전문은 옮겨 적지 않고 파일을 가리킨다
status: draft
tags: [data, contract]
owners: [human:미배정]
---

# 스키마

`app/infrastructure/db/migrations/`

**PostgreSQL이 업무 상태와 Action Transaction의 단일 원천이다.** DDL 전문은 실제 파일에 있다.

## Core 테이블 (도메인 무관)

`001_schema.sql` — 14종

```text
tenants
  └ customers
      └ customer_cases ──┬─ case_events        UNIQUE(case_id, aggregate_version)
                         ├─ agent_runs ── team_tasks
                         └─ action_requests ── action_approvals

knowledge_documents ── knowledge_chunks        vector(1536)
outbox · prompts · llm_calls · feedback_analytics_reports
```

| 테이블 | 무엇 | 핵심 제약 |
|---|---|---|
| `customer_cases` | Case 상태. `version` 보유 | 낙관적 동시성 기준 |
| `case_events` | append-only 이벤트 | `UNIQUE(case_id, aggregate_version)` |
| `action_requests` | 실행 요청 | `UNIQUE(tenant_id, idempotency_key)` |
| `outbox` | 발행 대기 | `UNIQUE(tenant_id, topic, dedupe_key)` — `tenant_id` 가 빠지면 테넌트끼리 충돌한다 |
| `prompts` | 프롬프트 버전 | `(prompt_key, version)` UNIQUE + sha256 immutable |
| `llm_calls` | 호출 감사 | `prompt_id` FK로 어떤 프롬프트가 만든 답인지 추적 |

**UNIQUE 제약 셋이 idempotency의 최종 방어선이다.** 애플리케이션 로직만으로는 동시성을 못 막는다.

## 도메인 테이블 (커머스)

`002_domain_commerce.sql` · `006_products_catalog.sql`

```text
orders ──┬─ order_items
         ├─ shipments
         └─ returns
products
```

```sql
orders      (order_id, tenant_id, customer_id, order_no,
             total_cents, item_count, status, ordered_at)
order_items (order_item_id, tenant_id, order_id,
             sku, name, quantity, unit_cents)
shipments   (shipment_id, tenant_id, customer_id, order_id,
             carrier, tracking_no, status, shipped_at, delivered_at)
returns     (return_id, tenant_id, customer_id, order_id,
             reason_code, quantity, status, requested_at)
```

## ★ 결제 테이블이 없다

`[실측]` 마이그레이션 6개 전체에 `payments`가 없다. 의도된 것이다. → [../../../wiki/decisions/D-001-payment-ownership.md](../../../../wiki/decisions/D-001-payment-ownership.md)

결제 상태는 `orders.status`에 섞여 있다.

```sql
status text NOT NULL,  -- placed / paid / shipped / delivered / cancelled
```

**주문 진행 상태와 결제 사건이 한 칸에 있다.** 지저분하지만 지금 틀린 답을 만들지는 않는다.

## ★ 금액 칸이 하나뿐이다 — 그런데 절반은 있다

```sql
orders.total_cents  int NOT NULL
```

**정가인지 실결제액인지 구분이 없다.** 할인·포인트·쿠폰이 들어갈 자리가 없다.

**다만 `order_items.unit_cents`가 이미 있다.** 품목별 단가를 안다.

```
현재 환불 계산: total_cents × 수량 ÷ item_count   ← 균등 분할 가정
가능한 개선  : order_items.unit_cents 로 품목별 배분
```

`[실측]` 즉 **"모든 품목 값이 같다"는 가정은 지금 데이터로도 버릴 수 있다.** 남은 문제는 할인 반영이다.

| 문제 | 해결 가능한가 |
|---|---|
| 균등 분할 가정 | **가능.** `order_items.unit_cents` 사용 |
| 할인·쿠폰 미반영 | **불가.** 실결제액 칸이 없다 → 쇼핑몰이 줘야 함 |

## tenant 격리

`[실측]` 인덱스 주석이 규칙을 밝힌다.

```sql
-- ★조회는 항상 tenant_id + customer_id 로 좁힌다(설계 원칙 §1).
CREATE INDEX orders_tenant_customer_idx    ON orders (tenant_id, customer_id);
CREATE INDEX shipments_tenant_customer_idx ON shipments (tenant_id, customer_id);
CREATE INDEX returns_tenant_customer_idx   ON returns (tenant_id, customer_id);
```

**조건 없는 조회 쿼리는 그 자체가 보안 결함이다.**

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-SEC-005` | 같은 tenant 안에서도 customer 간 누출이 없다 | automated | `tests/security/test_query_scope.py::test_case_list_does_not_leak_across_customers_in_one_tenant` |
| `INV-CS-SEC-006` | customer 미지정 조회도 tenant를 벗어나지 않는다 | automated | `tests/security/test_query_scope.py::test_case_list_without_customer_stays_inside_the_tenant` |

## 임베딩 차원

`knowledge_chunks.embedding vector(1536)` — `text-embedding-3-small` 기준.

**모델을 바꾸면 DDL과 적재분을 함께 바꿔야 한다.**

## 상태를 바꾸는 법

`customer_cases`를 직접 `UPDATE`하지 않는다. `transition_case()`만이 진입점이다.

`case_events`는 append-only다. `UPDATE`·`DELETE`하지 않는다.

→ [../runtime/case-lifecycle.md](../../runtime/case-lifecycle.md)

---

## 필드 전체 명세

`[실측]` 2026-09-03. 계약 원문의 필드·타입·제약을 전부 옮겼다.

→ **[fields.md](fields.md)**

**여기는 개념이고 거기는 명세다.** 구현할 때는 그쪽을 본다.

