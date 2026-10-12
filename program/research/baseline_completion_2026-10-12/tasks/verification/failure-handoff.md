## 최종 독립 검증 인계 — 2026-10-12T06:54:08.573439+09:00

[최종 결과와 필수 미통과·미검증 범위](final-handoff-2026-10-12.md)를 먼저 확인합니다. 이전22건·보안156건·이력14건은 모두 통과했고 통합 원본7/7회 집계·해시가 일치했습니다. 제품 전체 인수는 보류입니다. 검색16건과 요식·이동 실자료7건은 남아 있습니다. [현재 JSON](runs/2026-10-12_followup_064826/final-handoff.json), [변경 전 백업](_backup/2026-10-12_065408_final_handoff/).

# 검증 실패 재현과 통합 접합안 — 2026-10-12

최신 공통 시험은 871/871 통과이며 여행 시험에서는 새 접합 결함을 확인했습니다. 이 검증 세션은 제품 기능이나 시험 본문을 수정하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 최신 공통 시험 | 통과 | 871/871 = 100% |
| 여행 삭제 실제 재현 | 결함 확인 | 1/1 = 100% |
| 일정 고정 단독 재현 | 실패 재현 | 1/1 = 100% |

## 현재 여행 접합 실패

**05:15 정정:** 아래 1번의 발견 당시 잔존은 최신 삭제 코드·SQL로 다시 실행해 여행 연결 행 3종이 모두 0임을 확인했습니다. [최신 재현](runs/2026-10-12_final_hash_1/trip-delete-latest.json). 진단 기록의 여행 연결 해제와 전체 롤백도 확인했으며, 전체 게스트·회원 삭제 시험은 별도 최신 실행 중입니다. 아래 최초 실패 설명은 이력으로 보존합니다.

1. **여행 삭제 뒤 운영 조회 기록이 남습니다.** `test_every_table_that_carries_a_trip_number_is_accounted_for`는 운영 신규 표 3개가 정리 목록에 없다고 실패했습니다. [최신 전체 SQL의 외래 키 조회](runs/2026-10-12_common_final_1/operations-trip-constraints.json)에서 진단 사건은 `ON DELETE SET NULL`, 조회 예산·조회 시각 표는 외래 키가 없는 것을 확인했습니다. [실제 삭제 함수](../../../../../final_project_cs/app/domains/travel_ops/components/itinerary/trip_delete.py)의 `_PURGE`에도 조회 표 2개가 없습니다. [합성 여행 직접 재현](runs/2026-10-12_common_final_1/trip-delete-orphan-reproduction.json)에서는 실제 `delete_trip` 후 trips 0행·조회 예산 1행·조회 시각 1행이었고 진단 사건의 여행 연결은 해제됐습니다. 시험 자료는 전체 롤백됐습니다. **접합안:** 기존 여행 삭제·게스트/회원 정리 경로에 조회 기록 2개 파기를 연결하고, 진단 사건의 비식별 보존 계약과 삭제 관문 목록을 근거와 함께 일치시킵니다. 단순히 3개 표를 예외 목록에 넣고 통과시키지 않습니다.

2. **고정 일정 검사에 이동 항목이 추가됩니다.** `test_a_locked_item_is_registered_as_customer_pinned`는 고정 장소 true·다른 장소 false 값은 맞지만 추가된 이동 항목(false) 때문에 전체 사전 비교가 실패했습니다. [단독 재현](runs/2026-10-12_clean_travel/pinned-recheck.xml)도 1실패입니다. [시험](../../../../../final_project_cs/tests/e2e/test_intake_review.py)의 조회는 kind를 가리지 않고 모든 일정 항목을 비교합니다. 이동 항목을 저장하는 현재 계약과 시험의 검사 범위를 먼저 맞춰야 합니다. 이 한 실패로 고객 고정 기능이 깨졌다고 단정하지 않습니다.

