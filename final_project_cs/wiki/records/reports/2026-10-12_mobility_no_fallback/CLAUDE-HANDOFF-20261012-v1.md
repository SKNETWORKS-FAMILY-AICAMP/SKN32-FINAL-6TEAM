# 클로드 인수인계 — 서울 이동 모듈, 2026-10-12

서울 이동 21개 기능의 실제 사용 수준 달성 작업을 이어서 수행하십시오. 직접 도보의 임의 거리 대체와 차량 탐색 결함은 수정했지만, 택시 과소 예측·일부 보행 연결·운영 화면 검증은 남아 있습니다. 아래 수치는 이전 실행 기록이며, 현재 파일과 해시를 다시 확인한 뒤 작업하십시오.

| 할 일 | 확인된 상태 | 진행 |
|---|---|---|
| 직접 도보·추정 관련 선택 시험 | 이전 최종 실행 통과 | 60/60 = 100% |
| 차량 탐색 관련 선택 시험 | 이전 최종 실행 통과 | 58/58 = 100% |
| 카카오 도보 거리 허용 오차 | 742.65m 대 672m, 실패 | 0/1 = 0% |
| 신규 웹 도보 관측 | 출발·도착 3쌍 선정만 완료 | 0/3 = 0% |
| 전체 21개 실사용 완료율 | 일괄 완료 판정 미확정 | 분자 미확정/21, % 산출 보류 |

분모는 선택 시험 수·같은 조건의 웹 대조 수입니다. 시험 통과율을 기능 전체 완료율로 바꾸지 마십시오. 이전에 검증된 개별값을 무시해 모두 0%로 돌리는 것도 금지합니다.

## 1. 가장 먼저 지킬 사용자 지시

1. **하드코딩이나 폴백은 절대 하지 마십시오.** 특정 출발·도착, 영수증, 웹 정답에 맞춘 상수·특례·보정계수를 추가하지 마십시오. 조회 실패를 직선거리·과거 ETA·다른 추정 숫자로 조용히 대체하지 마십시오. 공식 운임표·시간표·도로 제한 같은 근거 있는 입력 자료와 표본 맞춤 보정은 구분하십시오.
2. 사용자는 가능한 검증을 직접 발로 뛰게 하지 말고 네이버·카카오 등 웹 지도와 공식 자료로 수행하라고 요청했습니다. 지하철의 같은 조건 웹 운임·경로를 골든셋으로 사용할 수 있습니다. 실제 관측한 결과만 정답으로 등록하고 URL 준비·검색 요약을 관측으로 세지 마십시오.
3. 출발지·도착지·좌표·시각·요일·서비스 종류·결제 자격·시간 범위를 맞추십시오. 같은 좌표여도 추천 경로가 다르면 경로 차이를 기록하십시오. 웹 예측, 공표 예정값, 실제 탑승·결제는 별도 검증입니다. 개발에 사용한 표본을 독립 검증이라고 부르지 마십시오.
4. 이전 코드와 산출물을 덮어쓰기 직전에 `_backup/<날짜_시각>_<내용>/`으로 복사하십시오. 새로운 보고서·로그·시각화는 새 이름으로 보존하십시오. 다른 작업자의 변경을 되돌리지 마십시오.
5. 이번 인수인계는 커밋·푸시·배포·운영 서비스 종료·결제·팀원 메시지 전송을 승인하지 않습니다. 보고는 한국어 존댓말, 결론 다음 `할 일/상태/진행` 표, `n/m = %`, 파일 링크를 사용하십시오.
6. 기존 wiki의 대체 소스 문구보다 **최신 사용자 지시인 폴백 금지**를 우선하십시오. 근거 없는 숫자를 없애는 것은 필요하지만, 후보를 모두 차단한 상태만으로 제품 완성이라고 보고하지 마십시오. 검증 가능한 실제 데이터와 경로를 확보해 유효한 안내를 복구해야 합니다.

### API 소비 제한

일일 한도 L에서 최소 `ceil(L×0.20)`을 남기고 최대 `floor(L×0.80)`까지만 사용합니다. 기존 설정이 더 엄격하면 더 작은 값을 따릅니다. 공급자·프로젝트·키·엔드포인트별 실제 제한 단위와 갱신 시간대를 먼저 확인하십시오. 같은 키·프로젝트를 사용하는 cs 프로젝트 서버·수집 도구·다른 예약 실행의 누적 사용량을 합산해야 하며, 6시간 실행마다 새 예산을 주지 않습니다.

