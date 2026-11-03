---
type: report
title: ST4F-719 identity-bound 독립 검토 — 개인정보 잔존·401 경계·옛 키 호환성 HOLD
status: draft
domain: travel
---

# 판정

2026-10-29 KST. 이전 구현 세션과 별개인 이번 Codex가 독립 검토했습니다. **승인 보류, 필수 관문 2/3 = 66.7%, 보안 HOLD 유지**입니다. 계정·다중 탭 온보딩 잔존(P1), 같은 세션 재조회 뒤 늦은 401 무시(P2), 무효 쿠키와 유효한 옛 키의 이관 실패(P2)를 재현했습니다. 서버 권한 우회가 재현됐다는 뜻은 아닙니다. 원본 제품 코드 수정·운영/고객/트래커 쓰기·커밋·push·배포·파일 삭제는 0건입니다.

[검토한 인계](../../../../wiki/handoff/2026-10-29_st4f719-identity-bound.md) · [이번 인계](../../../../wiki/handoff/2026-10-29_st4f719-identity-independent.md) · [정제 증거](../evidence/2026-10-29_st4f719-identity-independent/).

# 발견 사항

## P1 — 계정 경계와 다른 탭 로그아웃에서 온보딩 개인정보가 남습니다

후보 `src/app/providers.tsx:26,51`의 계정 경계는 `OnboardingProvider` 안쪽에 있고, `/mypage/account*`의 경계 키는 계속 `account`입니다. `features/onboarding/onboarding-state.tsx:77`은 최초 한 번 저장소를 읽으며 세션 종료·계정 변경·다른 탭 저장소 변경을 구독하지 않습니다. `SignOut`이 정리하는 것은 그 컴포넌트가 실행된 탭의 상태입니다.

실제 Edge와 격리 인증 API에서 A의 설문 자유입력 및 webhook 초안을 메모리에 만든 뒤 쿠키를 B로 바꾸고 성공한 `/auth/me`로 B scope를 확인했습니다. **B의 온보딩 메모리에는 A의 자유입력과 webhook 초안이 남았고, `tripilot.web.onboarding.v2`에는 A의 자유입력이 남았습니다.** webhook 초안이 localStorage에 저장됐다는 주장은 아닙니다.

별도 두 탭 시험에서는 다른 탭에 같은 개인정보를 만든 다음 첫 탭에서 실제 로그아웃했습니다. 다른 탭의 `currentSession()`은 null이 됐지만 온보딩 메모리는 A 값을 유지했습니다. diff 제거 시험만으로는 이 경계를 검증하지 못합니다. 두 수락 조건 모두 실패하여 **0/2 = 0%**입니다. 재현: `identity.spec.ts`의 `independent: B must not inherit…`, `extra: cross-tab logout…`.

수정 시 온보딩·동의의 현재 계정 소유권과 기기 공통 설정을 구분해야 합니다. 늦은 A 정리가 이미 시작된 B의 상태를 지우지 않는 검사도 유지해야 합니다. 이 검토에서는 수정하지 않았습니다.

## P2 — 동일 scope 재조회 뒤 요청의 실제 401을 무시합니다

후보 `lib/live/client.ts:359–365`의 `sessionChecked()`는 여전히 `snapshot.session !== beganWith`라는 객체 동일성을 검사합니다. 성공한 강제 재조회는 같은 scope의 새 객체를 만듭니다. 따라서 요청 당시와 같은 서버 세션인데도 뒤늦은 `unauthenticated`를 새 계정의 응답처럼 무시합니다.

Edge에서 실제 `api('/v1/web/auth/me')`를 보류하고 같은 scope의 성공 probe를 수행한 다음, 격리 서버의 실제 `/auth/logout`으로 세션을 폐기했습니다. 보류한 GET을 서버에 전달하여 실제 401을 받았습니다. 서버는 거절했으나 **클라이언트 세션은 계속 활성이고 그 scope의 diff도 남았습니다.** 요구한 종료·제거 수락은 **0/1 = 0%**입니다. 단위 시험에서도 같은 객체 교체 경계를 재현했습니다. 재현: `identity.spec.ts`의 `independent: real revoked 401…`.

logout의 동일 scope 소유권 보강은 이 경로까지 적용되지 않았습니다. 서로 다른 B scope의 늦은 A 거절은 계속 무시해야 하지만, 같은 scope의 확정 폐기는 종료해야 합니다. 이는 서버가 폐기된 세션의 접근을 허용하는 결함이 아니라 클라이언트의 종료·개인정보 정리 결함입니다.

## P2 — 무효 쿠키가 있으면 옛 키 이관을 끝낼 수 없습니다

