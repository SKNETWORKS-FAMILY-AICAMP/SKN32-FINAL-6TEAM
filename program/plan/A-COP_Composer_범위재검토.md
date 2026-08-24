# A-COP Composer 범위 재검토

## 1. 결론

요구사항 1과 2를 만족하려면 토글 전용 v3를 전체 Composer의 대체 계약으로 쓰면 안 된다. 대상이 제공하는 등록 카탈로그에서 구현 종류를 고르고, UI에서 인스턴스 이름과 설정을 입력해 생성·수정·삭제하는 관리 계약이 필요하다. 새 Python 구현이 없는 경우에는 등록된 구현체의 인스턴스 생성과 선언형 Team 생성으로 범위를 넓힌다. 새 Python 구현이 필요한 경우에는 템플릿 생성과 검증된 플러그인 배포 절차로 연결한다. UI는 대상의 Python이나 Core 모델을 가져오지 않는다. 대상은 카탈로그, 스키마, 검증, 저장, 재시작, 감사, 롤백을 책임진다. `/toggle`은 빠른 상태 변경으로 남긴다. `/current`, `/validate`, `/apply`의 전체 선언 기능은 인스턴스 CRUD의 기반 또는 호환 경로로 유지한다. 장기 정본은 raw YAML 편집이 아니라 카탈로그 기반 명령형 API로 바꾼다.

## 2. 지금 실제로 가능한 것

### 2.1 선언 모델과 `/apply`

`ProjectConfig.modules`는 고정 필드가 아니라 `dict[str, ModuleConfig]`다. 따라서 새 모듈 키와 `enabled` 값을 스키마상 받을 수 있다. 근거는 `final_project_cs/app/core/project_config.py:29`, `:62`다.

`ProjectConfig.teams`는 `TeamConfig` 목록이다. 각 항목에는 `team_id`, `active`, `implementation_ref`만 허용된다. 추가 설정이나 세부사항을 담는 필드는 없다. `team_id`는 중복될 수 없다. Team은 한 개 이상 남아야 한다. 근거는 `final_project_cs/app/core/project_config.py:41-45`, `:64`, `:70-76`이다.

`POST /composer/apply`는 전달받은 전체 `config`를 후보 파일로 만든다. 대상의 `load_project_config()`로 검증한 뒤 `os.replace()`로 `project.yaml`을 교체한다. 따라서 API에 올바른 `reason`과 최신 `base_revision`을 직접 보내면 `teams:`에 새 항목을 추가하거나 기존 항목을 삭제할 수 있다. 새 모듈 키도 추가할 수 있다. 근거는 `final_project_cs/app/presentation/api/composer.py:67-91`과 `final_project_cs/app/application/composer_service.py:91-115`다.

다만 저장 성공과 실제 동작 성공은 다르다. `/apply`의 검증은 완성된 런타임 조립을 수행하지 않는다. 예를 들어 중복 capability와 미구현 활성 모듈은 `composition.build_registry()` 또는 `build_controller()` 단계에서 뒤늦게 실패할 수 있다.

### 2.2 `implementation_ref` 제한의 실제 위치

v3 문서의 “registry ID allowlist로 이미 제한됐다”는 말은 현재 코드에 근거가 있다. 다만 제한 주체는 `TeamRegistry`가 아니다.

`KNOWN_IMPLEMENTATION_REFS`는 `final_project_cs/app/core/project_config.py:16-23`에 있다. Composer HTTP의 `/validate`와 `/apply`는 `enforce_registry=True`를 사용한다. 서비스는 활성 Team의 `implementation_ref`가 이 집합에 없으면 거부한다. 근거는 `final_project_cs/app/application/composer_service.py:57-68`과 `final_project_cs/app/presentation/api/composer.py:62`, `:74-75`다.

반면 일반 `load_project_config()`는 allowlist를 사용하지 않는다. 활성 Team의 문자열 형식을 검사한 뒤 대상 프로세스에서 `importlib.import_module()`로 경로를 직접 해석한다. 대상이 class인지와 `manifest`, `execute`가 있는지도 확인한다. 근거는 `final_project_cs/app/core/project_config.py:106-151`이다.

