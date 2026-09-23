# 버그사냥 05 — GraphStore·REST

## 점검 범위

- `app/infrastructure/graphstore/sql_adapter.py`의 `neighbors()`, `path()`, `subgraph()`
- `app/presentation/api/cases.py`의 `GET /v1/cases`, `GET /v1/cases/{id}`
- `app/infrastructure/db/repository.py`의 조회 함수

## 발견 사항

### app/infrastructure/graphstore/sql_adapter.py:117-119 — `subgraph()`가 DoD-21 관계 edge type 세 가지를 제외함
- 시나리오: `subgraph(case_id, depth=2)`를 호출해 Case→Issue→Policy, Issue→Team, Case→Action 관계를 함께 받으려는 경우, 내부의 `neighbors()` 호출 목록이 `owns`, `has_event`, `proposed`, `approved`, `contains`, `in_document`으로 고정되어 있다. 따라서 같은 파일의 `edges` CTE에 정의된 `has_issue`, `governed_by`, `handled_by`는 `subgraph()` 결과에 포함되지 않는다. `neighbors(case_id, ["has_issue", "governed_by"], depth=2)`처럼 직접 호출하면 조회되는 관계가 `subgraph()` 경로에서는 사라진다.
- 왜 기존 테스트가 못 잡는가: `tests/unit/infrastructure/test_graph_v7_axes.py`는 세 관계를 `neighbors()`로 직접 호출해 검증한다. `tests/integration/graph/test_sql_graph_adapter.py`의 `subgraph()` 검증은 `has_event` fixture만 사용하므로, `subgraph()` 호출자가 DoD-21 관계를 전달하지 않는 실제 경로를 검증하지 않는다.
- 재현 시도: 관련 GraphStore 테스트와 DoD-21 축 테스트를 실행해 `26 passed`를 확인했다. 해당 테스트들은 직접 `neighbors()` 경로만 통과시키며 `subgraph()`의 세 관계 누락은 코드 읽기로 확인했다. `subgraph()`에 세 관계를 요구하는 별도 테스트는 없어 독립 재현은 안 해봄.
- 위험도: 보통

### app/infrastructure/db/repository.py:26-30 / app/presentation/api/cases.py:102-106 — Case 목록 정렬이 `created_at` 동률에서 안정적이지 않음 (의심됨 — 확인 필요)
- 시나리오: 같은 `customer_id`로 짧은 시간에 여러 Case를 만들고 `GET /v1/cases?customer_id=...&limit=N`을 반복 호출할 때, `list_cases()`는 `ORDER BY created_at DESC LIMIT %s`만 사용한다. `created_at`이 같은 행이 limit 경계에 걸리면 PostgreSQL이 동률 행의 순서를 보장하지 않으므로, 반복 요청에서 경계의 Case가 바뀌어 클라이언트가 새 항목을 놓치거나 같은 항목을 중복 수신할 수 있다. 호출 API도 `limit`만 전달하고 cursor/고유 tie-breaker를 추가하지 않는다.
- 왜 기존 테스트가 못 잡는가: API 테스트는 목록의 상태 코드와 권한만 확인하고, 같은 `created_at` 동률 데이터에 대해 반복 요청 결과의 ID 순서를 비교하지 않는다. repository 테스트에도 이 조회의 안정적 순서 계약을 확인하는 테스트가 없다.
- 재현 시도: 관련 API·GraphStore 테스트를 실행해 `26 passed`를 확인했지만, 동률 timestamp를 강제로 만든 반복 목록 호출 재현은 안 해봄, 코드 읽기로만 판단. 실제 발생 여부는 PostgreSQL에서 동일 `created_at` 행을 limit 경계에 두고 반복 실행해 확인 필요.
- 위험도: 보통

## 발견하지 못한 항목

- `SqlGraphAdapter`의 세 관계 질의(`has_issue`/`governed_by`/`handled_by`, `proposed`)에는 모두 tenant 경로가 있다. Case→Issue는 Case의 tenant, Issue→Policy는 `kd.tenant_id=cc.tenant_id`, Issue→Team은 Case의 tenant, Case→Action은 Action과 Case의 tenant를 함께 조건으로 사용한다. `path()`도 시작 Case와 graph walk에 tenant 조건이 있다.
- `neighbors()`의 depth는 재귀 CTE의 `WHERE w.depth < %s`에 반영되고, `path()`도 `WHERE w.depth < %s`를 사용한다. Python에서만 잘라내기 위해 DB가 무제한 조회하는 형태는 확인되지 않았다.
- `GET /v1/cases/{id}`와 repository의 `get_case()`, `get_case_events()`는 tenant_id와 case_id를 함께 조건으로 사용한다.
- `repository.py`의 조회 SQL은 값에 문자열을 직접 결합하지 않는다. `list_cases()`의 문자열 조립은 고정된 SQL 조각(`AND customer_id=%s`, `ORDER BY...`, `LIMIT %s`)뿐이고 실제 값은 parameter binding으로 전달된다. tenant_id 조건이 빠진 조회 함수나 사용자 입력 기반 SQL injection 경로는 발견하지 못했다.

## 검증

```text
python -m pytest -q tests/integration/graph tests/unit/infrastructure/test_graph_v7_axes.py tests/integration/api/test_api_runtime.py
26 passed, 1 warning
```

완료 기준의 전체 명령도 실행했다. 대상 코드와 무관한 `tests/integration/rag/test_rag_integration.py` 3건이 `api.openai.com` 연결 시도에서 `WinError 10013`으로 실패하여 전체 결과는 `342 passed, 3 failed, 1 deselected`였다. 실패는 GraphStore/REST 변경에 의한 것이 아니며, 해당 파일을 제외한 대상 테스트는 위와 같이 통과했다.

코드 수정은 하지 않았다.
