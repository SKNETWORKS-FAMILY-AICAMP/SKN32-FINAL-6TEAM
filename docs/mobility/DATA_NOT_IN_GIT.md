# 이동 모듈 — git 에 올리지 않는 데이터 (DATA_NOT_IN_GIT)

> **팀원은 pull 만 하면 된다** — 판정기 입력 18파일은 저장소 `datasets/mobility/processed/mobility/` 에 있다(9/29). 이 문서는 팀원 할 일 목록이 아니라 「그 18파일이 어디서 어떻게 나왔나 · 저장소에 없는 것은 어디 있나」의 **기록**이다. 재생성은 데이터가 바뀔 때 이동 담당이 한다.

75번 방 · 2026-09-29 · 인벤토리 확인 시각 2026-09-29 12:03(노트북 playdata)
드라이브 위치: `data\travel\` 동기화 폴더(노트북 `C:\final_project\data\travel\` · 집 PC 같은 구조 · 백업 zip `C:\final_project\_backup\`) · 드라이브 zip 이름은 영어로.

합계: `processed\mobility\` 1,697 MB 중 git 후보 148 MB(§DATA_IN_GIT) 를 뺀 **1,549 MB** + `raw\mobility\` **1,710 MB** = 약 3.3 GB 가 git 밖.

## C-1 원자료 (`raw\mobility\` · 1,710 MB · 전부 공공데이터 · 재수집 가능)

| 폴더/파일 | 크기 | 출처 URL | 산출(재생성 스크립트) |
|---|---:|---|---|
| `tago_timetable.jsonl` + `tago_*.json` | 94 MB | 국토교통부 TAGO 지하철 API (data.go.kr · `DATA_GO_KR_KEY`) | `timetable_v1.jsonl` (`collect/tago_subway_collect.py` → `build_timetable_v1.py`) |
| `seoul_timetable_fill/holiday_2_7/branch.jsonl` · `first_last_2to9.json` · `stations_all.json` | 18 MB | 서울 열린데이터광장 OA-101 · OA-15442 (data.seoul.go.kr) | `timetable_v1.jsonl` · `station_coords.json` 역명 (`seoul_metro_collect.py` · `seoul_fill_*.py`) |
| `seoul_bus_all_routes.json` · `seoul_bus_all_stops.json` · `seoul_bus_*.json` | 22 MB | 서울시 버스 정보 API (topis.seoul.go.kr / data.seoul.go.kr) | `bus_route_v1.jsonl` · `bus_stops_v1.jsonl` (`seoul_bus_collect.py` → `build_bus_all_v1.py`) |
| `bus_speed\tpss_route_section_speedh_*.zip` 9 + master csv 2 | 422 MB | 서울 OA-21217 노선별 정류장 구간별 평균 운행시간 (data.seoul.go.kr/dataList/OA-21217) · 원행 8,743,191 | `bus_seg_profile_v1.jsonl.gz` (`build_bus_seg_profile_v1.py`) |
| `서울교통공사_지하철혼잡도정보_20260630.csv` | 0.4 MB | 서울교통공사 · data.go.kr | `congestion_v1.jsonl` (`congestion_build.py`) |
| `congestion_line9\line9_congestion_2020~2026.xlsx` | 57 MB | 서울 OA-22197 / data.go.kr 15112492 (정본 2026 · 나머지 연도 비교용) | `congestion_line9_v1.jsonl` (`congestion_build.py --line9`) |
| `서울교통공사_환승역거리 소요시간 정보_20251231.csv` · `서울교통공사 역간거리 및 소요시간_240810.csv` | <0.1 MB | 서울교통공사 · data.go.kr | `transfer_walk_v1.json` · `line_station_order_v1.json` `distance_m` |
| `전체_도시철도역사정보_20260630.xlsx` | 0.3 MB | 국가철도공단 표준데이터 (data.kric.go.kr) | `station_coords.json` (`station_coords_build.py`) |
| `car_position\molit_fast_transfer_20250923.csv` · `seoulmetro_transfer_20260901.csv` | 0.2 MB | data.go.kr 15151816 · 15098252 | `transfer_car_v1.json` (`build_transfer_car_v1.py`) |
| `bike\*` (master csv · xlsx · bikeList probe · OSM cycleways) | 10 MB | 서울 OA-21235 · OA-15493 · OA-13252 · OSM Overpass | `bike_stations_v1.jsonl` (`build_bike_stations_v1.py`) |
| `osm\south-korea-latest.osm.pbf` (+ md5) · OSM 출구/역 raw json | 275 MB | Geofabrik south-korea-latest (download.geofabrik.de) · OSM Overpass · ODbL | `station_exits_v1.json` · `graph\` (`build_station_exits_v1.py` · `graph\_build\01_geom.py`) |
| `topis\topis_speed_daily_202509~202608.xlsx` 12 + 링크 매핑 xlsx/csv | 465 MB | 서울 TOPIS 교통정보 (topis.seoul.go.kr · 공공누리) | `graph\topis_link_profile_v1.jsonl.gz` · `topis_class_factor_v1.json` (`graph\_build\03a/03b`) |
| `nodelink\NODELINKDATA_20260914.zip` | 259 MB | 국가교통정보센터 표준노드링크 (its.go.kr) | 검토용 — 산출 없음(14번 방 · TOPIS 로 감) |
| `incheon_airport_bus.json` · `tago_bus_*` | 0.2 MB | 인천공항 · TAGO 버스 | `airport_bus_v1.jsonl` (C-3) |
| `walk_courses\*` (둘레길 pdf 21 · TourAPI · 서울시 xlsx) · `walk_pref\SOURCES.md` | 10 MB | 서울둘레길(gil.seoul.go.kr) · TourAPI · 서울 열린데이터 | `walk_pref_v1.json` (C-3 · 30 보류) |
| `bus_pos_obs_*.jsonl` · `kakao_walk_probe.jsonl` | 0.6 MB | 버스 위치 API 관측 · 카카오 탐침(응답 원문 아님 · 요약) | `bus_speed_v1.json` (C-3) |

이유: 크기(zip·xlsx·pbf 1.4 GB) · 재수집 가능 · 산출이 판정기 입력이므로 원자료는 재생성 경로만 있으면 됨. 규칙 24(원문 저장 안 함)에 해당하는 요금 공지·안내도 원문은 애초에 저장하지 않았다.

## C-2 개인 실측 (`processed\mobility\ground_truth\` 7 + `raw\mobility\ground_truth\tmoney_tags_202609.csv` · 합 0.1 MB)

| 파일 | 내용 | 이유 |
|---|---|---|
| `commute_trips_202609.csv`(22) · `r13_field_log_v1.csv`(27) · `field_legs_v1.json` · `taxi_actual_v1.csv`(1) | 본인 출퇴근 실측(앱 예측 vs 문앞 도착) · 택시 실승차 | **개인 이동 기록** — 이름·카드번호·좌표 원값은 없지만(run_id·시각·역명만) 담당자 본인의 일상 동선이라 공개 저장소에 안 올린다. 평가용(28 · `mobility_metrics.py` · `build_field_cases_v1.py`) — 판정기 입력 아님 |
| `tmoney_tags_202609.csv`(raw · 29여정 90태그) | 티머니 태그 기록 | 같은 이유 · 앱 총액 대조용 |
| `bike10_naver_v1.csv` · `car_sample30_naver_v1.csv` · `taxi10_naver_v1.csv` · `ground_truth_v1.csv`(루트 · 20) · `transfer_car_naver_check_v1.csv`(12) | 네이버 지도 수동 대조 표본(숫자만 옮겨 적음) | 아무 코드도 안 읽음 · 검수 기록 · 규칙 24(원문 캡처 저장 안 함 · 숫자만) |

드라이브: `data\travel\processed\mobility\ground_truth\` · `raw\mobility\ground_truth\`(노트북 · 집 PC).

## C-3 아무도 안 읽거나 스크립트만 읽는 산출 (`processed\mobility\` 루트 · 32 MB)

| 파일 | 크기 | 읽는 곳 | 이유 |
|---|---:|---|---|
| `bus_route_v2.jsonl` · `bus_stops_v2.jsonl` · `bus_stop_coords_v2.json` | 21 MB | 없음 | **sha256 이 v1/원본과 동일**(45 재생성 때 생긴 사본) — v1 만 올림. 정본 폴더 정리는 이 방 범위 밖(정본 무변경) |
| `bus_stop_coords.json` | 5.0 MB | `build_bus_all_v1.py` · `seoul_bus_collect.py`(중간 산출) | `bus_stops_v1.jsonl` 에 좌표가 이미 있음 |
| `airport_bus_v1.jsonl`(8,949행 · 180노선) · `airport_bus_stops.jsonl`(170) · `_report.md` | 6.0 MB | `load_mobility_db.py` · `build_airport_bus_v1.py` 만 | 판정기가 안 읽음(공항 리무진은 `bus_route_v1` 공항 유형으로 감) — 후속 방이 쓰면 그때 A 로 |
| `bus_speed_v1.json` · `_report.md` | <0.1 MB | `load_mobility_db.py` · `bus_speed_observe.py` | 41 프로파일로 대체된 표정속도 통계(낙관) |
| `walk_pref_v1.json` | 23.7 KB | 없음(29 · 규칙에 값 800/1,250 m 로 옮김) | 판정기는 규칙 파일을 읽음 |
| `REPORT.md`(44 KB) · `consistency_report.md` · `travel_min_check_report.md` · `airport_bus_v1_report.md` · `bus_speed_v1_report.md` | 0.1 MB | 사람 | 제출 문서(`_backup\` 경유 드라이브 제출) · 저장소 `docs\mobility\` 에는 안 둠(9/28 방침) |
| `budget_probe\budget_legs_measured_v1.json` | 3.8 KB | `budget_probe_measure_v1.py` | 탐침 결과(중간 산출) |

## C-4 그래프 라우터 = 재빌드 (`processed\mobility\graph\gh\` 1,240 MB + `graph\` 나머지 6 MB)

| 파일 | 크기 | 이유 · 재생성 |
|---|---:|---|
| `gh\graph-cache\*` 17파일 | 916 MB | GraphHopper 11.0 빌드 산출(edges 177 · shortcuts_car 302 · geometry 95 …) — `gh\gh_build.ps1` 로 `korea_topis.osm.pbf` + `config-topis.yml` 에서 재빌드(노트북 실측 빌드 시간 `gh\logs\build_times.txt`) |
| `gh\korea_topis.osm.pbf` | 275 MB | `graph\build_topis_pbf.py`(v2 · 정적 속도 주입) 가 `raw\osm\south-korea-latest.osm.pbf` 에서 만듦 |
| `gh\graphhopper-web-11.0.jar` | 45 MB | github.com/graphhopper/graphhopper releases 11.0 |
| `gh\config-topis.yml` · `gh_build.ps1` · `gh\logs\*` | 4 MB | 설정 2개는 작아서 저장소에 둘 수 있음(◆ · 18번 방 문서 참조) · 로그는 안 올림 |
| `graph\topis_link_geom_v1.geojson`(2.9 MB) · `topis_link_geom_v1_len_check.csv` · `topis_osm_match_v1.csv` · `osm_way_topis_link_v1.csv` · `road_test_expected_v1.csv` · `gh_*_result.csv` · `sample10.json` · `step3_result_*.json` · `test_route_teheran_up.json` | 6 MB | 매칭 검수·회귀 기대값·표본 — `car.py` 가 안 읽음(README 표 참조) |
| `graph\_build\*.py` · `build_topis_pbf.py` · `graph_time.py` · `gh_sample_run.py` · 인계 md 2 | 0.1 MB | **스크립트가 데이터 폴더에 있음** — 저장소 `mobility_scripts\` 로 옮기는 건 별도 방(◆ · 재생성 경로라 합의 필요 · 9/29 팀장 답 항목) |

없을 때: `CarGraph.load` 는 5개 파일(A)로 뜨지만 라우터(`MOBILITY_GH_URL`)가 없으면 택시·자동차·자전거 소요는 근거없음 — 회귀 `CAR-*`·`BIKE-*` 는 전체층(`mobility_full`)이고 `allow_router_down` 이라 팀원 게이트엔 영향 없음.

## C-5 판정 로그 · ML 실험 (`logs\` 74 MB · `ml_compare*\` 6 MB)

| 파일 | 크기 | 이유 |
|---|---:|---|
| `logs\judged_log_v1.jsonl`(88,151행) · `regression_fail_dump_*.jsonl` · `DEVICE.txt` | 74 MB | 40번 방 판정 로그 — 노트북 `playdata` 에만 쌓임 · 축적 산출이지 입력이 아님 · 커질수록 git 에 못 올림 |
| `ml_compare\model_hgb.pkl`(2.8 MB) · `ml_compare_v2\model_hgb_v2.pkl` · `summary.json` · `fails_probe_seed0.json` · `fold_results.json` · `report.md` | 6 MB | ML 대조 실험(판정은 코드 유지 · 학습결과서 참조) — pkl 은 재현 스크립트 `eval_ml_compare*.py` 로 다시 만듦 |

## 정본 폴더에 있어도 되는가

정본 `processed\mobility\` 는 이 방에서 **한 파일도 바꾸지 않았다**. 중복 v2 삭제·스크립트 이동·로그 정리는 각각 별도 결정(27 일배정).
