---
type: concept
title: Shared State
description: Customer Case의 공식 상태. 버전을 가지며 모든 갱신은 CAS를 거친다
status: draft
tags: [state, architecture]
owners: [human:미배정]
---

# Shared State

`app/core/case_runtime/case/`, `app/core/case_runtime/concurrency/`

## 책임

Customer Case의 **공식 상태**를 저장한다. 여러 Team이 같은 Case를 보고 갱신한다.

담는 것.

```
Case status · owner · evidence · decisions
open tasks · approval state · version
```

## 경계

**Team은 Shared State를 우회해 별도의 공식 상태를 만들 수 없다.**

Team이 자기 상태를 들고 있으면 이중 장부가 된다. 어느 쪽이 진짜인지 판정할 수 없어진다.

## 불변식

| ID | 불변식 | 판정 | 상태 |
|---|---|---|---|
| `INV-CS-RT-001` | Shared State가 Case의 단일 원천이다 | review | **자동화 필요** |
| `INV-CS-RT-002` | 모든 상태 변경은 version을 증가시킨다 | review | **자동화 필요** |
| `INV-CS-RT-003` | 동시 갱신은 CAS를 거친다 | review | **자동화 필요** |
| `INV-CS-RT-004` | 실패한 갱신은 부분 변경을 남기지 않는다 | review | **자동화 필요** |

`[미확보]` **넷 다 테스트로 강제되지 않는다.** 이 저장소 불변식 카탈로그의 가장 큰 구멍이다.

`tests/integration`에 관련 테스트가 있을 수 있으나 불변식 ID로 연결되지 않았다. → [../quality/test-map.md](../quality/test-map.md)

## 결정 — 낙관적 동시성

**전역 잠금이 아니라 CAS(Compare-And-Swap)를 쓴다.**

이유는 **독립적인 Agent Team이 동시에 동작할 수 있어야 하기 때문**이다. 전역 잠금을 걸면 Team 하나가 느릴 때 전체가 멈춘다.

대가는 충돌 처리를 직접 해야 한다는 것이다. → [conflict-retry.md](conflict-retry.md)

## 실패 사례 — 버전 충돌

```text
Team A: case_version=12 로 읽음
Team B: case_version=12 로 읽음

Team A commit → version=13  ✅
Team B commit → CONFLICT     ❌

Controller가 version=13 을 다시 읽고 재시도 또는 재계획
```

`StateConflict` 예외가 `app/core/contracts.py`에 정의돼 있다.

**충돌이 나면 부분 변경을 남기면 안 된다.** `INV-CS-RT-004`가 그것이고, 자동 판정이 없다.

## 저장

PostgreSQL이 단일 원천이다. `customer_cases` 테이블에 `version` 칸이 있다.

```
customer_cases → case_events   (aggregate_version으로 순서 보장)
```

`case_events`에 `UNIQUE(case_id, aggregate_version)` 제약이 있어 **같은 버전의 이벤트가 두 번 들어갈 수 없다.**

→ [../data/schema.md](../data/schema.md)

## 구현

```text
app/core/case_runtime/case/
app/core/case_runtime/concurrency/
app/core/transition.py       상태 전이 규칙 (232줄)
```

## 관계

- [case-lifecycle.md](case-lifecycle.md) — 어떤 상태를 지나는가
- [conflict-retry.md](conflict-retry.md) — 충돌 처리
- [agentic-controller.md](agentic-controller.md) — 갱신을 지시하는 쪽
- [../data/schema.md](../data/schema.md) — 저장 구조
- [../quality/invariants.md](../quality/invariants.md) — 불변식 전체
