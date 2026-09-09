---
type: guide
title: 마이그레이션
description: 6개 파일과 순서. 재실행이 안전하다
status: draft
tags: [data]
owners: [human:미배정]
domain: commerce
domain_note: 코드가 아직 커머스다 — 여행 전환 층 5(DB 도메인 표 19표 중 여행 표 0개) 미완. 문서는 코드를 정확히 적고 있다. 코드가 옮겨지면 이 문서도 같이 옮긴다 — program/plan/A-COP_여행전환_현황_2026-09-09.md
---

# 마이그레이션

`app/infrastructure/db/migrations/`

## 6개

`[실측]`

| 파일 | 무엇 | 왜 나중에 |
|---|---|---|
| `001_schema.sql` | Core 테이블 14종 | 기반 |
| `002_domain_commerce.sql` | orders · order_items · shipments · returns | 도메인 |
| `003_outbox_tenant_scoped_dedupe.sql` | outbox 중복 제거를 tenant 범위로 | 격리 결함 수정 |
| `004_agent_runs_active_uniqueness.sql` | 동시 실행 방지 | 동시성 결함 수정 |
| `005_outbox_resolution.sql` | outbox 해소 상태 | 운영 중 필요해짐 |
| `006_products_catalog.sql` | products | Catalog Team 착수 |
| **`007_returns_order_item.sql`** | **`returns.order_item_id`** | **환불 금액 추정 결함 수정** |

**003·004·007이 결함 수정에서 나왔다.** 처음 설계에 없던 제약이 운영·테스트에서 발견돼 추가됐다.

### ★ 007 — 환불 금액을 지어내던 것을 막았다

`[실측]` 2026-09-01. [D-001](../../../wiki/decisions/D-001-payment-ownership.md) 1-A 후속.

`returns` 에는 `order_id`·`reason_code`·`quantity` 만 있었다. **"주문 X 에서 3개 반품"은 알지만 어느 품목인지를 몰랐다.**

그래서 환불 금액을 이렇게 계산하고 있었다.

```python
amount = total * int(quantity) // item_count   # 주문 총액의 균등 분할
```

**품목 값이 서로 다르면 이 액수는 근거가 없다.** 할인이 걸려 있어도 마찬가지다.

#### NULL 을 허용한 게 핵심이다

**이미 쌓인 반품 행에는 품목 정보가 없다.** 지금 와서 채우면 그건 지어낸 값이다.

> `NULL` 은 **"모른다"**이고, 모르면 다품목 주문에서 **금액을 만들지 않고 사람에게 넘긴다.**

**빈 값을 그럴듯한 값으로 메우지 않는다.** [D-005](../../../wiki/decisions/D-005-write-gate.md)와 같은 원칙이다.

## 계획서보다 테이블이 5개 많다

`[실측]` 2026-09-01 기준.

| | 테이블 |
|---|---|
| 계획서 v8 §22 DDL 전문 | **14** |
| 실제 migrations | **19** |

**차이 5개가 다 도메인 쪽이다.**

```
orders · order_items · shipments · returns   (002)
products                                     (006)
```

**계획서 §22 는 Core 스키마만 적고 있다.** 도메인 커머스 테이블은 검증 쇼핑몰 연계가 결정되면서 나중에 붙었다.

`[미확보]` **§22 를 갱신할지 "Core 만"이라고 명시할지 정해지지 않았다.** 지금은 §22 만 읽은 사람이 테이블 수를 14로 안다.

## 재실행이 안전하다

전부 `CREATE TABLE IF NOT EXISTS` · `CREATE INDEX IF NOT EXISTS`다.

**여러 번 돌려도 같은 결과다.** 개발 중에 반복 실행하게 되므로 중요하다.

## 빠뜨리면 무너지는 제약 셋

`[실측]` handoff 계약이 "★빠뜨리면 시스템이 무너지는 제약 3개"로 따로 표시한 것들.

```sql
case_events     UNIQUE (case_id, aggregate_version)
action_requests UNIQUE (tenant_id, idempotency_key)
outbox          UNIQUE (tenant_id, topic, dedupe_key)
```

★`[정정 2026-09-07]` `outbox` 는 오래 `UNIQUE (topic, dedupe_key)` 로 적혀 있었다.
`003_outbox_tenant_scoped_dedupe.sql` 이 `tenant_id` 를 넣은 뒤에도 여러 문서가 옛
제약을 실었다. 살아 있는 DB 에서 `pg_constraint` 를 읽어 확인한 값이 위의 것이다
(`outbox_tenant_topic_dedupe_key_key`). 경위는 [outbox.md](../actions/outbox.md).

| 제약 | 없으면 |
|---|---|
| `case_events` | 같은 버전 이벤트가 두 번 들어가 상태가 갈린다 |
| `action_requests` | 같은 요청이 두 번 실행된다 |
| `outbox` | 같은 메시지가 두 번 발행된다 |

**애플리케이션 로직만으로는 동시성을 못 막는다.** DB 제약이 최종 방어선이다.

→ [../actions/idempotency.md](../actions/idempotency.md)

## 인덱스

`[실측]` 조회 격리를 받치는 인덱스.

```sql
orders_tenant_customer_idx     (tenant_id, customer_id)
shipments_tenant_customer_idx  (tenant_id, customer_id)
returns_tenant_customer_idx    (tenant_id, customer_id)
```

주석이 규칙을 밝힌다.

```sql
-- ★조회는 항상 tenant_id + customer_id 로 좁힌다(설계 원칙 §1).
```

## extension

```
vector     임베딩 vector(1536)
pgcrypto   gen_random_uuid()
```

**둘 다 없으면 001이 실패한다.**

## 환경 주의

`[실측]` **PostgreSQL이 Windows 서비스가 아니다.** conda env `pgv`에서 뜬 프로세스다. 재부팅 후 안 떠 있을 수 있다.

```
127.0.0.1:5433
```

`psql`이 PATH에 없다. → [../operations/local-setup.md](../operations/local-setup.md)

**Docker가 설치돼 있지 않다.** `docker/compose.yml`로 DB를 띄우는 전제는 이 기계에서 성립하지 않는다. 로컬 PG를 쓰고 compose 파일은 재현용으로만 남긴다.

## 임베딩 차원을 바꾸려면

```sql
knowledge_chunks.embedding vector(1536)   -- text-embedding-3-small
```

**모델을 바꾸면 DDL과 적재분을 함께 바꿔야 한다.** 차원이 다르면 기존 임베딩을 다 버려야 한다.

## 스키마를 바꾸려면

| 함께 해야 할 것 |
|---|
| 영향받는 Team 확인 |
| 계약(`contracts.py`) 대조 |
| 회귀 테스트 |
| handoff 문서 갱신 |

`[실측]` `app/core/contracts.py`는 `wiki/records/handoff/01_계약_Pydantic.md`의 **구현체다. 둘이 어긋나면 결함이다.**

## 관계

- [schema.md](schema/index.md) — 테이블 의미
- [tenancy.md](tenancy.md) — 격리
- [../operations/local-setup.md](../operations/local-setup.md) — DB 기동
- [../actions/idempotency.md](../actions/idempotency.md) — UNIQUE 제약의 역할
