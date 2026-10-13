===== FILE: write-channel.md =====
---
type: concept
title: Composer의 단일 쓰기 경로
description: 설정 변경을 한 경로로 모으는 이유와 그 경로가 적용 전에 검사하는 조건을 설명한다.
status: draft
tags: [architecture, state, api, testing]
---

# Composer의 단일 쓰기 경로

Composer의 HTTP 명령은 `/composer/apply`, `/composer/changes`, `/composer/toggle`로 나뉘지만, 실제 저장 판정은 `apply_candidate()` 하나로 모인다. [실측] `/changes`와 `/toggle`은 `_perform_change()`를 공유하고, `_perform_change()`와 `/apply`는 모두 `apply_candidate()`를 호출한다. `acop_composer/api.py:202-215`, `acop_composer/api.py:317-332`, `acop_composer/api.py:362-364`, `acop_composer/api.py:415-424`

이 경로를 하나로 유지하는 이유는 검증, revision 충돌 판정, 저장소의 조건부 쓰기를 모든 변경 방식에 동일하게 적용하기 위해서다. [실측] `/toggle`도 별도 저장 구현을 갖지 않고 `/changes`와 같은 경로를 사용한다. `acop_composer/api.py:164-171`

## 변경이 저장되기까지

1. [실측] `/composer/current`가 현재 선언과 `revision`을 반환한다. 쓰기 요청은 이 값을 `base_revision`으로 제출한다. `acop_composer/api.py:392-396`
2. [실측] `/changes`는 현재 선언을 깊은 복사한 뒤 요청 대상 하나만 변경한 후보 선언을 만든다. 모듈과 Team의 존재 여부, 생성 중복, Team 생성 시 `implementation_id` 필요 여부도 이 단계에서 판정한다. `acop_composer/api.py:259-314`
3. [실측] `/toggle`은 `enable` 또는 `disable` 변경 명령으로 변환되어 `_perform_change()`에 들어간다. `acop_composer/api.py:202-215`
4. [실측] `apply_candidate()`는 쓰기 잠금을 잡은 뒤 저장소에서 현재 선언을 다시 읽고, 현재 revision과 요청의 `base_revision`을 비교한다. 다르면 `RevisionConflict`를 발생시킨다. `acop_composer/service.py:137-147`
5. [실측] 후보는 `config_from_declaration()`으로 다시 검증된다. 검증 실패는 저장소의 `write()` 호출 전에 발생한다. `acop_composer/service.py:149-153`
6. [실측] 저장소에는 `base_revision`과 새 revision을 함께 전달한다. 저장소가 `RevisionMismatch`를 반환하면 API 계층에서 409 `revision_conflict`로 변환되는 `RevisionConflict`가 발생한다. `acop_composer/service.py:151-156`, `acop_composer/api.py:365-370`
7. [실측] 저장 성공 후 변경 주체, 대상, 시각, 이전·새 revision, 변경 필드, 사유와 상관관계를 감사 저장소에 기록한다. `/changes`와 `/toggle`은 작업 종류와 인스턴스 정보도 기록한다. `acop_composer/api.py:372-388`, `acop_composer/api.py:432-442`

## 적용 전에 검사하는 것

