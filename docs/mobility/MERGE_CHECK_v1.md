# 이동 모듈 merge 통과 기준 — 한 장 (v1 · 2026-09-29 · 71번 방)

**이동 모듈이 들어 있는 `develop` 을 merge 했으면 이걸 돌린다.** 초록이면 끝. 빨강이면 §4 표에서 그 줄을 찾는다.
작성 서유현(이동·동선 담당). 회귀가 무엇인지는 `REGRESSION_EXPLAINED_v1.md`.

---

## 1. 명령 (final_project_cs 에서 · 팀 venv)

```powershell
cd final_project_cs
python -m ruff check .                                                       # 0 이어야 (CI 관문 · F·E9)
python -m pytest tests/unit/travel/mobility -q                               # ★ 팀원 게이트 — 이것만 돌리면 된다
python -m pytest tests/contract/test_team_layout.py tests/contract/test_team_tool_discipline.py -q   # 팀 배치 검사
```

우리(이동 담당)만 추가로, 방을 닫을 때:

```powershell
python -m pytest tests/unit/travel/mobility -m "mobility_full and not live" -q   # 우리 전체층 — 실데이터 회귀 나머지 + 실데이터 단위
```

## 2. 기대 숫자

| 실행 | 데이터 없음(팀원 PC · CI) | 데이터 있음(`DATA_DIR`) | 시간(노트북 실측 9/29) |
|---|---|---|---|
| **게이트** `pytest tests/unit/travel/mobility -q` | **144 passed · 67 skipped · 179 deselected** | **211 passed · 179 deselected**(78 뒤 · 알려진 빨강 0) | 없음 20초 · 있음 **2분 32초**(71 측정) |
| 전체층 `-m "mobility_full and not live"` | 4 passed · 181 skipped · 211 deselected | **185 passed · 211 deselected**(78 뒤) | 있음 7분 28초(71 측정) |
| 팀 배치 검사 | 57 passed(9/29 develop `747dc79` 기준 · 파일이 늘면 커진다) | 같음 | 3초 |

- 게이트 211 = 데이터 없이 도는 단위 189(팀장 `test_review_fixes_*`·`test_check_scripts` 포함 · 78 에서 봉투 참조·04:00 양쪽·재판정 문맥·로그 진입점 등 +6) + **회귀 게이트 21**(주요 기능마다 1건) + 목록 정합성 1. 전체층 185 = 회귀 나머지 156 + 실데이터 단위 29(`plan_concurrency`·`plan_estimate`·`plan_bike` 의 DATA_DIR 축 · 78 `test_bus_bus_walk_v1` 6). **회귀 177 = 21 + 156**(78 에서 171 + 새 6: 버스↔버스 환승 BB-01~04 · 막차 통과 반대편 NIGHT-10B · 역방향 버스 MIX-07) — 잠그는 것은 줄이지 않았고 층만 나눴다.
- **§2-1 알려진 빨강 — 없음**(2026-09-29 · 78 「73 후속」에서 정리). 747dc79 merge 직후 데이터 있는 기기에서 보이던 빨강(`test_plan_v1` 6 · 전체층 3 · 회귀 3케이스 `MIX-06`·`MULTI-06`·`NIGHT-10`)은 기대·골든을 팀장 판에 맞추고 우리 엔진 수정(규칙 v0.9.2)과 함께 잠갔다. 이제 빨강이 나오면 그게 진짜 회귀다.
- **`skipped` 는 빨강이 아니다** — 「data not present」·「시간표 없음(DATA_DIR)」이면 데이터가 없어서 건너뛴 것. **9/29 부터 데이터가 저장소 안(`datasets/mobility/processed/`)에 있으므로 pull 한 기기에서는 회귀 게이트가 skip 되지 않는다**(§3) — skip 이 나오면 pull 이 안 됐거나 `.env` 의 `DATA_DIR` 이 엉뚱한 곳을 가리키는 것.
- **`deselected` 는 전체층이 기본 실행에서 빠진 것**(conftest.py). 빨강·노랑 어느 쪽도 아니다.
- 건수·시간은 노트북(`playdata` · Python 3.11 · develop `747dc79` merge 커밋 `37000a9`) 실측 2026-09-29 15:31.

## 3. 데이터 받는 법 — **pull 만 하면 된다**(2026-09-29 · 75번 방 · 팀장 폴더 배정)

판정기 입력 18파일(148 MB)이 저장소 **`datasets/mobility/processed/mobility/`** 에 들어 있다(서버가 자기 자료 폴더를 갖기 전까지 임시 · `git add -f` 추적 · 전부 공공데이터). `.env` 에 `DATA_DIR` 이 없으면 명령줄·pytest 는 이 폴더를 자동으로 쓴다 → 회귀 게이트 21건이 skip 없이 돈다.

