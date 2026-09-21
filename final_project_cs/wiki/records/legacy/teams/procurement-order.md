---
type: concept
title: Procurement + Order & Payment Team
description: 견적·주문·결제 상태를 다룬다. 이름에 Payment가 있지만 결제 조회 권한이 없다
status: draft
tags: [agent, customer-operations]
owners: [human:미배정]
domain: commerce
domain_note: v10 §0-2 가 MVP 경로에서 제외한 커머스 Team 이다. 2026-09-09 에 config/project.yaml 등록에서 빠졌고 소스만 app/modules/customer_ops/ 에 남아 있다
---

# Procurement + Order & Payment Team

`app/modules/customer_ops/procurement_order_payment.py`

**Commerce Ops Pack.** 검증 쇼핑몰 일정에 따라 조정된다.

## manifest

`[실측]`

```python
capabilities = [
    "procurement.quote", "order.verify", "order.create",
    "order.modify", "order.cancel", "payment.status",
]
accepted_case_types = ["procurement", "order", "payment"]
required_context    = ["case_state", "policy", "db_facts", "history"]
allowed_tools       = ["read.order", "read.account", "read.policy", "read.catalog"]
knowledge_scope     = ["catalog", "pricing", "order", "payment", "procurement"]
max_steps           = 6
```

**capability 6개로 가장 많다.** 조달과 주문과 결제를 통합한 Team이라서다.

## ★ 이름이 권한보다 넓다

**"Payment"가 이름에 있는데 결제 조회 도구가 없다.**

```python
allowed_tools = ["read.order", "read.account", "read.policy", "read.catalog"]
```

read 도구 7종 중 결제용은 애초에 없다. → [../actions/tool-gateway.md](../../../actions/tool-gateway.md)

## `payment.status`는 DB를 읽지 않는다

`[실측]`

```python
payment = task.context.current_state.get("payment") or task.context.current_state.get("payment_status")
...
if not payment:
    return self._escalate(task, "payment_status_evidence_missing")
```

**넘겨받은 값을 그대로 돌려주고 없으면 사람에게 넘긴다.**

근거 문자열도 그렇게 적혀 있다.

```
"payment status supplied by the local context/database facts"
```

**이미 올바른 방향이다.** 결제를 소유하지 않고 상태를 설명만 한다. → [../../../wiki/decisions/D-001-payment-ownership.md](../../../../../wiki/decisions/D-001-payment-ownership.md)

## 왜 통합 Team인가

조달·주문·결제를 따로 나누지 않았다.

**셋이 한 흐름이기 때문이다.** 견적 → 주문 → 결제가 순서대로 이어지고, 중간에 다른 Team이 끼면 상태를 주고받는 비용이 커진다.

Team을 너무 잘게 쪼개면 Controller 라우팅이 복잡해지고 평가 축이 늘어난다. → [../../../wiki/architecture/core-vs-team.md](../../../../../wiki/architecture/core-vs-team.md)

## 근거 없이 답하지 않는다

`[실측]` dojo가 심어 본 결함이 이 Team에서 잡혔다.

```
"제안이 근거 id 를 달지 않는다"
  → test_proposal_carries_the_evidence_it_was_built_from 이 잡음
```

**모든 제안은 `rationale_evidence_ids`를 달아야 한다.** → [../actions/evidence-check.md](../../../actions/evidence-check.md)

## 검증 쇼핑몰 의존

이 Team이 실제로 동작하려면 검증 쇼핑몰이 주문·결제 데이터를 줘야 한다.

`[미확보]` 협의 창구와 필드 계약이 아직 안 정해졌다. → [../../../wiki/decisions/D-001-payment-ownership.md](../../../../../wiki/decisions/D-001-payment-ownership.md) 조치 5

## 관계

- [team-contract.md](../../../teams/team-contract/index.md) — 계약
- [return-refund.md](return-refund.md) — 환불 쪽
- [fulfillment-logistics.md](fulfillment-logistics.md) — 배송 쪽
- [../../../wiki/decisions/D-001-payment-ownership.md](../../../../../wiki/decisions/D-001-payment-ownership.md) — 결제 경계
