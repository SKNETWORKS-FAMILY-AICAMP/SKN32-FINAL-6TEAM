---
type: concept
title: 승인 경계
description: 무엇이 사람 승인 대상인가. 승인은 버그가 아니라 제품의 일부다
status: draft
tags: [security, architecture]
owners: [human:미배정]
---

# 승인 경계

> `[실측 2026-09-01]` **`app/core/case_runtime/`·`access_action/` 은 `__init__.py` 만 남은 빈 패키지다.**
> 2026-08-13 에 중첩 구조로 갔다가 **평면 구조로 되돌아왔다.** 정본은 `app/core/*.py` 다.
> 구조가 또 바뀔 수 있으므로 **작업 전에 실제 경로를 확인한다.**

`app/core/`

## 승인은 실패가 아니다

`[실측]` 골든셋에서 **21%가 `wait_for_approval`**로 사람에게 간다.

이걸 "자동화 실패율"로 읽으면 안 된다. **승인 경계가 일부러 보내는 것**이다.

[중앙 허브 포지셔닝](../../../wiki/product/positioning.md)의 human-on-the-loop이 여기서 구현된다. 고위험 Action만 사람이 승인하고 나머지는 자동 처리한다.

## 무엇이 승인 대상인가

`ActionProposal`에 두 필드가 있다.

```python
approval_required : bool
risk_level        : low | medium | high
```

**Team이 제안하지만 최종 판정은 Core가 한다.** Team이 `approval_required=False`로 줘도 Core 정책이 요구하면 승인으로 간다.

**Team이 승인을 우회할 수 없다는 게 핵심이다.**

## 승인자 권한

승인자는 `action:approve` scope를 가져야 한다.

`[실측]` scope 10개는 guardrail이 소유한다(`INV-CS-SEC-007`). 코드에 흩어져 있지 않다.

## 반려하면

**`resuming`으로 가지 않는다.** `INV-CS-RT-019`가 강제한다.

```
tests/contract/test_case_state_table.py::test_rejection_does_not_resume
```

반려는 "다시 해봐"가 아니라 "하지 마"다. 자동 재개하면 반려의 의미가 없다.

## 대기가 만료되면

**자동 resolve하지 않는다.** `escalated`로 간다. `INV-CS-RT-018`.

```
tests/contract/test_case_state_table.py::test_wait_expiry_escalates_not_auto_resolves
```

**만료를 완료로 처리하면 고객은 답을 못 받았는데 시스템은 해결됐다고 본다.** 이게 이 규칙이 있는 이유다.

## 승인 전 재검증

승인 대기 중에 데이터가 바뀔 수 있다. 그래서 **승인 직전에 다시 대조한다.**

```
tests/integration/api/test_recheck_before_execution.py
```

→ [evidence-check.md](evidence-check.md)

## 감사 기록

승인·반려는 전부 기록된다. `action_approvals` 테이블.

```sql
action_approvals (approval_id, action_id, approver_id, decision, decided_at)
```

`[실측]` **감사 기록이 대기 큐에 유령 항목으로 남는 결함**이 실제로 있었고 수정됐다. 브라우저로 승인 버튼을 여러 번 눌러 발견한 것이다.

```
tests/integration/api/test_approval_audit_row_excluded_from_queue.py
```

**테스트만으로는 안 잡혔다.** UI를 실제로 열어 봐야 나온 결함이다.

## 사업적 의미

승인 21%는 비용이지만 **축 2(오류 비용)를 사는 대가**다.

| 승인 비율 | 뜻 |
|---|---|
| 0% | 안전장치가 없다 |
| 너무 높음 | 자동화 이득이 사라진다 |

**균형점이 제품의 값이다.** `적절한 기권율`·`과잉 기권율`이 이걸 잰다. → [../../../wiki/evaluation/metrics.md](../../../wiki/evaluation/metrics.md)

## 불변식

| ID | 불변식 | 판정 |
|---|---|---|
| `INV-CS-RT-018` | 대기 만료는 자동 resolve하지 않고 escalate한다 | automated |
| `INV-CS-RT-019` | 반려된 승인은 resume하지 않는다 | automated |
| `INV-CS-SEC-007` | scope 10개는 guardrail이 소유한다 | automated |

## 관계

- [action-proposal.md](action-proposal.md) — `approval_required`·`risk_level`
- [evidence-check.md](evidence-check.md) — 승인 직전 재검증
- [../runtime/case-lifecycle.md](../runtime/case-lifecycle.md) — `waiting_approval` 상태
- [../../../wiki/product/personas.md](../../../wiki/product/personas.md) — 승인하는 사람
