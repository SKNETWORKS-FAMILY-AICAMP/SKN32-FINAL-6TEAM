---
type: guide
title: Context
description: Team이 필요한 자료를 모아 주는 읽기 경로. Team은 직접 읽지 않는다
status: draft
---

# Context

`app/core/case_runtime/context/`, `app/infrastructure/rag/`

**Team은 read 도구를 직접 호출하지 않는다.** Context Broker가 `required_context`에 따라 읽어서 `ContextPack`으로 만들어 준다.

## 왜 이렇게 하는가

**읽기 예산을 Core가 통제하기 위해서다.**

Team이 직접 읽으면 컨텍스트가 무한정 커진다. 그러면 두 가지가 터진다.

| 문제 | 실제로 터진 사례 |
|---|---|
| 비용 | `[실측]` 건당 입력 8,968 토큰. 늘면 그대로 비용 |
| 메모리 | `[실측]` 12GB VRAM에서 10,670 토큰 학습이 OOM |

두 번째가 실제로 프로젝트를 막았다. → [../../../program/wiki/business/infrastructure-cost.md](../../../wiki/business/infrastructure-cost.md)

## 읽기 순서

1. [context-broker.md](context-broker.md) — `required_context` → `ContextPack`
2. [context-budget.md](context-budget.md) — 예산과 절단 규칙
3. [rag-retrieval.md](rag-retrieval.md) — 지식 검색
4. [memory.md](memory.md) — 이력

## 각 문서

| 문서 | 답하는 질문 |
|---|---|
| [context-broker.md](context-broker.md) | 무엇을 어떤 순서로 모으는가 |
| [context-budget.md](context-budget.md) | 예산을 넘으면 무엇을 자르는가 |
| [rag-retrieval.md](rag-retrieval.md) | 지식 문서를 어떻게 찾는가 |
| [memory.md](memory.md) | 과거 이력을 어떻게 쓰는가 |

## 흐름

```text
Team이 required_context 선언
   ↓
Context Broker
   ├─ read 도구 호출        tool-gateway 경유
   ├─ RAG 검색              rag-retrieval.md
   ├─ Memory 조회           memory.md
   └─ 예산 안에서 조합       context-budget.md
   ↓
ContextPack  →  Team
   ↓
부족하면 Team이 need_more_context 반환
   ↓
Controller가 추가 요청
```

## ★ 예산이 실제로 문제를 일으킨 사례

`[실측]` 학습 데이터 수확 스크립트가 `ContextBroker.build()`를 안 거치고 `team_result.evidence`를 그대로 썼다.

그 결과 **정책 청크가 두 번 중복**됐다 — 개별 policy evidence 8개 + 그걸 통째로 품은 병합 evidence 1개.

```
중앙값 10,670 토큰 → 12GB VRAM OOM
evidence 예산 400자로 낮춰서야 완주 (중앙값 ≈1,600 토큰)
```

**프로덕션은 Broker가 예산 안에서 조합하므로 안전하다.** 문제는 Broker를 우회한 스크립트였다.

교훈은 **Broker 우회 경로를 만들지 말 것**이다.

## 인접 영역

- [../teams/index.md](../teams/index.md) — ContextPack을 받는 쪽
- [../runtime/agentic-controller.md](../runtime/agentic-controller.md) — `need_more_context`를 처리하는 쪽
- [../actions/tool-gateway.md](../actions/tool-gateway.md) — read 도구 실행
- [../data/index.md](../data/index.md) — 원본 데이터
