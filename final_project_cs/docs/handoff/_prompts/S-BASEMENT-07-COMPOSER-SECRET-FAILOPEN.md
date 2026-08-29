# S-BASEMENT-07-COMPOSER-SECRET-FAILOPEN — Composer JWT 시크릿 fail-open 결함 수정

## 0. 배경 — 지금 이 순간에도 활성인 인증 우회

`app/core/settings.py`(line 51-52):

```python
composer_jwt_secret: str = ""
composer_issuer_secret: str = ""
```

`final_project_sample/acop_basement/core/settings.py`(참고용, **절대 수정
금지**)와 대조하면 sample은 이 두 필드에 기본값이 없다 — 즉 환경변수가
없으면 `Settings()`가 `pydantic.ValidationError`를 던지고,
`get_settings()`(같은 파일)가 이를 `ConfigError`로 바꿔 **앱 기동 자체를
거부**한다. cs는 기본값 `""`이 있어서 환경변수 없이도 정상 기동된다.

이 파일 자신의 모듈 docstring이 이미 이 원칙을 선언하고 있다:

```python
"""...
규칙 (RULE.md §3.1, §3.2):
  - 폴백 금지. 값이 없으면 명시적 예외로 실패한다. 기본값으로 조용히 대체하지 않는다.
"""
```

**실제로 지금 cs의 `.env`에는 이 두 값이 설정돼 있지 않다.** 확인 결과
(Claude가 직접 python-dotenv로 로드해 확인함) `ACOP_COMPOSER_JWT_SECRET`,
`ACOP_COMPOSER_ISSUER_SECRET` 둘 다 값이 비어 있다.

`app/presentation/composer_auth.py::authenticate_composer()`는:

```python
claims = jwt.decode(authorization[7:], get_settings().composer_jwt_secret,
                    algorithms=[ALGORITHM], audience=AUDIENCE, ...)
```

`composer_jwt_secret`이 빈 문자열이면, **빈 문자열을 HMAC 키로 서명한
JWT가 그대로 서명 검증을 통과한다** — 이건 알려진 JWT 위조 기법이다.
`require_composer_scope(...)`로 막아둔 모든 Composer 쓰기채널 엔드포인트
(`/composer/validate`, `/composer/apply`)가 사실상 인증 없이 뚫린다.

`issue_token()`(같은 파일, line 28-32)은 `if not expected or ...` 가드가
있어 빈 시크릿으로 토큰 **발급**은 이미 막혀 있다 — 문제는 **검증** 경로뿐이다.

## 1. 할 일

1. `app/core/settings.py`의 `composer_jwt_secret`/`composer_issuer_secret`
   에서 `= ""` 기본값을 제거해 다른 필수 필드(`database_url`,
   `openai_api_key`, `tenant_id`, `secret_key`)와 같은 방식의 필수
   필드로 만들어라(단순 타입 애노테이션만 남긴다: `composer_jwt_secret: str`).
2. `app/presentation/composer_auth.py`는 건드리지 마라 — `issue_token()`의
   기존 가드는 그대로 유효하고, `authenticate_composer()`는 이제
   `get_settings()` 자체가 실패하므로 별도 수정이 필요 없다.

## 2. `.env` 처리 — 너는 손대지 마라

`.env`는 gitignore 대상이고 실제 로컬 비밀값을 담고 있다. 이 필드를
필수로 바꾸면 값이 없는 한 앱 전체(테스트 포함)가 기동을 거부하게
되는데, **실제 `.env`에 값을 채우는 것은 Claude가 이 계약과 별개로 직접
처리한다.** 너는 `.env` 파일을 읽거나 쓰지 마라 — `.env.example`에는
이미 두 키가 문서화돼 있으니 그것만 확인하고 넘어가라.

## 3. 검증

- 재현 테스트를 새 파일 `tests/unit/core/test_settings_composer_secrets.py`
  에 추가해라(기존 `tests/e2e/test_composer_write_channel.py`는 다른
  작업이 동시에 건드릴 수 있으니 **손대지 마라**):
  - `monkeypatch`로 `ACOP_COMPOSER_JWT_SECRET`/`ACOP_COMPOSER_ISSUER_SECRET`
    를 제거(또는 빈 문자열로 설정)한 환경에서 `Settings()`(또는
    `get_settings()`, `lru_cache` 초기화 순서에 유의해 캐시를 우회하는
    방법을 써라 — 예: `Settings.model_construct` 대신 실제
    `Settings(_env_file=None, **overrides)`를 직접 호출하거나,
    `get_settings.cache_clear()`를 테스트 안에서 호출)를 만들면
    `ConfigError`(또는 그 원인이 되는 `pydantic.ValidationError`)가
    나는지 확인해라.
  - 두 값이 모두 채워진 정상 환경에서는 `Settings()`가 정상 생성되는지도
    확인해라(회귀 없음).
- `python -m pytest -q -m "not live"` 전체 실행 결과를 리포트에 붙여라
  (378 passed 기준 변화 명시). ★주의: 이 계약 적용 후 `.env`에 실제
  값이 없으면 전체 스위트가 대량으로 실패할 수 있다 — Claude가 `.env`를
  먼저 채워둘 것이므로, 만약 네 실행 환경에서 대량 실패가 나면 그 사실과
  실패 개수만 리포트에 정직하게 적고 원인을 "`.env`에 시크릿 없음"으로
  기록해라(다른 원인으로 둘러대지 마라).

## 4. 쓰기 대상

- `app/core/settings.py`
- `tests/unit/core/test_settings_composer_secrets.py` (신규)
- `docs/reports/2026-08-24_S-BASEMENT-07-COMPOSER-SECRET-FAILOPEN_리포트.md` (신규)

## 5. 하지 말 것

- `final_project_sample/` 수정 금지 — 읽기만
- `.env` 읽기·쓰기 금지 (Claude가 별도로 처리)
- `app/presentation/composer_auth.py` 수정 금지 — 이미 올바르다
- `tests/e2e/test_composer_write_channel.py` 수정 금지 — 병렬로 도는
  S-BASEMENT-08 계약이 그 파일을 쓴다
