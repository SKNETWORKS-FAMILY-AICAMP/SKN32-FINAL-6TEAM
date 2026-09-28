# 구현 지시 — A2A / Graph **Port 신설** (이동은 하지 않는다)

## 0. 지난 시도가 실패한 이유

모듈화(디렉터리 이동)를 먼저 하다가 **순환 import 로 테스트 수집이 중단**됐고,
정작 중요한 **신설 7종에 도달하지 못했다.** 전부 되돌렸다.
→ `wiki/records/reports/debugs/2026-08-13_1400_모듈화가_순환import로_실패했다.md`

★**이번에는 이동을 하지 않는다.** 현재 구조 위에 **새 것만 더한다.**
디렉터리 재배치는 이게 끝난 뒤 별도로 한다.

현재 기준선: **116 passed, 0 failed, skipped 0**. 이걸 깨면 실패다.

## 1. 계약

- `wiki/records/handoff/07_모듈화_구조.md` **§4 신설 목록**
- `../A-COP_구현계획서_A2A_Graph반영.md` **§9-C(A2A) · §9-D(Graph)** — 읽기 전용
- `../A-COP_브리핑_A2A_Graph반영_최종.html` §6 — 모듈형 Basement 4축

## 2. 소유 범위

```
app/core/remote_team/**          ← 신설
app/core/graph_retrieval/**      ← 신설
app/infrastructure/graphstore/** ← 신설
app/presentation/a2a/**          ← 신설
app/application/controller.py    ← Port 경유로 최소 변경
tests/**
wiki/records/reports/ , wiki/records/history/
```

★**기존 파일을 옮기지 마라.** `app/core/contracts.py`, `app/domain/`, `app/core/context.py` 등
현재 위치 그대로 둔다. 새 모듈은 **현재 경로에서 import** 한다 (순환이 생기지 않는다).
★`eval/**`, `knowledge/**`, `config/**`, `scripts/**`, `wiki/records/handoff/**`, `wiki/records/evidence/**`, `wiki/records/submission/**` 금지.

## 3. 만들 것

### 3-1. `app/core/remote_team/executor.py` — ★최우선

```python
class TeamExecutorPort(Protocol):
    async def execute(self, task: TeamTask) -> TeamResult: ...

class LocalTeamExecutor:
    """현재 동작을 그대로 감싼다 — TeamModule.execute() 직접 호출."""
    def __init__(self, registry) -> None: ...
    async def execute(self, task: TeamTask) -> TeamResult: ...
```

- `TeamTask`/`TeamResult` 는 `app.core.contracts` 에서 가져온다 (**계약 변경 없음**)
- ★`app/application/controller.py` 가 Team 을 **Port 로만** 호출하게 바꾼다.
  이게 `LOCAL` ↔ `A2A` 교체점이다. **다른 동작은 바꾸지 마라**
- 기존 116건이 그대로 통과해야 한다

### 3-2. `app/core/remote_team/a2a_executor.py` — 골격

```python
class A2ATeamExecutor:
    """원격 Agent System 에 Task 를 위임한다. 전송은 주입받는다(테스트는 fake)."""
    def __init__(self, transport, capability_resolver) -> None: ...
    async def execute(self, task: TeamTask) -> TeamResult: ...
```

★A2A Task ↔ Case 상태 매핑을 **이 Adapter 안에서** 한다 (신 계획서 §9-C):

| Remote Task 상태 | 매핑 |
|---|---|
| 진행 중 | `running` 유지, deadline 까지 폴링 |
| 추가 입력 요구 | `TeamResult(outcome='waiting', next_action=wait_for_input)` |
| 완료 | Artifact → `TeamResult(outcome='completed')` |
| 실패 | `outcome='failed'` |

★**Controller 는 Case 상태만 본다.** 원격 Task 상태를 Controller 에 노출하지 마라.
★실제 네트워크 호출은 하지 마라 — transport 를 주입받고 테스트는 fake 로 한다.

