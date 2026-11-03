---
type: report
title: ST4F-719 개인정보·인증 복구 후보 독립 검토 — 기존 화면 회귀 7건, 수락 불가·보안 HOLD 유지
status: draft
domain: travel
---

# 판정

2026-10-29 KST. [복구 후보](2026-10-29_st4f719-privacy-auth-recovery.md)(`candidate.patch` SHA-256 `52bbc414…e68b`, 기준 `656579fe3`)를 새 격리 사본에서 독립 검토했습니다. **후보 자체 관문은 재현했지만 후보가 실행하지 않은 기존 화면 시험에서 회귀가 나와 수락할 수 없습니다.** 서버 쪽 권한 상승·혼합 자격·다른 계정 정보 노출은 찾지 못했습니다. 필수 관문은 **2/3 = 66.7%**로 보안 HOLD를 유지합니다. 원본 제품 코드·scanner·보호 XML 수정, 커밋·push·배포·삭제는 0건입니다.

| 검사 | 직접 센 결과 |
|---|---|
| 후보 manifest 일치 | 18/18 = 100% |
| 실제 PG 계약 / DoD / 쿠키·API e2e | 367/367 · 26/26 · 35/35 = 100% |
| 보안 | 124/125 = 99.2% — 기존 `st4f728-guest-logout/security-ready.xml`과 같은 실패 |
| 실제 Edge 수락 10건 재실행 | 10/10 = 100% |
| Vitest | **1260/1260** — 보고서의 1282에는 `candidate.patch`에 없는 시험 파일 3개(22건)가 섞여 있었음. 독립 탐침 2건을 더하면 1262/1262 |
| TypeScript | 1/1 = 100% |
| 독립 API 탐침(실제 PG 인증 라우터) | 23/24 = 95.8% |
| **기존 화면 시험 6개 파일(mock stub, Edge)** | **기준 60/61 = 98.4% → 후보 53/61 = 86.9%, 새 실패 7건** |

# 결함

1. **[P1] 기존 화면 흐름 회귀 — 인증 scope가 바뀌면 화면 트리 전체를 다시 그림.** `Providers`의 `Fragment key={boundary}`와 `OnboardingProvider`의 `key={scope}` 때문에 로그아웃·로그인 완료·첫 게스트 세션 생성 때 하위 화면 상태가 사라집니다. 새 실패 7건 중 4건은 두 key를 고정하는 변이에서 다시 통과해 원인을 확인했습니다. 해당 시험은 `session.spec`:63 · `session.spec`:93의 「로그아웃했어요」, `login-consent-flow`:137의 `/auth/done` 결과 제목, `onboarding.spec`:150의 새 여행 → `/intakes/…` 이동입니다. 나머지 3건 가운데 `session.spec`:123은 mock stub에 새 `adopt-ticket`/`adopt-cookie`가 없어서 생긴 계약 누락입니다. `login-consent-flow`:113·152는 원인을 끝까지 확인하지 못했습니다. `session.spec`:23은 기준에서도 실패합니다.
2. **[P1] 처리 중인 채팅의 답변 유실.** 이번 후보가 창 `focus`/`pageshow`마다 `probeSession(force)`를 부르도록 바꿨습니다. 같은 scope를 다시 조회해도 세션 객체는 새로 만들어지는데, `trip-chat` onSuccess가 `context.session !== currentSession()`으로 **객체를 비교**합니다. 실제 Edge에서는 focus 대조군만 통과했고, focus를 넣은 조건은 답변이 화면에 나오지 않았습니다. 조건을 scope 비교로 바꾼 변이는 2/2 통과했습니다. `sessionChecked`에서 고친 객체 비교 문제가 다른 경로에 남아 있습니다.
3. **[P2] 로그아웃 경합 시 동의 사본이 남음.** 로그아웃 응답이 오기 전에 focus 재조회가 들어오면 `logout()`이 null을 돌려줍니다. 그러면 `SignOut`은 `forgetConsents`·`blankOnboarding`을 실행하지 않고 끝납니다. 실제 Edge 후보에서 대조군은 동의 사본이 지워졌지만, focus 조건은 그대로 남았습니다(ST4F-601 F10 규칙 위반).
4. **[P2] 점검 중 옛 키 이관 불가.** 옛 `/auth/adopt`는 점검 예외라 201을 받지만, 새 `/auth/adopt-ticket`은 503 `maintenance`를 받습니다. 이관 실패 시 키를 보존하므로 자료 손실은 없지만, 기존 동작과 다릅니다.
5. **[P3] 저장 설문이 주인 없이 남음.** 서버에서 세션이 끝나거나 브라우저를 재시작해 쿠키가 사라지면, 끝난 scope의 `onboarding.v3:<scope>` 답이 localStorage에 계속 남습니다. 익명 상태로 새로 고쳐도, 다른 계정으로 로그인해도 지워지지 않았습니다. 다른 계정 화면에 노출되지는 않았습니다. scope가 세션 단위라 같은 회원이 다시 로그인해도 설문을 복원하지 못합니다.
6. **[P3] 관찰된 한계.** 발급한 표의 TTL 안에서는 키를 폐기한 뒤에도 교환이 201로 성공합니다(차단 계정은 다음 사용에서 403). 두 탭이 같은 옛 키를 동시에 이관하면 한 탭이 409 뒤 `failed`에 남습니다(새로 고치면 회복). 이관 한 번에 `auth_adopt` 한도를 2단위 써서 실질 한도가 주소당 시간 15회로 줄었습니다. 로그아웃 뒤 폐기된 쿠키는 쿠키 저장소에 남지만 401만 받고 되살아나지 않습니다.

