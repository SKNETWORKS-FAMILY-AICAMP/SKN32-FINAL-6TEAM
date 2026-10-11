# S-MIGRATE-DUPLICATE-GUARD 실행 리포트

- 실행일: 2026-08-20 (Asia/Seoul)
- 목적: core/domain 마이그레이션의 동명 파일을 DB 연결 전에 탐지

## 변경 파일

- `acop_basement/infrastructure/db/migrate.py`
  - `collect_migration_files()`를 추가했다.
  - core와 domain 디렉터리의 동일 파일명을 검사하고, 충돌 파일명과 두 디렉터리 경로를 담은 `RuntimeError`를 발생시킨다.
  - 충돌이 없으면 기존과 동일하게 두 목록을 `key=lambda p: p.name`으로 합쳐 정렬한다.
- `tests/unit/infrastructure/test_migrate.py`
  - 서로 다른 파일명의 병합·파일명 순서 정렬을 검증한다.
  - 동명 파일에서 `RuntimeError`, 파일명·두 경로 포함, `get_connection` 미호출을 검증한다.

## 실행 예시

### 정상 케이스

```powershell
python -m pytest tests/unit/infrastructure/test_migrate.py::test_collect_migration_files_merges_and_sorts_core_and_domain -q
```

```text
1 passed
```

예시 입력(`001_core.sql`, `003_core.sql`, `002_domain.sql`, `004_domain.sql`)의 산출 순서는 다음과 같다.

```text
001_core.sql, 002_domain.sql, 003_core.sql, 004_domain.sql
```

### 충돌 케이스

```powershell
python -m pytest tests/unit/infrastructure/test_migrate.py::test_main_rejects_duplicate_filename_before_database_connection -q
```

```text
1 passed
```

`001_schema.sql`이 core/domain 양쪽에 있으면 `RuntimeError`가 발생하며, 예외 메시지에 파일명과 두 디렉터리 경로가 포함된다. 이 시점은 `get_connection()` 호출 전이다.

## 테스트 결과

```text
python -m pytest tests/unit/infrastructure -q
python -m pytest tests/architecture -q
python -m pytest -q --ignore=tests/integration/rag
```

- `python -m pytest tests/unit/infrastructure -q`: 120초 타임아웃. 신규 테스트 2건은 별도 실행 시 통과했으며, 기존 DB 연결 테스트 구간에서 출력 없이 대기했다.
- `python -m pytest tests/architecture -q`: `72 passed`
- `python -m pytest -q --ignore=tests/integration/rag`: 120초 타임아웃. 기존 DB 의존 테스트 구간에서 약 20% 진행 후 대기했다.

환경상 기본 pytest 임시 디렉터리와 `.pytest_cache`에 권한 경고가 있어, 신규 테스트와 지정 테스트는 작업공간 아래 `--basetemp`로 실행했다. 해당 권한 문제는 이번 변경과 무관하다.
