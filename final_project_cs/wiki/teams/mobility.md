---
type: plan
title: Mobility Team
description: 구간 이동이 성립하는지 판정한다. 이 Team의 재계획은 일정 순서 자체를 바꾸므로 가장 넓게 흔든다
status: draft
tags: [agent, customer-operations]
owners: [human:미배정]
domain: travel
---

# Mobility Team

★**코드가 생겼다.** `[실측 2026-09-10 작업 트리]` `app/modules/travel_ops/mobility.py` 가 있고 `config/project.yaml` 에 등록돼 있다. **`[실측 2026-09-10 git]` 둘 다 아직 커밋 전이다** — 되돌려지면 이 문장이 거짓이 된다. 이 문서는 한때 "아직 코드가 없다"고 적었다.

근거는 계획서 v11 §5. **MVP 필수는 아니다** — 5주차에 선제 조정 루프와 함께 붙는다(v11 §9-B).

`[실측]` 뼈대는 쇼핑몰 `fulfillment_logistics` 에서 가져온다 — 구간·경로 판정이 구조가 같다. 그 Team 이 이미 `business_subject` 를 옳게 쓰는 유일한 Team 이기도 하다(아래).

## ★ [2026-09-10] 판정 도구가 아직 값을 안 준다

`[실측 2026-09-10 작업 트리]` **`ReadToolbox.route()` 와 `transit()` 가 둘 다 `None` 을 돌려준다**(`app/tools/read_tools.py:252,256`).

★**그래서 아래의 이동 시간·환승·막차 판정이 지금은 돌지 않는다.** 계약과 뼈대는 있고 **바깥에서 값이 안 들어온다** — v11 §7-C 가 정한 1단계 공개 API(이동)가 아직 안 붙었다.

| 무엇 | 상태 |
|---|---|
| `mobility.check_route`·`status`·`exception` capability | 선언돼 있다 |
| 경로·소요 시간 조회 | **`None`** |
| 환승·막차 데이터 | **`None`** |

★**「모름」으로 끝나는 것이 폴백보다 낫다**(v11 §4-D). 값이 없으면 없다고 돌려주고, 추정으로 채우지 않는다. 다만 **문서가 판정을 현재 동작처럼 적으면 안 된다.**

`[실측]` `select_capability()` 가 `intent == "mobility"` 만 본다 — 라우팅이 두 축이 됐으므로 그 분기도 같이 봐야 한다(코드 담당 몫).

## 셋을 갖는다

### ① 검증 규칙 — 코드가 판정한다

| 무엇 | 판정 |
|---|---|
| 구간 이동 시간 | A에서 B로 그 시간 안에 갈 수 있는가 |
| 환승 | 환승이 몇 번인가. 환승 시간이 현실적인가 |
| 막차 | **마지막 일정에서 숙소로 돌아갈 수 있는가** |
| 여유 | 앞 일정 종료와 다음 일정 시작 사이에 이동 시간을 빼고 남는가 |

★**막차가 이 Team에서 가장 조용히 터지는 자리다.** 낮 일정은 다 맞는데 마지막 일정이 끝나면 돌아갈 수단이 없는 경우가 있다. 인바운드 고객은 대안 교통편을 모른다.

**LLM을 부르지 않는다.** 전부 계산 판정이다(v11 §4-D).

### ② 감시 소스

| 소스 | 무엇을 본다 | 상태 |
|---|---|---|
| 운행 정보 | 지연·운휴·파업 | `[미확보]` 출처 미정 |
| Routes | 경로·소요 시간 | 제공자 데이터 |

`[미확보]` 소요 시간이 **실시간인지 표준 시간인지**를 구분해 저장해야 한다. 표준 시간을 실시간처럼 쓰면 러시아워에 전부 틀린다. v11 §4-D의 "확인 수준과 시각을 같이 저장한다"가 이 자리에 걸린다.

### ③ 재계획 후보

**경로·순서 재배열.** 이 Team의 재계획은 다른 Team과 성질이 다르다.

| Team | 재계획이 바꾸는 것 |
|---|---|
| Activity · Dining | 그 항목 하나의 시각 또는 대상 |
| **Mobility** | **일정의 순서 자체** |

## ★ 그래서 가장 넓게 흔든다

순서를 바꾸면 그 안의 모든 예약 시각이 따라 움직인다. Activity 예약 시간, Dining 영업시간, Booking Handoff가 걸어야 할 업체 건까지 전부 다시 봐야 한다.

