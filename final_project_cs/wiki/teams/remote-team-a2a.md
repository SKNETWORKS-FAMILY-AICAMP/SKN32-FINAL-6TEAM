---
type: concept
title: Remote Team 실행
description: 원격 Team을 로컬과 같은 자리에서 실행한다. Controller는 어느 쪽인지 모른다
status: draft
tags: [agent, architecture]
owners: [human:미배정]
domain: neutral
---

# Remote Team 실행

`app/core/remote_team/`

## 두 실행기

```
app/core/remote_team/
├─ executor.py        LocalTeamExecutor
└─ a2a_executor.py    A2ATeamExecutor
```

**같은 인터페이스다.**

```python
async def execute(self, task: TeamTask) -> TeamResult
```

**Controller는 어느 쪽인지 모른다.** `TeamExecutorPort`가 교체점이다.

## 왜 지금 경계를 세웠나

`GraphStorePort`와 다르다.

| | A2A | GraphStorePort |
|---|---|---|
| 나중에 넣으면 | Controller·Registry·계약·상태 매핑을 **전부** 다시 건드림 | Port만 두면 구현을 미룰 수 있음 |
| 왜 | **실행 경로가 코드 전반에 퍼진다** | 저장소 교체 문제 |
| 판단 | 지금 세운다 | 나중 |

→ [../../../wiki/decisions/D-002-graph-store-gate.md](../../../wiki/decisions/D-002-graph-store-gate.md)

## 마감과 취소

`[실측]` `A2ATeamExecutor`의 안전장치.

```python
_call_within_deadline    TeamTask.deadline_at 안에서만 기다린다
_cancel_best_effort      마감을 넘기면 원격에 취소를 시도한다
_failed                  실패를 TeamResult 로 정규화
```

**`best_effort`라고 이름에 적혀 있다.** 취소가 보장되지 않는다.

그래서 **원격 결과를 나중에 받아도 안전해야 한다.** idempotency가 여기서도 필요하다.

## 결과 정규화

원격이 무엇을 주든 `TeamResult`로 바꾼다.

```
outcome     = "waiting"
next_action = "escalate"
wait_reason = "external_callback"
   ↓
Case → waiting_external
```

**A2A Task 생명주기와 Case 상태를 매핑한다.**

`[미확보]` **위 `Case → waiting_external`은 설계다.** Controller가 실제로 Case를 `waiting_external`에 두고 원격 완료로 resume하는 종단은 아직 관측된 적이 없다 — [DoD-26](../records/evidence/DoD-26_A2A_Catalog_왕복.md)이 확인한 왕복은 Executor·Transport 층까지다. → [../external/a2a-protocol.md](../external/a2a-protocol.md)

구조만 보면 우리 Case가 A2A Task에 대응한다. `waiting_approval`·`waiting_input` 같은 장기 상태를 갖기 때문이다.

## 추가 입력 왕복

원격이 중간에 정보를 더 요구할 수 있다.

```
원격: package_unit 이 필요하다
  ↓
Controller: 내부 Team 또는 운영 UI에 질문 전달   # [2026-09-10] 쇼핑몰 판에서는 Catalog Team 이었다. 여행 판 원격은 Place Verification
  ↓
답을 받아 A2A Task 에 resume 입력
```

**Team이 직접 왕복하지 않는다.** Controller가 한다.

## Artifact를 대조한다

완료 시 `verification_report`와 `evidence_manifest`를 반환한다.

**근거 식별자를 Context/DB와 대조한 뒤에** Shared State에 저장한다.

**우리 Team 제안을 대조하는 것과 같은 규칙이다.** 원격이라고 믿지 않는다.

→ [../actions/evidence-check.md](../actions/evidence-check.md)

## 현재 범위

| | 상태 |
|---|---|
| Port 경계 | **완료** |
| Agent Card | 완료 |
| 더미 Remote Agent 왕복 | 완료 (`tests/integration/a2a/test_travel_remote_round_trip.py`, 7건 — `[정정 2026-09-10]` 파일 이름이 `test_remote_round_trip.py` 로 적혀 있었다. 대상 원격도 Place Verification 으로 바뀌었다) |
| 실제 외부 Agent | `[미확보]` |

MVP 범위는 **Remote A2A PoC 1개**다. 더미는 A-COP 본체가 아니라 왕복 검증용 상대역이다.

## 후보 Team

[catalog-verification.md](../records/legacy/teams/catalog-verification.md)가 A2A Remote 후보다. 장기 실행·추가 입력·Artifact 세 조건을 만족한다.

## 관계

- [team-contract.md](team-contract/index.md) — `TeamTask` / `TeamResult`
- [catalog-verification.md](../records/legacy/teams/catalog-verification.md) — 후보 Team
- [../external/a2a-protocol.md](../external/a2a-protocol.md) — 프로토콜
- [../runtime/agentic-controller.md](../runtime/agentic-controller.md) — Port를 쓰는 쪽
