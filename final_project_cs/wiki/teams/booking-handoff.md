---
type: plan
title: Booking Handoff Team
description: 승인이 필요한 업체 예약 건을 특정해 대안·차액을 정리해 넘긴다. 자동 실행은 Mock 공급자에만 열린다
status: draft
tags: [agent, customer-operations, security]
owners: [human:미배정]
domain: travel
---

# Booking Handoff Team

★**코드가 생겼다.** `[실측 2026-09-10 작업 트리]` `app/modules/travel_ops/booking_handoff.py` 가 있고 `config/project.yaml` 에 등록돼 있다. **`[실측 2026-09-10 git]` 둘 다 아직 커밋 전이다** — 되돌려지면 이 문장이 거짓이 된다. 이 문서는 한때 "아직 코드가 없다"고 적었다.

근거는 계획서 v11 §5·§4-C.

## 명세와 코드 — 2026-09-22 에 거의 다 닫혔다

`[실측]` 이 문서는 한때 아래를 **현재 동작처럼** 적고 있었고, 2026-09-10 에 세어 보니 대부분 코드에 없었다. 지금은 넷이 생겼다.

| 명세 | 그때(09-10) | 지금(09-22) |
|---|---|---|
| 승인 대기 제안 정리 | 있다 | 있다 |
| `tier == 'simulated'` 게이트 · `supplier_bookings.tier` | 없다 | **있다**(마이그레이션 017, 기본값 `real`) — 아래 「안전장치」 |
| 위임 범위 판정 | 없다 | **있다**(019) — 아래 「위임 범위」 |
| 되돌림 경로 | 없다 | **있다**(`booking.revert`) — 아래 「되돌림」 |
| 변경 링크 생성 | 없다 | **있다** — 아래 「변경 링크」 |
| 협약사 Mock **자동 실행** | 없다 | **승인 뒤에만** 있다(Mock 한정) |

★★**「자동 실행」이 두 가지를 가리켜 왔다** — ①승인을 건너뛰는 것: **여전히 없다**(예약 적용기는 전부 `auto_apply=False`) ②승인 뒤 **공급자 원장을 사람 손 없이 바꾸는 것**: 있다(Mock 한정). DoD-18~21 이 재는 것은 ②다.

★**게이트는 테스트와 함께 만들었다** — 먼저 만들고 나중에 막으면 그 사이에 새어도 아무도 모른다(DoD-14·15).

`[결정 2026-09-10]` 이 Team 몫인 DoD-14~21 은 **MVP 판정에서 뺀다**(MVP 는 Activity·Dining·Mobility 셋, 18항목). 다만 `[2026-09-22]` **넷 다 실행으로 판정했고 26항목 기준으로는 통과**다.

## MVP 에서 뺐다

`[결정 2026-09-10]` **MVP Team 은 Activity·Dining·Mobility 셋이고 이 Team 은 MVP 다음 단계다.** 09-08 의 「등급만 → MVP 필수」 승격을 뒤집었다. 그때 올린 이유는 지금도 기능 설명으로 유효하다 — *「감지해서 우리 일정을 고쳐도 업체 예약을 못 바꾸면 고객이 결국 직접 처리한다.」* **무엇을 어떻게 바꿔야 하는지 정리해 넘기는 것까지가 제품**이고, 이름이 Execution 이 아니라 **Handoff** 인 이유다.

## 기본 동작은 실행이 아니라 인계다

`[실측]` v11 §4-C. **업체 예약은 승인 없이 실행하지 않는다.** 승인 게이트(D-005)를 승계하되 적용 범위를 나눈다.

| 어디 | 규칙 |
|---|---|
| **우리 DB의 일정 버전** | Pre-CS — 먼저 조정하고 통지한다 |
| **업체 예약** | 승인 없이 실행하지 않는다 |

업체가 걸리면 두 경우뿐이다.

| # | 경우 | 처리 | 지금 |
|---|---|---|---|
| 1 | **협약사**, 위임 범위 안 | 사람을 멈추지 않고 실행하고 통지 | **시뮬레이션 범위** — Mock 공급자에서만 |
| 2 | **비협약사** 또는 위임 범위 밖 | 실행하지 않고 **변경 링크**로 넘긴다 | **실제 동작** |

