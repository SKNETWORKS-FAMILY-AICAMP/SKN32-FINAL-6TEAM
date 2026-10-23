---
type: concept
title: Team Registry
description: 도메인 구현을 import하지 않고 주입받은 Team의 메타데이터와 실행 가능성을 확인한다
status: draft
domain: neutral
---

# Team Registry

2026-10-11 로컬 구현 기준입니다. 담당이 없거나 꺼져 있으면 해당 업무를 실행하지 않습니다. 운영 반영은 [수명주기 검증 상태](team-plugin-lifecycle.md)와 구분합니다.

Registry는 Team을 import하거나 생성하지 않습니다. 조립 루트가 구현 또는 비가용 메타데이터를 주입합니다. Core는 여행 이름·업무별 SQL을 알지 않습니다.

## 읽기와 실행을 구분하는 입구

| 입구 | 의미 | 실패 |
|---|---|---|
| register(team) | manifest와 구현 등록 | 중복 id/capability·major 계약 불일치: RegistryError |
| declare_unavailable(team_id, reason) | 구현 import 없이 비가용 선언 | 선언 모순·중복: RegistryError |
| declare_case_types(team_id, case_types) | 도메인이 알려준 담당 관계만 보관 | 모호한 실제 해결: RegistryError |
| get(team_id) | 메타데이터 조회 | 미등록: RegistryError. 실행 허가 아님 |
| require_runnable(team_id, capability) | 활성·적재·계약·소유 확인 후 실행 객체 | 부재·비활성: TeamUnavailable, 계약 위반: TeamContractViolation |
| resolve(case_type) | 활성 제공자 하나 선정 | 알려진 담당 부재: TeamUnavailable, 미분류·모호함: RegistryError |

get으로 읽은 inactive 객체를 직접 실행해서는 안 됩니다. Controller·Local/A2A 실행기와 필수 계산 경계는 require_runnable을 사용합니다. 비활성 선언은 실제 구현 객체를 만들지 않아 get용 manifest가 항상 존재한다고 가정할 수 없습니다.

## 미분류와 알려진 담당 부재

other/general처럼 알려진 담당 관계가 없는 분류는 기존 RegistryError를 유지합니다. Controller는 한 번 재배분하거나 routing_failed로 기록합니다. 제공자 0개를 모두 503으로 바꿔 업무를 고정하지 않습니다.

예를 들어 도메인이 dining 종류의 담당을 Dining으로 알려줬는데 해당 구현이 제거됐으면 not_installed입니다. 담당 관계는 [순수 도메인 메타데이터](../../app/domains/travel_ops/components/core_hooks/routing.py)에서 주입하며 Registry 안에 여행 종류를 하드코딩하지 않습니다. 실제 활성 manifest가 제공하는 종류는 기존 정상 해결을 우선합니다.

## 후보 조립과 실행 관문

선언 문법 검증은 구현 import와 분리합니다. inactive 구현은 불러오지 않습니다. 선택 적재 실패만 load_failed로 격리합니다. 계약 오류·필수 적재 실패는 후보를 거절하며 이전 조립을 유지합니다. capability는 제공자 하나만 허용하고 major 계약 호환을 검사합니다.

실행 관문은 담당 ROUTED 저장·재개 입력 반영·토큰 소비 전에 적용합니다. 선택된 Registry는 요청의 Controller·Executor·BindingTable과 같은 revision입니다. 새 Registry를 만들었다고 실행 중인 요청의 등록표를 교체하지 않습니다.

## 검증과 관계

[미분류·담당 부재 회귀 190/190](../records/evidence/2026-10-11_1936_team_plugin_implementation/unknown-route-regression-v3.log)은 실제 Registry와 로컬 DB Controller를 포함합니다. [인수 매핑](../records/evidence/2026-10-11_1936_team_plugin_implementation/acceptance-mapping.json)은 자동·직접 실행, 비활성·제거·재개 조건을 연결합니다. 로컬 검증이며 실제 원격 기계의 가용성을 보장하지 않습니다.

- [코드](../../app/core/registry.py), [실행 오류](../../app/core/team_availability.py)
- [구성 선언](composition.md), [가용성 계약](team-contract/plugin-availability.md), [수명 관리](team-plugin-lifecycle.md)
