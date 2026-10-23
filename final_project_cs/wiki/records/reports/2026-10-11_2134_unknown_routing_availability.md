---
type: report
title: 미분류 재배분과 알려진 담당 부재 구분
status: verified
domain: travel
---

# 미분류 재배분과 알려진 담당 부재 구분

담당을 아직 정하지 못한 문의는 한 번 더 분류할 수 있게 복구했고, 알고 있는 담당이 꺼졌거나 삭제된 업무는 다른 담당이 대신하지 않도록 유지했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 계약·중립 Registry 수정 | 완료 | 1/1 = 100% |
| 여행 담당 메타데이터 | 완료 | 1/1 = 100% |
| 실제 Registry·Controller 새 종단시험 | 통과 | 5/5 = 100% |
| 관련 전체 회귀 | 통과 | 190/190 = 100% |

## 동작

- `other`·`general`·등록되지 않은 종류는 `RegistryError`입니다. Controller가 재배분을 한 번 시도하고 성공하면 그 담당을 실행하며, 실패하면 기존 `routing_failed`·`escalated` 경로를 사용합니다.
- 알려진 담당 관계는 도메인의 [순수 라우팅 메타데이터](../../../app/domains/travel_ops/components/core_hooks/routing.py)에 있습니다. 구현 import 없이 Core의 `declare_case_types(team_id, case_types)`에 주입합니다. 여행 Team 이름 목록을 코어에 넣지 않았습니다.
- 실제 제공자 0개일 때 알려진 담당이 정확히 하나면 실행 관문이 부재·비활성·적재 실패를 구분합니다. 삭제된 활동 담당에게 속한 업무를 요식 담당으로 재배분하지 않으며 Case·실행 기록·입력을 소비하지 않습니다. 모호하거나 빈 종류는 기존 `RegistryError`입니다.
- 조립 배선은 부모 작업자가 같은 상수와 중립 API로 추가했습니다. 이 보고서의 190건 범위에는 프로젝트 조립 시험 파일은 포함하지 않습니다.

## 검증

[최종 실행 로그](../evidence/2026-10-11_1936_team_plugin_implementation/unknown-route-regression-v3.log): 190/190 통과, 19.24초. Core availability, 실제 로컬 개발 DB의 Registry·Controller 새 종단 5건, 기존 재배분, 도메인 중립성, plugin unavailable 종단시험을 포함합니다. ruff와 변경 공백 검사도 통과했습니다.

새 종단시험은 `other/general × 재배분 성공/실패` 4건과 알려진 활동 담당 삭제 1건입니다. 합성 여행 사용자·문의만 만들며 시험 fixture가 정리합니다. mock 서버 시험은 사용하지 않았습니다. 실서버 확인(서버 응답)은 로컬 개발 DB에 연결한 cs 프로젝트 Controller 내부 경로이며, x600 서버의 cs 프로젝트 API·DB 및 실제 LLM 호출은 확인하지 않았습니다.

첫 회귀의 1/157 실패는 기존 수제 Registry fixture에 새 `require_runnable` API가 없는 문제였습니다. API를 최소 보완했고 최종 회귀는 통과했습니다. 별도 조립 회귀의 1/99 실패는 `technical`을 부재 Team이라고 기대하던 시험의 계약 변경입니다. 미등록 분류이므로 `RegistryError`가 맞으며 부모 작업자가 이 기대를 정정합니다. 이 실패를 제품 실행 성공으로 표시하지 않습니다.

## 변경·복구 근거

- [Registry·계약·시험 해시](../evidence/2026-10-11_1936_team_plugin_implementation/unknown-route-sha256-2134.json)
- [Registry 수정 전 백업](../../../app/core/_backup/2026-10-11_2131_unknown_routing/registry.py)
- [Core 시험 수정 전 백업](../../../tests/unit/core/_backup/2026-10-11_2131_unknown_routing/test_plugin_availability.py)
- [계약 수정 전 백업](../../teams/team-contract/_backup/2026-10-11_2131_unknown_routing/plugin-availability.md)
- [기존 재배분 시험 수정 전 백업](../../../tests/unit/travel/_backup/2026-10-11_2133_registry_gate_fixture/test_routing_reroute.py)

새 메타데이터와 새 Controller 시험 파일은 신규 생성입니다. 커밋·푸시·배포는 하지 않았습니다.