서버 후보는 logout과 무효 쿠키 401의 삭제 `Set-Cookie`를 제거합니다. 이는 늦은 A 응답이 B 쿠키를 지우는 문제를 막으며 실제 경합 시험도 통과했습니다. 그러나 `client.ts`의 `adoptLegacyKey()`는 401이 쿠키를 지웠다는 기존 가정 아래 계속 `credentials: "include"`와 `X-User-Key`를 함께 전송합니다. 서버 `web_cookie.py:_identify()`는 쿠키와 키가 함께 있으면 쿠키 유효성과 무관하게 `400 ambiguous_credentials`로 거절합니다.

동일한 격리 DB의 유효한 옛 키로 두 조건을 실제 Edge에서 비교했습니다. **쿠키 없음은 회원 세션 이관·옛 키 삭제에 성공하고, 무효 쿠키 있음은 snapshot.failed=true·세션 없음·옛 키 잔존으로 실패합니다. 호환성 수락은 1/2 = 50%**입니다. 후자는 기존 handoff가 미해결로 남긴 조합이며 이번에 실제 브라우저로 확인했습니다. 재현: `identity.spec.ts`의 `independent: valid legacy key plus invalid cookie…`, `extra: legacy key with no cookie…`.

혼합 자격 거절을 조용히 약화하거나 삭제 Set-Cookie를 그대로 되살리는 것으로 닫으면 안 됩니다. 공유 인증 계약에 이관·회복 경로를 먼저 명시하고, 새 B 쿠키 보존과 옛 키 이관을 함께 검증해야 합니다. 현재 후보 wiki는 cookie 삭제 제거를 제안 상태로 기록했으며 운영 승인·적용 근거는 아닙니다.

# 통과한 경계와 실행 결과

| 실행 | 직접 센 결과 |
|---|---|
| 전달 patch 후보의 기존 전체 Vitest | **1268/1268 = 100%**, skip 0 |
| TypeScript | 1/1 = 100% |
| 기존 세션 단위 시험 대조군 | 8/8 = 100% |
| 추가 거절·오프라인·저장소 차단·잘못된 탭 신호 시험 | **9/9 = 100%** |
| 실제 Edge 기존 3조건 + 옛 키/쿠키 없음 | 4/4 = 100% |
| 추가 실제 Edge 실패조건 | 0/4 = 0% — P1 두 조건·P2 두 조건 |
| 최종 서로 다른 Edge 수락 조건 합계 | **4/8 = 50%**, skip 0 |
| 독립 재실행 단위 변이 검출 | 3/3 = 100% |
| 실제 Edge UI 소유권 guard 제거 변이 검출 | 1/1 = 100% |
| 변이 합계 | **4/4 = 100% 검출** |
| 새 격리 PG 계약 | **367/367 = 100%** |
| DoD | **26/26 = 100%** |
| 실제 쿠키 서버 e2e | **28/28 = 100%** |
| 보안 | **124/125 = 99.2%**, 기존 tracked infrastructure 탐지 1건 실패 |
| 필수 관문 | **2/3 = 66.7%, HOLD** |
| handoff 선정 보호 파일의 기존 해시 및 이번 말미 해시 | 각각 **740/740 = 100%** 동일 |
| 전달 사본과 후보의 제품·계약/e2e 파일 해시 대조 | **10/10 = 100%** 동일 |

기존 Edge 3조건은 같은 scope 두 탭의 diff 종료, B probe·새로고침의 B 이력 보존/A 고아 이력 제거, 실제 늦은 A logout 뒤 B 쿠키·query·diff 보존입니다. 서버 발급 `privacy_scope`는 설정 비밀키와 tenant·session_hash에 대한 분리 도메인 HMAC이며 권한 자격으로 사용하지 않습니다. 탭 신호에는 scope·nonce만 있고 CSRF·쿠키·고객 번호가 없습니다. scope 없는 세션은 diff를 저장·복원하지 않습니다.

거절 시험은 logout의 CSRF 403·동의 403·429·503·오프라인이 현재 계정 이력을 유지하고, 확정 unauthenticated 종료는 제거함을 확인했습니다. 저장소 getter 차단 시 읽기·쓰기는 닫힌 상태로 실패하며 종료는 완료됩니다. 다른 scope/잘못된 신호는 B를 종료하지 않습니다. probe 실패는 failed로 노출하고 저장된 before 값을 확정 폐기 전까지 유지하되 현재 읽기에서는 숨깁니다. 저장소 신호를 놓친 동결 탭의 즉시 종료는 보장하지 않습니다.

변이는 별도 `mutation-web`에서 logout 소유권 검사 제거, diff 삭제 제거, 저장 키의 scope 공유화를 각각 적용하여 정상 대조군의 실제 assertion 실패를 확인했습니다. UI 변이는 정상 브라우저 종료 뒤 단독으로 `SignOut`의 두 소유권 guard를 제거하여 B query 유실을 검출했습니다. 문법/부팅 오류를 검출로 세지 않았고 원문 bytes로 복구했습니다.

# 방법·보존·한계

