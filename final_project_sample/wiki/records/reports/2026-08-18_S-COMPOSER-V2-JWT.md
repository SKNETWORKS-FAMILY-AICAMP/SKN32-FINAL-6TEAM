# S-COMPOSER-V2-JWT 구현 리포트

## 변경 내용

- `app/presentation/composer_auth.py`를 추가해 issuer secret으로 보호되는 `/auth/token`, HS256 JWT 발급/검증, `aud`·`sub`·`scope`·`iat`·`exp`·`jti` 검증을 구현했다.
- `app/presentation/api/composer.py`의 세 API를 `composer:read`, `composer:validate`, `composer:write`로 분리하고 `reason` 필수 필드를 추가했다.
- apply 성공 시 `var/audit/composer_events.jsonl`에 actor, revision, changed_fields, reason, correlation id를 JSONL로 append한다. audit append 실패는 500으로 알리되 이미 적용한 config는 유지한다.
- `app/application/composer_service.py`에 HTTP 경로 전용 registry 검사 플래그를 추가했다. 로컬 UI와 canonical loader 경로는 기존처럼 임의 선언을 검증하고, HTTP 후보만 `KNOWN_IMPLEMENTATION_REFS`를 통과시킨다.
- `config/guardrails.yaml`, `app/core/settings.py`, `.env.example`, `requirements.txt`에 scope, TTL, secret 설정, `PyJWT==2.13.0`을 추가했다.
- Composer E2E 및 scope contract 테스트를 JWT와 새 scope 계약에 맞게 갱신했다.

## 검증

```powershell
python -m pytest -q --basetemp .pytest-tmp tests/e2e/test_composer_write_channel.py tests/unit/application/test_composer_service.py tests/security/test_scope_contract.py
```

실제 출력: `9 passed, 1 warning`

```powershell
python -m pytest -q --basetemp .pytest-tmp --ignore=tests/integration/rag
```

실제 출력: `360 passed, 1 deselected, 1 warning`

`python -m pytest -q` 전체 실행은 Composer 관련 테스트를 포함해 통과했으나, `tests/integration/rag`의 3개 테스트가 실행 환경의 네트워크 차단으로 `api.openai.com` 연결 오류를 냈다. 해당 실패는 이번 변경 파일과 무관한 외부 임베딩 의존성이다.

## 계약 차이

문서와 구현 사이에 의도적인 기능 차이는 없다. 계약의 “HTTP API에만 registry allowlist 적용” 조건을 보존하기 위해 서비스 함수에 `enforce_registry` 선택 인자를 두고 API 호출에서만 활성화했다. 따라서 로컬 `/ui/composer`와 `load_project_config()`의 기존 신뢰 경로는 변경하지 않았다.