### 3-3. `app/presentation/a2a/agent_card.py`

우리가 A2A **서버**로서 발행하는 capability 문서.
Team Registry 의 `capabilities` 에서 생성한다. `GET /a2a/agent-card` 로 노출해도 되고
함수로만 두어도 된다. ★**`/v1/*` 경로를 늘리지 마라** — REST 5개 계약이 깨진다.

### 3-4. `app/core/graph_retrieval/port.py`

```python
class GraphStorePort(Protocol):
    async def neighbors(self, node_id: str, edge_types: list[str], depth: int = 1) -> list[dict]: ...
    async def path(self, src: str, dst: str, max_depth: int = 4) -> list[dict]: ...
    async def subgraph(self, root_id: str, depth: int = 2) -> dict: ...
```

### 3-5. `app/infrastructure/graphstore/sql_adapter.py`

`SqlGraphAdapter` — **PostgreSQL JOIN 과 재귀 CTE(`WITH RECURSIVE`)** 로 구현.

노드/엣지는 **기존 FK 를 그대로** 쓴다:
- `customers → customer_cases` (owns)
- `customer_cases → case_events` (has_event)
- `customer_cases → action_requests → action_approvals` (proposed / approved)
- `knowledge_documents → knowledge_chunks` (contains)

★**주 용도는 설명가능성 경로**다: `Case → Evidence → Document` 를 거슬러 올라간다.
★**Neo4j / AGE 를 도입하지 마라.** 신 계획서 §9-D 가 명시적으로 거부했다 —
"현재 규모에서는 JOIN 이 맞다". Phase 2 비교 대상일 뿐이다.
★모든 질의에 **`tenant_id` 조건**을 넣는다.

## 4. 테스트 (`tests/`)

1. `LocalTeamExecutor` 가 기존 Team 직접 호출과 **동일한 `TeamResult`** 를 낸다
2. Controller 가 `TeamExecutorPort` 를 통해서만 Team 을 호출한다
3. `A2ATeamExecutor` 의 원격 상태 → `TeamResult` 매핑 4종 (fake transport)
4. `SqlGraphAdapter.path()` 가 `Case → Evidence → Document` 경로를 **실제로** 반환
5. `SqlGraphAdapter` 가 다른 tenant 데이터를 반환하지 않는다
6. Agent Card 가 Registry 의 capability 를 반영한다

★`pytest.skip` 금지. 실제 LLM·네트워크 호출 금지. 테스트 전용 tenant, teardown 삭제, `demo` 보존.

## 5. 완료 조건 — ★단계마다 확인한다

각 구성요소를 만들 때마다 `python -m pytest tests -q` 를 돌린다.
**깨지면 다음으로 가지 말고 그 자리에서 고쳐라.**

최종:
```powershell
python -m pytest tests -q
python -m scripts.verify_dod
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe" -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```
기대: **116건 이상 통과, 0 failed, skipped 0**, `tenants=1`.

PG 가 죽어 있으면:
```powershell
$data="C:\Users\playdata2\Documents\llm_workspace\_unified_mall_3\data\pgdata"
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\pg_ctl.exe" -D $data -o "-p 5433" -l "$data\server_5433.log" start
```

## 6. 리포트

`wiki/records/reports/2026-08-13_S-PORTS_리포트.md` — 만든 파일, 각 단계의 테스트 결과,
Controller 변경 내용(최소 변경임을 보여라), §5 명령의 **실제 출력 원문**.

## 7. 하지 말 것
- ❌ **기존 파일 이동** (이번 범위 아님. 지난번 이걸로 실패했다)
- ❌ 계약(`TeamTask`/`TeamResult`) 변경
- ❌ Neo4j / AGE / 별도 Graph 저장소
- ❌ 실제 A2A 네트워크 호출
- ❌ `/v1/*` 경로 추가
- ❌ `tenant_id` 없는 그래프 질의
- ❌ 테스트가 깨진 채로 다음 단계 진행
- ❌ 돌려보지 않고 "완료"