`TeamRegistry`는 구현체 목록을 생성자로 주입받는다. 이 클래스는 `app.modules`를 import하지 않는다. 계약 버전, 중복 `team_id`, 라우팅 조건을 검사할 뿐이다. 근거는 `final_project_cs/app/core/registry.py:30-45`다.

정리하면 allowlist는 문서상의 방침만이 아니다. Composer HTTP 쓰기 채널에 실제로 구현돼 있다. 그러나 시스템 전체의 공통 registry ID 체계는 아니다. 일반 로더와 composition root에는 임의 import 경로 해석이 남아 있다.

또 다른 예외가 있다. HTTP allowlist와 일반 로더는 비활성 Team을 import 검사에서 건너뛴다. 따라서 `/apply`는 미등록 경로를 가진 비활성 Team을 저장할 수 있다. 그러나 `build_registry()`는 활성 여부와 관계없이 모든 선언을 import한다. 재시작 시 이 비활성 Team 때문에 조립이 실패할 수 있다. 근거는 `final_project_cs/app/core/project_config.py:114-115`, `final_project_cs/app/application/composer_service.py:60-63`, `final_project_cs/app/composition.py:121-138`이다.

### 2.3 새 Team이 실제로 동작하는 조건

import 경로를 해석하는 주체는 UI가 아니라 `final_project_cs` 프로세스다. 후보 검증 때는 `load_project_config()`가 해석한다. 실제 조립 때는 composition root의 `_import_ref()`가 다시 해석하고 인스턴스를 만든다. 생성된 객체는 `TeamRegistry`에 주입된다. 근거는 `final_project_cs/app/composition.py:73-89`, `:110-138`이다.

현재 API 앱은 `create_app()`에서 `composition.build_controller()`를 한 번 호출한다. 모듈 전역의 `app = create_app()`도 import 시 실행된다. 적용된 YAML이 이미 실행 중인 Controller와 TeamRegistry를 다시 만들지는 않는다. 근거는 `final_project_cs/app/presentation/api/app.py:14-20`, `:50`과 `final_project_cs/app/composition.py:171-183`이다.

따라서 새 Team, Team 삭제, 모듈 조립, Port 교체는 원칙적으로 프로세스 재시작이 필요하다. 개발용 `--reload`가 파일 변경을 감지할 수는 있다. 이것은 운영 계약이 아니다.

같은 구현체를 다른 `team_id`로 한 번 더 선언하는 것도 현재 구조에서는 일반적인 인스턴스 복제가 아니다. `build_registry()`는 구현체 manifest의 capability를 그대로 사용한다. 둘 이상의 인스턴스가 같은 capability를 주장하면 조립을 거부한다. Team별 설정 필드도 없다. 현재 allowlist의 구현체가 모두 이미 선언돼 있으므로 새 행을 하나 더 추가하는 동작은 저장될 수 있어도 재시작 후 중복 capability로 실패할 가능성이 높다.

### 2.4 새 모듈 키와 GraphStore

`/apply`는 새 모듈 키 자체를 저장할 수 있다. 그러나 composition root는 활성 모듈을 `_MODULE_IMPLEMENTATIONS`와 대조한다. 목록에 없는 새 키가 `enabled: true`이면 시작 시 실패한다. `enabled: false`이면 저장되지만 아무 기능도 만들지 않는다. 근거는 `final_project_cs/app/composition.py:50-62`다.

기존 `graph_store` 키는 켜고 끌 수 있다. `ports.graph_store`는 `sql`, `age`, `neo4j` 중 하나만 받는다. 현재 composition은 `age`와 `neo4j`를 미구현으로 거부한다. 따라서 지금 실제 동작하는 선택은 `sql`이다.

