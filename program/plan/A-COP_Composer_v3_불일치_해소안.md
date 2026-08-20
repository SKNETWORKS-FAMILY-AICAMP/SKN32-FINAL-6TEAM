# A-COP Composer v3 불일치 해소안

## 결론 요약

현재 상태는 v3 설계와 sample 구현이 서로 다른 계약을 가리키는 불일치다. v3는 `POST /composer/toggle`만으로 등록 ID 확인, flag 변경, revision 충돌 확인, 감사 기록을 수행하도록 좁혔다. sample은 `ProjectConfig` 전체를 받아 검증하고 교체하는 v2형 `GET /composer/current`, `POST /composer/validate`, `POST /composer/apply`를 구현한다.

이번 문서는 선택지를 정리한다. 최종 선택은 고객용 빌드의 Composer 배제 여부와 v2 계약의 연속성에 대한 사람의 결정이 필요하다.

근거는 [대조 보고서](../research/_컴포저_설계대비_구현대조.md), 기존 [v3 설계 문서](A-COP_Composer_v3_설계_토글전용_UI이관.md), 그리고 sample의 아래 파일들이다.

- `final_project_sample/acop_composer/api.py`: 현재 Composer 경로와 `ProjectConfig` import.
- `final_project_sample/acop_composer/service.py`: 전체 선언 검증, `load_project_config()`, 원자적 파일 교체, revision 확인.
- `final_project_sample/acop_basement/core/project_config.py`: `ProjectConfig` 스키마와 활성 Team 구현체 import 검증.
- `final_project_sample/acop_basement/presentation/api/app.py`: Composer router를 선택적으로 주입하는 app factory.
- `final_project_sample/app/entrypoint.py`: 관리용 진입점에서 Composer router와 인증 router를 주입.
- `final_project_sample/pyproject.toml`: `acop_basement*`와 `acop_composer*`를 같은 배포 패키지 검색 대상에 포함.
- `final_project_sample/Dockerfile.customer`: 고객용 이미지에서 `acop_composer`를 복사하지 않는 현재 경로.
- `final_project_sample/tests/e2e/test_composer_write_channel.py`: v2형 세 endpoint와 인증, 전체 config apply를 검증.
- `final_project_sample/tests/unit/application/test_composer_service.py`: 전체 config apply 서비스의 실패 정리 동작을 검증.
- `final_project_sample/tests/integration/api/test_openapi_surface.py`: API 표면과 scope dependency를 검증.

## 공통 사실

sample은 디렉터리 수준에서는 `acop_basement`와 `acop_composer`를 분리했다. 그러나 `pyproject.toml`의 package discovery는 두 패키지를 모두 포함하고, `app/entrypoint.py`는 두 Composer router를 관리용 앱에 연결한다. 따라서 현재 분리는 소스와 주입 지점의 분리이지, 모든 배포 산출물에서 Composer가 자동으로 분리된 상태는 아니다.

반대로 `acop_basement/presentation/api/app.py`의 `create_app()`은 Composer router 인자를 선택적으로 받는다. `Dockerfile.customer`도 `acop_composer`를 복사하지 않는다. 이 두 사실은 Composer를 고객용 런타임에서 제외할 수 있는 기반이 이미 있음을 뜻하지만, package metadata와 빌드 검증까지 포함한 완결된 경계라고 단정할 수는 없다.

`final_project_ui`가 실제로 Core 모델을 import하는지는 sample만으로 검증할 수 없다. 다만 v3 계약의 의도는 UI가 HTTP와 raw data만 사용하고 `ProjectConfig`와 `TeamManifest`를 import하지 않는 것이다. 아래 영향 판정은 이 목표를 유지하는지를 기준으로 한다.

## 안 A. 구현을 설계에 맞춘다

한 줄 요약: v2형 전체 설정 교체를 제거하고 `toggle` 중심의 얇은 쓰기 계약으로 전환한다.

