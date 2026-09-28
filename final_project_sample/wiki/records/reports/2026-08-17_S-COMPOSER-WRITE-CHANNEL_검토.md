# Composer 쓰기 채널 검토 리포트

## 결론

Composer는 `basement`의 쓰기 API를 정식 채널로 만들고, `final_project_ui`는 그 API를 호출하는 얇은 화면으로 분리하는 방향이 맞다. 다만 현재 저장 경로를 그대로 HTTP API로 노출하면 안 된다. 먼저 다음 계약을 확정해야 한다.

1. `POST /composer/validate`: 입력 선언을 검증하고 후보 구성과 오류만 반환한다. 파일을 변경하지 않는다.
2. `POST /composer/apply`: `base_revision`을 필수로 받아 서버의 현재 revision과 일치할 때만 적용한다. 성공 시 새 revision과 적용 결과를 반환한다.
3. 두 API 모두 `composer:read`/`composer:write`처럼 읽기와 쓰기 권한을 분리하고, 대상 인스턴스 식별자와 테넌트 경계를 서버 측에서 확정한다.
4. 실제 적용은 단일 writer 또는 저장소 기반 lock/transaction을 통해 원자적으로 수행한다.

현재 구현은 `/ui/composer`의 HTML POST가 `project.yaml`을 직접 수정하는 임시 제품 내부 도구에 가깝다. `/introspection`은 이미 별도의 인증된 read-only JSON 표면이므로, 이것을 쓰기 채널의 기반 계약으로 재사용하기보다 같은 구성 모델을 공유하는 별도 write API를 추가하는 편이 경계가 명확하다.

## 1. HTML과 API의 분리 방향

권장 흐름은 다음과 같다.

```text
final_project_ui
    ├─ GET /introspection                 상태 조회
    ├─ POST /composer/validate            후보 검증
    └─ POST /composer/apply               승인된 후보 적용
                                             │
                                             ▼
                                      basement writer
                                      ProjectConfig + 저장소
```

현행 `/ui/composer`는 화면 렌더링과 YAML 파싱/검증/백업/파일 쓰기를 한 라우터에 함께 둔다 (`app/presentation/ui/composer.py:232-278`). 이 구조는 초기 운영 화면으로는 동작하지만, 별도 콘솔이 생긴 뒤에는 화면이 저장 정책을 소유하게 만든다. API-first로 전환하되, 마이그레이션 중에는 기존 HTML 화면이 새 API의 내부 호출자가 되도록 하면 기존 화면과 외부 콘솔의 동작을 한 계약으로 수렴시킬 수 있다.

`final_project_ui`가 `Composer HTML`을 운영 중 직접 임베드하는 선택지는 권장하지 않는다. 임베드는 인증 쿠키, CSRF, 같은 프로세스 의존성, 릴리스 결합을 다시 만든다. 화면은 API의 입력/출력 계약만 의존해야 한다.

## 2. 쓰기 API가 만드는 공격 표면과 통제

### Scope

현재 `/introspection`은 `ops:introspect` 인증을 사용한다 (`app/presentation/api/app.py:48-50`). 구성 변경에는 이 scope를 재사용하면 안 된다. 최소한 다음을 분리해야 한다.

- 조회: `ops:introspect` 또는 `composer:read`
- 후보 검증: `composer:validate` 또는 read 권한과 동일한 별도 정책
- 파일 적용: `composer:write`

특히 `validate`가 import 및 구현체 검증을 수행하므로 단순 문자열 검사와 같은 권한으로 취급할지 결정해야 한다. 외부 입력으로 활성 Team의 `implementation_ref`를 import하는 현재 검증 (`app/core/project_config.py:116-153`)은 서버 프로세스에서 코드 로딩을 유발한다. 적용 API에서는 허용된 모듈/클래스 allowlist를 두고, 임의 Python 경로를 원격 입력으로 허용하지 않는 것이 안전하다.

### 기본값과 인스턴스별 상태

