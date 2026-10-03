# road_graph_v1 — 서울(+인접·공항) 차도·자전거 그래프 파일 (76 · 2026-09-29)

서버(GraphHopper) 없이 파이썬에서 택시·자동차(·자전거) 경로를 계산하기 위한 **지도 데이터**. 경로는 저장하지 않는다.
- 원자료: Geofabrik `south-korea-latest.osm.pbf` · md5 `b4aac9966079cb88204b1d8df495e33c` · OSM 기준 시각 2026-09-18T20:21:10Z · ODbL 1.0(© OpenStreetMap contributors)
- **GH 그래프와 같은 pbf**: `graph\_build\seoul_bbox.osm.pbf.meta.json` src_md5 동일 · `gh\korea_topis.osm.pbf.meta.json` src 경로·바이트(287,530,348) 동일 · GH import 2026-09-20T05:15Z(`graph-cache\properties.txt`)
- 등급: **확정(OSM 공표)** — 형상·일방통행·접근 태그. 소요는 이 파일에 없다(77 이 TOPIS 프로파일로 계산 · 회전 제약 없음 → 라우터 소요 등급 = 추정)
- 생성: `mobility_scripts/collect/build_road_graph_v1.py`(약 3.5분 · pyosmium) · 검수: `check_road_graph_v1.py` → `check_report.json`
- 같은 pbf 면 md5 재현(gzip mtime=0 · 정렬 고정) — 클라우드 두 번 빌드 md5 일치 확인

## 파일
| 파일 | 행 | 크기(gz) | 텍스트 | md5 |
|---|---:|---:|---:|---|
| `nodes.jsonl.gz` | 280,065 | 3.24 MB | 16.5 MB | `1742f2eece86fbe6c8195e3224c0b72c` |
| `edges.jsonl.gz` | 375,651 | 12.63 MB | 68.2 MB | `5fef4bf787b91ddcbed1c5ec4a1eb49b` |
| `region_v1.geojson` | 11 도형 | 0.09 MB | — | `94335aee0dc3681cbb3700f4e8e47ab5` |
| 합계 | | **15.96 MB** | 84.7 MB | 목표 15~30 MB gz 안 → `service` 제외 안 함 |

## 열 뜻
**nodes** — 간선 끝점(교차점·way 끝)만. 중간 형상점은 간선 `g` 에.
| 열 | 뜻 |
|---|---|
| `id` | OSM node id |
| `lat` `lon` | WGS84 (소수 7자리) |
| `r` | 1 = 범위(서울+인접+공항) 안 · 0 = 3 km 여백(경계에서 잘린 일방통행이 막다른 길이 되지 않게 더 실은 부분) |

**edges** — way 를 그래프 노드에서 자른 조각 1행 = 1간선(방향은 `ow` 로).
| 열 | 뜻 |
|---|---|
| `u` `v` | 끝 노드 id(way 진행 순서 u→v) |
| `way` | OSM way id — `graph\osm_way_seg_topis_link_v1.csv` 의 `osm_way_id` |
| `sa` `sb` | way 노드 순번 구간 [sa, sb] (sa<sb). 세그먼트 i(=노드 i→i+1, sa≤i<sb)가 링크 표 `seg_idx` 와 같은 기준 · 방향 fwd = u→v |
| `len` | 길이 m(하버사인 합) |
| `ow` | 차량 일방: 0 양방향 · 1 u→v 만 · -1 v→u 만 (motorway·회전교차로는 태그 없어도 1) |
| `hw` | OSM `highway` |
| `ms` | OSM `maxspeed`(km/h · 없으면 null · 원 태그 — TOPIS 주입값 아님) |
| `car` | 1 = 차량 통행(아래 규칙) |
| `bike` | 1 = 자전거 통행 · `bow` 자전거 일방(같은 뜻 · `oneway:bicycle=no` 면 0) |
| `g` | 형상 Google encoded polyline(정밀도 1e-6 · 끝점 포함) — 좌표→간선 스냅용 |
| `main` | 1 = 차량 **최대 강연결 성분**(어디서든 오가며 닿는 망). 77 은 여기에만 스냅한다 |
| `bmain` | 1 = 자전거 최대 약연결 성분 |

