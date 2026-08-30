# S-AUDIT-STORE — 감사 로그 저장 계층 리포트

## 결론

Composer 감사 이벤트의 계약 shape를 바꾸지 않고 파일 JSONL과 중앙 PostgreSQL을
같은 인터페이스로 다루는 저장 부품을 추가했다. 제품 코드에는 갱신·삭제 경로가
없고, 같은 idempotency key도 고유 제약 없이 모두 append 된다.

이 작업은 `program/plan/A-COP_Composer_중앙설정저장소_결정.md` 6단계의 부품
작성 범위다. 배선은 후속 작업이므로 `acop_composer/**`와 기존 파일은 수정하지
않았다.

## 만든 파일

- `acop_basement/core/audit_store.py`
  - `AuditStoreError`, `AuditStore` Protocol
  - `FileAuditStore`, `PostgresAuditStore`
- `acop_basement/infrastructure/db/migrations/007_composer_audit_events.sql`
  - append-only `composer_audit_events` 테이블
  - 대상별 최근 조회와 idempotency 조회용 비고유 인덱스
- `tests/integration/test_audit_store.py`
  - 실제 PostgreSQL 4건, 파일 JSONL 2건 검증
- `docs/reports/2026-08-29_S-AUDIT-STORE_리포트.md`

## 설계 판단

### 이벤트 전문 보존

PostgreSQL의 `payload JSONB`에 전달받은 이벤트 dict 전체를 저장한다. `event`,
`actor`, `idempotency_key` 컬럼은 조회를 위한 중복 컬럼일 뿐 payload를 다시
조립하는 근거가 아니다. 따라서 `docs/handoff/13`의 기본 필드와 `/changes`
추가 필드는 이름·의미를 바꾸지 않고 왕복한다.

### 최근 이벤트 순서와 대상 격리

`recent()`는 최신 이벤트부터 반환한다. DB는 `created_at DESC, event_id DESC`,
파일은 정상 JSON object를 모두 읽은 뒤 역순으로 반환한다. DB의 append와 모든
조회에는 `deployment_id` 조건을 넣어 대상 간 이벤트가 섞이지 않게 했다.

### `find_by_idempotency_key` 구현

- 파일: 기존 `acop_composer.api._find_idempotent`와 같은 순방향 전체 스캔이다.
  빈 줄과 JSON 파싱이 깨진 줄을 건너뛰며 최초 일치 이벤트를 반환한다. 파일이
  없거나 키가 없으면 `None`이다.
- DB: `(deployment_id, idempotency_key)` 인덱스로 대상을 포함해 조회하고,
  `event_id ASC LIMIT 1`로 최초 일치 이벤트를 반환한다. 이 인덱스는 UNIQUE가
  아니므로 같은 키의 후속 감사 이벤트도 모두 남는다.

두 구현 모두 이벤트 전문을 반환한다. 후속 배선에서 기존 동작처럼 `result`를
꺼내 응답하는 것은 호출자 책임이다.

### append-only

제품 저장소 API는 `append`, `recent`, `find_by_idempotency_key`만 제공한다.
마이그레이션에도 데이터 `UPDATE`·`DELETE`가 없다. 통합 테스트 fixture의
`DELETE`는 테스트 대상별 행을 정리하기 위한 격리 절차이며 제품 경로가 아니다.

## 검증 결과

워크트리에 `.env`가 없어 최초 마이그레이션 시도는 설정 검증에서 중단됐다.
`.env.example`과 `CLAUDE.md`의 로컬 PostgreSQL 안내에 따라 테스트 프로세스에만
환경값을 주입한 뒤 재실행했다. 파일에는 환경값을 기록하지 않았다.

```text
python -m acop_basement.infrastructure.db.migrate
Applied 7 migrations ...

python -m acop_basement.infrastructure.db.migrate
Applied 7 migrations ...
```

연속 두 번 모두 성공해 007 마이그레이션의 재실행 안전성을 확인했다.

```text
python -m pytest tests/integration/test_audit_store.py -q --basetemp=.pytest-basetemp-audit
......                                                                   [100%]
6 passed in 1.15s

python -m pytest tests/architecture -q --basetemp=.pytest-basetemp-architecture
........................................................................ [ 86%]
...........                                                              [100%]
83 passed in 0.62s
```

이 환경의 pytest 기본 임시 폴더는 ACL 때문에 접근할 수 없어, 파일 테스트에는
쓰기 가능한 워크트리 내부 `--basetemp`를 사용했다. 검증 후 임시 파일과 폴더를
정리했다.

DB 메타데이터도 직접 조회했다. 테이블은 요구된 7개 컬럼과 nullability/default를
가졌고, 인덱스는 기본키 외에 다음 두 개가 존재했다.

```text
composer_audit_events_deployment_created_at_idx
  (deployment_id, created_at DESC)
composer_audit_events_deployment_idempotency_key_idx
  (deployment_id, idempotency_key)  -- 비고유
```

## 미해결·후속 작업

이번 범위에는 미해결 구현 항목이 없다. 의도적으로 제외한 후속 작업은
`acop_composer/api.py`가 `AuditStore`를 주입받아 append 및 idempotency 조회에
쓰도록 배선하는 것이다.

## 참조

- `acop_basement/core/config_store.py`
- `acop_composer/api.py`의 `_append_audit`, `_find_idempotent`
- `acop_basement/infrastructure/db/migrations/006_project_configs.sql`
- `tests/integration/test_config_store.py`
- `docs/handoff/13_Composer_쓰기채널_계약.md`
- `CLAUDE.md` §0.3