# 확인한 보안 경계(통과)

표 발급은 키만 허용합니다. 쿠키 동반 400, 쿠키만 400, 무자격 401이며 응답은 `no-store`이고 쿠키를 만들지 않습니다. 쿠키 교환은 Origin이 없거나 외부 Origin이면 403입니다. 헤더 키와 Bearer 키는 400, nonce가 틀리면 410이며 표를 소모하지 않습니다. 유효한 다른 쿠키가 있으면 409이고 표를 보존합니다. 추가 필드는 422, 재사용은 410, 만료는 410입니다. 성공한 세션은 키 주인에게 묶입니다(DB 확인). OAuth 교환은 legacy 표를 410으로 거절하고, 늦은 logout/401은 `Set-Cookie`를 보내지 않습니다. 공개 증거에서 fixture 자격 원문 68개를 대조했고 0건 겹침을 확인했습니다.

# 실행과 경계

사본은 `scratch/st4f719-privacy-independent-20261029/`입니다. 이전 복구 사본에서 `--no-hardlinks --no-checkout`으로 복제한 뒤 `final_project_cs`/`final_project_sample`만 checkout하고 후보 patch를 적용했습니다. 전용 PG는 port 57723이며 종료 후 접속 거부를 확인했습니다. 실행 진입점은 `run_all.py`(관문·수락 Edge·독립 Edge·API 탐침)와 `run_browser.py`(`SPEC`/`RESULT_NAME`/`WEB_ROOT`)입니다. 기준 비교는 `git archive`로 만든 `base/` 웹 사본에서 실행했습니다. 시험 harness는 이전과 같습니다(fixture 화면, stub의 `privacy_scope`, `node_modules` junction). 두 변이 후에는 원래 bytes로 복구하고 hash 일치를 확인했습니다. 외부 OAuth·다른 브라우저·실기기·운영 API·production build 재실행의 분모는 모릅니다. [증거](../evidence/2026-10-29_st4f719-privacy-auth-independent-review/) · [인계](../../../../wiki/handoff/2026-10-29_st4f719-privacy-auth-independent-review.md).
