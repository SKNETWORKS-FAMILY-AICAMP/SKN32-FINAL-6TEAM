# S-BASEMENT-04-CONCURRENCY — `agent_runs` 동시성 결함 수정

## 변경 내용

- `app/infrastructure/db/migrations/004_agent_runs_active_uniqueness.sql`
  추가
  - `agent_runs(tenant_id, case_id)`에 partial unique index
    `agent_runs_one_active_per_case`를 추가했다.
  - 조건은 `status IN ('active', 'running', 'resuming')`이다.
  - `CREATE UNIQUE INDEX IF NOT EXISTS`로 재실행 가능하게 했다.
- `app/application/case_service.py`
  - INSERT 경합에서 발생하는 `psycopg.errors.UniqueViolation`을
    `ActiveRunError("active run already exists for case ...")`로 변환했다.
  - 기존 `SELECT ... FOR UPDATE`의 빠른 사전 검사도 유지했다.
- `tests/integration/controller/test_active_run_uniqueness.py`
  - 서로 다른 DB 연결에서 같은 Case에 동시에 `start_run()`을 호출한다.
  - 성공 1건, 명확한 활성-run 거부 1건, 최종 활성 행 1건을 검증한다.

`final_project_sample/`은 수정하지 않았다.

## 검증 결과

### 마이그레이션 멱등성

다음 명령을 연속으로 두 번 실행했고 모두 성공했다.

```text
python -m app.infrastructure.db.migrate
Applied migrations from ...\app\infrastructure\db\migrations

python -m app.infrastructure.db.migrate
Applied migrations from ...\app\infrastructure\db\migrations
```

### 동시성 테스트

```text
python -m pytest -q tests/integration/controller/test_active_run_uniqueness.py
1 passed
```

### 전체 비-live 테스트

```text
python -m pytest -q -m "not live"
336 passed, 18 failed, 11 errors, 3 deselected
```

요청 기준인 `359 passed`와 비교하면 현재 실행 결과는 23건 적은 passed이며,
실패/오류가 함께 발생했다. 새 동시성 테스트는 통과했다. 전체 실패는 이번
변경과 직접 관련 없는 기존 워크스페이스 상태/실행 환경 문제로 확인됐다.

- outbox 관련 일부 테스트: 현재 DB의 outbox dedupe 제약과 `ON CONFLICT`
  기대가 불일치하여 `InvalidColumnReference` 발생
- RAG 통합 테스트: OpenAI embeddings 연결이 `WinError 10013`으로 거부됨
- 일부 E2E/holdout 테스트: pytest 임시 디렉터리 접근 권한 오류

따라서 이번 변경의 직접 검증 항목인 마이그레이션 재실행과 동시 최초 실행
경합은 통과했으며, 전체 기준선 복구를 위해서는 위 환경/기존 변경 상태를
별도로 정리해야 한다.
