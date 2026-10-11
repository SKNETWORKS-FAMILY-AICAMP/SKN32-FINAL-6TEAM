---
type: runbook
title: 도메인을 갈아 끼우는 절차
description: basement 를 새 도메인에 복사할 때 무엇을 바꾸고 무엇을 안 바꾸나. 순서가 있다
status: draft
tags: [architecture, data, contract]
domain: neutral
---

# 도메인을 갈아 끼우는 절차

`[실측]` `final_project_cs/wiki/records/handoff/10_도메인_교체_가이드.md` 에서 이관.

**이 문서가 sample 이 혼자 서는 것의 실무 절차다.** [another-domain.md](another-domain.md) 가 "된다"를 증명한다면, 여기는 "어떻게 하나"다.

## ★ 이 문서가 생긴 이유

`[실측]` 2026-08-16 에 `core/verification.py` 가 **구독·결제 어휘를 Core 에 박고 있었다.**

> 그 상태로 쇼핑몰에 복사했다면 **`order_id` 가 "확인 불가 → 자동 거부"** 에 걸렸을 것이다.
>
> **그 도메인의 가장 중요한 식별자가 basement 의 거부 목록에 있는 정반대 상황이다.**

원인이 명확했다.

> 계획서 표가 `payment_id`·`amount` 를 **예시로** 든 것을 **스펙으로 읽은 탓**이었다.
>
> **계획서의 예시는 그 계획서의 도메인일 뿐이다.**

> **basement 에는 메커니즘만 올라가고, 어휘는 선언으로 내려간다.**

## 갈아 끼우는 것 — 순서대로

### 1. 도메인 테이블

```
migrations/002_domain_<이전>.sql  →  002_domain_<새것>.sql
# [2026-09-10] sample 의 도메인 SQL 은 config/migrations/ 에 있다(지금 002_domain_customer_ops.sql).
#   Core SQL(acop_basement/infrastructure/db/migrations/)과 합쳐 파일명순으로 적용한다 — collect_migration_files()
```

`[실측]` **`001_schema.sql`(Core 14 테이블)은 손대지 않는다.**

`migrate.py` 가 `sorted(glob("*.sql"))` 로 전부 읽으므로 **파일만 두면 적용된다.**

### 2. 대조 선언

```python
VerificationPolicy(
    references={"order_id": "orders", "shipment_id": "shipments"},
    quantities=(QuantityRule("refund_amount", "order_id", "total_cents", scale=Decimal(100)),),
    opaque=frozenset({"coupon_id"}),        # 아직 대조 수단이 없는 것
    ignored=frozenset({"reason", "template"}),
)
```

**네 칸이 도메인이고 나머지가 엔진이다.**

`[실측]` **`opaque` 의 뜻이 강하다.**

> **`opaque` 에 넣는다는 것은 "확인 못 하니 거부한다"는 선언이다.**

**모르는 것을 통과시키지 않는다.** `ignored` 와 반대다 — 그건 "대조 대상이 아니다"이고 `opaque` 는 "대조해야 하는데 수단이 없다"다.

### 3. FACT_QUERIES

대조에 쓸 사실을 어디서 읽을지 선언한다.

```python
FACT_QUERIES = (("orders",
                 "SELECT order_id, total_cents, status FROM orders WHERE tenant_id=%s AND customer_id=%s",
                 ("order_id", "total_cents", "status")),)
```

**`tenant_id` 가 쿼리에 박혀 있다.** 도메인을 바꿔도 격리는 안 바뀐다.

## 갈아 끼우지 않는 것

**basement 전부다.** → [domain-free.md](domain-free.md)

`[실측]` 무엇이 basement 인지는 [invariants.md](invariants.md) 의 `INV-SAMPLE-ARCH-001` 이 강제한다.

## 복사 후 첫 검증

**새 도메인 선언으로 `test_engine_serves_another_domain.py` 를 돌린다.**

```bash
python -m pytest tests/architecture/test_engine_serves_another_domain.py -q
# 10 passed in 0.04s        (2026-09-02 확인, 쇼핑몰 선언 기준)
```

**깨지면 basement 가 특정 도메인에 묶였다는 뜻이다.**

## 관계

- [another-domain.md](another-domain.md) — 된다는 증명
- [domain-free.md](domain-free.md) — 무엇이 격리되나
- [verification.md](verification.md) — 대조 규칙
- [invariants.md](invariants.md) — 강제되는 것
