# 인계 — ST4F-631 메모 줄이 여행 제목이 되던 결함 (2026-10-28)

한 일:
- 팀 role-manager `ffb5fb1b5` 를 scratch detached worktree(`Hermes scratch/st4f631/wt`)로 꺼내 TDD 로 고쳤다. RED 5 → GREEN 67/67, 접수 unit 1044/1044. `tests/unit` 전체에서 실패 475건이 났는데, 수정 전 코드로 다시 돌린 결과와 nodeid 집합이 같아 이번 수정이 만든 회귀는 0이다.
- 후보 patch: `Hermes scratch/st4f631/ST4F-631.patch`(assemble.py `_title` + 새 시험 1파일). 증거는 `st4f631/evidence/`(red/green/wide2/unit/base67 로그·XML, 시험 원문 51개 전후 비교).
- 보고서: [ST4F-631 보고](../../final_project_cs/wiki/records/reports/2026-10-28_ST4F-631_메모줄_여행제목.md)

부모가 할 일:
- 이 patch 를 role-manager 에 커밋할지 정한다. **push 0** 이다.
- 커밋한다면 DB e2e 와 x600 에서 test20 제목이 「내 여행」으로 나오는지 확인한다. TeamFlow 갱신도 남아 있다.
- 일정 앞에 쓴 메모와 표 머리가 제목이 되는 것은 계약 결정이 필요한 별도 일이다.

추가(2026-10-28 03:50): role-manager `8a1feae8` 위 커밋 후보 `4f899ecd3`(worktree `Hermes scratch/st4f-rm-20261028-0336/rm`, push 0). 판단 근거를 구조(`items[*]` claim 줄 · 읽은 날짜/일차 머리줄 번호 · 원문 순서)로 고침 — Codex 1차 BLOCK → 2·3차 COMMIT_OK. RED 8/14 → 14/14, 빠른 관문 10,563/0. C12 후속 `129741ec3` 은 `80863b6f3` 로 이미 반영(patch-id 같음). [보고](../../final_project_cs/wiki/records/reports/2026-10-28_ST4F-631_메모줄_여행제목.md)
