# S-COMPOSER-V2-JWT — Composer 쓰기채널 v2 구현 (JWT 인증·scope 3분화·registry allowlist·audit)

## 계약 — 반드시 먼저 읽는다

`wiki/records/handoff/13_Composer_쓰기채널_계약.md` **전체**를 읽고 그대로 구현한다.
이번엔 리포트가 아니라 **실제 구현**이다. 이 프롬프트는 계약의 핵심을
요약한 것일 뿐 계약 문서가 우선한다.

## 배경 — 지금 상태

`app/application/composer_service.py`(검증·원자적 쓰기),
`app/presentation/api/composer.py`(`/composer/current`, `/composer/validate`,
`/composer/apply`)가 이미 있다. 지금은 `composer:write` scope 하나로 세
엔드포인트를 다 지킨다. 인증은 `app/presentation/security.py` 의
`_development_key()`(HMAC, TTL 없는 고정 방식)를 쓴다. 이걸 계약 v2로
업그레이드한다.

## 구현할 것

### 1. JWT 인증 (`app/presentation/security.py` 확장 또는 새 파일 `app/presentation/composer_auth.py`)
- `PyJWT` 를 쓴다 — 이미 이 환경에 설치돼 있다(`pip show pyjwt` → 2.13.0).
  `requirements.txt` 에 `PyJWT==2.13.0` 을 추가한다(지금 안 적혀 있다).
- HMAC(`HS256`) 서명. signing secret 은 `app.core.settings` 를 통해
  환경변수로 주입한다(예: `ACOP_COMPOSER_JWT_SECRET`) — **하드코딩 금지**
  (RULE.md §3.1). `.env.example` 에 항목을 추가한다.
- `POST /auth/token` 발급 엔드포인트를 새로 만든다. 계약은 "VPN 내부에서
  별도의 운영자 확인 또는 짧은 유효기간의 발급 credential 을 요구한다"고
  적었다 — 이 규모에서는: 발급 요청 자체도 인증돼야 한다(누구나 토큰을
  못 받아가게). 발급 요청 바디에 `{"sub": "...", "scope": ["composer:read", ...]}`
  와 함께, signing secret 을 아는 사람만 호출 가능하도록 별도의 발급용
  secret(`ACOP_COMPOSER_ISSUER_SECRET`, signing secret 과 다른 값)을
  `Authorization: Bearer <issuer_secret>` 로 요구한다. 발급된 access
  token 의 TTL 은 `config/guardrails.yaml` 에 새 값으로 추가한다
  (예: `security.composer_jwt_ttl_minutes: 30`, 15~60 사이 — RULE.md §3.1,
  수치를 코드에 박지 않는다).
- claim: `sub`, `aud`("final_project_sample" 고정), `scope`(배열), `iat`,
  `exp`, `jti`(uuid4).
- `/composer/*` 세 엔드포인트는 이제 `Authorization: Bearer <JWT>` 를
  요구하고, signature·`exp`·`aud`·`sub` 존재·필요 scope 를 전부 검증한다.
  실패 시 401(서명/만료 문제) 또는 403(scope 부족).

### 2. Scope 3분화
- `config/guardrails.yaml` 의 `security.scopes` 에 `composer:read`,
  `composer:validate` 를 추가한다(`composer:write` 는 유지 — apply 전용).
- `GET /composer/current` → `composer:read`
- `POST /composer/validate` → `composer:validate`
- `POST /composer/apply` → `composer:write`
- 셋은 서로를 암묵적으로 포함하지 않는다 — `composer:write` 만 있고
  `composer:read` 가 없는 토큰은 `/composer/current` 를 못 부른다.

### 3. `POST /composer/apply` 에 `reason` 필드 추가
`ApplyPayload` 에 `reason: str = Field(min_length=1)` 를 추가한다(필수).
왜 이 변경을 적용하는지 사람이 남기는 자유 텍스트다.

### 4. Registry ID allowlist — 임의 `implementation_ref` import 경로 폐기
지금 `app/core/project_config.py::_validate_active_team_implementations()`
는 요청이 들어온 `implementation_ref` 문자열을 그대로
`importlib.import_module()` 에 넘긴다(설치된 모듈만 로드되긴 하지만, 원격
요청 문자열이 import 대상을 직접 고른다). 계약 v2 는 이걸 막는다.

- **로컬 파일 편집 경로(`load_project_config()` 자체, `/ui/composer` HTML
  폼)는 손대지 않는다** — 이미 신뢰된 로컬 파일 편집 경로다.
