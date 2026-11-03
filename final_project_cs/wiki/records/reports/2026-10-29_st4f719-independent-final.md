---
type: report
title: ST4F-719 인증·개인정보 차단 수정안 독립 최종 검토 — 남은 결함 1건(401 뒤 캐시 소유자) 격리 수정, 새 회귀 0, 보안 HOLD 유지
status: draft
domain: travel
---

# 판정

2026-10-29 KST. Claude(Hermes 하위 세션)가 [차단 결함 수정](2026-10-29_st4f719-blocker-fix.md)을 독립 재검토했습니다. 15:37에 중단된 앞 검토 세션의 격리 사본 `scratch/st4f719-blocker-independent-20261029/`을 그대로 이어 썼고, 새 clone은 0건입니다. 기준은 `656579fe3` 위의 `full-candidate.patch`이며 manifest 29/29가 일치했습니다.

**결론: 조건부 수락입니다.** 차단 결함 수정 자체는 맞습니다. 다만 같은 설계에 남아 있던 개인정보 결함 1건(P1)을 찾았습니다. **A의 세션이 401로 끝난 뒤 같은 탭에 B(다른 계정이나 새 게스트)가 들어오면, A의 화면 캐시가 B에게 남았습니다.** 사본에서만 고쳤고(아래 patch), 고친 뒤 새 회귀는 0건입니다. 반영할 때는 이 patch를 함께 넣어야 합니다. 보안 HOLD(`test_no_infra_in_tracked_files` ← ST4F-728 증거 XML)는 유지합니다. 필수 관문은 **2/3 = 66.7%**입니다. TeamFlow 후속 이슈는 **ST4F-744**(담당 `3rd_team_4_be` = role-manager)입니다. 원본 작업 폴더의 제품 코드·scanner·보호 XML은 수정하지 않았습니다. 커밋·push·배포·병합도 0건입니다.

# 찾은 결함 (P1, 개인정보)

- 위치: `frontend/apps/web/src/app/providers.tsx`의 캐시 정리 구독
- 원인: 직전 세션을 `previous = next`로 매번 덮어썼습니다. 그래서 A→없음(401) 다음에 오는 없음→B를 「첫 세션」으로 보고 `client.clear()`를 건너뛰었습니다. 온보딩 답(`onboarding.v3:<scope>`)은 `client.ts`가 A→없음에서 지우므로 문제가 없습니다. 남는 것은 화면 query cache입니다. query key에 scope가 없어서(`["support-inquiries", language]` 등) B가 다시 받기 전까지 A의 값이 보입니다.
- 실제로 생기는 길: 공용 기기에서 A의 세션이 만료(401)된 뒤 같은 탭에서 게스트를 시작하는 경우, 그리고 다른 탭에서 B가 로그인한 뒤 이 탭이 focus 재조회로 B를 받는 경우입니다.
- 재현: 검토자 시험 `indep-review-20261029.spec.ts`는 수정 전 2/3이었습니다. `A → 401 → B` 시험이 `"A PRIVATE TRIP"`을 받았고, 대조군(A→B 직접)은 통과했습니다.
- 수정: 캐시 소유자 scope를 401에서는 유지합니다. 소유자는 다른 계정이 들어오거나 의도한 종료(`retired`)가 있을 때만 바뀝니다. 첫 세션(없음→게스트) 초안 유지, A→401→A 화면 유지, 401 오류 화면 유지는 그대로입니다. 증거 [`providers-owner-survives-401.patch`](../evidence/2026-10-29_st4f719-independent-final/providers-owner-survives-401.patch)(SHA-256 `289e842f…69fd`, providers 전 `b0a79f54…05ff` → 후 `83f6e69d…139a`)

# 직접 센 결과

