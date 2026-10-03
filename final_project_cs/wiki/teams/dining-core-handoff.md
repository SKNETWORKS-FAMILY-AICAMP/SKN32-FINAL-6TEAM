---
type: plan
title: 요식 → 코어·팀 맞출 것
description: 코어 통합 확인 목록, 코어에 부탁할 연결 셋, activity 와 대안 기준 비교, 설문 식이 조건 제안
status: draft
tags: [agent, customer-operations]
owners: [human:요식 담당]
domain: travel
---

# 요식 → 코어·팀 맞출 것

`[2026-09-29]` develop `747dc79` 기준. 코드 확인은 `python scripts/dining/check_core_integration.py` 로 다시 돌린다.

## 1. 코어 통합 확인 목록

「요식 → 코어 통합」 문서(2026-09-28)의 여덟 항목. develop 에서 무엇을 보면 된 것인지 적는다.

| # | 항목 | 된 것으로 보는 근거 | develop 747dc79 |
|---|---|---|---|
| 1 | 같은 이름 둘이어도 들어간다 | 029 의 `places_shared_name_kind_uq(tenant_id, name, kind)` 를 걷는 마이그레이션 | ⬜ |
| 2 | 식당 번호 하나 | 코어 `places` 가 요식 `place_uid` 를 번호로 쓴다 | ⬜ |
| 3 | 영업시간 복사 안 함 | 일정 짜기 · 대체 판정이 `dining.open_at_slot` 을 부른다 | ⬜ |
| 4 | 사본 23행 정리 · 관광공사 음식점 제외 | 데이터 작업. DB 에서 사본 수를 센다 | 확인 필요 |
| 5 | 고객사 구분 | 데이터 작업. 요식 식당이 운영 고객사 소속인지 | 확인 필요 |
| 6 | 식사 조건 | 동행 조건 판정이 `dining.meets_condition` 을 부른다 | ⬜ |
| 7 | 등록 때 요식 먼저 | `intake/places.py` 가 요식 원장을 먼저 찾는다 | ⬜ |
| 8 | 다시 적재가 코어 DB 를 안 지움 | `rebuild.py --target core` (요식 쪽. role-dining 에 있고 develop 에는 아직) | ⬜ |

요식이 약속하는 것.

- 코어가 읽는 입구는 이것뿐이다. 이름을 바꿀 때는 먼저 알린다.
  `dining.dn_place` · `dining.open_at_slot` · `dining.meets_condition` · `dining.suggest_alternatives` · `dining.alternative_pool`
- `place_uid` 는 바뀌지 않는다(uuid5, 출처 번호에서 만든다). 폐업해도 행을 지우지 않고 `record_status = 'closed'` 로 둔다.
- 코어 DB 에 다시 채울 때는 `rebuild.py --db <코어DB> --target core` 만 쓴다. dining 스키마만 지우고 채운다.

코어에 물을 것.

- 수정이 어느 브랜치 · PR 에 있는가.
- 요식 `place_uid` 를 코어 장소 번호로 그대로 쓰는가, 짝 표를 두는가.
- 원장에 없는 식당을 코어가 새로 만들면 요식에 어떻게 알리는가.

## 2. 코어에 부탁할 연결 셋

### A. 휴무 · 지연 대안에 요식 원장 대안을 쓴다

지금 `itinerary_changes.plan_closed` 는 코어 `places` 에서 대안을 찾는다. 코어 장소에는 가격 · 결제 칸이 비어 있어
후보가 다 걸러지고 `itinerary_unresolved` 로 사람에게 넘어간다(2026-09-28 시험, 15:05 휴무 신고).

```sql
SELECT * FROM dining.suggest_alternatives(:place_uid, :starts_at, :ends_at, :conds, :next_lat, :next_lng);
```

돌려주는 것: 기준별 한 곳씩 — 일정이 가장 덜 밀리는 곳 · 원래와 비슷한 곳 · 가장 가까운 곳. 이유(`reason`)가 같이 온다.
이미 닫힌 곳 · 그 시각에 닫힌 것으로 확인된 곳 · 조건에 어긋나는 곳은 들어오지 않는다.

### B. 당일 점검(`tick_once`)을 부른다

```python
from app.modules.travel_ops.dining.tick import tick_once
notices = [r["notice"] for r in tick_once(conn, now, items) if r["notice"]]
```

