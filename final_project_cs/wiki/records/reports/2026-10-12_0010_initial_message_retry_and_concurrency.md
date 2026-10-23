# 초기 메시지 실패 재시도·동시 생성 경계 보완

초기 실행 실패를 완료한 중복 요청으로 응답하던 경계를 저장된 동일 업무 재시도로 바꿨습니다. 같은 초기 요청이 동시에 들어와 업무가 두 개 만들어지는 결함도 실제 HTTP로 재현하고 생성 장부로 차단했습니다. 운영 배포 완료 또는 모든 결함 부재를 뜻하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 초기503 재시도·마스킹·버전 HTTP | 선행 판 통과 | 8/8 = 100% |
| 동시 생성·메시지·여행·tenant 분리와 경합 | 최종 판 통과 | 7/7 = 100% |
| 답변 커밋 직후 중단 HTTP 복구 | 선행 판 통과 | 1/1 = 100% |
| 최초 담당 비활성 HTTP 재시도 | 선행 판 통과 | 1/1 = 100% |
| 최종 경합·상태 unit와 관련 회귀 | 통과 | 31/31 = 100% |
| 실제 Sonnet 최종 보충 감사 | 완료 | 1/1 = 100% |

분모는 각각의 pytest 수집·실행 결과입니다. HTTP는 합성 여행을 쓰는 로컬 개발 서버 앱의 실제 요청/DB 경로입니다. mock 서버 화면 시험, 운영 고객 실측 또는 이동 경로 정확도 측정이 아닙니다. 동시/경합 HTTP7개는 최종 제품 판에서 재실행했습니다. 나머지 HTTP10개는 마지막 경합 관문 직전 판의 선행 근거이며, 최종 배포 후보 검증 기록과 대조해야 합니다.

## 확인한 결함과 변경

1. **커밋 뒤 실패한 초기 요청의 재전송**: 준비 계산에서 실패한 routing과 Team 실행 중 실패한 running을 mode on/off 각각 실제 HTTP로 재현했습니다. 저장된 `conversation_dispatch`를 CLASSIFIED와 함께 커밋한 뒤 실패하면 같은 Case·같은 기준 버전·같은 해석으로 이어갑니다. 재전송마다 분류/추출 모델을 다시 부르지 않으며 실행 불가는 계속503입니다. 활성 실행, 옛 계획 없는 미완료 업무, new/classifying/resuming와 이미 답변 이력이 있는 업무는409입니다. 대기/종결 조회 정책을 바꾸지 않습니다. 이후 일정이 변경되면409로 거절하며 최신 버전을 조용히 대입하지 않습니다.
2. **동시 최초 요청의 중복 생성**: 모델 해석 완료 시점만 Barrier로 맞춘 두 동일 HTTP 요청은 수정 전200/200과 Case2를 만들었습니다. `create_case_once`는 기존 action_requests 장부와 짧은 advisory 트랜잭션으로 Case·CREATED·생성 장부를 함께 기록합니다. 기존 `open_case`의 몸통과 즉시 분류 의미는 변경하지 않았습니다. 웹 호출자는 생성 전 읽기 트랜잭션을 종료하며 생성 잠금이 후속 분류/Team까지 남지 않습니다. 동시 최초 모델 호출은2회 가능하지만 Case/CREATED는1개이고 뒤 요청은409입니다. 먼저 저장된 상태를 덮지 않습니다.
3. **메시지 원문 구분**: 신규 Case에는 원문의 SHA-256만 저장해 마스킹 결과가 같은 서로 다른 메시지도409로 구분합니다. 원문 저장과 event projection은 기존 마스킹 함수를 거칩니다. 옛 SHA 없는 Case만 masked subject 비교와 호환합니다. selected/at/location까지 같은지 검사하는 계약은 아닙니다. 같은 메시지 재전송은 최초 계획을 유지하며 새로운 의미의 요청은 새 request_id를 사용합니다. key는 tenant/trip/request 범위이며 다른 여행과 다른 tenant는 충돌하지 않습니다.
4. **사전 확인 뒤 실행 경합**: ActiveRunError가 HTTP500으로 전파되는 running 재시도를 DB 없는 unit로 재현했습니다. 실제 Sonnet5.5도 독립 정적 검토에서 같은 문제를 지적했습니다. 최종 수정은 retry_initial의 routing→execute와 running→run_case 두 분기에서 이 예외만409로 변환합니다. 승자의 run/Case를 변경하지 않습니다. API 전체 예외 catch는 넓히지 않았습니다.

