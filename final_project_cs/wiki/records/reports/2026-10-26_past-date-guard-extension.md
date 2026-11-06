---
type: report
title: 과거 날짜 가드레일 확장 — 연도 없는 날짜 · 확인 단계 · 채팅 되묻기 · 일정 추가/수정
status: draft
domain: travel
---

# 2026-10-26 과거 날짜 가드레일 확장

작업 위치: 격리 worktree `scratch/mgr-merge-20261026-0045`, 브랜치 `feat/past-date-guard-ext-20261026`(기준 `integ/manager-develop-ui-20261026-0045` HEAD `0239cef98`). 원본 `C:/_proj/final_workspace` 는 건드리지 않았다. 커밋까지만, push · 배포 · 로컬 서빙 교체 없음. 실DB · 실모델 · 외부 호출 0(격리 runner 가 socket · psycopg 차단).

## 사용자 확정 요구와 결과

| # | 요구 | 확인한 현재 코드 | 변경 |
|---|---|---|---|
| 1 | 연도 없는 날짜 = 오늘 이후 처음 오는 그 날(오늘 포함), 연도 명시 과거만 과거. 모델 구조화 날짜 + 원문 인용으로 판정 | 규칙 읽기(`--MM-DD` → `dates._fill_year`)는 맞음. **모델 읽기(`agent_read.ground`)는 모델이 붙인 연도를 그대로 믿어** 「10월 5일」을 올해(지난 날)로 내면 `written`(명시 과거)이 됐다 | `ground`: 모델 날짜의 연도 숫자가 날짜 인용·본문 어디에도 없고 인용에 숫자가 있으면(상대 날짜 아님) `--MM-DD` 로 바꿔 기존 `resolve_dates` 의 `year_filled`(오늘 포함 다가오는 날, 확인 필요 배지)를 탄다. 프롬프트 · 스키마는 그대로(가르친 E4B 입력 유지). 채팅 넣기(`chat_edit._read_adds`)도 같은 `_fill_year` 로 채운다(전에는 이 값에서 `ValueError` 로 죽었을 경로) |
| 2 | 전부 과거 계획이면 확인(review) 단계에 머문다(서버·웹), 일부 과거는 통과 | 10-25 hotfix 의 `review.admission_dates`(ready=false) · `_create_trip` 새 여행 분기 422 `all_dates_in_past` 가 이미 있음. 웹은 `needs.total>0` 이면 「다시 제출」만 나오고 `intakeRegistrationReady` 가 `review.ready` 를 따른다 | 제품 변경 없음. 웹 회귀 시험(전부 과거 review → 등록 불가) 추가. 서버 기존 시험 13/13 유지 |
| 3 | 채팅 수정이 과거 날짜면 「오타 아닌가요?」 + 가장 가까운 미래 날짜 버튼, 기존 choices 계약 재사용 | 시각 옮기기는 `time_in_past` 로 거절만, 넣기는 「완료」 단계 `item_in_past` 로만 막힘 | `chat_edit.past_time_refusal`: 코드 `time_in_past` 유지 + `choices`(같은 시각, 앞으로의 여행 날짜 → 없으면 오늘·내일, 최대 가드레일 `travel.chat_edit.past_date_choices`=3) · `choices_title`「혹시 오타 아닌가요?」. 시각 옮기기(`edit_intent.time_ops` start) · 넣기(anchor_time) · 읽기 에이전트 넣기에 적용. `trip_desk` 는 choices 를 실은 거절을 `clarify` 로 답한다. 기존 `chat_reply` allowlist(`choices`·`choices_title`)로 저장 |
| 4 | 추가/수정: 새로 넣거나 바꾸는 날짜·시각은 지금 이후만, 지난 일정은 날짜·시각 그대로인 수정·삭제 허용, 과거 신규 불허, 진행 중/미래 1개 이상 유지 | `reopen.plan_edit`: 바뀐 일정의 원래/새 끝 ≤ 지금, 추가의 끝 ≤ 지금, 지난 일정 삭제를 모두 `item_in_past` | `plan_edit`: 추가는 시작 < 지금(분 단위)이면 past, 바뀐 일정은 날짜·시각을 바꿨을 때만 검사(이미 끝난 일정의 시각 변경 · 시작을 지금 이전으로 · 끝을 지금 이하로), 날짜·시각 그대로인 지난 일정 수정과 지난 일정 삭제는 허용. 새 `no_upcoming`(원래 진행 중/미래 일정이 있었는데 새 판에 0) → `reopen_commit` 422 `no_upcoming_items`. 웹: `model.pastEdit`(같은 규칙) — 수정 모드(`TripEditMode.clock`)에서만 「직접 고치기」 · 일정 추가 폼이 보내기 전 막고, 서버가 최종 판정. 오류 문구 `item_in_past` · `no_upcoming_items` 추가 |