작업 사본은 `scratch/st4f719-independent-20261029/repo`입니다. 이전 **격리 delivery-repo**를 `--no-hardlinks --no-checkout`으로 clone하고 `656579fe37d613a64caeb96cdb344958890a1c4d`에 전달 `candidate.patch`를 적용했습니다. 원본에서 checkout·설정 변경·Git 쓰기를 하지 않았고 격리 Git에도 `GIT_OPTIONAL_LOCKS=0`을 적용했습니다. 기존 사본·PG·로그를 삭제하거나 원본으로 역복사하지 않았습니다.

루트/CS AGENTS, CS RULE, 양쪽 wiki, 개발 역할·코드 경로, 원래 handoff와 보고, 후보 D-CS-011·REST 계약, 실제 인증·Providers·SignOut·TripChat·consent/onboarding 호출부를 읽었습니다. 루트 `wiki/coord`는 없으며 실제 `cache/scratch/_coord`의 현재 NOTICE **63/63 = 100%**를 읽어 비공개 사본과 목록을 보존했습니다. T/S3/R/V 및 718/728/731/732의 작업 경계·HOLD를 유지했습니다. 메시지 전송·담당 재배정·통합 예약은 하지 않았습니다.

새로 initdb한 loopback PG와 새 API/Next/stub 포트만 사용했습니다. 브라우저는 설치된 실제 **Microsoft Edge 한 종류**입니다. Chrome/Firefox/Safari·실기기·외부 Google OAuth·운영 여행 API·동결 탭·최신 원격 통합의 수락 분모는 모릅니다. 실제 쿠키·lookup·CSRF·revoke·키 이관은 제품 서버 코드와 PG를 사용했고, 로그인 세션 생성은 격리 fixture입니다. 화면 fixture는 실제 Providers·SessionCard·SignOut·client·diff·OnboardingProvider를 사용하며 부수 API는 stub입니다. 실제 회원 화면 screenshot도 직접 열어 확인했습니다. 전체 운영 화면의 종단간 수락으로 일반화하지 않습니다.

초기 checkout은 Windows 긴 경로 오류를 냈고 격리 checkout 재시도를 보존했습니다. 무관한 benchmark JSONL 일부의 작업 트리 누락 흔적이 있어 완전한 전체 저장소 복제 수락을 주장하지 않습니다. 검토한 전달 제품/계약 파일의 해시는 대조했습니다. 첫 runner는 준비 스크립트 미완료로 migration 등 준비/관문 실행이 실패했습니다. 그 로그를 남기고 실제 migration·프롬프트 등록 후 관문을 다시 실행했습니다. `run_pg.py`가 자식 실패를 exit code로 전달하지 않으므로 wrapper의 0 대신 pytest/DoD 실제 결과로 판정했습니다.

최초 독립 탐색 단위 시험은 **8/10 = 80%**였습니다. 두 실패 중 하나는 위 동일 scope 401이고, 다른 하나는 localStorage에 임의로 주입한 `chatDiffs.v1`의 잔존입니다. 확인한 지원 v1은 **sessionStorage**였으므로 후자를 역사적 저장 호환성 결함으로 세지 않았습니다. 최종 localStorage 발견은 실제 제품이 기록하는 온보딩 답변입니다. 최초 옛 키 브라우저 시험은 동의 gate 때문에 fixture 자체가 붙지 않아 실패했고, 동의를 준비한 뒤 최종 시험에서 실제 failed snapshot·키 잔존 assertion으로 다시 실패한 것을 보존했습니다. 최종 8조건은 `final-browser` 6조건과 `extra-browser` 2조건이며 앞선 반복 실행을 더해 분모를 부풀리지 않았습니다.

기존 XML·scanner·예외 목록은 고치거나 무시하지 않았습니다. 보안 원시 실패 로그는 공개 evidence에 복제하지 않았고 탐지 이름·집계만 보존했습니다. 실제 시험 쿠키·옛 키·CSRF 원문은 비공개 `actors-private.json`에만 두며 출력하지 않았습니다. 공개 evidence는 그 값과 일치하는 bytes가 없는지 검사한 뒤 기록했습니다. 740은 선정 manifest의 분모이며 전체 디스크 보호 보장이 아닙니다. PG는 전용 data_directory·database·port를 조회한 후 정상 종료하고 접속 거부를 확인했습니다. 모든 사본·데이터·실패 로그는 남겨 두었습니다.

재실행 진입점은 scratch의 `run_final_browser.py`(`IDENTITY_RESULT_NAME`, 선택 `IDENTITY_GREP`), `run_gates.py`, `mutate_unit.py`, `mutate_browser.py`입니다. `run_final_browser.py`는 새 fixture 세션을 만들고 PG 종료까지 수행합니다. 명령·fixture·비공개 값은 scratch에 있으며 공개 evidence에는 재현 시험 소스·정제 결과·SHA manifest를 남겼습니다. 다음 작업은 위 세 경계의 격리 수정과 독립 재검증이며, 기존 HOLD 해제·push·배포 승인은 포함하지 않습니다.
