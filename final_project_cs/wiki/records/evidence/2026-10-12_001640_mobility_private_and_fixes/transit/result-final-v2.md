# 출발 재검증 구조 결함 최종 검증

저장 경로 구조 손상으로 출발 안내 회차가 중단되는 결함1건을 수정했고, 관련195개 시험이 모두 통과했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 신규 구조·회복 회귀 | 통과 | 9/9 = 100% |
| 첫 회귀 묶음 | 통과 | 93/93 = 100% |
| 지하철·안내 연결 회귀 | 통과 | 102/102 = 100% |
| 최종 고유 시험 합계 | 통과 | 195/195 = 100% |

첫 회귀93개는 신규9개를 포함합니다. 추가102개와 파일 목록이 겹치지 않아 최종 고유 분모195개입니다. 시험 통과율이며 전체21개 기능의 실사용 완성률이 아닙니다.

## 실행 및 환경 오류 복구

- `route-shape-before-v1.log`: 수정 전8실패·1통과로 재현, 종료1.
- `route-shape-after-v1.log`: 수정 후93통과, 종료0, 건너뜀0.
- `subway-notice-integration-v1.log`:100통과·2오류. 둘 다 pytest 공용 임시폴더 생성 실패이며 로그를 보존했습니다.
- `subway-notice-integration-v2.log`: 기존 경로 부재를 확인하고 작업별 신규 `--basetemp`를 지정하여 같은102개를 재실행,102통과·종료0·건너뜀0.
- 추가 묶음 명령: `python -m pytest tests/unit/travel/mobility/test_subway_departure_v1.py tests/unit/travel/mobility/test_subway_primary_name_v1.py tests/unit/travel/mobility/test_departure_express_basis_v1.py tests/unit/travel/mobility/test_departure_publish_basis_v1.py tests/unit/travel/test_departure_observer_notice_v1.py tests/unit/travel/test_departure_assembly_v1.py --basetemp ../.tmp/mobility_finish_20261011/transit/pytest_subway_v2_233123 -q`.

수정·원인·백업·확인 범위는 `result-v1.md`, SHA-256은 `source-hashes-v1.json`, 수정1곳의 차이는 `source-change-v1.diff`에 있습니다. 기존 접근시간43케이스 결함과 별개입니다. 저장 경로가 비어 있지 않은 list이고 각 구간이 dict인지 도착정보 조회 전에 확인합니다.

실제 공급자 API·외부 서비스 호출0, 사용자 개인 영수증 접근0, 커밋·푸시·배포0. 실제 탑승·결제 및 운영 환경 확인은 안 했습니다. 종료 시 pyreadline3 콘솔 정리의 ignored OSError는 로그에 보존했고, 최종 두 묶음 종료 코드는0입니다.
