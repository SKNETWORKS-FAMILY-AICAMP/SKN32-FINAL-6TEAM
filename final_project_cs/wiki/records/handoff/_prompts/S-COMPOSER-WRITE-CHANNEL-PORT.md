# 구현 지시 — Composer 쓰기 채널을 final_project_sample에서 이식

## 0. 배경 — 왜 지금 이게 없으면 안 되나

이 저장소(`final_project_cs`)에서 오늘(2026-08-18) `app/presentation/ui/composer.py`
(`/ui/composer` HTML 폼)를 완전히 제거했다 — 인증 없이 고객 접근 가능한 이 앱에
물려 있던 것을 실측으로 확인했기 때문이다(`wiki/records/handoff/09_Composer_GUI_계약.md`
상단 배너 참고).

그런데 확인해보니 **이 저장소엔 인증된 `/composer/*` API가 애초에 없다** —
`app/application/composer_service.py`도, `app/presentation/api/composer.py`도,
`app/presentation/composer_auth.py`도 없다. 그 결과 지금 이 저장소는 module/Team/Port
구성을 원격에서 바꿀 방법이 **전혀 없다.** 별도 프로그램 `final_project_ui`가
그 API를 호출해 구성을 바꾸는 구조인데, 부를 API 자체가 없다.

`final_project_sample`(basement, 같은 루트의 형제 저장소)엔 이미 완성된 구현이
있다 — 그걸 이식한다.

## 1. ★먼저 읽을 파일

이 저장소는 주석이 한글이다. **넓게 훑지 마라.**

이 저장소(포팅 대상):
```
app/composition.py
app/core/project_config.py
app/presentation/api/app.py
app/presentation/security.py
config/guardrails.yaml
config/project.yaml
```

`final_project_sample`(포팅 원본 — **읽기만 한다, 이 저장소 파일은 절대 안 건드린다**):
```
C:\Users\playdata2\Documents\final_workspace\final_project_sample\app\application\composer_service.py
C:\Users\playdata2\Documents\final_workspace\final_project_sample\app\presentation\api\composer.py
C:\Users\playdata2\Documents\final_workspace\final_project_sample\app\presentation\composer_auth.py
C:\Users\playdata2\Documents\final_workspace\final_project_sample\app\core\settings.py
C:\Users\playdata2\Documents\final_workspace\final_project_sample\config\guardrails.yaml
C:\Users\playdata2\Documents\final_workspace\final_project_sample\docs\handoff\13_Composer_쓰기채널_계약.md
C:\Users\playdata2\Documents\final_workspace\final_project_sample\tests\e2e\test_composer_write_channel.py
```

## 2. 만들 것 — sample의 구현을 이 저장소 구조에 맞춰 이식

### 2-1. `app/application/composer_service.py`
sample과 같은 책임: `read_current`·`validate_candidate`·`apply_candidate`.
검증은 이 저장소의 `load_project_config`(`app/core/project_config.py`)를 쓴다 —
sample의 `ProjectConfig`를 import하지 마라, **이 저장소 자신의** 모델을 쓴다.
revision 불일치 시 `RevisionConflict`, 원자적 쓰기(`os.replace`), 성공 시
`.yaml.bak` 백업 — sample과 동일한 안전장치를 전부 가져온다.

### 2-2. `app/presentation/composer_auth.py`
sample과 동일 — `POST /auth/token` 발급, HMAC JWT(`HS256`), TTL은
`config/guardrails.yaml`의 `security.composer_jwt_ttl_minutes`(15~60분, 없으면
이 키를 sample처럼 추가해라). `app/core/settings.py`에 `composer_jwt_secret`·
`composer_issuer_secret` 필드를 추가한다(sample의 `Settings` 클래스 참고,
env prefix는 이 저장소 기존 관례를 따른다 — `.env.example`에 있는 접두사 확인해라).

### 2-3. `app/presentation/api/composer.py`
sample과 동일 — `GET /composer/current`(`composer:read`), `POST /composer/validate`
(`composer:validate`), `POST /composer/apply`(`composer:write`). `require_composer_scope`는
2-2에서 만든 것을 쓴다(이 저장소의 옛 `security.require_scope`가 아니다 — sample도
Composer는 별도 JWT 인증 체계를 쓴다, 나머지 API(`ops:introspect` 등)는 그대로 둔다).

### 2-4. `app/presentation/api/app.py`에 등록
`composer_write_router`·`composer_auth_router`를 `include_router` — sample의
`app.py` 56~60줄 패턴을 따른다. `composer_ui` 토글과 무관하게 **항상** 등록한다
(이 저장소엔 애초에 `composer_ui` 모듈 자체가 없다 — 그냥 항상 켠다).

### 2-5. `config/guardrails.yaml`
`security.scopes`에 `composer:read`·`composer:validate`·`composer:write` 추가
(sample의 목록 참고). `security.composer_jwt_ttl_minutes` 추가.

### 2-6. `.env.example`
`ACOP_COMPOSER_JWT_SECRET`·`ACOP_COMPOSER_ISSUER_SECRET`(또는 이 저장소의 실제
env prefix) 자리를 추가한다 — sample의 `.env.example`을 참고하되 **실제 비밀값을
적지 마라**, placeholder만.

## 3. ★지킬 것

| 규칙 | 이유 |
|---|---|
| **sample 파일을 절대 안 건드린다** | 읽기 전용 참고다 — 이식 작업이 그쪽 저장소를 건드리면 안 된다 |
| **이 저장소의 `ProjectConfig`를 쓴다** | sample 모델을 import하면 두 저장소가 몰래 결합된다 |
| **JWT 만료/위조 테스트를 반드시 포함한다** | sample의 `test_expired_token_is_rejected`·`test_forged_signature_is_rejected`와 동등한 테스트를 이 저장소에도 만든다 |
| **동시 apply 409 테스트 포함** | sample의 `test_concurrent_apply_one_wins_one_gets_409`와 동등하게 |
| **가짜 비밀값을 커밋하지 마라** | `.env.example`엔 placeholder만, 실제 `.env`는 건드리지 마라(gitignore 대상) |

## 4. 완료 조건 — ★출력으로 증명하라

```powershell
cd C:\Users\playdata2\Documents\final_workspace\final_project_cs
python -m pytest tests -q
```
★기대: **281 → 늘어난다.** 0 failed. 늘어난 숫자와 원문을 리포트에 적어라.

그리고 **실제로 서버를 띄워 확인하라**:
```powershell
$env:PORT="8073"
python -m uvicorn app.presentation.api.app:app --port 8073
```
`/auth/token`으로 토큰 발급 → `/composer/current`로 현재 config 조회가 실제로
되는지 원문을 붙여라. 확인 후 서버를 종료하라.

## 5. 리포트

`wiki/records/reports/2026-08-18_S-COMPOSER-WRITE-CHANNEL-PORT_리포트.md`
— 만든 파일 목록, 테스트 증가 수, §4 실행 원문, sample과 의도적으로 다르게 만든 부분(있다면 이유와 함께).

## 6. 하지 말 것
- ❌ `final_project_sample`의 파일을 수정
- ❌ `final_project_sample`의 `ProjectConfig`/모델을 import
- ❌ 실제 비밀값을 `.env.example`이나 코드에 하드코딩
- ❌ 테스트 수가 그대로인 채 "완료"
- ❌ 띄워보지 않고 "완료"
