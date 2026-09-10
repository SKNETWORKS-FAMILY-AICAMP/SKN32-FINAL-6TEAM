---
type: guide
title: final_project_cs 지식 지도
description: 릴리스 대상 저장소의 9개 영역과 각 영역이 답하는 질문
status: draft
domain: travel
domain_note: 판올림 이력을 싣는다. 두 도메인이 대조로 나온다
---

# final_project_cs 지식 지도

> `[실측 2026-09-01]` **`app/core/case_runtime/`·`access_action/` 은 `__init__.py` 만 남은 빈 패키지다.**
> 2026-08-13 에 중첩 구조로 갔다가 **평면 구조로 되돌아왔다.** 정본은 `app/core/*.py` 다.
> 구조가 또 바뀔 수 있으므로 **작업 전에 실제 경로를 확인한다.**

처음이면 [quickstart.md](quickstart.md)부터 본다.

여기는 **코드와 같은 커밋에서 바뀌어야 하는 지식**만 둔다. 제품·일정·사업성은 [중앙 허브](../../wiki/index.md)에 있다.

★**[2026-09-08] 도메인이 여행으로 바뀌었다**(그 판이 v10, 지금 기준선은 **v11**). **코어는 그대로 쓴다** — `runtime/`·`actions/`·`context/`의 계약·동시성·승인 경계는 도메인을 모르므로 유효하다. 반면 `teams/`의 Team 페이지 다섯(return-refund·fulfillment-logistics·procurement-order·catalog-verification·voc-store-manager)은 **MVP 경로에서 빠진 쇼핑몰 Team**이고, 여행 Team(Activity·Booking Handoff·Dining·Mobility)의 페이지는 아직 없다. `[실측 2026-09-09]`

여행에서 코어가 바뀌는 것은 **여섯**이다(v11 §5-A) — 분류 라벨(슬러그 `itinerary_submit`/`incident_report`/`confirm_request`/`adjust_reject`/`other`), **라우팅 축 둘**(`case_type`+`intent`, §5-B), **분류 어휘의 자리**(코드 상수 → `config/` 선언 하나), **capability 선택**(팀이 `select_capability` 로 고른다, §5-C), Context Broker가 싣는 것(여행 상태), Action 3종(장소·운영 / 이동 시간 / 기상), Composer 소재(**한국어** 통지 문구 — `[정정 2026-09-10]` v10 은 영어였다). 새 집합체는 **Trip** 하나이고 `Case`에 `trigger_source`·`trip_id`가 붙는다(§4-B).

## 말 네 개를 먼저 나눈다

이 저장소는 아래 네 말을 **다른 뜻으로** 쓴다. 섞으면 소유 판단이 틀어진다.

| 말 | 뜻 | 구성기에서 |
|---|---|---|
| **컴포넌트** | 제거하면 시스템이 성립하지 않는 구성물 | **선택 불가** — 항상 포함 |
| **모듈** | 켜고 끌 수 있는 단위. 빼도 나머지가 돈다 | **선택 가능** |
| **Port** | 구현을 갈아 끼우는 지점 | 구현체를 **고른다** |
| **인스턴스** | 같은 계약을 만족하는 것을 **여러 개** 둘 수 있다 | 개수를 **더하고 뺀다** |

★"모듈형 Basement" 의 실체는 **컴포넌트는 고정이고 모듈은 가변**이라는 것이다.

`[실측 2026-09-07]` 지금 실제로 꺼질 수 있는 것은 둘뿐이다 — `config.require_module()`
호출처가 `vector_rag`(기본 ReadToolbox)와 `graph_store`(GraphStore 어댑터) 둘이다
(`app/composition.py`).

★**이 구분이 실제로 사고를 냈다.** 인라인 분류는 필수 기능이라 컴포넌트인데
2026-08-30 모듈 토글 작업이 그것을 `voc` **모듈** 아래 묶었다. 그래서 `voc: false`
로는 제품이 아예 안 떴다 — **빼도 되는 자리에 뺄 수 없는 것을 넣은 것**이다.
지금은 풀렸고 `require_module("voc")` 호출은 0곳이다. 경위는
[../../program/research/2026-09-01_VOC가_팀모듈로_흘러간_경위.md](../../program/research/2026-09-01_VOC가_팀모듈로_흘러간_경위.md).

## 영역

### [runtime/](runtime/index.md) — Case가 흘러가는 곳
`app/core/` (평면)
Case 생명주기, Shared State, Controller, 충돌 처리, 메시지 배달.
**이 영역은 도메인을 모른다.** 환불이든 배송이든 여행 일정 조정이든 다 같은 Case다 — 그래서 여행 판올림에서 **그대로 승계한다**(v11 §6). 다만 Case를 시스템도 만든다는 것이 새로 붙는다(`trigger_source`).

### [teams/](teams/index.md) — 업무 책임 단위
`app/modules/travel_ops/`
Team 계약, Registry, 경계, 개별 Team 페이지.
`[실측 2026-09-10]` **개별 Team 문서는 여행 넷이다** — [activity](teams/activity.md)·[booking-handoff](teams/booking-handoff.md)·[dining](teams/dining.md)·[mobility](teams/mobility.md). **쇼핑몰 7종은 [records/legacy/teams/](records/legacy/teams/) 로 옮겼다.** 계약·Registry·경계 문서는 도메인과 무관하게 유효하다 → v11 §5.

### [context/](context/index.md) — 읽기 경로
`app/core/context.py`, `app/infrastructure/rag/`
Team이 필요한 자료를 모아 주는 계층. **Team은 직접 읽지 않는다.**