```
Mobility: "오후 순서를 B→A→C 로 바꾸면 이동 40분이 줄어든다"
   ↓ 이 후보 하나가 그날 예약 전부의 시각을 바꾼다
코어 검증 층: 전체 일정 정합성 재검증
   ↓ Activity 예약 시간이 안 맞으면 그 후보는 버려진다
   ↓ 통과한 것만
통지
```

★**그래서 Mobility가 다른 Team을 호출하고 싶어진다.** "A Team, 이 시간으로 옮길 수 있어?"라고 묻고 싶어진다. **금지다** — Team 간 직접 호출은 의존 그래프를 만들고 교체를 불가능하게 한다([team-boundary.md](team-boundary.md)). 후보를 내고 코어 검증 층의 판정을 받는다.

`[미확보]` 재배열 후보를 몇 개까지 내는지, 코어가 어떤 순서로 검증하는지 안 정했다. 조합이 폭발하는 자리다 — v11 §9-A는 **OR-Tools 최적화를 MVP에서 뺐다.** 규칙 기반 소수 후보로 시작한다.

## manifest — 실제 구현

`[실측 2026-09-10 작업 트리]` `app/modules/travel_ops/mobility.py`. **한때 이 절은 「제안이다. 코드에 없다」였다.**

```python
capabilities          = ["mobility.check_route", "mobility.status", "mobility.exception"]
accepted_case_types   = ["mobility"]                 # ★객체 종류다. 요청 종류가 아니다
required_context      = ["case_state", "policy", "db_facts", "history"]
allowed_tools         = ["read.route", "read.transit", "read.policy"]
knowledge_scope       = ["mobility", "transit", "route_exception"]
max_steps             = 6
default_capability    = "mobility.check_route"
```

★**`accepted_case_types` 가 「객체 종류」다.** 이 문서는 한때 `itinerary_submitted`·`incident_reported` 같은 **요청 종류**를 적어 뒀다. **축이 틀렸다.** v11 §5-B — 라우팅은 두 축이고 Team 을 고르는 것은 `case_type`(객체 종류, `issue_code` 접두에서 뽑는다)이다. 요청 종류는 `intent` 쪽이다.

★**요청 종류 다섯만으로는 여섯 팀 어디에도 안 간다** — 2026-09-09 실행으로 확인됐고 그래서 v11 이 축을 둘로 갈랐다.

★`locked_bookings` 가 이 Team에 특히 중요하다. **잠긴 예약(항공·숙박)은 순서 재배열의 고정점**이다. 움직일 수 없는 것을 모르면 재배열이 무의미해진다.

## `business_subject` — 도메인이 바뀌어도 안 바꾸는 칸

`[실측 2026-09-09]` `A-COP_여행Team모듈_구성안.md`. 도메인 객체 id 는 코어에 없다 — `customer_cases` 컬럼에도 `app/core/`·`app/application/` 코드에도 `order_id`·`booking_id` 가 **0회**다. 도메인 객체는 `idempotency_key(tenant_id, request_id, action_type, business_subject)` 의 `business_subject` **문자열 한 칸**으로 들어간다.

★**칸 이름을 `booking_id` 로 바꾸면 다음 도메인에서 또 바꿔야 한다.** 이름은 이미 중립이고 맞다. 정해야 하는 것은 규칙이다.

> **`business_subject` 에는 그 Action 이 바꾸는 대상 객체의 id 를 넣는다. 대상이 특정되지 않으면 실행하지 않고 escalate 한다.**

**`case_id` 폴백을 두지 않는다.** 폴백이 있으면 특정 실패가 조용히 넘어간다. 그리고 여행에서 실제로 터진다 — `request_id` 는 Case 당 하나라서, **한 Case 안에서 같은 종류의 작업을 두 객체에 하면 키가 같아진다.**

```
subject = case_id   →  같은 키    ← 둘째가 조용히 중복 처리되거나 막힌다
subject = 객체 id    →  다른 키
```

`[실측]` 쇼핑몰에서는 Case 하나가 대개 주문 하나라 잘 안 드러났다. 여행은 Trip 하나에 예약이 여럿이고 **"비가 온다" 는 사건 하나가 여러 예약을 동시에 바꾼다.**

### ★ [2026-09-09] 코드가 이 규칙을 안 지킨다

`[실측]` `app/modules/travel_ops/_base.py:169` — 여행 Team 공용 기반이 **3단 폴백**을 쓴다.

```python
subject = str(arguments.get("booking_id") or arguments.get("trip_id") or task.case_id)
```

★**`case_id` 로 떨어지는 마지막 칸이 위 규칙이 두지 말라고 한 바로 그것이다.** 그리고 이번엔 한 Team 이 아니라 **공용 기반이라 여행 Team 전부가 물려받는다.**

