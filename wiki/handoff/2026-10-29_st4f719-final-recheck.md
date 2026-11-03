---
type: handoff
title: ST4F-719 최종 재검증 — P1 확인, 폐기 키 이관 표(P3) 격리 수정, 문서 정정, 새 회귀 0, 보안 HOLD 유지
status: draft
domain: travel
---

# 진행 표

| 구역 | 상태 | 근거 |
|---|---|---|
| 1. 이어받기 | 완료 | 같은 사본 `scratch/st4f719-blocker-independent-20261029/`을 재사용했습니다(새 clone 0). providers `83f6e69d…`를 확인했습니다. 남은 프로세스 0, tsconfig 복구 cmp 일치 |
| 2. P1 재검토 | 완료 | 소유자 유지 규칙과 늦은 응답·mutation 경합을 점검했습니다. 막는 결함 0, P3 관찰 1건(id 키 늦은 쓰기 4곳) |
| 3. 격리 수정 | 완료(사본만) | 폐기 키 이관 표는 410으로 막습니다. `web-auth.md` 45·51행과 이관 절을 고쳤습니다. `cache-owner.ts`를 따로 빼고 Vitest 9건을 더했습니다 |
| 4. 관문 | 완료 | 계약 367/367 · DoD 26/26 · 쿠키 e2e 38/38 · 보안 124/125(HOLD). Vitest 1299/1299 · tsc 0 · build 0. Edge 22/22 · 세션 9파일 82/82 · 탐침 24/25·10/10. 새 e2e는 RED(201)에서 GREEN으로 바뀌었고, 변이 4/9 검출 |
| 5. 반영 | 대기 | TeamFlow **ST4F-745**(task · review · high · 담당 `3rd_team_4_be`). 다시 조회해 제목·본문이 일치함을 확인했습니다. 열린 이슈 107→108, 담당 없는 미완료 25건은 그대로 |

[보고서](../../final_project_cs/wiki/records/reports/2026-10-29_st4f719-final-recheck.md) · [증거](../../final_project_cs/wiki/records/evidence/2026-10-29_st4f719-final-recheck/)

# 반영 담당자에게

1. `656579fe3` 위에 `full-candidate.patch`를 적용하고, 이어서 `providers-owner-survives-401.patch`를 적용합니다. 마지막으로 `final-review-fix.patch`(SHA-256 `67fbfe22…5edc`, 6파일)를 적용합니다.
2. 이번 patch에 문서 정정(앞 인계 3항)과 fixture 없는 캐시 시험이 들어 있습니다. `indep-review-20261029.spec.ts`는 원하면 `tests/live`에 넣습니다.
3. 보안 HOLD(ST4F-728 `security-ready.xml`)가 풀리기 전에는 push·병합하지 않습니다.

# 남은 것

- id 키에 늦게 쓰는 mutation 4곳(`intake-review` edit, `trip-edit` reopen, `trip-screen` 재개, `useServerReview` apply)에 query 동일성 가드를 넣는 후속 작업을 권고합니다(P3).
- 디스크: 이번에 늘어난 것은 약 102MB입니다(`.next-indep-prod` 96MB 갱신, `final-recheck` 1.3MB, `tmp-pw-final*` 4.8MB). 사본 전체는 약 5.5GB입니다. C: 여유는 174GB로, 목표 400GB에 못 미칩니다. 삭제는 사용자 승인 대상이라 하지 않았습니다. `disk_guard inventory`에서 미등록 디렉터리는 0입니다.
