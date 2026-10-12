---
type: contract
title: 구성 단위와 조립 선언
description: 필수 컴포넌트·선택 모듈·교체 Port·Team 인스턴스의 로딩과 요청별 조립 판
status: draft
domain: neutral
---

# 구성 단위와 조립 선언

2026-10-11 로컬 구현 기준입니다. 비활성 Team은 불러오지 않고 그 업무를 실행하지 않습니다. 필수 코어와 독립 조회는 유지합니다. 운영 반영·전체 회귀 완료 상태는 [수명 관리](team-plugin-lifecycle.md)에서 확인합니다.

## 구성 단위

| 단위 | 의미 | 실제 경계 |
|---|---|---|
| 컴포넌트 | 제품 성립에 필요한 고정 부품 | Core 상태기계·계약·Registry·Controller·DB·Outbox |
| 모듈 | 제거해도 독립 기능이 유지되는 기능 | web_account·mcp·live_progress 등, 기능별 게이트 |
| Port | 동일 계약의 구현 교체 | TeamExecutorPort Local/A2A, MessageBrokerPort, GraphStorePort |
| 인스턴스 | 동일 TeamModule 계약으로 추가·제거하는 담당 | manifest + execute, 조립이 주입 |

인라인 분류와 공통 업무 상태 처리는 필수 컴포넌트입니다. voc 모듈을 껐다는 이유로 분류를 제거하지 않습니다. Team은 제안하고 Core가 부작용을 적용합니다.

## 선언 필드와 호환성

[실제 선언](../../config/project.yaml)은 modules·ports·teams를 가집니다. Team 필드는 다음과 같습니다.

| 필드 | 형식·기본값 | 의미 |
|---|---|---|
| team_id | 비어 있지 않은 문자열 | 고유 담당 id |
| active | bool, 필수 | false면 import·생성·실행하지 않음 |
| implementation_ref | module:Class, 필수 | 활성 구현의 조립 위치 |
| required | bool, 기본 true | 활성 구현 적재 실패 시 후보 전체 거절 여부 |
| capabilities | 중복 없는 목록 또는 None | 명시하면 실제 manifest와 일치해야 함 |
| hooks | 중복 없는 목록 또는 None | 계산 제공 경계 선언 |

구현 참조 문법·선언 id/capability 중복은 정적으로 검사합니다. 정적 검증 단계에서는 구현을 import하지 않습니다. 기존 required 미지정 선언은 필수 Team 의미를 유지합니다. inactive에서는 required가 true여도 구현을 적재하지 않습니다.

```yaml
teams:
  - team_id: mobility
    active: false
    required: true
    implementation_ref: app.domains.travel_ops.instances.mobility:MobilityTeam
    capabilities: [mobility.itinerary]
```

위 예시는 패키지가 설치되지 않아도 비활성 구현을 불러오지 않습니다. 실제 모듈·Port 조합은 [선언 모델](../../app/core/project_config.py)과 [조립 코드](../../app/composition.py)가 검증합니다. 미구현 Port 선택을 자동 대체하지 않습니다.

## 적재 실패와 후보 게시

| 조건 | 현재 정책 |
|---|---|
| inactive Team | 구현 import·생성 0회, disabled 메타데이터 |
| 명시적 선택 Team의 import·생성·provider 실패 | 해당 팀 load_failed, 수집 중 일부 계산은 폐기 |
| 필수 Team·필수 코어 실패 | 후보 실패, 기존 판 유지 또는 최초 기동 실패 |
| manifest 계약·선언 capability 불일치·중복 | 선택 여부와 관계없이 후보 실패 |
| 활성 필수 엔진 데이터 불가 | engine_unavailable, 추정 성공 금지 |
| 후보 완성 | Controller·Registry·Executor·계산 표·revision 함께 게시 |

선택 적재 실패와 활성 엔진 장애를 같은 예외로 숨기지 않습니다. 비활성 Team의 이름과 알려진 담당 관계는 구현 import 없는 메타데이터로 보존할 수 있습니다.

## 요청·백그라운드 회차의 같은 조립 판

[BindingTable](../../app/core/service_bindings.py)은 복사한 읽기 전용 계산 표를 가집니다. 후보 조립의 register는 후보 수집 표에만 들어갑니다. 완료된 Controller가 해당 표와 revision을 보유합니다.

[RuntimeComposition](../../app/application/runtime.py)은 완성된 새 판을 짧은 잠금에서 게시하고 reload 작업을 직렬화합니다. 요청은 pure ASGI middleware에서 판 하나를 고정해 SSE 종료와 동기 threadpool까지 유지합니다. 백그라운드는 한 회차에 고정합니다. 운영용으로 조립한 Controller를 직접 주입해도 그 Controller의 실제 revision을 사용합니다.

이전 요청은 이전 판으로 종료하고 새 요청만 새 판을 사용합니다. 전체 clear/register 후 Controller만 교체하지 않습니다. 별도 강제 drain·가변 disable API는 추가하지 않았습니다. 이동 엔진 데이터·경유 설정 변경은 재기동 대상이며 활성/비활성 Team 교체와 구분합니다.

## 계산과 선택 기능의 끼움 자리

| 자리 | 제공자 | 부재 정책 |
|---|---|---|
| team_hooks.legs 필수 이동 함수 | Mobility | 해당 의존 요청 503, 어림값 우회 금지 |
| team_hooks.dining_ledger state/states/catalog_state | Dining | 영업 판정 503. 등록 전도 같은 관문 |
| dining_ledger 근처 목록 보강·이름 찾기 | Dining | 독립 조회의 보강만 생략·이유 기록 |
| team_hooks.similarity | Activity | 독립 정렬의 선택 신호 생략·이유 기록 |
| team_hooks.watch_planners | 해당 Team | 해당 종류 감시 미실행 기록 |
| settings_hook·progress_hook·trip_scope | 선택 모듈 | 기능별 기존 독립 기본값 유지 |
| ports/data_sources/simulation_hook | 시나리오 어댑터 | 자료 소스 계층이 감시 구현을 직접 import하지 않음 |

Team callback은 조립 때 실제 함수를 고정합니다. 호출 때 다른 판의 모듈 함수를 다시 읽어 섞지 않습니다. 전역 register/clear는 명시적 standalone_services 경계에 한정하며 제품 요청의 무조건 fallback이 아닙니다. wire_optional_features는 후보 조립 밖에서 앱·작업 프로세스의 선택 기능을 연결합니다.

## 실패 관찰과 검증

JSON/SSE/MCP의 필수 Team 불가는 team_unavailable이며 HTTP는 503입니다. 사전에 확인 가능한 불가는 업무 입력·토큰을 소비하기 전에 거절합니다. 원격 실행 후 장애의 감사 기록·재시도는 [가용성 계약](team-contract/plugin-availability.md)에 따릅니다.

회차 조립 실패는 Team 의존 작업에만 영향을 주며 독립 정리·분류·기존 주기 안전 점검을 계속합니다. [인수 조건 매핑](../records/evidence/2026-10-11_1936_team_plugin_implementation/acceptance-mapping.json)에서 실제 시험을 확인합니다. [D-CS-013](../decisions/D-CS-013-domain-folder-layout.md)은 폴더와 의존 방향의 정본입니다.

- [Registry](team-registry.md), [Team 계약](team-contract/index.md), [수명 관리](team-plugin-lifecycle.md)
- [Core 중립성 검사](../../tests/architecture/), [조립 판 시험](../../tests/unit/test_plugin_composition_runtime.py)