후속 Sonnet는 routing 재시도가 최신 running/resolved 상태를 읽은 뒤 ROUTED를 시도하는 별도 창을 지적했습니다. 승자 실행 중/완료 두 조건을 실제 HTTP로 재현한 뒤, execute가 최신 상태를 읽은 직후 routing이 아니면409로 거절하게 했습니다. 이 읽기 이후의 경합은 기존 expected_version 관문이 전이 유효성보다 먼저 확인합니다. InvalidTransition 전체 catch는 추가하지 않았습니다. 최종 실제 Sonnet는 이 수정과 시험을 읽고 새 지적 없이 독립 unit31/31을 실행했습니다.

입력 커밋 후 실행 시작 전 중단은 별도 실제 HTTP 시험에서 resuming 상태를 확인한 뒤 같은 답변 이벤트로 복구했습니다. VALID_INPUT1/RESUMED1/적용1/변경 알림1이며 초기 원문 재전송으로 답변 처리를 대신하지 않습니다.

## 코드·시험 범위

- [app/application/case_intake.py](../../../app/application/case_intake.py): 신규 중립 `create_case_once`와 공개 이름만 추가했습니다. 도메인 import와 스키마 변경은 없습니다.
- [components/conversation/trip_messages.py](../../../app/domains/travel_ops/components/conversation/trip_messages.py): 초기 Case 생성, 최초 실행 계획 저장, 기존 요청 처리와 계획 추출 함수입니다. 부모 작업의 대기 상관관계 수정과 함께 파일을 공유했으므로 전체 파일을 옛 사본으로 덮지 않았습니다.
- [components/conversation/case_dispatch.py](../../../app/domains/travel_ops/components/conversation/case_dispatch.py): execute/descriptor/retry_initial이 본 작업 범위입니다. resume_pending/_matches_implicit_reply는 부모가 별도 담당했습니다.
- 신규 시험: [tests/e2e/test_web_initial_retry.py](../../../tests/e2e/test_web_initial_retry.py)8, [tests/e2e/test_web_initial_concurrency.py](../../../tests/e2e/test_web_initial_concurrency.py)7, [tests/e2e/test_web_resume_commit_recovery.py](../../../tests/e2e/test_web_resume_commit_recovery.py)1, [tests/unit/travel/test_initial_retry_boundaries.py](../../../tests/unit/travel/test_initial_retry_boundaries.py)20입니다.

기존 DB 열만 사용합니다. 초기 재시도의 신규 SELECT는 customer_cases의 tenant_id/case_id와 agent_runs의 tenant_id/case_id/status를 읽습니다. 생성은 기존 repository와 action_requests 장부를 사용합니다. 059/227의 pending_changes.proposal_scope 열이나 constraint를 신규 코드에서 참조하지 않습니다. 기존 도메인 적용 코드 전체가 그 열을 쓰지 않는다는 주장과는 구분합니다.

## 실행 근거와 판 구분

모든 로그는 [wiki/records/evidence/2026-10-11_1936_team_plugin_implementation/](../evidence/2026-10-11_1936_team_plugin_implementation/)에 보존했습니다.

