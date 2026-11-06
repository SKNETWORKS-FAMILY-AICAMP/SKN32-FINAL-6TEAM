---
type: handoff
title: 과거 날짜 가드레일 확장 인계
status: draft
domain: travel
---

# 2026-10-26 과거 날짜 가드레일 확장 — 인계

상세: [cs 기록](../../final_project_cs/wiki/records/reports/2026-10-26_past-date-guard-extension.md)

## 한 일
- 브랜치 `feat/past-date-guard-ext-20261026`(격리 worktree `scratch/mgr-merge-20261026-0045`, 기준 `0239cef98`)에 커밋. push · 배포 · 로컬 서빙 교체 안 함(원격 0/2, x600 미반영, 로컬 미반영).
- 요구 1: 모델(E4B) 날짜의 연도가 원문에 없으면 `--MM-DD` → 오늘 포함 다가오는 날(`agent_read.ground`). 채팅 넣기도 같은 해석.
- 요구 2: 서버 · 웹 모두 이미 확인 단계에 머문다 — 제품 변경 없이 웹 회귀 시험 추가.
- 요구 3: 채팅 지난 날짜 → 「혹시 오타 아닌가요?」 + 가장 가까운 앞으로의 날짜 `choices`(가드레일 `travel.chat_edit.past_date_choices`).
- 요구 4: `reopen.plan_edit` 규칙 교체(지금 이후만 · 지난 일정 이름 수정/삭제 허용 · 마지막 진행/미래 일정 보호 `no_upcoming_items`) + 웹 수정 모드 사전 검사.
- 검증: 관련 Python 303/303 = 100%, travel unit 7383 통과(비통과 8 = DB 차단), 관문 617 통과(비통과 19 = DB 차단), 웹 vitest 1180/1181(시간 초과 1, 단독 재실행 통과) · tsc 0 · eslint 0.

## 남은 일
- Codex 설계 검토 **미수행** — codex CLI 미로그인(401). 로그인 후 `DESIGN_v1.md` 로 다시 검토 필요.
- 지난(고정) 일정을 웹 · 채팅에서 고르는 이름 수정 · 삭제 경로 결정 · 구현.
- 실DB e2e(`test_trip_reopen.py` 등) · 실화면 · 웹 build · 실모델 확인.
