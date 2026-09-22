---
type: concept
title: 승인 경계
description: 무엇이 사람 승인 대상인가. 승인은 버그가 아니라 제품의 일부다
status: draft
tags: [security, architecture]
owners: [human:미배정]
domain: neutral
domain_note: 승인 경계 규칙은 도메인 무관이다. 「승인 없이 적용」·「승인 뒤 실행」 절이 지금 조립의 예(여행 일정·예약 적용기)를 한 줄씩 든다
---

# 승인 경계

> `[실측 2026-09-01]` **`app/core/case_runtime/`·`access_action/` 은 `__init__.py` 만 남은 빈 패키지다.**
> 2026-08-13 에 중첩 구조로 갔다가 **평면 구조로 되돌아왔다.** 정본은 `app/core/*.py` 다.
> 구조가 또 바뀔 수 있으므로 **작업 전에 실제 경로를 확인한다.**

`app/core/`

## 승인은 실패가 아니다

`[실측 2026-09-10]` 골든셋 기대 라벨 중 **`wait_for_approval` 이 15/72 = 20.8%** 다(`eval/datasets/golden.jsonl` 의 `expected_next_action`). ★**이건 정답 라벨의 분포이지 실제로 사람에게 넘어간 비율이 아니다** — 운영에서 잰 인계율은 `[미확보]`. 그리고 **그 72건은 쇼핑몰 시나리오**다 — 여행 골든셋은 0건이라 여행에서 몇 %가 승인으로 가는지는 아직 모른다. `[정정]` 이 줄은 분모 없이 「21%가 사람에게 간다」로 적혀 있었다.

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

## 승인 없이 적용되는 제안 `[결정 2026-09-17]`

v11 §4-C — **업체 예약은 승인 없이 실행하지 않는다. 먼저 고치고 알리는 것(Pre-CS)은 우리 DB 안의 일정 버전에만** 적용한다. 그 자리를 코어가 도메인을 모르고 여는 규칙은 이렇다.

| 조건 | 모두 참이어야 적용한다 |
|---|---|
| Team 결과 | `next_action=respond` 이고 제안의 `approval_required=false` |
| 적용기 | 조립이 그 `action_type` 의 **적용기**를 주입했고, 적용기가 `auto_apply=True` 를 선언했다 |
| 위험도 | 제안의 `risk_level=low` |
| 사실 대조 | 도메인 대조 선언(`VerificationPolicy`)을 통과한다 — 승인 제안과 **같은 검사** |
| Context | `degraded=false` |

- **하나라도 거짓이면 적용하지 않고 `escalated`** 로 보낸다(`guardrail`: `action_handler_missing`·`action_requires_approval`·`action_proposal_verification_failed`·`degraded_context_blocks_action`). 제안을 조용히 버리지 않는다 — 전에는 `respond` 결과의 제안이 저장도 실행도 안 되고 사라졌다(`controller.py:353-354`, 2026-09-17 실측).
- **적용 · `action_requests` 기록(`status=succeeded`) · Case 완료 전이 · 통지(outbox)는 한 트랜잭션**이다. 적용기가 「대상이 그 사이 바뀌었다」(`ActionConflict`)를 내면 그 부분만 되돌리고 `escalated`(`action_target_changed`) — 재계산 없이 다시 밀어 넣지 않는다.
- 멱등 키의 대상은 **적용기가 인자에서 꺼낸 대상 id**다(v11 §4-E). 같은 키가 이미 `succeeded` 면 다시 적용하지 않는다.
- ~~승인이 필요한 제안을 승인 뒤 실행하는 코드는 여전히 없다~~ — `[2026-09-18]` 아래 절로 채웠다.

## 승인 뒤 실행 `[2026-09-18]`

전에는 승인하면 Case 가 `resuming` → **Team 을 다시 불렀을 뿐** 아무것도 실행되지 않았다(Team 은 side effect 를 안 한다). 이제 **코어가 실행한다.**