호출 전 신뢰할 수 있는 공급자 사용량 또는 누락 없는 공유 기록, 이번 요청의 차감 단위, 원자적인 예산 확보가 필요합니다. 실패·재시도·페이지 조회도 보수적으로 차감합니다. 공유 사용량·갱신·예산 확보가 불명확하면 해당 API는 호출하지 마십시오. 월 무료 한도·비용 상한도 별도로 지킵니다. 80% 도달 시 다음 공급자 일일 갱신까지 중단하며 다른 키로 우회하지 않습니다. 비밀값 없이 전후 사용량·잔여량·갱신 시각·이번 호출 수를 기록하십시오. 직전 작업의 제한 개발자 API 호출은 0회입니다.

### 개인 영수증 보호

사용자가 제공한 택시 영수증은 팀원에게 공유되지 않는 별도 위치에 보관하고 결제수단은 ‘삼성’ 정도만 남기도록 마스킹하라는 지시가 있습니다. 이번 인수인계에서는 원본을 열거나 복사하지 않았고 **마스킹 완료·현재 접근권한을 재검증하지 않았습니다.** 필요할 때 기존 비공개 처리 기록부터 확인하십시오. 원본·카드 끝자리·주거지·기사/차량 식별값을 공용 문서·저장소·외부 모델에 보내지 마십시오. 클로드 코드 전송 승인이 개인 영수증 전송 승인으로 확대되는 것은 아닙니다.

## 2. 작업 위치와 읽는 순서

작업 폴더는 `C:/Users/playdata2/Documents/final_workspace`, 실제 제품은 `final_project_cs`입니다. `final_project_sample`은 참고 구현이며 릴리스 검증 근거로 대체하지 마십시오. PowerShell, 기존 Python은 `C:/Users/playdata2/anaconda3/python.exe`입니다.

아래 경로는 작업 폴더 기준이며, 현재 코드·실행 기록이 과거 성과표보다 우선합니다.

1. 루트 `AGENTS.md`, `final_project_cs/AGENTS.md`, `final_project_cs/RULE.md` 및 수정 대상 하위의 작업 규칙.
2. [이동팀 현재 계약](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/teams/mobility.md).
3. [직전 최종 수정 보고서](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/reports/2026-10-12_mobility_no_fallback/REPORT-v2.md).
4. [21기능 상세 검증표](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/reports/2026-10-12_mobility_web21_golden/feature-status-v3.md). 이 표는 직접 도보 폴백 제거 전 결과도 포함하므로 최신 변경 후 재확인하십시오.
5. [직전 파일·입력·산출물 해시](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/reports/2026-10-12_mobility_no_fallback/MANIFEST-final-v1.json). 소스·입력 13개와 산출물 156개의 기준 기록입니다. 새 인수인계 문서는 기존 manifest 대상이 아닙니다.
6. 데이터 작업 전 `datasets/README.md`, `datasets/mobility/REPORT.md`와 해당 데이터셋의 REPORT.

v11은 당시 계획 기록입니다. 현재 사양은 wiki의 후속 확정 결정·계약을 따릅니다. 쇼핑몰 시절 자료를 현재 시험·시연에 재사용하지 마십시오. 작업 폴더에는 다른 작업의 변경이 있으므로 전체 초기화·전체 되돌리기를 하지 마십시오.

## 3. 이번에 실제 바뀐 코드

아래 제품 파일의 공통 위치는 `final_project_cs/app/domains/travel_ops/instances/mobility/`입니다.

### 직접 도보 조회 실패 처리

