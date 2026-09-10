---
type: guide
title: Architecture
description: 시스템 경계와 저장소 관계. 구현 세부는 각 코드 저장소 wiki에 있고 여기는 경계만 다룬다
status: draft
domain: travel
---

# Architecture

**여기는 경계만 다룬다.** 구현은 각 코드 저장소의 `wiki/`에 있다.

여기 있는 것과 저기 있는 것을 가르는 기준은 [../governance/structure-guide.md](../governance/structure-guide.md) §2에 있다. 요약하면 **"무엇이 이 문서를 틀리게 만드는가"**로 판정한다.

## 읽기 순서

1. [system-context.md](system-context.md) — 시스템 경계와 외부 행위자
2. [core-design.md](core-design.md) — **Core 8개 구성요소**
3. [core-vs-team.md](core-vs-team.md) — 무엇이 Core에 남고 무엇이 Team으로 가는가
4. [pack-model.md](pack-model.md) — **Runtime 위에 도메인 Pack 을 갈아 끼우는 구조**
5. [concurrency.md](concurrency.md) — **경합 8종을 누가 처리하는가**
6. [repository-map.md](repository-map.md) — 저장소 6개의 역할과 관계
7. [tech-stack.md](tech-stack.md) — 쓰는 것과 미룬 것
8. [notifications.md](notifications.md) — **알림 두 종류와 확인할 수 있는 것**
9. [diagrams.md](diagrams.md) — 다이어그램 8종과 근거

## 각 문서

| 문서 | 답하는 질문 | 건드리면 위험한 것 |
|---|---|---|
| [system-context.md](system-context.md) | 누가 우리 시스템과 대화하는가 | 외부 경계를 늘리면 인증·감사 전부 영향 |
| [core-design.md](core-design.md) | **Core가 무엇으로 이루어져 있나** | 두 Broker 를 헷갈리면 Team이 브로커를 직접 잡는다 |
| [concurrency.md](concurrency.md) | **어떤 경합을 누가 처리하나** | 담당이 겹치면 아무도 안 한다 |
| [core-vs-team.md](core-vs-team.md) | 새 기능이 Core인가 Team인가 | 잘못 판정하면 Team 추가가 리팩토링이 된다 |
| [pack-model.md](pack-model.md) | Pack을 어떻게 교체하는가 | Core가 Pack을 import하면 교체 불가 |
| [tech-stack.md](tech-stack.md) | 무엇으로 만드나 | Docker 전제를 넣으면 이 기계에서 안 돈다 |
| [notifications.md](notifications.md) | **알림이 닿았는지 어떻게 아나** | 안내를 Case 로 만들면 원가가 안내 수에 붙는다 |
| [diagrams.md](diagrams.md) | 어떤 그림이 있고 근거가 어디인가 | 계약이 바뀌면 조용히 낡는다 |
| [repository-map.md](repository-map.md) | 어느 저장소가 무엇을 소유하는가 | 소유가 겹치면 이중 장부 |

## 핵심 판정 기준 하나

> **도메인 지식이 필요하면 Pack, 도메인과 무관하면 Core.**

이 한 줄이 아키텍처 결정의 대부분을 처리한다. 상세는 [core-vs-team.md](core-vs-team.md).

## 구조 요약

`[실측]` v11 §5·§6.

```text
              A-COP Runtime (Core)  ← 도메인을 모른다
   Case · Controller · Registry · Port · 승인 경계 · 감사 · 평가
                        │
        ┌───────────────┴───────────────┐
   여행 도메인 Pack                 (다음 도메인)
   Activity · Booking Handoff       갈아 끼우는 자리
   Dining · Mobility
   Lodging/Flight (등록만)
```

**Team을 늘리는 일이 리팩토링이 되면 설계가 잘못된 것이다.**

★**도메인을 바꾸는 일도 마찬가지다.** 2026-09-08 에 커머스 → 여행으로 한 번 바꿨다. 무엇을 갈아 끼우고 무엇을 안 끼우는지는 [`cs/domain-swap.md`](../../final_project_cs/wiki/domain-swap.md) 가 정본이고, **어느 문서가 도메인에 묶여 있는지**는 [../governance/domain-axis.md](../governance/domain-axis.md) 가 정한다.

`[실측 2026-09-09]` **여행 Team 여섯이 `config/project.yaml` 에 붙었다**(`activity`·`booking_handoff`·`mobility`·`dining`·`lodging`·`flight`).

`[실측 2026-09-10 작업 트리]` **여행 분류 어휘와 두 축 라우팅이 이미 적용돼 있다** — `app/modules/travel_ops/feedback.py` 의 `INTENTS` 다섯이 슬러그이고 `ISSUE_CODES` 가 여행 17개이며, `app/application/controller.py:73,176` 이 `case_type_of(issue_code)` 와 `intent` 를 **둘 다** 넘긴다. **`[실측 2026-09-10 git]` 이 구현은 아직 커밋 전이다** — 되돌려지면 다시 막힌다.

## 이 영역의 불변식

코드 저장소에서 강제되는 것들. 전체 목록은 [`quality/invariants.md`](../../final_project_cs/wiki/quality/invariants.md) · [sample](../../final_project_sample/wiki/quality/index.md).

| ID | 불변식 | 판정 |
|---|---|---|
| `INV-CS-ARCH-001` | Core 계층은 도메인 어휘에 의존하지 않는다 | automated |
| `INV-CS-ARCH-002` | Core는 Team 내부를 import하지 않는다 | automated |
| `INV-CS-ACT-001` | Team은 side effect를 실행하지 않는다 | automated |

## 관련 결정

- [../decisions/D-002-graph-store-gate.md](../decisions/D-002-graph-store-gate.md) — Port를 두고 구현을 미룬다
- [../decisions/D-003-message-broker.md](../decisions/D-003-message-broker.md) — in-process queue
- [../decisions/D-001-payment-ownership.md](../decisions/D-001-payment-ownership.md) — 결제 경계

## 인접 영역

- [`final_project_cs/wiki/index.md`](../../final_project_cs/wiki/index.md) · [sample](../../final_project_sample/wiki/index.md) — 구현
- [../product/scope.md](../product/scope.md) — 범위가 아키텍처를 제약한다
- [stack-sources.md](stack-sources.md) — 기술 스택 공식 문서 URL. `curl` 로 HTTP 200 확인

