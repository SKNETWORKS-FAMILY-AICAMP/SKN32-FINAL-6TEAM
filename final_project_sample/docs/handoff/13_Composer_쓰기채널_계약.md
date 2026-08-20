# Composer 쓰기 채널 계약 v2

`app.composer_staging.composer_service`(`read_current` / `validate_candidate` /
`apply_candidate`)가 `config/project.yaml`(또는 주입된 대체 경로)을 검증·저장하는
**유일한** 통로다. `GET /composer/current`, `POST /composer/validate`,
`POST /composer/apply`가 이 서비스를 HTTP로 노출한다.

★왜 필요한가 — `/ui/composer` HTML 폼은 `composer_ui` 모듈로 끌 수 있다(릴리스 시
끈다, [[12_introspection_계약]]이 설명하는 것과 같은 이유로 개발자 전용 화면이다).
그런데 Composer는 basement에 남는 **유일한 쓰기 기능**이다 — `final_project_ui`
는 read-only 원칙을 지키므로 대상 저장소 파일을 직접 못 쓴다. 릴리스 이후에도
외부 개발 콘솔이 모듈을 켜고 끄려면 HTML 페이지와 무관하게 사는 쓰기 채널이 있어야
한다. 이 세 엔드포인트는 **`composer_ui` 토글과 무관하게 항상 등록된다**.

Codex 교차검증(`docs/reports/2026-08-17_S-COMPOSER-WRITE-CHANNEL_검토.md`)이
지적한 고정 임시 파일명 충돌, revision 확인 누락, 비원자적 교체 문제는
`composer_service.py`에서 고쳤다. 이 계약 v2에서는 릴리스 후 콘솔 연결을 전제로
인증 계층, 세분화된 scope, 영속 audit, 구현체 allowlist까지 확정한다.

## 인증과 신뢰 경계

### 계층 1 — 사설망(VPN/SSH 터널) 접근

`final_project_ui`와 대상 제품의 Composer API는 사설망 안에서만 통신한다.
공개 인터넷에 이 API를 노출하지 않는다. VPN/SSH 터널은 필요한 네트워크 경계이지
인증 자체를 대체하지 않는다.

### 계층 2 — 실행 시 발급하는 단명 토큰

모든 Composer 요청은 `Authorization: Bearer <token>`을 요구한다. 토큰은 고정 API
키가 아니라 15~60분 TTL의 서명된 JWT이며, 최소한 다음 claim을 가진다.

```json
{"sub": "final_project_ui", "aud": "final_project_sample",
 "scope": ["composer:read", "composer:validate"],
 "iat": 0, "exp": 0, "jti": "..."}
```

`final_project_ui`는 연결할 때마다 `/auth/token` 발급 절차를 통해 새 토큰을 받고,
만료되면 재발급받는다. access token을 코드나 설정 파일에 고정하지 않는다. 토큰은
실행 시점의 별도 채널(예: VPN 내부에서 수행하는 운영자 인증/일회성 발급 절차 또는
환경변수 주입)로 전달하며, 로그·화면·저장소에 남기지 않는다.

우리 규모에서의 구현 선택은 **HMAC 서명 JWT + 간단한 `/auth/token` 발급 엔드포인트**다.
서버만 보유하는 JWT signing secret은 환경변수/실행 환경 secret으로 주입하고,
발급 엔드포인트는 VPN 내부에서 별도의 운영자 확인 또는 짧은 유효기간의 발급
credential을 요구한다. signing secret과 access token을 혼동하지 않는다. secret이
노출되면 즉시 교체하고 기존 토큰 TTL을 짧게 유지한다.

이 방식은 별도 IdP 없이 구현할 수 있고 6명·10주 일정에 맞는다. self-signed 내부 CA와
mTLS는 더 강한 workload identity를 주지만 인증서 발급·배포·회전·폐기 운영을 새로
맡아야 하므로 이번 프로젝트에는 과하다. 운영 환경으로 확대할 때는 OIDC 또는 mTLS로
교체할 수 있도록 claim의 `sub`/`aud`/`scope` 검증 경계는 서비스에 둔다.

### Scope