`booking_id` 가 `None` 이면 조용히 `case_id` 가 되고, **한 Case 안의 두 예약이 같은 키를 갖는다.** 둘째가 중복으로 걸려 조용히 안 나간다.

| 지금 | 문서가 정한 것 |
|---|---|
| `booking_id` → `trip_id` → `case_id` | `booking_id` 없으면 **실행하지 않고 escalate** |

`[실측]` 보낼 자리는 이미 있다 — 같은 파일의 `_unknown()` 이 "값이 없는 게 아니라 모르는 상태"를 escalate 로 보낸다.

**코드 수정은 담당 세션 몫이다.** 이 문서는 어긋남만 적는다.

### ★ [2026-09-10] 계획서가 이 규칙을 받았다 — v11 §4-E

`[결정 2026-09-10]` **`[미확보]` 가 닫혔다.** 어제까지 "규칙을 계획서 §6 에 넣는 일이 남았다"고 적혀 있었다. v11 이 **§4-E 를 신설해** 정했다.

> **실행 요청의 멱등 키에 들어가는 「대상」은 서버가 정한다** — 인자에서 꺼내 **실재하는지·이 여행의 것인지 확인한 뒤** 키에 넣는다.

| 작업 종류 접두 | 꺼낼 인자 | 무엇인가 |
|---|---|---|
| `mobility.*` | `item_id` | 일정 항목 한 구간 |

★**이 Team 은 언제나 `item_id` 다.** 구간은 예약이 아니라 일정 항목이다.

★**Team 이 준 값을 그대로 쓰지 않는다.** 코드 주석이 이미 그렇게 경계한다 — `controller.py:371` 의 *"The Team value is advisory. The server owns the final key at the write boundary."*

★**왜 Case 를 쪼개는 쪽을 택하지 않았나.** 다른 안은 "한 Case 에 같은 종류 작업은 하나"를 사양으로 못박는 것이었다. **비가 오면 액티비티·식당·이동이 한꺼번에 흔들린다** — Case 를 쪼개면 한 사건을 여러 Case 로 나눠 고객에게 따로 통지하게 되고, **DoD-8(거부하면 되돌린다)에서 어디까지 되돌릴지가 애매해진다.**

`[실측 2026-09-10]` **v11 §12 가 이것을 DoD-24 로 올렸다** — 「한 Case 에서 대상 객체가 다른 제안 둘이 각각 저장된다」. 문서 규칙이 아니라 검사 항목이 됐다.

`[미확보]` 위 규칙표를 코드에 둘지 `config/` 에 둘지는 안 정했다. **어휘는 설정으로 빼기로 했지만(v11 §5-B) 이건 계약에 더 가깝다.**

## 이 Team이 하지 않는 것

| 하지 않는다 | 왜 |
|---|---|
| 교통편을 예약하지 않는다 | side effect는 코어 Action 층. 업체 건은 [booking-handoff.md](booking-handoff.md) |
| **다른 Team에게 묻지 않는다** | 위 절. 후보를 내고 코어 판정을 받는다 |
| 최적 경로를 계산하지 않는다 | MVP는 성립 판정과 소수 후보까지. OR-Tools는 범위 밖 |
| 보행 부담·피로를 모델링하지 않는다 | 범위 밖 (v11 §9-A) |
| read 도구를 직접 호출하지 않는다 | Context Broker가 읽기 예산을 통제한다 |

## 걸리는 것

| 항목 | 상태 |
|---|---|
| 운행 정보 출처 | `[미확보]` |
| 소요 시간이 실시간인가 표준인가 | `[미확보]` 구분해 저장해야 한다 |
| 재배열 후보 수와 검증 순서 | `[미확보]` 조합 폭발을 어디서 끊는지 |
| 막차 데이터 | `[미확보]` **도시는 서울로 정해졌다**(2026-09-10). 확인이 가능해졌고 아직 안 했다 |
| 골든셋 | `[실측]` 지금 72건은 쇼핑몰. 이 Team 시나리오는 0건 |

## 관계

- [index.md](index.md) — Team 목록과 경계
- [team-boundary.md](team-boundary.md) — **다른 Team을 부르지 않는다**가 여기서 가장 시험된다
- [activity.md](activity.md) · [dining.md](dining.md) — 순서가 바뀌면 이 둘이 흔들린다
- [booking-handoff.md](booking-handoff.md) — 업체 건 인계
- [../../../wiki/product/scope.md](../../../wiki/product/scope.md) — 여행 MVP 범위
