---
type: guide
title: final_project_cs 시작하기
description: A-COP 릴리스 대상 저장소의 구조와 작업별 진입점
status: draft
domain: neutral
---

# final_project_cs 시작하기

> `[실측 2026-09-01]` **`app/core/case_runtime/`·`access_action/` 은 `__init__.py` 만 남은 빈 패키지다.**
> 2026-08-13 에 중첩 구조로 갔다가 **평면 구조로 되돌아왔다.** 정본은 `app/core/*.py` 다.
> 구조가 또 바뀔 수 있으므로 **작업 전에 실제 경로를 확인한다.**

**A-COP의 릴리스 대상이다.** Core(실행 기반)와 Team(업무 모듈)이 Registry로 분리돼 있다.

제품이 무엇인지는 [중앙 허브](../../wiki/quickstart.md)에 있다. 여기는 **코드를 고칠 때** 보는 곳이다.

## 한 장으로 보는 구조

```text
외부 요청 (REST / MCP / A2A)
  ↓  external/
Agent Gateway  ← Trust Boundary
  ↓
Agentic Controller ──── Team Registry ──── Agent Team
  │   runtime/            teams/              teams/
  │                                             │
  ├── Context Broker ─── 읽기                    │ ActionProposal
  │     context/                                 ↓
  └── Shared State ←──────────────────── Action Layer
        runtime/                            actions/
                                               │ 승인
                                               ↓
                                            Outbox
```

## 코드와 문서의 대응

| 문서 | 코드 |
|---|---|
| [runtime/](runtime/index.md) | `app/core/` (평면) |
| [actions/](actions/index.md) | `app/core/` (평면) |
| [teams/](teams/index.md) | `app/modules/travel_ops/` — `[실측 2026-09-10]` 작업 트리 기준. git 에는 아직 `customer_ops/` 다(삭제·추가가 커밋 전) |
| [context/](context/index.md) | `app/core/context.py`, `app/infrastructure/rag/` |
| [external/](external/index.md) | `app/presentation/` |
| [data/](data/index.md) | `app/infrastructure/db/` |
| [quality/](quality/index.md) | `tests/` |

## 작업별 진입점

| 하려는 일 | 여기부터 | 반드시 같이 읽을 것 |
|---|---|---|
| Team 추가 | [teams/team-contract/index.md](teams/team-contract/index.md) | [teams/team-boundary.md](teams/team-boundary.md) |
| Team 로직 수정 | 해당 `teams/<team>.md` | [actions/action-proposal.md](actions/action-proposal.md) |
| 읽기 자료 바꾸기 | [context/context-broker.md](context/context-broker.md) | [context/context-budget.md](context/context-budget.md) |
| 쓰기 동작 추가 | [actions/tool-gateway.md](actions/tool-gateway.md) | [actions/idempotency.md](actions/idempotency.md), [actions/approval.md](actions/approval.md) |
| Case 상태 건드리기 | [runtime/shared-state.md](runtime/shared-state.md) | [runtime/conflict-retry.md](runtime/conflict-retry.md) |
| 스키마 변경 | [data/schema/index.md](data/schema/index.md) | [data/migrations.md](data/migrations.md) |
| API 추가 | [external/rest-api.md](external/rest-api.md) | [external/auth-boundary.md](external/auth-boundary.md) |
| 평가 돌리기 | [quality/eval-harness.md](quality/eval-harness.md) | |

## ★ 고치기 전에 반드시 확인

[quality/invariants.md](quality/invariants.md) — **깨면 안 되는 규칙 목록**이다. 대부분 테스트가 강제하므로 어기면 CI가 실패한다.

특히 자주 걸리는 것 넷.

| 규칙 | 어기면 |
|---|---|
| Team은 side effect를 실행하지 않는다. `ActionProposal`만 반환한다 | 승인 경계 우회 |
| Team은 read 도구를 직접 호출하지 않는다. Context Broker가 넣어준다 — `[실측 2026-09-10 작업 트리]` **여행 코드는 `_read()` 로 직접 부른다**(허용·예산은 `ReadToolbox.call()` 이 강제). 원칙과 코드가 갈라져 있다 → [teams/team-boundary.md](teams/team-boundary.md) §2 | 컨텍스트 예산 붕괴 |
| Core는 Team 내부를 import하지 않는다 | Pack 교체 불가 |
| Core 계층에 도메인 어휘를 넣지 않는다 | `test_basement_is_domain_free` 실패 |

## 자주 쓰는 명령

```bash
pytest tests/architecture
```

```bash
pytest tests/contract
```

```bash
# [2026-09-10] eval/run.py 가 없다 — 이 명령은 돌지 않는다. 러너는 eval/runners/{baseline_a,baseline_b,proposed}.py 이고
#   정답이 모델 입력에 들어가는 문제로 여행 평가 전에 고쳐야 한다(루트 wiki/evaluation/protocol.md)
python -m eval.run --arm Proposed
```

## 테스트 현황

`[실측]` 2026-09-01 기준 70개 파일

| 분류 | 파일 수 | 무엇을 |
|---|---|---|
| `tests/unit` | 28 | 단위 |
| `tests/integration` | 22 | 통합 |
| `tests/contract` | 7 | 계약·격리 |
| `tests/e2e` | 4 | 종단 |
| `tests/security` | 4 | 인증·스코프·PII |
| `tests/architecture` | 2 | **계층 경계** |

## 다음

[index.md](index.md)가 9개 영역 지도다.
