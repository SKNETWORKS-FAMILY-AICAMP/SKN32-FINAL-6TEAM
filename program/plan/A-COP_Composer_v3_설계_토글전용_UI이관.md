# A-COP Composer v3 설계 — 토글 전용 UI 이관

> **정정 2026-08-28.** 이 문서의 두 가지가 뒤에 바로잡혔다.
> 첫째, 토글 전용 범위는 사용자 요구를 충족하지 못한다. `A-COP_Composer_범위재검토.md`가 정본이다.
> 둘째, Composer 소유권은 sample이 만들고 UI가 가져다 쓰는 것이다. `A-COP_Composer_소유권_정정.md`가 정본이다.
> 충돌하면 그 두 문서를 따른다.

## 목차

1. [배경과 결론](#1-배경과-결론)
2. [v3 계약 — 토글 전용](#2-v3-계약--토글-전용)
3. [프로젝트별 책임 재배정](#3-프로젝트별-책임-재배정)
4. [pip화와의 관계](#4-pip화와의-관계)
5. [기존 v2 계약과의 관계](#5-기존-v2-계약과의-관계)
6. [다음 실행 단계](#6-다음-실행-단계)
7. [정합성 및 범위 확인](#7-정합성-및-범위-확인)
8. [패키징](#8-패키징)

## 1. 배경과 결론

결론부터 말하면 Composer의 쓰기채널은 v2의 “전체 ProjectConfig 선언 제출·검증·적용”에서 v3의 “등록된 항목의 활성 상태만 변경”으로 축소한다. 판단·화면·요청 전송은 `final_project_ui`가 맡고, 대상은 등록 여부 확인과 해당 flag의 원자적 변경·감사만 맡는다. 대상의 Core 계약 모델은 UI로 가져오지 않는다.

v2가 필요 이상으로 넓었던 이유는 다음과 같다.

- v2는 임의의 새 선언을 통째로 제출하게 하고, 서버가 `TeamManifest` 등 Core 계약으로 깊이 검증한 뒤 적용하는 모델이었다.
- 그러나 `implementation_ref`는 임의 경로가 아니라 제품이 미리 등록한 registry ID allowlist에서만 고르게 이미 제한돼 있었다.
- 따라서 실제 운영 요구는 새 구현을 등록하거나 계약 구조를 설계하는 일이 아니라, 등록된 모듈·Team·Port를 켜고 끄거나 제외하는 좁은 관리 작업이다.
- 좁은 토글에는 등록 ID 목록과 현재 상태, 그리고 ID와 활성 상태를 담은 최소 요청만 필요하다. `ProjectConfig`·`TeamManifest`를 UI가 복제하거나 검증할 이유가 없다.

이 결론에 따라 Composer의 판단·요청 로직과 화면은 pip 패키지화 완료를 기다리지 않고 `final_project_ui`로 이관한다. `final_project_sample`의 basement를 `acop_basement`로 분리하는 pip화는 Core 코드의 배포·중복 문제를 다루는 별도 트랙이다.

## 2. v3 계약 — 토글 전용

### 2.1 대상이 제공해야 하는 것

대상은 기존 read-only introspection 응답을 재사용하거나 확장해, 제품이 등록해 둔 항목의 ID와 현재 상태를 제공한다. UI는 대상 프로세스의 Python이나 Core 모델을 import하지 않고 응답을 raw data로 취급한다.

제안하는 응답 형태는 기존 명명 관례(`contract_version`, `config_revision`, `modules`, `ports`, `teams`)를 보존하면서 등록 목록을 명시하는 방식이다.

```json
{
  "contract_version": "introspection.v3",
  "config_revision": "<content-hash>",
  "registered_ids": {
    "modules": ["vector_rag", "graph_store", "a2a_executor", "mcp", "voc", "ops_ui"],
    "teams": ["order_shipping", "return_exchange"],
    "ports": ["team_executor", "message_broker", "graph_store"]
  },
  "modules": {
    "vector_rag": {"enabled": true}
  },
  "teams": {
    "order_shipping": {"active": true}
  },
  "ports": {
    "team_executor": {"active": true}
  }
}
```

`modules`와 `teams`의 현재 선언 형태는 각각 `enabled`와 `active`를 유지한다. Port는 현재 선언이 값 선택형일 수 있으므로, 토글 가능한 Port만 대상 응답에서 명시적 `active` flag를 제공한다. 단순히 연결 방식 값을 선택하는 Port를 임의로 활성/비활성으로 해석하지 않는다.

### 2.2 UI가 보내는 요청

v2의 `config` 전체 대신 대상 종류·등록 ID·활성 상태만 보낸다. 기존 v2의 `base_revision`과 `reason` 관례는 동시 수정 방지와 감사 추적을 위해 유지한다.

```json
{
  "target_type": "module",
  "target_id": "vector_rag",
  "active": false,
  "base_revision": "<config_revision>",
  "reason": "운영 점검 중 임시 비활성화"
}
```

여기서 `target_type`은 `module`, `team`, `port` 중 하나이고 `target_id`는 introspection의 `registered_ids`에 있어야 한다. `module`에는 `active`를 `enabled`로, `team`에는 `active`로 매핑하는 등 저장 필드의 차이는 대상 내부에서 처리한다. UI는 Core 스키마를 재현하지 않는다.

제안 endpoint는 `POST /composer/toggle`이다. 읽기는 기존 introspection과 Composer의 read scope를 재사용할 수 있고, 쓰기는 `composer:write` scope를 사용한다. 구현 시 인증 방식은 기존 단명 JWT·scope 분리 원칙을 유지한다.

### 2.3 대상이 처리하는 것

대상의 처리는 다음 네 단계로 한정한다.

1. 요청의 `target_type`과 `target_id`를 현재 등록 목록과 대조한다. 목록에 없으면 거부한다. 이것은 새 선언의 깊은 검증이 아니라 등록 ID 존재 확인이다.
2. `base_revision`이 현재 `config_revision`과 다르면 기존 revision 충돌로 거부한다.
3. 해당 등록 항목의 flag만 바꾼다. 전체 `ProjectConfig`를 새로 구성하거나 다른 모듈·Team·Port를 재계산하지 않는다. 임시 파일 작성 후 교체하는 원자적 쓰기와 기존 백업·복구 안전장치를 유지한다.
4. 요청자, 대상 종류, 대상 ID, 이전 상태, 새 상태, base/current revision, 사유, 결과를 append-only 감사 로그에 남긴다.

성공 응답은 최소한 새 `config_revision`, 대상 ID, 새 상태를 반환한다.

```json
{
  "target_type": "module",
  "target_id": "vector_rag",
  "active": false,
  "config_revision": "<new-content-hash>",
  "audit_id": "<event-id>"
}
```

### 2.4 명시적으로 안 되는 것

> ★**2026-08-29 정정** — 아래 두 번째 항목("등록 목록 자체를 추가·삭제")은
> **철회됐다.** 사용자 요구가 켜고 끄기보다 넓다는 것이 확인돼, 카탈로그에
> 등록된 구현의 **인스턴스 생성·삭제**가 정본 관리 계약이 됐다
> (`GET /composer/catalog`·`POST /composer/changes` — 구현·검증 완료).
> 첫 번째 항목(**임의 Python 경로 제출 금지**)은 그대로 유효하다 — 고를 수
> 있는 것은 카탈로그에 등록된 구현뿐이다.
> 근거: `A-COP_Composer_범위재검토.md`,
> `A-COP_Composer_중앙설정저장소_결정.md`,
> `final_project_sample/docs/handoff/13_Composer_쓰기채널_계약.md`.

- 새 `implementation_ref`를 임의 값으로 제출해 registry에 등록하는 것
- ~~등록 목록 자체를 Composer 요청으로 추가·삭제하는 것~~ (2026-08-29 철회)
- `ProjectConfig`, `TeamManifest`, `ContextPack` 등 Core 계약 구조를 바꾸는 것
- 여러 선언을 통째로 덮어쓰거나, UI가 대상의 검증 모델을 복제해 사전 검증하는 것
- 토글을 코드 배포·새 Team 구현·Port 구조 변경의 대체 수단으로 사용하는 것

위 작업은 코드 또는 배포 변경이 필요한 별도 작업이다. v3 토글의 범위가 아니다.

## 3. 프로젝트별 책임 재배정

| 프로젝트 | v3 책임 | 하지 않는 것 |
|---|---|---|
| `final_project_ui` | introspection에서 등록 ID·현재 상태를 읽고, 화면에서 활성 상태를 판단하며, 최소 토글 요청을 인증해 전송 | Core 계약 모델 import·복제, 대상 파일 직접 쓰기, 대상 Python import |
| `final_project_cs` | 릴리즈 대상. 등록 ID 확인 → flag 원자적 변경 → 감사 로그를 수행하는 최소 endpoint만 보유하거나 향후 제거 | Composer 화면·판단 로직·전체 선언 검증·Composer 관련 공용 파일 보유 |
| `final_project_sample` | pip 배포용 basement 소스, Team 모듈 예제 라이브러리(`examples/`), **그리고 UI가 가져다 쓸 Composer 판단·요청 로직**을 만든다 | 대상 제품의 Team 도메인 구현 |

### 3.1 `final_project_ui`와 기존 §0.2·§0.3 원칙의 양립

| 기존 원칙 | v3에서의 적용 | 충돌 여부 |
|---|---|---|
| §0.2: UI는 화면과 읽기 어댑터이고 대상 Core 모델을 포크하지 않는다 | 등록 ID·상태는 introspection raw data로 읽고, 토글 요청은 좁은 외부 API 계약으로만 전송한다 | 충돌 없음 |
| §0.2: 대상 선언의 유효성 판정은 대상 책임이다 | UI는 ID가 등록 목록에 있는지와 응답 상태만 표시·분기한다. Core 구조의 유효성을 판정하지 않는다 | 충돌 없음 |
| §0.3: 대상 프로젝트의 Python을 import하지 않는다 | `ProjectConfig`·`TeamManifest`를 import하지 않고, 기존처럼 raw dict/HTTP 응답만 사용한다 | 충돌 없음 |
| §0.3: 대상 파일·DB를 직접 쓰지 않는다 | 쓰기는 인증된 대상 endpoint가 대상 프로세스 안에서 수행한다. UI는 `POST /composer/toggle`만 호출한다 | 충돌 없음 |
| §0.3의 Composer API 예외 | 전체 선언 적용 예외를 토글 전용 인증 API 예외로 좁힌다 | 원칙을 구체화함 |

기존 UI 코드에서 `console/discovery.py`는 대상의 introspection 자료 존재 여부를 탐지하고, `console/live.py`의 `read_introspection()`은 `GET`으로 응답을 읽은 뒤 `contract_version`을 확인한다. `console/readers.py`의 `read_declaration()`도 `project.yaml`을 검증 모델로 파싱하지 않고 `modules`·`ports`·`teams`의 표시용 raw 값만 만든다. v3는 이 경로에서 이미 확보하는 등록 목록·상태 데이터를 Composer 화면에 재사용한다.

기존 `console/composer.py`의 `read_current()`·`validate_candidate()`·`apply_candidate()` 중 v3에서 유지할 것은 인증, raw dict 통신, scope 분리, revision 충돌 결과 처리다. 전체 후보 JSON 편집·validate·apply 화면과 함수는 토글 UI 및 `toggle` 요청으로 대체한다.

## 4. pip화와의 관계

두 작업은 선행조건이 아닌 병렬 트랙이다.

```text
트랙 A — Composer v3 UI 이관
  introspection 등록 목록 재사용
        → final_project_ui 토글 화면·판단·요청
        → cs 최소 /composer/toggle 적용 endpoint

트랙 B — basement pip화
  final_project_sample basement 분리
        → acop_basement 패키지화
        → cs가 pip install하고 자기 Team 모듈만 보유
```

트랙 A는 등록 ID를 제공하는 현재 introspection과 좁은 대상 endpoint 계약만으로 진행할 수 있다. 트랙 B의 `acop_basement` 배포 준비가 끝나야 트랙 A를 시작하거나 완료할 수 있는 구조가 아니다. 반대로 pip화가 진행 중이라는 이유로 UI의 Composer 판단·요청 로직 이관을 미룰 필요도 없다.

## 5. 기존 v2 계약과의 관계

이 문서는 `final_project_sample/docs/handoff/13_Composer_쓰기채널_계약.md`의 v2를 대체하는 v3 제안이다. v2의 인증, scope 분리, revision 충돌 방지, 원자적 쓰기, 감사라는 안전장치는 유지하되, 전체 선언 제출·Core 깊은 검증·전체 apply라는 범위는 제거한다.

해당 v2 파일은 현재 다른 세션에서 실시간으로 작업 중이므로 이번 작업에서 열거나 직접 병합하지 않았다. v2 작업이 끝난 뒤 담당 세션에서 이 v3 제안과 계약 내용을 대조해 반영해야 한다. 특히 endpoint 이름, 응답의 `config_revision`, 인증 scope, 감사 로그 필드는 최종 계약에서 하나의 명명으로 확정한다.

## 6. 다음 실행 단계

이 설계가 승인된 뒤에 다음 순서로 실제 코드를 옮긴다.

1. 대상 endpoint 계약을 확정한다: `POST /composer/toggle`, `target_type`, `target_id`, `active`, `base_revision`, `reason`, 성공·실패 응답, 인증 scope.
2. introspection 응답에 `registered_ids`와 토글 가능한 현재 상태가 이미 있는지 확인하고, 부족한 경우 최소 확장만 정의한다. Core 계약 모델을 UI로 복사하지 않는다.
3. `final_project_cs`에는 등록 ID 확인, revision 비교, 해당 flag의 원자적 쓰기, append-only 감사 로그만 구현한다.
4. `final_project_ui`에는 introspection 목록을 재사용하는 모듈·Team·Port 토글 화면과 raw dict 요청 어댑터를 구현한다.
5. 기존 Composer 화면·코드에서 전체 JSON 편집, `validate_candidate`, 전체 `apply_candidate`, Core 선언 구조 표시·검증에 해당하는 항목을 제거하거나 토글 경로로 대체한다.
6. UI와 대상에 대해 미등록 ID, revision 충돌, 인증 실패, 원자적 쓰기 실패, 감사 로그 실패, 대상 미응답을 각각 검증한다.
7. 릴리즈 대상에서 Composer UI·판단 코드가 물리적으로 남아 있지 않은지 검색하고, 남길 최소 endpoint 외의 Composer 관련 파일을 제거한다.
8. 마지막으로 v2 계약 담당 세션의 결과와 v3 명명·scope·응답을 대조하고, `program/research/index.md`의 현재 기준 사실 표에 새 사실을 추가할 필요가 있는지 판정한다.

## 7. 정합성 및 범위 확인

`program/research/index.md`의 “현재 기준 사실” 표는 문서 기준선, CS Pack 및 검증 쇼핑몰 Team 목록, DoD 수, 배포 단계와 일정을 현재 사실로 관리한다. 이번 문서는 Composer v3의 책임·API 범위를 설계하며 그 표의 DoD·Team 목록을 변경하지 않는다. 따라서 현재 확인한 범위에서는 충돌이 없다. 실제 Team 목록을 v3 문서의 예시로 새로 확정하지 않고, 확인한 대상의 현재 등록 ID를 계약 예시로만 사용한다.

이번 작업은 이 문서 파일 하나를 새로 작성하는 것으로 한정한다. `final_project_sample/`은 읽거나 수정하지 않았으며, v2 원문도 열지 않았다.

## 8. 패키징

### 8.1 패키지 구성

- `acop_basement` — Core/Team/Registry/Controller 런타임을 담는다. 릴리즈 대상인 cs가 항상 설치하는 패키지이며, 컴포저 관련 코드는 포함하지 않는다.
- `acop_composer` — 대상 제품이 선택적으로 설치하는 토글 적용 endpoint glue다. 등록 ID 확인, flag 원자적 쓰기, 감사 로그를 담당한다. 고객용 릴리즈 빌드에는 이 패키지 자체를 설치하지 않는다. `.dockerignore` 같은 빌드 제외 임시방편이 아니라, 애초에 이 패키지가 설치되지 않은 빌드는 컴포저 파일이 존재할 수조차 없게 하는 것이 핵심이다.
- `final_project_ui` — pip 패키지로 배포하지 않는 독립 실행 서비스다. 대상에는 HTTP로만 접속한다. **Composer 판단·요청 로직은 sample이 만든 패키지를 pip install해서 쓴다.** §0.3이 금지하는 것은 **대상**(`final_project_cs`)의 Python을 import하는 것이지, sample 산출물을 쓰는 것이 아니다. sample은 대상이 아니라 공용 구현체다. 이 구분은 `A-COP_Composer_소유권_정정.md`가 정본이다.

개발은 전부 `final_project_sample` 한 저장소에서 진행하되, 배포만 `acop_basement`와 `acop_composer`라는 두 개의 별도 패키지로 나눈다. 이는 Django 같은 프레임워크가 코어 위에 부가 기능을 별도 패키지로 배포하는 것과 같은 패턴이다. 같은 저장소에서 함께 개발하는 편의와, cs에는 basement만 주고 관리 가능한 빌드에는 composer를 선택적으로 추가하는 배포 경계를 동시에 유지한다.

| 구성 | 배포 원칙 |
|---|---|
| `acop_basement` | cs가 항상 설치 (Core/Team/Registry/Controller, 컴포저 없음) |
| `acop_composer` | 별도 선택 패키지, “관리용 빌드”에만 설치 (토글 엔드포인트 glue) |
| `final_project_ui` | 패키지 아님, 독립 서비스. HTTP로만 대상에 접속 |

### 8.2 아키텍처 경계 테스트

`acop_basement`를 실제로 wheel로 빌드한 뒤, 빌드 산출물의 파일 목록을 실제로 열어 `acop_composer` 또는 컴포저 관련 파일이 0개인지 검사하는 자동 테스트를 도입할 것을 권고한다. 기존 저장소에 있는 “basement가 도메인 코드를 안 섞는지” 검사하는 아키텍처 테스트(예: `test_basement_is_domain_free.py` 계열)와 같은 원리로, “basement가 composer를 안 섞는지”를 검사하는 짝 테스트다.

단순히 “import 안 한다”는 사실을 코드 리뷰로만 믿어서는 안 된다. basement와 composer를 같은 저장소에서 함께 개발하므로, 실수로 composer 코드나 파일이 `acop_basement` 빌드에 섞일 위험이 실제로 남아 있다. 따라서 import 의존성 검사가 아니라 wheel 파일 목록을 빌드 후 직접 검사하는 경계 테스트로 강제한다.