| 로그 | 결과 | 의미 |
|---|---|---|
| [initial-retry-e2e-v1.log](../evidence/2026-10-11_1936_team_plugin_implementation/initial-retry-e2e-v1.log) | 5/5,146.56초 | 초기 실패 on/off·prepare/team와 추출 실패 분류 기록 |
| [initial-retry-regression-v2.log](../evidence/2026-10-11_1936_team_plugin_implementation/initial-retry-regression-v2.log) | 25/25,114.77초 | HTTP9와 당시 unit16; 실행 중 시험 쿼리 오타1 수정이 있어 최종 일괄 판으로 부르지 않음 |
| [initial-concurrency-before-v1.log](../evidence/2026-10-11_1936_team_plugin_implementation/initial-concurrency-before-v1.log) | 1실패,29.63초 | 수정 전 실제 두 Case 생성 확정 |
| [initial-concurrency-after-v1.log](../evidence/2026-10-11_1936_team_plugin_implementation/initial-concurrency-after-v1.log) | 29/29,195.33초 | 동시 생성 수정 후 HTTP13와 당시 unit16 |
| [initial-create-scope-v1.log](../evidence/2026-10-11_1936_team_plugin_implementation/initial-create-scope-v1.log) | 2/2,41.10초 | 추가 여행·tenant 분리; 위29와 분리 실행 |
| [resume-commit-http-v1.log](../evidence/2026-10-11_1936_team_plugin_implementation/resume-commit-http-v1.log) | 1/1,36.18초 | 실제 DB에서 VALID_INPUT 이후 RESUMING 중단 복구 |
| [initial-retry-race-before-v1.log](../evidence/2026-10-11_1936_team_plugin_implementation/initial-retry-race-before-v1.log) | 1실패,5.07초 | ActiveRunError 미매핑 재현 |
| [initial-retry-race-after-v2.log](../evidence/2026-10-11_1936_team_plugin_implementation/initial-retry-race-after-v2.log) | 29/29,2.68초 | 이 단계 초기unit18+Controller10+watch1 |
| [initial-routing-race-before-v1.log](../evidence/2026-10-11_1936_team_plugin_implementation/initial-routing-race-before-v1.log) | 1실패,5.23초 | 승자 완료 후 resolved→ROUTED 오류 실제 HTTP 재현 |
| [initial-routing-running-race-before-v1.log](../evidence/2026-10-11_1936_team_plugin_implementation/initial-routing-running-race-before-v1.log) | 1실패,8.66초 | 승자 실행 중 running→ROUTED 오류 실제 HTTP 재현 |
| [initial-routing-race-after-v1.log](../evidence/2026-10-11_1936_team_plugin_implementation/initial-routing-race-after-v1.log) | 38/38,20.63초 | 최종 HTTP7+초기unit20+Controller10+watch1 |

서로 겹치는 집합의 통과 수를 더해 전체 테스트 수로 부르지 않습니다. `ruff`7파일은 통과했습니다. mock 서버 시험은 이 작업에서 실행하지 않았습니다. 실서버 확인(서버 응답)은 합성 로컬 개발 서버 앱의 HTTP/DB 경로만 했으며 x600 서버의 cs 프로젝트 서버 운영 확인은 하지 않았습니다.

최종 본 작업 제품 해시([고정 기록](../evidence/2026-10-11_1936_team_plugin_implementation/initial-message-final-product-sha256.json)). trip_messages.py의 이전 요약에 있던 db169b… 값은 옛 판이므로 현재 고정 기록과 2차 감사 종료 해시가 공통으로 확인한 1b5c70f…로 정정했습니다:

| 파일 | SHA-256 |
|---|---|
| [case_intake.py](../../../app/application/case_intake.py) | 9abd0180e0d0b59fbe71c6340c597dec8d4307287518dbd3ae84ac431c17cd3d |
| [case_dispatch.py](../../../app/domains/travel_ops/components/conversation/case_dispatch.py) | 79201223bd6becf1c523ba269dc8794defca631bd6fbd287db3b21b397298cb4 |
| [trip_messages.py](../../../app/domains/travel_ops/components/conversation/trip_messages.py) | 1b5c70f75a2b659ba96a91c257388c601cd3b69223137cdb5f708353b91a3489 |

## 독립 감사와 백업