- `engine/plan.py`의 `Planner._walk_path`: 라우터 부재·장애·불량 응답에서 직선거리×우회계수로 거리·시간을 생성하던 처리를 제거했습니다. `(None, None, True)`와 `source=walking_network/status=unavailable/reason=...` 근거를 반환합니다.
- 실제 연결을 보장하지 못하는 `optimistic=True` 응답도 `unverified_walk_access`로 제외합니다. 유효한 보행망의 계단 시간 처리는 유지했습니다. 실제 `no_path`와 조회 근거 상실을 구분합니다.
- `Planner.leg`는 실패 근거를 전달하며 `walk_source_unavailable`과 `no_walk_path`를 구분합니다.
- `engine/departure_observer.py`: 조회 근거 상실은 `fatal/walk_source_unavailable`, 실제 경로 없음은 재계획 처리입니다. 저장 ETA로 출발 문구를 만들지 않습니다.
- `engine/plan_estimate.py`의 기존 누락 처리 경로를 사용했으며, 직전 작업에서 그 제품 파일을 새로 고친 것은 아닙니다.
- 실제 조립된 `build_departure` 시험 3건에서 조회 실패·접근 미검증·경로 없음일 때 문구가 생성되지 않는 것을 확인했습니다.

**미완료 범위:** 역·정류장 접근의 `_eff`, 연결통로 계수, 별도 환승 도보 추정, 지도 형상의 직선 연결까지 전부 제거한 것은 아닙니다. `plan.py`, `plan_estimate.py`, `verify_time.py`, `route_shape.py`를 확인한 범위의 발견 사항이며 다른 이름·동적 호출까지 전수 감사하지 않았습니다. 실제 호출 경로를 추적해 남은 폴백을 해결하십시오.

### 차량 A* 복수 목표 처리

- `engine/graph_router.py`에서 도착 후보의 요청점까지 거리 차이 ≤12m를 후보끼리 거리 ≤12m로 오해하던 휴리스틱을 고쳤습니다.
- 실제 목표 그래프 끝점까지 거리 하한과 잔여 비용의 합 중 최솟값을 사용합니다. 끝점 1m 이내 잔여비용 0인 기존 경계도 반영했습니다.
- 합성 반례: 수정 전 A* 14.462초 / Dijkstra 11.593초 → 수정 후 11.593초 일치. 실제 주행시간 측정은 아닙니다.
- 특정 도로·정답 맞춤 특례를 추가하지 않았습니다. 현재 `_maxspeed` 상한은 100km/h이므로 소넷의 ‘120km/h 처리’ 지적은 현재 코드의 수정 근거로 채택하지 않았습니다.
- 직전 SHA-256: `9c1ebf89d3b71a5eb292b50de4d9260a0726662e7e8adf9ce1be0def5e8d5bb2`.
- [차량 수정·반례·경계 시험 보고서](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/reports/2026-10-12_mobility_no_fallback/walk-engine/REPORT-durable-v2.md).

간선 길이 반올림·형상 좌표의 척도 차이가 남을 수 있으므로 모든 입력의 엄밀한 최적성을 보장했다고 말하지 마십시오. 계단 비용이라는 기존 보행 목적함수를 정답 거리 맞춤용으로 바꾸지 않았습니다.

## 4. 해결 우선순위와 재현 단서

### 먼저: 남은 폴백을 실제 보행 연결로 교체

남은 접근·환승·지도 연결을 추적하십시오. 실패를 숨기는 상수·직선 연결을 제거하되, 유효한 경로를 실제 출입구·횡단보도·계단·통로 자료로 복구해야 합니다. 그래프를 만들었다는 이유만으로 도로 밖 연결을 검증됐다고 처리하지 마십시오.

현재 웹 거리 실패는 같은 요청 좌표 `(위도37.5665, 경도126.9780)` → `(위도37.56948, 경도126.98222)`입니다. 카카오 최단 672m, 제품 742.65m로 **+10.51%**, 기존 ±10%를 초과합니다. 과거 표의 반올림값 743m/+10.57%와 혼동하지 마십시오.

제품 도로 형상 693.20m + 출발·도착 직선 접근 49.45m입니다. A*와 Dijkstra는 같은 결과여서 차량 휴리스틱 수정으로 해결되지 않았습니다. 카카오 상세는 중간 골목·을지로1길·교량을 안내하지만 원본 경로 좌표는 확보하지 못했습니다. 가까운 계단 way360147780는 최대 연결 성분 밖에 있습니다. 이를 임의 연결하거나 화면 픽셀로 형상을 만들지 마십시오. 을지로1길 자체는 기존 그래프에도 있어 ‘도로 전체 누락’으로 단정하면 안 됩니다.