### 무엇을 바꿔야 하는가

`final_project_sample/acop_composer/api.py`에서 `/composer/current`, `/composer/validate`, `/composer/apply`와 전체 `config` payload를 대체하거나 제거하고, `target_type`, `target_id`, `active`, `base_revision`, `reason`을 받는 `/composer/toggle`을 추가해야 한다.

`final_project_sample/acop_composer/service.py`도 `ProjectConfig` 전체를 후보 파일로 검증하는 흐름에서 벗어나야 한다. 등록 ID 목록 확인, 대상 flag의 단일 변경, revision 조건부 쓰기, append-only 감사 이벤트를 별도 서비스 흐름으로 구현해야 한다. 기존의 `os.replace()`와 process-local `_WRITE_LOCK`은 재사용할 수 있지만, 전체 YAML을 재구성하는 현재 방식은 flag 단위 변경에 맞게 바뀌어야 한다.

`final_project_sample/acop_basement/core/project_config.py`와 `acop_composer/api.py` 사이의 깊은 결합도 줄여야 한다. Composer가 Core 모델을 직접 import하지 않도록 registry ID와 flag 저장·조회에 필요한 최소 경계를 정해야 한다. `acop_basement/presentation/api/app.py`의 선택적 router 주입과 `app/entrypoint.py`의 관리용 wiring은 유지하거나 새 router에 맞게 조정한다.

`final_project_sample/tests/e2e/test_composer_write_channel.py`, `tests/unit/application/test_composer_service.py`, `tests/integration/api/test_openapi_surface.py`의 v2 기대를 v3 계약으로 바꿔야 한다. 기존 endpoint 유지 여부를 전제로 한 테스트는 삭제 또는 대체 대상이다.

`final_project_sample/pyproject.toml`, `Dockerfile`, `Dockerfile.customer`, `docker/compose.yml`에는 패키지 경계를 다시 확인하는 작업이 필요하다. 설계의 목표대로라면 `acop_composer`는 관리용 build에만 들어가고 고객용 build에는 들어가지 않아야 한다.

### UI 프로젝트 영향

`final_project_ui`는 Core 계약 모델을 import할 필요가 없다. UI는 introspection 응답에서 등록 ID와 현재 flag를 받고, `POST /composer/toggle`에 계약 payload만 보내면 된다. 서버가 등록 ID 존재와 저장 규칙을 책임진다.

단, 기존 v2 UI가 전체 `ProjectConfig`를 편집하도록 이미 구현되어 있다면 화면과 client 호출을 toggle 중심으로 다시 설계해야 한다. 이것은 import 문제는 해결하지만 기능 범위를 줄이는 변경이다.

### 패키지 경계 영향

Composer 코드는 `acop_basement`에서 제거하는 방향과 잘 맞는다. `acop_basement/presentation/api/app.py`의 선택적 주입 구조를 유지하면 고객용 app에는 Composer router를 넣지 않을 수 있다.

다만 현재 `acop_basement/core/settings.py`의 `composer_jwt_secret`, `composer_issuer_secret` 같은 설정 필드와 `project_config.py`의 Composer 관련 registry 보조 구조는 별도 정리가 필요하다. `pyproject.toml`에서 두 패키지가 함께 검색되는 사실도 관리용·고객용 배포 metadata로 분리해 검증해야 한다.

### 작업량

큼에 가깝다. endpoint와 payload 변경만이 아니라 서비스 저장 알고리즘, Core 결합, 인증 scope, 감사 이벤트, UI client, 관련 테스트와 build 검증을 함께 바꿔야 한다. 기존 원자적 쓰기와 revision 검사는 재사용 가능하므로 완전한 재작성은 아니다.

### 위험과 기존 테스트

