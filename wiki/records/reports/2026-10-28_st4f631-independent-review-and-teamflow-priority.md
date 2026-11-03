---
type: report
title: ST4F-631 최신 role-manager 독립 리뷰 · 통합 검증 + TeamFlow 미해결 우선순위
description: 팀 role-manager efc6fca4 기준 ST4F-631 반영 확인(push 완료 상태), 단위·DB e2e 재검증, 미해결 117건 중 버그 17건 최신 코드 대조와 우선순위. 트래커·원격 쓰기 0
status: done
domain: travel
impl_scope: cs
---

# ST4F-631 독립 리뷰 · 통합 검증 + TeamFlow 우선순위 (2026-10-28)

## 기준

- 팀·개인 `role-manager` = `efc6fca47c76ba12cbf6557358b458c025c630b4`(`git ls-remote` 두 원격 같음). develop `36ba4c2fc` · main `e88e01925`.
- 작업 위치: Hermes scratch `st4f631-review-20261028/wt`(detached worktree, scratch 저장소 `allpast-hotfix-20261025-2005/repo` 에 fetch). 원본 작업 폴더 코드 · index · 원격 · TeamFlow 쓰기 0.

## 1. ST4F-631 후보 상태 — 이미 통합됨

| 항목 | 결과 |
|---|---|
| 후보 `4f899ecd3` ↔ role-manager `6833b1153` | patch-id 같음(`8ca35c2c…`) — 05:20 push `4fee819c` 묶음으로 들어감 |
| `6833b1153..efc6fca4` 사이 `assemble.py` · 새 시험 변경 | 0 |
| 첫 patch `st4f631/ST4F-631.patch`(sha256 `2b91b325…`, ffb5 기준 1차) | **대체됨 — 다시 적용하지 않는다**(2차 구조 판단이 상위 호환) |
| develop · main 포함 여부 | 없음. `merge-tree` 모의 cherry-pick 은 둘 다 충돌 0(시험은 안 돌림) |

## 2. 독립 리뷰(코드)

- `_title` 과 `rules.read_plan` 모두 `str.splitlines()` 로 줄을 나눠 줄 번호가 일치한다(CRLF · U+2028 탐침 포함).
- 판단 근거는 `items[*]` claim 줄과 `read_lines` 의 날짜/일차 머리줄뿐, 낱말 목록 없음. 고객이 고친 `trip.title` 은 먼저 쓴다.
- 탐침 17건(efc6fca4): 일정 사이 메모 · 화살표 나열 · 여러 원문 뒤 메모 → 「내 여행」, 제목 첫 줄 · 장소 이름이 든 제목 · 인원/박일 제목 · 「10월 5일 서울 가족여행」 · 영어 제목 → 유지. 기대와 다른 것 0.
- 남은 알려진 한계(보고서와 같음, 회귀 아님): 일정 **앞** 메모(「한복 입고 다닐 거예요」), 표 머리(「날짜,시간,장소」), 문단 첫 문장이 제목이 된다. 고치려면 읽기 에이전트가 `trip.title` 을 내는 계약 결정이 필요 — 별도 티켓 후보.
- 판정: **차단 사유 없음.** `read_plan` 을 제목용으로 한 번 더 부르는 비용은 정규식 기반이라 무시 가능(미측정).

## 3. 통합 검증(efc6fca4, 격리)

| 묶음 | 결과 |
|---|---|
| `tests/unit/travel/test_intake*.py` 75파일(`not live/db/slow`, 소켓·DB 차단 runner, Py 3.12) | 1,028/1,028 = 100% (새 제목 시험 포함) |
| DB e2e `tests/e2e/test_trip_intake_api.py`(승인된 비교 DB `gugu_replay_improved_20261025`, 고유 tenant) | 21/21 = 100%, 「내 여행」 DB 제목 단언 포함. 전후 표 23개 행 수 · digest · tenant 변화 0 |
| x600 실서버 test20 제목 | **미실행** — 운영 쓰기가 필요해 범위 밖 |

## 4. TeamFlow 미해결 우선순위(MCP 읽기만)

`list_issues`(프로젝트 84): todo 48 · inprogress 20 · review 49 = 미해결 117. 그중 버그 todo 17건을 efc6fca4 와 대조했다. ST4F-631 은 TeamFlow 에서 아직 `todo`.

| 순위 | 키 | 판단 | 다음 일 |
|---|---|---|---|
| 0 | 631 · 685 · 709 | 코드가 role-manager 에 들어감(`6833b1153` · `b8c191b6a` · `ede8d85a9`+`c91289b16`) | TeamFlow → review(**사용자 승인 필요**). 631 은 x600 test20 확인 뒤 done |
| 0 | 678 · 692 · 694 | K 대조의 해결 근거 유지(관련 파일 ffb5 이후 변경 없음) | 같이 review 로 정리(승인 필요) |
| 1 | **710** (LB-04) | **efc6fca4 에서 재현** — 같은 날 체크인 15:00 · 시각 없는 체크아웃 → 끝 11:00 같은 날(거꾸로 된 숙박). `assemble._stays` 의 `"99:99"` 비교 | TDD 수정 후보(결정적 · 작음 · 고객 데이터 결함). 같은 날 체크아웃을 다음 날로 볼지 거절할지 결정 필요 |
| 2 | 711 (LB-09) | `intake-review/` 웹 코드 ffb5 이후 변경 없음 — 미해결 | mock 서버 Playwright 로 재현 → 재전송 안내 |
| 3 | 589 · 554 | x600 운영(관광공사 예산 소진 · 채팅 지연) — 코드 대조 불가 | 운영 읽기 점검(예산 설정 값) |
| 4 | 504 | `test_conversation_resume.py` 변경 없음, 흔들림 | 격리 DB 반복 실행으로 시험/경쟁 구분 |
| 5 | 653 | Playwright 실행 확인 전 판정 보류 | mock 화면 시험 1건 실행 |
| 6 | 555 · 556 | develop(Oracle) 서버 문제 | develop 서버 점검 때 |
| 7 | 597 · 547 · 521(P3) | 원장 자료 · 시험 기반 문제 | 낮음 |

## 증거(저장소 밖)

Hermes scratch `st4f631-review-20261028/`: `probe.py` · `ev/probe_head.json` · `probe710.py` · `ev/intake_unit.{log,xml}` · `db/ev/db-intake_e2e/`(pre/post/cmp) · `tf_read.mjs`(읽기 도구만 허용) · `tf_issues.json`(토큰 없음).
