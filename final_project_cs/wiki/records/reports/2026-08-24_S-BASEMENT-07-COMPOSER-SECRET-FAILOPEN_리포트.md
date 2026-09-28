# S-BASEMENT-07-COMPOSER-SECRET-FAILOPEN 수정 리포트

## 변경 사항

- `app/core/settings.py`에서 `composer_jwt_secret`와 `composer_issuer_secret`의 빈 문자열 기본값을 제거했다.
- 두 필드를 다른 필수 설정값과 동일한 필수 필드로 변경했다.
- `app/presentation/composer_auth.py`, `.env`, `final_project_sample/`, `tests/e2e/test_composer_write_channel.py`는 수정하지 않았다.
- `.env.example`에 두 환경변수가 이미 문서화되어 있음을 확인했다.

## 회귀 테스트

신규 테스트 `tests/unit/core/test_settings_composer_secrets.py`에서 다음을 검증한다.

- 두 Composer 시크릿 환경변수가 없으면 실제 `Settings(_env_file=None, ...)` 생성이 `pydantic.ValidationError`로 실패한다.
- 두 값이 설정되면 `Settings`가 정상 생성되고 값을 읽는다.

전체 테스트 실행 결과:

```text
명령: python -m pytest -q -m "not live"
결과: 366 passed, 4 failed, 3 deselected, 11 errors in 72.49s
```

전체 스위트의 실패/오류 원인은 이번 설정 변경이나 Composer 시크릿 부재가 아니었다.

- 4건의 RAG 실패는 샌드박스에서 `api.openai.com` 연결이 차단되어 발생했다.
- 11건의 오류 중 Composer e2e 및 holdout 테스트는 pytest 임시 디렉터리
  `C:\Users\playdata2\AppData\Local\Temp\pytest-of-playdata2`에 대한
  `PermissionError (WinError 5)`로 셋업 단계에서 실패했다.
- architecture 테스트 1건은 기존 `app/core/project_config.py`의 도메인 모듈
  경로 문자열을 탐지해 실패했다.

신규 단위 테스트 단독 실행 결과는 `2 passed`였다.