★**1번은 "협약이 되면 이렇게 된다"를 보여주는 것이지 지금의 운영 규칙이 아니다.**

### 안전장치 — `tier == 'simulated'` 게이트

자동 실행 분기는 `supplier.tier == 'simulated'` 일 때만 열린다. 실제 공급자가 등록되면 그 건은 승인 경로로 간다. **아키텍처 테스트로 막는다**(v10 DoD-14·15).

★**시연 모드는 이 Team 안에 갇힌다.** 다른 Team은 이 분기를 모른다.

#### `[2026-09-22]` 게이트가 생겼다 — 이 절이 명세였다가 사실이 됐다

등급이 **데이터에** 있다 — `supplier_bookings.tier`(마이그레이션 [017](../../app/infrastructure/db/migrations/017_supplier_tier.sql)).
**기본값은 `real`** 이고 DB CHECK 가 값을 `('real','simulated')` 둘로 묶는다. 등급을 잊은 행은
전부 실제 공급자로 취급돼 자동 실행이 막힌다 — **잊음의 대가가 돈인 쪽으로 기울이지 않는다.**

| 등급 | 적용기가 하는 일 |
|---|---|
| `simulated` | 공급자 원장(`supplier_bookings`)과 우리 예약을 함께 바꾼다 |
| 그 밖(기본 `real`·`None`·오타) | 원장을 **한 글자도 안 건드리고** `ActionRejected` → 코어가 전부 되돌리고 `action_rejected` 로 사람에게 |

- 판정은 **`simulated` 가 아닌 것 전부를 막는** 쪽이다. 「`real` 이면 막는다」로 쓰면 등급을 못 읽은 행이 자동 실행 대상이 된다.
- 등급은 **적용 시점에** `FOR UPDATE` 로 읽는다 — 제안을 만든 뒤 등급이 바뀌었을 수 있다. 승인 **뒤**에 바뀌어도 막힌다.
- `booking.change` 는 원장을 어느 등급에서도 안 건드린다(인계) — 그래서 게이트가 없다.
- 시험: [`tests/architecture/test_supplier_tier_gate.py`](../../tests/architecture/test_supplier_tier_gate.py)(6) —
  AST 로 **원장을 바꾸는 SQL 전부**를 찾아 게이트가 그보다 앞에 불리는지 센다. ★검사기 자신도 시험한다.
  행동은 [`test_travel_approval_proposal_reaches_waiting.py`](../../tests/integration/controller/test_travel_approval_proposal_reaches_waiting.py) 의 3건.
  근거 → [evidence](../records/evidence/DoD-v11-14-15_공급자등급게이트.md) · [리포트](../records/reports/2026-09-22_0831_DoD-14-15_공급자등급게이트_리포트.md)

## 2번은 빈손으로 넘기지 않는다

`[실측]` v11 §4-C 의 통지 예시 — *「10/03 인천→후쿠오카 편이 결항됐습니다. 같은 날 15:20 편이 있고 차액은 +42,000원입니다. 그날 15시 액티비티는 17시로 옮겨 두었습니다. 항공권 변경은 아래 링크에서 진행해 주세요.」*

**우리 일정 버전은 이미 고쳐 두고 업체 건만 링크로 넘긴다.** 링크에 들어가는 것 — 바꿀 항목 · 대안 · 차액.

### 변경 링크 `[2026-09-22]` — 이 절도 명세였다가 사실이 됐다

`[실측 2026-09-22]` `GET /booking-change/{booking_id}?t=…` — 구현은 [`app/modules/travel_ops/change_link.py`](../../app/modules/travel_ops/change_link.py), 라우트는 `trip_api.py`. **모양은 계획서 링크를 본떴다** — 로그인 없음 · **예약별** HMAC 토큰 · 토큰을 저장하지 않고 비밀 키로 다시 계산 · 틀리면 `404`(있는지도 말하지 않는다).

★**이 경로는 승인이 필요 없다.** 아무것도 쓰지 않는다 — 읽기만 하고, **업체 예약을 바꾸는 것은 고객이 업체 쪽에서** 한다. 승인이 필요한 것은 우리 예약을 `change_requested` 로 옮기는 **기록** 쪽이고, 그 기록(`booking.change` 적용기)이 이 링크를 인계 메시지에 싣는다.

