# 활동 후보를 영업시간 확인 전에 자르는 문제

## 해결됨 (2026-10-10, 부분) — 로컬 코드·회귀 시험 완료, ARM 반영 대기

[실측] Oracle ARM의 빈 기준 DB에 기존 여행 사실 자료를 트랜잭션으로 시험 적재한 뒤, 외부 API 없이 활동 후보와 운영시간 연결을 확인했다. 시험 자료는 롤백했다.

경복궁 주변 3km에서 가까운 활동 10곳은 운영시간이 있는 곳 0/10이며, 같은 반경에서 100곳을 읽으면 30/100이었다. 광장시장 주변은 1/10·11/100, 남산 주변은 5/10·35/100이다. 이는 정확도 평가가 아니라 후보 데이터 보유 범위다.

원인: `nearby_activities`가 먼저 가까운 10곳을 자른 뒤 `widen_activity_pool`이 영업시간 없는 곳을 제외한다. 실제 데이터에 시간 정보가 있는 곳이 있어도 처음 10곳 밖이면 추천에 들어오지 않는다.

수정 범위: 활동 후보 확대 경로에서만 DB의 운영시간 보유 조건을 먼저 적용하고, 그 뒤 가까운 후보 개수를 제한한다. 검색 요청의 외부 호출 금지와 여행별 장소 격리는 유지한다. 시간 미보유 장소를 영업 중으로 만들지 않는다.

검증 대기: 앞의 10곳은 시간이 없고 11번째 후보에만 시간이 있는 별도 여행 자료로 회귀 시험한다. 수정 적용 위치와 실제 ARM 운영 반영 여부를 최종 리포트에 구분한다.

[실측] 로컬에서 운영시간 보유 조건을 후보 개수 제한 전에 적용했다. `python -m pytest tests/integration/travel/test_activity_catalog_pool.py tests/integration/travel/test_activity_hours_before_limit.py -q` 7/7 통과이며, 변경 전 코드로 새 회귀 시험을 돌리면 1/1 실패한다. 첫 10곳 밖의 시간 보유 미술관 선택과 요청 중 외부 호출 불변을 확인했다. [코드](../../../../app/domains/travel_ops/components/places/catalog_pool.py) · [새 회귀 시험](../../../../tests/integration/travel/test_activity_hours_before_limit.py) · [복구 리포트](../2026-10-10_0535_arm-place-source-recovery.md). ARM 코드 반영은 아직 하지 않았다.