3. **선택 장소 등록이 시간 겹침으로 거절됩니다.** `test_a_place_the_customer_picked_is_taken_as_shown_and_stays_private_to_the_trip`는 200 기대에 422 `itinerary_infeasible`을 받았습니다. 추가 이동 항목 종료 11:49와 다음 올리브영 시작 11:25가 겹칩니다. [진행 원본](runs/2026-10-12_clean_travel/travel-v3c-progress.jsonl)에 실제 응답·시험 줄이 있습니다. 이동 삽입 시각과 자동 조정·등록 검사 접합을 검토하고, 고객이 고른 장소의 여행 범위 보존까지 함께 다시 확인해야 합니다. 전체 실행은 계속 중이므로 추가 실패는 후속 집계에서 확인합니다.

## 초기 공통 실패의 최신 처리

### 05:08 추가 여행 실패

4. **예약 사실 보존과 고객 고정 계약을 섞은 검사 2건입니다.** `test_booking_declared_without_a_number_stays_booked_after_registration`와 `test_a_booking_number_is_carried_and_protects_the_item`는 예약 정보 보존 검사 뒤 `protected_reason(...) == "booked"`에서 실패했습니다. [현재 D-020](../../../../../wiki/decisions/D-020-trip-survey-and-ask-first.md)의 9월 24일 오전 정정 A는 돈·예약 여부로 항목을 고정하지 않고 `customer_pinned`만 보호하도록 명시합니다. 10월 12일 규칙은 업체 예약·결제·환급 승인 검사를 별도로 유지합니다. **접합안:** 예약 정보 보존 검사와 고객 고정 검사, 공급자 거래 승인 검사를 각각 유지하며 현재 결정에 맞게 시험 기대를 대조합니다. 예약 정보를 잃었다거나 승인 검사를 없애야 한다는 결론이 아닙니다.

5. **항목별 결과 표지 없는 실패가 고객 통지로 이어졌습니다.** `test_a_batch_whose_close_has_no_item_tokens_is_not_announced`는 `fatal_source_failure`로 닫힌 묶음에 `notified`가 생겨 실패했습니다. [시험](../../../../../final_project_cs/tests/e2e/test_watch_failures.py)은 바뀐 항목을 모르면 고객 통지 대신 운영 진단으로 보내는 경로를 검증합니다. `batch_executor`·`trip_watch_batch`의 최신 진단 접합이 실행 시작 뒤 바뀌었으므로 최신 코드 단독 재현과 실패 통지 계약 확인이 필요합니다. 이 검증 과정은 고객 알림을 실제 발송하지 않았습니다.

이전 1번 삭제 결함의 코드와 SQL도 실행 시작 뒤 변경됐습니다. 최초 직접 재현은 발견 당시 증거로 보존하며 최신 코드에서 재검증하기 전 해결로 바꾸지 않습니다.

아래 초기 19실패의 원문과 단계 측정은 보존합니다. 최신 공통 실행은 [871/871 통과](runs/2026-10-12_common_final_1/common-final-v1.xml)입니다. 다른 담당이 역사 원문을 보존하는 상태 인덱스와 조회 진입을 보장하는 취소 시험을 접합했습니다. 초기 실패를 현재 미해결 개수로 계속 세지 않습니다.

## 과거 결함 보고서 상태 18건

[검사 코드](../../../../../final_project_cs/tests/unit/core/test_debug_report_status.py)는 문서 전체에서 `## 해결됨`·`## 미해결`을 찾습니다. 두 표현이 같이 있거나 둘 다 없는 보고서가 실패했습니다. [실행 집계](runs/2026-10-12_035832/summary_042048.json)의 `failed_nodeids`가 정확한 재현 목록입니다. [공통 로그](runs/2026-10-12_035832/common-v2.log)에 각 assertion과 원문 경로가 있습니다.

현재 상태를 표시해야 한다는 요구와 역사 기록을 소급해서 바꾸지 않는 요구를 함께 지켜야 합니다. wiki 담당·통합 담당은 우선 보고서 첫 상태 표기를 현재 상태로 읽는 계약과 검사 범위를 정합시켜야 합니다. 과거 발견 상태를 삭제하거나 사실 확인 없이 해결로 바꾸는 방식은 사용하지 않습니다. 이번 세션은 해당 기록을 수정하지 않았습니다.