- [실측] 요청 모델은 선언되지 않은 추가 필드를 거부하며, `reason`과 대상 ID에는 최소 한 글자를 요구한다. 작업과 자원 종류도 허용된 문자열로 제한한다. `acop_composer/api.py:131-160`, `acop_composer/api.py:174-179`
- [실측] 모든 변경 엔드포인트는 `composer:write` scope를 요구한다. 검증 전용 엔드포인트는 `composer:validate`, 현재 선언과 카탈로그 조회는 `composer:read`를 요구한다. `acop_composer/api.py:202-204`, `acop_composer/api.py:228-230`, `acop_composer/api.py:317-319`, `acop_composer/api.py:392-401`, `acop_composer/api.py:415-417`
- [실측] 중앙 설정 서비스에서는 `X-Deployment-Id` 헤더가 비어 있으면 400 `deployment_required`로 거부한다. 파일 방식과 중앙 방식의 저장소 선택도 요청 처리 전에 이루어진다. `acop_composer/api.py:62-96`
- [실측] HTTP 쓰기 경로는 `enforce_registry=True`로 적용한다. 별도 registry 검사는 활성 Team의 `implementation_ref`가 `KNOWN_IMPLEMENTATION_REFS`에 들어 있는지 확인한다. `acop_composer/service.py:62-76`, `acop_composer/api.py:363-364`, `acop_composer/api.py:423-424`
- [실측] 후보 전체는 별도 UI 검증기가 아니라 서버의 `config_from_declaration()`에 전달된다. `/validate`와 실제 적용이 같은 정규 검증 진입점을 사용한다. `acop_composer/service.py:99-121`, `acop_composer/service.py:149-150`
- [미확보] `config_from_declaration()` 내부의 세부 스키마·호환성 규칙은 허용된 파일 범위 밖이므로 이 문서에서 독립적으로 확인하지 않았다.
- [실측] 동일한 `base_revision`으로 동시에 보낸 두 `/apply` 요청 중 하나는 200, 다른 하나는 409가 되어야 한다는 E2E 검사가 있다. `tests/e2e/test_composer_write_channel.py:187-234`
- [실측] 알 수 없는 구현 참조는 422로 거부되고 선언 파일은 그대로 남아야 한다는 E2E 검사가 있다. `tests/e2e/test_composer_write_channel.py:171-184`

## 쓰지 않는 경로

[실측] `/composer/validate`는 후보를 검증하고 결과와 계산된 revision만 반환한다. 저장소에 쓰지 않는다. `acop_composer/api.py:399-412`

[실측] `/changes`의 `dry_run`도 후보를 검증하지만 `apply_candidate()`를 호출하지 않는다. 응답의 `desired_revision`은 기존 revision이며 파일 내용과 수정 시각이 유지되어야 한다는 검사가 있다. `acop_composer/api.py:352-360`, `tests/e2e/test_composer_catalog_changes.py:100-112`

## 확인된 한계

[실측] `_WRITE_LOCK`은 단일 프로세스 안의 동시 쓰기만 직렬화한다. 여러 워커나 여러 인스턴스 사이의 최종 충돌 판정은 저장소의 조건부 쓰기에 맡긴다. `acop_composer/service.py:41-44`, `acop_composer/service.py:142-156`

[미확보] 파일 저장소와 PostgreSQL 저장소가 물리적으로 어떤 원자적 연산을 사용하는지는 허용된 파일 범위에서 확인하지 않았다.

[실측] 감사 기록은 설정 저장 뒤에 실행된다. 감사 저장이 실패하면 API는 500 `audit_failure`를 반환하지만 오류 메시지는 변경 자체가 이미 적용되었음을 명시한다. 이 코드에는 설정을 되돌리는 처리가 없다. `acop_composer/api.py:385-388`, `acop_composer/api.py:439-442`

[미확보] 허용된 테스트 파일의 현재 실행 성공 여부는 확인하지 않았다.

## 관계

- 인증 주체와 scope 판정은 [auth-scope.md](auth-scope.md)를 참조한다.
- UI가 이 쓰기 경로 밖으로 나가지 못하게 하는 경계는 [ui-boundary.md](ui-boundary.md)를 참조한다.

===== FILE: auth-scope.md =====
---
type: concept
title: Composer 인증 주체와 scope 판정
description: 누가 Composer 기능을 호출할 수 있으며 요청 scope를 어떻게 판정하는지 설명한다.
status: draft
tags: [architecture, api, security]
---

# Composer 인증 주체와 scope 판정

Composer 권한은 JWT의 `scope` 목록에 필요한 문자열이 정확히 들어 있는지로 판정한다. [실측] scope 사이의 상속 관계나 와일드카드 판정은 없으며, 요구된 문자열이 목록에 없으면 403 `scope_denied`다. `acop_composer/auth.py:71-77`

기능별 요구 권한은 다음과 같다.

| 기능 | 필요한 scope |
|---|---|
| 현재 선언 조회 | `composer:read` [실측] |
| 카탈로그 조회 | `composer:read` [실측] |
| 후보 선언 검증 | `composer:validate` [실측] |
| 전체 선언 적용 | `composer:write` [실측] |
| 인스턴스 변경 | `composer:write` [실측] |
| Team·모듈 토글 | `composer:write` [실측] |