## Codex 검토

설계안 `scratch/past-guard-ext-20261026/DESIGN_v1.md` 를 `codex exec -s read-only`(codex-cli 0.163.0)로 보냈으나 **실패**: `codex login status` = `Not logged in`, 실행은 `401 Unauthorized`(로그 `codex_run_v1.log`). 로그인은 사용자 자격 증명이 필요해 하지 않았다. 따라서 Codex 의견은 **반영되지 않았다**. 대신 자체 점검으로 반영한 것: ① 웹 숙박(끝이 시작보다 이른 일정)은 화면에서 「끝났다」를 단정하지 않는다 ② 넣기 비교는 분 단위 내림(「지금 바로」 허용) ③ 기존 `time_in_past` · `item_in_past` 코드를 유지해 웹 · 기록 호환.

## 남은 것 · 한계

- **지난(고정) 일정의 이름 수정 · 삭제 경로는 아직 없다.** 수정 접수는 지난 일정을 넣지 않는다(`fixed_reason=past`). 서버 규칙은 허용으로 바뀌었지만 웹 · 채팅에서 지난 일정을 고를 길이 없어 실제로 쓰이는 경우는 「수정 화면을 연 뒤 시간이 흘러 지난 일정이 된 것」뿐이다. 지난 일정을 접수에 넣되 날짜 · 시각만 잠글지(안 a), 고정 일정 전용 이름 · 삭제 동작을 둘지 결정이 필요하다.
- 모델 날짜 연도 판정은 연도 숫자가 원문 어딘가에 있으면 명시로 본다(가격 「2026원」 같은 우연 일치는 명시로 남는다).
- 모델이 읽은 연도 없는 날짜는 이제 `year_filled`(확인 필요)로 표시된다 — 규칙 읽기와 같아졌지만 화면 배지가 늘 수 있다.
- 채팅 다중 넣기는 하나라도 지난 때면 하나도 넣지 않고 되묻는다.
- 감시 · 대안 교체 · 되돌리기 · MCP 쓰기 등 다른 판 쓰기 경로는 이번 범위 밖(`web-screen-api.md` ⑤ 그대로).
- 실DB e2e(`tests/e2e/test_trip_reopen.py` 등) · 실화면 · 실모델 미실행.

## 검증(실행 결과)

격리 runner `scratch/past-guard-ext-20261026/run_isolated.py`(socket · psycopg 차단, `PASTEXT_SOURCE_ROOT` 출력), Python 3.12 venv(`date_risk_env_312`, 일부 `travel-writing-s1-venv`).

- RED(고유 로그): `red-yearless.log` 2 실패 · `red-chat-typo.log` 5 실패 · `red-reopen-past.log` 5 실패 · `red-web.log` 5 실패. 「완료」 거절 시험 2건은 구현 뒤 작성(RED 없음).
- 관련 묶음 최종: **303/303 = 100%**(`focused-final.xml`, 기준 283 + 신규 20). `test_all_past_dates.py` · `test_all_past_confirm_api.py` 포함.
- `tests/unit/travel` 전체: 7383 passed / 134 skipped / 458 deselected, 실패 2 · 오류 6 — **8건 모두 runner 의 DB 차단**(`network/database denied`), 7391/7399 실행 중 차단 외 실패 0.
- `tests/architecture` · `contract` · `security`: 617 passed, 실패 13 · 오류 6 — **19건 모두 DB 차단**.
- ruff F·E9(변경 Python 9파일) 통과, `git diff --check` 통과.
- 웹(`frontend/apps/web`, 새 `npm ci`): vitest 전체 1차 1181/1181, 마지막 수정 뒤 1180/1181(`tokens.test.ts` 5초 시간 초과 1건 — CSS 미변경, 단독 재실행 통과), `past-edit.test.ts` 6/6 · `error-text.test.ts` 6/6, `tsc --noEmit` 0, 변경 파일 eslint 0. `npm run build` · 브라우저 시험 미실행.