기존 v2 소비자가 있으면 endpoint와 payload가 깨진다. 특히 `test_composer_write_channel.py`의 `current`, `validate`, `apply`, 동시 `apply`, 구현 불가 `implementation_ref` 검증은 그대로는 실패한다. `test_composer_service.py`는 전체 선언 후보를 대상으로 하므로 새 서비스 테스트로 교체해야 한다.

Core loader가 제공하던 활성 Team 구현체 검증을 toggle 경로에서 의도적으로 하지 않게 되므로, 잘못된 전체 설정이 별도 경로로 유입되는 위험이 있다. 반대로 v3의 범위를 지키면 Composer가 Core 계약 변경에 끌려가는 위험은 줄어든다.

### 되돌리기 쉬운가

중간이다. v2 endpoint와 서비스 구현을 별도 branch나 compatibility adapter로 보존하면 되돌리기 쉽다. 기존 endpoint와 테스트를 즉시 제거하고 데이터 저장 형식까지 바꾸면 되돌리기 어렵다.

## 안 B. 설계를 구현에 맞춘다

한 줄 요약: v3 문서를 접고 현재 v2형 전체 `ProjectConfig` 검증·적용 계약을 정본으로 삼는다.

### 무엇을 바꿔야 하는가

기존 구현을 정본으로 선언하고 `program/plan/A-COP_Composer_v3_설계_토글전용_UI이관.md`를 폐기하거나 v2 계약 문서로 대체해야 한다. 이 작업 자체에서는 기존 설계 문서를 고치지 않으므로, 실제 결정 후 별도 문서 작업이 필요하다.

sample 코드 변경은 상대적으로 적다. `acop_composer/api.py`, `service.py`, `acop_basement/core/project_config.py`의 현재 동작을 계약으로 명시하고, `docs/handoff/13_Composer_쓰기채널_계약.md`, 관련 handoff와 배포 문서를 같은 endpoint·payload·검증 수준으로 정렬하면 된다.

기존 테스트는 v2형 동작을 이미 전제로 한다. 따라서 테스트 파일을 대량으로 바꾸기보다는 계약명과 누락된 실패 경로를 보강하는 쪽이 된다.

### UI 프로젝트 영향

HTTP client 자체는 `ProjectConfig`를 import하지 않아도 된다. 현재 `acop_composer/api.py`의 주석과 payload 구조도 raw dict를 보내고 서버가 검증하는 방식을 설명한다.

그러나 UI가 전체 설정을 편집하고 미리 검증하려면 `ProjectConfig`와 동등한 스키마를 UI에 복제할 유인이 생긴다. 그렇게 하면 v3가 피하려던 Core 계약 복제와 버전 동기화 문제가 다시 발생한다. 따라서 “UI가 Core 모델을 import해야 하는가”에 대한 판정은 직접 import는 불필요하지만, 계약 모델 복제 위험은 높음이다.

### 패키지 경계 영향

Composer는 `acop_basement` 코드에 직접 들어가지 않아도 된다. 현재처럼 `acop_composer` 별도 패키지와 선택적 router 주입을 유지할 수 있다.

다만 v2형 Composer가 `acop_basement.core.project_config`를 import하고, Core가 활성 Team 구현체와 registry를 검증한다. 즉 패키지 디렉터리는 나뉘어도 Composer와 basement의 실행 계약은 깊이 결합된다. 고객용 build에서 Composer를 완전히 배제하려면 `Dockerfile.customer`처럼 복사하지 않는 경로와 `pyproject.toml`의 wheel 산출물 검증을 함께 유지해야 한다. v2 정본 자체가 고객용 build에 Composer 포함을 요구하는 것은 아니지만, 현재 단일 project metadata는 실수 가능성을 남긴다.

### 작업량

작음에서 중간이다. 현재 구현을 보존하는 비용은 낮다. 문서, handoff, API 계약, 배포 acceptance criteria를 실제 v2 동작에 맞추고, UI가 전체 config를 다룰지 확인하는 일이 핵심이다.

### 위험과 기존 테스트

