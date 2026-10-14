# 백그라운드 초기화 장애 격리와 제품 시험 계산 조립

작성: 2026-10-11 22:00 KST. 로컬 구현·로컬 개발 DB 검증입니다. x600 서버의 cs 프로젝트 서버에는 반영하지 않았습니다.

Team 조립 또는 기능 배선이 실패해도 독립 정리·분류 작업을 계속하며, 필수 계산은 우회하지 않도록 보완했습니다. 제품 경로의 시나리오 시험은 필요한 합성 계산 제공자를 앱의 불변 조립 표에 명시했습니다. 전체 제품 시험 3차는 진행 중이므로 전체 완료 근거로 사용하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 회차·종료·주기 회귀 | 통과 | 36/36 = 100% |
| REST·웹 결정 흐름 회귀 | 통과 | 25/25 = 100% |
| 질문 정책 회귀 | 통과 | 4/4 = 100% |
| 공유 여행 API 회귀 | 통과 | 23/23 = 100% |
| MCP 읽기·사진 재독 회귀 | 통과 | 26/26 = 100% |
| 전체 E2E 2차 실행 범위 | 종료 | 650/999 = 65.07% |
| 전체 E2E 3차 | 실행 중 | 분모 999개 |
| 운영 반영 | 미실시 | 0/1 = 0% |

각 집중 시험은 실행 로그의 수이며 전체 기능 완료율이 아닙니다. 전체 2차 결과는 통과 637·실패 12·건너뜀 1·미실행 349개, 1124.09초입니다. 실패 12개 제한 때문에 미실행을 통과로 세지 않았습니다.

## 백그라운드 회차

[실행 가용성 계약](../../teams/team-contract/plugin-availability.md)의 회차 실패 격리를 구현했습니다. 하나의 회차는 성공적으로 조립된 Controller·등록표·계산 표를 종료까지 사용합니다.

- Team 조립 실패는 `composition_fatal`로 기록합니다. Team 의존 작업을 건너뛰고 분류·회원 정리·끝난 여행 정리는 계속합니다. 기능 배선이 성공했다면 재난 점검도 기존 감시 주기 안에서 독립 수행합니다.
- 기능 배선 실패는 `features_fatal`로 따로 기록합니다. 초기화에는 게스트 여행 제외 등 필수 범위 설정도 포함되므로 Team 감시·출발 안내·재난 점검을 실행하지 않습니다. 범위를 모른다고 모든 여행으로 확대하지 않습니다. 범위 연결에 의존하지 않는 독립 정리는 계속합니다.
- 작업별 일반 예외를 격리하고 다음 독립 작업을 진행합니다. 상주 실행의 예외는 회차 실패로 기록하고 다음 회차를 진행합니다. 단발 실행은 실패 종료 코드를 반환합니다. 명시적 종료 신호는 유지합니다.

실패 로그에는 작업 이름·판 번호·예외 종류를 남기며 예외 메시지의 고객 입력·접속 정보는 추가하지 않습니다. 기능 배선 실패의 실제 재현은 수정 전 3개 시험 모두 실패했고, 수정 뒤 해당 4개 조건을 포함한 36개 회귀가 통과했습니다.

근거: [조립 실패 결함 기록](debugs/2026-10-11_2135_worker_composition_stops_independent_jobs.md), [배선 실패 결함 기록](debugs/2026-10-11_2151_worker_feature_wiring_stops_cleanup.md), [최종 36개 실행 로그](../evidence/2026-10-11_1936_team_plugin_implementation/worker-features-regression-v2.log).

## 제품 시험의 계산 제공자

필수 이동 엔진을 끈 상태에서 이전 전역 callback·직선 어림으로 성공하던 시험 전제를 수정했습니다. [공통 시험 도우미](../../../tests/helpers/plugin_bindings.py)는 기존 등록표와 판 번호를 확인한 뒤, 해당 앱의 새 BindingTable에만 합성 제공자를 넣어 게시합니다. 운영 fallback을 복구하지 않습니다.

공유 `api`를 직접 가져오는 파일은 AST로 47개를 확인했습니다. [전체 목록과 범위](../evidence/2026-10-11_1936_team_plugin_implementation/shared-api-explicit-provider-scope.json)를 보존했습니다. 공유 fixture는 CRUD·권한·버전·알림·정책 시나리오를 검증하기 위해 좌표·시각 계약을 검사하는 고정 5분 구간을 사용합니다. 경로 정확도나 실제 요금의 검증 근거가 아닙니다. 실제 그래프·시간표 시험은 고유 엔진 fixture와 실제 탐색을 유지했습니다.

