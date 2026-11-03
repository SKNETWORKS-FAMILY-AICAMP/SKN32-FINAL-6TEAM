# 두 응답 계약 분리 — 일정 설명·배치 이유·답 불가 원인 안내 인계 (2026-10-29 KST)

- **기준**: 팀 SKN · 개인 A-COP `role-manager` = `fab3da50a`(두 원격 재확인). 원본 작업 폴더 코드 무수정.
- **후보 커밋**: `738aa9ad9`(push 0 · x600 0 · 로컬 서빙 0). worktree `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/schedule-explain-impl-20261029/wt`, patch `…/patch/0001-feat-chat-split-program-conversation-answer-contract.patch`(sha256 `527ea0ab…616e`).
- **TeamFlow**: ST4F-742(task · review · 담당 `3rd_team_4_be` = role-manager 매니저), 재조회로 담당·본문 935자 일치. 기존 담당 없는 미완료 25건 불변.
- **바꾼 것**: `answer_contract.py`(새) — 프로그램 계약(모델 호출은 스키마 구조화 답만, 유료 경로 가짜 클라이언트 시험) / 대화 계약(fact `day` 설명: 순서 · 바로 이웃한 이동 · 저장된 배치 이유만, 기록 없으면 지어내지 않았다고 밝힘 · 해석 실패: 원인 4분류 + 다음 할 일 · 규정 미일치: 다음 할 일). `decision_unit` SYSTEM·스키마 · 공개 상태 · DB 무변경.
- **검증**: 새·관련 시험 112/112 = 100%, RED 5/24(연결 전), 변이 15/15 = 100%, 빠른 관문 10,993건 새 실패 0 · 잃은 시험 0(실패 1 = 기존 보안 HOLD `test_no_infra_in_tracked_files` ← ST4F-728 XML, 기준 동일), contract+architecture 520/520(보고서 포함 최종 트리), ruff 통과. Claude Opus 5.5 · Codex 검토 4회 → 4차 둘 다 승인.
- **비용**: 제품 모델 E4B 0 · 유료 0. 개발 도구 Claude $1.60(4회), Codex 4회(토큰 63,296). 보낸 것은 공개 코드 · 합성 자료뿐.
- **보고서**: [final_project_cs/wiki/records/reports/2026-10-29_answer-contracts-split.md](../../final_project_cs/wiki/records/reports/2026-10-29_answer-contracts-split.md) · 계약 문서는 후보 트리 `final_project_cs/wiki/external/answer-contracts.md`.

## 다음 할 일

1. 통합(role-manager 담당): 보안 HOLD 가 정식 승인으로 풀린 뒤, 두 원격 tip 이 `fab3da50a` 그대로면 `738aa9ad9` 를 ff push(움직였으면 새 tip 위 `apply -3` + 빠른 관문 재실행) → x600 배포 확인 → ST4F-742 상태 갱신.
2. (승인 필요) E4B 실모델로 「일정 설명」 표현 세트의 `day` vs `ask_policy` 라우팅 비율 측정 — 이 후보는 프롬프트를 바꾸지 않아 비율은 그대로 `[미측정]`.
3. (승인 필요) `general_requests` 추천 이유 확장 — 프롬프트 변경 + E4B · 유료 재측정(비용 근거 먼저).
