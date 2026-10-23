# 백그라운드 상태 보존과 E2E 앱 조립 전수 점검

작성: 2026-10-11 22:42 KST. 로컬 구현·검증 기록입니다. 전체 E2E 4차는 이 문서 작성 시 진행 중입니다.

반복 초기화가 준비된 해석 상태를 지우는 문제를 해결했고, 독립 앱의 필수 이동 계산을 명시했습니다. 변경 채팅 시험은 담당 Team의 실제 변경·중복 방지·질문·답변 재개까지 확인하도록 보강했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 백그라운드 상태·회차·종료·주기 | 통과 | 38/38 = 100% |
| E2E 앱 생성 전수 점검 | 완료 | 28/28 = 100% |
| 계획·접수·복구·SSE 집중 시험 | 통과 | 86/86 = 100% |
| 변경 채팅·대기·재개 | 통과 | 1/1 = 100% |
| 격리 DB의 Dining 원장 시험 | 통과 | 5/5 = 100% |
| 전체 E2E 3차 실행 범위 | 종료 | 733/999 = 73.37% |
| 전체 E2E 4차 | 실행 중 | 수집 999개 |
| 운영 반영 | 미실시 | 0/1 = 0% |

각 행의 분모는 해당 실행 또는 감사 범위입니다. 집중 시험과 전체 시험의 같은 항목을 합산하지 않습니다.

## 상태 보존

[별도 결함 기록](debugs/2026-10-11_2242_worker_feature_reregistration_loses_pointer_state.md)에 실제 클래스 재현·원인·성공 한 번만 등록하는 수정·회귀 38개를 기록했습니다. API 앱 생성과 Team 후보 조립의 계산 표 고정은 유지합니다.

## 앱 생성 28곳

[AST 목록과 수동 분류](../evidence/2026-10-11_1936_team_plugin_implementation/e2e-app-construction-reviewed-v2.json)는 `tests/e2e/test_*.py`의 `create_app` 28곳과 `TestClient` 54곳을 포함합니다. 백업 폴더는 제외합니다. 기존 앱을 다시 감싼 클라이언트는 새 조립으로 세지 않습니다. 별도의 운영 앱·첫 화면 앱은 여행 계산 경로가 아닙니다.

[공유 API를 직접 가져오는 파일 47개](../evidence/2026-10-11_1936_team_plugin_implementation/shared-api-explicit-provider-scope.json)는 CRUD·권한·버전·멱등 시나리오용 합성 이동 제공자를 사용합니다. 독립 앱은 목적에 따라 명시 합성 계산, 명시 엔진 부재, 실제 로컬 그래프, 인증·조회·운영 전용으로 분류했습니다. 실제 이동 엔진을 켜는 `test_mobility_engine_flow`는 대체하지 않았습니다. 엔진 부재를 검사하는 MCP·SSE 시험의 503과 일정 불변 기대도 유지했습니다.

계획 생성 fixture에는 기존 `MOVE_BUFFER_MIN`을 지키는 합성 도착 계산을 넣었습니다. 기존 출발 시각 기대값을 낮추지 않았습니다. 읽기·확정 앱 두 종류를 각각 확인했고, 원문 줄 읽기만 확인하는 독립 앱 둘은 등록 성공의 근거로 세지 않습니다. 검토 화면 시험의 명시 review 대역도 실제 경로 정확도 근거가 아닙니다.

## 변경 채팅

기존 시험은 합성 여행의 9월 일정에 1월 1일 신고를 보냈고, Team은 `itinerary_not_today`로 차단했습니다. [응답·Case 상태·이벤트 재현](../evidence/2026-10-11_1936_team_plugin_implementation/web-chat-response-and-state-v2.json)에 분류·`dining.check_open` 라우팅·`report_delay`·분 수 30·차단 사유를 보존했습니다. 운영 코드 결함으로 단정하지 않고 시험 날짜를 바로잡았습니다.

새 시험의 원래 식당은 계획 시간에는 열려 있고, 30분 늦으면 14:10 휴식 시간 전 주문 여유가 부족합니다. Controller가 Dining Team에 전달한 `request.action`과 `minutes=30`, 실제 새 식당 변경, 고객 답의 원 식당·새 식당·13:30 도착·14:10 근거를 검사합니다. 같은 요청을 다시 보내도 일정 판은 최초 등록+변경의 2개로 유지됩니다.

