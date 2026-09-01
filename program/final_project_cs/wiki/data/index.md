---
type: guide
title: Data
description: 스키마·마이그레이션·tenant 격리. DDL 전문은 문서에 옮겨 적지 않는다
status: draft
---

# Data

`app/infrastructure/db/`

**PostgreSQL이 업무 상태와 Action Transaction의 단일 원천이다.**

## 각 문서

| 문서 | 답하는 질문 |
|---|---|
| [schema.md](schema.md) | 테이블 관계와 의미 |
| [migrations.md](migrations.md) | 마이그레이션 6개와 순서 |
| [tenancy.md](tenancy.md) | tenant 격리를 어떻게 보장하는가 |

**DDL 전문은 여기 옮겨 적지 않는다.** 실제 파일을 가리킨다.

## 마이그레이션

`[실측]` `app/infrastructure/db/migrations/`

| 파일 | 무엇 |
|---|---|
| `001_schema.sql` | Core 테이블 14종 |
| `002_domain_commerce.sql` | orders, order_items, shipments, returns |
| `003_outbox_tenant_scoped_dedupe.sql` | outbox 중복 제거 범위 |
| `004_agent_runs_active_uniqueness.sql` | 실행 중복 방지 |
| `005_outbox_resolution.sql` | outbox 해소 |
| `006_products_catalog.sql` | products |

## 테이블 지도

**Core (도메인 무관)**

```
tenants → customers → customer_cases → case_events
                    ↘ agent_runs → team_tasks
                    ↘ action_requests → action_approvals
knowledge_documents → knowledge_chunks
outbox · prompts · llm_calls · feedback_analytics_reports
```

**도메인 (커머스)**

```
orders → order_items
      ↘ shipments
      ↘ returns
products
```

## ★ 결제 테이블이 없다

`[실측]` 마이그레이션 6개 전체에 `payments` 테이블이 없다. 결제 상태는 `orders.status`에 섞여 있다.

```sql
-- 002_domain_commerce.sql:19
status text NOT NULL,  -- placed / paid / shipped / delivered / cancelled
```

**주문 진행 상태와 결제 상태가 한 칸에 있다.** 의도된 것이고 결정 근거는 [D-001](../../../wiki/decisions/D-001-payment-ownership.md).

### 금액 칸이 하나뿐이다

```sql
-- 002_domain_commerce.sql:17
total_cents int NOT NULL,
```

**정가인지 실결제액인지 구분이 없다.** 할인·포인트·쿠폰이 들어갈 자리가 없다.

이게 [../teams/return-refund.md](../teams/return-refund.md)의 환불 계산이 할인에 취약한 근본 원인이다.

## 이 영역의 불변식

| ID | 불변식 | 판정 |
|---|---|---|
| `INV-CS-SEC-005` | 같은 tenant 안에서도 customer 간 누출이 없다 | automated |
| `INV-CS-SEC-006` | customer 미지정 조회도 tenant를 벗어나지 않는다 | automated |

**모든 조회에 `tenant_id`가 들어간다.** 빠뜨리면 위 테스트가 실패한다.

## 인접 영역

- [../runtime/shared-state.md](../runtime/shared-state.md) — 상태가 저장되는 방식
- [../context/index.md](../context/index.md) — 여기서 읽어 간다
- [../actions/outbox.md](../actions/outbox.md) — outbox 테이블
