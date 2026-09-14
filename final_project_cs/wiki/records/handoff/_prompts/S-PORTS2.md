# 구현 지시 — S-PORTS 나머지 4종 (A2A Executor · Agent Card · Graph Port · SQL Adapter)

## 0. 이어서 하는 작업

★**`wiki/records/handoff/_prompts/S-PORTS.md` 를 먼저 읽어라. 그 문서의 §3-2 ~ §3-5 가 이번 범위다.**

지난 실행에서 **§3-1 만 완료**됐다:
- `app/core/remote_team/executor.py` — `TeamExecutorPort`, `LocalTeamExecutor` ✅
- `app/application/controller.py:124` 가 `self.team_executor.execute(task)` 로 Port 경유 ✅
- 테스트 **119 passed** (기준선 116 → +3)

**이번에 만들 것: §3-2, §3-3, §3-4, §3-5.**

## 1. 현재 기준선

```
119 passed, 0 failed, skipped 0
```
★이걸 깨면 실패다. **단계마다 `python -m pytest tests -q` 를 돌리고, 깨지면 그 자리에서 고쳐라.**

## 2. 소유 범위

```
app/core/remote_team/**          (a2a_executor 추가)
app/core/graph_retrieval/**      ← 신설
app/infrastructure/graphstore/** ← 신설
app/presentation/a2a/**          ← 신설
tests/**
wiki/records/reports/ , wiki/records/history/
```

★**기존 파일을 옮기지 마라.** 지난 시도가 이동 때문에 순환 import 로 실패했다
(`wiki/records/reports/debugs/2026-08-13_1400_모듈화가_순환import로_실패했다.md`).
`app/core/contracts.py`, `app/domain/`, `app/core/context.py` 는 **현재 위치 그대로** 두고
새 모듈이 그 경로에서 import 한다.

★금지: `eval/**`, `knowledge/**`, `config/**`, `scripts/**`, `wiki/records/handoff/**`,
`wiki/records/evidence/**`, `wiki/records/submission/**`, `app/core/contracts.py`, `app/domain/**`.

## 3. 만들 것 — S-PORTS.md §3-2 ~ §3-5 그대로

요약(상세는 S-PORTS.md 참조):

| # | 파일 | 핵심 |
|---|---|---|
| 3-2 | `app/core/remote_team/a2a_executor.py` | `A2ATeamExecutor` — transport 주입, **Task↔Case 상태 매핑 4종** |
| 3-3 | `app/presentation/a2a/agent_card.py` | Registry capability 에서 Agent Card 생성. ★`/v1/*` 경로 늘리지 마라 |
| 3-4 | `app/core/graph_retrieval/port.py` | `GraphStorePort` — `neighbors` / `path` / `subgraph` |
| 3-5 | `app/infrastructure/graphstore/sql_adapter.py` | `SqlGraphAdapter` — **JOIN + `WITH RECURSIVE`** |

### 3-2 상태 매핑 (신 계획서 §9-C)

| Remote Task | TeamResult |
|---|---|
| 진행 중 | `running` 유지, deadline 까지 폴링 |
| 추가 입력 요구 | `outcome='waiting'`, `next_action=wait_for_input` |
| 완료 | Artifact → `outcome='completed'` |
| 실패 | `outcome='failed'` |

★**Controller 는 Case 상태만 본다.** 원격 Task 상태를 밖으로 노출하지 마라.
★**실제 네트워크 호출 금지.** transport 를 주입받고 테스트는 fake 로.

### 3-5 그래프 엣지 (기존 FK 를 그대로 쓴다)

```
customers → customer_cases            (owns)
customer_cases → case_events          (has_event)
customer_cases → action_requests → action_approvals
knowledge_documents → knowledge_chunks
```

★주 용도는 **설명가능성 경로**: `Case → Evidence → Document` 역추적.
★**Neo4j / AGE 도입 금지** — 신 계획서 §9-D 가 "현재 규모에서는 JOIN 이 맞다"고 거부했다.
★모든 질의에 **`tenant_id` 조건**.

## 4. 테스트

S-PORTS.md §4 의 3~6번:
3. `A2ATeamExecutor` 상태 매핑 4종 (fake transport)
4. `SqlGraphAdapter.path()` 가 `Case → Evidence → Document` 경로를 **실제로** 반환
5. `SqlGraphAdapter` 가 다른 tenant 데이터를 반환하지 않는다
6. Agent Card 가 Registry 의 capability 를 반영한다

★`pytest.skip` 금지. 실제 LLM·네트워크 호출 금지. 테스트 전용 tenant, teardown 삭제, `demo` 보존.

## 5. 완료 조건

```powershell
python -m pytest tests -q
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe" -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```
기대: **119건 이상, 0 failed, skipped 0**, `tenants=1`.

PG 가 죽어 있으면:
```powershell
$data="C:\Users\playdata2\Documents\llm_workspace\_unified_mall_3\data\pgdata"
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\pg_ctl.exe" -D $data -o "-p 5433" -l "$data\server_5433.log" start
```

## 6. 리포트

`wiki/records/reports/2026-08-13_S-PORTS2_리포트.md` — 만든 파일, 단계별 테스트 결과,
§5 명령의 **실제 출력 원문**, 만들지 못한 것과 사유.

## 7. 하지 말 것
- ❌ 기존 파일 이동 (지난번 이걸로 실패)
- ❌ 계약(`TeamTask`/`TeamResult`) 변경
- ❌ Neo4j / AGE
- ❌ 실제 A2A 네트워크 호출
- ❌ `/v1/*` 경로 추가
- ❌ `tenant_id` 없는 그래프 질의
- ❌ 테스트 깨진 채 다음 단계
- ❌ 돌려보지 않고 "완료"