재현은 공통 실행기를 사용해 `tests/unit/core/test_debug_report_status.py`만 선택합니다. 보고서 파일 목록이 이후 추가되면 분모와 실패 이름도 달라질 수 있으므로 해당 시점 해시를 함께 남깁니다.

## 30ms 원격 조회 취소 시험 1건

[시험](../../../../../final_project_cs/tests/unit/ports/test_team_ports.py)의 `test_a2a_poll_timeout_is_bounded_and_best_effort_cancels_remote`는 마감을 먼저 정한 후 실행기를 만듭니다. [구현](../../../../../final_project_cs/app/core/remote_team/a2a_executor.py)은 초기 설정을 읽고 동기 조회 함수를 스레드로 보내며, 제출에 들어가기 전에도 마감을 검사합니다. 원격 식별자를 받기 전 마감되면 취소할 원격 작업이 없습니다.

원본 조건 단독 실행: 1실패·7선택 제외. [재현 로그](runs/2026-10-12_035832/a2a-recheck.log)·[결과](runs/2026-10-12_035832/a2a-recheck-outcomes.json).

[단계 측정기](probe_a2a.py)는 동기 조회 조건과 비동기 조회 비교를 교대로 3회씩 실행했습니다. 30ms 마감은 동일하게 유지했습니다. 동기 조건은 3/3회 제출 전 종료, 비교 조건은 3/3회 조회·취소까지 진입했습니다. 첫 객체 생성 217.33ms, 두 번째 동기 조회 진입은 마감 설정부터 44.10ms였습니다. 이는 현재 PC 부하와 첫 설정 읽기·스레드 준비 시간이 시험 경로를 바꿀 수 있다는 직접 증거입니다. 독립 성능 비교나 제품의 모든 취소 경로 보증은 아닙니다. 원본에는 이벤트별 실제 시각과 구현 해시가 있습니다.

접합안: 설정·실행기를 마감 설정 전에 준비하고, 이 시험의 조회는 즉시 끝나는 비동기 함수로 만들어 실제 원격 조회 진입을 보장합니다. 별도의 동기 조회 마감 시험은 유지합니다. `poll` 진입을 명시적으로 확인한 다음 마감 시 취소를 검증합니다. 제품 마감을 늘리거나 취소 assertion을 지워 통과시키지 않습니다. 구현 담당의 검토 뒤 해당 시험과 기존 마감·계약 시험을 다시 실행해야 합니다.

## 실행 중 소스 변경

### 05:23 추가 인계

**05:27 마감 원인 확인:** [시험 helper](../../../../../final_project_cs/tests/unit/travel/helpers.py)는 발견 당시 모듈 import 시각 `NOW + 90초`를 모든 새 작업의 마감으로 재사용했습니다. 전체 실행에서 해당 단위 시험에 도달하기 전 이미 만료될 수 있습니다. 통합 담당이 보존한 수정 전 사본의 해시는 여행 전체·219건 재검증의 시작 해시와 같습니다. [직접 교대 재현](runs/2026-10-12_final_hash_1/fixture-deadline-comparison.json)에서 수정 전 함수의 새 시각은 3/3 완료, import 시각 120초 경과 조건은 3/3 `fatal_source_failure`·전 항목 retry, 수정 후 현재 함수는 과거 import 시각 조건에서도 3/3 완료였습니다. 제품 계산기와 90초 제한은 유지했습니다. 최신 직접 일정·읽기·실행 계획 단위 [75/75 통과](runs/2026-10-12_final_hash_1/latest-unit-recheck.xml)와 묶음 [15/15 통과](runs/2026-10-12_common_final_1/batch-unit-recheck.xml)를 보존합니다. 이 원인 재현으로 전체 실행의 다른 실패까지 해결로 간주하지 않습니다.

