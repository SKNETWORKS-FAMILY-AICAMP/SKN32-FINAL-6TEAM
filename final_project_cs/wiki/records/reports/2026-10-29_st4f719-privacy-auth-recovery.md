---
type: report
title: ST4F-719 개인정보·401·옛 키 복구 격리 수정 — 보안 HOLD 유지
status: draft
domain: travel
---

# 판정

2026-10-29 KST. [독립 검토에서 발견한 세 경계](2026-10-29_st4f719-identity-independent.md)를 새 격리 사본에서 재현하고 수정했습니다. 대상 결함은 **3/3 = 100%** 격리 검증했으며, 실제 Edge 최종 **10/10 = 100%**, 음성 변이 검출 **4/4 = 100%**입니다. **필수 관문 2/3 = 66.7%, 보안 HOLD를 유지합니다.** 원본 제품 코드 반영·커밋·push·배포·고객/트래커 쓰기·파일 삭제는 0건입니다. 독립 수락과 운영 승인이 아닙니다.

구현·자체 검토 담당은 이번 Codex 세션입니다. 독립 검토자는 미확보입니다. 공유 인증 계약과 웹 호출부를 함께 수정한 후보이며, 매니저·인증/API·웹 담당의 통합 검토는 남아 있습니다. [정제 증거와 패치](../evidence/2026-10-29_st4f719-privacy-auth-recovery/) · [인계](../../../../wiki/handoff/2026-10-29_st4f719-privacy-auth-recovery.md).

# 재현과 수정

원래 여덟 조건을 그대로 재실행하여 Edge **4/8 = 50%**를 확인했습니다. 계정 변경·다른 탭 로그아웃의 온보딩 잔존, 같은 scope 재조회 뒤 실제 폐기 401 무시, 무효 쿠키와 유효 옛 키의 이관 실패가 모두 실제 assertion에서 실패했습니다. 서버 권한 우회가 재현됐다는 뜻은 아닙니다.

온보딩은 `OnboardingProvider` 안에 인증 scope별 소유 경계를 두었습니다. 같은 scope 재조회는 유지하고, 변경·확정 종료는 메모리의 설문·webhook·동의 초안을 새 상태로 바꿉니다. 저장한 설문은 `tripilot.web.onboarding.v3:<privacy_scope>`에만 귀속합니다. 이전 무소유 v2는 복원하지 않고 정리합니다. 인증 전 초안과 webhook은 저장하지 않습니다. 늦은 이전 소유자의 저장은 현재 scope 검사로 거부합니다. 언어·테마 같은 기기 설정은 변경하지 않습니다. 확정 종료 신호는 해당 scope의 저장분만 정리하므로 늦은 A 종료가 B 저장분을 지우지 않습니다.

`sessionChecked()`는 요청의 객체가 교체됐어도 서버 발급 privacy scope가 현재와 같으면 확정 `unauthenticated`를 종료로 처리합니다. 다른 B scope의 늦은 A 거절은 여전히 무시합니다. 자동 재전송·새 게스트 생성으로 오류를 숨기지 않습니다.

옛 키 이관은 혼합 자격 거절을 유지하는 명시적 두 단계로 바꿨습니다. `POST /auth/adopt-ticket`은 `credentials: omit`과 옛 키로만 인증하고, nonce에 묶인 짧은 수명의 일회용 표를 발급합니다. 세션·쿠키는 만들지 않습니다. `POST /auth/adopt-cookie`는 키 없이 쿠키와 표/nonce만 보내며 허용 Origin을 검사합니다. 유효한 기존 쿠키가 있으면 409로 거절하고 표·쿠키를 보존합니다. 무효/없는 쿠키만 유효한 legacy 전용 표를 원자적으로 소비해 새 HttpOnly 세션을 발급합니다. 기존 표 저장소·설정된 TTL·인증 요청 제한을 사용합니다. OAuth와 legacy 표는 서로 교환하지 않습니다. 표 발급 중 같은 페이지에서 B가 시작되면 교환 요청을 보내지 않습니다. 실패 시 옛 키를 유지하고, 성공 또는 명시적 키 인증 거절 때만 제거합니다.

일반 인증의 쿠키+키 거절, tenant/customer 격리, CSRF·Origin·동의 경계는 완화하지 않았습니다. 늦은 logout/401의 삭제 Set-Cookie도 복구하지 않았습니다. 후보 계약은 사본 wiki의 REST 인증 문서에 기록했으며 운영 승인 상태로 올리지 않았습니다.

# 실행 근거

| 검사 | 직접 센 결과 |
|---|---|
| 원래 Edge 재현 | 4/8 = 50%, 대상 네 조건 실패 |
| 최종 실제 Edge | **10/10 = 100%**, skip 0 |
| 전체 Vitest | **1282/1282 = 100%**, skip 0 |
| TypeScript | 1/1 = 100% |
| Next webpack production build | 1/1 = 100% |
| 실제 PG 계약 | 367/367 = 100% |
| DoD | 26/26 = 100% |
| 쿠키/API e2e | **35/35 = 100%** — 기존 28 + 복구 경계 7 |
| 보안 | **124/125 = 99.2%**, 기존 tracked infrastructure 검사 실패 |
| 필수 관문 | **2/3 = 66.7%, HOLD** |
| 음성 변이 | **4/4 = 100% 검출** |
| 선정 원본 보호 파일 | **740/740 = 100%** 기존 hash 일치 |
| follow-up patch 적용 사전검사·공백 검사 | 각각 1/1 = 100% |

