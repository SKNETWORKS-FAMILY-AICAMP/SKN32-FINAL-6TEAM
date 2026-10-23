# 기능 초기화 실패로 독립 정리까지 멈추는 경로

## 해결됨 (2026-10-11)

기능 초기화 실패를 Team 조립 실패와 구분해 기록하고, 독립 정리를 계속 수행하도록 수정했습니다. 감시 대상 범위가 확보되지 않은 상태에서 전체 여행으로 감시를 넓히지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 수정 전 재현 | 실패 확인 | 3/3 = 100% |
| 추가 실패 격리 시나리오 | 통과 | 4/4 = 100% |
| 관련 단위·DB 주기 회귀 | 통과 | 36/36 = 100% |

재현 3건은 기대 동작을 만족하지 못한 시험 수입니다. 최종 4건에는 재현한 3건과 재난 점검 단독 실행 시나리오가 들어가며, 모두 최종 36항목에 포함됩니다. 별도 43항목으로 합산하지 않습니다.

## 원인과 수정

[작업자 코드](../../../../scripts/run_sweepers.py)에서 `wire_optional_features()` 예외가 `_CompositionFailed` 보호 밖으로 빠졌습니다. 정상 Team 조립 뒤 기능 연결이 실패한 경우, Team 조립·기능 연결이 모두 실패한 경우, 독립 정리만 요청한 경우 모두 정리 작업에 도달하지 못했습니다. [수정 전 원문](../../evidence/2026-10-11_1936_team_plugin_implementation/worker-features-before.log)에 세 실패를 보존했습니다.

기능 초기화는 게스트 여행 제외 같은 필수 감시 범위와 선택 문구·화면 기능을 함께 연결합니다. 어느 연결이 누락됐는지 확정할 수 없으므로 기능 초기화 실패에는 별도 `features.fatal=1`을 남기고 Team 작업·안내·재난 점검을 실행하지 않습니다. 분류와 독립 회원·여행 정리는 계속합니다. Team 조립만 실패하고 기능 연결이 성공하면 재난 점검은 기존 주기 안에서 수행합니다.

[계약](../../../teams/team-contract/plugin-availability.md)을 먼저 보완하고 `_FeaturesFailed`와 `_wire_features`를 추가했습니다. 두 초기화가 함께 실패하면 `composition`·`features`를 각각 기록하며, 고객 내용이 섞일 수 있는 예외 메시지는 새 로그에 싣지 않습니다. [변경 직전 보존본](../../../../legacy/team_plugin_worker_audit/2026-10-11_2147/)은 상대 경로를 유지합니다.

## 검증

```powershell
python -m pytest tests/unit/travel/test_plugin_worker_availability.py tests/unit/core/test_run_sweepers_signals_errors.py tests/integration/test_watch_cadence.py -q
python -m ruff check scripts/run_sweepers.py tests/unit/travel/test_plugin_worker_availability.py tests/helpers/plugin_bindings.py tests/e2e/test_trip_api.py tests/e2e/test_desk_gate.py tests/e2e/test_case_version_rest.py tests/e2e/test_decision_unit_web.py
```

[최종 회귀 로그](../../evidence/2026-10-11_1936_team_plugin_implementation/worker-features-regression-v2.log) 36/36 통과, [정적 검사](../../evidence/2026-10-11_1936_team_plugin_implementation/worker-features-e2e-lint.log) 7파일 통과입니다. 시험은 안전하지 않은 범위 의존 함수가 호출되면 즉시 실패하게 하고, 독립 작업 호출 수와 기능·조립 실패의 별도 집계를 확인합니다.

실서버 확인(서버 응답): 로컬 개발 서버의 앱 코드·PostgreSQL 주기 시험을 실행했습니다. 운영 중인 cs 프로젝트 서버 배포 확인은 하지 않았습니다. mock 서버 화면 시험은 해당 없습니다. 실제 선택 기능을 하나씩 독립 적재하는 조립기 개편은 이번 수정에 포함하지 않았으며, 보수적인 미실행 사유를 명시하는 범위입니다.
