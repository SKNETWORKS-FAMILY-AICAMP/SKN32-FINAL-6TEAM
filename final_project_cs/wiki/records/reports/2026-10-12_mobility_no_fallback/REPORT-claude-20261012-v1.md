# 이동 모듈 이어받기 — 웹 도보 관측 · 그래프 v3 시험 · 시험 대역 정리 (Claude, 2026-10-12 밤)

[인계 문서](CLAUDE-HANDOFF-20261012-v1.md)를 이어받아 첫 우선순위(남은 도보 연결)를 진행했습니다. 제품 코드(`app/`)는 바꾸지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 기준 해시·첫 회귀 재확인 | 일치 · 통과 | 소스 13/13 = 100% · 회귀 5/5 = 100% |
| 카카오 웹 같은 좌표 도보 관측 | 관측 | 4/4 OD = 100% (새 좌표 W02~W04 3/3) |
| 제품 ±10% 안 | 실패 다수 | 1/4 = 25% (W04 만, 조건이 다름) |
| 보행 광장 그래프 v3 시험 | 만들고 비교 · **채택 안 함** | 개선 0/4 |
| 시험 대역 실패 정리 | 끝 | 14/14 = 100% |
| 관련 시험 재실행 | 통과 | 172/172 = 100% |
| 예시 일정 골든 시험 4건(`test_plan_v1`) | 미해결 | 0/4 = 0% |
| 지도 개발자 API 호출 | 안 함 | 0회 |

## 1. 웹 관측 — 4쌍 모두 제품이 더 길다

관측 자료: [datasets/mobility/raw/mobility_walk_web_20261012_v3/](../../../../../datasets/mobility/raw/mobility_walk_web_20261012_v3/REPORT.md) (카카오 공개 웹 화면이 받은 응답을 옮겨 적음 · API 0회).

| ID | 카카오 최단 | 제품(v2 그래프) | 차이 |
|---|---|---|---|
| W01 | 672 m | 742.65 m | +10.51% |
| W02 | 432 m | 592.23 m | +37.09% |
| W03 | 516 m | 590.19 m | +14.38% |
| W04 | 580 m | 628.22 m | +8.31% (카카오 출발이 역사 안 — 조건 다름) |

- 카카오 총거리 = 길 위 경로 + 양 끝 요청점 접근 직선(4쌍 모두 1 m 안에서 맞음). 제품과 같은 정의다 → 차이는 **정의 차이가 아니라 경로 차이**.
- WCONG→위경도 변환 교차 검증 오차 0.20~0.50 m.
- 분석: [walk-web-analysis-v2graph.json](claude-walk-web-v1/walk-web-analysis-v2graph.json) · 그림 [kakao-vs-product-v2graph.png](claude-walk-web-v1/kakao-vs-product-v2graph.png).

## 2. 어디서 갈라지나 — 카카오 경로 띠(±10 m) 안 그래프 연결 검사

[corridor-breaks-v2graph.json](claude-walk-web-v1/corridor-breaks-v2graph.json) · OSM 원자료 태그 [osm-probe-graphsrc-v1.json](claude-walk-web-v1/osm-probe-graphsrc-v1.json)(그래프 원본 pbf md5 70860ce7…).

- W02: 카카오 마지막 골목(약 39 m 북쪽)이 그래프에 없다. 가까운 OSM 길은 서비스 골목뿐.
- W03: 탑골공원 서문 보행로 way 306381845(6.8 m)가 막다른 토막(끝점 연결 1). 그 너머 공원 안마당은 OSM 에서 `highway=pedestrian, area=yes` 면이다. 돈화문로11길 건널목 자리는 그래프상 터널 구간(way 1013396417, layer −1).
- W01: 청계천 보행교(way 656122968)는 그래프에 있으나 을지로1길 북쪽 일부가 카카오 선형과 10 m 넘게 떨어진다. 출발점은 서울광장 안.

## 3. 그래프 v3(보행 광장 면 연결) — 만들었지만 채택하지 않음

- 생성기 [build_road_graph_v3.py](../../../../../datasets/mobility/scripts/build_road_graph_v3.py) (v2 생성기·v2 그래프는 그대로). 같은 원본 pbf. 메모리 부족(다른 세션 시험이 3.4GB 사용)으로 행정 경계는 v2 저장본을 재사용(`--region-from`).
- 규칙: 닫힌 way 광장 1,383곳 둘레 + 입구끼리 **면 안에만 있고 건물을 뚫지 않는** 직선(18,779개 · 건물 관통 거절 107 · 면 밖 거절 30,172). 다각형 relation 광장 376곳은 미처리.
- 결과([walk-web-analysis-v3graph.json](claude-walk-web-v1/walk-web-analysis-v3graph.json) · [그림](claude-walk-web-v1/kakao-vs-product-v3graph.png)): W01 +10.51% → **+20.70%(악화)**, W02·W03·W04 변화 없음.
  - W01 악화 원인: 도착점 근처에 새 간선이 생기자 「가장 가까운 간선 하나에만 붙이는」 걸음 규칙 때문에 연결이 나쁜 쪽에 붙었다.
  - W03 무변화 원인: 서문 보행로 끝점이 광장 테두리와 **같은 OSM 점이 아니다**(가깝기만 함). 잇는 것은 임의 연결이라 하지 않았다.
