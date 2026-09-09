---
type: concept
title: Core 8개 구성요소
description: Basement 가 무엇으로 이루어져 있고 각각 무엇을 책임지는가
status: draft
tags: [architecture]
owners: [human:미배정]
domain: travel
---

# Core 8개 구성요소

`[실측]` v8 §8·§8-A에서 이관. **여덟 구성요소 자체는 v10 이 승계했다** — v10 §0-2 가 "Controller · TeamExecutorPort · Registry 승계", §6 이 동시성·idempotency·감사를 그대로 둔다.

**Core는 도메인을 모른다.** 여기 있는 것 중 어느 것도 "환불"이나 "액티비티 예약"을 알지 않는다. **도메인이 커머스에서 여행으로 바뀌어도 이 여덟은 안 바뀐다** — 2026-09-08 판올림에서 실제로 안 바뀌었다.

★**단 두 곳은 내용물이 바뀐다.** 기제가 아니라 적재분이다(v10 §5-A).

| 구성요소 | 기제 | 적재분 |
|---|---|---|
| 4. Context Broker | 예산·절삭·`degraded`/`omissions` — **안 바뀐다** | 주문·배송 정보 → **여행 상태**(최신 일정·잠긴 예약·필수 조건·다음 확인 시점) |
| 7. Tool / Action Layer | 권한·idempotency·승인·감사 — **안 바뀐다** | 주문/배송/환불 Action → **장소·운영 조회 / 이동 시간 조회 / 기상 조회** |

## 여덟

| # | 구성요소 | 한 줄 |
|---|---|---|
| 1 | **Agent Gateway** | 외부 요청이 들어오는 **Trust Boundary** |
| 2 | **Customer Case Layer** | 메시지 하나를 **장기 실행 가능한 업무 Case**로 바꾼다 |
| 3 | **Team Registry / Contract** | capability에 맞는 Team을 찾고 **교체 가능성을 보장** |
| 4 | **Context Broker** | 필요한 자료를 **선택·조합·정규화·압축** |
| 5 | **Message Broker** | 판단하지 않고 **전달만** |
| 6 | **Shared State** | 여러 Team이 이어서 처리하는 **공식 단일 상태** |
| 7 | **Tool / Action Layer** | Agent가 DB를 직접 안 고치게 **통제** |
| 8 | **Agentic Controller** | 라우팅·재계획·WAIT/RESUME·완료 판단 |

## 1. Agent Gateway

```
OAuth Access Token 검증 · user/client 식별 · Scope 검사
요청 위험도 확인 · 승인된 요청만 Case Layer 로
```

→ [`auth-boundary.md`](../../final_project_cs/wiki/external/auth-boundary.md) · [sample](../../final_project_sample/wiki/composer/auth-scope.md)

## 2. Customer Case Layer

한 번의 메시지를 **업무 Case**로 변환한다.

```
case_id · status/owner · event/history
approval state · resume/checkpoint · version
```

→ [`case-lifecycle.md`](../../final_project_cs/wiki/runtime/case-lifecycle.md) · [sample](../../final_project_sample/wiki/runtime/case-lifecycle.md)

## 3. Team Registry / Team Contract

| | 무엇 |
|---|---|
| Registry | `team_id`·capabilities·version·활성 상태·scope 관리 |
| Contract | 표준 입출력 규칙 |

**Core는 Team 내부 구현을 직접 알지 않는다.**

→ [`team-registry.md`](../../final_project_cs/wiki/teams/team-registry.md) · [sample](../../final_project_sample/wiki/teams/team-registry.md)

## 4. Context Broker

```
RAG/Knowledge · DB Current State · Case History
Memory · Team별 Knowledge Scope
```

→ [`context-broker.md`](../../final_project_cs/wiki/context/context-broker.md) · [sample](../../final_project_sample/wiki/runtime/context-pack.md)

## 5. Message Broker

**책임이 두 계층으로 갈린다.** `[실측]` v8 §8-A

| 계층 | 책임 |
|---|---|
| **Application / Coordination** | Agentic Controller, Top-Level LangGraph, Routing, Replan, WAIT/RESUME, Task/Event Contract, **MessageBus Port** |
| **Infrastructure** | Redis / Redis Streams / RabbitMQ **Adapter** |

**핵심 규칙 한 줄.**

```
Controller 는 redis.xadd(...) 를 직접 호출하지 않는다
message_bus.publish(task) 를 호출한다
```

**Broker는 Team 선택이나 실행 순서를 판단하지 않는다.** 큐·재시도·이벤트 전달만 한다.

`[실측]` **Message Broker는 Agent Team 전용 부속이 아니다.** Coordination이 사용하는 컴포넌트다. 이 구분이 없으면 Team이 브로커를 직접 잡게 된다.

MVP는 in-process queue다. → [D-003](../decisions/D-003-message-broker.md)

## 6. Shared State

```
evidence · decisions · open_tasks
owner · status · version · approval state
```

### ★ Memory와 다르다

| | 무엇 |
|---|---|
| **Shared State** | **현재 Case의 공식 상태** |
| Memory | 과거 경험·지식 |

**섞으면 안 된다.** Team별 Episodic Memory는 Shared State가 아니다.

→ [`shared-state.md`](../../final_project_cs/wiki/runtime/shared-state.md) · [sample](../../final_project_sample/wiki/runtime/shared-state.md)

## 7. Tool / Action Layer

**Agent가 DB나 외부 시스템을 직접 수정하지 않는다.** Business Capability API를 통한다.

```
Tool 권한/Scope · Idempotency · Human Approval 여부
Audit Log · 실제 외부 side effect 실행
```

→ [`actions/index.md`](../../final_project_cs/wiki/actions/index.md) · [sample](../../final_project_sample/wiki/runtime/idempotency.md)

## 8. Agentic Controller

```
Capability 기반 Team routing · WAIT/RESUME · Replan/Retry
Human Approval · 다른 Team handoff · 완료/종료 판단
```

**Top-Level LangGraph가 이 계층에 있다.** 각 Agent Team은 별도 Subgraph를 가질 수 있다.

→ [`agentic-controller.md`](../../final_project_cs/wiki/runtime/agentic-controller.md) · [sample](../../final_project_sample/wiki/runtime/agentic-controller.md)

## 두 Broker를 헷갈리지 않는다

이름이 비슷해서 자주 섞인다.

| | Message Broker | Context Broker |
|---|---|---|
| 무엇을 | Task·Event **전달** | 자료 **조합** |
| 방향 | Controller → Worker | 저장소 → Team |
| 판단 | **안 한다** | 예산 안에서 선택한다 |
| Port | `MessageBusPort` | — |

## 관계

- [core-vs-team.md](core-vs-team.md) — 무엇이 Core이고 무엇이 Team인가
- [system-context.md](system-context.md) — 바깥 경계
- [concurrency.md](concurrency.md) — 경합 처리 책임
- [`final_project_cs/wiki/index.md`](../../final_project_cs/wiki/index.md) · [sample](../../final_project_sample/wiki/index.md) — 각 구성요소의 구현