`POST /composer/toggle`은 현재 선언에 이미 있는 module 또는 team만 바꾼다. 새 키나 새 Team을 만들지 않는다. Port도 지원하지 않는다. 근거는 `final_project_cs/app/application/composer_service.py:121-143`이다.

### 2.5 현재 운영 UI의 종단 상태

v2 화면에는 Team 행 추가와 제거가 있다. 이 동작은 먼저 브라우저 안의 후보 목록만 바꾼다. 사용자가 적용을 눌러야 대상에 저장된다. 모듈과 Port는 현재 `/current`가 준 이름만 다시 그리므로 새 모듈 키나 새 Port 종류를 화면에서 추가할 수 없다. 근거는 `final_project_ui/console/web.py:517-551`, `:851-871`이다.

현재 UI의 `apply_candidate()`는 `config`와 `base_revision`만 전송한다. CS의 `ApplyPayload`는 필수 `reason`을 요구한다. 화면은 reason을 입력받지만 클라이언트 호출에 전달하지 않는다. 따라서 관찰한 코드 조합에서는 UI의 v2 적용이 422로 거부된다. 직접 API 호출은 `reason`을 포함하면 가능하다. 근거는 `final_project_ui/console/composer.py:133-138`, `final_project_ui/console/web.py:879-887`, `final_project_cs/app/presentation/api/composer.py:26-29`이다.

v3 빠른 토글도 현재 계약이 맞지 않는다. UI 기본 지원 버전은 `v1`이다. CS introspection 버전은 `1.0`이다. UI는 module과 team 상태를 ID별 객체로 기대한다. CS는 modules를 boolean map으로 내고 teams를 list로 낸다. CS의 `registered_ids.ports`는 빈 목록이다. 환경에서 버전을 맞추더라도 현재 형태로는 상태를 읽어 토글 버튼을 만드는 데 실패한다. 근거는 `final_project_ui/console/profiles.py:24`, `final_project_ui/console/live.py:42-43`, `final_project_ui/console/web.py:401-446`, `final_project_cs/app/introspection/contract.py:11`, `:46-60`이다.

introspection은 요청마다 현재 파일을 다시 읽고 새 registry를 조립한다. 반면 업무 Controller는 앱 생성 시 만들어진 객체를 계속 쓴다. 따라서 introspection이 새 선언을 보여도 실제 업무 Controller는 이전 registry를 사용할 수 있다. 현재 응답은 desired state와 effective state를 구분하지 않는다.

## 3. 세 층 구분표

| 층 | 가능한 범위 | UI가 보내는 것 | 대상이 하는 것 | 현재 상태 |
|---|---|---|---|---|
| 설정만으로 되는 것 | 이미 설치된 구현 종류의 인스턴스 선언, 선언형 Team 생성, 활성 상태 변경, 허용된 Port 선택, 인스턴스 삭제 예약 | `implementation_id`, `instance_id`, 설정값, 활성 상태, `base_revision`, `reason`, idempotency key | 카탈로그 조회, 스키마 검증, 의존성 검사, 원자적 저장, 감사, 새 desired revision 반환 | 토글과 전체 YAML 저장의 일부만 있음. 일반 인스턴스 설정과 선언형 Team은 없음 |
| 재시작이 필요한 것 | 새 TeamRegistry 구성, Team 추가·제거의 실제 반영, 모듈 조립 변경, GraphStore adapter 교체 | 위 변경 요청과 `activation_mode: controlled_restart` 또는 별도 재조립 요청 | 변경을 staged 상태로 저장, drain, 재시작, health check, effective revision 확인, 실패 시 rollback | YAML 저장은 가능. 재시작·health check·rollback 계약은 없음 |
| 코드 배포가 필요한 것 | 새로운 Python Team 종류, 새 GraphStore adapter, 새 모듈 종류, 새 생성자 형태, 새 Core 계약 | 승인된 패키지 ID와 버전 또는 생성 작업 ID | 서명·호환성·테스트 확인, 격리된 설치, 카탈로그 등록, 재시작, 검증, rollback | 고정 소스와 import 경로만 사용. 배포 관리 기능은 없음 |

