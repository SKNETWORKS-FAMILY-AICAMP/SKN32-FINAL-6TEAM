---
type: handoff
title: ST4F-719 인증·개인정보 독립 최종 검토 — 401 뒤 캐시 소유자 결함 격리 수정, 새 회귀 0, 보안 HOLD 유지
status: draft
domain: travel
---

# 진행 표

| 구역 | 상태 | 근거 |
|---|---|---|
| 1. 이어받기 | 완료 | 중단된 deleg_20889115 사본 `scratch/st4f719-blocker-independent-20261029/` 재사용(새 clone 0). 남은 프로세스 0. tsconfig 두 벌을 저장 원본으로 복구하고 cmp 일치 |
| 2. 독립 검토 | 완료 | 결함 1건(P1): A→401→B에서 A 화면 캐시 잔존. 판단 요청 4항목 판정은 보고서 참고 |
| 3. 격리 수정 | 완료(사본만) | `providers.tsx` 캐시 소유자를 401에서 유지. Vitest 1290/1290, tsc 0, build 0 |
| 4. 관문·회귀 | 완료 | PG 계약 367/367·DoD 26/26·쿠키 e2e 37/37·보안 124/125(HOLD). 검토자 시험 2/3→3/3, 실제 인증 Edge 19/19, 세션 9파일 82/82(기준 81/82), 전체 화면 921/958(기준 910/954), 단독 재실행 43/43 양쪽 → 새 회귀 0 |
| 5. 반영 | 대기 | 보안 HOLD가 정식으로 풀린 뒤 `role-manager` 담당이 반영. TeamFlow **ST4F-744**(task · review · high · 담당 `3rd_team_4_be`). 다시 조회해 담당·제목·본문 1000자가 일치함을 확인. 열린 이슈 106→107, 담당 없는 미완료 25건은 그대로 |

[보고서](../../final_project_cs/wiki/records/reports/2026-10-29_st4f719-independent-final.md) · [증거](../../final_project_cs/wiki/records/evidence/2026-10-29_st4f719-independent-final/)

# 반영 담당자에게

1. 기준 `656579fe3` 위에 `full-candidate.patch`(blocker-fix 증거)를 적용한 다음, 이 검토의 `providers-owner-survives-401.patch`를 적용합니다.
2. 검토자 시험 `indep-review-20261029.spec.ts`를 `tests/live`에 넣습니다. 이 시험은 identity-test fixture를 씁니다.
3. `web-auth.md` 45·51행의 「쿠키를 지운다」를 현재 동작(삭제 Set-Cookie 없음, 서버 행 폐기)으로 고칩니다.
4. 보안 HOLD가 풀리기 전에는 push·병합하지 않습니다.

# 남은 것

- 폐기한 키로 받은 표가 TTL 60초 안에서 교환되는 문제(P3): 교환 때 원래 키가 살아 있는지 확인하는 것을 후속으로 권고합니다.
- guest→member 설문 초안 삭제는 제품 결정 사항입니다.
- 디스크: 이 사본은 약 5.5GB이고, 그 안의 `base.tar`가 380MB입니다. 삭제는 사용자 승인 대상이라 남겨 두었습니다. 반환할 때는 `python tools/disk_guard.py release --dest <사본> --owner <작업자>`를 씁니다(이 사본은 guarded_clone으로 만들지 않아 등록돼 있지 않을 수 있습니다).
