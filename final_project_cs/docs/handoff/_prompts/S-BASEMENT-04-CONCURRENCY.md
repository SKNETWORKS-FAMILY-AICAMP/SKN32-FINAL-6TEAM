# S-BASEMENT-04-CONCURRENCY — agent_runs 동시성 결함 수정 (migration 004)

## 0. 배경

`final_project_sample/acop_basement/application/case_service.py` (참고용,
**절대 수정 금지**) 와 `app/application/case_service.py` 대조에서 발견됨.

`start_run()` 이 지금 앱 레벨 `SELECT ... FOR UPDATE` 로만 "이미 활성
run 이 있는지" 를 확인하는데, 이 락은 **이미 존재하는 행**만 잠근다.
같은 Case 에 활성 run 이 **0개**인 상태에서 동시에 두 번 `start_run()`
이 호출되면 락이 아무것도 안 걸려있어서 둘 다 insert 에 성공할 수
있다(레이스). sample 은 DB 레벨 partial unique index
(`agent_runs_one_active_per_case`, migration
`004_agent_runs_active_uniqueness.sql`)를 추가하고, 앱 코드에서
`psycopg.errors.UniqueViolation` 을 실제 방어선으로 잡는다.

## 1. 할 일

1. `app/infrastructure/db/migrations/004_agent_runs_active_uniqueness.sql`
   신규 작성 — sample 의 마이그레이션을 참고해서 cs 의 `agent_runs`
   테이블 스키마에 맞는 partial unique index 를 만들어라(정확한 컬럼명은
   cs 의 `001_schema.sql` 에서 실제 `agent_runs` 테이블 정의를 확인해라
   — sample 과 컬럼명이 다를 수 있다).
2. `app/application/case_service.py` 의 `start_run()` 에
   `UniqueViolation` 을 잡아서 "이미 활성 run 이 있다"는 명확한 실패로
   처리하는 코드를 추가해라(무엇을 반환/예외처리할지는 이 함수의 기존
   실패 처리 패턴을 따라라).

## 2. 검증

- **레이스 재현 테스트**를 먼저 만들어라 — 동시에 두 `start_run()` 을
  호출해서(스레드나 asyncio.gather 등으로) 수정 전에는 둘 다 성공할 수
  있었다는 걸 확인하고, 수정 후엔 정확히 1개만 성공하는지 확인해라.
  (`tests/integration/controller/` 안의 기존 동시성 테스트 패턴 —
  예를 들어 outbox 관련 race 테스트 — 을 참고해라.)
- 마이그레이션이 재실행 안전한지(멱등) 확인해라 — 기존 마이그레이션
  실행 방식(`app/infrastructure/db/migrate.py`)을 따라 실제로
  두 번 실행해봐도 에러 없이 통과하는지 확인해라.
- `python -m pytest -q -m "not live"` 결과를 리포트에 붙여라(359 passed
  기준 변화 명시).

## 3. 쓰기 대상

- `app/infrastructure/db/migrations/004_agent_runs_active_uniqueness.sql` (신규)
- `app/application/case_service.py`
- 관련 테스트 파일(신규 또는 기존 파일에 추가)
- `docs/reports/2026-08-24_S-BASEMENT-04-CONCURRENCY_리포트.md` (신규)

## 4. 하지 말 것

- `final_project_sample/` 수정 금지 — 읽기만
- 마이그레이션 번호 004 는 이 작업 전용이다 — 003(다른 작업), 005(다른
  작업)와 겹치지 않는다, 그대로 004 를 써라
