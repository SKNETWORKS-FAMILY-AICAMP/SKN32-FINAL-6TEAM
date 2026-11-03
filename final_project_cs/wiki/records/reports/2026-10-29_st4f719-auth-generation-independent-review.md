---
type: report
title: ST4F-719 인증 세대 경합 수정 독립 검토
status: draft
domain: travel
---

2026-10-29, 지정된 [수정 인계](../../../../wiki/handoff/2026-10-29_st4f719-auth-generation-race-fix.md)를 독립 검토했습니다. **검토한 인증 수정에서 새 제품 결함은 재현되지 않았습니다. 통합·릴리스 HOLD는 유지합니다.** 보안 관문은 실행 환경 복구 후에도 보존 XML을 검출합니다. 이번 세션은 수정 담당자의 자체 검증과 별개인 검토이며, 매니저·기능 담당자 전체 승인이나 최신 통합본 수락을 대신하지 않습니다.

## 범위와 지침

기존 `scratch/st4f719-blocker-independent-20261029/repo`만 재사용했습니다. 루트 사용자 지침, 후보 cs의 AGENTS/RULE, wiki 허브·역할·코드 경로·웹 인증 계약, transport 네 파일과 호출부·시험을 읽었습니다. 후보 루트에는 AGENTS와 상위 wiki가 없어 원본의 읽기 자료를 참조했습니다. 원본 제품 코드·Git 설정·색인에는 쓰지 않았습니다.

프로필의 [Windows isolated Git test validation 스킬](C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/skills/windows-isolated-git-test-validation/SKILL.md)을 적용했습니다. 현재 도구 목록에 coord 기능이 없고 `wiki/coord`, `_coord`도 없었습니다. 기존 `scratch/st4f719-review-20261029/coord-read.json`의 snapshot 62개·관련 notice 13개와 후보의 coord 요약을 읽었습니다. 과거 snapshot을 실시간 예약·현재 tip 확인으로 간주하지 않습니다. 통합 예약·외부 통지·tracker 변경은 하지 않았습니다.

## 발견 사항과 판정

1. **기존 보안 차단 유지.** 서명된 Git helper를 정확한 Python 자식 환경에서 실행하자 scanner가 실제 추적 파일을 열거했습니다. 실패는 이제 Git PermissionError가 아니라 기존 `wiki/records/evidence/2026-10-29_st4f728-guest-logout/security-ready.xml`의 탐지 5건입니다. 보안 124/125 = 99.2%, 필수 관문 2/3 = 66.7%입니다. detector·예외·XML·assertion을 바꾸거나 삭제하지 않았습니다.
2. **인계 해시의 의미를 구분해야 합니다.** 실제 후보 HEAD는 `efeb873a8d065fbd28fe8e92dcc42e5cfb3de3e3`이고 setup의 기준은 `656579fe37d613a64caeb96cdb344958890a1c4d`입니다. Git 색인은 후자의 전체 기준과 cached diff 0으로 일치합니다. cs 기준 경로·색인 각각 10,889개가 일치하고 파일 누락 0입니다. HEAD를 오늘 수정본 커밋이나 최신 원격 tip으로 보고하지 않습니다. 이 사본은 cs 중심으로 materialize되어 있어 루트 전체 working tree의 일반적 검증·병합 준비 완료를 주장하지 않습니다.
3. **실제 경계와 fixture를 구분합니다.** 기존 Edge 18건의 업무 401과 일부 logout-login은 제어한 응답입니다. 별도 1건은 실제 PG 로그아웃의 늦은 응답과 같은 고객의 새 서버 세션을 검증합니다. 이번 새 6건은 실제 PG에서 구 세션을 폐기하고 `/auth/me`의 실제 401 응답을 보류한 뒤 새 서버 세션으로 인증하여 구 응답을 완료합니다. 세 watcher·api·openApi·streamApi 각각을 통과했습니다. 이때 401의 제공 endpoint는 `/auth/me`로 연결한 것이며, 실제 여행 업무 쓰기 endpoint나 외부 OAuth 제공처 로그인을 시험한 것은 아닙니다.

## 동작 검토와 실행 결과