근거: `acop_composer/api.py:202-204`, `acop_composer/api.py:228-230`, `acop_composer/api.py:317-319`, `acop_composer/api.py:392-401`, `acop_composer/api.py:415-417`

## 토큰을 발급할 수 있는 주체

[실측] `/auth/token`은 `Authorization: Bearer <issuer secret>`을 요구한다. 이 값은 `composer_issuer_secret`과 일치해야 한다. 누락되거나 형식이 다르면 401 `unauthenticated`다. `acop_composer/auth.py:27-33`, `acop_composer/auth.py:80-85`

[실측] issuer secret을 가진 호출자는 비어 있지 않은 `sub`와 하나 이상의 scope를 요청할 수 있다. 요청한 scope가 guardrail의 `security.scopes` 목록에 없으면 422 `invalid_scope`다. `acop_composer/auth.py:17-20`, `acop_composer/auth.py:34-36`

[미확보] 실제 환경에 설정된 `security.scopes` 목록과 issuer secret의 배포·보관 주체는 허용된 파일에서 확인하지 않았다.

[실측] 발급 코드는 issuer secret 보유자와 요청의 `sub`가 같은 사람 또는 시스템인지 확인하지 않는다. 따라서 이 코드 안에서는 issuer secret을 가진 호출자가 임의의 비어 있지 않은 `sub`와 구성된 scope 조합을 요청할 수 있다. `acop_composer/auth.py:27-49`

## 토큰에 들어가는 값

[실측] 발급되는 토큰은 HS256으로 서명되며 다음 claim을 포함한다. `acop_composer/auth.py:13-14`, `acop_composer/auth.py:40-49`

- `sub`: 요청자가 제출한 주체 식별자 [실측]
- `aud`: `final_project_sample` [실측]
- `scope`: 요청한 문자열 목록 [실측]
- `iat`: 발급 시각 [실측]
- `exp`: 만료 시각 [실측]
- `jti`: 새 UUID 문자열 [실측]

[실측] TTL은 `security.composer_jwt_ttl_minutes`에서 읽으며 15분 이상 60분 이하여야 한다. 범위를 벗어나면 토큰 발급이 `RuntimeError`로 실패한다. 응답의 `expires_in`은 분 단위 TTL에 60을 곱한 초 값이다. `acop_composer/auth.py:37-50`

## 요청을 인증하는 순서

1. [실측] `Authorization` 헤더가 `Bearer `로 시작하는지 확인한다. 누락되면 401이다. `acop_composer/auth.py:53-55`
2. [실측] `composer_jwt_secret`으로 HS256 서명을 검증하고 audience가 `final_project_sample`인지 확인한다. `acop_composer/auth.py:56-60`
3. [실측] `sub`, `aud`, `scope`, `iat`, `exp`, `jti`가 모두 존재해야 한다. 서명·audience·만료·형식 검증 오류는 401로 변환된다. `acop_composer/auth.py:56-63`
4. [실측] `sub`는 비어 있지 않은 문자열이어야 하고 `scope`는 문자열로만 이루어진 목록이어야 한다. `acop_composer/auth.py:64-68`
5. [실측] 엔드포인트가 요구하는 scope가 목록에 정확히 포함되어야 한다. 없으면 인증 성공과 별개로 403이다. `acop_composer/auth.py:71-76`

[실측] E2E 검사는 토큰 누락을 401로, 다른 scope를 403으로, 만료 토큰과 다른 비밀키로 위조한 토큰을 각각 401로 거부하도록 요구한다. `tests/e2e/test_composer_write_channel.py:78-120`

## 변경할 수 있는 대상

[실측] `composer:write` 토큰은 `/apply`, `/changes`, `/toggle`을 호출할 수 있다. 성공한 변경의 감사 이벤트에는 JWT의 `sub`가 `actor`로 기록된다. `acop_composer/api.py:317-319`, `acop_composer/api.py:375-383`, `acop_composer/api.py:415-437`

