---
type: concept
title: Shared State
description: Customer Case의 공식 상태. 버전을 가지며 모든 갱신은 CAS를 거친다
status: draft
tags: [state, architecture]
owners: [human:미배정]
---

# Shared State

> `[실측 2026-09-01]` **`app/core/case_runtime/`·`access_action/` 은 `__init__.py` 만 남은 빈 패키지다.**
> 2026-08-13 에 중첩 구조로 갔다가 **평면 구조로 되돌아왔다.** 정본은 `app/core/*.py` 다.
> 구조가 또 바뀔 수 있으므로 **작업 전에 실제 경로를 확인한다.**

`app/core/transition.py` · `app/domain/case.py`

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

이 문서가 말하는 네 성질은 **전부 자동 판정된다.** 어느 불변식이 어느 성질을 받치는지는 이렇다.

| 성질 | 받치는 불변식 | 판정 | 어디 |
|---|---|---|---|
| Shared State가 Case의 단일 원천이다 | `INV-CS-RT-001` 이벤트 재생은 결정적 · `INV-CS-RT-002` version은 이벤트 수와 같다 — projection이 이벤트에서 다시 나오므로 두 원천이 생길 수 없다 | automated | [../quality/invariants.md](../quality/invariants.md) |
| 모든 상태 변경은 version을 증가시킨다 | `INV-CS-RT-003` | automated | 동 |
| 동시 갱신은 CAS를 거친다 | `INV-CS-RT-009` 같은 version을 읽은 두 writer는 정확히 1건만 충돌 · `INV-CS-RT-011` 동시 최초 실행은 active run 1개 | automated | [conflict-retry.md](conflict-retry.md) |
| 실패한 갱신은 부분 변경을 남기지 않는다 | `INV-CS-RT-008` 거부된 쓰기는 Case를 바꾸지 않는다 · 예외 주입 시 `case_events`·`outbox` 둘 다 롤백(DoD-12 `test_transition_exception_rolls_back_event_and_outbox`) | automated | [conflict-retry.md](conflict-retry.md) · [../actions/outbox.md](../actions/outbox.md) |

### ★ [2026-09-06] 이 절이 틀려 있었다

`[실측]` 이 절은 위 네 성질에 **`INV-CS-RT-001`~`004`라는 ID를 붙이고 "넷 다 테스트로 강제되지 않는다 — 카탈로그의 가장 큰 구멍"**이라고 적고 있었다. 정본 [invariants.md](../quality/invariants.md)와 대조하니 **둘 다 틀렸다** — `RT-001`~`004`는 리듀서 결정성·version 규칙이고 넷 다 automated다. 같은 ID가 두 문서에서 다른 문장을 달고 있었다.

**[check_wiki.py](../../../wiki/governance/review-policy.md)가 못 잡는 종류다.** 검사기는 불변식 ID와 테스트의 연결만 보지, 같은 ID에 붙은 **문장이 문서마다 같은지**는 안 본다. ID를 인용할 땐 정본에서 복사해야 한다.

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

→ [../data/schema/index.md](../data/schema/index.md)

## 구현

```text
app/core/transition.py       transition_case() — projection UPDATE(version 가드) · case_events append
                             · outbox insert 를 한 함수에서, commit 은 호출자가 (232줄)
app/domain/case.py           apply_event — 순수 리듀서. transition_case() 와 replay_case() 가 같은 것을 쓴다
```

`[실측]` 두 경로가 **같은 리듀서**를 쓰는 게 단일 원천의 실체다. 각자 계산하면 조용히 어긋난다. → [DoD-03](../../docs/evidence/DoD-03_동시성_appendonly_replay.md)

## 관계

- [case-lifecycle.md](case-lifecycle.md) — 어떤 상태를 지나는가
- [conflict-retry.md](conflict-retry.md) — 충돌 처리
- [agentic-controller.md](agentic-controller.md) — 갱신을 지시하는 쪽
- [../data/schema/index.md](../data/schema/index.md) — 저장 구조
- [../quality/invariants.md](../quality/invariants.md) — 불변식 전체
