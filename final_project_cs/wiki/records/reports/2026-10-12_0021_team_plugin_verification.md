# Team 플러그인·대화 재개 구현과 운영 후보 검증

담당 팀을 우회하던 업무 실행, 답변 대기·재개, 중단 후 재시도와 동시 요청 경합을 보완했습니다. 기존 운영 이미지를 기준으로 분리한 최종 후보는 격리 Linux·합성 PostgreSQL 시험 388개를 모두 통과했습니다. 운영 중인 cs 프로젝트 서버에는 아직 적용하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 최종 운영 후보 회귀 | 통과 | 388/388 = 100% |
| 최종 코드 계약·보안·구조 관문 | 통과 | 464/464 = 100% |
| 요청한 두 모델의 실제 CLI 검토 | 수행 | 2/2 = 100% |
| 운영 반영 | 미실시 | 0/1 = 0% |

388은 고정된 최소 후보의 실제 pytest 실행 집합, 464는 현재 작업 코드의 계약·보안·아키텍처 실행 집합입니다. 두 모델은 Claude Opus 5.5와 Claude Sonnet 5.5입니다. 서로 겹치는 시험과 반복 실행은 합산하지 않습니다. 시험 통과를 제품 전체 무결함이나 이동 데이터 정확도 판정으로 바꾸지 않습니다.

## 서비스에서 달라지는 동작

- 변경 업무는 Controller가 등록된 Team의 실행 함수를 호출하고, Team의 제안을 공통 적용기가 한 번 반영합니다. 담당 팀이 꺼졌거나 설치되지 않으면 그 업무와 필수 계산을 거절합니다. 저장된 계획서 조회 같은 독립 기능은 유지합니다.
- 정보가 부족하면 업무를 완료하지 않고 답변 대기로 보존합니다. 「30분이요」 같은 추가 답변은 같은 업무에 전달됩니다. 관계없는 새 문의는 이전 질문의 답변으로 소비하지 않습니다.
- 담당 부재 후 같은 초기 요청은 저장된 계획으로 재시도합니다. 동시에 같은 요청이 들어와도 업무 생성·일정 적용·알림은 하나입니다. 다른 요청이 먼저 실행하거나 완료하면 승자의 상태를 보존하고 충돌을 반환합니다.
- 요청·SSE 응답·백그라운드 한 회차는 같은 조립 판을 사용합니다. 감시 업무도 중단된 기존 업무를 복구하며 독립 작업은 계속합니다.

현재 사양은 [Team 수명주기](../../teams/team-plugin-lifecycle.md), [가용성 계약](../../teams/team-contract/plugin-availability.md), [메시지 API 계약](../../external/rest-endpoints/web-access.md)이 정본입니다. [흐름 그림](assets/2026-10-11_team_plugin/plugin-flow.html)은 시작·판단·처리·대기·실패·종료를 구분합니다.

## 실제 코드 경로

브라우저 요청을 받는 [trip_api](../../../app/domains/travel_ops/entry/trip_api.py)의 `web_message`와 에이전트 메시지 입구는 [trip_messages](../../../app/domains/travel_ops/components/conversation/trip_messages.py)의 `handle_trip_message`를 함께 사용합니다. 업무 해석 뒤 [case_dispatch](../../../app/domains/travel_ops/components/conversation/case_dispatch.py)의 `execute`가 담당·기능을 확인하고 [Controller](../../../app/application/controller.py)의 `run_case`로 전달합니다. 로컬 실행기는 등록된 `Team.execute`를 호출합니다. 재개는 같은 Controller에 답변 본문·업무 ID·요청 ID·토큰·Case 버전을 전달합니다.

사실·서비스 안내의 읽기 응답을 모두 Team 업무로 바꾸지는 않습니다. 계산 제공자를 재사용하는 경로도 소유 팀과 필수 여부를 같은 계산 표에서 확인합니다. 담당·기능과 입구가 명시적으로 준비 검사한 조건은 입력 소비 전에 거절합니다. 실행 도중 알게 된 교차 Team 의존성 실패는 이미 접수한 입력·실패 실행을 보존하며, 같은 요청으로 복구합니다. 모든 의존성이 사전에 알려진다고 주장하지 않습니다.

## 실패 재현과 독립 검토

[실제 Opus 5.5 후보 감사](2026-10-11_2313_plugin_v5_opus_readonly_audit.md)는 후보 v5 변경 diff의 정적 검토입니다. 보고된 7개 지적을 바로 실행 증명으로 취급하지 않고, 대기 분리·명시/자동 만료·담당 부재 격리·감시 복구·RESUMING 중단·초기 재시도·복원 호출의 개별 실행으로 확인하고 보완했습니다.