### [actions/](actions/index.md) — 쓰기 경로
`app/core/` (평면)
**side effect가 일어나는 유일한 곳.** 제안·근거대조·승인·실행·발행.

### [external/](external/index.md) — 바깥과 만나는 면
`app/presentation/`
REST, MCP, A2A, Trust Boundary.

### [data/](data/index.md) — 저장
`app/infrastructure/db/`
스키마, 마이그레이션, tenant 격리.

### [quality/](quality/index.md) — 무엇으로 보증하는가
`tests/`
**불변식 카탈로그**, 테스트 지도, 평가 하네스, 사각지대.

### [operations/](operations/index.md) — 돌리는 법
로컬 셋업, 실행, 문제 해결.

### [decisions/](decisions/index.md) — 이 저장소에만 영향을 주는 결정
여러 저장소에 걸친 결정은 [중앙 허브](../../wiki/decisions/index.md)에 있다.

## 흐름으로 보기

읽기와 쓰기가 갈리는 게 이 설계의 핵심이다.

```text
                    ┌─────────────┐
   요청 ──────────→ │  external/  │
                    └──────┬──────┘
                           ↓
                    ┌─────────────┐
                    │  runtime/   │ ←──── data/
                    │ Controller  │
                    └──┬───────┬──┘
              읽기 ↙          ↘ 위임
        ┌──────────┐      ┌─────────┐
        │ context/ │ ───→ │ teams/  │
        └──────────┘      └────┬────┘
                               │ ActionProposal (제안만)
                               ↓
                         ┌───────────┐
                         │ actions/  │ ← side effect는 여기서만
                         └───────────┘
```

## 이 저장소의 불변식

전체는 [quality/invariants.md](quality/invariants.md).

| ID | 불변식 | 판정 |
|---|---|---|
| `INV-CS-ARCH-001` | Core 계층은 도메인 어휘에 의존하지 않는다 | automated |
| `INV-CS-ARCH-002` | Core는 Team 내부를 import하지 않는다 | automated |
| `INV-CS-ACT-001` | Team은 side effect를 실행하지 않는다 | automated |
| `INV-CS-ACT-002` | 동일 idempotency key는 1회만 실행된다 | automated |
| `INV-CS-RT-001` | Shared State가 Case의 단일 원천이다 | automated |

## sample과의 관계

`final_project_sample`에서 먼저 검증한 계약을 여기로 이식한다.

**sample의 예시 Team과 검증 상태를 여기의 릴리스 완료로 간주하지 않는다.**

### ★ [2026-09-03] 계약은 이식하고 파일은 복사하지 않는다

`[실측]` `wiki/records/handoff/11_basement_version_reference.md` 에서 이관. **전량 미이관이었다.**

> **CS 는 sample 의 basement 참조를 기록만 하고, basement 파일을 복사·적용하지 않는다.**

**위 서술이 "이식한다"라고만 적고 있었다.** 이 부정 진술이 없으면 **파일을 복사해도 되는 것처럼 읽힌다.**

```
basement_version   0.2.0
source_commit      92b4c438a8f3bce1a5c65a54b38285d150020225
source_branch      project-final_project_sample
applied_at         2026-08-18T13:13:26Z
```

기록은 `wiki/records/manuals/basement_version.json` 에 있다.

#### 이 참조는 낡았다

`[실측]` 2026-09-03 확인.

| | 커밋 |
|---|---|
| 기록된 참조 | `92b4c43…` (2026-08-18) |
| **sample 의 현재 HEAD** | **`8a1ac56`** — "cs 가 먼저 고친 결함 넷을 sample 에도 이식한다" |

**16일 벌어져 있다.** 그리고 그 사이 변경이 **cs → sample** 방향이었다.

> **향후 basement 갱신은 명시적으로 기록하고 sample manifest 와 재대조해야 한다.**

`[미확보]` **재대조 시점이 정해져 있지 않다.** [drift-case-voc](../../wiki/governance/drift-case-voc.md) 와 같은 종류다 — 참조가 낡았는데 아무도 안 센다.

## 중앙 허브

| 알고 싶은 것 | 어디 |
|---|---|
| 제품이 무엇인가 | [product/](../../wiki/product/index.md) |
| 왜 이렇게 설계했나 | [decisions/](../../wiki/decisions/index.md) |
| 일정과 DoD | [delivery/](../../wiki/delivery/index.md) |
| 평가 기준 | [evaluation/](../../wiki/evaluation/index.md) |

## 최근 변경

[log.md](log.md)
- [domain-swap.md](domain-swap.md) — **도메인을 갈아 끼울 때 무엇을 바꾸고 무엇을 두나.** 11행이 Core 의 정본

## 기록 구역 `records/` (2026-09-08)

옛 `docs/`가 이 wiki 아래 `records/`로 합쳐졌다. **읽는 순서는 wiki 본문 먼저**, `records/`는 본문이 인용한 근거를 확인할 때 연다.

| `records/` | 지위 |
|---|---|
| `evidence/` · `reports/` | 계속 쓴다 — 재현 출력과 작업 리포트. 날짜 파일명 그대로, 고치지 않는다 |
| `handoff/` · `history/` · `plans/` · `vision/` 등 | 동결된 기록. 현재 계약·계획·결정은 wiki 본문 |

규칙은 허브 [governance/work-loop.md](../../wiki/governance/work-loop.md) 2026-09-08 절. 검사기는 `records/`를 면제한다.
