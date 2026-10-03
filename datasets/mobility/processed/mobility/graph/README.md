# graph/ — 이동 모듈 라우터 그래프 (18번 방 · 2026-09-19 · v2 2026-09-20)

OSM(13번) + TOPIS 속도(14번) → GraphHopper 입력과 시각별 소요 계산기. **경로는 저장하지 않는다** — 여기 있는 것은 지도 데이터·프로파일·매핑표뿐이다.

## 파일

| 파일 | 내용 | 등급 |
|---|---|---|
| `topis_link_geom_v1.geojson` | TOPIS 5,128 링크 폴리라인, EPSG:5181→4326. 속성에 도로명·방향·급·파일거리 | 확정(형상) |
| `topis_link_geom_v1_len_check.csv` | 링크별 5181/4326/14번 csv 길이 대조 | 회귀 |
| `topis_osm_match_v1.csv` | 링크별 OSM 매칭률·이격·매칭 way | 검수 |
| `osm_way_topis_link_v1.csv` | OSM way × 진행방향(fwd/bwd) → 링크 (way 단위 · PBF 주입용) | |
| `osm_way_seg_topis_link_v1.csv` | OSM way 세그먼트(노드쌍) × 방향 → 링크 (소요 계산용) | |
| `osm_way_geom_v1.csv` | 매칭된 way 의 노드 좌표 (graph_time 이 세그먼트를 찾을 때) | |
| `topis_link_profile_v1.jsonl.gz` | 링크×요일형(평일/토요일/휴일)×시간대(0~23) 평균속도·관측일·p10/p90. 학습 2025-09~2026-05 | 추정 |
| `topis_class_factor_v1.json` | 도로급×요일형×시간대 평균속도와 자유속도 대비 계수 (TOPIS 없는 간선 대체값) | 추정(약함) |
| `daytype_calendar_v1.csv` | 2025-09-01~2026-08-31 요일형. `holidays` KR + 2025-10-02 임시공휴일 추가 · **2026-07-17 제헌절 = 휴일**(34번 9/21 정정 — 18번의 「제외」는 틀렸다 · 2026-01 법 개정) | |
| `road_test_expected_v1.csv` | 353 도로×방향 × 요일형×시각 관측 소요(2026-06~08) + 양끝 좌표 — 노트북 주입 시험 기대값 | |
| `build_topis_pbf.py` | **v2** PBF 에 정적 속도 ÷0.9 를 `maxspeed[:forward/:backward]` 로 주입: TOPIS 링크(평일 07~20시 평균) + 서울 상자 안 비커버 간선(도로급 평균) + 골목(residential 15 · service 10 · living_street 6 · unclassified 20) → `gh\korea_topis.osm.pbf` | 추정 / 추정(약함) / 근거없음 |
| `graph_time.py` | GraphHopper 응답(`details=[osm_way_id, road_class]`) + 프로파일 → 시각별 소요·커버 비율·등급 | |
| `gh_sample_run.py` · `sample10.json` | 표본 10구간 · 도보 20 회귀 · 도로 단위 주입 시험(링크 체인 경유점) 실행기. `--dump` 는 디버그용(끝나면 지움) | |
| `gh_sample10_result.csv` · `gh_walk20_result.csv` · `gh_road_test_result.csv` | 2026-09-20 노트북 실행 결과(v2 빌드). 도로 시험 같은 도로 42표본 MAPE 3.6% — **`gh_road_test_result.csv` 의 `obs_s`·`ape` 는 옛 달력 기대값 그대로(기록). 달력 정정 후 3.75%**(34번, 예측값 불변 · 기대값만) | 결과 |
| `gh/config-topis.yml` · `gh/gh_build.ps1` | GraphHopper 11.0 설정·빌드 스크립트. car 만 turn_costs. 전국 빌드 약 30분 · 힙 5 GB(`-Xmx6g`) | |
| `_build/` | 이 폴더를 만든 스크립트(클라우드에서 실행한 원본. 경로만 노트북용으로 바꿈) | |

## 노트북 실행 순서

```powershell
cd C:\final_project\data\travel\processed\mobility\graph
pip install osmium
python build_topis_pbf.py --src ..\..\..\raw\mobility\osm\south-korea-latest.osm.pbf --out gh\korea_topis.osm.pbf   # ~5분
cd gh
.\gh_build.ps1          # jar 내려받기 → 빌드(~30분) → 서버. logs\build_times.txt 에 시간·메모리
# 다른 창에서
cd ..
python gh_sample_run.py  # gh_sample10_result.csv · gh_walk20_result.csv · gh_road_test_result.csv
```
`gh_sample10_result.csv` 의 `naver_dist_m`·`naver_min` 칸은 네이버 지도(자동차/도보)에서 같은 좌표로 읽어 손으로 채운다.

## 설계 (담당자 결정)

- **경로 선택은 정적, 소요는 동적.** GraphHopper 는 `maxspeed` 로 주입된 평일 주간 평균으로 경로를 고른다(CH 유지 → 빠름). 시각별 소요는 `graph_time.py` 가 경로의 edge 마다 `링크×요일형×시간대` 값을 다시 적용한다(진행하면서 시각을 넘긴다).
- **등급**: edge 에 프로파일 있음 = 추정(topis) · 간선인데 없음 = 추정(약함, class) · 골목 = 근거없음(default, 골목 고정값 — `build_topis_pbf.py` 와 같은 표). 구간 등급은 가장 약한 등급(골목 비율 50% 초과면 근거없음). 커버 비율은 m 단위로 같이 낸다 — 경계값은 코드 방에서.
- `source_id`: `topis_link_profile_v1@2025-09~2026-05` · `osm_road_graph@2026-09-18`.

## 실측 (2026-09-20 노트북)

같은 도로 위 42표본 MAPE 3.6%(GraphHopper 정적 소요 11.1%) → **달력 정정(34번) 후 3.75% · 11.2%** · 도보 20 gh/카카오 ±25% 안 11/20 · 서울역→강남역 평일 18시 33.5분(topis 커버 86%). 전문은 `18_전처리_도로망그래프_인계_20260919.md` §4.

## 34번 정정 (2026-09-21)

- `daytype_calendar_v1.csv` 20260717 → `휴일,True` · `road_test_expected_v1.csv` 평일·휴일 4,216행 재계산(평일 64→63일 · 휴일 +1일 · 토요일 불변) · `step3_result_fix34.json` 신설(정본).
- `topis_link_profile_v1.jsonl.gz` · `topis_class_factor_v1.json` 은 **다시 만들어도 값이 같아**(프로파일 바이트 동일 · 계수는 `calendar` 표기 외 동일) 그대로 둔다(07-17 은 시험 기간 — 학습 2025-09~2026-05 밖). class factor 안의 `"calendar": "fix"` 표기는 학습 달력 기준이라 틀리지 않다.
- `_build/03b_profile_test.py` 기본 판 `fix34` · `osm_car_ways.pkl` 대신 `osm_way_geom_v1.csv` 로 세그먼트 길이(결과 동일 — `fix` 로 4.43% 재현 확인).