동시 초기 생성과 메시지 원문 구분도 추가 검증했습니다. Sonnet 후속 검토가 지적한 활성 실행 시작 경합과 최신 running/resolved 상태의 재배정 경합은 각각 실제 실패를 재현한 뒤 좁게 수정했습니다. [초기 재시도·동시 요청 보고서](2026-10-12_0010_initial_message_retry_and_concurrency.md)에 수정 전·후 로그와 판별 범위를 보존합니다.

마지막 실제 Sonnet 검토는 [모델 메타데이터](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-routing-closure-2026-10-12_0016-model-metadata.json)에서 `claude-sonnet-5-5`, `is_error=false`, CLI 종료 0을 확인했습니다. 한정한 최종 관문을 읽고 [단위 시험 31/31](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-routing-closure-2026-10-12_0016-test-output.json)을 직접 실행했으며 추가 지적은 없었습니다. 모델이 운영 HTTP를 직접 시험했다거나 전체 저장소를 마지막에 다시 감사했다는 뜻은 아닙니다.

## 최종 검증과 이전 기록 구분

| 실행 | 실제 결과 | 근거 |
|---|---|---|
| 최종 후보 v9 Linux·DB | 388 통과·실패 0·건너뜀 0, 39.56초 | [전체 실행 로그](../evidence/2026-10-11_1936_team_plugin_implementation/candidate-v9-isolated-linux-db-full-v1.log) |
| 현재 코드 필수 관문 7차 | 464 통과, 45.47초 | [로그](../evidence/2026-10-11_1936_team_plugin_implementation/required-gates-v7.log), [JUnit](../evidence/2026-10-11_1936_team_plugin_implementation/required-gates-v7.xml) |
| 대기·새 문의·기존 재개 | 16 통과, 70.52초 | [범위별 보고서](2026-10-12_0004_conversation_isolation_regression.md) |
| 마지막 초기·배정 경합 | 38 통과, 20.63초 | [실행 로그](../evidence/2026-10-11_1936_team_plugin_implementation/initial-routing-race-after-v1.log) |
| 감시 복구·기존 호환 | 고유 69 통과, 예산 0 및 최소 구성 각 4개 재검증 | [감시 보고서](debugs/2026-10-12_0000_watch_failed_run_recovery.md) |

최종 후보는 업무 대기·자동/명시 답변·초기 동시 접수·RESUMING 커밋 직후 중단·감시 복구·동적 의존성 재시도·기존 접수 복원 성공과 보호 조건을 함께 실행했습니다. 운영 DB·운영 환경 값·운영 볼륨은 연결하지 않았습니다. 임시 합성 DB와 명시적 시험 계산 제공자를 사용합니다. 관련 시험 집합을 더해 고유 전체 수로 부르지 않습니다.

필수 관문의 기존 invalid escape 경고 6건과 최종 Linux 실행의 Starlette/AnyIO DeprecationWarning 1건은 통과와 구분합니다. 새로운 런타임 결함으로 확인된 것은 아니며 이번 수정에 섞어 해당 이동·라이브러리 코드를 변경하지 않았습니다.

이전 후보 v7은 무관 기능의 부분 이식 누락으로 355 통과·24 실패·3 건너뜀이었습니다. [실패 로그](../evidence/2026-10-11_1936_team_plugin_implementation/candidate-v7-isolated-linux-db-full-v1.log)를 보존했고 후보를 새로 만들어 보완했습니다. v8은 384개 통과였으며 마지막 경합 보완 4개를 더한 v9 388개와 별도 판입니다.

[이전 전체 E2E](2026-10-11_2318_worker_e2e_full_v4.md)의 1,000 통과·6 건너뜀은 실행 중 소스 4개가 변한 별도 결과입니다. 6개를 다른 자료 환경에서 따로 확인했더라도 같은 고정판 전체 1,006개 통과로 표현하지 않습니다. 이번 최종 388개가 기존 전체 E2E 전량이라는 뜻도 아닙니다.

## 운영 후보와 남은 운영 절차

[최종 후보 v9](../../../legacy/deployment_candidates/2026-10-12_001736_plugin_v9/)는 실제 운영 소스 기준선에서 필요한 런타임 파일 51개만 선택 이식했습니다. SQL 85개와 requirements는 기준선과 같습니다. 다른 작업자의 새 기능과 DB 변경을 통째로 포함하지 않았습니다. 새 내부 import·호출의 정적 대조는 [AST 근거](../evidence/2026-10-11_1936_team_plugin_implementation/candidate-v9-ast-closure-v1.json)에 있습니다.

