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

### ★ [2026-09-05] 같은 브라우저 재검증에서 결함이 하나 더 나왔다 — 화면표시용 필드가 재검증에 막혔다

`[실측]` [DoD-18 evidence](../../docs/evidence/DoD-18_UI_시나리오_종단표시.md). 승인 버튼을 실제로 눌렀더니 `HTTP 409 verification_failed` — 사유가 `"evidence: 선언되지 않은 필드다"`였다.

seed 스크립트가 화면 표시·버튼 활성화용으로 `arguments_json.evidence`를 채워 뒀는데, [승인 전 재검증](#승인-전-재검증)이 `verification_policy.py::CUSTOMER_OPS_POLICY.ignored`에 없는 최상위 키를 전부 거부하는 방식이라 이 표시용 필드까지 막았다. `ignored`에 `"evidence"`를 등록해 고쳤다.

**이 재검증 게이트가 같은 이유로 막힌 게 이번이 처음이 아니다.** [evidence-check.md](evidence-check.md)의 `calculation_basis` 결함(2026-09-03, 정상 환불 제안을 전부 막음)과 **완전히 같은 형태다** — 필드를 새로 추가할 때 `ignored`(또는 대조 어휘)에 등록하는 걸 놓치면 화이트리스트가 정상 동작을 막는다. **필드 하나를 늘릴 때마다 반복될 수 있는 종류의 결함이라는 뜻이다.**

### ★ 같은 검증에서 "UI 버그인 줄 알았던" 것이 실은 옳은 동작이었다

같은 세션에서 승인 버튼이 `disabled`인 걸 보고 처음엔 UI 결함으로 의심했다. 원인은 `app/presentation/ui/routes.py:191`의 `disabled = " disabled" if not evidence else ""` — **근거 없는 제안은 승인할 수 없다는 가드레일이 옳게 동작한 것**이었고, seed 스크립트가 evidence를 안 채운 게 잘못이었다.

**고치기 전에 어느 쪽이 잘못인지부터 확인해야 한다.** 가드레일을 의심 없이 풀었다면 근거 없는 승인을 열어 주는 방향으로 결함을 만들 뻔했다.

### ★ 승인 실패가 조용히 삼켜지고 있었다

같은 재검증에서 `approve()`의 두 분기가 성공·실패 모두 똑같이 `303 → /ui/approvals`를 반환하고 있었다.

**승인은 되돌릴 수 없는 행위인데, 실패해도 운영자는 "눌렀으니 됐겠지"로 넘어갈 뻔했다** — [CLAUDE.md §3](../../CLAUDE.md) "조용한 스킵을 만들지 않는다"를 UI 레이어에서 어긴 사례. 실패 사유를 화면에 띄우도록 고치고 `tests/integration/api/test_ui_approval_failure_is_visible.py`로 고정했다.

**HTTP 200(또는 303)만 봤다면 셋 다 못 찾았을 결함이다.** 최초 판정에서 화면 4개가 200을 내는 것만 확인하고도 화면이 실제로는 비어 있었던 것과 같은 종류의 누락이다.

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
