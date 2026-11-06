---
type: handoff
title: 날짜 읽기 LLM 판단 전환 인계
status: draft
domain: travel
---

# 2026-10-26 날짜 읽기 LLM 판단 전환 — 인계

상세: [cs 기록](../../final_project_cs/wiki/records/reports/2026-10-26_llm-date-reading.md)

## 한 일
- 브랜치 `feat/past-date-guard-ext-20261026`(격리 worktree `scratch/mgr-merge-20261026-0045`, 앞 커밋 `337bcbd68` 위)에 커밋. push · 배포 · 로컬 서빙 교체 안 함(원격 0/2, x600 미반영, 로컬 서빙은 옛 프롬프트).
- 계획 읽기 에이전트 스키마에 `year_quote` · `date_form`(explicit_year · relative · yearless) — 순서 `date_quote → year_quote → date_form → date`. 프롬프트 날짜 절 재작성(예시 날짜는 `system_for` 가 오늘에서 계산).
- `agent_read._year_written`(본문 아무 줄의 연도 숫자) · 「숫자 없는 인용 = 상대」 정규식 판정 제거 → `_grounded_date`(인용 존재 · 필드 일치 · 달력 유효만). 연도 인용이 원문에 없는 explicit_year 는 연도 없는 날(확인 필요, 별도 메모).
- `dates`: 2/29 는 다음 윤년, 없는 날짜(2/30)는 모름.
- 실측(로컬 E4B, 합성 81문장): 개발 28/41 → 39/41, 보류1(일부 튜닝에 사용) 14/20 → 17/20, 깨끗한 보류2 12/20 → 15/20. 「다가오는 날을 지난 날로」 오류 10 → 1건.
- Codex 3회: 반영 · 미반영(강등 정책) 이유는 기록 「Codex 논의」.

## 남은 일
- 남은 실패 유형(2자리 연도 year_quote 비움, 「N째 주 X요일」, 「이번 주 일요일」 계산, 기념일, 합성 인용) — 새 칸을 넣은 학습 자료로 LoRA 재학습 검토(승인 필요).
- 모델이 날짜를 비웠을 때의 규칙 상대 날짜(`dates._relative_for_item`) 경로 정리 여부 결정.
- 로컬 서빙 반영(부모 승인 · 교체) · 실DB e2e(옮긴 e2e 대역 2개 포함) · 실화면 · x600 확인.
