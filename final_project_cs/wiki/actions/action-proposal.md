---
type: contract
title: ActionProposal
description: Team이 반환하는 제안. 실행이 아니다. 근거 ID가 대조의 입력이 된다
status: draft
tags: [contract, agent]
owners: [human:미배정]
domain: neutral
domain_note: ActionProposal 계약은 도메인 무관이다. Action 어휘는 도메인마다 갈린다
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

`[실측 2026-09-10 작업 트리]` **아래 그림의 「위험도 판정 → 저위험 자동 실행」 갈래는 설계였고 코드에 없다.** `risk_level` 은 계약 필드로만 있고(`app/core/contracts.py:214`) Controller 는 제안을 전부 `pending_approval` 로 적는다(`app/application/controller.py:376-377`). `app/` 에서 `auto_execute`·`low_risk` 를 찾았고 안 나왔다 — 다른 이름의 분기는 이 검색이 놓칠 수 있다. 자동 실행 분기는 v11 DoD-15 가 **`tier == 'simulated'` 에서만** 열리게 정했다. 멱등 키도 Team 이 준 값이 아니라 **Core 가 쓰기 경계에서 다시 계산**한다(`controller.py:372`).

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
Context에 booking.amount_cents = 300000 이 있다
Team이 refund_amount_cents = 150000 을 제안하고 그 evidence를 가리킨다
→ 근거 대조 통과 ✅

그런데 업체 위약금 규정이 50% 가 아니라 30% 면 실제 환급은 90,000원이다  ❌
```

**Context 자체가 틀리면 통과한다.** `[실측 2026-09-10]` 여행에서 이 위험이 더 크다 — **위약금율이 업체마다 다르고 규정 원문을 아직 표본으로만 갖는다**(v11 §0-3). 커머스 쪽 같은 사례는 [D-001](../../../wiki/decisions/D-001-payment-ownership.md).

## ★ [2026-09-03] Action 어휘가 고정돼 있다 — 그런데 코드와 다르다

`[실측]` `program/plan/A-COP_예제Team모듈_확충설계.md` §3.3 에서 이관. **wiki 에 이 목록이 없었다.**

> **Action Gateway vocabulary 는 아래 9종으로 고정한다.**

```
order.create · payment.authorize · payment.capture
shipment.investigate · shipment.reroute · shipment.replace
return.request · refund.request · voc.escalate
```

### ★ [2026-09-10] 도메인이 바뀌어 어휘가 통째로 갈렸다

`[실측 2026-09-10]` `app/modules/travel_ops/` 에서 직접 센 여행 어휘다. **위 커머스 9종은 코드에 없다.**

| 접두 | Action |
|---|---|
| `activity.*` | `check_feasible` · `check_cancelable` · `propose_change` · `change` |
| `booking.*` | `verify` · `prepare_change` · `prepare_cancel` · `change` · `cancel` |
| `dining.*` | `check_open` · `check_conditions` |
| `mobility.*` | `check_route` · `status` · `exception` |
| `lodging.*` · `flight.*` | `status` (등록만) |
| `read.*` | `place` · `route` · `transit` · `weather` · `booking` · `supplier` · `policy` |

★**접두가 곧 라우팅 축이다.** v11 §5-B — `case_type`(객체 종류)을 `issue_code` 의 접두에서 뽑고, 그게 Team 선택에 쓰인다. **「접두사 규칙이 편하다」가 아니라 계약이 됐다.**

★**`read.*` 와 나머지가 성질이 다르다.** `read.*` 는 Context Broker 가 부르는 조회이고, 나머지는 **제안의 종류**다. Team 은 `read.*` 를 직접 호출하지 않는다.

`[미확보]` **9종 고정이라는 규칙이 여행에서도 유효한지 안 정했다.** 지금 여행 어휘는 스물셋이다 — 고정 상한이 아니라 Team 이 늘면 같이 는다.

### 왜 고정하나

> **기존 코드와 계약 테스트가 쓰는 `refund.request` 와 namespace·동사 형식을 유지해 **idempotency key 와 audit 의 action type 이 흔들리지 않게** 한다.

★**고정한 이유는 도메인이 바뀌어도 유효하다.** 갈린 것은 낱말이고 **`namespace.verb` 형식과 "한 번 정하면 안 흔든다"는 규칙은 그대로다** — `action_type` 이 idempotency key 의 한 칸이기 때문이다(v11 §4-E).

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

`[실측]` **`return_refund` 의 실제 값은 `medium` 이다.** 설계는 환불을 `high` 로 봤다. → [../teams/return-refund.md](../records/legacy/teams/return-refund.md)

## 관계

- [../teams/team-contract/index.md](../teams/team-contract/index.md) — 전체 계약
- [../teams/team-boundary.md](../teams/team-boundary.md) — 왜 제안만 하는가
- [evidence-check.md](evidence-check.md) — 근거 대조
- [approval.md](approval.md) — 승인 판정
- [idempotency.md](idempotency.md) — 중복 방지