[실측] 중앙 설정 서비스에서 실제 변경 대상은 JWT claim이 아니라 `X-Deployment-Id` 헤더가 정한다. 헤더가 없으면 요청을 거부한다. `acop_composer/api.py:62-83`, `acop_composer/service_app.py:34-41`

[실측] 발급된 JWT에는 deployment 식별 claim이 없으며, scope 검사도 deployment와 토큰 주체의 관계를 확인하지 않는다. `acop_composer/auth.py:41-48`, `acop_composer/auth.py:71-76`

[미확보] 특정 `sub`가 특정 deployment만 변경하도록 제한하는 외부 네트워크 정책이나 별도 인가 계층은 허용된 파일에서 확인되지 않았다. 이 코드 범위에서는 유효한 `composer:write` 토큰과 대상 헤더가 변경 권한 판정에 사용된다.

[실측] 읽기 scope로 `/changes`를 호출하면 403이어야 한다는 E2E 검사가 있다. `tests/e2e/test_composer_catalog_changes.py:208-213`

[미확보] 허용된 테스트 파일의 현재 실행 성공 여부는 확인하지 않았다.

## 관계

- 권한 검사를 통과한 변경이 저장되는 과정은 [write-channel.md](write-channel.md)를 참조한다.
- UI가 인증 뒤에도 서버 검증 책임을 침범하지 않게 하는 경계는 [ui-boundary.md](ui-boundary.md)를 참조한다.

===== FILE: ui-boundary.md =====
---
type: concept
title: Composer UI 패키지의 경계
description: UI가 넘지 말아야 할 구현 경계와 이를 검사하는 장치를 설명한다.
status: draft
tags: [architecture, contract, testing, security]
---

# Composer UI 패키지의 경계

UI는 대상의 검증 모델, 서버 구현, Python 구현 경로를 소유하거나 복제하지 않는다. [실측] UI 클라이언트는 JSON API 계약만 사용하고, 선언 검증과 권한 판정은 Composer 서버가 수행하도록 경계가 설정되어 있다. `tests/architecture/test_composer_ui_package_boundary.py:1-9`, `tests/e2e/test_composer_ui_client_contract.py:1-9`

## 넘으면 안 되는 선

[실측] `acop_composer_ui` 소스에는 다음 import 문자열이 들어오면 안 된다. `tests/architecture/test_composer_ui_package_boundary.py:22-46`

- `acop_basement`
- `acop_composer.`
- `app.`
- `fastapi`
- `pydantic`
- `yaml`

이 제한은 UI 프로세스가 대상 Core, Composer 서버, 제품 조립부, 서버 프레임워크와 선언 모델 구현을 끌어오는 것을 막는다. [실측] 검사 코드는 UI 패키지 아래의 모든 `*.py` 파일에서 `import` 또는 `from`으로 시작하는 줄을 확인한다. `tests/architecture/test_composer_ui_package_boundary.py:19-27`, `tests/architecture/test_composer_ui_package_boundary.py:36-46`

[실측] UI 코드에는 `ProjectConfig`, `TeamManifest`, `ContextPack` 식별자가 나타나면 안 된다. 주석과 삼중 큰따옴표 docstring은 검사 대상에서 제거한 뒤 실제 코드만 검사한다. `tests/architecture/test_composer_ui_package_boundary.py:49-58`

[실측] UI 패키지의 `project.dependencies`는 빈 목록이어야 한다. 또한 제품 루트의 패키지 탐색 설정은 `packages`로 시작하는 제외 패턴을 가져야 한다. 즉 UI 클라이언트는 표준 라이브러리만 사용하는 별도 배포 단위로 유지되는 것이 검사 계약이다. `tests/architecture/test_composer_ui_package_boundary.py:61-75`

## UI가 대신 사용하는 계약

[실측] UI는 구현 Python 경로 대신 서버 카탈로그가 제공하는 `implementation_id`를 사용한다. ID와 Python 경로의 매핑은 Composer 서버의 `IMPLEMENTATION_IDS`에만 있다. `acop_composer/catalog.py:22-27`, `acop_composer/catalog.py:52-57`