## 결정(담당자 · 76)
- **범위** = 서울특별시(rel 2297418) ∪ 고양 2409166 · 성남 2409180 · 과천 2409169 · 하남 2409172 · 구리 2409168 · 광명 2409171 · 부천 2409162 · 김포 2409165 ∪ **영종구 13349474**(인천공항 섬 전체 · 2026-07 인천 행정개편으로 중구에서 분리된 이름이 pbf 에 있음) ∪ 인천국제공항고속도로(158 way) 양옆 500 m 회랑(서구·계양구 통과 구간) · 약 2,024 km² · 싣는 범위는 여기에 3 km 여백. 근거 = 같은 pbf 의 행정경계 relation(확정) · URL `https://www.openstreetmap.org/relation/<id>` · 확인 2026-09-29 17:58 KST
- **차량 도로**: motorway~tertiary(+link) · unclassified · residential · living_street · road · service. `service=parking_aisle·drive-through·emergency_access` 제외(주차장 통로는 택시 경로 아님). `motor_vehicle/motorcar=no·private` 제외 · `access=no·private` 는 차량 허용 태그 없으면 제외 · `access=destination` 은 실음. `track` 은 차량 아님.
- **자전거**: cycleway(`bicycle=no` 아니면) · path/footway/pedestrian/track/bridleway 는 `bicycle=yes·designated·permissive` 일 때만 · 차도는 `bicycle=no` 아니면 허용 · motorway·trunk(자동차전용)는 `bicycle=yes` 있을 때만.
- **회전 제약 생략** — turn restriction relation 을 싣지 않는다. 좌회전 금지 교차로에서 실제보다 짧은 경로가 나올 수 있다 → 77 라우터 소요 등급은 추정.
- 크기가 목표 안이라 `service` 를 뺀 판은 만들지 않았다(service 간선 124,550 = 전체의 33%).

## 검수(`check_report.json` · 2026-09-29 클라우드 · 같은 pbf)
- 차량 간선 327,274 · 자전거 365,390(자전거 전용 48,377) · 차량 길이 26,229 km · 일방 45k
- **연결 성분**: 차량 강연결 최대 성분 97.9%(전체) · **범위 안 차량 노드의 98.8%** · 약연결 98.6% · 자전거 약연결 98.1%. 20 노드 이상 섬 20개 — 대부분 여백 끝(인천 서구·시흥 쪽 막다른 일방)과 주차장(예: 인천공항 T1 남동 주차장 86 노드 — `parking_aisle` 로만 이어짐). 섬은 `main=0` 으로 표시.
- **353 도로 시험 좌표 706점 전부 `main` 간선 200 m 안**(p50 2.3 · p90 6.8 · 최대 21.2 m) — 여백 0 으로 만들었을 때는 5점(동부간선·동일로 북단·서부간선)이 경계에서 잘린 일방통행 섬에 붙었다 → 3 km 여백으로 0.
- **TOPIS 링크 연결**: 링크 표 way 8,664 중 8,662(99.98%) · 세그먼트 67,458 중 67,451(99.99%)가 간선 [sa, sb) 안 · 방향 허용 전부 · 빠진 2 way 는 `access=no`(495340530 막힌 회차로 · 602097726 driveway) = 제외가 맞음. `osm_way_geom_v1.csv` 8,662 way 의 노드 순번이 간선 끝 좌표와 전부 일치.
- 랜드마크 13곳(인천공항 T1·T2 · 김포공항 · 서울역 · 강남 · 판교 · 킨텍스 · 서울대공원 · 스타필드 하남 · 부천 · 광명 · 구리 · 김포시청) 최근접 `main` 간선 1~211 m(킨텍스 211 m 는 좌표가 전시장 건물 한가운데 — 대략 좌표 · 추정).