[도보 진단·선정된 새 OD 3쌍](C:/Users/playdata2/Documents/final_workspace/datasets/mobility/raw/mobility_walk_web_20261012_v2/REPORT-v2.md). 직전 실행은 브라우저 접근이 실패하여 새 관측 0/3입니다. 다음 실행에서는 브라우저 상태와 공개 지도 결과 접근을 다시 확인하십시오. 링크만 있는 3쌍을 수집 완료로 세지 마십시오.

### 다음: 확장 계획 시험 실패 4건 해결

확장 실행은 121/126 성공, 5건 실패, 20개 선택 제외였습니다. 그 뒤 1건의 시험 대역 계약을 수정하고 해당 파일 8/8을 재검증했습니다. 전체 126건을 수정 후 다시 모두 실행한 결과는 아닙니다.

- `test_golden`, `test_golden_all_modes`, `test_reasons_axis`: 이번 직접 도보 수정 전 코드에서도 실패했습니다. 현재 시간표·문구·경로와 기대 결과의 계약을 독립 근거로 대조하십시오.
- `test_walk_m_and_fare`: 이전 성공 → 직접 도보 수정 후 실패. 서울역 예시의 해당 접근이 최대 84.6m이고 `optimistic=true`여서 후보가 제외됩니다. 직선138.69m / 라우터330.3m. 검증 가능한 보행 연결을 확보해야 합니다.
- 이전 정밀 시간표 연결 후 시험 대역에 빠진 `Verifier.ride_of`와 예정도착 메서드를 실제 구현으로 연결했습니다. 제품에 폴백 메서드를 추가한 것이 아닙니다.
- [이전·수정 교대 대조](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/reports/2026-10-12_mobility_no_fallback/plan-fixture-delta-v1.json), [예시 접근 진단](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/reports/2026-10-12_mobility_no_fallback/example-walk-rejection-v1.json).

정답 JSON을 현재 출력으로 덮어쓰거나 차단을 풀어 시험을 초록색으로 만들지 마십시오.

### 다음: 택시 과소 예측과 사전 상품료

실제 서울 영수증 4건 모두 미터요금을 적게 예측했습니다. ±1,000원 기준은 2/4 통과입니다. 브랜드·호출 상품료의 사전 상단을 반영한 예산은 4/4를 커버하지만, 이것이 미터 예측 정확도 해결은 아닙니다. 같은 좌표의 새 웹 견적은 반대로 제품 5,500원 / 웹 4,800원으로 +14.58% 과대입니다.

`engine/car.py`, `engine/taxi_pricing.py`, `engine/taxi_call_policy.py`의 호출 경로와 실제 거리·저속 구간·시간대·상품 조건을 분해하십시오. 실제 요금에서 출발지나 거리를 역산해 맞추지 마십시오. 사용자는 커피빈 출발지를 신촌역 커피빈, 배스킨라빈스는 용산 한남동이라고 설명했습니다. ‘마이미르’는 사용자가 안경점인지 되물었을 뿐 정확한 지점이 확정된 것은 아닙니다. 이미지 3·4는 같은 결제의 중복 화면이므로 별도 표본으로 세지 마십시오. 대구 영수증은 서울 정책 검증으로 섞지 마십시오.

[택시 구조 조사](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/reports/2026-10-12_mobility_no_fallback/taxi-research/REPORT.md)에서 기본요금 소진 단계 누락을 확인했습니다. 현재 계산은 기본시간을 소진하지 않고 전체 저속 시간을 후속 시간요금에 더합니다. 하지만 이것만으로 실제 4건의 과소 예측이 설명된 것은 아닙니다. 서울 미터의 실제 초기 펄스 설정을 확보하지 못했으므로 유도값 366.412초를 실제 설정으로 넣거나 1.6km 미만의 시간요금을 전부 없애지 마십시오. 직전 작업에는 이 부분 제품 패치가 없습니다.

### 이후: 실시간·지도·일정 조정의 실제 제품 연결

첫 탑승·환승 재계산은 선택 열차·생성시각·신선도·운행 종류를 맞춰 확인하십시오. 지도는 백엔드 형상과 웹 모델 시험만 통과한 범위가 있으므로 실제 로컬 개발 서버의 cs 프로젝트 서버 HTTP 응답과 브라우저 지도 SDK 표시를 따로 확인하십시오. 휴대폰 표시를 확인하지 않았으면 그대로 적으십시오. 사건 후 조정은 DB 적용·최신 여행계획서·중복 방지까지 검증하되 외부 메시지 발송을 임의로 하지 마십시오.

