---
type: concept
title: 충돌과 재시도
description: 낙관적 동시성에서 버전 충돌을 어떻게 판정하고 되돌리는가. 충돌과 전이 오류는 다르다
status: draft
tags: [state, architecture]
owners: [human:미배정]
---

# 충돌과 재시도

`app/core/case_runtime/concurrency/` · `app/core/transition.py`

## 왜 낙관적 동시성인가

**전역 잠금을 쓰지 않는다.** 독립적인 Agent Team이 동시에 동작할 수 있어야 하기 때문이다.

전역 잠금을 걸면 Team 하나가 느릴 때 전체가 멈춘다.

대가는 **충돌을 직접 처리해야 한다**는 것이다.

## 충돌이 나는 방식

```text
Team A: case_version=12 로 읽음
Team B: case_version=12 로 읽음

Team A commit → version=13   ✅
Team B commit → CONFLICT      ❌

Controller가 version=13 을 다시 읽고 재시도 또는 재계획
```

`StateConflict` 예외가 `app/core/contracts.py`에 정의돼 있다.

## ★ 충돌과 전이 오류를 구분한다

이게 미묘하고 중요하다. `INV-CS-RT-010`이 강제한다.

| | 뜻 | 대응 |
|---|---|---|
| **충돌** | 남이 먼저 썼다 | **재시도** |
| **전이 오류** | 허용되지 않은 전이다 | **버그. 재시도해도 안 됨** |

같은 예외로 뭉뚱그리면 **Controller가 잘못 대응한다.** 버그를 무한 재시도하거나, 정상 충돌을 실패로 처리한다.

`[실측]` 테스트가 이걸 검사한다.

```
tests/integration/db/test_stale_write_conflict.py
  ::test_stale_write_on_an_advanced_case_is_a_conflict_not_a_transition_error
```

## 양방향으로 막는다

`[실측]` 낮은 버전만 막는 게 아니다.

| 상황 | 결과 | 불변식 |
|---|---|---|
| 현재보다 **낮은** version 쓰기 | 거부 | `INV-CS-RT-006` |
| 현재보다 **앞선** version 쓰기 | 거부 | `INV-CS-RT-007` |

**앞선 버전도 막는 이유**는 그게 계산 오류거나 다른 Case를 건드리는 것이기 때문이다. 조용히 받아들이면 이벤트 순서가 깨진다.

## 부분 변경을 남기지 않는다

`INV-CS-RT-008`. **거부된 쓰기는 Case를 전혀 바꾸지 않는다.**

```
tests/integration/db/test_stale_write_conflict.py
  ::test_a_rejected_stale_write_does_not_change_the_case
```

이게 안 지켜지면 충돌 후 상태가 어중간해져서 재시도해도 복구가 안 된다.

## 정확히 한 번만 충돌한다

`INV-CS-RT-009`. 같은 version을 읽은 두 writer 중 **정확히 하나만 성공하고 하나만 충돌한다.**

둘 다 성공하면 갱신이 유실되고, 둘 다 실패하면 진행이 멈춘다.

DB 수준에서 `case_events`의 `UNIQUE(case_id, aggregate_version)`가 이를 보장한다.

## 실행 유일성

`INV-CS-RT-011`. **동시에 최초 실행을 시도해도 active run은 정확히 1개다.**

```
tests/integration/controller/test_active_run_uniqueness.py
  ::test_two_simultaneous_first_start_runs_leave_exactly_one_active_run
```

마이그레이션 `004_agent_runs_active_uniqueness.sql`이 DB 제약으로 받친다.

## 불변식 전체

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-RT-006` | 현재보다 낮은 version 쓰기는 거부된다 | automated | `tests/integration/db/test_stale_write_conflict.py::test_writing_with_a_version_older_than_current_is_rejected` |
| `INV-CS-RT-007` | 앞선 version 쓰기도 거부된다 | automated | `tests/integration/db/test_stale_write_conflict.py::test_writing_with_a_version_ahead_of_current_is_rejected` |
| `INV-CS-RT-008` | 거부된 쓰기는 Case를 바꾸지 않는다 | automated | `tests/integration/db/test_stale_write_conflict.py::test_a_rejected_stale_write_does_not_change_the_case` |
| `INV-CS-RT-009` | 같은 version을 읽은 두 writer는 정확히 1건만 충돌한다 | automated | `tests/integration/db/test_stale_write_conflict.py::test_two_writers_that_read_the_same_version_produce_exactly_one_conflict` |
| `INV-CS-RT-010` | 진행된 Case의 stale 쓰기는 전이 오류가 아니라 충돌이다 | automated | `tests/integration/db/test_stale_write_conflict.py::test_stale_write_on_an_advanced_case_is_a_conflict_not_a_transition_error` |
| `INV-CS-RT-011` | 동시 최초 실행은 active run을 정확히 1개 남긴다 | automated | `tests/integration/controller/test_active_run_uniqueness.py::test_two_simultaneous_first_start_runs_leave_exactly_one_active_run` |

## 재시도가 아닌 것

**provider timeout은 재시도하지 않는다.** 성공했는지 모르기 때문이다.

`unknown`으로 남기고 사람이 판단한다. → [../actions/idempotency.md](../actions/idempotency.md)

| | 재시도 | 이유 |
|---|---|---|
| 버전 충돌 | **한다** | 우리 쪽 상태 문제. 다시 읽으면 된다 |
| provider timeout | **안 한다** | 바깥에서 이미 실행됐을 수 있다 |

**둘을 섞으면 이중 결제가 난다.**

## 오류 메시지 주의

`[실측]` 이 프로젝트에서 실제로 겪은 문제다.

> 오류 메시지가 사실을 잘못 전하지 않게 한다. **상태 충돌을 "LLM 실패"로 보고하면 한참 헤맨다.**

충돌은 정상 동작이다. 실패로 보고하면 있지도 않은 버그를 찾게 된다.

## 관계

- [shared-state.md](shared-state.md) — 버전과 CAS
- [case-lifecycle.md](case-lifecycle.md) — 전이 규칙
- [agentic-controller.md](agentic-controller.md) — 재시도·재계획 판단
- [../actions/idempotency.md](../actions/idempotency.md) — 실행 쪽 중복 방지