릴리스 후 외부 콘솔이 붙는 시나리오가 확정됐으므로 세 동작의 권한을 분리한다.
`composer:write` 하나로 모두 허용하면 조회 전용 도구나 검증 자동화가 실제 적용
권한까지 갖게 되어 최소 권한 원칙을 지킬 수 없다.

| 엔드포인트 | 필수 scope | 파일/구성 변경 |
|---|---|---|
| `GET /composer/current` | `composer:read` | 없음 |
| `POST /composer/validate` | `composer:validate` | 없음 |
| `POST /composer/apply` | `composer:write` | 있음 |

발급 토큰은 필요한 scope만 가진다. 예를 들어 상태 표시용 콘솔은 `composer:read`,
검증 화면은 `composer:read` + `composer:validate`, 실제 적용 작업은 명시적으로
`composer:write`를 받아야 한다. `composer:write`가 read/validate를 암묵적으로
허용하지는 않는다.

## 엔드포인트

### `GET /composer/current`

`composer:read`를 요구한다. 현재 파일의 `revision`과 `config`(선언 전체,
`revision` 필드 제외)를 낸다. `apply`를 보내기 전 `base_revision`을 여기서 얻는다.

### `POST /composer/validate`

`composer:validate`를 요구한다.

```json
{"config": {...}}
```

후보 선언을 **canonical loader**(`load_project_config`)로 검증만 한다.
**파일을 바꾸지 않는다.** 활성 Team의 구현체는 요청의 임의 Python 경로를 import하지
않고, 대상 제품이 제공하는 **구현체 registry의 ID**로만 선택한다. 요청의
`implementation_ref`는 registry에 등록된 ID인지 확인하고, registry가 해당 ID에
연결한 사전 등록 callable/모듈만 로드한다. registry 밖의 모듈명·경로·클래스명은
422로 거부한다. 따라서 원격 요청 문자열이 `importlib.import_module`의 입력이 되는
경로를 두지 않는다. registry 변경은 대상 제품 릴리스에 포함된 코드 변경이다.

응답: `{"valid": true, "errors": [], "revision": "..."}` 또는
`{"valid": false, "errors": ["..."]}`.

### `POST /composer/apply`

`composer:write`를 요구한다.

```json
{"config": {...}, "base_revision": "...", "reason": "..."}
```

검증을 통과하고 `base_revision`이 **현재 파일의 revision과 일치할 때만** 원자적으로
쓴다.

- **revision 불일치 → `409 revision_conflict`**(`current_revision` 포함).
  요청 자체는 유효했고 그 사이 파일이 바뀐 것이므로 400이 아니다.
- **검증 실패 → `422 invalid_declaration`**.
- 쓰기는 프로세스 내 lock(`_WRITE_LOCK`) 아래서 임시 파일에 전부 쓴 뒤
  `os.replace()`로 교체한다. 임시 파일명은 요청마다 `uuid4()`를 섞는다.
- 성공 시 이전 파일을 `.yaml.bak`으로 백업하고 새 `revision`을 낸다.
- 성공한 apply마다 아래 audit event를 append한 뒤 성공 응답을 반환한다. audit
  기록 실패는 성공으로 숨기지 않고 명시적 오류로 처리한다.

## Audit 영속 로그

`.yaml.bak`은 직전 상태 복구용일 뿐 이력·행위자 기록이 아니므로 audit의 근거로
사용하지 않는다. MVP에서는 `case_events`와 같은 append-only 원칙을 적용해 대상
제품의 별도 파일 `var/audit/composer_events.jsonl`에 이벤트 한 건을 한 줄씩
추가한다. apply의 구성 파일 교체와 audit append는 같은 writer lock 아래서 수행하고,
append 후 flush한다. 다중 프로세스/다중 인스턴스 운영으로 확장할 때는 이 파일을
append-only DB 테이블로 옮기되 동일한 이벤트 계약을 유지한다.

최소 event shape은 다음과 같다.

```json
{"event": "composer.apply", "actor": "final_project_ui",
 "subject": "...", "timestamp": "2026-08-18T00:00:00Z",
 "previous_revision": "...", "revision": "...",
 "changed_fields": ["teams[0].implementation_ref", "ports.api.enabled"],
 "reason": "...", "correlation_id": "..."}
```

