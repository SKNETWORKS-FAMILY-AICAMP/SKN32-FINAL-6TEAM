---
type: concept
title: tenant 격리
description: 모든 조회에 tenant_id를 넣는다. 조건 없는 쿼리는 그 자체가 보안 결함이다
status: draft
tags: [security, data]
owners: [human:미배정]
---

# tenant 격리

## 규칙 하나

> **모든 query에 `tenant_id`와 `customer_id`(또는 `case_id`) 조건을 적용한다.**

**조건 없는 조회 쿼리는 그 자체가 보안 결함이다.** 결과가 비어 있어도 결함이다. 데이터가 늘면 새기 시작한다.

## 두 층

```text
tenant   도입 기업 단위        다른 회사 데이터가 보이면 안 됨
customer 그 회사의 고객 단위    다른 고객 데이터가 보이면 안 됨
```

**둘 다 필요하다.** tenant만 막으면 같은 회사 안에서 고객 간에 샌다.

## 불변식

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-SEC-005` | 같은 tenant 안에서도 customer 간 누출이 없다 | automated | `tests/security/test_query_scope.py::test_case_list_does_not_leak_across_customers_in_one_tenant` |
| `INV-CS-SEC-006` | customer 미지정 조회도 tenant를 벗어나지 않는다 | automated | `tests/security/test_query_scope.py::test_case_list_without_customer_stays_inside_the_tenant` |

**006이 미묘하다.** `customer_id`를 안 넘기는 조회도 있다(운영자 화면 등). 그때도 tenant는 벗어나면 안 된다.

**필터가 하나 빠졌을 때 전체가 열리는 걸 막는다.**

## 인덱스가 받친다

```sql
CREATE INDEX orders_tenant_customer_idx    ON orders (tenant_id, customer_id);
CREATE INDEX shipments_tenant_customer_idx ON shipments (tenant_id, customer_id);
CREATE INDEX returns_tenant_customer_idx   ON returns (tenant_id, customer_id);
```

**복합 인덱스 순서가 `(tenant_id, customer_id)`다.** tenant만으로 좁히는 조회도 이 인덱스를 탄다.

## outbox도 격리한다

`003_outbox_tenant_scoped_dedupe.sql`

**다른 테넌트의 같은 `dedupe_key`가 서로를 막으면 안 된다.**

두 회사가 우연히 같은 키를 만들면 한쪽 메시지가 발행되지 않는다. **조용히 안 나간다** — 가장 나쁜 실패다.

```
tests/integration/messaging/test_outbox_tenant_guard.py
```

## 없는 것을 요청하면

**404다. 403이 아니다.**

403은 "있는데 권한이 없다"를 알려준다. 그것만으로도 정보가 샌다.

## 시드 데이터로 확인한다

`[실측]` 테스트 후 `tenants=1`이 유지되는지 센다. 테스트가 테넌트를 늘려 놓으면 격리 검사가 무의미해진다.

## RAG도 격리한다

`knowledge_documents`에 `tenant_id`와 `scope`가 있다.

**검색 결과가 다른 테넌트 문서를 가져오면 안 된다.**

```
tests/integration/rag/
```

→ [../context/rag-retrieval.md](../context/rag-retrieval.md)

## PII와 다른 문제다

| | tenant 격리 | PII 마스킹 |
|---|---|---|
| 막는 것 | **남의 데이터를 보는 것** | 내 데이터가 원문으로 남는 것 |
| 어디서 | 쿼리 | 저장·전달 |
| 불변식 | `SEC-005` `SEC-006` | `SEC-004` |

**둘 다 필요하다.** 격리만 하면 자기 PII가 audit에 원문으로 남고, 마스킹만 하면 남의 마스킹된 데이터가 보인다.

## 관계

- [schema.md](schema.md) — 테이블별 `tenant_id`
- [migrations.md](migrations.md) — 인덱스
- [../external/auth-boundary.md](../external/auth-boundary.md) — 인증·scope
- [../context/rag-retrieval.md](../context/rag-retrieval.md) — 지식 검색 격리
