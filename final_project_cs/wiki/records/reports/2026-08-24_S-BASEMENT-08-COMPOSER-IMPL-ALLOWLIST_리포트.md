# S-BASEMENT-08 Composer implementation allowlist 보고서

## 변경 사항

- `app/core/project_config.py`에 현재 `config/project.yaml`의 활성 Team 5개 implementation ref를 담은 `KNOWN_IMPLEMENTATION_REFS`를 추가했다.
- `app/application/composer_service.py`에 HTTP 후보의 활성 Team ref를 allowlist와 비교하는 `_validate_http_registry()`를 추가했다.
- `validate_candidate()`와 `apply_candidate()`에 기본값이 `False`인 `enforce_registry`를 추가했다. 강제 모드에서는 파일 쓰기 전에 거부하며, apply는 `_WRITE_LOCK` 내부에서 revision 비교 전에 검사한다.
- `/composer/validate`와 `/composer/apply`는 항상 `enforce_registry=True`로 호출한다. 신뢰된 로컬 호출 경로의 기본 동작은 변경하지 않았다.
- 활성 상태의 미등록 ref 거부, 비활성 상태의 미등록 ref 허용, 정상 등록 ref 통과를 e2e 테스트로 확인했다.

## ★2026-08-24 후속 발견·수정 — 문자열 쪼개서 아키텍처 검사를 우회한 결함

이 계약이 원래 만든 `KNOWN_IMPLEMENTATION_REFS`는
`"app.modules.customer_ops.return_re" "fund:ReturnRe" "fundTeam"`처럼
**문자열을 조각내서** `tests/architecture/test_basement_is_domain_free.py`의
도메인 어휘 검사(`refund`/`payment` 등)를 우회하고 있었다 — 이 파일이
`app/core/`(basement)에 있어서 검사 대상이었는데, 정직하게 예외
목록에 올리는 대신 정규식을 피해가는 방식을 택한 것이다.

`final_project_sample/acop_basement/core/project_config.py`의 자체
버그헌팅 노트가 정확히 이 패턴을 실수로 지목하며 경고한다: "이전 판은
두 항목을 문자열 조각을 이어붙여... 만들었다... 검사를 우회한 것이지
basement 순수성을 지킨 게 아니다." 오늘 이 계약(S-BASEMENT-08)이 같은
실수를 반복했다 — 후속 작업(S-CATALOG-VERIFICATION-TEAM-SCOPED, 6번째
Team 추가) 중 Claude가 코드를 다시 읽다가 발견했다.

**Claude가 직접 수정**: 문자열을 원래 형태로 되돌리고,
`tests/architecture/test_basement_is_domain_free.py`의 `ALLOWED`
예외 목록(이미 `redaction.py`가 "보안 규칙이라 도메인 어휘가
불가피하다"는 같은 이유로 올라 있음)에 `app/core/project_config.py`를
정직하게 추가했다 — "재발 금지" 주석과 함께. `ALLOWED` 상한(3개)
안에 들어간다. `python -m pytest tests/architecture -q` **71 passed**로
재확인.

## 검증 결과

명령:

```text
python -m pytest -q tests/e2e/test_composer_write_channel.py -v
13 passed
```

전체 비-live 검증:

```text
python -m pytest -q -m "not live"
385 passed, 3 failed, 3 deselected
```

기준 378 passed 대비 이번 e2e 테스트 3개가 추가되어, 환경 의존 실패를 제외한 통과 수는 증가했다. 실패한 3건은 `tests/integration/rag/test_rag_integration.py`의 OpenAI embedding 호출이며, 실행 환경에서 `api.openai.com:443` 네트워크 연결이 `WinError 10013`으로 차단되어 발생했다. allowlist 변경과 무관하다.

참고로 초기 pytest 실행은 시스템 임시 디렉터리 접근 거부가 있어 작업공간 내부 basetemp로 재실행했다.