## 5. 21개 기능별 인수인계 요약

아래는 기존 보고서의 확인 범위입니다. ‘새로 할 일’은 완전한 결함 목록이 아니라 다음 검증에 필요한 핵심 사항입니다. 각 기능의 코드·정답 링크·오차 기준은 [21기능 상세표](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/reports/2026-10-12_mobility_web21_golden/feature-status-v3.md)에 있습니다.

| 기능 | 기존에 확인한 범위 | 새로 할 일 |
|---|---|---|
| 택시 예상 요금 | 실미터 ±1천원 2/4, 웹 ±10% 0/1 | 거리·저속·기본단계·심야 원인 해결 |
| 택시 예산 여유 | 사전 상품료 상단 예산 4/4 | 새 표본 초과율·저장 왕복 |
| 자동차 시간 | 같은 좌표 웹 ±5분 1/1 | 교통·형상 정렬 표본 확대 |
| 자동차 거리 | 독립 정확도 분모 미확정 | 회전 제한·반올림·접근 분해 |
| 대중교통 전체 시간 | 첫 승차~마지막 하차 ±5분 6/6 | 문앞 전체시간·버스 대기 범위 |
| 지하철 경로 | 정차·서비스 종류 각 6/6 | 다른 경로·운행 예외 |
| 버스 직행·환승 | 혼합 후보 생성3/3, 최종 제공2/3 | 새 OD·다중 환승·접근 |
| 지하철 요금 | 웹6/6, AREX 공식72/72 | 다른 자격·조조·별도요금 조합 |
| 버스·지하철 환승 요금 | 선택경로3/3, 제공옵션2/2 | 다른 OD·환승창·자격 |
| 장소 사이 도보 거리 | 웹 ±10% 0/1 | 현재 실패 원인·연결·새 정답 |
| 도보·역 접근 시간 | 직접 도보 웹 ±5분 1/1 | 접근·계단·환승 폴백 해결 |
| 자전거 경로 | 같은 좌표 후보 제공1/1 | 금지도로·교량 형상 대조 |
| 자전거 시간 | 정확도 분모 미확정 | 순수 주행과 대여·반납 분리 |
| 첫차·막차·출발 시각 | AREX 공표 경계8/8 | 다른 노선·요일·단축운행 |
| 환승·출구·승차 칸 | 같은 혼합 경로 두 필드2/2 | 다른 방향·개방·화면 전파 |
| 실시간 도착 | 관련 시험52/52, 실제 ETA 분모 미확정 | 동일 열차·생성시각·재계산 |
| 혼잡 안내 | 9호선 공표 평균8208/8208 | 현재 열차 혼잡과 구분·표시 |
| 무정차·도로 사고 | TOPIS 사건분류42/42 | 실제 경로 영향·방향·해제지연 |
| 따릉이 대여·반납·재고 | 식별3/3, 관측 재고 재생3/3 | 신선도·재고 변경·거래 범위 |
| 사건 후 일정 자동 조정 | 관련 시험17/17 | DB·계획서 실제 왕복 |
| 지도 경로 표시 | 일반/급행 웹 모델 재생2/2 | 실제 HTTP·SDK·좁은 화면 |

주의: 혼합 3경로는 고유 1OD이며 3OD가 아닙니다. M03은 공통12:09 출발 조건에서 더 이른 출발이 필요해 제외됐습니다. 무조건 포함시켜 3/3을 만들지 마십시오. 공표 평균 혼잡·사건 분류·재고 재생은 현재 특정 열차의 혼잡·사건 탐지율·실제 자전거 대여 거래가 아닙니다.

## 6. 확보 데이터와 API 연결 준비

### OSM 원본

[새 원본 보고서](C:/Users/playdata2/Documents/final_workspace/datasets/mobility/raw/osm_20261012_v1/REPORT.md). 파일 `datasets/mobility/raw/osm_20261012_v1/south-korea-261011.osm.pbf`, 289,058,579바이트, MD5 `df6f9430a975f927c08f4afddade7f97`, SHA-256 `a856bb1e43c968612b2339af0e01da8bb972e10ba21ca86b9d91aac4d1d64505`입니다. 제품 그래프에는 아직 적용하지 않았습니다. 새 버전 그래프를 별도 생성하고 비교한 뒤 적용을 판단하십시오. 단순 다운로드를 정확도 개선으로 세지 마십시오. OSM 출처·ODbL 의무를 유지하십시오.