| 검사 | 결과 |
|---|---|
| manifest | 29/29 |
| Vitest(수정 뒤) | **1290/1290**(399 파일) · tsc 오류 0 |
| production build(`next build`, 수정 전·후) | 둘 다 exit 0, 정적 18/18. 기준 사본 build는 node_modules junction이 Turbopack 루트 밖이라 실행할 수 없었습니다(환경 문제) |
| 실제 PG 계약 / DoD / 쿠키 e2e | 367/367 · 26/26 · 37/37 |
| 보안 | 124/125 — 기존 HOLD와 같은 1건 |
| API 탐침(실제 PG 인증 라우터) | 엄격 비교 24/25(관찰 항목: 점검 중 옛 `adopt` 201 vs 표 발급 200, 둘 다 허용) |
| 검토자 독립 탐침 | 10/10(rate 한도, 틀린 nonce는 표를 태우지 않음, 동시 교환은 세션 1개, TTL 61초 만료, 로그아웃은 요청한 세션만, CSRF, 차단 계정 403, 표·nonce 교차 불가) |
| 검토자 캐시 시험 | 수정 전 2/3 → 수정 뒤 **3/3** |
| 실제 인증 Edge(수정 뒤) | identity 10/10 · independent2 3/3 · independent-focus 2/2 · session-recheck-race 4/4 |
| 세션 관련 기존 화면 9파일(session·login-consent-flow·onboarding·onboarding-alerts·consent·chat-cards·account-consent-design·profile·social-login) | 수정 후보 **82/82**, 기준 81/82(기준에서만 session:23 실패) → 새 실패 0 |
| 기존 화면 전체(Edge, 3샤드, 수정 후보) | 921/958(건너뜀 20). 기준(같은 호스트, 앞 세션 실행) 910/954. 두 쪽 공통 실패 15건(영상·촬영·지도 등 11파일). 후보에서만 실패한 2건(`guardian-card` 375px, `stop-ask-flow` 스크롤)은 단독 재실행에서 후보 43/43·기준 43/43 → **새 회귀 0** |

# 판단 요청 항목

1. **stub의 삭제 Set-Cookie 제거와 `contract_correction` 6곳은 약화가 아닙니다.** 실제 백엔드도 401·로그아웃에서 삭제 Set-Cookie를 보내지 않습니다(API 탐침 `logout_no_clear_cookie`·`dead_cookie_401_no_clear`). 서버가 세션 행을 폐기하므로 남은 쿠키로는 아무것도 열리지 않습니다(session.spec 「여행을 묻지도 않았다」 유지). 다만 **`wiki/external/rest-endpoints/web-auth.md` 45행(logout 「쿠키를 지운다」)과 51행(401 「+ 쿠키 삭제 Set-Cookie」)은 옛 문장 그대로**이고, D-CS-011 109행만 고쳐져 있습니다. 반영할 때 문서도 함께 고쳐야 합니다(P3).
2. guest→member 로그인 때 설문 메모리를 비우는 것은 개인정보를 보수적으로 지키는 쪽입니다. 같은 사람이어도 게스트 초안을 잃는 UX 비용이 있으므로 제품 결정으로 남깁니다(막는 결함 아님).
3. 폐기한 키로 받은 표는 TTL(60초) 안에서 아직 교환됩니다(관찰 `revoked_key_ticket_redeemable_in_ttl`). 기준에서도 키 폐기가 그 키로 만든 쿠키 세션을 거두지 않고, 키를 가진 쪽은 폐기 전에 옛 `adopt`로 세션을 만들 수 있었습니다. 그래서 새로 열린 위험은 60초 창뿐입니다(P3, 후속 권고: 교환 때 원래 키가 살아 있는지 확인).
4. 이관 한 번에 rate 2단위(표+교환)를 씁니다. 주소당 한 시간 30단위이므로 15번까지 옮길 수 있습니다. 실측에서 15번을 마친 뒤 다음 표 요청이 429였고 `Retry-After`가 있었으며, 표만 나가고 교환이 거절되는 경우는 없었습니다. 허용 가능합니다.

# 남은 것

- `independent-logout-race.spec.ts`는 identity-test fixture의 동의 gate 때문에 대조군까지 0/2입니다(fixture 한계, 알려진 사항). 실제 계정 화면 `session-recheck-race` 4/4로 대신 확인했습니다.
- `preferences.spec.ts`:451 기준 실패는 이번 단독 재실행에서 양쪽 모두 통과했습니다(불안정, 원인 미확인).
- 검토자 캐시 시험은 후보에 들어 있지 않습니다. 반영할 때 `tests/live`에 넣거나 같은 내용을 Vitest로 옮기기를 권고합니다.
- 공개 증거·보고는 비공개 fixture 값(`actors-private.json`)과 대조해 일치 0건이었습니다.
