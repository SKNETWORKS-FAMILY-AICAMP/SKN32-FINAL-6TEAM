# 구현 지시 — `SqlGraphAdapter` 검증 테스트 (미검증 유일 컴포넌트)

## 0. 상황

신설 7종이 전부 생성됐고 테스트 **119 passed**. 그런데 신설분 테스트는 3건뿐이다:

```
tests/unit/ports/test_team_ports.py
  test_local_executor_is_identical_to_direct_team_call      ✅
  test_a2a_maps_remote_states_without_exposing_them         ✅
  test_agent_card_reflects_registry_capabilities            ✅
```

★**`SqlGraphAdapter` 만 미검증**이다. `S-PORTS.md` §4 의 4번·5번이 빠졌다.
신설분 중 **유일하게 DB 를 타는 컴포넌트**이고, `tenant_id` 조건이 빠지면
그 자체가 보안 결함이다. import 는 되지만 동작은 확인된 적이 없다.

★이 프로젝트에서 "코드 존재 ≠ 동작" 으로 세 번 데었다:
route 등록 ≠ endpoint 동작 · 코드 존재 ≠ 적재 완료 · 컬럼 존재 ≠ 값 기록.

## 1. 소유 범위

```
tests/unit/ports/**
tests/integration/graph/**       ← 신설 가능
wiki/records/reports/ , wiki/records/history/
```

★**제품 코드를 고치지 마라.** `app/infrastructure/graphstore/sql_adapter.py` 나
`app/core/graph_retrieval/port.py` 를 수정하지 마라.
**테스트가 결함을 드러내면 고치지 말고 리포트에 적어라.** 그게 이 작업의 목적이다.

★금지: `app/**`, `eval/**`, `knowledge/**`, `config/**`, `scripts/**`,
`wiki/records/handoff/**`, `wiki/records/evidence/**`, `wiki/records/submission/**`.

## 2. 만들 테스트

먼저 `app/infrastructure/graphstore/sql_adapter.py` 와
`app/core/graph_retrieval/port.py` 를 **읽어라.** 실제 시그니처에 맞춰 작성한다.

### 2-1. ★`path()` 가 설명가능성 경로를 실제로 반환한다

`Case → Evidence → KnowledgeDocument` 를 역추적하는 것이 이 어댑터의 주 용도다.

1. 테스트 전용 tenant 에 Case 를 만들고, `case_events` 와
   `knowledge_documents`/`knowledge_chunks` 로 이어지는 관계를 세운다
2. `path(src=case_id, dst=document_id, max_depth=4)` 를 호출
3. ★**빈 리스트가 아니라 실제 경로**가 나오는지 단언한다
4. 경로의 각 hop 이 기대한 엣지 종류인지 확인한다

### 2-2. ★tenant 격리

1. **다른 tenant** 의 노드를 `src`/`dst` 로 주면 → **빈 결과**
2. `neighbors()` 도 다른 tenant 데이터를 섞어 반환하지 않는다
3. `subgraph()` 도 마찬가지

★이건 보안 검사다. **`tenant_id` 조건이 빠진 질의가 하나라도 있으면 이 테스트가 잡아야 한다.**

### 2-3. `neighbors()` · `subgraph()` 기본 동작

- `neighbors(case_id, edge_types=[...], depth=1)` 이 직접 연결된 노드를 반환
- `depth=2` 가 depth=1 보다 많거나 같은 결과를 낸다
- `subgraph(root_id, depth=2)` 가 노드·엣지를 함께 담은 구조를 반환

### 2-4. 재귀 CTE 가 무한히 돌지 않는다

순환 관계나 `max_depth` 초과 상황에서 **깊이 제한이 지켜지는지** 확인한다.

## 3. 규칙

- ★**테스트 전용 tenant**(`test_<uuid>`), teardown 에서 자기 행 전부 삭제 (FK 순서 주의)
- ★**`demo` tenant 를 지우지 마라** — seed 다
- ★`pytest.skip` 금지. 데이터가 없으면 fixture 로 만들고, 그래도 안 되면 **fail**
- ★실제 LLM·임베딩 호출 금지 (이 환경은 외부 네트워크가 막혀 있다)
- 기존 방식 참고: `tests/integration/db/test_db_integration.py`

## 4. 완료 조건

```powershell
python -m pytest tests -q
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe" -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```

기대: **119건 이상, skipped 0**, `tenants=1`.
★**실패하는 테스트가 있으면 실패한 채로 두고 리포트에 원인을 적어라.**
단언을 약화시켜 통과시키지 마라.

PG 가 죽어 있으면:
```powershell
$data="C:\Users\playdata2\Documents\llm_workspace\_unified_mall_3\data\pgdata"
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\pg_ctl.exe" -D $data -o "-p 5433" -l "$data\server_5433.log" start
```
★`-o "-p 5433"` 를 빠뜨리면 5432 로 뜬다.

## 5. 리포트

`wiki/records/reports/2026-08-13_S-GRAPHTEST_리포트.md`:
1. 추가한 테스트 목록
2. §4 명령의 **실제 출력 원문**
3. ★**실패한 테스트와 원인** — 특히 `tenant_id` 누락을 발견했다면 그게 핵심 산출물이다
4. 검증하지 못한 것과 이유

`wiki/records/history/2026-08-13_S-GRAPHTEST.md` 이력 추가.

## 6. 하지 말 것
- ❌ 제품 코드 수정
- ❌ 단언 약화 / `pytest.skip`
- ❌ `demo` tenant 오염·삭제
- ❌ 소유 범위 밖 수정
- ❌ 돌려보지 않고 "완료"