설정만으로 된다는 말은 플랫폼에 범용 런타임과 구현체가 미리 배포돼 있다는 뜻이다. 선언형 Team도 범용 실행기가 한 번 배포된 뒤부터 설정만으로 추가할 수 있다.

## 4. 계약 제안

### 4.1 공통 조회 계약

`GET /composer/catalog`를 추가한다. 이 응답은 UI가 고를 수 있는 module type, Team implementation, declarative Team type, Port implementation을 제공한다. 각 항목에는 안정된 `implementation_id`, 버전, 입력 JSON Schema, 필요한 모듈과 Port, 충돌 가능한 capability, 재시작 필요 여부, 허용 가능한 tool 목록, 배포 digest를 넣는다. Python 경로는 UI 계약에 노출하지 않는다.

`GET /composer/current`는 다음 상태를 구분해야 한다.

- `desired_revision`은 저장된 선언의 revision이다.
- `effective_revision`은 현재 Controller가 실제 사용하는 revision이다.
- `activation_state`는 `effective`, `pending_restart`, `failed`, `rolling_back` 중 하나다.
- 각 인스턴스는 `instance_id`, `implementation_id`, 설정 버전, desired 상태, effective 상태를 가진다.

UI는 이 raw 응답을 그린다. UI가 Core Pydantic 모델을 복제하지 않는다. 입력 폼은 대상이 준 JSON Schema에서 만든다. 이는 `final_project_ui/CLAUDE.md` §0.2와 §0.3을 지킨다.

### 4.2 설정 변경 계약

일반 운영 화면에는 전체 YAML 대신 인스턴스 명령을 사용한다.

```json
{
  "operation": "create",
  "resource_type": "team_instance",
  "instance_id": "vip_return_review",
  "implementation_id": "team.declarative.v1",
  "parameters": {
    "display_name": "VIP 반품 검토",
    "capabilities": ["return.vip_review"],
    "accepted_case_types": ["return"],
    "prompt": "정책 근거를 확인하고 승인 필요 여부를 판단한다.",
    "allowed_tools": ["read.order", "search.policy"],
    "knowledge_scope": ["return_policy"],
    "max_steps": 4
  },
  "active": true,
  "base_revision": "<desired_revision>",
  "reason": "VIP 반품 전담 흐름 추가",
  "idempotency_key": "<uuid>"
}
```

제안 endpoint는 `POST /composer/changes`다. `operation`은 `create`, `update`, `delete`, `enable`, `disable`을 받는다. 대상은 권한, 카탈로그, 스키마, capability 중복, tool 권한, 참조 관계, 실행 중 작업을 검사한다. 성공 응답에는 `change_id`, 새 `desired_revision`, `activation_state`, 필요한 다음 조치를 넣는다.

GraphStore 같은 기능도 같은 계약을 쓴다. UI는 `resource_type: module_instance`, `instance_id: graph_store`, `implementation_id: graph_store.sql.v1`과 연결 설정을 보낸다. 대상은 `modules.graph_store`와 `ports.graph_store`를 하나의 변경으로 검증하고 저장한다. 삭제할 때는 GraphStore를 참조하는 Team이나 기능을 먼저 찾아 영향 목록을 반환한다. UI가 module flag와 Port 값을 서로 어긋나게 따로 쓰지 않게 한다.

삭제는 즉시 파일 행을 없애는 한 단계 작업으로 보지 않는다. 대상은 먼저 새 라우팅을 막는다. 실행 중인 작업을 drain한다. 재개할 작업이 있으면 기존 구현 버전을 고정한다. 안전해진 뒤 선언을 tombstone 상태로 바꾸고 보존 기간 후 제거한다.

`POST /composer/validate`는 유지한다. 다만 UI가 전체 Core 구조를 만들어 보내는 방식보다 `changes`와 같은 명령을 `dry_run: true`로 검증하는 방식을 우선한다. 응답은 단순 valid 외에 의존성, 재시작, 중단 영향, 권한, rollback 가능 여부를 보여준다.