- 확인: `cd final_project_cs; python -c "from app.modules.travel_ops.mobility.engine.runtime import build_verifier; build_verifier()"` — 「`[mobility] 시간표 444,915행 …`」이 찍히면 됨(출처 `repo_datasets`).
- 서버로 켤 때: 저장소 루트 `.env` 에 `ACOP_MOBILITY_DATA_DIR=datasets/mobility/processed`(팀 `.env.example` 항목).
- 드라이브 정본(`DATA_DIR=C:\final_project\data` · `travel/processed/mobility/`)을 쓰던 기기는 그대로 — `.env` 의 `DATA_DIR` 이 있으면 그쪽이 이긴다.
- 파일 설명·sha256: `datasets/mobility/REPORT.md` · `docs/mobility/DATA_IN_GIT_v1.md` · `MANIFEST_git_v1.json`.

## 4. 빨강이면 어디를 보나

| 빨강이 난 시험 | 이건 무엇이 깨진 것 | 먼저 볼 것 |
|---|---|---|
| **`test_regression_cases.py::test_gate[<id>]`** | 실패 메시지 첫 줄에 **`[기능] … — 깨지면: …`** 가 찍힌다. 그 기능이 죽었다는 뜻 | 메시지의 `MISS 기대 X → 실제 Y` 칸(판정? 도착 시각? 경고?) → `REGRESSION_EXPLAINED_v1.md` §7 순서. 한 건만 다시: `python -m pytest tests/unit/travel/mobility/test_regression_cases.py -k <id> -q`(전체층 케이스는 `-m mobility_full` 을 같이 — 없으면 deselect 돼 「no tests ran」) |
| `test_regression_cases.py::test_gate_list_is_consistent` | 게이트 목록(`regression_gate_v1.json`)이 케이스 파일과 안 맞거나, 케이스 id 가 겹치거나, 합이 `N_ALL`(78 기준 177) 이 아니다 | 케이스를 더하거나 뺐으면 `test_regression_cases.py` 의 `N_ALL`·`N_GATE` 와 목록을 같이 고친다 |
| `test_plan_v1.py::test_golden` · `test_golden_all_modes` | **코어로 나가는 `plan()` 출력**이 골든과 다르다 — 이동 항목·`routes` 의 시각·후보가 움직였다 | `plan.py`·`options.py` 를 만졌나 → 아니면 판정기 값이 바뀐 것(회귀 게이트도 같이 빨강일 가능성). 의도한 변경이면 골든 재생성: `python -m app.modules.travel_ops.mobility.engine.plan --in tests/unit/travel/mobility/plan_example_in_v1.json --no-basis --modes subway walk bus --out tests/unit/travel/mobility/plan_example_out_all_v1.json`(`subway walk` 판도) |
| `test_plan_v1.py::` 그 밖 | `plan()` 계약(기존 칸만 · 새 키 0 · `uses` 자가 검사 · 요금 · `left_out`) | `plan.py` · 팀 `route_uses.py`(표기 정규식이 바뀌면 `test_uses_self_check` 가 운다) |
| `test_verify55_v1.py::` | 동명이역(양평·신촌) · 환승 제외 · p90 도보 밀기 | `geo.py`·`candidates.py`·`verify_time._shift_out` |
| `test_bus_profile_unit.py::` | 버스 구간 프로파일 누적 규칙(합성) | `bus_profile.py` |
| `test_bus_window_norm.py::` | 버스 운행구간 정규화(N26 자정 등) | `mobility_scripts/collect/build_bus_all_v1.normalize_window` |
| `test_car_fare.py::` | 택시 요금 산식 | `car.py` |
| `test_judgment_log.py::` | 판정 로그·차단 목록·지표 | `judgment_log.py` · `mobility_scripts/classification_metrics.py` |
| `test_timeutil.py::` | 24시 넘김·운행일 분 계산 | `timeutil.py` — 이게 깨지면 위 전부가 같이 깨진다 |
| **`ERROR collecting …`**(수집 단계) | import 만으로 파일·폴더·네트워크를 건드리는 코드가 들어왔다(27번 규칙 26) — CI 는 `.env` 없이 수집한다 | 트레이스의 모듈. `mobility_scripts/collect/_paths.py` 방식(import 는 값만 · 쓰기 직전 `ensure_dirs()`) |
| `tests/contract/test_team_layout.py` · `test_team_tool_discipline.py` | 팀 폴더 규율(`mobility/` 안 `.py` 는 인프라 직접 import 금지 · `mobility.py` 파일과 폴더 공존 금지) | 새로 넣은 파일의 import |
| skipped 가 기대보다 많다 | 데이터가 안 보인다 | `.env` 의 `DATA_DIR` · §3 의 3번 |