★**계획서 토큰과 접두가 다르다**(`plan:` vs `booking-change:`). 같은 비밀 키에서 나오므로 접두가 같으면 계획서 토큰으로 예약 화면이 열린다 — 시험이 그것을 본다.

세 값의 출처는 이렇다. **어디서 얻는지가 정해져 있고, 없으면 지어내지 않는다.**

| 값 | 어디서 | 없으면 |
|---|---|---|
| **바뀔 항목** | `bookings`(booking_no·kind·status·starts_at·party_size·amount_cents) + `places.name` + `supplier_bookings`(supplier·supplier_ref). 그 예약에 걸린 일정 항목의 제목·시각도 | 칸마다 「확인되지 않았습니다」 |
| **대안** | 그 예약에 걸린 **일정 항목의 `detail.alternates`** — 감시 루프가 재계획할 때 들고 둔 「다른 안」(`replan.alternate_record`). 1차 소스 `itinerary_items.booking_id`, 대체 소스 같은 장소(`bookings.place_id`) | **대안 0건**이라고 적는다. ★여기서 후보를 **새로 계산하지 않는다** — 고객이 계획서에서 본 것과 다른 안이 여기 뜨면 안 된다 |
| ★★**차액** | 양쪽 **1인 가격**(`places.attributes.price_krw`) 차 × 인원. 같은 소스끼리 뺀다 — 실제 결제액(`amount_cents`)과 카탈로그 가격을 섞어 빼면 무엇을 뺀 수인지 아무도 모른다. 결제액은 **따로** 「지금 결제된 금액」으로 보인다 | `difference_krw`=`null` + **어느 쪽을 몰라서인지**. 화면은 「확인되지 않았습니다」 — **0원으로도 추정으로도 채우지 않는다**(v11 결정 15 · 근거 없는 문장 금지) |

- 분모를 화면에 적는다 — `difference_basis` 「1인 가격 차 × 인원 N명」. 인원을 모르면 그것도 적는다.
- 업체가 청구하는 **변경 수수료는 차액에 없다**(우리가 모르는 값이다). 화면이 그렇게 말한다.
- 기록: 승인 뒤 `booking.change` 적용기가 `change_url`·`text` 를 바깥함(`booking.handoff`)에 싣는다. 업체 예약을 우리가 바꾸지 않으므로 **남는 것은 예약 상태와 이 메시지뿐**이고, 그것이 「무엇을 왜 넘겼나」의 기록이다.
- 시험: [`tests/e2e/test_booking_change_link.py`](../../tests/e2e/test_booking_change_link.py)(4) — 세 값이 보이는가 · 틀린 토큰은 404(계획서 토큰으로도 안 열린다) · **차액을 모를 때 지어내지 않는가** · 실제 공급자(`tier='real'`) 원장이 한 글자도 안 바뀌는가.
  근거 → [evidence](../records/evidence/DoD-v11-16-17_변경링크.md) · [리포트](../records/reports/2026-09-22_1150_DoD-16-17_업체예약_변경링크_리포트.md)

## 셋을 갖는다

### ① 검증 규칙

| 무엇 | 판정 |
|---|---|
| 승인이 필요한 건인가 | 업체 예약을 건드리는가. 우리 DB만 바뀌는가 |
| 위임 범위 안인가 | **시연 모드에서만.** 아래 표 |
| 위약금 | 지금 바꾸면 얼마인가 |

#### 위임 범위 — 1번에서만 쓴다

| 항목 | 어디에 | 지금 값 |
|---|---|---|
| **위임이 살아 있나** | **데이터** `delegations(tenant_id, customer_id, revoked_at)` | ★**행이 없으면 위임이 없다.** 철회는 지우는 것이 아니라 `revoked_at` 을 적는 것이다 |
| 금액 상한 | 설정 `travel.delegation` | 건당 `max_per_action_cents` 50,000원 · 누적 `max_total_cents` 150,000원 |
| 대상 종류 | 동 `kinds` | `activity`·`dining`. 항공·숙박은 제외(잠긴 예약) |
| 되돌림 조건 | 동 `free_cancellation_lead_hours` | 출발 **72시간** 전까지를 무료 취소 구간으로 본다 |
| 횟수 | 동 `max_changes_per_booking` | 같은 예약 **2회**까지 |
| 되돌림 기한 | 동 `revert_window_hours` | 실행 시점 + **24시간**, 단 무료 취소 구간 끝을 넘지 않는다(이른 쪽) |