운영 API·worker의 이미지 ID는 [00:18 읽기 전용 재확인](../evidence/2026-10-11_1936_team_plugin_implementation/deployed-baseline-image-recheck-before-v9-build.json)에서 기준선과 2/2 동일했습니다. 운영용 새 이미지 제작·내부 검증과 교체·되돌림 절차는 [별도 준비 보고서](2026-10-12_0023_plugin_v9_linux_release_preparation.md)에 기록합니다. 첫 제작의 외부 metadata 조회 실패는 보존했고, 검증한 로컬 기준 태그를 사용한 두 번째 제작은 성공했습니다. 새 이미지의 소스 51/51·패키지 8/8·시작 설정 5/5 일치를 확인했습니다. 비루트·읽기 전용·네트워크 차단 프로세스의 최초 토큰 계산 3개가 성공했고 계측한 연결 시도는 0회였습니다. 빌드 metadata 통신 횟수는 계측하지 않았습니다. [이미지 내부 검증](../evidence/2026-10-11_1936_team_plugin_implementation/candidate-v9-isolated-image-verification-v1.json).

운영 교체 절차도 읽기 전용으로 검증했습니다. 첫 비교에서 발견한 API 시작 명령 차이는 이미지 기본 명령 상속을 반영하지 않은 비교 문제였고, 실제 유효 명령은 일치했습니다. 환경 차이는 이미지 태그 선택 키 하나였습니다. 디스크 설정으로 바로 재생성하지 않고 기존 실행 환경을 메모리에서 보존하는 표준입력 override를 사용합니다. [최종 절차 전제](../evidence/2026-10-11_1936_team_plugin_implementation/deployed-preserving-stdin-release-preconditions-v5.json)는 기존 환경값 144/144와 두 프로세스의 명령·마운트·네트워크·재시작 등 구성을 보존하며, 새 캐시 변수 하나만 추가함을 확인합니다. [YAML 값 대조](../evidence/2026-10-11_1936_team_plugin_implementation/candidate-v9-yaml-preservation-and-intended-additions.json)는 기존 값 474/474 보존과 의도한 추가를 확인했습니다. 비밀값을 출력하거나 디스크에 저장하지 않았습니다. 첫 비교 기록은 삭제하지 않고 정정 근거와 함께 보존했습니다.

운영 이미지 교체·API/worker 재기동·운영 데이터 쓰기·커밋·푸시는 실행하지 않았습니다. 기존 ‘배포 승인을 추정하지 않는다’는 지시에 따라 실제 운영 적용 승인을 확인합니다. 제안 범위는 API·worker 이미지 교체·재기동과 읽기 전용 기동·구성·회차 확인입니다. 현재 인증은 운영 tenant에 고정되고 알림은 고객별 스위치가 꺼지면 운영자 발행기로 넘어갑니다. 합성 사용자의 연락처를 비워도 외부 발송 차단을 보장하지 못하므로 운영 HTTP 쓰기·합성 데이터 생성·정리는 이 승인 범위에 포함하지 않습니다. 운영 반영 전에는 기존 cs 프로젝트 서버가 이번 코드로 동작한다고 말하지 않습니다.

## 문서와 백업

[운영 절차 정정 전 백업](../../_backup/2026-10-12_003432_plugin_release_preconditions/), [최종 문서 갱신 전 백업](../../_backup/2026-10-12_002749_plugin_final_summary/), [현재 계약 개정 전 백업](../../_backup/2026-10-12_001815_plugin_final_evidence/), [대화 수정 전 소스](../../../legacy/team_plugin_lifecycle/2026-10-11_2325_conversation_isolation/), [초기 생성 전 소스](../../../legacy/team_plugin_lifecycle/2026-10-11_2351_initial_create_once/), [배정 경합 전 소스](../../../legacy/team_plugin_lifecycle/2026-10-12_0013_routing_race/), [감시 원본](../../../legacy/team_plugin_watch_recovery/)을 보존합니다. 최초 초기 retry 계약 문단 직전의 정확한 별도 사본을 만들지 못한 사실은 초기 재시도 보고서에 그대로 기록했습니다. 이전 단계 백업을 정확한 직전 사본이라고 소급하지 않습니다.

mock 서버 시험(화면 반응): 최종 코드의 브라우저 화면 시험은 하지 않았습니다. 기존 화면 통신 단위 53개는 [별도 범위](2026-10-11_2250_frontend_resume_contract.md)의 근거입니다.

실서버 확인(서버 응답): 로컬 개발 앱·DB와 운영 기준 이미지의 격리 합성 DB에서 요청 경로를 검증했습니다. 운영 중인 cs 프로젝트 서버의 새 코드 응답은 아직 확인하지 않았습니다.