`actor`/`subject`는 JWT의 검증된 `sub` 및 필요 시 `jti`에서 얻고, timestamp는 서버
시간을 사용한다. `changed_fields`는 값·secret·전체 설정을 복사하지 않고 경로와
변경 종류(add/update/remove)만 요약한다. token, signing secret, 임의 파일 경로와
민감한 설정값은 event와 응답에 기록하지 않는다. `read`/`validate`도 필요하면
호출 감사 로그를 남길 수 있지만, 최소 영속 audit의 필수 대상은 mutation인 `apply`다.

## 경계 / 운영 제한

- **단일 프로세스 잠금**이다. 여러 워커·여러 인스턴스에 걸친 잠금은 없다. 이번
  프로젝트에서는 한 writer 인스턴스만 운영하고, 인스턴스가 늘어나면 파일 lock 또는
  DB 조건부 쓰기로 넓힌다.
- API는 VPN/SSH 터널과 Bearer JWT를 모두 요구한다. 브라우저 쿠키를 인증 수단으로
  쓰지 않으며, 브라우저에서 직접 호출하게 할 경우 CORS 허용 origin을 명시적으로
  제한한다.
- 토큰 검증은 signature, `exp`, `aud`, `sub`, scope를 모두 확인한다. 만료·위조·scope
  부족은 각각 적절한 401/403으로 거부한다.

## 테스트 계약

`tests/e2e/test_composer_write_channel.py`는 인증 필요, JWT 만료/위조, 세 scope 분리,
`composer_ui`가 꺼져 있어도 API가 살아 있음, validate가 파일을 안 건드림, registry
밖의 구현체 ID가 422로 거부됨, audit event의 actor/revision/changed_fields 기록,
동일 `base_revision`으로 보낸 동시 apply 2건 중 1건만 200이고 나머지는
409(`revision_conflict`)임을 검증한다.

## 개정 이력

### 2026-08-18 — 릴리스 후 개발 콘솔 보안 계약 확정

- 고정 공유 키를 폐기하고 VPN/SSH 터널 + 실행 시 발급하는 단명 JWT의 2계층 인증을
  추가했다. 학생 프로젝트 규모에는 HMAC JWT를 선택하고 mTLS는 후속 확장으로 남겼다.
- `composer:read`/`composer:validate`/`composer:write` scope를 확정했다.
- `.yaml.bak`을 audit으로 간주하지 않고 append-only JSONL audit event를 정의했다.
- 임의 `implementation_ref` import를 폐기하고 registry ID allowlist를 확정했다.
- final_project_ui는 인증된 Composer API만 호출하고 대상 파일/DB/Python을 직접
  만지지 않는 예외 경계를 문서화할 수 있도록 했다.
## 배포 경계와 운영상 제약

- `_WRITE_LOCK`은 **프로세스 로컬**이다. 배포는 writer 프로세스가 정확히
  하나여야 한다 — 워커나 인스턴스가 여러 개면 이 락을 공유하지 않는다.
  수평 확장을 하려면 먼저 분산 락 또는 DB 조건부 쓰기 경계로 바꿔야 한다.
- `/auth/token`은 공개 JWT 검증 API가 아니라 **운영자가 관리하는 JWT
  발급 endpoint**다. Composer 호출자는 단명 Bearer JWT만 받는다 — 발급
  자격증명과 서명 비밀키는 관리 경계 안에만 머문다.
- 실제 `apply()` 순서는 다음과 같다: `apply_candidate()`가 검증 후
  `_WRITE_LOCK` 아래서 `config/project.yaml`을 원자적으로 교체하고,
  **그 다음** API 핸들러가 `var/audit/composer_events.jsonl`에 audit
  이벤트를 append한다. **이 둘은 하나의 원자적 트랜잭션이 아니다** —
  audit append가 실패해도 config는 이미 적용된 상태이고, API는 오류를
  반환한다.
- `config/project.yaml`을 적용해도 **이미 떠 있는 프로세스가 그 상태를
  자동으로 재로드한다는 보장은 없다.** 재시작·reload endpoint·polling
  중 무엇을 쓸지는 운영 판단이며, 이 계약은 그것을 의도적으로 정하지
  않는다.
