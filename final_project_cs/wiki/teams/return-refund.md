---
type: concept
title: Return & Refund Team
description: 반품 가능 여부와 환불 금액을 판단해 제안한다. 현재 계산식에 알려진 결함이 있다
status: draft
tags: [agent, customer-operations]
owners: [human:미배정]
domain: commerce
domain_note: v10 §0-2 가 MVP 경로에서 제외한 커머스 Team 이다. 코드에는 아직 등록돼 있다
---

# Return & Refund Team

`app/modules/customer_ops/return_refund.py`

## manifest

`[실측]`

```python
capabilities        = ["return.check_eligibility", "return.request", "refund.calculate"]
accepted_case_types = ["return", "refund", "exchange"]
required_context    = ["case_state", "policy", "db_facts", "history"]
allowed_tools       = ["read.order", "read.return", "read.policy"]
knowledge_scope     = ["order", "return", "refund", "exchange", "policy"]
max_steps           = 6
```

**Commerce Ops Pack.** 검증 쇼핑몰 일정에 따라 조정된다.

## 무엇을 하는가

```text
capability 판정
   ↓ 모르는 capability면 escalate (unsupported_capability)
read.order · read.return · read.policy
   ↓ 도구 반복 초과면 escalate (tool_loop_guard)
근거(Evidence) 조립
   ↓
기간·수량 판정
   ↓
ActionProposal 생성 → wait_for_approval
```

## 도구 루프 가드

`[실측]` `seen` 집합으로 같은 도구를 반복 호출하는 걸 막는다.

```python
seen: set[str] = set()
try:
    order = self.tools.call("read.order", task.context, {}, task.allowed_tools, seen)
    ...
except ToolLoopExceeded:
    return self._result(task, outcome="escalated", failure_code="tool_loop_guard")
```

**루프에 빠지면 조용히 도는 게 아니라 escalate한다.**

## 근거가 없으면 계산하지 않는다

```python
if not isinstance(total, int) or not isinstance(item_count, int) or item_count <= 0:
    return self._result(task, outcome="escalated",
                        failure_code="refund_calculation_evidence_missing")
```

**추정으로 채우지 않는다.** 모르면 사람에게 넘긴다.

## 환불은 항상 승인을 거친다

```python
approval_required=True, risk_level="medium"
next_action=NextAction.WAIT_FOR_APPROVAL, wait_reason="human_approval"
```

**돈이 나가는 동작이라 자동 실행하지 않는다.**

`warnings`에도 명시한다.

```
"Mock 단계에서는 승인 제안만 생성하며 실제 처리는 수행하지 않습니다."
```

`decisions`에 `mock_side_effect: False`가 붙는다. **지금 단계에서 실제 환불이 나가지 않는다는 걸 데이터로 남긴다.**

## ★ 알려진 결함 — 환불 계산식

`[실측]` 현재 계산.

```python
amount = total * int(quantity) // item_count
```

두 가정에 기대고 있다.

| 가정 | 성립하나 | 고칠 수 있나 |
|---|---|---|
| 모든 품목 값이 같다 | ❌ | **가능.** `order_items.unit_cents`가 이미 있다 |
| 할인이 없다 | ❌ | 불가. 실결제액 칸이 없다 |

터지는 방식.

```
30,000원 주문 · 5,000원 쿠폰 → 실결제 25,000원
2개 중 1개 반품

우리 안내: 30,000 × 1 ÷ 2 = 15,000원
실제 입금: 25,000 × 1 ÷ 2 = 12,500원
                            차액 2,500원
```

**근거 대조로 안 잡힌다.** `INV-CS-VER-002`는 "환불 ≤ 주문 총액"만 보는데 15,000 ≤ 30,000이라 통과한다.

`calculation_basis`에 근거를 남기고는 있다.

```python
"calculation_basis": {"order_total_cents": total, "order_item_count": item_count}
```

**근거를 남겨도 근거 자체가 틀린 기준이면 소용없다.**

조치는 [중앙 허브 D-001](../../../wiki/decisions/D-001-payment-ownership.md). **1-A(품목별 배분)는 지금 할 수 있다.**

## 골든셋 비중

`[실측]` 이 Team의 capability가 걸린 케이스가 72건 중 30건(42%)이다.

| capability | 건수 |
|---|---|
| `return.request` | 13 |
| `return.check_eligibility` | 10 |
| `refund.calculate` | 7 |

**금액이 걸린 케이스가 가장 많다.** 그래서 계산식 결함이 위험하다.

## 관계

- [team-contract.md](team-contract/index.md) — 계약
- [team-boundary.md](team-boundary.md) — 경계
- [../actions/action-proposal.md](../actions/action-proposal.md) — 제안 구조
- [../actions/evidence-check.md](../actions/evidence-check.md) — 대조가 못 잡는 것
- [../data/schema/index.md](../data/schema/index.md) — `order_items.unit_cents`
- [../../../wiki/decisions/D-001-payment-ownership.md](../../../wiki/decisions/D-001-payment-ownership.md) — 조치안
