# 이동 모듈 — git 에 올리는 데이터 (DATA_IN_GIT v1)

75번 방 · 2026-09-29 · 인벤토리 확인 시각 **2026-09-29 12:03 (노트북 playdata)** · 줄인 판 생성 12:05
정본 `C:\final_project\data\travel\processed\mobility\` (무변경) → 줄인 판 **저장소 `datasets/mobility/processed/mobility/`**(9/29 재개 · 팀장 폴더 배정)

> **팀장 답(9/29 · 본인 전언)** — ⓑ 폴더 = **`datasets/mobility/processed/`**(팀장이 만든 팀별 데이터셋 폴더 · 커밋 `4f6297e`) · 「서버가 뜰 때까지 임시 · develop 까지 올려라」.
> 팀 `.gitignore` 는 `datasets/**/processed/**` 를 막지만 손대지 않고 **`git add -f`** 로 추적한다(폴더 README 「이동 팀 예외」 절 · 전부 공공데이터 · 개인정보 0).
> ⓒ `.gz` 는 안 씀 — 시간표 텍스트 75.1 MB 그대로(GitHub 경고선 50 MB 는 넘고 거부선 100 MB 는 아래 · 판정기 `open()` · gz 전환은 78 ⑦ loader 뒤).
> ⓐ 상한은 묻지 않음 — 우리 기준 파일당 100 MB 아래 · 총 148 MB.

## 0. 요약

검증(9/29 재개 · 노트북 · 팀장 판 `c45593a` 위): 줄인 판을 `DATA_DIR` 로 잡고 회귀 게이트·전체층·CLI 171 을 돌려 정본과 같은 값 — 결과는 §7.

| | 값 |
|---|---|
| `processed\mobility\` 전체 | **1,697 MB** · 88파일(`graph\gh` 그래프 캐시 1,240 MB 포함) |
| 판정기·plan 이 읽는 파일 | **18파일 = 13종 + graph 5** (+ 저장소 안 규칙 2: `rules_v0.3.json` · `holidays_2026_2027.json`) |
| 그 18파일 정본 크기 | **261.0 MB** |
| 줄인 판(텍스트) | **148.0 MB** — 시간표 188.1 → 75.1 MB(8열만) · 나머지 그대로 |
| 50 MB 넘는 파일 | **시간표 하나**(75.1 MB) → `.gz` 옆에 생성 **1.8 MB** |
| git 총합 | `.gz` 쓰면 **74.7 MB** / 텍스트로 두면 148.0 MB(시간표 75 MB 가 경고선 초과) |
| 행 삭제 | **0** (시간표 463,326행 그대로 · 출발없음 18,411행은 후보 — 73 회귀 뒤) |
| 중복으로 확인된 파일(sha256 동일) | `bus_route_v2 = v1` · `bus_stops_v2 = v1` · `bus_stop_coords_v2 = bus_stop_coords` → v1 만 올림 |

## 1. 누가 무엇을 읽나 (grep 근거 · 엔진 `app/modules/travel_ops/mobility/engine/`)

파일 경로의 정본은 `runtime.py default_paths()` L47~62 와 `verify_time.py build_verifier_for_cases()` L2466~2478. 둘 다 `paths.PROCESSED / "mobility"` 아래 같은 이름.

| 파일 | 읽는 코드 | 없으면 |
|---|---|---|
| `timetable_v1.jsonl` | `verify_time.Timetable.load` | RuntimeError(필수) |
| `timetable_v1_meta.json` | `runtime.py`(built_at) | 행의 `fetched_at` 로 대신 |
| `line_station_order_v1.json` | `line_order.LineOrder` · `candidates` | 필수 |
| `transfer_walk_v1.json` | `transfer_walk.TransferWalk` | 필수(코드상 None 허용이나 runtime 이 막음) |
| `bus_route_v1.jsonl` · `bus_stops_v1.jsonl` | `bus.BusRoutes` · `geo` | 필수 |
| `station_coords.json` | `geo.StationCoords` | 필수 |
| `station_exits_v1.json` | `exits.StationExits` | 역 좌표로 대신(경고) |
| `bike_stations_v1.jsonl` | `bike.BikeStations` | 자전거 근거없음 |
| `bus_seg_profile_v1.jsonl.gz` | `bus_profile.BusSegProfile`(gzip) | 표정속도 모델 |
| `congestion_v1.jsonl` · `congestion_line9_v1.jsonl` | `congestion.Congestion` | 가산 없음(근거없음) |
| `transfer_car_v1.json` | `options.TransferCar`(display off · ◆칸) | None |
| `graph/topis_class_factor_v1.json` `topis_link_profile_v1.jsonl.gz` `osm_way_seg_topis_link_v1.csv` `osm_way_geom_v1.csv` `daytype_calendar_v1.csv` | `car.CarGraph`(택시·자동차 · 라우터 GraphHopper 는 별도 · C) | 택시·자동차 근거없음 |

시험: `tests/unit/travel/mobility/test_regression_cases.py` 는 위 경로를 `paths.PROCESSED` 로 읽고 없으면 `skip("data not present")`. `plan.py`·`plan_estimate.py` 는 `runtime.build_verifier()` 를 거쳐 같은 파일을 읽는다(직접 여는 파일 없음 · `holidays` 만 규칙 폴더).

## 2. 분류 A(그대로) · B(줄여서) — 파일별 문서

공통: 경로 = 정본 `processed\mobility\<파일>` → git `datasets/mobility/processed/mobility/<파일>`(`mobility/` 하위는 엔진 경로 규칙 `PROCESSED / "mobility"` 때문). 재생성 스크립트는 `mobility_scripts/collect/…`(저장소 루트 `mobility_scripts/`). 갱신법은 「원자료 다시 받기 → 스크립트 → 정본에 쓰기 → `reduce_75.py` 로 줄인 판 → MANIFEST 갱신 → 회귀 171」. 등급은 파일 안 `grade` 칸·`_report.md` 기준.

### B-1 `timetable_v1.jsonl` — 지하철 시간표 (유일하게 줄인 파일)

| | |
|---|---|
| 행수 | **463,326**(전/후 같음) · 판정에 오르는 행 444,915 · 출발없음(`dep_time` null) 18,411 |
| 크기 | **188.1 MB → 75.1 MB** (`.gz` 1.8 MB) |
| 열(정본 20) → 남긴 열 **8** | `line`(노선 24종 `01호선`…) · `station_nm`(역명) · `day_type`(`weekday`/`saturday`/`holiday`) · `dep_time`(`HH:MM:SS` · 24시 넘김 유지 · null=출발없음) · `dir`(`U`/`D` 참고용) · `dest_nm`(행선지 — 방향의 정본) · `dest_inferred`(`chain_v1` 20,548행 = 28번 방이 채운 값 · 판정 등급 추정) · `fetched_at`(`2026-09-09` TAGO / `2026-09-11` 서울 · evidence `observed_at`) |
| 뺀 열 12 | `station_key` `station_cd` `station_nm_en` `arr_time` `orig_nm` `train_no` `express` `source` `source_station_id` `fetched_at_precision` `dest_basis` `dest_hops` — **판정기가 읽지 않음**(`verify_time.py` L140~151: `r.get("line")` `station_nm` `fetched_at` `dep_time` `day_type` `dir` `dest_nm` `dest_inferred` 8개뿐 · 그 밖의 `r.get(` 없음 · `Dep` dataclass 4칸) |
| 한 행(줄인 판) | `{"line":"01호선","station_nm":"가능","day_type":"weekday","dep_time":"06:58:00","dir":"U","dest_nm":"동두천","dest_inferred":null,"fetched_at":"2026-09-09"}` |
| 원자료 | 서울 열린데이터광장 OA-101(`raw\mobility\seoul_timetable_*.jsonl` · 39,430행) + 국토부 TAGO(`tago_timetable.jsonl` 93.5 MB · 423,896행) |
| 생성 | `collect/build_timetable_v1.py`(9/12 판 · 중복 2,392+2,646 제거) → `collect/fill_timetable_dest_v1.py`(28 · 행선지 빈칸 채움 · 판 하나) |
| 등급 | 시각 확정 · 행선지 확정(원천) / **추정**(`dest_inferred=chain_v1`) · 근거없음(`dest_nm` null 5,872행) |
| 갱신 | 위 두 스크립트 재실행 → `timetable_v1_meta.json` 같이 갱신 → 회귀 171 기대값 재확인 |
| 줄인 방법 | `reduce_75.py reduce_timetable()` — 행 순서·행수 그대로 · 8열만 · `separators=(",",":")` · `ensure_ascii=False` · 줄 끝 `\n` |
| 검증(73 뒤 · 필수) | 줄인 판을 `DATA_DIR` 에 놓고 회귀 171 · pytest 133 이 같은 값 — **열을 뺐으므로 반드시** |

### A `timetable_v1_meta.json` · 7.4 KB
시간표 판 메타(`built_at 2026-09-12T20:38:16+09:00` · 원 행수 · 중복 제거 수 · 소스별 행수 · `cross_source_conflicts_kept` 18 · `gaps` 24노선). `runtime.py` 가 `built_at` 만 읽어 판정 이력 `timetable_built_at` 에 남긴다. 생성 `build_timetable_v1.py`. 등급 —.

### A `line_station_order_v1.json` · 761.6 KB
`lines`(24노선) → `stations[]`(`station_nm` `station_key` `station_cd` `fr_code` `fr_order` `is_spur` `has_timetable`) · `edges[]`(`a` `b` `travel_min` `travel_min_source` `travel_min_grade` `distance_m` `grade`) · `dir_label.reliable` · `is_loop` · `direction` · `dest_alias`. 777간선 · 793역 · 간선 등급 확정 636 / 추정 97 / 근거없음 44. 원자료 국가철도공단 FR_CODE + 시간표 관측 + 서울교통공사 역간거리 CSV(54 · 270간선 `distance_m`). 생성 `collect/build_line_station_order_v1.py`. 한 항목: `{"a":"소요산","b":"청산","travel_min":3,"grade":"확정",…}`.

### A `transfer_walk_v1.json` · 58.0 KB
`pairs`(213 · 키 `역|노선|노선` · `distance_m` `walk_min` `src_min`) · `stations`(74 · 역별 최장) · `grade{distance_m:확정, walk_min:추정(1.04 m/s)}` · `license 공공누리 1`. 원자료 `서울교통공사_환승역거리 소요시간 정보_20251231.csv`. 생성 `collect/build_transfer_walk_v1.py`. 한 항목 `{"station_nm":"서울역","from_line":"01호선","to_line":"04호선","distance_m":159.0,"walk_min":2.5,"src_min":2.2,"src_speed_mps":1.2}`.

### A `bus_route_v1.jsonl` · 470.0 KB · 717행
열 24: `route_id` `route_nm` `route_type`(1~15) `route_type_nm`(간선·지선·마을·심야·공항·광역·순환·투어) `route_type_grade` `corp_nm` `st/ed_station_nm` `length_km` `term_min`(배차 · 6 null) `first_time` `last_time`(24시 넘김 유지) `crosses_midnight` `grade_service_window`(확정/추정/근거없음) `grade_wait` `window_note` `time_base_date`(2026-09-10) `service_days`(716 daily) `service_days_grade` `service_days_basis` `source` `source_id` `fetched_at` `fetched_at_precision`. `bus.py` 는 행 전체를 `Route(..., r)` 로 보관하므로 **열 제거 안 함**. 원자료 서울시 버스 API(`raw\mobility\seoul_bus_all_routes.json`). 생성 `collect/build_bus_all_v1.py`(45 재생성 · `normalize_window`). 등급 첫차·막차 확정 · 배차 추정.

### A `bus_stops_v1.jsonl` · 15.6 MB · 41,820행
열 15: `route_id` `route_nm` `seq` `station_id` `ars_id` `station_nm` `lat` `lng` `direction` `sect_dist_m` `transfer_yn` `source` `source_id` `fetched_at` `fetched_at_precision`. `bus.py` 는 행 dict 를 그대로 `stops[route_id]` 에 넣고 `seq`·`station_nm`·`lat`·`lng`·`sect_dist_m`·`station_id` 를 쓴다(bus_profile 도 `station_id`·`seq`) — 50 MB 아래라 **그대로**. 원자료 `seoul_bus_all_stops.json`(19.7 MB). 생성 `build_bus_all_v1.py`. 등급 확정(좌표 · 순서).

### A `station_coords.json` · 528.2 KB
`stations`(793 · 키 **노선|역명** · `lat` `lng` `station_nm_en` `station_cd` `operator` `coord_source` `coord_join` `name_source` `fetched_at 2026-06-25`) + `source` `src_file` `data_basis_date` `built_at 2026-09-27` `count`. 좌표 없는 역 6(신길온천·GTX-A 3·서해구청). 원자료 국가철도공단 `전체_도시철도역사정보_20260630.xlsx` + OA-15442 `stations_all.json` + 보정표 `config/mobility/station_coord_fix.json`(저장소). 생성 `collect/station_coords_build.py`(57). 등급 확정(표준데이터) · 영문명 보정 39역.

### A `station_exits_v1.json` · 804.8 KB
`exits`(645역명 → `[{osm_id lat lng ref desc desc_en wheelchair attrib dist_to_station_m}]`) · `grade 추정`(OSM 비공식 · 커버 99.4%) · `license ODbL` · `radius_m 300` · `built_at 2026-09-27`. 원자료 OSM Overpass `raw\mobility\osm\osm_subway_entrances_sudogwon_raw.json`. 생성 `collect/build_station_exits_v1.py`.

### A `bike_stations_v1.jsonl` · 800.4 KB · 2,734행
열 11: `stationId` `no` `name` `lat` `lon` `rack` `mode`(QR/LCD) `gu` `checked_at 2026-09-19T21:55` `source_id` `grade{position:확정, mode:추정|근거없음}`. 실시간 거치 수는 없음(판정 시 `bikeList` 조회). 원자료 서울 OA-21235/15493/13252(`raw\mobility\bike\`). 생성 `collect/build_bike_stations_v1.py`.

### A `bus_seg_profile_v1.jsonl.gz` · 9.2 MB · 40,776행 + `_meta` 1행 (정본이 gz)
열 9: `route_id` `route_nm` `from_id` `to_id` `from_seq` `to_seq` `dist_m` `weekday{n[24] p10[24] p50[24] p90[24]}` `holiday{…}`. 717노선 · 구간 40,776/41,103 · 100일(2026-06-01~09-13). `bus_profile.py` 가 gzip 으로 읽는다(이미 gz — 이 파일은 `.gz` 그대로 올린다). 원자료 서울 OA-21217 zip 9(`raw\mobility\bus_speed\` 422 MB · 원행 8,743,191). 생성 `collect/build_bus_seg_profile_v1.py`(41). 등급 확정(5일 이상 관측 셀 1,457,091) · 1~4일 셀 18,130.

### A `congestion_v1.jsonl` · 32.2 MB · 65,169행
열 20: `station_key` `station_cd` `station_nm` `station_nm_en` `line`(1~8호선) `branch` `src_station_nm` `src_station_cd` `dir` `dir_raw` `day_type`(weekday/saturday/sunday) `slot`(30분 39칸) `congestion`(% · null 3,693=근거없음) `grade` `reason`(after_last_train 2,028 · terminus_direction 1,599 · no_train_in_window 66) `source*` `data_basis_date 2026-06-30` `fetched_at`. `congestion.py` 는 행을 통째로 `by_key` 에 두고 `lookup` 이 행을 돌려주므로 **열 제거 안 함**(50 MB 아래). 「판정에 쓰는 시간대만」 행 필터는 행 삭제라 하지 않음. 원자료 `서울교통공사_지하철혼잡도정보_20260630.csv`. 생성 `collect/congestion_build.py`.

### A `congestion_line9_v1.jsonl` · 3.0 MB · 8,208행
위와 같은 키 + `service`(local/express · loader 는 local 만 씀 · express 4,104행은 읽고 버림 → 행 삭제 후보지만 이 방에선 안 함) · `day_type` weekday/holiday 2종. 원자료 서울 OA-22197 xlsx(`raw\mobility\congestion_line9\line9_congestion_2026.xlsx` 정본). 생성 `congestion_build.py --line9`(25). 등급 확정 7,799 · 근거없음 409.

### A `transfer_car_v1.json` · 988.8 KB
`entries`(1,017 · 키 `환승역|노선|직전역|환승노선|둘째역` · `positions[{car door car_door}]` · `src` `src_sm`) · `missing_pairs` 79 · `merge_disagreements` 223. **표시 안 함(display=False 영구 · 46)** — 코드는 읽되 안내에 안 씀. 올리는 이유: `options.TransferCar.load` 가 경로를 찾으므로 있으면 로드·없으면 None 으로 갈리지 않게. 원자료 국토부 15151816 + 서울교통공사 15098252(`raw\mobility\car_position\`). 생성 `collect/build_transfer_car_v1.py`.

### A `graph/` 5개 (택시·자동차 소요 계산 · 13.6 MB)
| 파일 | 크기·행 | 열 | 등급 |
|---|---|---|---|
| `topis_class_factor_v1.json` | 7.9 KB | 도로급×요일형×시간대 평균속도·계수 · `osm_class_map` | 추정(약함) |
| `topis_link_profile_v1.jsonl.gz` | 5.0 MB · 365,798행 | `link_id` `daytype`(평일/토요일/휴일) `hour` `mean_kmh` `n_days` `std` `p10` `p90` — `car.py` 는 앞 4개만 씀(50 MB 아래 · 그대로) | 추정 |
| `osm_way_seg_topis_link_v1.csv` | 1.9 MB · 67,458행 | `osm_way_id` `seg_idx` `dir` `link_id` `n_pts` | — |
| `osm_way_geom_v1.csv` | 1.7 MB · 8,664행 | `osm_way_id` `highway` `name` `pts` | 확정(형상) |
| `daytype_calendar_v1.csv` | 8.0 KB · 365행 | `date` `daytype` `is_holiday` | — |
원자료 TOPIS 속도 xlsx 12개(`raw\mobility\topis\` 465 MB) + OSM pbf. 생성 `processed\mobility\graph\_build\01_geom.py → 02b_match.py → 03b_profile_test.py`(18 · 스크립트가 데이터 폴더에 있음 — 저장소로 옮기는 건 별도). **라우터(GraphHopper jar · pbf · graph-cache 1,240 MB)는 C** — 없으면 택시·자동차 근거없음(회귀 CAR-* 는 전체층 · `allow_router_down`).

### 부속 문서 12 (`_report.md` · 코드 안 읽음 · 합 40 KB)
`timetable_v1_coverage.md` `timetable_v1_destfill_report.md` `line_station_order_v1_report.md` `transfer_walk_v1_report.md` `bus_route_v1_report.md` `station_coords_report.md` `bike_stations_v1_report.md` `bus_seg_profile_v1_report.md` `congestion_v1_report.md` `congestion_line9_v1_report.md` `transfer_car_v1_report.md` `graph/README.md` — 파일별 커버리지·등급 근거. 같이 올린다(텍스트 · PR 에서 보임).

## 3. 크기표 전/후 (파일당)

| 파일 | 분류 | 전 | 후 | gz | 행 |
|---|---|---:|---:|---:|---:|
| `timetable_v1.jsonl` | B | 188.1 MB | **75.1 MB** | **1.8 MB** | 463,326 |
| `congestion_v1.jsonl` | A | 32.2 MB | 32.2 MB | — | 65,169 |
| `bus_stops_v1.jsonl` | A | 15.6 MB | 15.6 MB | — | 41,820 |
| `bus_seg_profile_v1.jsonl.gz` | A(정본 gz) | 9.2 MB | 9.2 MB | — | 40,776 |
| `graph/topis_link_profile_v1.jsonl.gz` | A(정본 gz) | 5.0 MB | 5.0 MB | — | 365,798 |
| `congestion_line9_v1.jsonl` | A | 3.0 MB | 3.0 MB | — | 8,208 |
| `graph/osm_way_seg_topis_link_v1.csv` | A | 1.9 MB | 1.9 MB | — | 67,458 |
| `graph/osm_way_geom_v1.csv` | A | 1.7 MB | 1.7 MB | — | 8,664 |
| `transfer_car_v1.json` | A | 988.8 KB | 〃 | — | |
| `station_exits_v1.json` | A | 804.8 KB | 〃 | — | |
| `bike_stations_v1.jsonl` | A | 800.4 KB | 〃 | — | 2,734 |
| `line_station_order_v1.json` | A | 761.6 KB | 〃 | — | |
| `station_coords.json` | A | 528.2 KB | 〃 | — | |
| `bus_route_v1.jsonl` | A | 470.0 KB | 〃 | — | 717 |
| `transfer_walk_v1.json` | A | 58.0 KB | 〃 | — | |
| `graph/daytype_calendar_v1.csv` | A | 8.0 KB | 〃 | — | 365 |
| `graph/topis_class_factor_v1.json` | A | 7.9 KB | 〃 | — | |
| `timetable_v1_meta.json` | A | 7.4 KB | 〃 | — | |
| **합계** | | **261.0 MB** | **148.0 MB** | **74.7 MB**(시간표만 gz) | |

## 4. 줄인 방법 · 하지 않은 것

- 열 제거는 **시간표만** — 근거는 §2 B-1 (`Timetable.load` 가 읽는 8열). 다른 파일은 loader 가 행 dict 를 통째로 들거나 50 MB 아래라 손대지 않았다.
- **행 삭제 0** — 출발없음 18,411행(`dep_time` null · loader 가 `skipped_no_dep` 로 세고 `stations` 집합에는 넣는다 → 빼면 `has_station()`·stats 가 달라질 수 있음)은 후보로만 둔다(`reduce_75.py --drop-no-dep` · 기본 off · 회귀 171 로 확인 뒤).
- 9호선 급행 4,104행(loader 가 버림)도 같은 이유로 안 뺐다.
- `.gz` 는 저장소에 넣지 않았다(판정기 `Timetable.load` 가 `open()` · 78 ⑦ loader 뒤 전환 가능 · `reduce_75.py --gz` 로 옆에 만들 수 있음 · 1.8 MB). 텍스트 75 MB 는 GitHub 경고(50 MB)만 · 거부(100 MB) 아님.
- 중복 v2 3개 · 아무도 안 읽는 파일 · 스크립트만 읽는 파일 · 개인 실측 · 그래프 캐시 · 중간 산출 → `DATA_NOT_IN_GIT.md`

## 5. 받는 법 — pull 만 하면 된다

`datasets/mobility/processed/mobility/` 가 저장소에 있다. `engine/paths.py`(75 수정): 준 경로의 마지막 폴더가 `processed` 면 그 자리를 PROCESSED 로 · 명령줄·시험은 `.env` `DATA_DIR` 이 없으면 저장소 폴더를 자동(출처 `repo_datasets`) · 서버는 `.env` `ACOP_MOBILITY_DATA_DIR=datasets/mobility/processed`. 드라이브 정본을 쓰던 기기는 `DATA_DIR` 이 이긴다. 자세한 절차 `MERGE_CHECK_v1.md` §3.

## 6. MANIFEST

`datasets/mobility/processed/mobility/MANIFEST_git_v1.json` — 파일마다 `path` `class` `source_raw` `regen_script` `read_by` `src_bytes` `src_sha256` `bytes` `sha256` `rows` `gz{path bytes sha256 reason}` `checked_at` + `totals` + 시간표 `reduce{rows_in rows_out rows_no_dep columns_kept columns_dropped columns_seen}`. 검증(75 · 클라우드): `.gz` 풀어 463,326행 · 텍스트 sha256 = MANIFEST `sha256` 일치 · 8열 전 행 동일 · 출발없음 18,411 · `chain_v1` 20,548.

## 7. 줄인 판 검증(9/29 · 노트북)

(재개 방에서 채움 — 게이트 pytest 건수 · 전체층 · 회귀 171 어긋남 · 정본 판과 대조)