분 수가 없는 신고는 `waiting_input`에서 질문하며, `30분이요`라는 추가 답이 같은 Case에 저장되어 재개됩니다. 새 식당은 그 지연에도 가능하므로 추가 변경 없이 완료하는 것까지 확인합니다. [최종 집중 실행](../evidence/2026-10-11_1936_team_plugin_implementation/web-chat-team-resume-v7.log) 1/1 통과입니다. 앞서 전체 웹 파일은 37개 통과·이 항목 1개 실패였으며, 전체 4차가 최종 판 전체를 재검증합니다.

`report` 필수 응답 여부는 `frontend/apps/web/src/lib/live/gateway.ts`, `features/trip/trip-chat.tsx`, `wiki/external/rest-endpoints.md`, `case_dispatch.response`와 기존 시험을 대조했습니다. UI는 `answer`·`status`·`outcome`·대기 스키마를 읽고, Team 업무의 기본 응답은 `report`를 요구하지 않습니다. 품절 업무의 기존 전용 `report`는 유지합니다. 일반 변경의 옛 추출기 필드 대신 실제 Team에 전달된 요청을 검사하며, 고객 답과 DB에 저장된 답이 같은지 확인합니다.

## Dining 원장과 검증 한계

로컬 개발 DB에는 실제 식당이 있어 원장 시험 5개가 의도적으로 건너뜁니다. 기존 로컬·운영 데이터를 바꾸지 않고, 이미 마련된 별도 합성 DB의 빈 원장에서 [5/5 통과](../evidence/2026-10-11_1936_team_plugin_implementation/dining-ledger-isolated-db.log)를 확인했습니다. Mobility만 명시 합성 계산 표를 쓰며, Dining 원장 선택·영업 판정·등록 연결·닫힌 식당 차단은 실제 구현과 기존 기대값을 유지합니다. 이 결과는 실제 식당·외부 API 정확도 측정이 아닙니다.

mock 서버 시험: 해당 없음(화면 반응을 검증하지 않았습니다).

실서버 확인(서버 응답): 로컬 개발 서버의 실제 ASGI·PostgreSQL 제품 경로를 검증했습니다. x600 서버의 cs 프로젝트 서버 반영·외부 지도·실제 모델 측정은 하지 않았습니다.

## 전체 실행 기록

전체 3차는 999개 수집, 715 통과·12 실패·6 건너뜀·266 미실행입니다. 실행 733개를 통과 733개로 표시하지 않습니다. [실패·건너뜀 목록](../evidence/2026-10-11_1936_team_plugin_implementation/e2e-full-v3-classification.json)을 보존했습니다. 실패는 독립 planner 7개·확정 앱 5개의 계산 제공자 누락입니다. 보완 후 [관련 86개](../evidence/2026-10-11_1936_team_plugin_implementation/planner-intake-explicit-providers-v2.log)가 통과했습니다.

건너뜀 6개는 실제 대피 자료가 있어 빈 자료 경로를 못 보는 1개와 실제 원장 때문에 CI 분기가 실행되지 않는 5개입니다. Dining 5개는 격리 DB 결과로 따로 확인했습니다. 3차 적재 이후 파일 수정이 있어 최종 소스 전체 검증으로 부르지 않습니다.

전체 4차는 `python -m pytest tests/e2e -vv --tb=short --maxfail=0 --junitxml=.../e2e-full-v4.xml`로 시작했습니다. [진행 로그](../evidence/2026-10-11_1936_team_plugin_implementation/e2e-full-v4.log)에 파일·시험별 결과를 남기고, [시작 소스 404파일 해시](../evidence/2026-10-11_1936_team_plugin_implementation/e2e-full-v4-source-start.json)를 보존합니다. 완료 결과는 후속 기록으로 추가합니다.

백업: [22:23 수정 전](../../../legacy/team_plugin_e2e/2026-10-11_2223/), [22:35 채팅·원장 수정 전](../../../legacy/team_plugin_e2e/2026-10-11_2235/). 기존 기록은 덮지 않았습니다. 커밋·푸시·배포는 하지 않았습니다.