최신 접합 선택 실행은 [219건 중 208통과·11실패](runs/2026-10-12_final_hash_1/integration-recheck-v1.xml)입니다. 선택 수는 [수집 원본](runs/2026-10-12_final_hash_1/integration-recheck-v1-collection.json)으로 확인했습니다. 실제 삭제 기록의 최신 직접 재현과 게스트·여행 삭제 관련 시험은 통과했습니다. 합성 조직을 준비한 뒤 승인 관련 준비 오류 6건도 이 실행에서는 통과했습니다. 지식·요식 자료는 적재하지 않았습니다.

이 실행 중에도 직접 일정 처리·읽기 요청·예약 기대·감시 통지 시험 등이 수정됐습니다. 실패 출력에는 수집 때의 assertion과 그 뒤 바뀐 소스 줄이 함께 보이는 사례가 있어, 현재 파일만 읽고 당시 실행 문장을 역으로 확정하지 않습니다. 최신 단위 재검증과 소스 해시를 따로 보존합니다.

- **API 표면 검사 2건:** 연결 폐기 경로는 `personal_ai_api.member` 안에서 브라우저 회원 쿠키를 확인하지만, 검사기는 FastAPI `Depends` 이름만 순회해 인증 의존성이 없다고 판정합니다. 실제 인증을 없애거나 공개 경로 예외로 통과시키지 말고 기존 인증/CSRF 부정 시험과 함께 선언·검사를 접합해야 합니다. 추가 경로 4개는 연결 목록·연결 폐기·공개 시험 시나리오·접수 복원이며 [OAuth 계약](../../../../../final_project_cs/wiki/external/personal-ai-oauth.md)·[시험 시나리오 계약](../../../../../final_project_cs/wiki/external/test-scenarios.md)·[접수 계약](../../../../../final_project_cs/wiki/external/rest-endpoints/web-intakes.md)에 정의가 있습니다. 문서가 없다는 결론 대신 검사 목록 정합성을 확인합니다.
- **출발 재계산 4건:** 급행 내용 판 변경 2건·인원/피로 변경 2건은 새 일정 판 3을 기대했지만 2였습니다. 시험이 여행 조건을 다시 쓸 때 `first_visit`·이동 선호만 넣고 자동 변경 동의 값을 생략합니다. [현재 D-020](../../../../../wiki/decisions/D-020-trip-survey-and-ask-first.md)의 미응답 기본 꺼짐과 대조해, 자동 변경을 시험하는 조건은 명시적으로 켜고 기본 꺼짐은 별도 확인해야 합니다. 원인 확정 전 기대 숫자만 바꾸지 않습니다.
- **여행 묶음 단위 11건:** 전체 실행에서는 실패했지만 새 프로세스 단독 실행은 [15/15 통과](runs/2026-10-12_common_final_1/batch-unit-recheck.xml)입니다. 공유 상태 누출과 동시 소스 변경을 아직 구분하지 못했습니다. 단독 통과로 전체 실패를 삭제하지 않습니다.
- **평가·이동 검산:** 여행용 공격 자료의 검사에서 옛 `order_id` 문구를 요구하는 1건이 실패했습니다. 현재 자료는 예약을 사용하므로 쇼핑몰 자료를 복원하지 말고 여행의 대조 의미를 검증해야 합니다. 택시 검산은 중형 23:30·5km에서 기대 10,400원과 계산 10,300원으로 단독 실행도 1실패/31검사입니다. [검산 로그](runs/2026-10-12_final_hash_1/car-fare-recheck.log). 공식 요금·반올림 규칙과 기존 이동 담당 결정에 맞춰 입력·기대·산식을 확인해야 하며 기대값만 고치지 않습니다.

공통 전체 실행 전후 해시가 13파일에서 다릅니다. 호출 조립·감시·여행 처리·운영 진단 SQL·설정이 포함됩니다. [집계](runs/2026-10-12_035832/summary_042048.json)의 `source_changes`를 기준으로 최종 구현과 재대조해야 합니다. 이번 결과는 변경 중의 회귀 관측이며 최종 기준선 승인 결과가 아닙니다.


