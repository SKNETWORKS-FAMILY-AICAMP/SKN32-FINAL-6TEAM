---
type: handoff
title: 지난 일정은 삭제만 인계
status: draft
domain: travel
---

# 2026-10-26 지난 일정은 삭제만 — 인계

상세: [cs 기록](../../final_project_cs/wiki/records/reports/2026-10-26_past-edit-delete-only.md)

## 한 일
- 브랜치 `feat/past-edit-delete-only-20261026`(격리 worktree `scratch/past-edit-delete-only-20261026`, 부모 `337bcbd68`)에 커밋. push · 배포 · 로컬 서빙 교체 안 함(원격 0/2, x600 미반영, 로컬 미반영).
- 서버 `reopen.plan_edit`: 끝난 일정은 무엇을 고쳐도 `item_in_past`(삭제만). 채팅: 지난 일정 장소/고정/순서/시각 변경 거절 + 「새 일정으로 추가」 안내, 지난 고정 일정 빼기는 아직 길이 없다고 답함. 웹 `pastEdit`: 이름 · 장소 변경도 막고 숙박 `endDate` 반영.
- Codex 검토 2회(로그 `scratch/past-edit-delete-only-20261026-evidence/codex_review*.log`).
- 검증: 관련 Python 320/320, travel unit 7367 통과 · 실패 0, 웹 vitest 1183/1183 · tsc 0 · eslint 0.

## 남은 일
- 이미 지난(고정) 일정 삭제 경로(웹 회색 줄 · 채팅) — 명시적 삭제 id 목록안, 계약 결정 필요.
- 되돌리기 · 대안 교체 경로의 지난 일정 보존 확인.
- 실DB e2e · 실화면 · 웹 build.
- `feat/past-date-guard-ext-20261026`(동시 세션)과 합칠 때 index 3곳 · `chat_edit.py` 충돌 가능(각자 한 줄 · 작은 hunk).
