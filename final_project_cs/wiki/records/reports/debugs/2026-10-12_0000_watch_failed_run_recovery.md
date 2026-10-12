# 감시 업무의 실패 실행 복구 검증

감시 업무가 실행 중 필요한 담당 기능의 비활성화로 멈춘 뒤, 기능을 다시 연결해도 영구히 대기하던 결함을 재현하고 고쳤습니다. 새 업무를 만들지 않고 기존 업무를 이어서 처리합니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 실제 Controller·DB 재현 | 결함 확인 | 1/1 = 100% |
| 신규·기존 worker 회귀 | 통과 | 43/43 = 100% |
| 기존 실패·묶음 호환 회귀 | 통과 | 26/26 = 100% |
| 재시도 예산 0 경계 재검증 | 통과 | 4/4 = 100% |
| 최소 후보 구성 호환 재검증 | 통과 | 4/4 = 100% |

43건과 26건은 서로 다른 시험 ID의 합계 69건입니다. 뒤의 4건 실행 두 번은 신규 DB 시험의 반복 검증이며 고유 시험 수에 더하지 않습니다. 모두 로컬 시험 결과입니다. x600 서버의 cs 프로젝트 서버에 반영하거나 외부 서비스에 실제 메시지를 보내지는 않았습니다.

## 재현한 원인과 수정 범위

[실패 재현 로그](../../evidence/2026-10-11_1936_team_plugin_implementation/watch-plugin-recovery-before-v4.log)는 실제 Controller가 교차 Team 계산의 비활성을 만나 실행 기록을 failed로 닫고 Case는 running으로 보존한 뒤, 의존 기능 복구 후에도 감시가 기존 사건이라고만 판단하여 실행하지 않는 것을 보여 줍니다. 이전 before~before-v3 로그는 시험 준비 오류로, 이 결함의 재현 근거로 사용하지 않습니다.

[감시 구현](../../../../app/domains/travel_ops/components/watch/trip_watch_cases.py)은 감시가 만든 동일 사건에 한하여 Case가 running이고 활성 실행이 없고 최신 실행이 failed인 경우 같은 Case를 Controller.run_case로 다시 보냅니다. agent_runs에 typed 실패 원인 열이 없으므로 이를 TeamUnavailable만의 복구라고 부르지 않습니다. 신규 생명주기 이벤트·DB 스키마·계산 fallback을 추가하지 않았습니다.

담당 Team 또는 capability의 비활성은 사전 관문에서 막아 새 실행 기록을 만들지 않습니다. 실행 중에야 드러나는 동적 교차 Team 의존성은 그 계산 관문에서 막히므로 비활성이 지속되면 같은 Case에 failed 실행이 추가될 수 있습니다. 이 한계는 기존 Controller 실행 계약과 같습니다. 복구가 기존 사건의 retry_max·cooldown에 묶이지 않는 것을 retry_max=0, cooldown=3600초로 검증했습니다.

입력 대기·종결·에스컬레이션, 활성 실행이 있는 업무, 실행 이력 없는 running, 최신 실행이 성공인 업무에는 이 복구를 적용하지 않습니다. Controller 시간 초과는 escalated로 끝나 새 running 복구에 들어가지 않습니다. 실행 시작 경합에서 ActiveRunError가 나도 먼저 실행 중인 Case를 일반 실패로 닫지 않습니다. 묶음 사건은 한 회차에 한 번만 실행합니다.

시간 초과 경계 시험에서 기존 guardrail.observed가 숫자일 때 리스트로 가정하여 TypeError를 내던 기존 결함도 확인했습니다([발견 로그](../../evidence/2026-10-11_1936_team_plugin_implementation/watch-plugin-recovery-after-v3.log)). 리스트와 스칼라를 함께 읽도록 최소 보완했고 닫힌 업무의 기존 cooldown·retry_max 정책은 유지합니다.

## 실행 근거

