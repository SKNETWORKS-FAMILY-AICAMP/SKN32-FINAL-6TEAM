# 플러그인·재개 후속 회귀 기록

담당 부재 오류가 빈 계산 결과로 바뀌는 경계를 보완했고, 질문·재개와 묶음 안내 시나리오를 검증했습니다. 이 기록은 로컬 검증이며 운영 배포 완료가 아닙니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 계약·보안·아키텍처 필수 시험 | 통과 | 464/464 = 100% |
| 여행 업무 전체 시나리오 | 통과 | 148/148 = 100% |
| 기존 DoD 자동 관문 | 통과 | 26/26 = 100% |
| 운영 반영 | 미실시 | 0/1 = 0% |

분모는 각 실제 실행 집합입니다. DoD는 기존 v11 자동 관문이며 최신 제품 사양 정본이나 실제 경로 정확도 측정을 대신하지 않습니다. 아래 좁은 회귀는 위 시험 또는 다른 후속 검증과 겹칠 수 있으므로 합산하지 않습니다.

## 오류를 숨기지 않는 경계

A2A 제출·조회가 None을 반환하면 시간 초과와 구분한 계약 오류로 거절합니다. 원격 handle을 확보한 조회 단계의 빈 결과는 유한 예산 안에서 취소도 시도합니다. [A2A 관련 86건](../evidence/2026-10-11_1936_team_plugin_implementation/a2a-empty-response-v2.log)이 통과했습니다. 첫 실행의 잘못된 시험 경로로 발생한 수집 오류 로그도 보존했습니다.

식사 대체 경로·접수 이동·이동 선택 계산의 일반 예외 처리 앞에서 TeamUnavailable을 그대로 전달합니다. 활성 엔진 장애나 조립 누락을 어림 계산 성공으로 숨기지 않습니다. 일반 예외의 기존 정책은 이번 수정에서 넓히지 않았습니다. [관련 62건](../evidence/2026-10-11_1936_team_plugin_implementation/unavailable-propagation-v1.log)에 세 경계 × 세 실패 이유의 신규 9건이 포함됩니다.

## 시나리오의 입력과 실제 이동 정확도를 구분

[CaseEngine](../../../app/domains/travel_ops/scenarios/case_engine.py)의 명시적인 재생용 제공자 주입은 Registry와 조립 revision을 보존합니다. 따라서 시험 제공자를 넣어도 disabled/not_installed Team을 실행 가능하게 만들지 못합니다. [재생 서비스](../../../app/domains/travel_ops/scenarios/replay_services.py)는 시나리오에 기록된 시간·노선을 사용하며 제품 HTTP 조립에는 넣지 않습니다. [단위 시험 4건](../evidence/2026-10-11_1936_team_plugin_implementation/scenario-services-gate-v1.log)으로 복사 독립성·기록 없는 경로 거절·담당 부재 관문을 확인했습니다.

재생은 실제 사고 반영·외부 경로 정확도·실제 탑승 성능의 근거가 아닙니다. 재생의 좌표 근접 기준과 1.2km 정책은 해당 시험 전제이며 웹 대조 표본으로 세지 않습니다. 기존 계획 도구와 Case 경로를 비교하는 fixture는 같은 조립 표를 명시적으로 공유합니다.

전체 시나리오 v2의 남은 1건은 모든 대안이 막혔다는 전제와 달리 확대 탐색으로 추가 카탈로그 후보를 찾아 선택 질문을 만든 상황이었습니다. 원래 일정의 다른 정상 장소는 그대로 두고, 해당 시험에서 추가 후보만 전부 통제로 점검하도록 고쳤습니다. 안내 1개·다음 두 회차 추가 0개·일정 판 불변·업무 상태 검증은 유지했습니다. 제품 계산 코드나 기대값을 바꾸지 않았습니다. 중간에 원래 일정까지 통제하여 실패한 v4도 삭제하지 않았습니다.

