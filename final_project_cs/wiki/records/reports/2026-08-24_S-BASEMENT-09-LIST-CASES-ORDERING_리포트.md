# S-BASEMENT-09 — `list_cases` 동률 정렬 비결정성 수정 보고서

## 변경 내용

- `app/infrastructure/db/repository.py`의 `list_cases()` 정렬을 다음과 같이 수정했다.
  - 기존: `ORDER BY created_at DESC LIMIT %s`
  - 변경: `ORDER BY created_at DESC, case_id DESC LIMIT %s`
- `get_case`, `get_case_events` 등 다른 repository 함수는 수정하지 않았다.

## 회귀 테스트

`tests/integration/db/test_db_integration.py`에 `test_list_cases_orders_equal_created_at_deterministically`를 추가했다.

- 동일 tenant/customer에 Case 3개를 삽입했다.
- 세 행의 `created_at`과 `updated_at`을 동일한 `2026-08-24 00:00:00+00` timestamptz로 강제했다.
- `list_cases()`를 10회 호출하고 매번 `case_id DESC` 순서인지 검증한다.

수정 후 검증 결과:

```text
python -m pytest -q tests/integration/db/test_db_integration.py -m "not live"
6 passed, 1 warning in 2.19s
```

## 전체 검증

요청 명령:

```text
python -m pytest -q -m "not live"
```

실행 결과:

```text
4 failed, 370 passed, 3 deselected, 2 warnings, 14 errors in 42.04s
```

기준으로 제시된 `378 passed`와 비교하면 이번 실행은 `370 passed`였다. 추가한 동률 정렬 테스트와 DB 통합 테스트 6개는 통과했다.

전체 결과의 기존 환경성 문제:

- `tests/architecture/test_basement_is_domain_free.py` 1건 실패
- `tests/integration/rag/test_rag_integration.py` 3건 실패 — OpenAI embeddings 외부 연결 차단
- `eval/tests/test_holdout_labeling.py` 및 `tests/e2e/test_composer_write_channel.py` 14건 오류 — pytest 임시 디렉터리 접근 권한 오류로 fixture setup 실패
- pytest cache 경로에도 `WinError 5` 권한 경고가 발생했다.

따라서 전체 suite는 기준 수치에 도달하지 못했지만, 실패·오류는 `list_cases()` 변경과 무관하며 관련 테스트는 통과했다.