`client.ts`는 요청 시작의 세대를 401 처리에 전달합니다. 같은 scope refresh는 세대를 유지하고, A→B→A 및 logout→새 인증은 세대를 바꿉니다. 로그아웃의 새 인증 진입 확인은 저장소 정리·다른 탭 종료 신호보다 먼저입니다. 세 watcher는 HTTP 401(빈 응답 포함)을 해당 세대에만 적용하며 오래된 packet 전달을 막습니다. 스트림 쓰기의 HTTP/인증 error event와 재연결 검사도 원래 세대를 사용합니다. public 로그인 실패 코드와 쿠키를 생략하는 공지 API는 세션 만료와 구분됩니다. 공통 client 밖 fetch 7곳과 해당 호출부를 대조했습니다. 모든 업무 endpoint 전수 검증의 분모는 모릅니다.

새 독립 단위 25건은 **401 headers 수신 후 JSON body를 읽는 도중의 전환**, 세 watcher 등의 다른 코드 HTTP 401, 같은 scope 강제 refresh 중 명시적 로그아웃 완료를 확인합니다. 같은 시험 바이트로 수정 전 네 transport를 적용하면 5/25 = 20%, assertion 실패 20건이며, 후보로 복구하면 25/25 = 100%입니다. RED 실행 동안 다른 시험은 실행하지 않았고 finally에서 네 파일을 바이트 복구했습니다.

| 검증 | 이번 실행 결과 |
|---|---|
| 전체 웹 Vitest, 독립 25건 포함 | 1,463/1,463 = 100%, 실패·skip 0 |
| 새 독립 단위 수정 전 / 후보 | 5/25 = 20% / 25/25 = 100% |
| TypeScript / transport·기존 새 시험 lint | 2/2 = 100%, exit 0 |
| 기존 PG·Edge 인증 세대 경합 | 19/19 = 100% |
| 기존 미리보기 소유권 | 28/28 = 100% |
| 기존 실제 인증·다중 탭·로그아웃 | 10/10 = 100% |
| 실제 여행 목록 401 오류 화면 | 1/1 = 100%, 스크린샷 직접 확인 |
| 새 실제 PG 폐기 쿠키 401 + 새 인증 | 6/6 = 100% |
| 위 최종 Edge 합계 | 64/64 = 100%, skip·flaky 0 |
| 실제 PG 쿠키 e2e | 38/38 = 100%, skip 0 |
| DoD | 26/26 = 100% |
| 계약 / 보안 | 367/367 = 100% / 124/125 = 99.2% |
| 필수 관문 | 2/3 = 66.7%, HOLD |
| 실행 전 고정한 소스·시험·보호 파일 | 673/673 = 100% SHA256 유지 |
| 보호 scanner·XML | 2/2 = 100% SHA256 유지, 위 673개에 포함 |
| app·stub·API·PG 종료 후 포트 거부 | 4/4 = 100% |

새 Edge 최초 실행은 0/6 = 0%였습니다. 일반 화면 요청이 실제 합성 PG 쿠키를 모르는 stub에서 401을 받아 **초기 인증 확인 단계**에서 실패한 harness 오류입니다. 최초 spec은 `edge-fixture-before.txt`, 원시 실패 JSON·로그·error context는 별도 이름으로 보존했습니다. 기존 PG Edge 방식대로 `/auth/me`·logout은 실제 API에 연결하고 일반 화면 요청만 stub의 known-session으로 연결했습니다. 대상 401을 stub으로 바꾸거나 assertion을 완화하지 않았으며, 수정 후 전체 6건을 새 evidence prefix로 실행했습니다. 이 6건 실패를 제품 RED 20건과 혼동하지 않습니다.

## Git 실행과 scanner 범위

기존 helper `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-candidates-20261029d/files/tf106-20261029/continue-711-20261029/git-tool/cmd/git.exe`를 재사용했습니다. Authenticode **Valid**, 서명자 Johannes Schindelin, shell 및 정확한 Python 실행 버전 `2.56.0.windows.4`를 확인했습니다. 다운로드·새 clone·전역 ACL/보안 정책 변경은 없습니다. 시험 전용 setup 파일의 Git 경로를 백업 후 임시 지정하고 finally에서 원래 바이트로 복구했습니다. 모든 Git 호출은 `GIT_OPTIONAL_LOCKS=0`입니다.

NUL 구분 경로로 열거한 cs 추적 10,889개를 extended-length 파일 읽기와 대조했습니다. scanner 예상 텍스트 9,692개와 실제 반환 9,692개가 일치하고 누락·예상 밖 파일 0입니다. 수정 transport도 이 추적 범위에서 실제 working bytes로 읽힙니다. 별도로 미추적 새 시험을 포함한 웹 src/tests 673개를 같은 detector로 검사해 탐지 0을 확인했습니다. `.env.apikeys`의 check-ignore는 정확히 0, `.env.apikeys.example`은 정확히 1입니다. 새 시험 두 개를 원래 색인에 추가하지 않았습니다.