### 4.3 재시작 계약

현재 구조에서는 설정 저장 뒤 controlled restart가 필요하다. 대상은 저장 성공을 곧바로 “동작 중”으로 응답하면 안 된다.

`POST /composer/activations`는 `desired_revision`, `strategy`, `reason`을 받는다. 실제 재시작 권한은 별도 `composer:activate` scope로 분리한다. 대상 또는 배포 supervisor는 새 프로세스를 띄운다. registry 조립과 health check를 통과시킨다. 트래픽을 전환한 뒤 `effective_revision`을 갱신한다. 실패하면 이전 파일과 이전 프로세스로 되돌린다.

단일 프로세스 안에서 hot reload를 만들 수도 있다. 이 경우 새 config와 registry를 별도 객체로 끝까지 조립해야 한다. 검증이 끝난 immutable registry snapshot만 원자적으로 교체해야 한다. 실행 중인 Case는 시작 당시 snapshot을 계속 써야 한다. 현재 코드에는 이 기능이 없으므로 첫 단계에서는 controlled restart가 더 명확하다.

### 4.4 코드 배포 계약

새 Python 구현이 필요하면 UI가 임의 소스나 import 경로를 운영 프로세스에 바로 보내면 안 된다. UI는 `package_id`, `version`, `digest`, `signature`, 호환 계약 버전, 필요한 권한을 가진 승인된 artifact를 선택한다.

대상 배포기는 격리 환경에서 설치와 import smoke test를 수행한다. 계약 테스트와 보안 검사를 통과한 artifact만 카탈로그에 등록한다. 그 뒤 일반 `create` 계약으로 인스턴스를 만든다. 설치, 등록, 인스턴스 생성은 각각 감사 이벤트를 남긴다.

## 5. 선언형 Team 검토

### 5.1 네 방식 비교

| 방식 | 가능 여부 | 사용자 경험 | 대가와 한계 |
|---|---|---|---|
| 등록 구현체 선택 후 이름·설정 입력 | 가능 | 목록에서 구현 종류를 고르고 인스턴스 이름과 설정을 입력한다 | 현재 TeamConfig에 설정 필드가 없다. 카탈로그와 instance schema가 필요하다. 동일 capability 정책도 바꿔야 한다 |
| 템플릿에서 새 구현체 생성 | 개발 환경에서 가능 | 이름과 설명으로 Python 골격, manifest, 테스트를 만든다 | 생성 결과는 코드다. 검토, 테스트, 서명, 배포, 재시작이 필요하다. 운영 UI에서 즉시 실행하면 안 된다 |
| 선언형 Team | 가능하며 우선 권고 | 이름, 역할, case type, capability, 프롬프트, 도구, 지식 범위를 입력하면 Team이 만들어진다 | 범용 실행기와 정책 엔진을 한 번 코드 배포해야 한다. 복잡한 알고리즘과 새 side effect는 표현하기 어렵다 |
| 플러그인 디렉터리 스캔 | 조건부 가능 | 승인된 패키지를 디렉터리에 놓으면 카탈로그에 나타난다 | 임의 파일 import는 원격 코드 실행과 같다. 서명, 고정 디렉터리, 격리 검사, 버전 고정, 재시작이 필요하다 |

### 5.2 선언형 Team의 권고 구조

선언형 Team은 “코드가 전혀 없다”는 뜻이 아니다. `DeclarativeTeamRuntime`이라는 범용 Python 구현체를 한 번 배포한다. 그 뒤 개별 Team은 데이터로 만든다.

개별 선언에는 다음 항목이 필요하다.

- `instance_id`와 표시 이름
- `capabilities`와 `accepted_case_types`
- version이 고정된 system prompt 또는 prompt resource
- `allowed_tools`와 각 tool의 read/write 등급
- `knowledge_scope`와 필요한 ContextPack 항목
- `max_steps`, token·비용 한도, timeout
- 결과를 `TeamResult`로 제한하는 output schema
- 생성자, 검토자, 승인자, 생성 시각, 변경 revision