복제된 인스턴스에서 `composer_ui`와 `a2a_executor`가 기본적으로 꺼져 있어야 한다는 원칙은 타당하다. 다만 설정 파일의 모듈 플래그만으로는 부족하다. API를 노출하는 앱이 실제 writer인지, read-only replica인지 서버 시작 시 명시적으로 선언하고, replica에서는 write route 자체가 등록되지 않거나 항상 거부되어야 한다.

### 재검증

클라이언트가 보낸 `base_revision`은 권한 검사를 대체하지 않는다. apply 직전에 서버가 현재 파일/저장소를 다시 읽고, schema·활성 Team import·지원 port를 재검증해야 한다. 현재 HTML POST도 canonical loader로 후보를 검증하지만 (`composer.py:267-269`), 검증 이후 현재 원본이 바뀌었는지 확인하지 않고 곧바로 쓴다 (`composer.py:270-273`).

## 3. 동시 편집과 revision

현재 `ProjectConfig.revision`은 선언 내용의 canonical JSON hash로 계산되어 추적성에는 적합하다 (`app/core/project_config.py:65-82`). 그러나 이것만으로 동시 편집을 막지는 못한다. 두 요청이 같은 revision을 읽으면 둘 다 같은 후보를 검증한 뒤 마지막 쓰기가 앞선 변경을 덮어쓴다.

따라서 `apply` 요청은 다음을 가져야 한다.

```json
{
  "base_revision": "현재 조회에서 받은 12자리 revision",
  "config": { "modules": {}, "ports": {}, "teams": [] },
  "reason": "변경 사유"
}
```

서버는 lock 또는 저장소 transaction 안에서 `current_revision == base_revision`을 확인하고, 불일치하면 `409 revision_conflict`를 반환해야 한다. 성공 응답에는 `previous_revision`, `revision`, `applied_at`, `actor`를 포함한다. 화면은 409를 받은 뒤 자동 덮어쓰기를 하지 말고 최신 구성과 diff를 보여줘야 한다.

현재 테스트는 revision 계산의 안정성은 확인하지만 (`tests/unit/core/test_config_revision.py`), 같은 base revision을 가진 두 apply 요청 중 하나만 성공해야 한다는 계약은 없다.

## 4. 멀티 인스턴스 관리

현재 `project_config_path`는 앱 상태 또는 기본 로컬 경로에서 선택되고 (`app/presentation/ui/__init__.py:26-29`, `composer.py:151-154`), 적용은 해당 프로세스의 로컬 파일을 직접 쓴다. 이 방식은 단일 프로세스에는 맞지만, 여러 제품/프로젝트 인스턴스를 관리하는 API의 대상 모델로는 부족하다.

쓰기 요청에는 적어도 다음이 필요하다.

- `instance_id` 또는 명시적인 대상 리소스 URI
- 대상 인스턴스의 writer endpoint/등록 정보
- 대상 인스턴스가 반환한 현재 revision
- 호출자 identity, tenant, scope, audit correlation id
- 대상 불일치·offline·replica 상태에 대한 명시적 오류

`instance_id`를 경로로 받아 서버가 임의 파일 경로로 조합하는 방식은 피해야 한다. 서버 측 registry가 instance ID를 canonical endpoint와 연결하고, 해당 endpoint가 자신이 가진 구성의 revision을 서명된 응답으로 돌려주는 구조가 적합하다. 단일 저장소를 공유하는 경우에는 파일이 아니라 DB/객체 저장소의 조건부 쓰기를 writer 계약으로 삼아야 한다.

## 5. 현재 구현에서 확인된 쓰기 경로의 위험

### 원자성 부족

현재는 후보 임시 파일 작성 → 후보 로드/검증 → `.bak` 작성 → 원본 `write_bytes` 순서다 (`composer.py:267-274`). 원본 쓰기 중 프로세스가 중단되면 partial YAML이 남을 수 있다. 임시 파일은 대상 디렉터리에서 생성하고 fsync 후 atomic replace해야 하며, 백업 정책과 복구 규칙도 API 계약에 포함해야 한다.

