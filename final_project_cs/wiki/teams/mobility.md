---
type: plan
title: Mobility Team
description: 구간 이동이 성립하는지 판정한다. 이 Team의 재계획은 일정 순서 자체를 바꾸므로 가장 넓게 흔든다
status: draft
tags: [agent, customer-operations]
owners: [human:미배정]
---

# Mobility Team

★**아직 코드가 없다.** `app/modules/` 에 파일이 없고 `config/project.yaml` 에도 없다 `[실측 2026-09-09]`. 이 문서는 명세다. 구현되면 `type` 을 `concept` 으로 바꾼다.

근거는 계획서 v10 §5. **MVP 필수는 아니다** — 5주차에 선제 조정 루프와 함께 붙는다(v10 §9-B).

## 셋을 갖는다

### ① 검증 규칙 — 코드가 판정한다

| 무엇 | 판정 |
|---|---|
| 구간 이동 시간 | A에서 B로 그 시간 안에 갈 수 있는가 |
| 환승 | 환승이 몇 번인가. 환승 시간이 현실적인가 |
| 막차 | **마지막 일정에서 숙소로 돌아갈 수 있는가** |
| 여유 | 앞 일정 종료와 다음 일정 시작 사이에 이동 시간을 빼고 남는가 |

★**막차가 이 Team에서 가장 조용히 터지는 자리다.** 낮 일정은 다 맞는데 마지막 일정이 끝나면 돌아갈 수단이 없는 경우가 있다. 인바운드 고객은 대안 교통편을 모른다.

**LLM을 부르지 않는다.** 전부 계산 판정이다(v10 §4-D).

### ② 감시 소스

| 소스 | 무엇을 본다 | 상태 |
|---|---|---|
| 운행 정보 | 지연·운휴·파업 | `[미확보]` 출처 미정 |
| Routes | 경로·소요 시간 | 제공자 데이터 |

`[미확보]` 소요 시간이 **실시간인지 표준 시간인지**를 구분해 저장해야 한다. 표준 시간을 실시간처럼 쓰면 러시아워에 전부 틀린다. v10 §4-D의 "확인 수준과 시각을 같이 저장한다"가 이 자리에 걸린다.

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

`[미확보]` 재배열 후보를 몇 개까지 내는지, 코어가 어떤 순서로 검증하는지 안 정했다. 조합이 폭발하는 자리다 — v10 §9-A는 **OR-Tools 최적화를 MVP에서 뺐다.** 규칙 기반 소수 후보로 시작한다.

## manifest — 제안

★**제안이다. 코드에 없다.**

```python
capabilities        = ["mobility.validate", "mobility.reorder"]
accepted_case_types = ["itinerary_submitted", "incident_reported", "confirm_request"]
required_context    = ["trip_state", "locked_bookings", "constraints"]
allowed_tools       = ["read.route"]                      # 이름 미정
knowledge_scope     = ["mobility", "transit", "route"]
max_steps           = 5
```

★`locked_bookings` 가 이 Team에 특히 중요하다. **잠긴 예약(항공·숙박)은 순서 재배열의 고정점**이다. 움직일 수 없는 것을 모르면 재배열이 무의미해진다.

## 이 Team이 하지 않는 것

| 하지 않는다 | 왜 |
|---|---|
| 교통편을 예약하지 않는다 | side effect는 코어 Action 층. 업체 건은 [booking-handoff.md](booking-handoff.md) |
| **다른 Team에게 묻지 않는다** | 위 절. 후보를 내고 코어 판정을 받는다 |
| 최적 경로를 계산하지 않는다 | MVP는 성립 판정과 소수 후보까지. OR-Tools는 범위 밖 |
| 보행 부담·피로를 모델링하지 않는다 | 범위 밖 (v10 §9-A) |
| read 도구를 직접 호출하지 않는다 | Context Broker가 읽기 예산을 통제한다 |

## 걸리는 것

| 항목 | 상태 |
|---|---|
| 운행 정보 출처 | `[미확보]` |
| 소요 시간이 실시간인가 표준인가 | `[미확보]` 구분해 저장해야 한다 |
| 재배열 후보 수와 검증 순서 | `[미확보]` 조합 폭발을 어디서 끊는지 |
| 막차 데이터 | `[미확보]` 도시가 정해져야 확인 가능 |
| 골든셋 | `[실측]` 지금 72건은 쇼핑몰. 이 Team 시나리오는 0건 |

## 관계

- [index.md](index.md) — Team 목록과 경계
- [team-boundary.md](team-boundary.md) — **다른 Team을 부르지 않는다**가 여기서 가장 시험된다
- [activity.md](activity.md) · [dining.md](dining.md) — 순서가 바뀌면 이 둘이 흔들린다
- [booking-handoff.md](booking-handoff.md) — 업체 건 인계
- [../../../wiki/product/scope.md](../../../wiki/product/scope.md) — 여행 MVP 범위