- **Composer HTTP API(`/composer/validate`, `/composer/apply`)에만** 추가
  방어선을 둔다: 새 상수 `KNOWN_IMPLEMENTATION_REFS`(`app/core/project_config.py`
  가 적절한 위치)를 만들어 지금 실제로 존재하는 구현체를 전부 등록한다
  (`app.modules.customer_ops:BillingSubscriptionTeam`,
  `app.modules.customer_ops:TechnicalEntitlementTeam`,
  `app.modules.customer_ops.feedback_team:FeedbackAnalyticsTeam`,
  `app.modules.placeholder:PlaceholderTeam` — 실제 저장소를 grep 해서
  빠진 게 없는지 확인한다).
- `composer_service.validate_candidate()`/`apply_candidate()` 가
  `load_project_config()` 를 부르기 **전에**, `raw["teams"]` 의 각
  `active: true` 항목의 `implementation_ref` 가 이 allowlist 에 있는지
  확인한다. 없으면 `ValidationResult(valid=False, errors=[...])` 또는
  `ProjectConfigError` 로 422 거부 — `importlib.import_module` 을 아예
  안 태운다.

### 5. Audit 영속 로그
- `var/audit/composer_events.jsonl`(저장소 루트 기준 상대 경로, 없으면
  생성) 에 `apply` 성공마다 한 줄 append.
- 이벤트: `{"event":"composer.apply","actor":<JWT sub>,"subject":<대상
  선언 경로>,"timestamp":<서버 시각 ISO8601>,"previous_revision":...,
  "revision":...,"changed_fields":[...],"reason":<request.reason>,
  "correlation_id":<요청마다 uuid4>}`.
- `changed_fields` 는 이전 config 와 새 config 를 얕게 비교해 바뀐 경로만
  담는다(값은 안 담는다) — 예: `["teams[1].active", "modules.voc.enabled"]`.
  간단한 재귀 dict-diff 헬퍼를 만들어도 된다.
- append 실패(디스크 오류 등)는 **apply 성공을 감추지 않는다** — append
  가 실패하면 그 사실을 명시적 500 오류로 알리고, 이미 쓴
  `config/project.yaml` 변경 자체는 롤백하지 않는다(파일 쓰기는 이미
  끝났다 — audit 실패와 별개다. 응답에 "config는 적용됐지만 audit 기록에
  실패했다"는 걸 명확히 전달한다).

## 하지 않을 것
- mTLS·OIDC 는 이번 범위 밖(계약이 명시적으로 후속 확장으로 미뤘다)
- 다중 프로세스/다중 인스턴스 락은 이번 범위 밖(계약이 명시)
- `app/core/**` 는 건드리지 않는다(basement 순수성 — 이 작업은 전부
  `app/presentation/**`, `app/application/composer_service.py`,
  `app/core/project_config.py` 안에서 끝난다)

## 테스트
`tests/e2e/test_composer_write_channel.py` 를 갱신·확장한다:
- 인증 없음 → 401, 만료된 JWT → 401, 위조 서명 → 401, scope 부족 → 403
- 세 scope 가 서로 분리돼 있는지(read 토큰으로 apply 시도 → 403 등)
- `composer_ui` 꺼져 있어도 API 는 산다(기존 테스트 유지)
- validate 는 파일을 안 건드린다(기존 테스트 유지)
- registry 밖의 `implementation_ref` 를 담은 config 를 validate/apply 에
  보내면 422 로 거부되고, `importlib.import_module` 이 안 불렸는지도
  간접 확인(예: 존재하지 않는 모듈 경로를 보내도 ImportError 가 아니라
  "registry 에 없다"는 메시지로 거부돼야 한다)
- apply 성공 시 `var/audit/composer_events.jsonl` 에 실제로 한 줄이
  추가되고 `actor`/`revision`/`changed_fields`/`reason` 이 들어있는지
- 동일 `base_revision` 으로 보낸 동시 apply 2건 중 1건만 200, 나머지
  409(`revision_conflict`) — 기존 테스트 유지

## 완료 기준
```powershell
python -m pytest -q   # 전체가 통과해야 한다 (2026-08-17 기준 355 passed 에서 시작)
```
`wiki/records/reports/` 에 리포트를 남긴다: 만든/고친 파일 목록, 재현 명령과 실제
출력, `wiki/records/handoff/13` 문서와 실제 구현이 어긋나는 부분이 있으면(있어야
한다면 이유와 함께) 명시한다.
