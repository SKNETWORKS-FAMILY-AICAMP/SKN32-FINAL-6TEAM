# PR 노트 — 이동·동선 모듈(`role-mobility` → `develop`) v1

2026-09-28 · 서유현(Mobility) · 기준 `origin/develop` `571d7d2`(merge 반영 완료 · 충돌 0)

## 1. 한 줄

이동 모듈은 **값을 내는 함수 하나**(`plan()`)와 그 판정기다. 코어(팀장) 배선은 `docs/mobility/2026-09-25_Mobility_호출안내_v2.md` 대로 부르면 되고, **팀 파일 수정은 0** 이다.

## 2. 어디에 무엇이 있나

| 자리 | 내용 |
|---|---|
| `final_project_cs/app/modules/travel_ops/mobility_engine/` | 판정 엔진(`verify_time.py`) · 계획 `plan.py`(`plan()` · CLI) · 후보·요금·규칙(`rules/rules_v0.3.json` — 내부 버전 v0.9.1) |
| `tests/mobility/` | 회귀 케이스 JSON 14묶음 + 단위·계약 시험(전부 pytest 로 돈다) |
| `mobility_scripts/` | 수집·빌드·자기점검·지표 스크립트(**이번 PR 에서 루트 `scripts/` 에서 옮김** — 아래 §4) |
| `docs/mobility/` · `config/mobility/` · `sql/mobility*` | 설계·호출 안내·규칙 보조표·DB 스키마(참고용) |

팀 파일 중 우리가 건드린 것: **없음.** 팀장 `travel_ops/mobility.py` · `route_uses.py` 는 그대로 쓴다.

## 3. 데이터는 git 밖이다

시간표·역 좌표·버스 프로파일 같은 원자료·가공물은 **드라이브(`DATA_DIR/travel/…`)** 에 있고 저장소에는 없다(`.env` 의 `DATA_DIR` 하나로 위치를 잡는다). 그래서

- **데이터가 없는 기기(팀원 포크 · CI)** 에서 `python -m pytest tests/mobility -q` 를 돌리면 실데이터 시험은 `skip`(사유 「data not present」/「시간표 없음」)되고 합성 픽스처 시험만 돈다 — 이번 확인: **74 passed · 62 skipped · error 0**.
- `.env` 가 없어도 import·`plan()` 은 돈다(라우터 주소는 규칙 파일 기본값 · 외부 키 없으면 그 기능만 근거없음/꺼짐).
- 데이터가 있는 기기에서는 **136 passed**(134 + 골든 교체 뒤 2).

## 4. 이번 PR 에서 구조만 바꾼 것 — 판정 규칙·출력 무변경

- 루트 `scripts/`(우리) 와 `final_project_cs/scripts/`(팀)가 **둘 다 정규 패키지 `scripts`** 여서 경로 순서에 따라 한쪽만 잡히던 문제 → 우리 것을 **`mobility_scripts/`** 로 옮겼다(`git mv` · 29파일 + `collect/` 45 + `probe/` 4). 루트 `scripts/` 에는 팀 파일(`README.md` · `build_competitor_doc.py`)만 남는다. 저장소 루트에서 `python -m mobility_scripts.<이름>` 이 PYTHONPATH 없이 돈다.
- pytest 수집을 막던 우리 시험 3파일(모듈 최상위 `sys.exit`)을 `test_*()` 로 감쌌다 — 스크립트로 직접 실행하는 방식은 그대로.
- 9/20 첫 커밋에 잘못 들어간 파일 5개 제거(루트 `__init__.py` · 빈 `modules/` 패키지 · 옛 메모 md 2).
- 골든 1곳 교체: 팀 `route_uses.py` 가 버스 노선명 검사를 넓혀(`01A`·`702A` 등 59노선 수용) 예시 출력의 **요약 한 줄**만 바뀜(`uses_format 2` → `before_prev_end 43`) · 이동 항목·경로 값 동일.

## 5. 숫자(기기 노트북 `playdata` · 2026-09-28 · GraphHopper 없음)

- 판정 회귀 **14묶음 171건 어긋남 0**(라우터 없는 기기라 alt 4건 SKIP — 종전과 같음)
- 단위·계약: 어댑터 30 · 런타임 26 · 판정 로그 57 · 자기점검 불변식 13 · 버스 프로파일 14 · 정규화 10 · 택시 요금 31 · 시각 32 · passes 6 · verify55 11 · plan 52 · plan_bike 13 · estimate 22 · concurrency 8
- 자기점검 탐침 **15,792**(불가 6,155 · 성립 8,089 · 판단불가 1,269 · 상한 279) · 치명 0
- `ruff check .`(develop CI 관문 F·E9) **0건**

## 6. 기기에서 회귀를 다시 돌리는 법

```powershell
cd C:\...\SKN32-FINAL-6TEAM
$env:PYTHONPATH = "final_project_cs"
python -m pytest tests/mobility -q                     # 데이터 없어도 됨(skip)
python -m app.modules.travel_ops.mobility_engine.verify_time --cases tests/mobility/real_legs_v1.json --check-expect   # 데이터 필요
python -m mobility_scripts.selfcheck_mobility --seeds "tests/mobility/*_legs_v1.json"                                  # 데이터 필요 · 느림
```
전체 묶음은 `scratch\_67\run67.ps1`(git 밖 · 담당자 기기)에 있다.

## 7. 알려진 한계(밝혀 둔다)

- **요금 커버 56%** — 지하철 요금은 탄 간선 전부 거리가 확정된 쌍(관광지 30역 쌍 432 중 243)에서만 값이 나온다. 10 km 넘는 쌍·9호선 등 거리 모르는 노선·버스 섞인 환승은 `fare_krw` 없음 → 코어 재계획이 그 후보를 「요금 미상」으로 떨어뜨리는 것은 정상 동작.
- **관광 구간 실측 0** — 실측 정답(26여정)은 담당자 통근·생활 동선(742·040·4319·3·7호선)이다. 여유 적중률 11/26·상한 초과 0 은 「이 노선들에서」다.
- 자전거는 추천하지 않는다 — `modes=["bike","walk"]` 로 여행자가 고른 때만 후보로 실린다.
- 환승 칸 안내는 뺐다(공공 원천 두 곳이 43% 서로 달라 안 믿는다) · 하차 칸은 API 계단·엘리베이터 칸만(POI 확정 뒤).
- GraphHopper(자동차·자전거 라우터)는 기기별 로컬 — 없는 기기는 해당 판정이 근거없음으로 나온다.

## 8. 코어 쪽에 이미 보낸 것

`팀장전달_모음.md`(12항목 · 통지 7 · 질문 2 · 제안 3) — 이 PR 과 별도. 코어 계약에 **새 키 0**(기존 칸 `starts_at`·`ends_at`·`eta_min`·`uses`·`label`·`planned` 만).
