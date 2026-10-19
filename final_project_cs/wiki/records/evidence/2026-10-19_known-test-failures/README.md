---
type: evidence
title: 알려진 시험 실패 35건 원인 조사 — 실행 결과 · 조사 도구 보존본
date: 2026-10-19
domain: travel
---

# 알려진 시험 실패 35건 원인 조사 — 실행 결과 · 조사 도구 보존본

[조사 보고서](../../reports/2026-10-19_알려진시험실패_원인조사.md)의 근거다. 시험에 쓴 임시 사본 · 시험 DB 는 2026-10-20 사용자 승인으로 지웠고, 남길 것은 여기로 옮겼다.

## 판별 실행 결과 (파일 하나씩 차례로, 이 PC · conda PostgreSQL 16 · 시간대 서울)

| 파일 | 판 | 무엇 |
|---|---|---|
| `summary_r1.txt` | role-manager `b9124602` (git 저장소 사본) | 대상 19파일 |
| `summary_dev.txt` | develop `f10bd172` | role-manager 에서 실패한 15파일 |
| `summary_4cedab22.txt` · `summary_faabcd92.txt` | 오라클 합치기 직전 · 직후 | 12파일 |
| `summary_0d73ca4d.txt` · `summary_88defd2b.txt` · `summary_7c255f38.txt` | 남부터미널 수정 전후 · 장소 종류 먼저 판정 | 4파일 |

## 지운 로그에서 옮겨 적은 값 (조사용 시험 · 플러그인 출력)

- 대안 묻기(`test_watch_relaxed`): 추적 플러그인 — `offer_relaxed(...) -> None`(후보 함수를 하나도 부르기 전). `watch_relaxed` 벽시계만 `2026-09-23T09:00+09:00` 로 고정 → 11 passed.
- 같은 판 두 번 읽기(`test_intake_direct_schedule` · `test_intake_autofix_dry_run`): 차이는 `risk_checked_at` · 항목 `risk.checked_at`(예 `2026-10-19T22:22:30…`, 위험 코드 `past`). `intake.risks` 벽시계 고정 → 15 passed.
- 창덕궁 순위(`test_intake_experience_tiers`): 순서 `광화문 어린이공원(similar_experience, 410m) → 북악 둘레길(861m) → 창덕궁(same_kind, 1234m)`. 창덕궁 `fits=false · status=warn` · 휴무 줄 「휴무·운영 조건을 확인해 주세요 (후원은 따로 예약해야 들어갈 수 있어요)」. 공원 둘은 운영시간 `unknown`.
- 「시험 기념관」(`test_intake_catalog_names`): `kind=lodging · place_state=unresolved`(계획 줄 `15:00 시험 기념관 체크인`).
- 숙소 든 여행 등록(`test_intake_stay_lines`): N서울타워 줄 「10:30에 열어요 · 09:30 시작은 일러요」(warn) → `needs.items=1` → 준비 안 됨.
- 이름 말한 곳 바꾸기(`test_decision_destination_condition_web`): 대화 시각 2030-01-01 → `edit_refused`(지난 일정), 여행 날 09:00 → `adjusted` · 「목적지를 통인시장(으)로 바꿨어요 … 확인 중」 · `pick.mode=change`.
- 남부터미널 재생: 기본 실행 `UnicodeDecodeError: 'cp949'`, `PYTHONUTF8=1` → 1 passed.
- live 3파일: 기본 옵션으로 모으면 `no tests collected (3 deselected)`.

## 조사 도구 (`tools/`) — 저장소 코드는 바꾸지 않는다

- `kf_trace_plugin.py` — `-p kf_trace_plugin` 으로 넣으면 대안 묻기 관련 함수의 호출 결과를 찍는다.
- `kf_clock_plugin.py` — `KF_MODULES`(모듈 경로) · `KF_FIXED_NOW`(시각)로 그 모듈의 `datetime.now` 만 고정한다.
- `test_zz_kf_probe.py` — 위 값들을 찍은 조사용 시험. 쓰려면 사본의 `tests/e2e/` 에 넣는다(이 폴더에서는 수집되지 않는다).
- `run_files_one_by_one.sh` · `ci_like_env.sh` — 파일 하나씩 돌리는 스크립트와 CI 와 같은 환경 변수. 경로 · DB 주소는 지운 사본 기준이라 쓰기 전에 바꾼다. 쓰는 법은 [시험 재현 방법](../../reports/2026-10-19_로딩설문_시험_재현방법.md) §1~§4.
