# 출발 재검증 구조·필수키 최종 보강

저장 경로 구조와 대중교통 필수 이름 누락에 따른 출발 안내 중단을 막았고, 관련217개 시험이 모두 통과했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 신규 구조·회복 회귀 | 통과 | 9/9 = 100% |
| 신규 필수키·정상 저장 회귀 | 통과 | 16/16 = 100% |
| 저장 문맥 회귀 | 통과 | 6/6 = 100% |
| 전체 고유 관련 시험 | 통과 | 217/217 = 100% |

217 = 앞서 확인한195개 + 추가 필수키16개 + 기존 저장 문맥6개입니다. 실제 제품21개 기능의 완성률이 아니라 이번 관련 시험 통과율입니다. 건너뜀0, 최종 종료 코드0입니다.

## 실제 확인한 결함과 수정

1. 경로가 dict·문자열·정수이거나 구간 항목이 비매핑이면 실제 첫 구간 처리에서 예외가 났습니다. 수정 전 신규9시험에서8실패·1통과를 기록했습니다. 경로를 비어 있지 않은 list, 각 구간을 dict로 조회 전에 확인합니다.
2. 빈 dict 또는 버스 route/from/to·지하철 line/from/to 누락은 위 형태 검사만으로 통과했습니다. 수정 전 추가16시험에서13실패·3통과를 기록했습니다. 실제 판정기에서 KeyError('route'/'from'/'to'/'line')와 잘못된 역 타입의 TypeError가 재현됐습니다. 대중교통 구간의 필수 이름3개가 비어 있지 않은 문자열인지 조회 전에 확인하고 기존 `needs_replan/route_check_missing_or_changed`로 반환합니다. 생략된 mode의 지하철 기본 해석, 정상 버스·지하철 및 JSON 왕복은 유지합니다.

Sonnet 검토의 ‘빈 dict가 predicted 지하철 매칭 뒤 rail_departures 키 생성에서 예외’라는 특정 경로는 확정하지 않았습니다. 실제 역 색인은 빈 dict를 unavailable로 처리했습니다. 확인된 실제 결함은 그 뒤 모델 재검증·구간 판정의 필수키 직접 접근 및 손상 후속 구간 확인 전에 첫 공급자 정보를 조회하는 경로입니다.

## 발견한 기존 시험 연결 문제

확장 첫 실행은216통과·1실패였습니다(`required-fields-after-v1.log`). 기존 `test_new_place_rejudgment_replaces_old_context`는 조립 뒤 `wiring.leg_planner`를 교체했지만, 소비 부품은 조립 때 원래 함수가 등록된 `team_hooks.legs.leg_planner`를 읽습니다. 운영 코드가 정상적으로 사용하는 등록 함수를 시험 대역이 교체하지 못한 문제였습니다.

상위 작업의 명시적 승인 범위에서 해당 시험1개를 백업하고 대역을 소비 위치에 주입하도록 보완했습니다. 제품 조립 코드나 공유 계약은 바꾸지 않았습니다. 두 legs 목록은 같은 context/detail에 함께 JSON 직렬화됩니다(`itinerary.py:542`, `departure_context.capture`). 튜플·리스트 검사를 불필요하게 완화하지 않았습니다.

## 최종 실행과 보존

- 최종 로그: `required-fields-after-v2.log` —217 passed in42.51s, 종료0.
- 수정 전 필수키 재현: `required-fields-before-v1.log` —13 failed /3 passed, 종료1.
- 기존217 묶음 실패 보존: `required-fields-after-v1.log` —216 passed /1 failed, 종료1.
- 이전 구조 결함 재현 및 임시폴더 오류 이력은 기존 로그를 그대로 보존했습니다.
- 제품 수정 전 백업: `final_project_cs/app/domains/travel_ops/instances/mobility/engine/_backup/2026-10-11_2341_route_required_fields/departure_observer.py`.
- 기존 시험 수정 전 백업: `final_project_cs/tests/unit/travel/_backup/2026-10-11_2350_departure_context_hook/test_departure_context_storage_v1.py`.
- 제품 추가 차이와 해시: `required-fields-change-v1.diff`, `source-hashes-v2.json`.
- 시험 연결 차이와 해시: `storage-hook-change-v1.diff`, `storage-hook-hashes-v1.json`.

최종 제품 소스 SHA-256: `2a3107ff8e0bc2d6fb1393c8e337677897ea878ed0d2b39fda5237ae572f115d`.

실제 공급자 API·외부 서비스 호출0, 개인 영수증 접근0, 커밋·푸시·배포0입니다. 로컬 제어 표본의 구성요소 연결 시험이며 실제 탑승·결제 및 운영 환경 확인은 안 했습니다. pytest 종료 시 pyreadline3 콘솔 정리의 ignored OSError는 로그에 보존했으며 최종 종료 코드는0입니다. wiki·공개 dated 보고는 상위 통합 작업에서 반영합니다.