검토 도구 자체의 최초 audit는 기본 Python의 pytest 부재, 이어서 현재 프로세스 PATH 미적용으로 실패했습니다. 정확한 Python과 process-local PATH를 적용한 뒤 전체 audit를 실행했습니다. provenance 대조의 최초 HEAD 기준 및 인용된 한글 경로의 줄 분리 결과는 잘못된 비교였으며 원시 JSON을 보존했습니다. 최종은 pinned 기준·NUL 경로·실제 접근·색인 diff 0으로 확인했습니다. scanner와 제품 시험을 고쳐 환경 문제를 우회하지 않았습니다.

wrapper가 자식 실패에도 0을 내므로 **실제 pytest XML·Playwright JSON과 각 자식 로그**로 판정했습니다. 원시 보안 XML·실패 로그는 격리 사본에 보존하고 문서에 탐지 값을 다시 싣지 않습니다.

## 증거·자원·인계

증거 중심은 `scratch/st4f719-blocker-independent-20261029/generation-independent-review/`입니다. `review.py`, `finalize.py`, `summary.json`, `frozen.json`, `preservation.json`, `git-signature.json`, `git-scanner-audit.json`, `coverage-reconciliation-pinned-nul.json`, `disk-inventory.json`과 RED/GREEN·전체 웹 결과를 남겼습니다. PG·Edge·관문 원시는 후보 상위의 `*generation-independent-review*` prefix와 `late-mutations/output-browser-generation-independent-review*`에 있습니다. 기존 screenshot은 먼저 백업하고 새 결과를 검토 폴더에 보존한 뒤 기존 경로를 복구했습니다. 합성 actor fixture는 기존 backend가 실행마다 다시 생성합니다.

실행 명령은 setup에 기록된 Python으로 `generation-independent-review/review.py audit`, `gates`, `web`, `browser`, `red-green`, `coverage`를 사용했습니다. 새 PG 경계는 `BROWSER_SPECS=auth-generation-independent-review`, `REVIEW_SUFFIX=-real-revoked-fixed`로 `browser`를 실행했습니다. `finalize.py`가 XML/JSON·해시·포트·inventory를 집계합니다. 제품 파일 변경은 없고 새 단위·Edge 검토 fixture 두 개만 후보에 남겼습니다. 배포물로 통합하지 않습니다.

Node heap은 `--max-old-space-size=1536`, Vitest·Edge worker는 각각 1개입니다. PG·Next 캐시를 재사용했고 큰 DB/모델 사본을 만들지 않았습니다. 관문 중 메모리가 적은 Python 실행과 웹 단위 실행이 일부 겹쳤으나 Edge 단계와 RED 변경은 순차 실행했습니다. 호스트 전체 RAM의 OS 강제 상한을 설정한 것은 아닙니다. 관측 가용 RAM은 약 3.6~5.6GiB였고 자원 종료를 확인했습니다. inventory lease entries는 0입니다. 새 증거 크기는 `artifact-size-final.json`에 남기며, 기존 PG/Next 캐시의 순증은 시작 크기를 재지 않아 분모 모름입니다. 어떤 자료·DB·사본도 삭제하지 않았습니다.

한 일 목록: 지침·스킬·wiki·coord snapshot 검토, 기존 후보 및 pinned 색인 확인, 서명 Git의 shell/Python 실행·필수 환경 복구, 세 watcher/401/logout/switch/re-login/stream 호출부 감사, 새 body-parse 단위 25건 RED/GREEN, 전체 웹·타입·lint, 기존 Edge 58건·새 실제 PG 경계 6건·화면 검토, 필수 관문·쿠키 e2e, scanner 경로/추적 범위·정확한 ignore exit 검사, 해시 복구·포트 종료·inventory·보고·인계 작성입니다.

**남은 조건:** 보존 증거에 대한 정당한 보안 차단 해결과 전체 필수 관문 재실행, 최신 통합 tip에서의 별도 통합 검증입니다. 외부 제공처 로그인·실제 여행 업무 쓰기·운영 수락·production build는 검증하지 않았습니다. 릴리스·운영 쓰기·push·새 clone·고객 데이터 접근은 0건입니다.