v3의 핵심 목표인 좁은 책임과 Core 결합 축소를 포기한다. Core schema, 활성 Team import, `implementation_ref` allowlist가 바뀔 때 Composer API도 영향을 받는다.

현재 `test_composer_write_channel.py`와 `test_composer_service.py`는 대체로 유지된다. 다만 `test_openapi_surface.py`의 문서화된 API 표면과 `docs/handoff`의 계약을 v2 정본으로 일치시키지 않으면 문서·OpenAPI·실제 동작이 다시 어긋날 수 있다.

### 되돌리기 쉬운가

높다. 현재 구현을 유지한 채 v3를 채택하지 않는 결정이므로 코드 이동이 적다. 나중에 v3로 전환하려면 새 endpoint를 추가하고 기존 계약을 단계적으로 폐기할 수 있다. 다만 v2를 정본으로 문서화하고 외부 소비자가 생기면, 이후 전환의 호환성 비용은 커진다.

## 안 C. 병행한다

한 줄 요약: `toggle`을 추가하고 v2형 endpoint를 일정 기간 유지해 소비자를 단계적으로 이동시킨다.

### 무엇을 바꿔야 하는가

`acop_composer/api.py`에 `/composer/toggle`과 새 payload·응답·scope를 추가하고, `service.py`에 flag 단위 변경 흐름을 추가한다. `/composer/current`, `/composer/validate`, `/composer/apply`와 전체 `ProjectConfig` 경로는 deprecation 기간 동안 남긴다.

두 계약이 같은 파일을 쓰므로 공통 저장 계층을 만들어야 한다. v2의 전체 apply와 v3의 toggle이 같은 `_WRITE_LOCK`, revision 계산, 원자적 교체, audit format을 공유하지 않으면 서로의 변경을 덮거나 revision 의미가 달라질 수 있다.

`tests/e2e/test_composer_write_channel.py`에는 v2 회귀 테스트와 v3 toggle 테스트를 모두 둔다. OpenAPI surface, 인증 scope, audit event, 동시 변경 테스트도 두 계약의 상호작용을 포함해야 한다. handoff 문서에는 deprecation 기간, 제거 조건, 두 endpoint의 권한 차이를 명시해야 한다.

### UI 프로젝트 영향

새 `final_project_ui`는 v3 toggle만 사용하면 Core 계약 모델을 import할 필요가 없다. 기존 v2 소비자는 전체 config 계약을 계속 사용하므로, 그 소비자에 한해서는 Core schema 복제 또는 서버 의존이 지속될 수 있다.

따라서 UI 영향은 이행 기간에 혼합된다. 새 UI를 v3로 만들 수 있지만, 조직 전체가 Core 모델 비의존이라는 목표를 달성했다고 보기는 어렵다.

### 패키지 경계 영향

Composer 코드는 계속 `acop_composer`에 둘 수 있고 `acop_basement`에는 선택적 router wiring만 남길 수 있다. 고객용 build에서 Composer를 빼는 것도 `Dockerfile.customer`와 선택적 인자를 이용해 가능하다.

그러나 v2 compatibility path가 `acop_basement.core.project_config`에 의존하는 동안, 관리용 Composer 패키지와 basement Core의 결합은 유지된다. 두 계약을 동시에 지원하는 동안 Composer를 완전히 제거한 basement wheel을 검증하려면 별도 wheel file-list 또는 import 테스트가 필요하다.

### 작업량

큼이다. 새 v3 경로를 만드는 작업에 더해 두 계약의 공존 규칙, 저장 충돌, 인증 scope, 문서, 테스트, deprecation telemetry를 관리해야 한다. 이미 있는 v2를 보존하므로 단기 migration 위험은 줄지만 총 코드와 검증 범위는 커진다.

### 위험과 기존 테스트

