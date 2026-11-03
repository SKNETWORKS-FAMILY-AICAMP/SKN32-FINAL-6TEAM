---
type: report
title: ST4F-719 최종 재검증 — P1 캐시 소유자 수정 확인, 폐기 키 이관 표(P3) 격리 수정, 인증 계약 문서 정정, 새 회귀 0, 보안 HOLD 유지
status: draft
domain: travel
---

# 판정

2026-10-29 KST. Claude(Hermes 하위 세션)가 [독립 최종 검토](2026-10-29_st4f719-independent-final.md)의 P1 수정(`providers-owner-survives-401.patch`)과 남은 항목을 다시 검증했습니다. 같은 격리 사본 `scratch/st4f719-blocker-independent-20261029/`을 재사용했고 새 clone은 0건입니다. 기준은 `656579fe3` + `full-candidate.patch` + 위 patch입니다(providers `83f6e69d…139a` 확인).

**결론: P1 수정은 맞습니다. 남은 결함 2건(P3 1건, 문서 1건)은 사본에서 고쳤고 새 회귀는 0건입니다.** 보안 HOLD(`test_no_infra_in_tracked_files` ← ST4F-728 `security-ready.xml`)는 다른 담당의 보호 XML이라 유지합니다. 필수 관문은 2/3입니다. 커밋·push·배포·운영 반영은 0건입니다. TeamFlow **ST4F-745**(담당 `3rd_team_4_be`)를 만들었습니다.

# P1 수정 재검토 (경합)

- 401 뒤에도 소유자를 유지하는 규칙을 다시 따져 보았습니다. A→401→B, A→401→401→B, 다른 탭 종료 신호(`retired`)는 모두 캐시를 비웁니다. 첫 게스트, 같은 scope 재조회, A→401→A는 화면을 유지합니다.
- `client.clear()`는 TanStack v5에서 진행 중인 query를 조용히 취소합니다. 그래서 A의 늦은 조회 응답은 B의 캐시에 들어가지 않습니다.
- 범위가 없는 키에 늦게 쓰는 mutation(지원 문의, 소셜 연결, 텔레그램, 웹훅, 프로필, 지킴이)은 이미 query 동일성을 검사합니다. trip-chat에는 세션 가드가 있습니다.
- id 키에 쓰는 일부 경로는 동일성 검사가 없습니다(`intake-review` edit, `trip-edit` reopen, `trip-screen` 재개, `useServerReview` apply). 이 경로가 문제가 되려면 A의 mutation이 계정 전환을 가로질러 진행 중이어야 하고, 같은 탭이 A의 id 화면에 머물러 있어야 합니다. **P3 관찰로만 남기고 고치지 않았습니다.**

# 고친 것 (사본만, `final-review-fix.patch`)

| 항목 | 내용 | 근거 |
|---|---|---|
| P3 폐기 키 이관 표 | `web_auth.consume_legacy`는 표 발급 시점 이전에 만든 살아 있는 키가 있어야 표를 씁니다. 없으면 `410 ticket_invalid`을 돌려주고 표는 쓰지 않은 상태로 두며 세션도 만들지 않습니다. rotate로 새로 만든 키는 그 표를 되살리지 않습니다. 스키마는 바꾸지 않았습니다 | 새 e2e `test_legacy_migration_ticket_dies_with_its_revoked_key`: 기준 코드 201(RED) → 수정 후 PASS. 탐침 두 벌 모두 교환 201→**410**, minted false |
| 문서 | `web-auth.md` 45행 로그아웃은 「쿠키를 지운다」에서 「요청을 인증한 세션 행만 거둔다, 삭제 Set-Cookie 없음」으로 고쳤습니다. 51행 401의 「+ 쿠키 삭제 Set-Cookie」는 「없음」으로 고쳤습니다. 이관 절에 키 폐기 규칙을 더했습니다. `clear_header()`는 남아 있지만 호출하는 곳이 0곳임을 확인했습니다 | 문서 전수 grep에서 남은 옛 문장 0건(관리 콘솔 쿠키는 다른 계약) |
| 후보 시험 | 캐시 소유자 규칙을 순수 함수 `lib/live/cache-owner.ts`로 옮겼습니다(동작은 같습니다). Vitest 9건을 더해 identity-test fixture 없이도 돌게 했습니다 | 옛 규칙(직전 세션 비교)으로 변이하면 5/9로 4건을 검출했고, 되돌린 뒤 hash가 일치했습니다 |

patch SHA-256은 `67fbfe22…5edc`입니다. 저장한 원본에 `git apply`하면 6/6 파일이 시험한 트리와 바이트까지 같습니다. 전·후 hash는 [증거](../evidence/2026-10-29_st4f719-final-recheck/)에 있습니다.

# 직접 센 결과

| 검사 | 결과 |
|---|---|
| Vitest | **1299/1299**(400파일 = 1290 + 새 9) · tsc 0 · `next build` exit 0(정적 19/19) |
| 실제 PG 계약 / DoD / 쿠키 e2e | 367/367 · 26/26 · **38/38**(새 1 포함) |
| 보안 | 124/125. 실패 1건은 ST4F-728 XML 한 파일뿐이며 기존 HOLD와 같습니다 |
| 실제 인증 Edge | indep-review 3/3 · session-recheck-race 4/4 · identity 10/10 · independent2 3/3 · independent-focus 2/2 = **22/22** |
| 세션 관련 기존 화면 9파일(stub) | **82/82**(앞 검토 기준 81/82) |
| API 탐침 / 독립 탐침 | 24/25(기존 관찰 1건: 점검 중 201 vs 200, 둘 다 허용) / 10/10 |

- 시험 장치 주의: 첫 API 탐침은 17:15 실행이 남긴 꺼진 점검 행 때문에 `UniqueViolation`으로 멈췄습니다. 격리 DB에서 그 행만 지우고 다시 돌려 24/25를 얻었습니다(제품 결함 아님).
- 공개 증거를 비공개 fixture 값 87개와 대조했고 일치는 0건입니다. IP·웹훅 문자열도 0건입니다.

# 남은 것

- 보안 HOLD: `security-ready.xml`(ST4F-728 증거)을 담당자가 정리해야 필수 관문이 3/3이 됩니다.
- P3 관찰: id 키에 늦게 쓰는 mutation 4곳에 query 동일성 가드를 넣는 후속 작업을 권고합니다.
- 키 폐기가 그 키로 만든 기존 쿠키 세션을 거두지 않는 것은 기준 동작입니다(범위 밖).
- guest→member 설문 초안 삭제는 제품 결정 사항입니다(앞 보고와 같음).