**하나라도 벗어나면 2번으로 내려간다** — 원장을 한 글자도 안 건드리고 `action_rejected` 로 사람에게 간다. 위임은 언제든 철회할 수 있다. 자동 실행은 무엇을·왜·얼마에·되돌림 기한까지 기록한다.

#### `[2026-09-22]` 이 절도 명세였다가 사실이 됐다 — `[미확보]` N·M·K 가 닫혔다

★★**값은 측정에서 나오지 않았다. 「우리가 고른 값」이다.** 그래서 코드가 아니라 **설정**(`config/guardrails.yaml` `travel.delegation`)에 자리를 만들고 거기에 적었다 — 실제 업체 협약이 생기면 그 협약이 이 자리를 받는다. 값이 옳은지는 아직 아무도 모르고, **값이 통제하는지**는 시험이 안다(설정을 고치면 판정이 바뀐다).

★**한계를 나누는 기준.** 「살아 있나」만 **데이터**이고 나머지는 **설정**이다. 위임은 고객이 우리에게 주는 것이라 고객마다 다르게 거둬야 하고(설정으로 두면 한 고객의 철회가 전원에게 적용된다), 언제 누가 거뒀는지가 남아야 한다. 한계값은 우리 상품 정책이라 전원에게 같다.

| 판정 순서 | 벗어나면 사유 이름 | 왜 이 순서인가 |
|---|---|---|
| 1 위임 행이 있나 | `delegation_absent` | 맡기지도 않은 것에 상한을 대볼 필요가 없다 |
| 2 철회됐나 | `delegation_revoked` | 동 |
| 3 종류가 맞나 | `kind_not_delegated` | 금액을 읽기 전에 대상부터 |
| 4 금액을 아나 | `amount_unknown` | ★**모름을 0 으로 읽지 않는다.** 모르면 상한 안이라고 단정할 수 없다 |
| 5 건당 상한 | `over_per_action_cap` | |
| 6 누적 상한 | `over_total_cap` | 이 고객의 **성공한 자동 실행 금액 합** + 이번 건 |
| 7 횟수 | `over_change_count` | 같은 예약에 성공한 자동 실행 건수 |
| 8 무료 취소 구간 | `outside_free_cancellation_window` | ★**되돌릴 수 없는 것을 사람 손 없이 하지 않는다** |

