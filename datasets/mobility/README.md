# Mobility(이동) 팀 데이터셋 폴더

Mobility(이동) 팀이 쓰는 데이터를 모으는 자리다(2026-09-29 신설).

## 현재 거리 보강 입력 (2026-10-08)

판정기는 기존 자료에 [OSM 선로 거리 v2](processed/mobility/rail_edge_track_v2.jsonl.gz)와
[공표 거리 대응표](processed/mobility/rail_distance_overlay_v1.json)를 추가로 읽는다.
기존 21개와 새 2개를 합친 23개가 [파일 명세](processed/mobility/MANIFEST_git_v1.json)에 등록돼 있다.
실제 읽은 파일 이름·크기·SHA-256을 검사하며, 명세에 등록된 새 판이 사라졌을 때 옛 판으로 조용히 대체하지 않는다.

| 자료 | 실제 행·간선 | 판정에 쓰는 등급 | 다시 만드는 코드 |
|---|---:|---|---|
| 선로 거리 v2 | 777행 중 거리 726개 = 93.4% | OSM 선로 길이 **추정** | [선로 거리 생성](../../final_project_cs/scripts/mobility/build_rail_track_v2.py) |
| 공표 거리 대응표 | 보강 214간선 | **공표값·대응방향 추정** | [공표 거리 대응표 생성](../../final_project_cs/scripts/mobility/build_rail_distance_overlay.py) |

