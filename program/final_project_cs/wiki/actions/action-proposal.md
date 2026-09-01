---
type: contract
title: ActionProposal
description: Team이 반환하는 제안. 실행이 아니다. 근거 ID가 대조의 입력이 된다
status: draft
tags: [contract, agent]
owners: [human:미배정]
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

## 관계

- [../teams/team-contract.md](../teams/team-contract.md) — 전체 계약
- [../teams/team-boundary.md](../teams/team-boundary.md) — 왜 제안만 하는가
- [evidence-check.md](evidence-check.md) — 근거 대조
- [approval.md](approval.md) — 승인 판정
- [idempotency.md](idempotency.md) — 중복 방지