- 판정은 **적용 순간**에, 위임 행을 `FOR UPDATE` 로 잠가 읽는다 — 승인 뒤에 철회돼도 막힌다. 적용이 한 트랜잭션이라 「반쯤 나간 자동 실행」이 없다.
- 한 Case 의 제안 둘 중 하나가 범위 밖이면 **첫째까지 되돌린다** — 위임 없는 상태에서 원장에 한 건이라도 남는 쪽이 더 나쁘다.
- 되돌린 건을 누적 합에서 **빼지 않는다.** 빼면 「취소 → 되돌림」을 반복해 상한을 무한히 쓸 수 있다.
- 판정 근거(무엇을 무엇과 비교했나)는 성공한 건의 `action_requests.delegation_json` 에, 거부된 건은 `case_events` 에 남는다.
- 구현: [`app/modules/travel_ops/delegation.py`](../../app/modules/travel_ops/delegation.py) · 마이그레이션 [019](../../app/infrastructure/db/migrations/019_delegation_and_execution_record.sql).
- 재는 것: `python -m scripts.measure_delegation_scope` — **실측 13건을 흘려 범위 밖 10건 중 자동 실행 0건**(분모는 범위 밖 시도 10건). 같이 본 것 — 범위 안인데 막힌 건수 0/3.
- 시험: [`tests/integration/controller/test_delegation_scope.py`](../../tests/integration/controller/test_delegation_scope.py)(13). 근거 → [evidence](../records/evidence/DoD-v11-18-21_위임범위와_되돌림.md) · [리포트](../records/reports/2026-09-22_1450_DoD-18-21_위임범위와_되돌림_리포트.md)
- ~~**아직 없는 것**: 위임을 주고 거두는 **화면·API**~~ → `[2026-09-22 해결]` **생겼다** — REST `/v1/delegations/*` 넷([`delegation_api.py`](../../app/modules/travel_ops/delegation_api.py))과 운영 화면 `/ui/delegations`. scope 는 `delegation:read`·`delegation:write` 로 **`action:approve` 와 나눴다**(승인은 제안 한 건, 위임은 거둘 때까지 서 있는 권한). 주고 거둔 **이력**은 마이그레이션 [021](../../app/infrastructure/db/migrations/021_delegation_audit_trail.sql) `delegation_events` 에 덧붙는다 — 019 만으로는 **다시 주기가 「누가 거뒀나」를 덮어 지웠다**. → [../actions/approval.md](../actions/approval.md#위임을-누가-주고-거두나-2026-09-22)
- **아직 없는 것**: 위임 범위를 **Trip 단위**로 좁히는 것 — `bookings` 에 `trip_id` 가 없어 고객 단위로 뒀고, 그쪽이 상한을 **더 빨리 채우는**(안전한) 방향이다.

### ② 감시 소스 · ③ 재계획 후보

| | 무엇 |
|---|---|
| 감시 소스 | 예약 확인(아직 유효한가·업체가 취소했는가) · Mock 공급자(시연 모드의 변경 성공·실패) |
| 재계획 후보 | **변경 링크 생성이 기본**이다. 시연 모드 한정으로 Mock 예약 변경을 제안한다 |

## 되돌림이 다른 Team과 다르다

`[실측]` v11 §4-C.

| 무엇 | 되돌림 |
|---|---|
| 우리 일정 버전 | **불변(append-only)**. 이전 버전을 복사해 새 버전을 만든다. 버전을 지우지 않는다 |
| **업체 예약** | **보상 거래가 필요하고 실패할 수 있다** |

시뮬레이션에서도 되돌림 시도를 상태로 남기고, **실패하면 사람에게 넘긴다.** 조용히 삼키지 않는다.

### `[2026-09-22]` 되돌림 경로가 생겼다 — 상태 이름의 `[미확보]` 가 닫혔다

issue_code `booking_revert_request` → capability `booking.prepare_revert` → 제안 `booking.revert` → **승인** → 적용기 `BookingRevert`(v11 §12 DoD-21).

**「보상 거래 실패 처리」의 상태 이름은 따로 만들지 않았다.** 되돌림 요청 자신이 `action_requests` 행이라 그 행의 `status` 가 곧 시도 상태다 — `pending_approval` → `succeeded` / `failed` / `unknown`. 새 어휘를 만들면 같은 것을 두 군데서 세게 된다.

| 되돌림이 막히는 자리 | 어떻게 되나 |
|---|---|
| 되돌림 기한 경과 | 되돌림 요청 행 `failed` · Case `escalated`(`action_rejected`) |
| 돌아갈 상태가 기록돼 있지 않다 | 같음. ★`confirmed` 를 **지어내지 않는다** — 취소 전이 `requested`·`changed` 였을 수도 있다 |
| 공급자 등급이 `simulated` 가 아니다 | 같음. 되돌림도 원장을 바꾸므로 등급 게이트가 선다 |
| 되돌릴 자동 실행이 없다 | 같음. 「성공」이라 답하지 않는다 |
| 예약이 그새 다른 상태 | `action_target_changed`. 재계산 없이 다시 밀지 않는다 |

- **실패 기록이 롤백에 휩쓸리지 않는다.** 코어가 savepoint 를 통째로 되돌린 **뒤** 그 행을 `failed` 로 적는다. 사유는 `case_events`(append-only)에 남는다.
- 무엇으로 되돌리나 — 원래 실행이 장부에 적어 둔 `prior_state_json`. 언제까지 — 그 건의 `revert_deadline`(지금 설정으로 다시 계산하지 않는다).
- ★**되돌림에는 위임 범위 게이트를 세우지 않았다.** 되돌림은 위임을 쓰는 것이 아니라 위임으로 한 일을 무르는 것이다 — 철회로 되돌림까지 막으면 철회한 순간 이미 나간 변경을 원상복구할 길이 사라진다. 돈이 나가는 방향이 아니라 되돌리는 방향이므로 연다.
- 실제 업체 API 의 보상 거래 실패(부분 성공·시간 초과)는 아직 재지 않았다 — 공급자 원장이 우리 DB 이기 때문이다(구현 단계 4).

## manifest — 실제 구현

`[실측 2026-09-10 작업 트리]` `app/modules/travel_ops/booking_handoff.py`. **한때 이 절은 「제안이다. 코드에 없다」였다.**

```python
capabilities          = ["booking.verify",           # 예약이 실재하고 우리가 아는 것과 같은가
                         "booking.prepare_change",   # 변경에 필요한 것을 정리한다
                         "booking.prepare_cancel",   # 취소에 필요한 것을 정리한다
                         "booking.prepare_revert"]   # `[2026-09-22]` 되돌림에 필요한 것을 정리한다
accepted_case_types   = ["booking"]                  # ★객체 종류다. 요청 종류가 아니다
required_context      = ["case_state", "policy", "db_facts", "history"]
allowed_tools         = ["read.booking", "read.policy", "read.supplier"]
knowledge_scope       = ["travel_cancellation", "travel_activity",       # [2026-09-22] 여행 scope 로 교체
                         "travel_dining"]                                  #   앞 값 넷은 전부 문서 0건이었다
max_steps             = 6
default_capability    = "booking.verify"
```

★★`[2026-09-22]` **이 Team 은 그때까지 모든 Case 가 사람에게 가고 있었다.** `policy` 를 필수로 선언해 뒀는데 위 `knowledge_scope` **넷 다 문서 0건**이라(DB 실측) 검색 0건 → `degraded=True` → `_guard` 가 곧바로 `escalated` 였다. 여행 코퍼스를 넣고 scope 를 바꿔 닫았다 — [../records/reports/debugs/2026-09-22_정책scope에_문서가_0건인_팀들.md](../records/reports/debugs/2026-09-22_정책scope에_문서가_0건인_팀들.md). 같은 결함이 Lodging·Flight 에도 있었고 그 둘은 `policy` 선언 자체를 뺐다(정책을 읽을 도구도 없는 팀이다).

`[2026-09-18]` **준비 capability 둘에 라우팅으로 닿는다.** 전에는 `select_capability` 가 없어 어떤 예약 요청이든 `booking.verify` 로만 불렸다. 이제 분류 결과로 고른다 — `booking_cancel_request` → `booking.prepare_cancel`, `booking_change_request` → `booking.prepare_change`, `[2026-09-22]` `booking_revert_request` → `booking.prepare_revert`, 그 밖은 기본(`verify`). 코어가 capability 선택에 `issue_code` 를 넘긴다. **승인 뒤 실행**도 생겼다 — [../actions/approval.md](../actions/approval.md) 「승인 뒤 실행」(취소는 Mock 공급자에 실행, 변경은 인계).

★**`accepted_case_types` 가 「객체 종류」다.** 이 문서는 한때 `itinerary_submitted`·`incident_reported` 같은 **요청 종류**를 적어 뒀다. **축이 틀렸다.** v11 §5-B — 라우팅은 두 축이고 Team 을 고르는 것은 `case_type`(객체 종류, `issue_code` 접두에서 뽑는다)이다. 요청 종류는 `intent` 쪽이다.

★**요청 종류 다섯만으로는 여섯 팀 어디에도 안 간다** — 2026-09-09 실행으로 확인됐고 그래서 v11 이 축을 둘로 갈랐다.

`[미확보]` `delegation_scope` 를 Context Broker가 싣는지, Team이 도구로 읽는지 안 정했다.

## `business_subject` — 도메인이 바뀌어도 안 바꾸는 칸

`[정정 2026-09-10]` Team의 3단 폴백 값은 최종 멱등 키에 쓰이지 않고 Core가 `business_subject=str(case["case_id"])`로 다시 계산한다. `booking_id` 유무와 무관하게 같은 Case·같은 종류의 제안이 서로 다른 객체를 바꾸면 충돌할 수 있으므로 결함의 수정 위치는 Core다. 근거: `app/application/controller.py:371-374`(2026-09-10 실측). Team은 대상 객체 id를 제안하고 서버는 §4-E의 작업 종류별 인자에서 대상을 꺼내 실재·소유를 확인한 뒤 최종 키에 쓰며, 특정하지 못하면 폴백하지 않고 거부해야 한다(v11 §4-E 미구현). 아래는 당시 Team 코드 관찰과 판단의 기록이다.

`[실측 2026-09-09]` `A-COP_여행Team모듈_구성안.md`. 도메인 객체 id 는 코어에 없다 — `customer_cases` 컬럼에도 `app/core/`·`app/application/` 코드에도 `order_id`·`booking_id` 가 **0회**다. 도메인 객체는 `idempotency_key(tenant_id, request_id, action_type, business_subject)` 의 `business_subject` **문자열 한 칸**으로 들어간다.

★**칸 이름을 `booking_id` 로 바꾸면 다음 도메인에서 또 바꿔야 한다.** 이름은 이미 중립이고 맞다. 정해야 하는 것은 규칙이다.

> **`business_subject` 에는 그 Action 이 바꾸는 대상 객체의 id 를 넣는다. 대상이 특정되지 않으면 실행하지 않고 escalate 한다.**

**`case_id` 폴백을 두지 않는다.** 폴백이 있으면 특정 실패가 조용히 넘어간다. 그리고 여행에서 실제로 터진다 — `request_id` 는 Case 당 하나라서, **한 Case 안에서 같은 종류의 작업을 두 객체에 하면 키가 같아진다.**

```
subject = case_id   →  같은 키    ← 둘째가 조용히 중복 처리되거나 막힌다
subject = 객체 id    →  다른 키
```

`[실측]` 쇼핑몰에서는 Case 하나가 대개 주문 하나라 잘 안 드러났다. 여행은 Trip 하나에 예약이 여럿이고 **"비가 온다" 는 사건 하나가 여러 예약을 동시에 바꾼다.**

★**이 Team 에서 가장 크게 걸린다.** 예약 변경은 예약 하나가 대상이고, 사건 하나가 예약 여럿을 건드리는 것이 이 Team 의 일상이다. `subject = case_id` 로 두면 **둘째 예약 변경이 조용히 합쳐진다.**

### 옛 기록 — 2026-09-09 의 「코드가 규칙을 안 지킨다」

`[실측 2026-09-09]` 여행 Team 공용 기반(`_base.py`)이 `booking_id → trip_id → case_id` 3단 폴백을 썼다.
`[정정 2026-09-10]` 그 값은 최종 키에 쓰이지 않는다 — 결함 자리는 Core 였다.
`[2026-09-18 해결]` Core 가 **적용기가 인자에서 꺼낸 대상 id** 로 키를 만든다. 적용기가 없는 제안은 아직 Case id 이고, `[2026-09-20]` 그때도 **조용히 합쳐지지 않는다**(`action_key_collision` 로 사람에게 간다).

### ★ [2026-09-10] 계획서가 이 규칙을 받았다 — v11 §4-E

`[결정 2026-09-10]` **`[미확보]` 가 닫혔다.** 어제까지 "규칙을 계획서 §6 에 넣는 일이 남았다"고 적혀 있었다. v11 이 **§4-E 를 신설해** 정했다.

> **실행 요청의 멱등 키에 들어가는 「대상」은 서버가 정한다** — 인자에서 꺼내 **실재하는지·이 여행의 것인지 확인한 뒤** 키에 넣는다.

| 작업 종류 접두 | 꺼낼 인자 | 무엇인가 |
|---|---|---|
| `booking.*` | `booking_id` | 예약 한 건 |

★**이 Team 만 `booking_id` 하나다.** 업체 예약을 바꾸는 것이 이 Team 의 일이므로 대상이 언제나 예약 한 건이다.

★**Team 이 준 값을 그대로 쓰지 않는다.** 코드 주석이 이미 그렇게 경계한다 — `controller.py:371` 의 *"The Team value is advisory. The server owns the final key at the write boundary."*

★**왜 Case 를 쪼개는 쪽을 택하지 않았나.** 다른 안은 "한 Case 에 같은 종류 작업은 하나"를 사양으로 못박는 것이었다. **비가 오면 액티비티·식당·이동이 한꺼번에 흔들린다** — Case 를 쪼개면 한 사건을 여러 Case 로 나눠 고객에게 따로 통지하게 되고, **DoD-8(거부하면 되돌린다)에서 어디까지 되돌릴지가 애매해진다.**

`[실측 2026-09-10]` **v11 §12 가 이것을 DoD-24 로 올렸다** — 「한 Case 에서 대상 객체가 다른 제안 둘이 각각 저장된다」. 문서 규칙이 아니라 검사 항목이 됐다.

`[미확보]` 위 규칙표를 코드에 둘지 `config/` 에 둘지는 안 정했다. **어휘는 설정으로 빼기로 했지만(v11 §5-B) 이건 계약에 더 가깝다.**

## 이 Team이 하지 않는 것

| 하지 않는다 | 왜 |
|---|---|
| **실제 공급자 예약을 바꾸지 않는다** | `tier=='simulated'` 가 아니면 승인 경로로 간다 |
| side effect를 직접 실행하지 않는다 | Mock 변경도 코어 Action 층이 한다. **이 Team은 판정만 한다**(v11 §5) |
| 결제하지 않는다 | 실결제는 구현 단계 4 |
| 링크 클릭 이후를 추적하지 않는다 | 이 Team 의 범위는 링크 생성까지다 |

## 걸리는 것

| 항목 | 상태 |
|---|---|
| 위임 범위 실제 값 (N·M·K) | `[2026-09-22 해결 — 단 근거가 측정이 아니다]` 설정 `travel.delegation` 에 **우리가 고른 값**으로 있다(건당 50,000원 · 누적 150,000원 · 2회). **협약이 생기면 그 협약이 이 자리를 받는다.** 값이 통제한다는 것은 시험이 안다 |
| 위임을 주고 거두는 화면·API | `[2026-09-22 해결]` REST `/v1/delegations/*` + 운영 화면 `/ui/delegations`. 맡기기는 **무엇이 열리는지 보여 주는 확인 단계**를 거치고, 거둘 것이 없으면 `409` 로 사유가 화면에 뜬다. 이력은 `delegation_events`(021)에 덧붙는다. ~~남은 구멍 — `/ui/*` 에는 로그인이 없다~~ ★`[2026-09-23 해결]` 로그인한 운영자만, 위임 변경은 `delegation:write` 가 있어야 하고 행위자는 **그 운영자 id** 로 남는다([D-CS-007](../decisions/D-CS-007-ui-operator-login.md)) |
| 위임 범위를 Trip 단위로 | `[미확보]` 고객 단위로 뒀다 — `bookings` 에 `trip_id` 가 없고, 고객 단위가 상한을 **더 빨리 채우는**(안전한) 방향이다 |
| 변경 링크의 형태 | `[2026-09-22 부분 해결]` **우리 쪽 화면은 생겼다**(위 「변경 링크」 절). 여전히 `[미확보]` 인 것은 **업체 쪽으로 가는 딥링크** — 업체별 예약 관리 URL 규격이 달라서, 지금 화면은 「업체에서 직접 변경해 주세요」까지만 말하고 업체 URL 을 싣지 않는다. 지어낼 수 없는 값이다 |
| 실제 업체 계약 | 범위 밖 — 구현 단계 4 |
| 보상 거래 실패 처리 | `[2026-09-22 해결]` **상태 이름을 새로 만들지 않았다** — 되돌림 요청 자신이 `action_requests` 행이라 그 행의 `status`(`failed`·`unknown`)가 시도 상태다. 위 「되돌림 경로」 절. 남은 것은 **실제 업체 API 의 부분 성공·시간 초과** — 공급자 원장이 우리 DB 라 아직 재지 못했다 |

★**이 Team이 이 프로젝트에서 가장 위험한 자리다.** 자동 실행 분기가 실제 공급자로 새면 승인 없이 남의 돈이 나간다. 게이트를 문서가 아니라 **테스트로** 막는 이유다.

## 관계

- [index.md](index.md) — Team 목록과 경계
- [activity.md](activity.md) — 예약 변경을 만들어 내는 쪽
- [../actions/index.md](../actions/index.md) — side effect가 일어나는 유일한 곳
- [../actions/approval.md](../actions/approval.md) — 승인 경계
- [../../../wiki/decisions/D-005-write-gate.md](../../../wiki/decisions/D-005-write-gate.md) — 쓰기 게이트. 승계한다
- [../../../wiki/product/scope.md](../../../wiki/product/scope.md) — 실행 경계