- 코어가 넘길 것: 다가오는 식사의 `(place_uid, 방문 시각)` 목록.
- 요식이 돌려주는 것: 보낼 문장. 보내는 것은 코어다. 같은 말은 두 번 돌려주지 않는다(`dn_notice`).
- 안에 반복 · sleep 이 없다. 1분 크론이든 버튼이든 한 번 부르면 한 번 돈다.

물을 것: 깨우는 간격, 알림 창구(웹 채팅 · 푸시), 여행자가 대안을 고르면 누가 일정을 바꾸는가.

### C. 설문의 식이 조건을 요식 조건으로 옮긴다

`dining.survey.conds_from_survey(constraints)` → `("halal", "vegetarian_menu")` 같은 조건 튜플.
대안 · 판정을 부를 때 `conds` 로 넘긴다. 이동의 `mobility.wiring.modes_from_survey` 와 같은 방식이다.

## 3. activity 와 대안 기준 비교

| | 요식 (`dining.suggest_alternatives`) | activity (`activity/alternatives.py`) |
|---|---|---|
| 거르기 | 폐업 · 그 시각 닫힘 확인 · 조건 불일치 확인은 뺀다. 모름은 남긴다 | 원문 「매주 ○요일」 휴무만 뺀다 |
| 반경 | 500 m → 1 km → 2 km, 셋이 모이면 멈춘다 | 없음(풀 전체) |
| 유사도 | 음식 종류 태그 겹침 | 분류 · 시군구 같은 갈래 |
| 선호 | 식이 조건은 거르기에만 쓴다(확인된 곳만) | 0 건이면 우선순위 낮은 필드부터 빼고 다시 거른다 |
| 순위 | 기준별 한 곳씩: 덜 밀리는 곳 · 비슷한 곳 · 가까운 곳 | 직선거리 오름차순 1 · 2 · 3 위 |
| 이동 | 직선거리 추정(이동 계산기 값으로 바꿀 자리 있음) | 직선거리 |

정할 것.

- 사용자에게 보이는 1 · 2 · 3 순위 문구를 두 팀이 같게 쓸지.
- 선호를 점수로 쓸지, 거르기로만 쓸지.
- 이동을 직선거리로 둘지, mobility 이동 계산기 값을 쓸지(develop 에 계산기가 연결됐다).

## 4. 설문 식이 조건 제안

`[실측 develop 747dc79]` 설문에 식이 문항이 없다. 음식 세부는 맛 · 친절 · 청결 셋뿐이다
(`frontend/apps/web/src/features/onboarding/model.ts` `detailOptions.food`). 서버 설문(`survey.TripSurvey`)은
세부를 「각 담당 팀이 정해서 알려 주기로」 했고 `priority_details.food` 를 문자열 목록으로 받는다.
그래서 **설문 모양(스키마)을 바꾸지 않고** 선택지 두 개만 더하면 된다.

| 화면 선택지 | 코드 | 요식 조건 | 동작 |
|---|---|---|---|
| 채식 · 비건 | `vegetarian` | `vegetarian_menu` | 확인된 곳만 권한다 |
| 할랄 | `halal` | `halal` | 확인된 곳만 권한다 |

- 확인된 곳이 없으면 「근처에 확인된 할랄 식당이 없어요」처럼 말한다. 모르는 곳을 권하지 않는다.
- 아이 동반은 설문에서 꺼내지 않는다. 여행자 구성 「가족」이 아이를 뜻하지 않는다. 필요하면 「아이와 함께」를 따로 묻는다.
- 알레르기 · 돼지고기 제외 같은 조건은 원장에 데이터가 없다. 받더라도 판정에 쓰지 않는다고 적는다.

화면 팀에 부탁할 것: `detailOptions.food` 에 `["vegetarian", "채식·비건", "Vegetarian / vegan"]`, `["halal", "할랄", "Halal"]` 두 줄.

## 5. 공통 — 각자 PC 에서 데이터 채우기

`rebuild.py --target core` 하나로 코어 DB 에 요식 데이터가 채워진다(약 20 초, 코어 표는 건드리지 않는다).
팀 공용 준비 스크립트에 이 한 줄을 넣자고 제안한다.

요식 현황(2026-09-29): 식당 1,227 곳 · 폐업 25 · 영업시간 없음 116(빈칸 초안이 확인되면 24) · 정답셋 정확도 99 %.