## 최신 남은 실패 22개

[최초 실패 선택 재검증](runs/2026-10-12_final_hash_1/travel-failures-recheck-v2.xml)은 31통과·22실패입니다. 실행 중 소스 5개가 바뀌었으며 [정확한 오류와 변경 목록](runs/2026-10-12_final_hash_1/remaining-failures.json)을 보존합니다.

| 검사 파일 | 실패 수 |
|---|---|
| [test_departure_express_db_v1.py](../../../../../final_project_cs/tests/scenario/test_departure_express_db_v1.py) | 2 |
| [test_departure_party_db_v1.py](../../../../../final_project_cs/tests/scenario/test_departure_party_db_v1.py) | 2 |
| [test_defense_metrics.py](../../../../../final_project_cs/tests/unit/eval/test_defense_metrics.py) | 1 |
| [test_car_fare.py](../../../../../final_project_cs/tests/unit/travel/mobility/test_car_fare.py) | 1 |
| [test_departure_watch_v1.py](../../../../../final_project_cs/tests/unit/travel/test_departure_watch_v1.py) | 1 |
| [test_dining_alternative_opening.py](../../../../../final_project_cs/tests/unit/travel/test_dining_alternative_opening.py) | 2 |
| [test_dining_nearby_fallback.py](../../../../../final_project_cs/tests/unit/travel/test_dining_nearby_fallback.py) | 5 |
| [test_moves_refresh_after_swap.py](../../../../../final_project_cs/tests/unit/travel/test_moves_refresh_after_swap.py) | 2 |
| [test_trip_api_plugin_boundaries.py](../../../../../final_project_cs/tests/unit/travel/test_trip_api_plugin_boundaries.py) | 6 |

출발 실패 진단은 대역 연결이 `None`인데 알림 저장의 `transaction()`에 도달했습니다. 식당 대안 7건에는 시험용 연결에 `cursor()`가 없는 경우와 가까운 식당 서비스 대역이 호출되지 않은 경우가 있습니다. 이동 2건은 실제 계산기 대역 대신 직선 추정으로 갔습니다. HTTP 경계 6건은 소유 모듈 비활성 상태에서 접수 복원 조회가 추가되고 대역 항목의 `starts_at`에 접근했습니다. 현재 계약·실제 서비스 경계와 시험 대역을 함께 대조해야 하며 assertion만 삭제하지 않습니다.


## 후속 대조 2026-10-12 05:49:42 KST

통합 담당의 최신 원본 실행은 229건 중 218통과·11건너뜀·0실패·0준비 오류입니다. 과거 22실패 중 22/22가 이 실행에서 통과했습니다. 이는 통합 담당 실행 결과이며, 이 검증 세션의 독립 재검증이나 최신 여행 전체 통과가 아닙니다. 실행 중 소스 변경은 0개, 대조 시점 이후 변경은 0개입니다.

검증 세션 최신 정책 시험 이후 소스 12개가 달라졌습니다. 통합 담당이 추가 수정 중이므로 영향 재검증 대상과 대기 조건을 저장했습니다. 새 제품 시험·검증 클러스터 재시작·업무 DB 변경·원격 배포·유료 호출·다른 세션 메시지는 하지 않았습니다.

- 대조 원본·22개 개별 대응·건너뜀 사유·재검증 대상: [heartbeat-2026-10-12_054942.json](C:/Users/playdata2/Documents/final_workspace/program/research/baseline_completion_2026-10-12/tasks/verification/runs/2026-10-12_final_hash_1/heartbeat-2026-10-12_054942.json)
- 변경 전 판본: [2026-10-12_054942_heartbeat_dependency](C:/Users/playdata2/Documents/final_workspace/program/research/baseline_completion_2026-10-12/tasks/verification/_backup/2026-10-12_054942_heartbeat_dependency/)


## 독립 선택 실행에서 새로 확인한 준비 상태 충돌 06:03 KST

