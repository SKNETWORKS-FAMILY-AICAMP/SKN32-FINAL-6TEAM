---
type: guide
title: Architecture
description: 시스템 경계와 저장소 관계. 구현 세부는 각 코드 저장소 wiki에 있고 여기는 경계만 다룬다
status: draft
---

# Architecture

**여기는 경계만 다룬다.** 구현은 각 코드 저장소의 `wiki/`에 있다.

여기 있는 것과 저기 있는 것을 가르는 기준은 [../governance/structure-guide.md](../governance/structure-guide.md) §2에 있다. 요약하면 **"무엇이 이 문서를 틀리게 만드는가"**로 판정한다.

## 읽기 순서

1. [system-context.md](system-context.md) — 시스템 경계와 외부 행위자
2. [core-vs-team.md](core-vs-team.md) — 무엇이 Core에 남고 무엇이 Team으로 가는가
3. [pack-model.md](pack-model.md) — Runtime + CS Pack + Commerce Ops Pack
4. [repository-map.md](repository-map.md) — 저장소 6개의 역할과 관계

## 각 문서

| 문서 | 답하는 질문 | 건드리면 위험한 것 |
|---|---|---|
| [system-context.md](system-context.md) | 누가 우리 시스템과 대화하는가 | 외부 경계를 늘리면 인증·감사 전부 영향 |
| [core-vs-team.md](core-vs-team.md) | 새 기능이 Core인가 Team인가 | 잘못 판정하면 Team 추가가 리팩토링이 된다 |
| [pack-model.md](pack-model.md) | Pack을 어떻게 교체하는가 | Core가 Pack을 import하면 교체 불가 |
| [repository-map.md](repository-map.md) | 어느 저장소가 무엇을 소유하는가 | 소유가 겹치면 이중 장부 |

## 핵심 판정 기준 하나

> **도메인 지식이 필요하면 Pack, 도메인과 무관하면 Core.**

이 한 줄이 아키텍처 결정의 대부분을 처리한다. 상세는 [core-vs-team.md](core-vs-team.md).

## 구조 요약

```text
              A-COP Runtime (Core)
   Case · Controller · Registry · Port · 승인 경계 · 감사 · 평가
                        │
            ┌───────────┴───────────┐
        CS Pack                 Commerce Ops Pack
   VOC · Response Review     Procurement+Order · Fulfillment
   (10주 착수 확정)           Return(Mock) · Catalog(A2A Remote)
```

**Team을 늘리는 일이 리팩토링이 되면 설계가 잘못된 것이다.**

## 이 영역의 불변식

코드 저장소에서 강제되는 것들. 전체 목록은 [`quality/invariants.md`](../../final_project_cs/wiki/quality/invariants.md).

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

- [`final_project_cs/wiki/index.md`](../../final_project_cs/wiki/index.md) — 구현
- [../product/scope.md](../product/scope.md) — 범위가 아키텍처를 제약한다