두 자료는 확정 운임거리로 승격하지 않는다. CSV 원문 24종·1,861행과 받아 온 시각·출처·해시는
[원문 명세](raw/official_distance_20261008/manifest-v2.json)에 있다.
원문은 로컬 보관하며, 재생성·검증·적용 우선순위는 [데이터 보고서](REPORT.md#거리-보강과-버스-도착정보-확인-2026-10-08)에 적었다.
아래 2026-09-29·09-30의 크기·21파일 수치는 당시 기록이다.

## 폴더

| 폴더 | 무엇을 두나 | git 에 올라가나 |
|---|---|---|
| `raw/` | 받은 그대로의 원본(API 응답, 내려받은 파일, 엑셀) | **안 올라간다** |
| `processed/` | 정리·가공한 결과(CSV·JSONL 등) | **안 올라간다** |
| `scripts/` | 원본을 받아 오고 가공하는 코드(`.py`·`.json`·`.txt` 등) | 올라간다 |
| `README.md` · `REPORT.md` | 무슨 데이터인지, 어디서 받았고 어디에 쓰는지 | 올라간다 |

★**데이터 파일 자체(CSV·TSV·JSONL·XLSX·Parquet·DB·압축본)는 이 폴더 어디에 두어도 git 에 올라가지 않는다.**
공개 저장소라서다 — 09-14 에 실제 주문 기록 조각(가린 이름·연락처 끝자리·주소)이 섞여 올라간 일이 있었다.
데이터는 각자 PC 나 팀 드라이브로 나누고, 여기에는 **다시 만드는 방법(scripts/)과 설명(REPORT.md)** 을 올린다.

## REPORT.md 에 적을 것

- 무슨 데이터인가 · 출처(기관·API·주소) · 받은 날짜 · 행 수
- 이용 조건(출처 표시 등) — 관광공사 자료는 ⓒ한국관광공사 표시를 유지한다
- 어떤 코드가 이 데이터를 읽는가(`final_project_cs/...` 경로)
- 개인정보가 섞일 수 있는지, 섞였다면 어떻게 걸렀는지

## 올리면 안 되는 것 (위 규칙이 막지만 이름을 바꾸면 샐 수 있다)

- 로그인 세션·쿠키·브라우저 프로필, API 키(`.env`) — 키는 `.env.apikeys` 같은 git 이 무시하는 파일에만 둔다
- 사람 이름·연락처·주소가 든 원본

---

## 이동(Mobility) 팀 — 이 폴더를 실제로 어떻게 쓰나 (2026-09-29 · 75번 방)

**판정기·라우터가 읽는 가공 데이터 21파일(89 MB · 9/30)을 `processed/mobility/` 에 두고 git 에 올린다** — 팀장 배정(9/29 · 「서버가 뜰 때까지 임시 · develop 까지」).
위 규칙과 어긋나는 점은 하나뿐이고 근거는 이렇다.

- 전부 **공공데이터**(서울 열린데이터광장 · 국토교통부 TAGO · 국가철도공단 · 서울교통공사 · OSM) — 개인정보·키·사용자 입력 **없음**. 원자료·개인 실측(담당자 출퇴근 기록·티머니 태그)은 여기 없고 드라이브에만(`DATA_NOT_IN_GIT.md`).
- 팀 `.gitignore` 는 손대지 않았다. `processed/**` 가 막혀 있으므로 **`git add -f`** 로 추적한다 — 한번 추적된 파일은 이후 변경도 보통 `git add` 로 잡힌다. **새 파일**을 더할 때만 다시 `-f`.
- 서버(`app.core.settings.mobility_data_dir`)가 자기 자료 폴더를 갖게 되면 이 폴더의 데이터는 지운다(히스토리엔 남는다 — 그래서 첫 커밋을 줄인 판 148 MB 로 작게 했다).

| 자리 | 무엇 | git |
|---|---|---|
| `processed/mobility/` | 판정기 입력 21파일(시간표는 판정기가 읽는 8열만 · **`.gz`** · 나머지 정본 그대로) + 파일별 `_report.md` 12 + `MANIFEST_git_v1.json`(sha256·md5·행수·원자료·확인 시각) | **올림(`-f`)** |
| `processed/mobility/graph/` | 택시·자동차 소요 계산 자료 5파일(TOPIS 속도 프로파일 등) | 올림 |
| `processed/mobility/road_graph_v1/` | 서울(+인접·공항) 차도·자전거 그래프(노드 280,065 · 간선 375,651 · 15.96 MB gz · OSM ODbL) — 서버 없는 파이썬 라우터 입력(9/30 추가) | 올림 |
| `processed/inventory_75.json` · `size_table_75.md` | 정본 폴더 인벤토리(88파일 열·행·sha) · 전/후 크기표 | 안 올림(ignore) |
| `raw/` | 비움 — 원자료 1.7 GB 는 드라이브 `data\travel\raw\mobility\` | 안 올림 |
| `scripts/` | `inventory_75.py`(인벤토리) · `reduce_75.py`(정본 → 이 폴더 줄인 판 + MANIFEST · 기본이 gz·행 삭제 채택안 · **파일을 더할 때는 이 스크립트의 `FILES` 표에 한 줄** — 지금 조사 중인 데이터도 같은 길) · 갱신용 수집·전처리 32개(82 · 파일표·갱신 순서는 `scripts/README.md`) | 올림 |
| `REPORT.md` | 데이터 설명(팀장 양식) | 올림 |
| `DATA_IN_GIT.md` | 올린 21파일 상세 — 읽는 코드 · 열 뜻 · 한 행 예시 · 원자료 · 생성 스크립트 · 등급 · 줄인 방법 · 검증 | 올림 |
| `DATA_NOT_IN_GIT.md` | 안 올린 것 — 원자료 · 개인 실측 · 라우터 캐시 · 로그 · 줄인 판에서 뺀 열·행 · 이유 · 드라이브 위치 | 올림 |

**읽는 코드**: `final_project_cs/app/domains/travel_ops/instances/mobility/engine/paths.py` — 명령줄·시험은 `.env` 의 `DATA_DIR` 이 없으면 이 폴더(`datasets/mobility/processed`)를 자동으로 쓴다(pull 만 하면 `pytest tests/unit/travel/mobility` 회귀 게이트가 skip 없이 돈다). 서버는 `.env` 에 `ACOP_MOBILITY_DATA_DIR=datasets/mobility/processed`(마지막 폴더 이름이 `processed` 면 그 자리를 그대로 자료 폴더로 본다).


## 공식 실시간 지하철 역 번호 (2026-10-09 확보)

[원문·수집 정보](raw/subway_realtime_station_20261009_v1/)와 [역ID 추출값](processed/mobility/subway_realtime_stations_20260902_v1.json)은 실시간 도착 응답을 계획 경로에 연결하기 위한 자료입니다. 원문696행·19호선, 출처: 서울특별시(공공누리 제1유형). [추출 코드](../../final_project_cs/scripts/mobility/build_subway_realtime_stations.py)는 새 출력파일만 생성합니다. 현재 cs 프로젝트 서버의 출발/환승 관측에는 이 대응값을 아직 연결하지 않았습니다. [현재 근거](REPORT.md)의 마지막 기록을 참조합니다.


## 2026-10-09_1014 서울역 공개 도착 샘플1개

[2026-10-09_1009_지하철응답_빈값오인_public_sample](raw/2026-10-09_1009_지하철응답_빈값오인_public_sample/)에 서울시 공개 sample HTTP200·INFO-000 원문3616바이트, 정규화5행과 수집정보를 보존했습니다. 2026-10-09T10:10:52.488223+09:00 조회1회이며 total18행 중5행만 반환했습니다. 원문SHA256 `061bb931bbe628c402394d67e0795451caae238840a5768de7e65662e3eaeb9a`. 4통제상황 ABBA16회 재생은 독립 표본이 아닙니다. 오류/정상빈결과/보관회복 검증에만 사용하고 실제ETA정확도·열차선택·탑승관측·출발/환승 연결을 주장하지 않습니다. 출처 서울특별시 OA-12764. 지도개발자API0회. [보고서](../../final_project_cs/wiki/records/reports/2026-10-09_1014_지하철_빈결과오인과_보관회복_검증.md).


## 2026-10-09_1032 공식 역ID 자료의 런타임 연결

[공식 역ID 추출물](processed/mobility/subway_realtime_stations_20260902_v1.json)을 이제 선택 입력으로 적재하며696행·19호선과 내용SHA256을 확인합니다. 첫 지하철 승차/하차 문맥·출발 대조·저장 직전 판 검사에 사용합니다. 없으면 ID 연결unavailable, 잘못된 파일은 적재 실패입니다. 정확 좌표 대응587/793·미대응206개를 보존하며 넓은 역명 별칭은 추정하지 않습니다. 추출물의 connected_to_departure=false는 실시간 운행 시각 적용 미연결이라는 의미로 유지합니다. 이전 “런타임 미연결” 기록은 당시 상태이며 현재 ID 적재/문맥은 연결됐습니다. 원문/가공물/기동 명세를 덮어쓰지 않았습니다. [보고서](../../final_project_cs/wiki/records/reports/2026-10-09_1032_계획지하철_공식역ID와_내용판_연결검증.md).
