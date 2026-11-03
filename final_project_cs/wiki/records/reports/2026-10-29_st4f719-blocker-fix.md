---
type: report
title: ST4F-719 독립 검토 차단 결함 격리 수정 — 재마운트·객체 비교·로그아웃 경합·점검 이관·누락 시험, 보안 HOLD 유지
status: draft
domain: travel
---

# 판정

2026-10-29 KST. [독립 검토](2026-10-29_st4f719-privacy-auth-independent-review.md)가 막은 결함을 새 격리 사본에서 재현하고 고쳤습니다. 기준 `656579fe3` 위에 [복구 후보](2026-10-29_st4f719-privacy-auth-recovery.md) `candidate.patch`(SHA-256 `52bbc414…e68b`)를 적용하고 그 위에 수정했습니다. **필수 관문은 2/3 = 66.7%이고 보안 HOLD를 유지합니다.** 원본 제품 코드·scanner·보호 XML 수정, 커밋·push·배포·병합·삭제는 0건입니다. 구현은 Claude(Hermes 하위 세션)가 했고 자체 검증만 했습니다. 독립 재검토는 아직 하지 않았습니다. 사용자 지시(2026-10-29)에 따라 팀플로 반영 담당은 매니저 브랜치(`role-manager`)입니다. 이 후보는 HOLD가 풀리기 전에는 어느 브랜치에도 반영하지 않습니다.

| 검사 | 직접 센 결과 |
|---|---|
| 후보 manifest | 18/18 내용 일치(manifest는 CRLF 작업본 기준, 사본은 LF blob — 줄끝 정규화 비교) |
| 재현(수정 전) | 기존 화면 6파일 기준 60/61 → 후보 53/61, 새 실패 7. focus 채팅 답 유실·로그아웃 경합 재현 |
| Vitest | **1290/1290** = 후보 1260 + 누락 복원 3파일 22 + 새 8 |
| TypeScript | 1/1 |
| 실제 PG 계약 / DoD / 쿠키 e2e | 367/367 · 26/26 · **37/37**(+2 새) |
| 보안 | 124/125 — 기존 `st4f728-guest-logout/security-ready.xml`과 같은 실패(HOLD) |
| 실제 인증 Edge 수락 / 독립 탐침 | 10/10 · 3/3 |
| 새 경합 화면 시험(`session-recheck-race-20261029.spec.ts`) | 4/4(채팅 focus·로그아웃 focus, 각 대조군 포함) |
| 기존 화면 6파일 + 설문·취향 | 수정 뒤 session:23 외 전부 통과, session:23 보정 뒤 `session.spec` 11/11 |
| API 탐침(실제 PG 인증 라우터) | 엄격 상태값 비교 23/24(옛 `adopt` 201 vs 표 발급 200, 둘 다 허용 — 503 회귀 해소). 차단 계정 교환 403·발급 없음 |
| 음성 변이 | 백엔드 2/2, Vitest 3/3, Edge 4/4 검출. 모두 원래 bytes로 복구하고 hash 일치 확인 |
| 기존 화면 전체(mock stub, Edge, 샤드 실행) | 기준 910/954, 후보 919/958(새 spec 4건 포함). 목록 기준 분모는 967/971인데 JSON에는 954/958만 기록돼, 양쪽 모두 13건의 결과가 없음(원인 미확인). 두 쪽 공통 실패 36건(영상·촬영·지도 SDK 등 환경). 기준에서만 실패한 8건은 후보에서 통과(session:23 보정 포함). 제목 기준으로 후보에서만 실패한 3건(`login-consent-flow`:32, `preferences` 영어·키보드, `trip-list` 최근 여행 카드)은 동시 부하 때 생겼고 단독 재실행에서 통과. 단독 재실행 결과는 후보 36/37, 기준 36/37이며, 공통 실패 1건은 `preferences.spec.ts`:451(기준에서도 실패하던 결함, 미해결) → **새 회귀 0** |

# 원인과 수정

