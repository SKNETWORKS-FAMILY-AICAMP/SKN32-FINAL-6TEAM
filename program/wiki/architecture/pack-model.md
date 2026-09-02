---
type: concept
title: Pack 모델
description: 하나의 Runtime 위에 도메인 Pack을 교체·확장하는 구조. Team 추가가 리팩토링이 되면 실패다
status: draft
tags: [architecture]
owners: [human:미배정]
---

# Pack 모델

## 구조

```text
              A-COP Runtime (Core)
   Case · Controller · Registry · Port · 승인 경계 · 감사 · 평가
                        │
            ┌───────────┴───────────┐
        CS Pack                 Commerce Ops Pack
   VOC & Store Manager      Procurement + Order & Payment
   Response Gen & Review    Fulfillment & Logistics
                            Return & Refund (Mock)
   (10주 착수 확정)          Catalog & Verification (A2A Remote)
                            (검증 쇼핑몰 일정에 따라 조정)
```

## 판정 기준

> **도메인 지식이 필요하면 Pack, 도메인과 무관하면 Core.**

상세는 [core-vs-team.md](core-vs-team.md).

## 왜 Pack인가

**하나의 Runtime을 여러 도메인에 팔기 위해서다.**

도입 기업이 자사 업무 Team을 추가해도 Core 코드가 안 바뀐다. 이게 [../product/positioning.md](../product/positioning.md)의 "기업이 자기 Team을 꽂아 쓰는 플랫폼"을 성립시킨다.

**상업적 주장이 구조적 성질에서 나온다.** 반대가 아니다.

## 교체가 성립하는 조건

| 조건 | 강제 방법 |
|---|---|
| Core가 Team 내부를 import하지 않는다 | `INV-CS-ARCH-002` |
| Core 계층에 도메인 어휘가 없다 | `INV-CS-ARCH-001` |
| Team은 Registry로만 해석된다 | Controller가 직접 생성 금지 |
| Team 계약이 고정돼 있다 | `TeamTask` / `TeamResult` |

**넷 중 하나라도 깨지면 Pack 교체가 불가능해진다.**

## ★ 확장 판단은 "만들 수 있는가"가 아니다

`[실측]` v8 §8-B

> Team이 늘면 golden set과 라우팅 평가 축이 함께 늘어난다. 확장 판단은 **"만들 수 있는가"가 아니라 "채점할 수 있는가"**로 한다.

**Team 하나를 더 만드는 비용보다 그 Team을 평가하는 비용이 크다.**

**Team 개수는 고정 상한이 아니다.** 확장 시 바뀌는 것은 Registry 레코드와 설정뿐이고 Core 코드는 안 바뀐다.

### 필요 Team과 착수 Team을 구분한다

| | |
|---|---|
| **기능상 필요** | Catalog & Verification · Procurement · Order & Payment · Fulfillment & Logistics · Return & Refund … |
| **착수** | 일정과 평가 여력이 허락하는 만큼 |

**몇 개를 만들 것인가는 아키텍처 제약이 아니라 일정 문제다.**

## Port 3종을 같은 원칙으로 둔다

`[실측]` 모듈형 Basement의 실행 경계. **2026-09-01 기준 셋 다 구현돼 있다.**

| Port | 무엇을 가른다 | 구현 위치 |
|---|---|---|
| `TeamExecutorPort` | **Team을 어디서 실행하는지**와 Controller 판단 | `app/core/remote_team/executor.py` · `a2a_executor.py` |
| `MessageBusPort` | 배달 계약과 구현 | `app/infrastructure/messaging/ports.py` |
| `GraphStorePort` | 관계 조회와 저장소 | `app/core/graph_retrieval/` · `app/infrastructure/graphstore/` |

`+ app/presentation/a2a/agent_card.py` — 우리가 A2A **서버**로서 발행하는 capability 문서

### MVP가 여기까지인 이유

**Port와 어댑터까지만 만들고 본체는 안 만든다.**

| 안 만드는 것 | 왜 |
|---|---|
| Graph 저장소 본체 | **"현재 규모에서는 JOIN이 맞다"** → [D-002](../decisions/D-002-graph-store-gate.md) |
| 완전한 A2A 서버 | **MVP는 경로 분리와 Port 확보다.** 개인 AI는 MCP(완료), 기업 Agent는 A2A(골격) |

**교체 지점만 확보하고 구현은 필요할 때 채운다.**

### `TeamExecutorPort`

```
LocalTeamExecutor   MessageBusPort 로 Task 발행 → 내부 Team Slot 이 처리
A2ATeamExecutor     A2A Adapter 로 Remote Agent System 에 위임
```

**Controller는 두 구현을 구분하지 않는다.** Registry의 `execution_type`을 보고 Executor를 고르는 일은 **Registry/Factory의 책임**이다.

**두 경로의 결과는 모두 `TeamResult`로 정규화되어 Shared State에 반영된다.**

## 성공 판정

> **Team을 늘리는 일이 리팩토링이 되면 설계가 잘못된 것이다.**

새 Team 추가에 필요한 것이 이것뿐이어야 한다.

```
1. Team 모듈 작성 (TeamManifest + 계약 구현)
2. Registry에 등록
```

Core 파일을 하나라도 고쳐야 하면 실패다.

## 현재 상태

`[실측]` `final_project_sample`과 `final_project_cs`에 Billing/Technical 2종이 구현돼 있고 **Core 격리 위반 0**이다.

이 둘은 10주 착수 로드맵에 없다. **Team-플러그인 아키텍처가 실제로 동작한다는 증거로만 남긴다.**

## Pack 범위 판단

| Pack | Team | 근거 |
|---|---|---|
| CS Pack | VOC & Store Manager, Response Generation & Review | 부트캠프 주제 자체. **확정** |
| Commerce Ops Pack | Procurement+Order, Fulfillment, Return(Mock), Catalog(A2A) | 검증 쇼핑몰 운영에 필요. 일정 따라 조정 |

**6명 팀 전체가 이 구성으로 고정된다는 뜻은 아니다.**

국외 배송·해외 구매대행의 실제 Live 연동은 Mock으로 남긴다.

## Vision

지금 안 하는 것. 재고·가격·발주·배송·정산의 전면 운영 자동화.

**Pack 구조가 이걸 나중에 가능하게 만드는 장치다.** 지금 만들지는 않는다.

## 관계

- [core-vs-team.md](core-vs-team.md) — 판정 기준 상세
- [../product/scope.md](../product/scope.md) — Pack별 착수 범위
- [../product/positioning.md](../product/positioning.md) — 상업적 근거
- [`cs/teams/index.md`](../../final_project_cs/wiki/teams/index.md) — 도메인 Team
- [`sample/wiki/teams/`](../../final_project_sample/wiki/teams/index.md) — **계약이 성립한다는 증거.** 예시 Team 이 여기 있다