- 판단: 이 4쌍에서 이득이 없고 1쌍은 나빠져 **제품에 연결하지 않는다**. 산출물 `datasets/mobility/processed/mobility/road_graph_v3/`(git 밖)은 비교 근거로 남긴다. v3 에는 자동차 회전 제한 표(turn_restrictions_v1.json)가 없다.

## 4. 시험 대역 정리 — 14건

기준선(이동 모듈 전체): 1,498 통과 · 18 실패 · 4 오류(오류 4는 메모리 부족, 단독 실행에서 통과) — [baseline-full-mobility.log](claude-walk-web-v1/baseline-full-mobility.log).
폴백 제거 전 코드(백업)를 임시 사본에 덮어 같은 시험을 돌려 가렸다.

| 묶음 | 원인 | 고친 것 |
|---|---|---|
| 도보 폴백 제거로 새로 깨짐 4건(자전거 2 · 최단출발 2) | 보행망 없이 직선×계수로 도보를 만들던 옛 동작에 기댐 | 시험에 **검증된 합성 보행망**을 명시적으로 단다 + 도보 값이 보행망 응답 그대로인지 단언 추가. 제품은 그대로 |
| 원래 있던 10건(자전거 5 · 지도 형상 4 · 버스 1) | 시험용 가짜 객체에 진짜 판정기·생성기의 새 계약이 빠짐(`label` · `ride_of` · `regular_alternative`) | 진짜 구현을 그대로 붙이거나 진짜와 같은 형식으로 맞춤 |

백업: [final_project_cs/_backup/2026-10-12_2230_walknet_test_doubles/](../../../../_backup/2026-10-12_2230_walknet_test_doubles/).
재실행: [final-regression-v1.xml](claude-walk-web-v1/final-regression-v1.xml) — 172/172 통과(인계 지정 파일 + 고친 파일 + 정밀 시간표).

| 파일 | SHA-256 |
|---|---|
| tests/…/test_plan_bike_v1.py | 95ed6e7c1b3f3691ac63986200d95ca6104dab5c0114c35f6c243436098261c1 |
| tests/…/test_earliest_v1.py | 1d0e797ae1052d5d3a6f0af4e7607f0beaf1b5cea37e34e61ac5f1c7e1546b81 |
| tests/…/test_route_shape_context_v1.py | ce087867a8b958de6b987464a8585a249fafb6c2547a38f06a1ab11c83f4b454 |
| tests/…/test_bus_only_planner_candidates.py | 0281a2ee0bcdb1c618d2561b4a55458086e78fe8cdd51b9046db313c1670d727 |
| datasets/mobility/scripts/build_road_graph_v3.py | dd7cf5df9eb8a6589d2be89598358b847c6f616f50305692abe5796b8af97785 |
| app/…/engine/plan.py (안 바꿈) | 52097f61bb5c8c43844ff201ae57656145fb8e2fb8f13fb93ce6b4cf5c6b01fd |
| app/…/engine/graph_router.py (안 바꿈) | 9c1ebf89d3b71a5eb292b50de4d9260a0726662e7e8adf9ce1be0def5e8d5bb2 |

## 5. 남은 것

1. **보행 자료 원천** — 남은 차이의 큰 몫은 OSM 보행 자료의 빈틈(골목 없음 · 입구가 이어지지 않음)이다. 서울 열린데이터광장 「서울시 자치구별 도보 네트워크 공간정보」(OA-21208 · 노드·링크 · 횡단보도·육교·지하철 출입구 포함 · 2020년 기준 · 공공누리 1유형)가 후보. 내려받기는 사용자 승인 필요.
2. **남은 직선×계수 계산**(코드 위치 확인, 미수정): 역·정류장 접근 `plan._eff`(라우터 없음·길 없음·낙관이면 직선, 서버형 라우터면 항상 직선) · 연결통로 `CONNECTOR_FACTOR_PROPOSED` · 정류장↔역·버스↔버스 환승(`verify_time._stop_station_walk` · `_bus_bus_walk`) · 따릉이 대여소 도보(`_bike_walk`) · 혼합 후보 연결 도보. 실제 보행 자료가 생기기 전에 끊으면 대중교통 후보 대부분이 사라진다 — 자료 확보와 함께 바꾼다.
3. `test_plan_v1` 4건 — 서울역 예시 도보가 낙관 접근(84.6 m)으로 빠지는 것(3건)과, 경복궁→성수 두 번째 후보가 12:41 출발에서 불성립이라 후보가 하나만 남는 것(1건). 골든을 덮지 않았다. 두 번째는 공식 시간표로 독립 대조가 필요하다.
4. 택시 과소 예측 · 실시간·지도 실제 화면 확인은 손대지 못했다.

mock 서버 시험(화면 반응): 안 했음.
실서버 확인(서버 응답): 안 했음 — x600 서버의 cs 프로젝트 서버 · 로컬 개발 서버 HTTP 모두 확인 안 함.
