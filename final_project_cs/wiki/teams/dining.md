---
type: plan
title: Dining Team
description: 식사가 성립하는지 판정한다. 영업시간 데이터가 "오늘 연다"의 증거가 아니라는 것이 이 Team의 핵심 함정
status: draft
tags: [agent, customer-operations]
owners: [human:미배정]
---

# Dining Team

★**아직 코드가 없다.** `app/modules/` 에 파일이 없고 `config/project.yaml` 에도 없다 `[실측 2026-09-09]`. 이 문서는 명세다. 구현되면 `type` 을 `concept` 으로 바꾼다.

근거는 계획서 v10 §5. **MVP 필수는 아니다** — Activity·Booking Handoff 다음이다(v10 §9-B, 4주차).

`[실측]` **뼈대로 쓸 쇼핑몰 Team 이 없다.** Activity 는 `return_refund`, Mobility 는 `fulfillment_logistics` 를 베끼는데 이 Team 은 **신규**다(`A-COP_여행Team모듈_구성안.md`).

## 셋을 갖는다

### ① 검증 규칙 — 코드가 판정한다

| 무엇 | 판정 |
|---|---|
| 영업시간 | 그 시각에 문을 여는가. 라스트오더를 넘지 않는가 |
| 휴무 | 그날 쉬는가. 정기휴무인가 임시휴무인가 |
| 예약 여부 | 예약이 필요한 곳인가. 예약 없이 갈 수 있는가 |
| 동행 조건 | **아이 동반 가능·할랄·채식** 을 만족하는가 |

★**동행 조건이 인바운드에서 실제로 걸린다.** 1순위 고객이 외국인 개인·친구 그룹이라(v10 §1) 할랄·채식은 "있으면 좋은 것"이 아니라 못 맞추면 그 식사가 성립하지 않는 조건이다.

## ★ 이 Team의 핵심 함정 — 영업시간 데이터는 개점 확인이 아니다

`[실측]` v10 §4-D.

> `currentOpeningHours` 는 **오늘부터 7일의 제공자 데이터**이지 조회 순간의 개점 확인이 아니다.

**재조회 시각을 현장 관찰 시각처럼 표시하지 않는다.** 이게 이 Team이 가장 틀리기 쉬운 자리다.

| 우리가 아는 것 | 어떻게 표시하나 |
|---|---|
| 제공자가 "월요일 11:00~21:00"이라 한다 | 출처와 **확인 시각**을 같이 저장한다 |
| 오늘 실제로 열었는가 | **모른다.** '미확인'으로 표시한다 |
| 지금 대기가 얼마인가 | **모른다.** 모델이 채워 넣지 못하게 한다 |

v10 §4-D의 세 갈래 — 계산으로 판정 가능 / 확인 수준을 높일 수 있음 / 모름 — 이 Team은 **가운데와 오른쪽이 섞이는 자리**다.

### ② 감시 소스

| 소스 | 무엇을 본다 | 상태 |
|---|---|---|
| 영업 공지 | 임시휴무·시간 변경 | `[미확보]` 출처 미정 |
| Places 영업시간 | 정기 영업시간·휴무 | 제공자 데이터. **위 함정 참고** |

### ③ 재계획 후보

| 후보 | 언제 |
|---|---|
| 인접 대안 | 걸어갈 거리에 조건을 만족하는 다른 곳이 있을 때 |
| 식사 시간 이동 | 같은 곳을 다른 시각으로 옮길 수 있을 때 |

**후보 생성은 LLM이 하고, 생성한 후보는 ①을 다시 통과해야 통지된다.** 특히 동행 조건은 대안에서 가장 자주 깨진다 — "근처 맛집"을 제안하면서 할랄을 놓치는 식이다.

## 재계획이 다른 Team의 일정을 건드린다

식사 시간을 옮기면 앞뒤 액티비티와 이동이 흔들린다. Activity와 같은 구조다.

```
Dining: "19시 → 20시" 또는 "다른 가게" 후보를 낸다
   ↓ 후보는 제안이지 확정이 아니다
코어 검증 층: 전체 일정 정합성 재검증 (시간 충돌·이동 여유·예산)
   ↓ 통과
통지
```

**Team은 다른 Team을 직접 호출하지 않는다.** 전체 정합성은 코어 검증 층이 본다(v10 §5).

## manifest — 제안

★**제안이다. 코드에 없다.**

```python
capabilities        = ["dining.validate", "dining.replan"]
accepted_case_types = ["itinerary_submitted", "incident_reported", "confirm_request"]
required_context    = ["trip_state", "constraints", "policy"]
allowed_tools       = ["read.place", "read.route"]        # 이름 미정
knowledge_scope     = ["dining", "opening_hours", "dietary_constraint"]
max_steps           = 5
```

`[미확보]` 동행 조건(할랄·채식·아이 동반)을 `constraints` 에 어떤 모양으로 싣는지 안 정했다. 이건 Trip의 **필수 조건**에 속하므로 Context Broker가 싣는 쪽이 맞아 보이지만 정하지 않았다.

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

`[미확보]` 규칙을 계획서 §6(승계하는 코어 규칙)에 넣는 일은 계획서 담당 몫으로 남아 있다 — 지금 §6 은 제약만 적고 키를 무엇으로 만드는지는 안 적는다.

## 이 Team이 하지 않는 것

| 하지 않는다 | 왜 |
|---|---|
| 예약을 직접 하지 않는다 | side effect는 코어 Action 층. 업체 예약은 [booking-handoff.md](booking-handoff.md) |
| 다른 Team을 부르지 않는다 | 의존 그래프 금지 |
| read 도구를 직접 호출하지 않는다 | Context Broker가 읽기 예산을 통제한다 |
| **"지금 열려 있다"고 단정하지 않는다** | 제공자 데이터는 개점 확인이 아니다 |
| 맛·평점을 판정하지 않는다 | 우리는 성립 여부를 본다. 취향은 계획 생성기의 일이고 그건 우리 일이 아니다 |

## 걸리는 것

| 항목 | 상태 |
|---|---|
| 영업 공지 출처 | `[미확보]` Activity와 같은 문제 — v10 §0-3 |
| 할랄·채식 정보의 신뢰도 | `[미확보]` 제공자 데이터에 이 속성이 있는지, 있어도 맞는지 확인 안 됨 |
| 도시 | `[미확보]` 서울 권장이나 미정. 도시가 정해져야 표본 조사가 된다 |
| 골든셋 | `[실측]` 지금 72건은 쇼핑몰. 이 Team 시나리오는 0건 |

## 관계

- [index.md](index.md) — Team 목록과 경계
- [activity.md](activity.md) — 같은 셋 구조. 재계획이 서로를 흔든다
- [mobility.md](mobility.md) — 인접 대안의 "걸어갈 거리"를 판정하는 쪽
- [team-boundary.md](team-boundary.md) — 하면 안 되는 것 셋
- [../../../wiki/product/scope.md](../../../wiki/product/scope.md) — 여행 MVP 범위