### 고정 임시 파일명과 경쟁

`with_suffix(".composer.validation.yaml")`은 요청마다 같은 경로를 사용한다. 동시 요청이 있으면 서로의 후보를 덮어쓰거나, 한 요청이 다른 요청의 임시 파일을 삭제할 수 있다. 요청별 고유 임시 파일과 lock이 필요하다.

### 오류/실패 후 상태

백업 생성과 원본 교체가 서로 다른 단계라 백업은 성공했지만 원본 교체가 실패하는 상태를 별도로 처리해야 한다. 현재 HTML 경로는 예외를 화면에 표시하지만 재시도용 operation id나 서버 감사 기록은 없다.

### 브라우저 쓰기 보호

HTML POST가 브라우저 세션/쿠키 기반으로 운영될 경우 CSRF 방어가 필요하다. API를 bearer token으로 보호하더라도 외부 콘솔의 토큰 보관 방식과 CORS 정책을 명시해야 한다. 현재 Composer 라우터에는 별도의 write scope 또는 CSRF 검사가 보이지 않는다 (`composer.py:243-278`).

### 구성 입력의 범위

`active=true` Team은 `implementation_ref`를 동적으로 import한다. 이는 단순 설정 편집을 넘어 서버 코드 실행 경로에 가까우므로, 제품 API에서는 선언 가능한 구현체 목록을 registry에서 제공하고 그 목록의 ID만 받는 방식이 바람직하다.

## 6. API 계약에 반드시 포함할 응답/오류

검증 성공은 `valid`, normalized candidate, warnings, `base_revision`을 반환해야 한다. 검증 실패는 필드 경로별 오류를 반환해야 한다. 적용은 다음 오류를 구분해야 한다.

- `401/403`: 인증 또는 scope 부족
- `404`: 알 수 없는 instance/module
- `409`: revision 충돌 또는 replica/read-only 대상
- `422`: schema/사업 규칙/허용되지 않은 구현체 오류
- `503`: writer 또는 대상 인스턴스가 준비되지 않음
- `500`: 적용 중 rollback 여부를 포함한 내부 오류

성공/실패 모두 secret, customer message, 임의 파일 경로를 반환하지 않아야 한다. `/introspection`이 이미 redaction과 versioned shape를 계약으로 갖고 있으므로, Composer write API도 별도 `contract_version`과 구조화된 error code를 가져야 한다.

## 7. 권장 구현 순서

1. `ProjectConfig`를 입력/정규화/검증하는 application service와 canonical 저장 writer를 정의한다.
2. `validate`와 `apply`의 JSON 계약, scope, instance 대상, 오류 코드를 먼저 고정한다.
3. `apply`에 revision 조건부 쓰기와 단일 writer/lock, atomic replace, audit event를 구현한다.
4. 기존 `/ui/composer` POST는 직접 파일을 쓰지 않고 위 service/API를 호출하게 바꾼다.
5. `final_project_ui`는 `/introspection` 조회와 Composer validate/apply API만 사용한다.
6. 다음 테스트를 추가한다: 동시 apply 2건의 1건 성공/1건 409, replica write 거부, scope 분리, CSRF/CORS, crash 중 atomicity, 임의 implementation_ref 거부, 대상 instance 불일치, audit/redaction.

## 검토 범위와 실행 결과

- 검토 대상: `app/core/project_config.py`, `app/presentation/ui/composer.py`, `app/presentation/ui/__init__.py`, `app/presentation/api/app.py`, `app/presentation/security.py`, 관련 Composer/introspection/revision 테스트
- 실행: `pytest -q tests/e2e/test_composer_ui.py tests/e2e/test_composer_structure.py tests/e2e/test_introspection_endpoint.py tests/contracts/test_introspection_contract.py tests/security/test_scope_contract.py tests/unit/core/test_config_revision.py`
- 결과: **29 passed** (pytest cache 디렉터리 권한 경고 1건)
- 이번 작업에서는 코드 파일을 변경하지 않았다.