실제 첫 Sonnet 감사는 [sonnet-conversation-delta-2026-10-11_2358 결과](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-conversation-delta-2026-10-11_2358-result.txt)와 [모델 메타데이터](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-conversation-delta-2026-10-11_2358-model-metadata.json)입니다. canonicalModel=claude-sonnet-5-5/is_error=false/고정unit27통과/PYTEST_EXIT0이며 정적 경합 지적1개를 별도 실행으로 확정했습니다. 감사 중 시험2파일이 변경됐고 제품 파일은 변하지 않았습니다. reducer.py 경로 오기는 실제 [case_lifecycle/case.py](../../../app/core/case_lifecycle/case.py)의 별도 시작/끝 해시로 보완했습니다. 읽지 않은 validate/reducer/HTTP 시험 범위는 첫 감사의 미확인으로 남기고 새 보충 감사에 전달했습니다.

2차 [sonnet-conversation-followup-2026-10-12_0007 결과](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-conversation-followup-2026-10-12_0007-result.txt)와 [모델 메타데이터](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-conversation-followup-2026-10-12_0007-model-metadata.json)는 요청한 unit3/e2e6/validate/reducer/Controller 관문을 읽고 unit29/29를 직접 실행했습니다. 시작/끝19파일 해시 변화0입니다. 추가 정적 지적1개는 위 실제 HTTP2조건으로 확정해 보완했습니다. 감사 내부에서 허용되지 않은 목록 조회 Bash1회는 권한 장치가 거절했고 Read로 진행했습니다. 제품 수정이나 그 명령 실행은 없었습니다.

마지막 [sonnet-routing-closure-2026-10-12_0016 결과](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-routing-closure-2026-10-12_0016-result.txt)와 [모델 메타데이터](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-routing-closure-2026-10-12_0016-model-metadata.json)는 해당 관문·전이·시험 구간만 읽고 추가 지적 없이 unit31/31(2.37초), PYTEST_EXIT0을 직접 실행했습니다. canonicalModel=claude-sonnet-5-5/is_error=false/권한 거절0/시작·끝4파일 해시 변화0입니다. 실제 HTTP 경합은 Codex가 실행했고 이 마지막 모델은 코드와 후 로그를 읽었습니다. 이 한정 범위 밖을 새로 감사했다고 주장하지 않습니다. 반복 감사는 종료했습니다. [마지막 감사 원문](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-routing-closure-2026-10-12_0016-review.jsonl), [직접 실행 시험 출력](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-routing-closure-2026-10-12_0016-test-output.json), [입력·종료 해시 차이](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-routing-closure-2026-10-12_0016-sha256-diff.json)도 보존했습니다.

백업은 [legacy/team_plugin_lifecycle/2026-10-11_2325_conversation_isolation/](../../../legacy/team_plugin_lifecycle/2026-10-11_2325_conversation_isolation/)(부모의 두 제품 원본), [legacy/team_plugin_lifecycle/2026-10-11_2340_initial_retry_boundaries/](../../../legacy/team_plugin_lifecycle/2026-10-11_2340_initial_retry_boundaries/), [legacy/team_plugin_lifecycle/2026-10-11_2351_initial_create_once/](../../../legacy/team_plugin_lifecycle/2026-10-11_2351_initial_create_once/), [legacy/team_plugin_lifecycle/2026-10-12_0003_initial_retry_race/](../../../legacy/team_plugin_lifecycle/2026-10-12_0003_initial_retry_race/), [legacy/team_plugin_lifecycle/2026-10-12_0013_routing_race/](../../../legacy/team_plugin_lifecycle/2026-10-12_0013_routing_race/)입니다. 보고서 최종 갱신 전 사본은 [_backup/2026-10-12_0018_initial_retry_final/](_backup/2026-10-12_0018_initial_retry_final/)입니다. 이번 링크 보정 전 사본은 [_backup/2026-10-12_0020_initial_retry_links/](_backup/2026-10-12_0020_initial_retry_links/)입니다. 해시 표 정정 전 사본은 [_backup/2026-10-12_0022_initial_retry_hash/](_backup/2026-10-12_0022_initial_retry_hash/)입니다. 첫 초기 retry 계약 문단 추가 직전의 정확한 계약 사본은 따로 만들지 않았습니다. 이후 변경 전의 계약 사본과 이전 단계 백업은 보존했습니다. 이를 백업 완료로 소급하지 않습니다.
