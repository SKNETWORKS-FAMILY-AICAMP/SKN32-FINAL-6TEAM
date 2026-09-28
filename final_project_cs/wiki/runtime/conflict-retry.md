---
type: concept
title: 충돌과 재시도
description: 낙관적 동시성에서 버전 충돌을 어떻게 판정하고 되돌리는가. 충돌과 전이 오류는 다르다
status: draft
tags: [state, architecture]
owners: [human:미배정]
domain: neutral
---

# 충돌과 재시도

> `[실측 2026-09-01]` **`app/core/case_runtime/`·`access_action/` 은 `__init__.py` 만 남은 빈 패키지다.**
> 2026-08-13 에 중첩 구조로 갔다가 **평면 구조로 되돌아왔다.** 정본은 `app/core/*.py` 다.
> 구조가 또 바뀔 수 있으므로 **작업 전에 실제 경로를 확인한다.**

`app/core/transition.py` · `app/core/contracts.py`

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

### ★ [2026-09-06] 진 쪽이 무엇으로 지는지는 타이밍에 달렸다

`[실측]` [회귀테스트 검증 로그](../records/evidence/2026-08-31_테스트_사각지대_회귀테스트_검증.md) §4. Controller 통합 테스트 `test_same_expected_version_has_one_success_and_one_state_conflict`에 이 성질을 깨는 결함을 심고 **단독으로 5회** 돌렸다.

```
결함 적용 + 단독 5회: passed · passed · passed · passed · FAILED
```

**결함이 있는데 4회는 통과했다.** 원인은 잡혔다 — 진 쪽이 이긴 쪽의 커밋 **뒤에** projection을 읽으면 상태가 이미 `running`이라 `running --routed-->`가 전이표에 없어 `StateConflict`가 아니라 **`InvalidTransition`**이 난다. 테스트의 `except StateConflict`에 안 걸려 스레드 밖으로 나간다.

**"정확히 한 번만 충돌한다"는 지켜진다. 다만 그 충돌이 어떤 예외로 보이는지는 읽는 시점에 따라 다르다.** 재시도 로직이 `StateConflict`만 잡으면 이 경우를 놓친다.

★`[실측 2026-09-10]` **지금은 이 갈림이 없다.** `app/core/transition.py` 가 **리듀서를 부르기 전에 version 을 먼저 비교**한다(`if current.version != expected_version`). 진 쪽이 이긴 쪽 커밋 뒤에 읽어도 **version 이 이미 다르므로 `StateConflict` 가 먼저 난다** — `InvalidTransition` 까지 가지 않는다. **위 두 문단은 그 선검사가 들어가기 전 서술이다.**

`[미확보]` 근본 원인은 `wiki/records/reports/debugs/2026-08-31_버전대조_가드_중복.md` §5에 있다. **고쳐졌는지는 이 wiki에서 확인하지 않았다.**

## 실행 유일성

`INV-CS-RT-011`. **동시에 최초 실행을 시도해도 active run은 정확히 1개다.**

```
tests/integration/controller/test_active_run_uniqueness.py
  ::test_two_simultaneous_first_start_runs_leave_exactly_one_active_run
```

마이그레이션 `004_agent_runs_active_uniqueness.sql`이 DB 제약으로 받친다.

### ★ [2026-09-05] 이 제약이 왜 필요했는가 — `SELECT FOR UPDATE`만으로는 안 됐다

`[실측]` [DoD-03](../records/evidence/DoD-03_동시성_appendonly_replay.md). **애초 구현은 앱 레벨 `SELECT ... FOR UPDATE`로 활성 run 존재를 확인하는 방식이었다.**

**이 락은 이미 존재하는 행만 잠근다.** 같은 Case에 활성 run이 **0개**인 상태에서 두 요청이 동시에 `start_run()`을 호출하면, 잠글 행 자체가 없으니 **둘 다 insert에 성공할 수 있었다** — 전형적인 확인-후-삽입(TOCTOU) 레이스다.