- REST 재개·웹 변경 시험은 답변 반영과 일정 버전 변화, 계산 호출 및 고정 구간의 실제 사용을 검사합니다. 엔진 부재 시험은 제공자를 명시적으로 비우고 503·실패 이유·일정 불변을 확인합니다.
- MCP 이동 판정의 성공 시험은 기존 12분 결과 제공자를 앱의 표에 연결합니다. 전역 clear/register fixture는 제거했습니다. 부재 시험은 503 `team_unavailable`·`engine_unavailable`을 확인하고 추정 결과가 없는지 검사합니다.
- 사진 재독 시험은 전용 앱에 고정 이동 제공자를 넣되 받아쓰기·두 해석·고객 수정·DB 저장 경로는 실제 구현을 유지합니다. 못 찾은 장소의 차단 보존 시험은 현재 원장의 오타 교정 여부와 분리하여 오독 이름만 `unresolved`로 주는 조건을 명시하고 호출도 확인합니다. `bad`·확인 필요·확정 불가 기대값은 유지했습니다.

MCP·사진 집중 검증의 첫 실행은 24개 통과·2개 실패였습니다. 하나는 검사식의 오류 응답 경로를 잘못 적은 것을 정정했고, 다른 하나는 현 원장의 오타 교정으로 시험의 못 찾음 전제가 성립하지 않았습니다. 수정 후 26개 전부 통과했습니다. 첫 실패 로그도 보존합니다.

## 실행 근거와 한계

집중 명령은 `python -m pytest <해당 파일들> -q --tb=short`이며 전체 명령은 `python -m pytest tests/e2e -q --tb=short --maxfail=12 --junitxml=<판별 XML>`입니다. 기존 로그를 덮지 않고 판별 이름으로 저장했습니다.

- [REST·웹 25개](../evidence/2026-10-11_1936_team_plugin_implementation/rest-decision-fixture-regression-v2.log), [질문 정책 4개](../evidence/2026-10-11_1936_team_plugin_implementation/desk-gate-regression.log), [공유 API 23개](../evidence/2026-10-11_1936_team_plugin_implementation/trip-api-explicit-provider.log).
- [MCP·사진 수정 전후 첫 실행](../evidence/2026-10-11_1936_team_plugin_implementation/mcp-intake-explicit-providers.log), [수정 후 26개](../evidence/2026-10-11_1936_team_plugin_implementation/mcp-intake-explicit-providers-v2.log), [소유 코드 9개 lint](../evidence/2026-10-11_1936_team_plugin_implementation/worker-e2e-final-lint.log).
- [전체 2차 원문](../evidence/2026-10-11_1936_team_plugin_implementation/e2e-full-v2.log), [실패 분류·미실행 수](../evidence/2026-10-11_1936_team_plugin_implementation/e2e-full-v2-classification.json), [진행 중인 3차 로그](../evidence/2026-10-11_1936_team_plugin_implementation/e2e-full-v3.log).
- [코드·계약 SHA256 10개](../evidence/2026-10-11_1936_team_plugin_implementation/worker-e2e-final-source-hashes-v2.json). 전체 2차는 후속 fixture 수정 전 소스를 이미 적재했던 프로세스이며 후속 집중 통과 결과와 혼합하지 않습니다.

백업: [초기 조립 실패 수정 전](../../../legacy/team_plugin_worker_audit/2026-10-11_2130/), [기능 배선 실패 수정 전](../../../legacy/team_plugin_worker_audit/2026-10-11_2147/), [REST·결정 흐름](../../../legacy/team_plugin_e2e/2026-10-11_2127/), [질문 정책](../../../legacy/team_plugin_e2e/2026-10-11_2142/), [공유 fixture](../../../legacy/team_plugin_e2e/2026-10-11_2145/), [MCP·사진](../../../legacy/team_plugin_e2e/2026-10-11_2155/). 마지막 백업에는 다른 작업자가 앞서 수정한 상태도 포함하여 보존했습니다.

이 기록의 DB 시험은 로컬 개발 DB와 실제 ASGI/MCP 처리 코드를 사용했습니다. 외부 모델·실제 이동 경로 정확도·x600 서버의 cs 프로젝트 서버 운영 상태는 이 합성 시험으로 확인하지 않았습니다. 커밋·푸시·배포는 하지 않았습니다.