이전 실패 22개만 새 프로세스에서 실행하면 **18통과·4실패**입니다. 실행 중 소스 변화는 0개입니다. 급행·동행자 변경 시나리오 4개가 `live mobility engine settings require a process restart`로 실패했습니다. 기존 판 버전 숫자 불일치와 다른 오류입니다. 공통 시험 준비는 이동 상태를 초기화하지만 조립기의 프로세스 설정 키를 같이 초기화하지 않으며, 해당 시나리오는 상태를 직접 켭니다. 통합 실행에서는 먼저 앱을 초기화하는 다른 시험의 영향을 받을 가능성을 추가 대조 중입니다. 제품 보호를 끄지 말고 시험 준비를 일치시킨 뒤 단독 실행이 필요합니다.

[개별 실패·명령 원본](runs/2026-10-12_followup_060032/independent-order-failure.json) · [변경 전 판본](_backup/2026-10-12_060353_independent_failure/)


## 후속 독립 검증 2026-10-12 06:12 KST

후속 독립 검증에서 공통 전체·운영 opt-in·관련 보안 회귀가 통과했습니다. 단독 실행의 준비 순서 문제 4개는 통합 대기로 남깁니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 공통 전체 실행 | 884통과·20건너뜀 | 904/904 = 100% 실행 |
| 운영 opt-in | 20통과 | 20/20 = 100% |
| 영향 보안·회귀 | 210통과 | 210/210 = 100% |
| 기존 관문 연결 여행 검사 | 150통과 | 150/150 = 100% |

분모는 각 실행에서 선택한 실제 시험 수입니다. 실행끼리 겹치는 시험을 합산하지 않습니다. 공통 건너뜀 20개는 메모리 PostgreSQL 12개·native PostgreSQL 8개로 별도 실행해 20개 모두 통과했으며, 단일 공통 실행 904통과라고 표기하지 않습니다.

이전 실패 22개만 고른 새 프로세스에서는 18통과·4실패입니다. 같은 소스에서 확장 선택 210개를 실행하면 이 4개도 통과합니다. 두 실행 사이와 각 실행 중 소스 변경은 0개입니다. 공통 준비는 이동 엔진 상태를 초기화하지만 조립기의 프로세스 설정 키는 초기화하지 않고, 해당 시나리오가 상태를 직접 켜는 경계에 문제가 있습니다. 제품 런타임 보호를 끄지 말고 단독 실행 준비를 보완해야 합니다.

기존 관문 도구의 26개 항목 중 26/26이 연결한 실제 검사를 통과했습니다. 이는 기존 도구 연결 검사 결과이며 현재 wiki의 전체 제품 인수·원래 릴리스 래퍼 실행·배포 완료를 뜻하지 않습니다. 최신 여행 전체는 통합 담당이 새 격리 DB에서 실행 중이라 중복 실행하지 않습니다.

기존 Oracle ARM 기록에서 장소 벡터 2041개·안내 청크 11개, 검색 진단 6/6·채팅 4/4를 원본과 대조했습니다. 게시자 Gemma-4-E4B QAT Q4_0 원본이며 우리 데이터 추가 학습은 없습니다. 당시 응답은 약 60~69초이고 독립 제품 평가셋은 아닙니다. 운영·자동 업데이트 보존 파일 해시는 5/5 일치하지만 현재 로컬 원본은 3/5만 일치하므로 현재 로컬의 원격 반영 증거로 쓰지 않습니다. 이 기록은 격리 여행 규정 시험의 12문서·130청크 전제를 대신하지 않습니다. 새 원격 요청·추론·민감 자료 전송을 하지 않았습니다.

검증 클러스터는 접속 0개 확인 후 정상 종료했고 이번 opt-in 시험 DB·역할만 삭제했습니다. 합성 DB와 실행 원본은 보존했습니다. 업무 DB·원격 배포·고객 알림·유료 호출·커밋·푸시는 하지 않았습니다.

