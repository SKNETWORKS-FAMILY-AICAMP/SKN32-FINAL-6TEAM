# Composer 쓰기 채널 포팅 리포트

## 변경 파일

- `app/application/composer_service.py`: 현재 선언 조회, 임시 파일 기반 검증, revision 비교, `.yaml.bak` 백업 및 `os.replace()` 원자적 적용.
- `app/presentation/composer_auth.py`: issuer 비밀값으로 토큰을 발급하고 HMAC `HS256` JWT를 검증하는 별도 인증 채널.
- `app/presentation/api/composer.py`: `composer:read`, `composer:validate`, `composer:write` scope를 사용하는 세 endpoint.
- `app/presentation/api/app.py`: Composer 인증/쓰기 router를 항상 등록.
- `app/core/settings.py`, `.env.example`, `config/guardrails.yaml`: Composer secret 설정, scope, 30분 TTL 추가.
- `tests/e2e/test_composer_write_channel.py`: 만료 토큰, 위조 signature, token 발급/current 조회, 동시 apply 409 테스트.

## sample과 의도적으로 다른 부분

이 저장소의 `ProjectConfig`에는 sample의 `revision` 필드와 `KNOWN_IMPLEMENTATION_REFS`가 없으므로 sample 모델을 import하지 않았다. 대신 이 저장소의 `load_project_config()`로 후보를 검증하고, 현재 모델의 canonical JSON을 SHA-256 해시해 revision을 계산한다. active Team 구현 검증은 이 저장소 loader의 기존 import 검증을 그대로 사용한다. JWT audience는 저장소 식별자에 맞춰 `final_project_cs`로 두었다.

기존 `.env`는 수정하지 않았다. 새 Settings 필드는 빈 기본값으로 추가했고, `.env.example`에는 placeholder만 기록했다.

## 테스트 실행 결과

새 테스트만 실행:

```text
python -m pytest tests/e2e/test_composer_write_channel.py -q
....                                                                     [100%]
4 passed, 8 warnings in 1.50s
```

전체 suite 실행(실행 환경의 임시 디렉터리 접근 제한 때문에 저장소 내부 TEMP 지정, cacheprovider 비활성화):

```text
python -m pytest tests -q -p no:cacheprovider
........................................................................ [ 24%]
........................................................................ [ 48%]
..........................................................FFF.F......... [ 72%]
.....FFF................................................................ [ 96%]
............                                                             [100%]
293 passed, 7 failed, 2 deselected, 8 warnings in 27.77s
```

7개 실패는 이번 변경과 무관한 기존 RAG/tiktoken 테스트가 `api.openai.com` 또는 `openaipublic.blob.core.windows.net`에 접근하려다 sandbox 네트워크 차단을 받은 것이다. Composer 신규 테스트 4개는 모두 통과했다.

## 실제 서버 확인

포트 8073에서 uvicorn을 실행한 뒤 issuer secret으로 토큰을 발급하고 current를 조회했다. 로그에 비밀값이 남지 않도록 access token 문자열은 리포트에서 마스킹했다.

```text
POST /auth/token -> 200 {"access_token":"<redacted>","token_type":"bearer","expires_in":1800}
GET /composer/current -> 200 {"revision":"72e6ac0674d1fc9ebcb2fbf3fb4e1473f7cb924dd6daa77ca1c0fda27607d074","config":{"modules":{...},"ports":{...},"teams":[...]}}
```

확인 후 서버 job은 종료했다.
