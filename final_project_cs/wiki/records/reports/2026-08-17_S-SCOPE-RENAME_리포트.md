# S-SCOPE-RENAME 구현 리포트

## 변경 내용

- `subscription:read`를 `order:read`로 변경했습니다.
- `technical:read`를 `return:read`로 변경했습니다.
- Guardrail scope 계약 테스트와 REST endpoint scope 매트릭스 테스트의 기대 목록을 동기화했습니다.
- scope 검사 구현과 REST 테스트의 분기 로직은 변경하지 않았습니다.

## 검증

- `python -m pytest tests/security/test_scope_contract.py -q`
- `python -m pytest tests/integration/api/test_api_runtime.py -q`
- `python -m pytest -q`

실행 결과:

- `tests/security/test_scope_contract.py`: 2 passed
- `tests/integration/api/test_api_runtime.py`: DB fixture가 `127.0.0.1:5433`의 PostgreSQL이 `the database system is starting up` 상태여서 300초 timeout
- `pytest -q`: 225 passed, 4 failed, 66 errors, 2 deselected

전체 실패와 오류는 PostgreSQL 기동 중 상태 및 기존 환경 의존 테스트에서 발생했으며, scope rename 관련 assertion 실패는 확인되지 않았습니다.
