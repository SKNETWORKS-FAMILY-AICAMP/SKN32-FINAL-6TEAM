---
type: handoff
title: 일정 설명 · 배치 이유를 대화 모델이 쓴다(explain_writer) — 후보 4bc2d9080
description: answer-contracts-split(738aa9ad9)의 템플릿 한계를 고쳐 E4B 가 검증된 사실만으로 설명 · 추천 이유 · 실패 원인을 쓰게 한 후보, 실측 · 관문 · 독립검토 7회 결과
status: draft
domain: travel
impl_scope: cs
---

# 일정 설명 작성 모델 후보 (2026-10-29)

## 상태
- 후보 커밋 **`4bc2d9080`** — 브랜치 `feat/schedule-explain-writer-20261029`(격리 작업 폴더 `scratch/schedule-explain-impl-20261029/wt`, 원격 없음). 부모 `738aa9ad9` → `fab3da50a`.
- **대상 manager 브랜치: `team/role-manager`(현재 끝 `fab3da50a`, ls-remote 확인)** — 이 후보는 그 위 2커밋이라 빨리 감기로 반영 가능. **push 0**(이 세션은 반영하지 않았다; 개인 `origin` 은 이 셸에서 인증 실패).
- 보안 관문: 기존 HOLD 그대로 — `tests/security/test_no_infra_in_tracked_files` 의 유일한 위반은 `wiki/records/evidence/2026-10-29_st4f728-guest-logout/security-ready.xml`(기준에도 있음). 이 후보 파일은 위반 0.

## 무엇을 했나
- 신규 `conversation/explain_writer.py`: 서버 확인 사실(F1…) → E4B 구조화 답(문장 + 근거 id) → 서버 검사 → 통과 문장만 고객. 실패 = 원인 한 줄 + 시간순 목록(조용한 대체 없음).
- `route` 모드: 규정 근거 0 인 `ask_policy` 답 · 대상 없는 detail/description 을 같은 사실로 schedule/other 재판단(「왜 이렇게 짰어?」 오분류 해소). `decision_unit` SYSTEM · 스키마 · `edit_intent` 는 `fab3da50a` 와 바이트 동일.
- `FailoverChat.local_only()` · `travel.chat_explain*` 가드레일(paid_failover false). 유료 실호출 0.
- 계약 `wiki/external/answer-contracts.md` 1번 · 보고서 `wiki/records/reports/2026-10-29_explain-writer-llm.md`.

## 근거
- 실 E4B(lease `schedule-explain-llm` 안에서만, 서버 정지 0): 운영 모양 경로 g4 8행 — 채택 5 · other 1 · 정당한 거절 2(범위 일정 누락 · 지어낸 배치 이유). 검사 전 원문 40행(f1 · f2 · g2 · g3 · g4) 최종 검사 재판정 불변.
- 단위 183 passed(explain_writer 102 포함). 변이 44+ 모두 죽음. 빠른 관문 cand11: 11,096건, cand4 대비 잃음 0 · 새 실패 0(실패 1 = 위 보안 HOLD).
- 독립 검토(Claude opus · Codex read-only, 코드 원문만) 7회 — 1~6차 REQUEST_CHANGES(우회 반례마다 시험 고정 후 수정), **7차 둘 다 APPROVE**. 7차 후속 2건(인과 「라서」 추가 · 야외 반례 시험 고정)도 반영 후 커밋.
- 기록: `scratch/schedule-explain-impl-20261029/review2/`(r1~r7 프롬프트 · 결과 · 응답표 · mutations*.txt · e4b_*_rows.json), `llm/out/*.json`.

## 남은 일 · 위험
- manager 반영(`team/role-manager` 빨리 감기)은 관리자 결정 — 보안 HOLD 해제 여부와 함께.
- 해석 → 작성 끝-끝은 이 기계 GPU 처리량(기준의 약 1/4)에서 제품 시한으로는 해석 단계가 넘칠 수 있어 측정용 시한으로만 확인.
- 검사는 낱말 · 마디 수준(보고서 「남은 위험」): 새 장소 이름 · 시각 맞바꾸기 · 다음 칸 뒤집기 · 낱말 비교 우연 통과. 보수적 거절(미끼 질문의 정직한 답 · 이유 마디의 시각 · 이름 없는 요약). route 판단의 긴 여행 사실 과다.
- 유료 경로 엄격 스키마 수용은 실호출 금지라 미검증(비용 상한 검증 뒤).
