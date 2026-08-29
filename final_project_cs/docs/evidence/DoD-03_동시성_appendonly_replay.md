# DoD-03 — optimistic concurrency · append-only event · projection replay

- v5 §20 항목 3 / 검증 방법: replay fixture
- 실행: 2026-08-12 22:50 · 커밋 `cbb75e6`
- 판정: **통과**

## 재현

```powershell
python -m pytest tests/integration/controller tests/integration/db tests/unit/core -q
```

## 실제 출력

```
107 passed in 25.14s      (전체, skipped 0)
```

## 근거 1 — optimistic concurrency

`tests/integration/controller/test_controller_integration.py::test_same_expected_version_has_one_success_and_one_state_conflict`
`tests/integration/db/test_db_integration.py::test_version_conflict`

같은 `expected_version` 으로 두 요청 → **1건 성공, 1건 `StateConflict`**.

실체는 SQL 이다 (v5 §6-1 그대로):
```sql
UPDATE customer_cases SET ... version = version + 1
WHERE tenant_id=:t AND case_id=:c AND version = :expected_version
RETURNING version;      -- affected 0 → StateConflict
```

## 근거 2 — append-only

- DDL `case_events UNIQUE(case_id, aggregate_version)` — DB 직접 조회로 실재 확인
  (`case_events_case_id_aggregate_version_key`)
- repository / application / messaging 계층에 `UPDATE case_events` · `DELETE FROM case_events` **0건**
  (정적 검사)

## 근거 3 — ★replay 동치성

`test_replay_case_is_projection_equivalent` — `replay_case()` 로 이벤트를 재생하면
저장된 projection 과 **동일 status·version** 이 나온다.

★구조적 근거: `transition_case()` 와 `replay_case()` 가 **같은 순수 리듀서**
(`app/domain/case.py:apply_event`)를 쓴다. 두 경로가 각자 계산하면 조용히 어긋나므로
하나로 묶었다. 단위 테스트가 리듀서의 결정성을 별도로 증명한다
(`tests/unit/core/test_case_reducer.py`: `fold_events` 가 단계별 적용과 일치,
반복 호출 시 동일, version == 이벤트 수).

## 실행 조건

PostgreSQL 16.14 `127.0.0.1:5433` / DB `acop` / 테스트 전용 tenant 사용,
teardown 후 `tenants=1` (seed 오염 없음).

## 한계

- 경합 테스트는 **같은 프로세스 내 순차 호출**로 version 충돌을 만든다.
  실제 다중 프로세스 동시성 부하 시험은 하지 않았다.
- replay 는 **테스트가 만든 이벤트 열**에 대한 것이다. 운영 규모 이벤트 재생은 검증 범위 밖이다.

## ★2026-08-24 갱신 — `agent_runs` 진짜 동시 시작 경합 결함 발견·수정

sample(`final_project_sample/acop_basement/`) 대조에서, `start_run()`이
앱 레벨 `SELECT ... FOR UPDATE`로만 활성 run 존재를 확인했는데 이 락은
**이미 존재하는 행만** 잠근다는 걸 발견했다 — 같은 Case에 활성 run이
**0개**인 상태에서 동시에 두 번 `start_run()`이 호출되면 둘 다 insert에
성공할 수 있는 레이스였다(위 §한계의 "실제 다중 프로세스 동시성 부하
시험은 하지 않았다"가 바로 이 종류의 결함을 놓치는 지점이었다).

`ThreadPoolExecutor`로 **진짜 동시** 두 스레드가 같은 Case에 `start_run()`을
호출하는 재현 테스트를 먼저 추가해 레이스를 확인한 뒤, DB 레벨 partial
unique index(`agent_runs_one_active_per_case`, migration
`004_agent_runs_active_uniqueness.sql`)를 추가하고 `UniqueViolation`을
`ActiveRunError`로 잡았다. 상세: `docs/reports/2026-08-24_S-BASEMENT-04-CONCURRENCY_리포트.md`.
