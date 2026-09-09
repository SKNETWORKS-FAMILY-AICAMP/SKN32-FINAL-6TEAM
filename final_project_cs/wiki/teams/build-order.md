---
type: plan
title: Team 을 어느 순서로 만드나
description: 여행 Team 을 무엇부터 하나. 그리고 실제로는 여섯이 한꺼번에 붙어서 순서가 다르게 흘렀다
status: draft
tags: [architecture, contract]
domain: travel
---

# Team 을 어느 순서로 만드나

`[실측]` 근거는 v10 §5·§9-B.

## 계획한 순서

| # | Team | 주차 | 왜 이 순서 |
|---|---|---|---|
| 1 | **Activity** | 2~3 | **취소·변경 규정이 문서로 존재한다.** 판정 규칙을 바로 쓸 수 있고 예약금이 걸려 실패 비용이 크다 |
| 1 과 함께 | **Booking Handoff** | 2~3 | 감지해서 우리 일정을 고쳐도 **업체 예약을 못 바꾸면 고객이 결국 직접 처리한다** (팀 결정 2026-09-08) |
| 2 | Dining | 4 | |
| 3 | Mobility | 5 | **선제 조정 루프와 함께 붙는다** — 이 Team 의 재계획이 일정 순서 자체를 바꾸므로 루프가 있어야 의미가 있다 |
| 등록만 | Lodging / Flight | — | 잠긴 예약으로만 취급한다 |

### 왜 Activity 가 첫째인가

**판정 규칙을 밖에서 가져올 수 있는 유일한 Team 이다.**

```
골프장 우천 위약금 규정  →  그대로 판정 규칙이 된다
기상청 초단기예보        →  그대로 감시 소스가 된다
```

다른 Team 은 이 둘 중 하나가 `[미확보]` 다 — Dining 은 임시휴무를 어디서 받는지 모르고, Mobility 는 운행 정보 출처가 미정이다.

★**Activity 하나만으로도 루프가 성립하도록 설계한다**(v10 §10 리스크). 7주 배분이 추정이라 Dining·Mobility 는 절삭 가능해야 한다.

### 왜 Booking Handoff 가 같이 가나

**Activity 가 만들어 내는 결과의 절반이 업체 건이기 때문이다.** "10/03 골프를 10/04 로 옮기자"는 후보를 냈는데 그걸 넘길 곳이 없으면 감지가 제품이 되지 않는다.

★**그리고 여기가 가장 위험한 자리다.** 자동 실행 분기가 실제 공급자로 새면 승인 없이 남의 돈이 나간다. `tier == 'simulated'` 게이트를 **아키텍처 테스트로** 막는다(DoD-14·15).

## ★ 실제로는 이 순서로 안 갔다

`[실측 2026-09-09]` **여섯이 한꺼번에 붙었다.**

| 항목 | 실측 |
|---|---|
| 모듈 | `app/modules/travel_ops/` 7파일 — `_base`·`activity`·`booking_handoff`·`dining`·`mobility`·`locked_bookings` |
| 등록 | `config/project.yaml` 6팀 전부 `active: true`, `implementation_ref` 6/6 해석됨 |
| 테스트 | 단위·계약·아키텍처 552개 통과 |

**순서를 지키는 것보다 `_base.py` 로 계약 포장을 한 번에 만드는 쪽이 쌌기 때문이다.** 여섯이 같은 뼈대를 쓰므로 하나씩 붙이면 뼈대를 여섯 번 고치게 된다.

### 그 선택이 만든 것 — 좋은 쪽과 나쁜 쪽

| | |
|---|---|
| **좋은 쪽** | 가드·`_result`·`_evidence`·`_escalate`·`_unknown`·`_proposal` 이 한 곳에 있다. Team 마다 다르게 하는 실수가 안 생긴다 |
| **★나쁜 쪽** | **결함도 한꺼번에 물려받는다.** `_base.py:136` 의 `business_subject` 3단 폴백(`booking_id → trip_id → case_id`)이 **여행 Team 전부에 걸린다** — 전에는 한 Team 만의 문제였다 |

★**공용 기반은 실수의 전파 경로이기도 하다.** 뼈대를 먼저 만들면 뼈대를 먼저 검증해야 한다.

## ★ 지금 막혀 있는 것 — Team 순서가 아니라 그 앞이다

