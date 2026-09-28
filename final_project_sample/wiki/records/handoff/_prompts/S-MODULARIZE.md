# 구현 지시 — 모듈화 구조 이행 (A2A / Graph Port 신설 포함)

## 0. 계약

★**`wiki/records/handoff/07_모듈화_구조.md` 를 먼저 읽어라. 그것이 이 작업의 계약이다.**
출처는 `../A-COP_브리핑_A2A_Graph반영_최종.html` §5(폴더 구조) · §6(모듈형 Basement 4축)이다.
같이 읽을 것: `../A-COP_구현계획서_A2A_Graph반영.md` §9-C(A2A) · §9-D(Graph).
**두 계획서 모두 읽기 전용. 수정 금지.**

현재 상태: **116 passed, 0 failed, skipped 0**. 이것이 기준선이다.

## 1. 소유 범위

```
app/**            (구조 이동 전체)
tests/**          (import 경로 갱신)
wiki/records/reports/ , wiki/records/history/
```
★`eval/**`, `knowledge/**`, `wiki/records/evidence/**`, `wiki/records/handoff/**`, `config/**`, `scripts/**` **금지**.

## 2. 작업 순서 — ★한 번에 다 옮기지 마라

각 단계마다 `python -m pytest tests -q` 를 돌리고 **116 passed 를 유지**한다.
깨지면 다음 단계로 가지 말고 그 단계를 고쳐라.

### 단계 1 — 디렉터리 골격 생성
`07_모듈화_구조.md` §2 트리대로 빈 패키지(`__init__.py`)를 만든다. 아직 파일을 옮기지 않는다.

### 단계 2 — `core/case_runtime/` 이동
`07` §3 대응표대로 옮긴다:
- `app/core/contracts.py` → `core/case_runtime/contracts/`
- `app/core/transition.py`, `app/domain/{case,events}.py` → `core/case_runtime/case/`
- `app/core/context.py` → `core/case_runtime/context/broker/`
- `app/core/registry.py` → `core/case_runtime/registry/`
- `app/application/controller.py`, `case_service.py` → `core/case_runtime/orchestration/`

★**기존 경로에 re-export 를 남긴다.** 예: `app/core/contracts.py` 를 지우지 말고
```python
from app.core.case_runtime.contracts import *  # noqa: F401,F403
```
로 바꾼다. 한 번에 모든 호출부를 고치면 되돌리기 어렵다.

### 단계 3 — `core/access_action/` 이동
`app/presentation/security.py` → `core/access_action/auth/`,
tools/approval/idempotency/audit 관련 코드를 해당 하위로.

### 단계 4 — `presentation/` 재배치
`api/mcp.py` → `presentation/mcp/`, `ui/` → `presentation/web/`, DTO → `presentation/schemas/`.

### 단계 5 — `infrastructure/` 재배치
`infrastructure/rag/` → `infrastructure/vectorstore/`(Adapter) +
`core/case_runtime/context/vector_retrieval/`(Port).

### 단계 6 — `modules/customer_ops/team_modules/`
`billing.py` → `local_team_a/`, `technical.py` → `local_team_b/`.

## 3. ★신설 (현재 코드에 전혀 없음)

### 3-1. `TeamExecutorPort` + `LocalTeamExecutor` — **최우선**
`core/case_runtime/remote_team/`

```python
class TeamExecutorPort(Protocol):
    async def execute(self, task: TeamTask) -> TeamResult: ...
```

- `LocalTeamExecutor` 가 현재 동작(`TeamModule.execute()` 직접 호출)을 그대로 감싼다
- ★**Controller 가 Team 을 Port 로만 호출**하게 바꾼다. 이게 `LOCAL` ↔ `A2A` 교체점이다
- `TeamResult` 계약은 **그대로** 쓴다

### 3-2. `A2ATeamExecutor` — 골격만
같은 위치. Agent Card 발견 → Task 발행 → Artifact 수신의 **인터페이스와 상태 매핑**까지.
★실제 원격 호출은 PoC 수준이면 된다. 네트워크가 막힌 환경이라 **호출 테스트는 fake 로** 한다.