## 5. 빨강을 고치는 세 갈래 (회귀 게이트·골든)

1. **데이터 판이 바뀌었다** — 시간표를 다시 받았거나 채운 판이 아니다 → 이동 담당이 값을 확인해 기대값을 갱신하고 `note` 에 이유를 적는다. 팀원이 할 일 아님.
2. **의도한 수정** — 판정 규칙을 바꿨다(규칙 버전 v0.9.1 → 다음) → 기대값 갱신 + 규칙 `changelog` + 인계 문서. 이것도 이동 담당.
3. **진짜 회귀** — 위 둘이 아니면 이것. **팀원은 여기서 멈추고 실패 줄(`[기능] …` 부터 `MISS …` 까지)을 이동 담당에게 보낸다.** 기대값을 통과하게 고치는 것은 회귀를 지우는 것과 같다.

## 6. 게이트 21건 — 기능 ↔ 케이스 (정본은 `tests/unit/travel/mobility/regression_gate_v1.json`)

| 기능 | 케이스 | 깨지면 |
|---|---|---|
| 지하철 구간 성립 + 도착 시각 | `R-BASE-01` | 판정기 본체 |
| 막차 이후 불가 + 늦어도 출발 | `R-LAST-03` | 막차 판정(after_last)·역산 |
| 첫차 이전 불가 | `R-FIRST-01` | 첫차 판정 |
| 24시 넘김 — 24:30 출발이 막차 안(합성) | `LAST-01` | timeutil 분 단위 시각 |
| 심야 N버스 첫차 자정 정규화 | `NIGHT-01` | 45 정규화 |
| 심야 N버스 운행일 | `NIGHT-03` | service_days |
| 운행일 경계 04:00 | `NIGHT-12` | to_service_min 경계 |
| 지하철 환승(도보 포함) | `R-TRANS-01` | 환승표·순환선 한 바퀴 |
| 순환선 시발역·행선지 | `R-LOOP-01` | 종착 필터 |
| 종착 열차 제외 | `R-TERM-01` | 막차 후보 필터 |
| 요일형(토·일·공휴일) | `R-HOL-01` | holidays·day_type_of |
| 버스 승차 소요(프로파일) | `BP-01` | 41 프로파일 누적 |
| 버스 막차 → 지하철 수단교체 | `BUS-03` | 버스 막차·수단교체 축 |
| 지하철↔버스 혼합 환승 도보 | `MIX-01` | 정류장↔출구 도보 |
| 이슈 — 무정차는 지나간다 | `ISSUE-02` | disruption 모델 |
| 이슈 — 양쪽 중단은 불가 | `ISSUE-03` | disruption 모델 |
| 불가일 때 대안 열거 + 재판정 | `ALT-01` | alternatives() |
| 최악값 판정 | `J-WORST-02` | 39 이중 계산 |
| 도착 목표 대비 여유 | `J-SLACK-01` | @·slack 계약 |
| 모르면 근거없음 | `J-NODATA-01` | no_data 정직 |
| 다목적 후보 생성 | `MULTI-01` | candidates.py |

게이트는 **라우터(GraphHopper)를 항상 끄고** 돈다(기기마다 결과가 달라지지 않게 · 택시 값은 이동 담당이 CLI 로 GH 있는 기기에서 본다).

게이트에 **없는** 것(전체층이 잠근다 · 코어 경로에 지금 도달하지 않거나 데이터 판 검사라서): 동행 상한(`R-LIMIT-*`) · 택시·자동차(`CAR-*`) · 따릉이(`BIKE-*`) · 채운 시간표 판(`D28-*`) · 프로파일 없음(`NP-*`) · 나머지 축 전부.

## 7. 두 층이 어떻게 갈리나

`tests/unit/travel/mobility/conftest.py` 가 마커 `mobility_full` 을 등록하고, `-m` 식에 `mobility_full` 이 없으면 그 항목을 **deselect** 한다. 팀 `pytest.ini` 는 안 만졌다 — 팀장님이 한곳에서 관리하고 싶으면 `pytest.ini` 를 `addopts = -m "not live and not mobility_full"` + `markers` 한 줄로 바꾸고 conftest 의 두 훅을 지우면 된다(동작 동일). `-m` 을 직접 주면 `pytest.ini` 의 `not live` 가 대체되므로 전체층 명령은 `-m "mobility_full and not live"` 로 적는다.