`[실측 2026-09-09]` **여섯이 다 붙었는데 여행 Case 가 하나도 라우팅되지 않는다.**

```
INTENTS               order · shipping · return · exchange · other   ← 쇼핑몰
여행 Team 이 받는 것   activity · booking · mobility · dining · lodging · flight
겹치는 것              0개  →  ClassificationFailed  →  escalated
```

**분류기가 막으면 여섯 중 아무도 안 불린다.** 그래서 **Team 순서보다 코어 1 의 분류 어휘 교체가 먼저다**(v10 §9-B 1주차 "코어 라벨 교체").

★**막으라고 만든 가드가 안 막는다.** `tests/unit/voc/test_feedback_intent_alignment.py` 가 등록표가 아니라 `VocStoreManagerTeam` 하나를 보는데, 그 Team 은 지금 `config/project.yaml` 에 등록조차 안 돼 있다. **고정된 예시를 보는 가드는 예시가 사라지면 가드가 아니게 된다.**

**코드 수정은 담당 세션 몫이다** → [../../../wiki/delivery/open-items.md](../../../wiki/delivery/open-items.md)

## 다음에 무엇을 만드나

| 순서 | 무엇 | 왜 |
|---|---|---|
| 1 | **코어 1 분류 어휘 교체** | 이게 없으면 위 여섯이 전부 죽은 코드다 |
| 2 | `business_subject` 폴백 제거 | 계약이라 나중에 바꾸면 그 위가 전부 따라 바뀐다 |
| 3 | Activity 판정 규칙 실물화 | 지금은 계약 포장만 있다 |
| 4 | 선제 조정 루프 | Mobility 와 함께 (v10 §9-B 5주차) |
| 5 | **Place Verification 등록** | `[실측 2026-09-10]` **원격은 생겼다**(`travel_remote_agent.py` 202줄 · 통합 테스트 7건). `config/project.yaml` 등록이 **0건**이라 아직 부를 수 없다 |

<details>
<summary>v9(쇼핑몰) 순서 여섯 — 무엇이 갈렸는지 보려고 남긴다</summary>

1 Response Generation & Review(구현이 끝나 있어 가장 빨리 데모) · 2 Return & Refund(Mock) · 3 Procurement + Order & Payment · 4 Fulfillment & Logistics · 5 VOC & Store Manager 보완 · 6 Catalog & Verification(A2A 라 마지막).

★**2번이 기준 Team 이었던 이유** — 외부 연동 없이 승인 경계 전체(`ContextPack → ActionProposal → 승인 대기`)를 보일 수 있는 유일한 Team 이고, 금융 side effect 가 fixture 로 격리돼 실수해도 돈이 안 나갔다. **여행에서 그 자리는 Activity 다**(규정이 문서로 있고 Mock 예약 확인이 허용된다).

★**1번의 함정** — `response_generation_review` 가 구현은 됐는데 `accepted_case_types=[]` 라 **Registry 가 선택할 수 없었다.** "구현됐다"와 "선택된다"는 다르다.

★**그 함정이 지금 더 큰 모양으로 재현됐다.** 이번엔 빈 목록이 아니라 **분류기가 그 case_type 을 아예 못 만든다.** 같은 사고의 상류 버전이다.

★**6번을 마지막에 둔 이유** — local canonical 결과와 승인 경계를 먼저 고정해야 원격이 그것과 같은지 잰다. **Place Verification 에도 그대로 걸린다.**

`[실측 2026-09-10]` **그런데 이번엔 원격이 먼저 나왔다.** 로컬 여섯이 라우팅도 안 되는 상태에서 원격이 생겼다 — 순서를 뒤집은 이유는 **A2A 로 부를 상대가 아예 없어졌기 때문**이고(등록 교체로 `catalog_verification` 이 빠졌다), 그 원격은 **시뮬레이터라 비교 기준이 아니라 왕복 증명이 목적**이다.

</details>

## 관계

- [index.md](index.md) — Team 영역
- [activity.md](activity.md) · [booking-handoff.md](booking-handoff.md) — MVP 필수 둘
- [common-utils.md](common-utils.md) — 공통 뼈대
- [../../../wiki/delivery/open-items.md](../../../wiki/delivery/open-items.md) — 지금 막혀 있는 것