**원래 이 문서의 "한계" 절이 정확히 이 결함을 놓치는 지점이라고 스스로 적어 뒀다** — "실제 다중 프로세스 동시성 부하 시험은 하지 않았다." 실제로는 부하가 아니라 **순수하게 동시에 두 번 부르기만 해도** 재현됐다.

`final_project_sample`과 대조하다 이 가능성을 발견했고, `ThreadPoolExecutor`로 진짜 동시 두 스레드가 같은 Case에서 `start_run()`을 부르는 재현 테스트를 **먼저** 추가해 레이스를 확인한 뒤, 앱 레벨 락 대신 DB 레벨 partial unique index로 옮겼다 — `UniqueViolation`을 `ActiveRunError`로 잡는다.

**교훈 — 앱 레벨 락은 "이미 있는 것"만 지킨다. "아직 없는 것"의 유일성은 DB 제약이 있어야 한다.**

## 불변식 전체

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-RT-006` | 현재보다 낮은 version 쓰기는 거부된다 | automated | `tests/integration/db/test_stale_write_conflict.py::test_writing_with_a_version_older_than_current_is_rejected` |
| `INV-CS-RT-007` | 앞선 version 쓰기도 거부된다 | automated | `tests/integration/db/test_stale_write_conflict.py::test_writing_with_a_version_ahead_of_current_is_rejected` |
| `INV-CS-RT-008` | 거부된 쓰기는 Case를 바꾸지 않는다 | automated | `tests/integration/db/test_stale_write_conflict.py::test_a_rejected_stale_write_does_not_change_the_case` |
| `INV-CS-RT-009` | 같은 version을 읽은 두 writer는 정확히 1건만 충돌한다 | automated | `tests/integration/db/test_stale_write_conflict.py::test_two_writers_that_read_the_same_version_produce_exactly_one_conflict` |
| `INV-CS-RT-010` | 진행된 Case의 stale 쓰기는 전이 오류가 아니라 충돌이다 | automated | `tests/integration/db/test_stale_write_conflict.py::test_stale_write_on_an_advanced_case_is_a_conflict_not_a_transition_error` |
| `INV-CS-RT-011` | 동시 최초 실행은 active run을 정확히 1개 남긴다 | automated | `tests/integration/controller/test_active_run_uniqueness.py::test_two_simultaneous_first_start_runs_leave_exactly_one_active_run` |

## CAS 구현

`[실측]` v8 §20. **한 문장으로 끝난다.**

```sql
UPDATE customer_cases
SET status=:status, state_json=:state_json, version=version+1, updated_at=now()
WHERE tenant_id=:tenant_id AND case_id=:case_id AND version=:expected_version
RETURNING version;
```

**`RETURNING`이 없으면 충돌이다.** 별도 조회가 필요 없다.

`transition_case(case_id, expected_version, event_type, payload, actor)`가 유일한 진입점이고, **transaction 안에서** 이벤트 추가와 projection 갱신을 함께 한다.

## worker claim은 `FOR UPDATE SKIP LOCKED`

`[실측]` outbox worker가 여러 개일 때.

**잠긴 행을 기다리지 않고 건너뛴다.** 기다리면 worker 하나가 느릴 때 전체가 막힌다.

## ★ Loop guard 4종

`[실측]` v8 §20. **Case당 상한이다.**

| 대상 | 상한 |
|---|---|
| graph step | **12** |
| Team task | **6** |
| tool call | **12** |
| 동일 signature 반복 | **2회** |

**마지막 줄이 특이하다.** 횟수가 아니라 **같은 호출을 반복하는 것**을 잡는다. 무한 루프는 보통 같은 걸 계속 부르는 모양으로 나타난다.

Team의 `max_steps`(4~6)는 이것과 별개로 Team 안의 상한이다.

## Action 상태 기계

```
proposed → pending_approval → approved → executing → succeeded
                                                   ↘ failed | unknown | cancelled
```

**`unknown`이 종단에 있다.** 실패가 아니라 **모르는 상태**다.

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