A2A Task ↔ Case 상태 매핑(신 계획서 §9-C):
| Remote Task 상태 | Case 상태 |
|---|---|
| 진행 중 | `running` |
| 추가 입력 요구 | `waiting_input` |
| 완료 | Team 결과로 merge |
| 실패 | `failed` 또는 `escalated` |

★**매핑은 Adapter 가 하고 Controller 는 Case 상태만 본다.**

### 3-3. Agent Card — `presentation/a2a/`
우리가 A2A **서버**로서 발행하는 capability 문서.
Team Registry 의 `capabilities` 에서 생성한다. 정적 JSON 이어도 된다.

### 3-4. `GraphStorePort` + `SqlGraphAdapter`
`core/case_runtime/context/graph_retrieval/` (Port) + `infrastructure/graphstore/` (Adapter)

```python
class GraphStorePort(Protocol):
    async def neighbors(self, node_id: str, edge_types: list[str], depth: int = 1) -> list[dict]: ...
    async def path(self, src: str, dst: str, max_depth: int = 4) -> list[dict]: ...
    async def subgraph(self, root_id: str, depth: int = 2) -> dict: ...
```

- `SqlGraphAdapter` 는 **PostgreSQL JOIN 과 재귀 CTE(`WITH RECURSIVE`)** 로 구현한다
- 노드/엣지는 기존 FK 관계를 그대로 쓴다:
  `Case → Evidence → KnowledgeDocument` · `Case → Action → Approval` · `Customer → Case`
- ★**설명가능성 경로**가 주 용도다: `Case → Evidence → Document → Policy → Decision → Action`
- ★**Neo4j/AGE 를 도입하지 마라.** 신 계획서 §9-D 가 명시적으로 거부했다 —
  "현재 규모에서는 JOIN 이 맞다". Phase 2 비교 대상일 뿐이다

## 4. 테스트

- 기존 116건이 **계속 통과**해야 한다 (import 경로만 갱신)
- ★`tests/contract/test_core_isolation.py` 의 검사 대상 경로를 **새 구조에 맞게 갱신**한다.
  Core 가 `app.modules` 를 import 하지 않는다는 **규칙 자체는 유지**한다
- 신설분 테스트:
  1. `LocalTeamExecutor` 가 기존 Team 호출과 **동일 결과**를 낸다
  2. Controller 가 `TeamExecutorPort` 를 통해서만 Team 을 부른다
  3. `A2ATeamExecutor` 의 Task→Case 상태 매핑 (fake 원격)
  4. `SqlGraphAdapter.path()` 가 `Case → Evidence → Document` 경로를 실제로 반환
  5. Agent Card 가 Registry 의 capability 를 반영

★`pytest.skip` 금지. 실제 LLM/네트워크 호출 금지. 테스트 전용 tenant, teardown 삭제, `demo` 보존.

## 5. 완료 조건

```powershell
python -m pytest tests -q
python -m scripts.verify_dod
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe" -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```

기대: **116건 이상 통과, skipped 0**, `tenants=1`.
★**구조 이동만으로 `verify_dod` 결과가 나빠지면 안 된다.** 나빠지면 이동이 아니라 동작 변경이다.

PG 가 죽어 있으면:
```powershell
$data="C:\Users\playdata2\Documents\llm_workspace\_unified_mall_3\data\pgdata"
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\pg_ctl.exe" -D $data -o "-p 5433" -l "$data\server_5433.log" start
```

## 6. 리포트

`wiki/records/reports/2026-08-13_S-MODULARIZE_리포트.md` — 단계별 이동 목록, 각 단계의 테스트 결과,
신설 7종의 위치, **re-export 를 남긴 경로 목록**, 미이동분과 사유.

## 7. 하지 말 것
- ❌ 한 번에 전부 이동 (단계별로, 매번 테스트)
- ❌ 기존 import 경로를 끊기 (re-export 유지)
- ❌ Neo4j / AGE / 별도 Graph 저장소 도입
- ❌ 완전한 A2A 서버 구현 (골격까지)
- ❌ `transition_case()` 단일 진입점·append-only·Core 격리 규칙 훼손
- ❌ `eval/**`·`config/**`·`scripts/**` 수정
- ❌ 테스트 단언 약화 / `pytest.skip`
- ❌ 돌려보지 않고 "완료"