브라우저는 설치된 Microsoft Edge와 새 loopback PG의 제품 인증 라우터를 사용했습니다. 실제 cookie·lookup·CSRF·폐기·옛 키 이관을 실행했습니다. 화면 fixture는 실제 Providers·SessionCard·SignOut·OnboardingProvider·client·diff를 쓰며 부가 여행 API는 stub입니다. 두 탭 종료, 계정 변경, 같은 scope 재조회·reload, 실제 서버 폐기 후 401, 무효 쿠키 유무의 이관, 늦은 A logout 뒤 B cookie/query/diff/onboarding 보존을 확인했습니다.

음성 변이는 온보딩 소유 경계 제거, 같은 scope 401의 객체 비교 복귀, 복구 교환의 유효 쿠키 보호 제거, OAuth 표 소비의 목적 분리 제거입니다. 각각 정상 조건과 대응하는 실제 assertion 실패를 확인하고 원래 bytes로 복구했습니다. 파서/준비 오류를 검출 성공으로 세지 않았습니다.

실행 진입점은 `scratch/st4f719-privacy-fix-20261029/`의 `run_final_browser.py`(`IDENTITY_RESULT_NAME=acceptance-browser`), `run_web.py`, `run_build.py`, `run_gates.py`, `run_negative.py`입니다. `run_pg.py` wrapper의 exit 0만으로 성공 판정하지 않고 내부 pytest·DoD 결과를 읽었습니다. 최종 변이 결과와 복구 후 SHA manifest를 보존했습니다.

# 시험 보정과 보존

첫 fixed Edge는 7/8이었습니다. Playwright `route.fetch`가 브라우저의 `credentials: omit`과 별개로 context cookie를 붙여 이관 준비 요청을 거절시킨 것으로 확인했습니다. 이관 요청을 `route.continue`로 실제 브라우저 network stack에 통과시킨 뒤 8/8이 됐습니다. 두 보존 조건 추가 후 첫 10건 실행에서는 이미 앞에서 폐기한 B/C fixture를 재사용해 로그인 준비가 실패했습니다. 새 E/F fixture로 분리한 최종 실행은 10/10입니다. 앞선 실패 로그를 보존하고 최종 분모에 반복 실행을 더하지 않았습니다.

전체 단위 시험에서 옛 단일 adopt 경로를 기대하던 mock 세 개는 새 두 단계 계약을 검사하도록 바꿨습니다. 다른 계정이라고 하면서 같은 scope를 쓰던 시험은 실제 다른 scope로 고쳤습니다. 독립 탐색 시험의 v1 localStorage 주입은 제품의 실제 sessionStorage로 정정했습니다. 이 잘못된 탐색 조건은 이전 독립 보고서에서도 실제 제품 결함으로 인정하지 않았던 조건입니다. 시험 삭제·skip·예외 추가는 하지 않았습니다. 마지막 표 발급 경합 시험까지 포함한 최종 분모는 1282입니다.

첫 checkout/apply의 Windows 긴 경로 실패, junction 준비, 변이 runner의 CRLF 문자열 일치 실패도 scratch에 보존했습니다. 변이 runner 실패는 검출 분모에 넣지 않았습니다. 원본·다른 사본·PG 자료·로그를 삭제하지 않았습니다.

# 작업 경계와 남은 한계

사본은 이전 독립 검토 사본에서 `--no-hardlinks --no-checkout`으로 새로 만들고 기준 `656579fe37d613a64caeb96cdb344958890a1c4d`에 검토한 변경을 적용했습니다. 원본 Git 조회/색인/설정을 바꾸지 않았고 격리 Git에도 `GIT_OPTIONAL_LOCKS=0`을 적용했습니다. 원본/CS 지침·RULE·양쪽 wiki·개발 역할·코드 경로·인계·인증 계약과 실제 coord NOTICE **63/63 = 100%**를 읽었습니다. T/S3/R/V 및 다른 항목의 파일·원격 소유 경계를 유지했습니다.

정제 evidence에는 실제 fixture 쿠키·옛 키·CSRF를 넣지 않았습니다. 원문은 비공개 scratch에만 있으며 공개 파일과 값이 겹치지 않는지 검사했습니다. 보안 scanner·보호 XML·기존 실패 원문·예외 목록은 수정하지 않았습니다. 새 PG는 data_directory/database/port를 확인하고 종료 및 접속 거부를 확인했습니다. 740은 선정 manifest의 분모이며 전체 디스크 보호 보장이 아닙니다.

외부 OAuth 공급자·다른 브라우저·실기기·운영 여행 API·동결/오프라인 탭·최신 원격 통합·운영 수락의 분모는 모릅니다. 쿠키 발급 응답 전체와 다른 탭 신규 로그인 사이의 모든 경합까지 증명한 것은 아닙니다. 이번 검증은 명시한 요청·응답 순서와 두 탭 경계의 수락입니다. 보안 실패의 원인 자료를 삭제하거나 scanner를 완화해 관문을 통과시키지 않습니다. 다음 단계는 후보 계약·패치의 독립 검토와 보안 HOLD의 별도 정식 해결이며 push·배포 승인은 포함하지 않습니다.
