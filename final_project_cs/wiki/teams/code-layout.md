---
type: guide
title: 에이전트 팀 코드·시험 경로
description: D-CS-013의 실제 구현·시험 경로와 공통 영역 변경 경계를 안내한다
status: draft
tags: [agent, architecture]
domain: travel
---

# 에이전트 팀 코드·시험 경로

에이전트 팀 구현은 `app/domains/travel_ops/instances/` 아래에 있습니다. **개발 담당 배치와 공유 계약 검토 절차는 [기능 책임 안내](../../../wiki/delivery/roles.md)가 정본**입니다. 이 페이지는 실제 코드·시험 위치를 안내합니다.

## 에이전트 팀별 경로

| 에이전트 팀 | 현재 구현 | 단위 시험 입구 |
|---|---|---|
| Activity | [instances/activity/](../../app/domains/travel_ops/instances/activity/) | [tests/unit/travel/activity/](../../tests/unit/travel/activity/) |
| Dining | [instances/dining/](../../app/domains/travel_ops/instances/dining/) | [tests/unit/travel/dining/](../../tests/unit/travel/dining/) 및 [travel/](../../tests/unit/travel/)의 `test_dining_*.py` |
| Mobility | [instances/mobility/](../../app/domains/travel_ops/instances/mobility/) | [tests/unit/travel/mobility/](../../tests/unit/travel/mobility/). 출발·이동 공통 시험은 [travel/](../../tests/unit/travel/)에도 있음 |
| Booking Handoff | [instances/booking_handoff/](../../app/domains/travel_ops/instances/booking_handoff/) | [근거 누적 시험](../../tests/unit/travel/test_evidence_accumulates.py), [승인 대기 연결 시험](../../tests/integration/controller/test_travel_approval_proposal_reaches_waiting.py). 등록·코드 존재를 MVP 제공 완료로 해석하지 않음 |
| Lodging·Flight | [instances/locked/](../../app/domains/travel_ops/instances/locked/) | 등록 전용·잠긴 예약 경계는 아래 등록 도달성 시험에서 확인. 자체 변경 기능 완료를 뜻하지 않음 |

[project.yaml](../../config/project.yaml)의 `implementation_ref`가 등록할 클래스의 정본입니다. 파일 하나·패키지·파일과 별도 엔진의 구조가 가능하므로 클래스가 실제로 정의된 곳은 import 결과로 확인합니다. 같은 이름의 파일과 패키지 폴더를 동시에 남기지 않습니다.

## 공통 기능과 고객 웹

아래 위치는 수정 영역 안내이며 새 담당자를 배정하는 표가 아닙니다.

| 기능 | 현재 구현 위치 |
|---|---|
| Case 흐름·에이전트 팀 선택·공유 계약 | [app/application/](../../app/application/), [app/core/registry.py](../../app/core/registry.py), [app/core/contracts.py](../../app/core/contracts.py) |
| 공통 API 인증·웹 계정 | [presentation/security.py](../../app/presentation/security.py), [modules/web_account/](../../app/domains/travel_ops/modules/web_account/) |
| 실행 안전·업무 실행 처리기 | [core/actions.py](../../app/core/actions.py), [application/proposal_guard.py](../../app/application/proposal_guard.py), [components/actions/](../../app/domains/travel_ops/components/actions/) |
| DB 접근·SQL 파일 | [infrastructure/db/](../../app/infrastructure/db/), [마이그레이션 안내](../data/migrations.md) |
| 고객 여행 웹 | [frontend/apps/web/src/](../../frontend/apps/web/src/), [웹 시험](../../frontend/apps/web/tests/). API 연결은 [entry/trip_api.py](../../app/domains/travel_ops/entry/trip_api.py), 기존 계획 링크 HTML은 같은 입구의 `/plan/{trip_id}`에서 제공 |
| 기존 운영 화면 | [presentation/ui/](../../app/presentation/ui/) — 고객 여행 웹과 다른 코드. 코드가 있다는 이유로 상주 고객 상담 운영 방침을 만들지 않음 |
| 여행 평가·통합 | [eval/](../../eval/), [tests/integration/travel/](../../tests/integration/travel/), [품질 지도](../quality/index.md) |

루트의 별도 `final_project_ui/`는 개발 콘솔입니다. 이를 고객 여행 웹으로 혼동하지 않습니다. 웹/API의 자세한 연결은 [화면별 연동 계약](../external/web-screen-api.md)을 따릅니다.

## 변경 경계와 검사

에이전트 팀 구현에서 다른 에이전트 팀 구현을 직접 import하지 않습니다. 다른 에이전트 팀의 일정 재계산은 [D-CS-013](../decisions/D-CS-013-domain-folder-layout.md)의 `watch_planners` 등록 경로를 사용합니다. TeamRegistry가 선택하고 실행 계약으로 호출하는 구조와 개발 담당자의 브랜치 이름은 별개입니다.

| 확인할 것 | 기존 시험 |
|---|---|
| 등록 클래스 도달성·파일/폴더 충돌 | [test_team_layout.py](../../tests/contract/test_team_layout.py) |
| 업무 폴더 사이 의존 방향 | [test_travel_ops_cells.py](../../tests/architecture/test_travel_ops_cells.py) |
| 에이전트 팀의 직접 인프라 호출·허용 도구 | [test_team_tool_discipline.py](../../tests/contract/test_team_tool_discipline.py) |
| Core와 에이전트 팀 격리 | [test_core_isolation.py](../../tests/contract/test_core_isolation.py) |
| 인증·데이터 격리 | [tests/security/](../../tests/security/) |
| 웹/API 계약 | [test_web_client_contract.py](../../tests/contract/test_web_client_contract.py) |

pytest 시험은 `tests/`, 별도로 실행하는 수집·생성·점검 스크립트는 `scripts/`에 둡니다. 외부 데이터가 필요한 시험은 자료 유무와 건너뛴 이유를 기록합니다. 팀별 하위 폴더만 실행하고 여행 전체 회귀가 통과했다고 적지 않습니다.

## 관계

- [기능 책임·공유 계약 변경](../../../wiki/delivery/roles.md) — 누가 구현·검토·검증하는가
- [D-CS-013](../decisions/D-CS-013-domain-folder-layout.md) — 폴더 구분과 의존 방향
- [Team 계약](team-contract/index.md) — 공유 입력·출력 경계
- [문서 작성 표준](../../../wiki/governance/document-standard.md) — 근거·정본·기록 분리

## 확인 근거

2026-10-12 후속 검토의 현재 경로·관련 시험은 [이번 결과](../../../program/research/baseline_completion_2026-10-12/tasks/wiki/report.md)에 기록합니다. 아래의 2026-10-11 결과를 오늘 실행한 결과로 재사용하지 않습니다.

[실측 2026-10-11 작업 트리] 위 경로의 존재, 설정의 등록 클래스 도달성, 업무 폴더 의존 검사를 확인했습니다. 실행한 시험·결과·한계와 수정 전 사본은 [W16 재검토 보고서](../records/reports/2026-10-11_2117_W16-responsibility-review.md)에 있습니다. 시험 입구를 열거한 것은 그 시험 전부의 통과를 뜻하지 않습니다.
