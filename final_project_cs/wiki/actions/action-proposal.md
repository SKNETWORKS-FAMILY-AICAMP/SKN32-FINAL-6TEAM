---
type: contract
title: ActionProposal
description: Team이 반환하는 제안. 실행이 아니다. 근거 ID가 대조의 입력이 된다
status: draft
tags: [contract, agent]
owners: [human:미배정]
domain: neutral
domain_note: ActionProposal 계약은 도메인 무관이다. refund.request 는 예시이자 계약 테스트 이름이다
---

# ActionProposal

`app/core/contracts.py`

**Team의 출력이자 Action Layer의 입력이다.** 제안이지 실행이 아니다.

## 모양

```python
action_type   : str
arguments     : dict
idempotency_key : str          8~128자
approval_required : bool
risk_level    : low | medium | high
rationale_evidence_ids : list[str]
```

## 각 필드가 무엇을 막는가

### `idempotency_key`

**같은 요청이 두 번 실행되는 것을 막는다.**

Team이 생성하고 Core가 검사한다. 동일 키는 side effect가 1회다.

| 불변식 | 판정 |
|---|---|
| `INV-CS-ACT-001` 동일 dedupe key는 1회 | automated |
| `INV-CS-ACT-002` 동시 claim도 1회 | automated |

→ [idempotency.md](idempotency.md)

### `approval_required` + `risk_level`

**고위험 Action이 사람 승인 없이 실행되는 것을 막는다.**

Team이 제안하지만 **최종 판정은 Core가 한다.** Team이 `approval_required=False`로 줘도 Core 정책이 승인을 요구하면 승인으로 간다.

→ [approval.md](approval.md)

### `rationale_evidence_ids`

**근거 없는 주장을 막는다.**

여기 적힌 evidence ID가 `ContextPack` 또는 DB에 실재하는지 Core가 대조한다. 없으면 실행하지 않고 escalate한다.

→ [evidence-check.md](evidence-check.md)

## 흐름에서의 위치

```text
Team
 └→ ActionProposal          ← 여기
      ↓
    근거 대조                evidence-check.md
      ↓
    위험도 판정
      ├→ 저위험: 자동 실행
      └→ 고위험: 사람 승인   approval.md
             ↓
        Action 실행          tool-gateway.md
             ↓
        Outbox 발행          outbox.md
```

## 계약이 강제하는 것

`[실측]` `TeamResult`의 `model_validator`가 검사한다.

```
next_action == wait_for_approval
  → action_proposals 가 최소 1건 있어야 한다
```

**"승인 대기인데 제안이 없다"는 상태를 만들 수 없다.**

## 근거 대조가 못 잡는 것

`rationale_evidence_ids`가 가리키는 evidence가 **실재하는지**는 확인한다. **그 값이 옳은지**는 확인하지 않는다.

```
Context에 order.total_cents = 30000 이 있다
Team이 refund_amount_cents = 15000 을 제안하고 그 evidence를 가리킨다
→ 근거 대조 통과 ✅

그런데 실결제액이 25,000원이면 실제 환불은 12,500원이다  ❌
```

**Context 자체가 틀리면 통과한다.** 조치는 [D-001](../../../wiki/decisions/D-001-payment-ownership.md).

## ★ [2026-09-03] Action 어휘가 고정돼 있다 — 그런데 코드와 다르다

`[실측]` `program/plan/A-COP_예제Team모듈_확충설계.md` §3.3 에서 이관. **wiki 에 이 목록이 없었다.**

> **Action Gateway vocabulary 는 아래 9종으로 고정한다.**

```
order.create · payment.authorize · payment.capture
shipment.investigate · shipment.reroute · shipment.replace
return.request · refund.request · voc.escalate
```

### 왜 고정하나

> **기존 코드와 계약 테스트가 쓰는 `refund.request` 와 namespace·동사 형식을 유지해 **idempotency key 와 audit 의 action type 이 흔들리지 않게** 한다.

**`action_type` 은 [idempotency key](idempotency.md) 의 입력이다.** 이름이 바뀌면 **같은 요청이 다른 키를 만든다.**

### ★ 지금 코드와 대조했다

`[실측]` 2026-09-03. `app/` 전체에서 `action_type=` 을 세었다.

| 설계 9종 | 구현 |
|---|---|
| `return.request` | **있다** |
| `voc.escalate` | **있다** |
| `order.create` | capability 로만 있고 `action_type` 아님 |
| `payment.authorize`·`payment.capture` | **없다** |
| `shipment.investigate`·`reroute`·`replace` | **없다** |
| **`refund.request`** | **없다 — 대신 `refund.calculate` 를 쓴다** |

```python
# app/modules/customer_ops/return_refund.py:380
action_type = "refund.calculate"
```

**마지막 줄이 문제다.** 설계가 **"`refund.request` 와 형식을 유지하라"**고 못박은 바로 그 자리에서 다른 이름을 쓴다.

`[미확보]` **의도적으로 바꾼 것인지 모른다.** `calculate` 와 `request` 는 다른 일이다 — 계산은 읽기고 요청은 쓰기다. **그렇다면 이름이 맞고 설계가 낡은 것일 수 있다.**

**어느 쪽이든 계약 문서와 코드가 지금 다르다.**

### 설계에만 있고 코드에 없는 것

`[실측]` `action_type` 으로 실제 쓰이는 것은 여섯이다.

```
action.approve · case.create · mcp.open_support_case
refund.calculate · return.request · voc.escalate
```

**앞 셋은 설계 어휘에 없다.** 시스템 내부 동작이라 성격이 다르다.

## risk_level 규칙

`[실측]` 설계가 Team 별로 정해 뒀다. **wiki 에 없었다.**

| 언제 | risk_level |
|---|---|
| 금액·수량·배송지·결제수단이 포함되거나 **주문 상태를 바꾸는** 제안 | **`high`** + `approval_required=True` |
| 주소·수취인·배송 상태 변경 | **`medium` 이상** |

`[실측]` **`return_refund` 의 실제 값은 `medium` 이다.** 설계는 환불을 `high` 로 봤다. → [../teams/return-refund.md](../teams/return-refund.md)

## 관계

- [../teams/team-contract/index.md](../teams/team-contract/index.md) — 전체 계약
- [../teams/team-boundary.md](../teams/team-boundary.md) — 왜 제안만 하는가
- [evidence-check.md](evidence-check.md) — 근거 대조
- [approval.md](approval.md) — 승인 판정
- [idempotency.md](idempotency.md) — 중복 방지