범용 실행기는 `TeamModule` 계약을 구현한다. 실행 때 선언으로 `TeamManifest`를 만든다. 모든 tool 호출은 서버의 tool gateway를 거친다. 결과는 기존 `TeamResult`로 검증한다. 승인 필요한 side effect는 계속 `ActionProposal`만 반환한다.

이 구조를 배포한 뒤에는 새 선언형 Team의 생성·수정·삭제에 새 Python 배포가 필요 없다. controlled restart 방식이면 생성 직후 `pending_restart`가 된다. atomic registry reload까지 구현하면 같은 프로세스에서 빠르게 활성화할 수 있다.

선언형 Team이 잘 맞는 범위는 분류, 정책 검색, 사실 조회, 답변 초안, 검토, handoff 판단이다. 새 DB transaction, 새 외부 프로토콜, 복잡한 결정론적 계산, 새 side effect가 필요하면 코드형 Team 또는 새 tool 배포가 필요하다.

프롬프트 원문을 `project.yaml`에 계속 덮어쓰는 방식은 피한다. prompt는 immutable version과 hash로 저장한다. Team 선언은 그 version을 참조한다. 이 방식은 현재 CS의 프롬프트 감사 원칙과 맞는다.

## 6. 안전 경계와 관리 방법

| 위험 | 기능을 살리는 관리 방법 |
|---|---|
| 임의 `package.module:Class` 실행 | UI에는 `implementation_id`만 노출한다. 대상의 서명된 카탈로그가 ID를 package digest와 entry point에 매핑한다 |
| 플러그인 디렉터리에 악성 파일 투입 | 고정된 비쓰기 디렉터리만 스캔한다. 서명과 digest를 확인한다. 별도 프로세스에서 manifest를 읽고 테스트한다. 운영 프로세스의 자동 import는 금지한다 |
| 선언형 Team이 과도한 tool 권한 획득 | 생성자가 가진 권한보다 넓은 `allowed_tools`를 부여할 수 없게 한다. tool gateway가 manifest 밖 호출을 다시 차단한다. write tool은 별도 승인 흐름을 유지한다 |
| 이름 충돌과 잘못된 라우팅 | `instance_id`와 capability에 namespace를 둔다. 활성 capability의 단일 소유 규칙을 검증한다. 겹침을 허용하려면 우선순위와 명시적 router 정책을 계약에 넣는다 |
| 삭제 중 실행 작업 유실 | disable, drain, tombstone, purge를 분리한다. 실행 중 Case는 구현 revision을 고정한다. 재개 가능 기간 동안 artifact를 보존한다 |
| 재시작 실패로 서비스 중단 | 새 프로세스 사전 조립, health check, 점진 전환, 이전 revision 자동 rollback을 사용한다 |
| 감사 누락 | 설정 교체 후 감사 기록에 실패하는 현재 순서를 바꾼다. 감사 저장을 먼저 예약하거나 DB transaction/outbox로 config commit과 묶는다. 실패 시 성공으로 응답하지 않는다 |
| 동시 쓰기로 변경 유실 | `base_revision`을 유지한다. process-local lock만 믿지 않는다. 다중 worker가 공유하는 DB CAS 또는 OS 파일 lock을 사용한다 |
| 비밀값 노출 | 선언에는 secret 원문 대신 secret reference만 둔다. 조회 응답과 감사 로그에는 값을 내보내지 않는다 |
| 프롬프트 주입과 비용 폭주 | 허용 tool, output schema, step·token·비용 한도, timeout을 서버가 강제한다. 활성화 전에 평가와 승인 정책을 적용한다 |
| 권한 상승과 책임 불명 | `composer:read`, `composer:validate`, `composer:write`, `composer:activate`, `composer:deploy`를 분리한다. 생성, 승인, 활성화 주체를 모두 기록한다 |