기존 주변261way의 표적 대조에서261/261 유지·30way 변경·기존 노드 좌표 변경0건이었습니다. 새 무명 도로 전체를 조사한 것은 아니므로 ‘새 원본에도 새 연결 없음’으로 결론 내리지 마십시오.

### 도보 공식 API 후보

[TMAP 키 준비 안내](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/reports/2026-10-12_mobility_no_fallback/api-guide/TMAP-key-preparation-20261012-v1.md). 직전 조사 기준 Free 앱키 1개가 후보입니다. [공식 앱 관리](https://openapi.sk.com/mypage/project/), [보행자 경로 문서](https://tmap-skopenapi.readme.io/reference/보행자-경로안내), [약관](https://tmapapi.tmapmobility.com/terms.html)을 다시 확인하십시오.

직전 공개 기준 경로안내 그룹1,000건/일은 자동차·도보 각각 새로운1,000건이 아닙니다. 실제 계정·공유 사용량 확인 전 호출0회 원칙을 적용하십시오. 응답24시간 이후 재사용 제한을 고려해 영구 저장 정답으로 취급하지 마십시오. `TMAP_APP_KEY`는 안내상의 예정 변수이며 제품에서 읽는 연결은 **아직 구현하지 않았습니다.** 로컬 일부 환경 파일의 변수명 부재 확인을 전체 환경·다른 기계의 키 부재로 일반화하지 마십시오. 키 값은 채팅에 요구하지 마십시오.

[카카오 보행자 API](https://developers.kakaomobility.com/affiliate/walking/start.html)는 직전 조사에서 제휴 승인이 필요했습니다. 기존 일반 REST 키만으로 바로 된다고 안내하지 마십시오. 공개 웹 지도 사용과 개발자 API 호출을 구별하십시오.

## 7. 재검증을 시작하는 방법

새 폴더에 로그를 남기고 먼저 현재 소스 해시와 manifest를 대조하십시오. 아래는 **이어받는 사람이 실행할 제안 명령**이며 이 인수인계 작성 중 다시 실행한 결과가 아닙니다. 파일 선택 범위가 이전과 달라 통과 수가 달라질 수 있습니다. 네트워크·DB·공급자 호출 가능성이 있는 시험은 먼저 fixture와 실행 조건을 읽고 API 예산을 확인하십시오.

```powershell
Set-Location 'C:\Users\playdata2\Documents\final_workspace'
$env:PYTHONPATH = 'final_project_cs'
$mobilityHandoffRun = Join-Path '.tmp' ('mobility_claude_resume_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Path $mobilityHandoffRun -ErrorAction Stop | Out-Null
Get-FileHash -Algorithm SHA256 -LiteralPath 'final_project_cs/app/domains/travel_ops/instances/mobility/engine/graph_router.py'
& 'C:/Users/playdata2/anaconda3/python.exe' -X utf8 -m pytest -q `
  final_project_cs/tests/unit/travel/mobility/test_graph_router_goal_heuristic_v1.py `
  final_project_cs/tests/unit/travel/test_departure_walk_no_fallback_v1.py `
  --junitxml "$mobilityHandoffRun/first-regression.xml" `
  --basetemp "$mobilityHandoffRun/pytest-temp" `
  *> "$mobilityHandoffRun/first-regression.log"
$mobilityHandoffExit = $LASTEXITCODE
Get-Content -LiteralPath "$mobilityHandoffRun/first-regression.log"
Write-Output "pytest_exit=$mobilityHandoffExit"
```

아래 관련 시험 파일을 확인해 필요한 검증 범위를 추가하십시오. 경로는 `final_project_cs` 기준입니다.

- `tests/unit/travel/mobility/test_review_fixes_plan.py`
- `tests/unit/travel/mobility/test_estimate_walk_network_v1.py`
- `tests/unit/travel/mobility/test_departure_walk_v1.py`
- `tests/unit/travel/mobility/test_walk_duration_contract_v1.py`
- `tests/unit/travel/mobility/test_plan_estimate_v1.py`
- `tests/unit/travel/mobility/test_graph_router.py`
- `tests/unit/travel/mobility/test_graph_router_metadata.py`

직전 시험 근거: [도보60개 XML](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/reports/2026-10-12_mobility_no_fallback/final-walk-estimate-v4.xml), [차량57개 XML](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/reports/2026-10-12_mobility_no_fallback/walk-engine/graph-router-final-v3.xml), [차량 경계2개 XML](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/reports/2026-10-12_mobility_no_fallback/walk-engine/goal-boundary-final-v4.xml). 차량57+2 중1개 중복으로58개이며 도보와 합쳐 고유118개입니다. 일부 Windows 로그의 pyreadline3 종료 정리 예외는 시험 본문 이후 발생했고 pytest exit0이었습니다. 새 실패를 같은 문제로 단정하지 마십시오.

mock 서버 시험(화면 반응): 직전 작업에서 안 했습니다.

실서버 확인(서버 응답): 직전 작업에서 x600 서버의 cs 프로젝트 서버 HTTP·DB 확인을 안 했습니다. 휴대폰 지도 SDK도 안 봤습니다. 인수인계 문서 작성 중 새 제품 시험은 실행하지 않았습니다.

## 8. 소넷 검토 이력과 백업

직전 Claude CLI2.1.287에서 실제 `claude-sonnet-5-5`, effort medium으로 검토했습니다. [실제 응답](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/reports/2026-10-12_mobility_no_fallback/claude-walk-result-v3.json), [사용량](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/reports/2026-10-12_mobility_no_fallback/claude-usage-v1.json). 입력2·캐시 생성9,067·재사용1,467·출력12,814토큰(추론9,167 포함), 표시비용$0.1647054, 계정 잔여율 미확인입니다. 일반 도로 탐색 함수8개만 발췌했고 키·환경 파일·개인 영수증은 전송하지 않았습니다. Windows 명령 길이와 제한 환경 DNS 실패 후 승인된 네트워크 실행에서 성공했습니다. 검토 지적은 코드와 일반 반례로 확인한 부분만 채택했습니다.

기존 사용자 코드 전송 승인은 비밀값을 제외한 관련 코드·시험의 제한된 검토에 대한 것입니다. 저장소 통째 전송·비공개 자료·환경 파일·새로운 결제를 승인한 것으로 해석하지 마십시오. 이 문서 작성은 클로드 실행·외부 전송을 수행하지 않습니다.

- [직접 도보 수정 전 백업](C:/Users/playdata2/Documents/final_workspace/final_project_cs/_backup/2026-10-12_163442_walk_no_fallback/).
- [시험 계약 수정 전 백업](C:/Users/playdata2/Documents/final_workspace/final_project_cs/_backup/2026-10-12_165004_estimate_test_contract/).
- [차량 탐색 수정 전 백업](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/reports/2026-10-12_mobility_no_fallback/walk-engine/_backup/2026-10-12_164345_goal_heuristic_fix/).
- [데이터 등록 전 백업](C:/Users/playdata2/Documents/final_workspace/datasets/_backup/2026-10-12_164237_mobility_public_osm_walk/).

## 9. 작업 완료 보고 기준

각 수정마다 원인·일반 수정·같은 조건의 이전/이후 비교·관련 회귀·새 공개 표본·남은 실패·데이터/코드 해시·백업·API 호출 수를 남기십시오. 웹 결과는 관측시각·좌표·경로·서비스 조건·허용 오차를 함께 저장하고 공급자 보존 제한을 지키십시오. 화면과 데이터 경로의 검증 범위를 나눠 보고하십시오.

21개 각각의 제품 경로, 유효한 입력 소스, 허용 오차, 새 표본 근거, 실패 처리, 실제 제공 가능한 안내를 확인하기 전에는 전체100%를 선언하지 마십시오. 검증된 소규모 표본은 해당 분모로 정확히 보고하고, 알 수 없는 전체 완료율은 임의로 만들지 마십시오. 사용자에게 다시 ‘웹으로 가능한데 직접 타고 확인하라’고 넘기지 말고, 독립적으로 확보 가능한 자료부터 최대한 해결하십시오.
