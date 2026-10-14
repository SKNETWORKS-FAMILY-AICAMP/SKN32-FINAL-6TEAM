# 비활성 팀 실행과 제거 시 조립 실패 경계

## 미해결

비활성 팀을 직접 지정하면 실제 execute가 호출됩니다. 또한 꺼진 구현 패키지를 제거해도 앱이 기동돼야 한다는 사용자 목표와 달리, 조립 코드가 그 구현을 불러옵니다. 제품 코드는 이번 작업에서 수정하지 않았습니다.

## 재현

저장소 루트에서 `PYTHONPATH`를 저장소 루트로 지정한 뒤 아래 파일을 Python으로 실행합니다. DB·네트워크·업무 변경을 사용하지 않습니다.

`python wiki/records/evidence/2026-10-11_1826_team_plugin_review/reproduce_registry.py`

[재현 스크립트](../../evidence/2026-10-11_1826_team_plugin_review/reproduce_registry.py)와 [출력 원문·소스 해시](../../evidence/2026-10-11_1826_team_plugin_review/registry-observations.json).

관측 일치 4/4는 현재 동작 재현입니다. 개선 인수 시험 통과 수치가 아닙니다.

| 확인 | 실제 결과 |
|---|---|
| inactive 자동 resolve | RegistryError |
| inactive get | 객체 반환, active=false |
| inactive LocalTeamExecutor.execute | `inactive_team_was_executed` 반환 |
| 미등록 get | `unknown team: dining` |

## 원인·위치

- `app/core/registry.py:51` get은 active를 검사하지 않습니다. `:73` resolve만 검사합니다.
- `app/core/remote_team/executor.py:23` get 뒤 `:31`에서 그대로 호출합니다.
- `app/application/controller.py:333` 이미 지정된 owner를 get으로 읽습니다.
- `app/composition.py:299` 선언 전체의 구현을 로딩하며, `:485` wire_domain_teams도 팀 내부를 직접 불러옵니다.
- `app/core/project_config.py::_validate_active_team_implementations`에서도 선언 검증 시 활성 팀을 미리 import하므로 조립 로더만 수정해선 선택 팀 실패 격리가 되지 않습니다.
- `components/conversation/case_dispatch.py:87` 담당을 먼저 지정합니다. `app/domains/travel_ops/entry/trip_api.py:1930`에서 RegistryError를 ValueError로 받아 사용자 입력 오류로 바꿉니다.

## 영향·확인 범위

꺼진 팀이 계산·제안을 수행할 수 있고, 그 결과가 일반 적용 경로를 타면 일정 변경까지 진행될 위험이 있습니다. 최소 재현에서는 실행 호출까지 확인했으며 실제 고객 일정 변경은 실행하지 않았습니다. 물리적 패키지 제거 후 전체 앱 기동, 채팅 HTTP 422, reload 실패 시 hook 오염은 코드 추적으로 확인한 경로이며 별도 종단 실행 검증이 남아 있습니다.

자동 선정 실패 시 재배분 시도와 escalated 처리는 별도 경로입니다. 해당 처리가 직접 owner 지정 경로까지 보호한다고 간주하면 안 됩니다.

개선 방향·16개 인수 조건은 [Team 플러그인 수명 관리 계획](../../../teams/team-plugin-lifecycle.md)에 있습니다.