| 단계 | 무엇 |
|---|---|
| 승인 대기로 갈 때 | `state_json.wait_reason = "human_approval"` 을 적는다. 전에는 안 적어 재개가 기본값 `customer_input` 으로 읽혔다 |
| 재개할 때 | 승인됐고(`action_approvals.decision=approved`) 아직 `pending_approval` 인 제안을 모은다 |
| 적용기가 **전부** 있으면 | 한 savepoint 안에서 적용기를 부르고 `action_requests.status=succeeded`·`provider_ref` 를 적은 뒤 `completed`(→ `resolved`). 적용기가 준 outbox 는 같은 트랜잭션 |
| 하나라도 적용기가 없으면 | 예전처럼 Team 을 다시 부른다 — 적용기가 없는 도메인의 승인 흐름은 안 바뀐다 |
| 적용기가 거부·충돌 | 전부 되돌리고 그 제안 `failed`, Case `escalated`(`action_rejected`·`action_target_changed`) |
| 시간 초과·연결 오류 | **성공으로 추정하지 않는다** — `unknown` 으로 남기고 `escalated`(`action_provider_unknown`), 자동 재실행 없음 |

- 적용기는 `auto_apply=False` 로 선언한다 — 승인 없이 오면 위 절의 규칙이 `action_requires_approval` 로 막는다.
- 승인 직전 재검증은 승인 API 가 이미 한다(아래 「승인 전 재검증」). 적용기는 적용 순간 대상을 **한 번 더** 잠가 확인한다.
- 여행: `booking.cancel` 은 **시연용 Mock 공급자**(`supplier_bookings`)와 우리 예약을 함께 `cancelled` 로, `booking.change` 는 바꿀 내용이 인자에 없어 **지어내지 않고 인계**한다(예약 `change_requested` + 바깥함 `booking.handoff`). `app/modules/travel_ops/booking_actions.py`.
- `[2026-09-22]` 그 인계 메시지에 **변경 링크**(`change_url`)가 실린다 — 고객이 바뀔 항목·대안·차액을 보고 **업체 쪽에서 직접** 진행한다(v11 §4-C · DoD-16·17). ★**링크를 만들고 여는 경로에는 승인이 없다** — 아무것도 쓰지 않기 때문이다. 승인이 필요한 것은 우리 예약을 `change_requested` 로 옮기는 기록 쪽이다. → [../teams/booking-handoff.md](../teams/booking-handoff.md#변경-링크-2026-09-22--이-절도-명세였다가-사실이-됐다)
- `[2026-09-22]` ★**승인이 나도 실제 공급자 원장은 안 바꾼다.** `booking.cancel` 은 `supplier_bookings.tier == 'simulated'` 일 때만 원장을 건드리고, 그 밖(기본값 `real`)이면 `ActionRejected` → 전부 되돌리고 `action_rejected` 로 사람에게 간다. **승인은 "이 변경을 해도 된다" 이지 "실제 업체에 직접 질러도 된다" 가 아니다**(v11 §4-C · DoD-14·15). → [../teams/booking-handoff.md](../teams/booking-handoff.md#2026-09-22-게이트가-생겼다--이-절이-명세였다가-사실이-됐다)
- `[2026-09-22]` ★**문이 하나 더 있다 — 위임 범위.** 등급 게이트를 지나도 **금액·대상 종류·횟수·되돌림 조건**을 벗어나면 원장을 건드리지 않고 `action_rejected` 로 사람에게 간다(v11 §12 DoD-18·19). 등급이 「누구의 원장인가」라면 위임은 「얼마까지 맡겼나」다. 판정은 **적용 순간에** 하므로 승인과 적용 사이에 위임이 철회되면 그 건은 열리지 않는다. → [../teams/booking-handoff.md](../teams/booking-handoff.md#위임-범위--1번에서만-쓴다)
- `[2026-09-22]` **적용은 장부에 넷을 적는다** — 무엇을(`action_type`·대상 id)·왜(`reason`)·얼마에(`amount_cents` + **그 금액을 어디서 읽었는지** `amount_source`)·되돌림 기한(`revert_deadline`). 마이그레이션 019 가 `action_requests` 에 만든 칸이고, **값은 적용기가 채우고 코어는 뜻을 모른다**(`AppliedAction.ledger()`). ★**모르는 금액은 비운다 — NULL 은 0 이 아니라 「확인되지 않았다」**다(인계 `booking.change` 는 차액을 모른다). DB CHECK 가 금액과 출처를 같이 채우거나 같이 비우게 한다.
- `[2026-09-20]` **끝났거나 기다리는 중인 Case 에는 Team 을 부르지 않는다**(`RUNNABLE_STATUSES`). 전에는 되잡기 작업이 같은 Case 를 또 집으면 Team 을 한 번 더 돌린 뒤 결과를 쓸 때 상태기계가 막았다 — 결과는 같지만 모델·도구를 한 번 더 쓰고 사유가 「전이 오류」로 보였다. 기다림을 푸는 것은 승인 API 와 `resume()` 이다.
- 시험: `tests/integration/controller/test_travel_approval_proposal_reaches_waiting.py`(라우팅 → 승인 대기 → 승인 → 실행 · 잠긴 예약 거부 · 적용기 없는 조립은 예전 흐름 · `[2026-09-22]` 공급자 등급별 실행/거부 3건) · `tests/architecture/test_supplier_tier_gate.py`(등급 게이트, 6건) · `[2026-09-22]` `tests/integration/controller/test_delegation_scope.py`(위임 범위·철회·장부·되돌림, 13건).

### 위임을 누가 주고 거두나 `[2026-09-22]`

`[실측]` **운영자다.** 자리는 REST `/v1/delegations/*` 와 운영 화면 `/ui/delegations` 다
(구현 [`app/modules/travel_ops/delegation_api.py`](../../app/modules/travel_ops/delegation_api.py) ·
화면 `app/presentation/ui/routes.py`). **전에는 자리가 없었다** — 판정(`delegation.py`)과
`delegations` 표(019)는 있는데 주고 거두는 경로가 없어 사람이 손으로 SQL 을 쳐야 했다.
「위임은 언제든 철회할 수 있다」가 그동안 말뿐이었다는 뜻이다.

| | |
|---|---|
| 권한 | `delegation:read`(보기) · `delegation:write`(주기·거두기). ★**`action:approve` 로는 못 한다** |
| ★왜 승인 권한과 나눴나 | 승인은 **제안 한 건**에 "이 변경을 해도 된다" 이고, 위임은 **서 있는 권한**이다 — 한 번 주면 거둘 때까지 그 고객의 모든 자동 실행이 한계 안에서 열린다. 영향 범위가 다르면 scope 를 나누는 것이 이 저장소의 방식이다(`composer:admin`·`ops:reload` 가 같은 기준으로 갈라졌다) |
| 무엇을 받나 | **누가**(`actor_id`)와 **왜**(`note`). 둘 다 필수이고 공백만 보내면 `422` — 근거 없이 위임 상태를 바꾸지 않는다 |
| ★맡기기 전에 보여 주는 것 | 화면이 **확인 단계**를 둔다 — 열리는 한계 · 이 고객에게 이미 나간 금액 · 남은 여유 · 지금까지 주고 거둔 기록. 그 화면은 **아무것도 바꾸지 않는다**. 거두기에는 확인 단계를 두지 않는다(막는 방향이고, 한 번 더 묻는 사이에 자동 실행이 나갈 수 있다) |
| ★거둘 것이 없으면 | `409 no_live_delegation` + 화면에 사유. **「거뒀다」고 답하지 않는다** — 200 으로 넘기면 운영자가 "눌렀으니 됐겠지" 로 간다(아래 「승인 실패가 조용히 삼켜지고 있었다」와 같은 형태다) |
| ★이력은 덮이지 않는다 | 주기·거두기가 `delegation_events`(마이그레이션 [021](../../app/infrastructure/db/migrations/021_delegation_audit_trail.sql))에 **덧붙는다**. `delegations` 한 행은 다시 주기가 `revoked_at`·`revoked_by` 를 NULL 로 덮으므로, 021 이 없으면 **「누가 언제 거뒀나」가 사라진다** — 019 자신이 지키라고 적어 둔 것이 다시 주는 순간 깨지고 있었다 |
| 한계 값은 화면에서 못 바꾼다 | `config/guardrails.yaml` `travel.delegation` 이 정본이다(RULE.md §3.1). 화면은 읽어서 보일 뿐이다 |
| 거둔 뒤 | 판정은 **적용 순간**에 하므로 승인 뒤·재개 전에 거둬도 그 건은 열리지 않는다. 이미 나간 건은 **되돌림 경로**로만 무른다(아래 절) |

★**이 화면에는 로그인이 없다** — `/ui/*` 전체가 그렇고 승인 화면도 같다(이 앱은 인증 없이
열린다). 위임을 주는 버튼이 그 위에 올라갔으므로 **승인 화면과 같은 크기의 구멍**이다.
→ [../records/reports/2026-09-22_1720_위임_주고거두는_화면과_API_리포트.md](../records/reports/2026-09-22_1720_위임_주고거두는_화면과_API_리포트.md) §미해결

시험: [`tests/integration/api/test_delegation_api.py`](../../tests/integration/api/test_delegation_api.py)(12 — 권한·주기·거두기 뒤 게이트가 실제로 닫히나·이력) ·
[`tests/integration/api/test_ui_delegation_screen.py`](../../tests/integration/api/test_ui_delegation_screen.py)(8 — 열리나·무엇이 열리는지 먼저 보이나·실패가 보이나).
계약 → [../external/rest-endpoints.md](../external/rest-endpoints.md#위임--v1delegations-2026-09-22)

### 되돌림도 승인 뒤 실행이다 `[2026-09-22]`

자동 실행을 무르는 것도 같은 경로를 탄다 — issue_code `booking_revert_request` → capability `booking.prepare_revert` → 제안 `booking.revert` → 승인 → 적용기 `BookingRevert`(v11 §12 DoD-21).

| | |
|---|---|
| 무엇으로 되돌리나 | 장부의 `prior_state_json`. ★**없으면 되돌리지 않고 사람에게** — `confirmed` 를 지어내지 않는다(취소 전이 `requested`·`changed` 였을 수도 있다) |
| 언제까지 | 장부의 `revert_deadline`. **그 건에 적힌 기한**을 본다 — 지금 설정으로 다시 계산하지 않는다(설정을 바꿔 지난 건의 기한을 늘리거나 줄이면 장부가 거짓이 된다) |
| 등급 게이트 | **선다.** 되돌림도 공급자 원장을 바꾼다 |
| 위임 범위 게이트 | **세우지 않는다.** 되돌림은 위임을 쓰는 것이 아니라 위임으로 한 일을 무르는 것이다 — 철회로 되돌림까지 막으면 이미 나간 변경을 원상복구할 길이 사라진다 |
| 실패하면 | 되돌림 요청의 `action_requests` 행이 `failed`(코어가 savepoint 를 되돌린 **뒤** 적는다 — 실패 기록이 롤백에 안 휩쓸린다) + Case `escalated`. 사유는 `case_events` 에 append-only. **조용히 삼키지 않는다** |

근거 → [../records/evidence/DoD-v11-18-21_위임범위와_되돌림.md](../records/evidence/DoD-v11-18-21_위임범위와_되돌림.md)

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

`[실측]` [DoD-18 evidence](../records/evidence/DoD-18_UI_시나리오_종단표시.md). 승인 버튼을 실제로 눌렀더니 `HTTP 409 verification_failed` — 사유가 `"evidence: 선언되지 않은 필드다"`였다.

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

승인 비율(쇼핑몰 골든셋 기대 라벨 20.8%)은 비용이지만 **축 2(오류 비용)를 사는 대가**다.

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