가장 큰 위험은 두 endpoint가 서로 다른 의미로 같은 `project.yaml`을 쓰는 것이다. v2 apply가 전체 config를 덮은 직후 v3 toggle이 동작하거나, 반대 순서로 동작할 때 revision·audit·old/new flag가 일관되지 않을 수 있다.

기존 v2 테스트는 유지할 수 있다. 하지만 새 toggle 테스트가 없으면 병행의 핵심 위험을 검증하지 못한다. `test_composer_write_channel.py`, `test_composer_service.py`, `test_openapi_surface.py`에 계약별 테스트와 교차 호출 테스트를 추가해야 한다.

### 되돌리기 쉬운가

단기적으로는 높다. 기존 소비자를 깨지 않고 v3를 시험할 수 있다. 장기적으로는 낮아진다. 두 계약의 사용자가 늘고 deprecation 기간이 길어지면 제거 시점과 데이터·감사 의미를 조정하기 어려워진다.

## 비교 기준과 결정 질문

설계 문서와 대조 보고서에서 확인되는 기준은 다음과 같다.

| 확인된 기준 | 안 A | 안 B | 안 C |
|---|---|---|---|
| UI가 Core 계약 모델을 import하지 않고 HTTP/raw data만 사용 | 가장 직접적으로 충족 | 직접 import는 피할 수 있으나 전체 schema 복제 위험 | 새 UI에는 충족하지만 구형 소비자와 혼재 |
| Composer를 선택 패키지로 두고 고객용 build에서 배제 | 구조상 충족 가능 | 현재 구조를 유지하며 가능 | 가능하지만 v2 compatibility path의 결합 검증 필요 |
| 등록 ID 확인·flag 원자 쓰기·revision·감사라는 좁은 v3 책임 | 충족 | 포기 | 새 경로에서는 충족, 구 경로에서는 미충족 |
| 기존 v2 테스트와 소비자 연속성 | 깨질 가능성이 큼 | 가장 잘 보존 | 단기 보존 |
| 변경과 되돌리기의 단순성 | 전환 완료 후 단순, 전환 중 큼 | 현재 상태를 보존해 단순 | 단기에는 유연, 장기에는 복잡 |

다음 질문에 답해야 결정할 수 있다.

1. 고객용 build에서 `acop_composer` 파일과 `/composer/*` endpoint를 완전히 배제하는 것이 양보할 수 없는 목표인가?
2. 기존 `/composer/validate`와 `/composer/apply`를 호출하는 외부 소비자나 운영 절차가 실제로 존재하는가?
3. 전체 `ProjectConfig` 교체가 필요한 운영 요구가 남아 있는가, 아니면 운영 요구가 flag toggle로 충분히 좁혀졌는가?
4. `final_project_ui`의 비포크 원칙은 Core 모델의 직접 import만 금지하는가, 아니면 동등한 전체 schema 복제도 금지하는가?
5. v2와 v3를 병행한다면 두 경로가 같은 `project.yaml`을 계속 공유해야 하는가, 아니면 한 경로를 읽기 전용·마이그레이션 전용으로 제한할 수 있는가?
6. deprecation 기간, 종료일, 기존 endpoint 제거의 책임 주체를 정할 수 있는가?

고객용 build에서 Composer 완전 배제가 양보 불가하고 기존 v2 소비자가 없다면 안 A가 가장 직접적으로 기준을 만족한다. 기존 소비자와 전체 config 적용이 필수라면 안 B의 연속성이 우선될 수 있다. 두 사실을 아직 확인하지 못했다면 안 C가 시험 기간을 제공하지만, 병행 기간과 제거 조건을 먼저 정해야 한다.

## 권고

권고: 고객용 Composer 완전 배제와 기존 v2 소비자 유무를 먼저 확인하고, 전자가 필수이며 후자가 없으면 안 A를 택하되, v2 소비자나 전체 config 적용이 필수라는 답이면 안 B 또는 명시적 종료일이 있는 안 C로 결정한다.