- 결과·개별 판정·해시·범위: [followup-summary.json](C:/Users/playdata2/Documents/final_workspace/program/research/baseline_completion_2026-10-12/tasks/verification/runs/2026-10-12_followup_060032/followup-summary.json)
- 단독 선택 4실패: [independent-order-failure.json](C:/Users/playdata2/Documents/final_workspace/program/research/baseline_completion_2026-10-12/tasks/verification/runs/2026-10-12_followup_060032/independent-order-failure.json)
- 기존 Oracle ARM 원본 대조: [existing-arm-evidence-review.json](C:/Users/playdata2/Documents/final_workspace/program/research/baseline_completion_2026-10-12/tasks/verification/runs/2026-10-12_followup_060032/existing-arm-evidence-review.json)
- 검증 환경 정리: [cleanup.json](C:/Users/playdata2/Documents/final_workspace/program/research/baseline_completion_2026-10-12/tasks/verification/runs/2026-10-12_followup_060032/cleanup.json)
- 백업: [변경 전 판본](C:/Users/playdata2/Documents/final_workspace/program/research/baseline_completion_2026-10-12/tasks/verification/_backup/2026-10-12_061206_followup_results/)


## 기존 경보·택시 원본 대조 2026-10-12 06:18 KST

경보와 택시의 개발 시험 통과를 제품 실사용 완료로 확대하지 않도록 기존 원본과 현재 소스를 대조했습니다. 이번 회차에서는 제품 시험·수집·분석·개인 영수증 접근·외부 호출을 새로 실행하지 않았습니다.

| 확인 | 결과 | 분모 |
|---|---|---|
| 경보 원본·입력 해시 | 모두 일치 | 58/58 = 100% |
| 경보 방향 수용 시험 | 2통과·18실패 | 2/20 = 10% 통과 |
| 택시 미터 오차1000원 이내 | 2건 | 2/4 = 50% |
| 택시 증거 소스·자료 해시 | 2개 변경 | 111/113 = 98.2% 일치 |

경보는 제품 규칙196/196과 공간 대조 자체13/13을 통과했지만 방향 수용20건 중18건이 실패했습니다. 방향별 도로 입력은12/28건이고 실제 고객 여행 영향은 확인0건이며 대안 안전도 미확인입니다. 도로 조각의 존재를 사건 시각의 고객 전체 이동 경로로 바꾸어 기록하지 않습니다.

택시 원본 JUnit은 Python279/279와 별도 후속 웹85/85이며 서로 더하지 않습니다. mock 서버 시험4/4 (화면 반응)을 로그에서 확인했습니다. 실서버 확인(서버 응답): 안 했음 — 해당 작업의 x600 서버 cs 프로젝트 서버·실제 DB 왕복은 원본상 미확인입니다. 현재 공식 정책으로 과거4건을 재생한 예산 충족4/4와, 미터4/4 과소추정·평균 절대오차1125원을 구분합니다. 당시 정책·GPS·사전 견적을 새로 확보한 독립 검증이 아닙니다.

택시 증거 명세에서 현재와 다른 파일은 [일정 직접 작성 부품](C:/Users/playdata2/Documents/final_workspace/final_project_cs/app/domains/travel_ops/components/intake/direct_schedule.py)과 [이동 규칙](C:/Users/playdata2/Documents/final_workspace/final_project_cs/app/domains/travel_ops/instances/mobility/engine/rules/rules_v0.3.json)입니다. 과거 결과를 현재 전체 통과로 재사용하지 않습니다. 최신 여행 전체는 통합 담당이 실행 중이고 이 검증 세션의 최근 공통 소스와 현재 디스크는 변경0개라 중복 실행하지 않습니다. 단독 시나리오4개 준비 문제와 자료 전제도 계속 대기합니다.

- 개별 실패·원본 수치·현재 해시: [대조 원본](C:/Users/playdata2/Documents/final_workspace/program/research/baseline_completion_2026-10-12/tasks/verification/runs/2026-10-12_followup_060032/external-evidence-061742.json)
- 변경 전 보존: [백업](C:/Users/playdata2/Documents/final_workspace/program/research/baseline_completion_2026-10-12/tasks/verification/_backup/2026-10-12_061838_external_evidence_review/)