[실측] 카탈로그 응답은 `implementation_id`, 종류, 표시 이름, 설명, 입력 스키마, 재시작 필요 여부를 제공하지만 Python 경로를 포함하지 않는다. `acop_composer/catalog.py:68-105`

[실측] 카탈로그 E2E 검사는 응답에 선언형 Team과 선언된 모듈 ID가 포함되고 `app.modules` Python 경로는 노출되지 않도록 요구한다. `tests/e2e/test_composer_catalog_changes.py:74-91`

[실측] UI가 인스턴스를 변경할 때는 전체 선언 구조를 재구성하지 않고 작업 종류, 자원 종류, 인스턴스 ID와 필요한 입력값을 `/composer/changes`에 보낸다. 서버가 현재 선언을 읽어 대상 하나만 바꾼 후보를 만든다. `acop_composer/api.py:143-160`, `acop_composer/api.py:259-314`

[실측] 토글은 대상 종류, 대상 ID, 활성 상태, 기준 revision과 사유만 받는다. 서버가 이를 `enable` 또는 `disable` 변경으로 변환한다. `acop_composer/api.py:164-179`, `acop_composer/api.py:202-215`

## 검증 책임이 서버에 남는 방식

[실측] UI 클라이언트와 실제 FastAPI 앱을 직접 연결하는 E2E 검사가 경로, payload, scope와 상태 코드의 일치를 확인한다. 네트워크 대신 주입된 transport가 `TestClient`를 호출한다. `tests/e2e/test_composer_ui_client_contract.py:1-9`, `tests/e2e/test_composer_ui_client_contract.py:48-68`

[실측] 계약 검사는 카탈로그 조회, 토글, 선언형 Team 생성, dry-run, revision 충돌을 실제 서버와 왕복한다. `tests/e2e/test_composer_ui_client_contract.py:71-136`

[실측] 읽기 전용 선언형 Team에 쓰기 도구를 넣는 요청도 UI 클라이언트가 자체 판정하지 않는다. 요청을 그대로 보낸 뒤 서버가 422로 거부해야 한다. `tests/e2e/test_composer_ui_client_contract.py:139-156`

[실측] 같은 권한 상승 요청을 Composer API에서 직접 보내도 422와 읽기 전용 오류가 나야 한다는 검사가 있다. `tests/e2e/test_composer_catalog_changes.py:306-320`

[실측] 중앙 방식에서는 UI 클라이언트가 deployment ID를 헤더로 전달한다. 대상 없이 중앙 서비스에 연결하면 400 `deployment_required`를 받아야 한다. `tests/e2e/test_composer_ui_client_contract.py:175-236`

## 경계를 막는 검사의 범위

[실측] 소스가 하나도 없을 때 경계 검사가 공허하게 통과하지 않도록, 검사 대상 `*.py` 파일이 최소 하나 존재하는지도 확인한다. `tests/architecture/test_composer_ui_package_boundary.py:26-33`

[실측] import 검사는 `import` 또는 `from`으로 시작하는 줄과 금지 문자열의 포함 여부를 검사한다. 동적 import나 다른 방식으로 구성한 모듈 이름을 탐지하는 로직은 없다. `tests/architecture/test_composer_ui_package_boundary.py:36-46`

[실측] 모델 복제 검사는 세 식별자 이름만 탐지한다. 같은 구조를 다른 이름으로 다시 구현했는지를 구조적으로 비교하지는 않는다. `tests/architecture/test_composer_ui_package_boundary.py:49-58`

[실측] 배포 분리 검사는 제품 루트 제외 목록에 `packages`로 시작하는 패턴이 하나 이상 있는지만 확인한다. UI 패키지의 실제 배포 산출물을 검사하는 코드는 이 테스트에 없다. `tests/architecture/test_composer_ui_package_boundary.py:69-75`

[미확보] 허용된 경계·E2E 테스트의 현재 실행 성공 여부와 동적 import 같은 우회가 실제 UI 소스에 존재하는지는 확인하지 않았다.

## 관계

- UI 요청이 공유하는 실제 저장 경로는 [write-channel.md](write-channel.md)를 참조한다.
- UI 요청을 읽기·검증·쓰기로 나누는 권한 판정은 [auth-scope.md](auth-scope.md)를 참조한다.