1. **재마운트(P1).** `Providers`의 `Fragment key`와 `OnboardingProvider`의 `key`를 없앴습니다. 온보딩은 렌더 중 소유자를 조정합니다. A→B나 A→없음일 때만 메모리를 비우고, 첫 세션(없음→게스트)은 직전 초안을 그대로 둡니다. 화면 캐시는 다른 계정이 들어오거나(A→B), 로그아웃·다른 탭 종료로 세션이 끝났을 때(`SessionSnapshot.retired`)만 비웁니다. 401로 끝난 경우에는 오류 화면을 유지합니다. 독립 검토가 원인을 밝히지 못한 `login-consent-flow`:152는 401 뒤 캐시를 비워 오류가 사라진 것이었습니다. :113은 저장 키가 바뀐 계약을 시험이 몰랐던 것입니다. 로그아웃 확인이 사라진 것은 `OnboardingProvider` 재마운트 때문이었습니다.
2. **채팅 답 유실(P1).** `sameSession`(같은 객체 또는 같은 인증 privacy scope)을 추가해 `trip-chat` onSuccess, `stream` 재연결, `sessionChecked`, `logout`에서 씁니다. 강제 재조회가 같은 세션·같은 세부값을 받으면 객체와 snapshot을 그대로 둡니다. 다른 scope의 주인 없는 사본 정리는 그대로 합니다.
3. **로그아웃 경합(P2).** `logout`은 다른 계정이 현재일 때만 null을 돌려줍니다. `SignOut`은 await 전에 동의 사본·온보딩을 지웁니다(ST4F-601 F10).
4. **점검 중 이관(P2).** `adopt-ticket`을 `_admin_access` `account_entry`에 넣었습니다(옛 `adopt`와 같음). 덧붙여 표 발급 뒤 차단된 계정은 `adopt-cookie`에서 403 `user_blocked`로 거절하고, 표 사용을 되돌리며 세션을 만들지 않습니다. 옛 한 단계 `adopt`도 같은 요청에서 차단을 확인했으므로 같은 정책입니다.
5. **주인 없는 설문(P3).** 확정 응답 뒤 다른 scope의 `onboarding.v3:*`를 지웁니다. 실패한 재조회(서버 연결 불가)에서는 지우지 않습니다. 같은 회원이 다시 로그인해도 설문이 복원되지 않는 것은 세션 단위 scope의 의도된 결과로 남겨 둡니다.
6. **mock·시험 계약.** stub에 두 단계 이관을 넣고, 401·로그아웃이 삭제 Set-Cookie를 보내지 않게 서버 계약과 맞췄습니다. 새 계약을 모르는 기존 시험 여섯 곳(`session.spec` 23·123·139, `login-consent-flow` 113, `survey-questions` 2건)과 `helpers.forgetStartScreen`은 의도를 유지하면서 기대값을 바꿨고, 바꾼 자리마다 `contract_correction` 주석을 달았습니다. session:23은 기준에서도 실패하던 시험입니다. 동의 사본이 없는 방문자에게는 아무것도 묻지 않는 계약을 반영하고, 머리글이 먼저 보이는 경합을 poll로 기다리게 했습니다. 시험 삭제·skip·완화는 하지 않았습니다. 후보 patch에서 빠졌던 시험 3파일 22건을 다시 넣었습니다.

# 남은 한계

TTL 안에서는 키를 폐기한 뒤에도 표 교환이 됩니다. 이관 한 번에 `auth_adopt` 2단위를 씁니다. 두 탭이 같은 옛 키를 동시에 이관하면 한 탭이 409를 받습니다. guest→member 로그인 때 게스트 설문 메모리를 비우는 것은 후보의 개인정보 선택을 유지한 결과입니다. 독립 탐침의 로그아웃 경합 fixture(`/mypage/account/identity-test`)는 동의 사본이 지워지면 동의 gate에 가려져 「로그아웃했어요」를 셀 수 없습니다. 실제 계정 화면 시험으로 대신 확인했습니다. 외부 OAuth·다른 브라우저·실기기·운영 API·최신 원격 통합의 분모는 모릅니다.

# 실행과 경계

사본은 `scratch/st4f719-blocker-fix-20261029/`입니다. 전용 PG는 port 57783을 썼고, 매 단계 끝에 접속 거부를 확인했습니다. `node_modules`는 기존 사본에 junction으로 연결했습니다(Next webpack dev·vitest·tsc용, production build는 재실행하지 않음). 실행 진입점은 `run_gates.py gates-*|browser-*`, `run_browser.py`(`SPEC`/`WEB`/`SHARD`/`IGNORE`), `run_mutants_py.py`, `run_mutants_front.py`, `run_mutO1.py`입니다. 공개 증거에는 fixture 쿠키·키·CSRF를 넣지 않았습니다. [증거](../evidence/2026-10-29_st4f719-blocker-fix/) · [인계](../../../../wiki/handoff/2026-10-29_st4f719-blocker-fix.md).