[묶음 회귀 v5](../evidence/2026-10-11_1936_team_plugin_implementation/watch-batch-notice-regression-v5.log)는 9/9, 20.89초입니다. [전체 시나리오 v3](../evidence/2026-10-11_1936_team_plugin_implementation/scenario-full-v3.log)는 148/148, 134.01초이며 [JUnit](../evidence/2026-10-11_1936_team_plugin_implementation/scenario-full-v3.xml)을 보존했습니다.

## 필수 관문과 산출물 확인

시험과 AST 구조 검사에서 _backup/legacy 보관본을 현재 제품 코드로 수집하지 않도록 범위를 맞췄습니다. 현재 제품 규칙을 완화하지 않고 보관본의 이전 구현만 검사에서 제외합니다. [필수 관문 v5](../evidence/2026-10-11_1936_team_plugin_implementation/required-gates-v5.log)는 464/464, 38.38초입니다. 기존 이동 judgment_log의 문서 문자열에서 invalid escape sequence 경고 6건이 있었으며 통과와 구분합니다. [DoD v3](../evidence/2026-10-11_1936_team_plugin_implementation/dod-gate-v3.log)는 전체 26/26, MVP 부분 18/18입니다.

[흐름 그림](assets/2026-10-11_team_plugin/plugin-flow.html)의 HTML·SVG XML·접근 가능한 제목·로컬 링크 두 개를 [정적 검사](../evidence/2026-10-11_1936_team_plugin_implementation/artifact-check-v1.json)했습니다. 화면 렌더링을 직접 확인한 결과로 표현하지 않습니다. 현재 계약 문서 네 개의 [로컬 링크 48개](../evidence/2026-10-11_1936_team_plugin_implementation/wiki-link-check-v1.json)도 확인했습니다.

## 보존과 확인 범위

[후속 수정 소스 13개 SHA256](../evidence/2026-10-11_1936_team_plugin_implementation/parent-followup-source-sha256-v2.json)과 [최종 인수 매핑](../evidence/2026-10-11_1936_team_plugin_implementation/acceptance-mapping-v2.json)을 보존합니다. 최종 매핑의 24개 조건에 직접 연결된 65개 시험을 다시 실행해 65/65, 14.42초를 확인했습니다. 기존 178개 묶음을 최종 판 실행 수로 재사용하지 않습니다. 최종 65건에는 MCP DeprecationWarning 1건이 있었으며 통과와 구분합니다.

원본은 [A2A 패치 전](../../../legacy/team_plugin_lifecycle/2026-10-11_215942_a2a_empty_response/), [예외 전달 패치 전](../../../legacy/team_plugin_lifecycle/2026-10-11_221151_unavailable_propagation/), [재생 주입 전](../../../legacy/team_plugin_lifecycle/2026-10-11_215708_scenario_services/), [파생 fixture 수정 전](../../../legacy/team_plugin_lifecycle/2026-10-11_220958_derived_scenario_bindings/), [안내 시험 수정 전](../../../legacy/team_plugin_lifecycle/2026-10-11_221732_watch_batch_diagnostic/), [구조 검사 수정 전](../../../legacy/team_plugin_lifecycle/2026-10-11_215338_architecture_archive_scope/)에 보존했습니다.

mock 서버 시험(화면 반응): 이번 기록 범위에서는 시행하지 않았습니다.

실서버 확인(서버 응답): 로컬 개발 DB의 합성 여행·Controller 시나리오와 FastAPI 처리기를 검증했습니다. 운영 중 cs 프로젝트 서버의 새 코드 요청이나 새 코드 기동을 확인한 것은 아닙니다. 운영 DB 구조의 읽기 전용 대조·운영 기준 후보·전체 E2E·최종 Sonnet 감사는 별도 기록으로 구분합니다. 커밋·푸시·배포·재기동은 하지 않았습니다.
