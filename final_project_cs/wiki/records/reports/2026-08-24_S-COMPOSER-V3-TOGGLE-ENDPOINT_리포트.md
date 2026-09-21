# S-COMPOSER-V3-TOGGLE-ENDPOINT 구현 리포트

## 구현 결과

- `app/introspection/contract.py`
  - `config_revision`을 `composer_service.revision(config)`의 실제 SHA-256 digest로 변경했다.
  - 최상위 `registered_ids`를 추가했다.
  - modules는 `config.modules`의 전체 키, teams는 선언된 모든 `team_id`, ports는 고정 빈 리스트를 반환한다.
- `app/application/composer_service.py`
  - `_WRITE_LOCK` 안에서 등록 확인 → revision 충돌 검사 → 단일 flag 변경 → 재로드 순서로 동작하는 `toggle_target()`을 추가했다.
  - 현재 YAML의 대상 `enabled` 또는 `active` 필드 하나만 수정하고, `.bak` 백업·staged 파일·`os.replace()`를 사용한다.
- `app/presentation/api/composer.py`
  - `POST /composer/toggle`을 추가했다.
  - 기존 `composer:write` scope, `ProjectConfigError` 422, `RevisionConflict` 409, 감사 실패 500 패턴을 재사용했다.
  - 감사 이벤트는 `composer.toggle`로 `composer_events.jsonl`에 기록한다.
- 테스트
  - module/team 정상 토글, revision 변경, 파일 반영, 단일 감사 로그, 미등록 module/port, stale revision, scope 거부, 비대상 선언 보존을 검증했다.
  - introspection의 등록 ID와 실제 config, 빈 ports, 실제 revision을 검증했다.

v2의 `/composer/validate` 및 `/composer/apply`와 기존 scope/ProjectConfig 계약은 변경하지 않았다.

## 검증 결과

지정 테스트:

```text
22 passed
```

전체 비-live 테스트:

```text
393 passed, 3 failed, 3 deselected
```

기준치 389 passed 대비 새 검증 케이스 반영으로 통과 수는 4건 증가했다.

실패한 3건은 기존 RAG integration 테스트가 `api.openai.com` 임베딩 API를 호출하는 항목으로, 실행 환경의 외부 네트워크 차단(`WinError 10013`)으로 실패했다. 토글/introspection 관련 지정 테스트 및 구현 경로의 실패는 없다.