- [신규 DB 시험 4건](../../../../tests/e2e/test_watch_plugin_recovery.py): 실제 ASGI 등록, Controller, Registry, 고정 BindingTable, SQL 실행 이력을 사용합니다. Team 계산 제공자는 명시적인 합성 시험용입니다. 모델·외부 지도 API·실제 이동 정확도 검증을 대신하지 않습니다.
- [동시 실행 시작 단위 시험 1건](../../../../tests/unit/travel/test_watch_recovery_race.py): ActiveRunError 후 기존 실행을 닫지 않는지 검사합니다.
- [43/43 로그](../../evidence/2026-10-11_1936_team_plugin_implementation/watch-plugin-recovery-after-v4.log): 신규 5건과 기존 worker 38건, 69.15초.
- [26/26 호환 로그](../../evidence/2026-10-11_1936_team_plugin_implementation/watch-recovery-compatibility.log): 기존 watch 실패 17건과 묶음 9건, 228.30초.
- [예산 0 재검증 4/4](../../evidence/2026-10-11_1936_team_plugin_implementation/watch-plugin-recovery-zero-budget.log): 122.16초.
- [최소 후보 호환 4/4](../../evidence/2026-10-11_1936_team_plugin_implementation/watch-plugin-recovery-candidate-compatible.log): 35.51초. 제외된 예보 기능을 시험에서 명시적으로 끄는 monkeypatch에 raising=False를 붙인 최종 시험판입니다. 예보 기능 자체를 검증하는 시험이 아닙니다.

실패 중 두 건의 action_requests를 0건으로 기대한 초기 시험은 잘못된 가정이었습니다. 실제 DB 관찰 결과는 Case 생성 멱등 장부인 case.create뿐이었습니다([관찰값](../../evidence/2026-10-11_1936_team_plugin_implementation/watch-action-scope.json)). 최종 시험은 최초 Case 수만큼의 case.create만 허용하고 재실행 후 추가 Case 생성·일정 변경 action·trip.notice 증가가 없는지 검사합니다. 일정 버전도 1로 유지되는지 확인합니다.

신규 DB 시험은 기존 개발 데이터와 분리한 합성 DB에서 실행했습니다. 최소 후보에 없는 예보 스키마를 추가하지 않고 예보 호출만 명시 제외했습니다. 기존 26건은 고유 tenant로 격리된 로컬 개발 DB 시험이며 다른 tenant 정리를 수행하지 않습니다. Ruff는 제품·신규 시험 세 파일 모두 통과했습니다.

## 정본·백업·소스 고정

[가용성 계약](../../../teams/team-contract/plugin-availability.md)의 ‘감시 업무의 실행 중단 복구’에 위 경계와 동적 의존성 한계를 기록했습니다. 부모 담당의 main wiki와 web-access 문서는 여기서 수정하지 않았습니다.

[백업](../../../../legacy/team_plugin_watch_recovery/)에 각 변경 직전 원본을 상대 경로로 보관했습니다. 마지막 시험 호환 한 줄의 직전 원본은 [2026-10-11_235732](../../../../legacy/team_plugin_watch_recovery/2026-10-11_235732/)에 있습니다.

[최종 관련 파일 해시](../../evidence/2026-10-11_1936_team_plugin_implementation/watch-recovery-stable-2026-10-11_235939-hashes.json)를 남겼습니다. 앞서 43건이 통과한 이후 제품 두 파일과 신규 경합 시험은 변경하지 않았으며 신규 DB 시험의 raising=False 한 줄만 바뀌었습니다. 공유 계약은 부모의 동시 작업 대상이므로 이 해시를 전체 저장소 동결로 해석하지 않습니다.

전체 E2E 4차 1000 passed·6 skipped·0 failed·0 unexecuted는 이 watch 보완 이전의 별도 실행입니다. 전체 실행 중 부모 소스 4파일 변경 제한과 별도 skip 6건 검증은 [전체 실행 보고](../2026-10-11_2318_worker_e2e_full_v4.md)에 보존했습니다. 이번 69건을 전체 E2E 최종 소스 전량 재검증으로 일반화하지 않습니다.