현재 `/apply`와 `/toggle`은 config를 먼저 바꾼 뒤 감사 파일을 쓴다. 감사 기록 실패 시 500을 반환하지만 설정은 이미 바뀌었다. 근거는 `final_project_cs/app/presentation/api/composer.py:74-89`, `:98-127`이다. 새 관리 계약은 이 부분을 우선 보강해야 한다.

## 7. v2·v3 정리 제안

토글 전용 v3는 전체 Composer를 대체한다는 지위를 폐기한다. 이유는 사용자 요구가 등록된 항목의 on/off보다 넓기 때문이다. 인스턴스 생성·삭제와 선언형 Team 생성을 막는 계약은 요구사항 1과 2를 충족하지 못한다.

다만 `/toggle` 자체는 유용하다. 기존 인스턴스의 빠른 enable/disable 명령으로 유지한다. 내부적으로는 `POST /composer/changes`의 `enable` 또는 `disable`과 같은 저장·revision·감사 경로를 사용하게 한다.

`/current`는 유지하고 desired state와 effective state를 함께 내도록 확장한다. `/validate`는 유지하고 명령 dry-run과 완성 조립 검증을 담당하게 한다. `/apply`는 당분간 bulk migration과 고급 관리용으로 유지한다. 일반 UI는 raw 전체 config를 만들지 않고 카탈로그 기반 CRUD를 사용한다.

권고하는 계약 단계는 다음과 같다.

1. 기존 v2의 인증, revision, 원자적 저장 개념을 보존한다.
2. 현재 `/apply`의 UI reason 누락과 runtime 조립 검증 누락을 먼저 계약상 결함으로 분류한다.
3. v3 introspection 형태와 실제 `1.0` 형태를 하나로 맞춘다.
4. `catalog`, `changes`, `activations`를 새 정본 관리 계약으로 추가한다.
5. 선언형 Team 범용 실행기를 배포한다.
6. 일반 UI를 인스턴스 목록과 생성 마법사 중심으로 전환한다.
7. bulk `/apply`는 외부 소비자와 migration이 없어졌을 때에만 축소 여부를 다시 결정한다.

이 결론은 v2를 그대로 정본으로 삼는 안도 아니고 v2를 없애는 안도 아니다. v2가 가진 넓은 변경 능력은 보존한다. v3가 가진 좁고 안전한 명령 방식도 보존한다. 두 경로 위에 사용자가 실제로 요구한 인스턴스 CRUD와 선언형 Team을 명시적 계약으로 올린다.

## 8. 확인하지 못한 것

- 실행 중인 CS와 UI 프로세스에 실제 HTTP 요청을 보내지는 않았다. 현재 판단은 2026-08-24 작업 트리의 코드와 테스트를 정적 검토한 결과다.
- 작업 트리에 Composer, introspection, UI 관련 미커밋 변경이 있다. 이 문서는 관찰한 파일 내용을 기준으로 한다. 다른 세션이 변경을 완료하면 line number와 일부 결론을 다시 확인해야 한다.
- 운영 배포가 단일 worker인지 다중 worker인지 확인하지 못했다. 따라서 process-local `_WRITE_LOCK`의 실제 경합 범위는 확정하지 않았다.
- 운영에서 프로세스를 재시작하는 supervisor와 권한 모델을 확인하지 못했다. controlled restart 계약은 제안이다.
- 외부에서 `/apply`를 사용하는 소비자 수와 폐기 가능 시점을 확인하지 못했다.
- 새 Team을 만들 때 진행 중 Case를 어느 기간까지 이전 구현으로 재개해야 하는지 정책이 없다.
- 플러그인 서명 체계, artifact 저장소, SBOM 정책은 확인하지 못했다.
- 선언형 Team의 품질 기준과 활성화 전 평가 문턱은 아직 정해져 있지 않다.
- 현재 `KNOWN_IMPLEMENTATION_REFS`의 변경 절차와 승인 주체는 코드에서 확인하지 못했다.
