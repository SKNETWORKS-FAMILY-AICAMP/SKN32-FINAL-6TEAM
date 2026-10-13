# 출발 재검증 저장 경로 구조 결함 수정

저장된 이동 경로가 손상됐을 때 출발 안내 회차가 예외로 중단되는 결함을 수정했습니다. 정상 경로의 실시간 첫 승차와 후속 버스 재계산은 유지합니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 별도 구조 결함 재현 | 완료 | 8/8 실패 재현 = 100% |
| 신규 회귀 | 통과 | 9/9 = 100% |
| 첫 회귀 묶음 | 통과 | 93/93 = 100% |

## 원인과 수정

`legs`와 `check.legs`가 같다는 검사만 있어 둘 다 같은 dict·문자열·정수·비매핑 구간 목록이면 통과했습니다. 이후 첫 구간 조회에서 KeyError/AttributeError/TypeError가 나거나 손상 뒷구간을 확인하기 전에 공급자 도착정보를 조회했습니다. 대중교통 경로를 비어 있지 않은 list, 각 구간을 dict로 조회 전에 검증하여 기존 `needs_replan/route_check_missing_or_changed`로 반환합니다. 손상 값을 정상 경로로 바꾸지 않습니다.

코드 변경은 `departure_observer.py`의 검사 조건 한 곳입니다. 신규 `test_departure_route_structure_v1.py`는 손상 첫 구간·뒷 구간의 조회 및 판정 금지, 안내 보류 뒤 정상 안내 회복, 현재 첫 승차와 후속 버스 재계산을 검증합니다.

## 실행 근거

- 수정 전: `route-shape-before-v1.log`, 8 failed / 1 passed, 종료 코드1.
- 수정 후: `route-shape-after-v1.log`, 93 passed, 종료 코드0, 건너뜀0.
- 첫 회귀 명령: `python -m pytest tests/unit/travel/mobility/test_departure_route_structure_v1.py tests/unit/travel/mobility/test_departure_observer_v1.py tests/unit/travel/mobility/test_departure_source_to_notice_v1.py tests/unit/travel/mobility/test_departure_access_bounds_v1.py tests/unit/travel/test_departure_boarding_guidance_v1.py -q`.
- 지하철·안내 추가 묶음은 `subway-notice-integration-v1.log`에 별도 보존하며 결과 확정 후 상위 보고에 기록합니다.
- 원본 백업: `final_project_cs/app/domains/travel_ops/instances/mobility/engine/_backup/2026-10-11_2326_route_structure/departure_observer.py`.
- 수정 전후 SHA-256: `source-hashes-v1.json`, 최소 차이: `source-change-v1.diff`.

## 확인 범위

로컬 제어 표본의 구성요소 연결 시험입니다. 실제 공급자 API·외부 서비스 호출0, 사용자 개인 영수증 접근0, 커밋·푸시·배포0입니다. 실제 탑승·결제 및 운영 환경 확인으로 부르지 않습니다. 기존 접근 시간 범위43케이스 수정과 별도 결함입니다. pytest 종료 시 pyreadline3 콘솔 정리의 ignored OSError가 남았지만 첫 회귀 종료 코드는0입니다.
