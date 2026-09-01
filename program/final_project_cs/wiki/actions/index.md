---
type: guide
title: Actions
description: 바깥 세계를 실제로 바꾸는 유일한 경로. 제안·대조·승인·실행·발행이 여기서 갈린다
status: draft
---

# Actions

`app/core/access_action/`

**A-COP에서 side effect가 일어나는 유일한 곳이다.** Team은 여기에 제안만 하고 실행은 Core가 한다.

## 왜 분리했는가

Team이 직접 실행하면 세 가지가 무너진다.

1. **승인 경계를 우회할 수 있다**
2. **같은 요청이 두 번 실행될 수 있다**
3. **감사 기록이 남지 않는다**

## 흐름

```text
Team
 └→ ActionProposal              action-proposal.md
      ↓
    근거 대조                    evidence-check.md   ← 걸리면 escalate
      ↓
    위험도 판정
      ├→ 저위험: 자동 실행
      └→ 고위험: 사람 승인        approval.md
             ↓
        Action 실행              tool-gateway.md
             ↓ (동일 키 = 1회)     idempotency.md
        Outbox 발행              outbox.md
```

## 각 문서

| 문서 | 답하는 질문 | 코드 |
|---|---|---|
| [action-proposal.md](action-proposal.md) | Team이 무엇을 어떤 모양으로 반환하는가 | `app/core/contracts.py` |
| [evidence-check.md](evidence-check.md) | 근거 없는 주장을 어떻게 걸러내는가 | `app/core/verification.py` |
| [approval.md](approval.md) | 무엇이 사람 승인 대상인가 | `access_action/approval/` |
| [tool-gateway.md](tool-gateway.md) | 어떤 도구를 누가 쓸 수 있는가 | `access_action/tools/`, `access_action/gateway/` |
| [idempotency.md](idempotency.md) | 같은 요청이 여러 번 와도 한 번만 | `app/core/idempotency.py` |
| [outbox.md](outbox.md) | 외부 발행을 어떻게 보장하는가 | `app/infrastructure/messaging/` |

## 코드 구조

```text
app/core/access_action/
├─ approval/      승인 경계
├─ audit/         감사 기록
├─ auth/          인증
├─ gateway/       진입점
├─ idempotency/   중복 실행 방지
├─ interop/       외부 연동
└─ tools/         도구 실행
```

## 이 영역의 불변식

전체는 [../quality/invariants.md](../quality/invariants.md).

| ID | 불변식 | 판정 |
|---|---|---|
| `INV-CS-ACT-001` | 동일 dedupe key는 side effect가 1회다 | automated |
| `INV-CS-ACT-002` | 동시 claim도 side effect가 1회다 | automated |
| `INV-CS-ACT-003` | timeout은 unknown이며 자동 재시도하지 않는다 | automated |

**`INV-CS-ACT-003`이 중요하다.** timeout을 실패로 보고 자동 재시도하면 이중 실행이 된다. **모르는 건 모르는 채로 둔다.**

## 근거 대조가 못 잡는 것

`evidence-check`는 **"모델이 주장한 값이 Context에 있는가"**를 본다.

**Context 자체가 틀리면 통과한다.** 환불 계산식이 그 사례다. → [../quality/invariants.md](../quality/invariants.md)의 `INV-CS-VER-002` 절

## 인접 영역

- [../teams/team-boundary.md](../teams/team-boundary.md) — Team이 하면 안 되는 것
- [../runtime/shared-state.md](../runtime/shared-state.md) — 실행 결과가 반영되는 곳
- [../external/index.md](../external/index.md) — 바깥으로 나가는 면

## 관련 결정

- [D-001 결제 소유 경계](../../../wiki/decisions/D-001-payment-ownership.md)
- [D-003 Message Broker](../../../wiki/decisions/D-003-message-broker.md)
