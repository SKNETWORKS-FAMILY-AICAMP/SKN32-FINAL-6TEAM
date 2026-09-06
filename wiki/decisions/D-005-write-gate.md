---
type: decision
title: 쓰기 권한을 여는 전제 조건
description: 착한 모델을 고르는 게 아니라 검사에 걸리는 모델을 만든다. 방어 7층과 필드별 대조
status: draft
tags: [security, architecture, evaluation]
owners: [human:미배정]
---

# D-005 쓰기 권한을 여는 전제 조건

`[실측]` v8 §9-E에서 이관.

## 맥락

Team이 `ActionProposal`을 반환하면 언젠가는 실행해야 한다. **그 전에 무엇을 확인할 것인가.**

3차 프로젝트에서 정한 원칙이 있었다 — **프롬프트를 방어선으로 삼지 않고 코드로 근거를 대조한다.** 그때 대상은 "답변"이었다.

## 결정

> **착한 모델을 고르는 게 아니라 검사에 걸리는 모델을 만든다.**
>
> **프롬프트를 무시하는 모델도 실행 전 검사를 통과하지 못해야 한다.**

3차의 원칙을 계승하되 대상을 **답변 → 행동(`ActionProposal`)**으로 바꾼다.

## 방어 7층

| 층 | 방법 | 강제력 |
|---|---|---|
| 입력 | **근거 0건이면 Action 제안 금지** | 강제 |
| 입력 | 프롬프트 인젝션을 **데이터로 취급하고 지시로 승격하지 않음** | 강제 |
| **지시** | **프롬프트에 근거·승인·기권 규칙 명시** | **약함** |
| 출력 | 구조화 스키마와 enum·필수 필드 강제. parse 실패 시 폐기·감사 | 강제 |
| 출력 | **대상·금액·수량·근거를 Context/DB와 대조** | 강제 |
| 실행 직전 | 최신 금액·수량·대상·scope·approval **재검증** | 강제 |
| 감사 | 제안·판정·거부·실행·원격 결과 append-only | 강제 |

**세 번째 층이 "약함"이라고 적혀 있는 게 이 표의 핵심이다.**

프롬프트는 방어가 아니다. 넣되 **그것만 믿지 않는다.**

## ★ 필드별 대조 규칙

| proposal 필드 | 대조 대상 | 불일치 시 |
|---|---|---|
| `order_id` | tenant/customer 범위의 실제 order row와 Case 연결 | **실행 전 거부** |
| `payment_id` | 실제 payment row, 해당 order의 결제 관계 | 실행 전 거부 |
| `subscription_id` | 실제 subscription row와 customer 소유권 | 실행 전 거부 |
| **`amount`** | 최신 **실제 결제액**·환불 가능 잔액·통화 | 실행 전 거부 |
| `quantity` | 주문 line item의 구매·취소 가능 수량 | 실행 전 거부 |
| `action_type` | Registry scope와 approval matrix | 거부 또는 승인 대기 |
| `evidence_ids` | ContextPack의 실제 evidence id와 **source digest** | 실행 전 거부 |
| `idempotency_key` | 기존 key와 payload hash | 중복 실행 금지, 상태 조회 |

`[실측]` 원문의 예가 명확하다.

> LLM이 "5만원 환불"이라고 해도 **실제 결제액이 3만원이면 버린다.**

**`amount` 행이 "최신 실제 결제액"이라고 적혀 있다.** 이게 [D-001](D-001-payment-ownership.md)의 환불 계산 결함과 직결된다 — 지금 `orders.total_cents`가 정가인지 실결제액인지 구분이 없다.

## 두 번 검증한다

```
① 승인 전   제안 검증
② 실행 직전  재검증 (최신 DB 재조회)
```

**프롬프트로 "실제 금액만 쓰라"고 말하는 것은 방어가 아니다.** Controller가 최신 DB/Context를 다시 읽고 필드별 대조 함수를 실행해야 한다.

### 자동 실행을 막는 네 조건

```
ContextPack.degraded = true
parse 실패
근거 식별자 불일치
현재 상태 변경
```

## 거부하면 조용히 넘기지 않는다

**폐기하고 `escalated`로 보낸다.** 감사 로그에 남기는 것.

```
action_id · case/run/task · 실패한 필드
기대값·실제값의 안전한 hash · actor · 시각
```

**다음 Action은 사람 승인 또는 추가 Context 이후에만** 새 proposal로 생성한다.

## 3차 지표를 옮긴 대응

| 3차 프로젝트 | A-COP |
|---|---|
| 인용 정합률 | **근거 정합률** |
| `verdict="unknown"` | `next_action="escalate"` |
| `parse_status != ok` 는 판정에서 제외 | `ContextPack.degraded=true` 는 **자동 실행 금지** |

**같은 구조를 답변에서 행동으로 옮긴 것이다.**

## 결과

| 바뀐 것 | |
|---|---|
| `app/core/verification.py` | 순수 판정 함수 |
| `proposal_guard` | 실행 직전 DB 재조회 |
| 불변식 | `INV-CS-VER-001`~`007` |
| DoD | 24·25 |

## 못 하게 되는 것

- 근거 없이 빠르게 처리할 수 없다. 근거 0건이면 제안 자체가 안 나온다
- 대조 비용이 매 실행마다 든다 (DB 재조회 2회)

## 관계

- [`cs/actions/evidence-check.md`](../../final_project_cs/wiki/actions/evidence-check.md) — 구현
- [`sample/wiki/runtime/`](../../final_project_sample/wiki/runtime/index.md) — `core/verification.py`. **도메인 선언을 주입받아** 대조한다
- [D-001](D-001-payment-ownership.md) — `amount` 대조의 기준값 문제
- [../evaluation/metrics.md](../evaluation/metrics.md) — 근거 지표
- [../delivery/dod.md](../delivery/dod.md) — DoD-24·25
