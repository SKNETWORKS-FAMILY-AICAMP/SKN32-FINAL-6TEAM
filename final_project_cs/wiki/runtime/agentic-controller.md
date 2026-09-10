---
type: concept
title: Agentic Controller
description: Case를 어느 Team으로 보낼지 정하고 재시도·재계획·WAIT/RESUME을 통제한다
status: draft
tags: [architecture, agent]
owners: [human:미배정]
domain: neutral
---

# Agentic Controller

> `[실측 2026-09-01]` **`app/core/case_runtime/`·`access_action/` 은 `__init__.py` 만 남은 빈 패키지다.**
> 2026-08-13 에 중첩 구조로 갔다가 **평면 구조로 되돌아왔다.** 정본은 `app/core/*.py` 다.
> 구조가 또 바뀔 수 있으므로 **작업 전에 실제 경로를 확인한다.**

`app/core/`

## 책임

Case의 다음 단계를 정한다. 네 가지다.

| 책임 | 무엇 |
|---|---|
| 라우팅 | capability로 Team을 찾아 Task를 만든다 |
| 재계획 | 결과를 보고 다음 Team을 정하거나 끝낸다 |
| WAIT/RESUME | 대기로 보내고 조건이 풀리면 재개한다 |
| 재시도 | 버전 충돌 시 다시 읽고 시도한다 |

## 경계

**Team을 직접 생성하지 않는다.** 반드시 Registry를 거친다.

직접 생성하면 Registry가 무의미해지고 Pack 교체가 불가능해진다. → [../teams/team-registry.md](../teams/team-registry.md)

**업무 판단을 하지 않는다.** "이 시각에 이 활동이 성립하나"는 Team이 정한다. Controller는 **누가 정할지**를 정한다.

VOC & Store Manager와 대비하면 명확하다.

| | Controller | VOC Team |
|---|---|---|
| 무엇 | 전역 조정 | 업무 판단 |
| 도메인 | 모른다 | 안다 |

## Team 간 위임은 Controller가 한다

Team은 다른 Team을 직접 호출하지 않는다. **위임 제안**을 `TeamResult`로 반환하고 Controller가 Task로 변환한다.

```text
VOC Team: "이건 Return 팀이 봐야 한다"
   ↓ TeamResult(next_action=handoff, handoff_capability=...)
Controller: capability로 Team 찾기 → 새 Task
```

계약이 강제한다. `handoff`면 `handoff_capability`가 있어야 한다.

## Port를 경유한다

`TeamExecutorPort`로 로컬과 원격을 같은 자리에서 바꾼다.

```
LocalTeamExecutor   app/core/remote_team/executor.py
A2ATeamExecutor     app/core/remote_team/a2a_executor.py
```

**Controller 코드는 어느 쪽인지 모른다.** 이게 A2A 경계를 지금 세운 이유다. 나중에 넣으면 Controller·Registry·계약·상태 매핑을 전부 다시 건드려야 한다.

→ [../../../wiki/research/a2a-adoption.md](../../../wiki/research/a2a-adoption.md)

## 재시도와 재시도 아닌 것

| 상황 | 대응 |
|---|---|
| 버전 충돌 (`StateConflict`) | **재시도.** 다시 읽고 진행 |
| 전이 오류 (`InvalidTransition`) | **버그.** 재시도해도 안 됨 |
| provider timeout | **재시도 안 함.** `unknown`으로 남김 |
| Team 실패 | `failed` → `escalated` |

**셋을 구분 못 하면 이중 실행이 나거나 무한 루프가 돈다.** → [conflict-retry.md](conflict-retry.md)

## 실행 유일성

동시에 최초 실행을 시도해도 active run은 정확히 1개다.

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-RT-011` | 동시 최초 실행은 active run을 정확히 1개 남긴다 | automated | `tests/integration/controller/test_active_run_uniqueness.py::test_two_simultaneous_first_start_runs_leave_exactly_one_active_run` |

`004_agent_runs_active_uniqueness.sql`이 DB 제약으로 받친다.

## 제안 차단

Team이 낸 제안이 근거 대조를 통과 못 하면 Controller가 막는다.

```
tests/integration/controller/test_proposal_guard_blocks.py
```

→ [../actions/evidence-check.md](../actions/evidence-check.md)

## 실패 사례

`[실측]` 이 프로젝트에서 실제로 잡힌 결함이다.

**`resuming → completed`를 상태 기계가 런타임 거부했다.** Controller가 `resumed` 단계를 건너뛰고 있었다.

**상태 기계가 진짜 결함을 잡은 사례다.** 전이표가 느슨했으면 조용히 통과했을 것이다.

## 관련 테스트

```
tests/integration/controller/
├─ test_controller_integration.py
├─ test_active_run_uniqueness.py
├─ test_proposal_guard_blocks.py
├─ test_provider_timeout_unknown.py
└─ test_response_review_wiring.py
```

## 관계

- [case-lifecycle.md](case-lifecycle.md) — 전이 규칙
- [shared-state.md](shared-state.md) — 상태 갱신
- [conflict-retry.md](conflict-retry.md) — 충돌 처리
- [message-broker.md](message-broker.md) — Task 배달
- [../teams/team-registry.md](../teams/team-registry.md) — Team 해석
- [../teams/team-contract/index.md](../teams/team-contract/index.md) — Task/Result 계약
