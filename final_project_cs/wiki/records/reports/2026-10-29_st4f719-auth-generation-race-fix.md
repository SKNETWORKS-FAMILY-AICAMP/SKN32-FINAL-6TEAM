---
type: report
title: ST4F-719 인증 세대 경합·watcher 401 수정
status: draft
domain: travel
---

2026-10-29, 지정한 독립 검토의 실패 8건을 기존 격리 후보에서 재현하고 수정했습니다. **인증 수정은 로컬 검증 완료, 통합·릴리스는 HOLD**입니다. 원본 제품 코드·scanner·보호 XML을 변경하지 않았고 clone·push·운영 접속·배포·자료 삭제는 0건입니다.

담당과 자체 검토는 이번 Codex 세션입니다. 새 독립 검토자 승인으로 표시하지 않습니다. 영향 범위는 웹 공통 client, 세 watcher, 스트림 쓰기·재연결입니다. 루트/후보 AGENTS·RULE, wiki 허브, 역할·코드 경로·웹 인증 계약, 기존 독립 보고를 읽었습니다. 전용 coord 도구와 현재 `wiki/coord`, `_coord`는 없었습니다. 기존 `scratch/st4f719-review-20261029/coord-read.json`의 62개 snapshot 요약과 관련 13개 notice를 확인했으며 최신 예약 상태·통합 tip을 확인한 것으로 간주하지 않습니다. 통합 예약은 하지 않았습니다.

## 후보와 변경

기존 `scratch/st4f719-blocker-independent-20261029/repo`만 재사용했습니다. setup의 후보 기준 해시는 `656579fe37d613a64caeb96cdb344958890a1c4d`이며 이번에 Git으로 새로 확인한 HEAD라는 뜻은 아닙니다. 증거와 수정 전 백업은 같은 상위 폴더의 `generation-race-fix/`입니다.

- `client.ts`: 요청 시작의 인증 세대를 401 완료까지 전달합니다. 이전 session 객체의 세대도 WeakMap에 보존하며, 직접 호출이 현재 세대를 기본값으로 가져오지 않습니다. A→B→A 또는 로그아웃→새 A 이후의 옛 401은 새 인증을 바꾸지 않습니다. 같은 scope의 강제 재확인은 세대를 유지합니다.
- 로그아웃은 시작 후 새 인증 진입이 있었는지 **저장소 정리·다른 탭 종료 신호보다 먼저** 검사합니다. 재확인이 A를 이미 401로 끝냈지만 새 로그인이 없으면 명시적 로그아웃 정리는 계속합니다. 새 A의 diff·onboarding·query와 다른 탭 신호를 옛 완료가 지우지 않습니다.
- `events.ts`, `intake-events.ts`, `stream.ts`: 세 watcher의 HTTP 401(빈 본문 포함)이 해당 요청 세대만 무효화합니다. 구독 이후의 옛 packet도 새 인증에 전달하지 않습니다. 기존 404/405·429·망 실패의 반환 분류는 유지합니다.
- 스트림 쓰기도 원래 인증 세대로 401·인증 error event를 처리하고, A→B→A 뒤 자동 재연결이 쓰기 본문을 새 세대로 재전송하지 않습니다.
- 인증 API는 HTTP 401 자체를 처리합니다. 쿠키 동반 `openApi`는 `unauthenticated` 또는 코드 없는 HTTP 401만 세션 만료로 처리하며, 공개 로그인 동작의 `invalid_credentials`·`ticket_invalid`·`unauthorized` 코드는 그대로 반환합니다. `credentials: omit`인 공개 공지 조회 두 곳은 세션을 바꾸지 않습니다.

서버 필드·권한 계약·인증 저장소 형식은 바꾸지 않았습니다. 기존 401 오류 query를 지우거나 자동 재시도하는 변경, 새로운 하드코딩 폴백은 넣지 않았습니다. 후보의 웹 인증 wiki에는 이 내부 경합 처리 범위를 추가했습니다.

## 실행 결과

| 검증 | 실제 결과 |
|---|---|
| 지정 독립 집중 시험, 수정 전 | 32/40 = 80%, 실패 8, skip 0 |
| 같은 집중 시험, 수정 후 | 40/40 = 100%, 실패·skip 0 |
| 원래 독립 경계 12건, 최종 전체 실행에서 | 12/12 = 100% |
| 새 인증 세대·공개 API·packet 경계 | 101/101 = 100% |
| 최종 전체 웹 Vitest | 1,438/1,438 = 100%, 실패·skip 0 |
| TypeScript / 변경 파일 lint | 2/2 = 100%, 각각 exit 0 |
| 새 실제 PG 인증 + Edge 경합 | 19/19 = 100%, skip/flaky 0 |
| 기존 미리보기 소유권 Edge | 28/28 = 100%, skip/flaky 0 |
| 기존 실제 PG 인증·로그아웃 Edge | 10/10 = 100%, skip/flaky 0 |
| 실제 여행 목록 401 오류 화면 | 1/1 = 100%, 만료 문구·로그인·재조회 버튼 유지, 스크린샷 직접 확인 |
| 최종 단위 변이 검출 | 8/8 = 100% |
| 실제 PG 인증 + Edge 세대 검사 제거 변이 검출 | 1/1 = 100%, 예상 실패 뒤 후보·러너 바이트 복구 |
| PG 쿠키 인증 e2e | 38/38 = 100% |
| DoD | 26/26 = 100% |
| 계약 관문 | 365/367 = 99.5%, Git 실행 불가 2건 |
| 보안 관문 | 124/125 = 99.2%, Git 실행 불가로 scanner 시험 1건 실패 |
| 이번 필수 관문 | 1/3 = 33.3%, HOLD |
| 의도한 변경 외 기존 소스·보안 파일 | 503/503 = 100% SHA256 일치 |
| 보호 scanner / 기존 XML | 2/2 = 100% SHA256 일치 |
| app·stub·API·PG 종료 후 포트 거부 | 4/4 = 100% |

첫 전체 웹 실행 1,429/1,429 이후 packet 6건·HTTP 상태 1건·쿠키 없는 공개 조회 2건을 추가해 최종 1,438건을 실행했습니다. 첫 실행 원문은 `first-web-run/`에 보존했습니다. 원래 실패 8건의 기대값은 완화하지 않았습니다.

새 단위 시험은 6개 호출 경로 × envelope/빈 본문 × 현재/refresh/전환 복귀/로그아웃 후 로그인/다른 계정 60건을 포함합니다. 같은 세션 refresh는 실제 `probeSession(force=true)`로 상세·CSRF를 갱신하며 검증합니다. 쓰기 401은 fetch 1회만 발생하는지 확인합니다. 현재 소스의 직접 fetch 7곳을 감사했고, 세션 공통 client·watcher/쓰기 스트림 5곳과 쿠키를 생략하는 공지 2곳을 구분했습니다. 개별 endpoint 전수 검증의 분모는 모릅니다.

Edge 19건 중 18건은 실제 로컬 PG의 `/auth/me`로 인증하고 대상 업무 요청의 빈 401 완료를 제어합니다. 나머지 1건은 **실제 PG 로그아웃 응답을 지연**시킨 동안 같은 customer의 별도 새 서버 세션으로 바꿔, 메모리·query·diff와 실제 `/auth/me` 쿠키가 유지되는지 확인합니다. PG fixture G와 G2는 같은 customer이며 세션 scope는 서로 다릅니다. 업무 미리보기 응답은 stub입니다. 실제 여행 업무 DB 쓰기·외부 OAuth 제공처 로그인·운영 환경을 검증한 것은 아닙니다.

최종 단위 변이는 401 세대 검사, 로그아웃 진입 검사, watcher 401, 빈 공개 401, 공개 로그인 오류 경계, 스트림 재연결 세대, 스트림 인증 error event, watcher packet 세대 검사입니다. 모두 113개 고정 시험 중 관련 assertion이 실패했습니다. Edge 변이는 A→B→A 뒤 옛 401이 새 A를 null로 만드는 것을 검출했습니다. 첫 변이 묶음은 시험 추가 시점 때문에 분모 111/113이 섞여 있어 별도 보존했고, 최종 묶음은 모두 113건입니다. 원래 실패·변이 실패 로그는 지우지 않았습니다.

## 관문 HOLD와 실행 환경 한계

기존 러너 setup의 portable Git 경로는 현재 없습니다. PATH의 WindowsApps Git은 `WinError 5` 실행 거부입니다. 계약의 실제 키 파일 ignore·템플릿 ignore 두 시험과 scanner의 tracked 파일 열거가 이 지점에서 실패했습니다. 이번 보안 실패를 과거 보호 XML 탐지 실패와 같은 원인이라고 보고하지 않습니다. **scanner가 실제 tracked 파일을 검사하는 단계까지 가지 못했으므로 최신 보안 관문은 미확인**입니다. 과거 필수 2/3 = 66.7%와 보호 XML 관련 HOLD도 해제하지 않습니다. scanner·XML·시험 assertion·Git 설정을 고쳐 우회하지 않았습니다.

실제 Playwright JSON과 pytest XML을 읽어 판정했습니다. 기존 wrapper는 하위 실패에도 exit 0을 반환할 수 있어 wrapper 종료 코드로 통과를 선언하지 않았습니다. 최신 통합 tip·타 담당 검토·전체 실제 업무 endpoint·운영 수락·production build는 이번 검증 범위 밖입니다.

## 증거와 보존

`generation-race-fix/final.json`, `preservation-final.json`, `mutations-final.json`, `fetch-audit.json`, `disk-inventory-final.json`, `ports-closed.json`, `commands.md`를 보존했습니다. `candidate-change.patch`는 제품 transport 4개·새 단위 시험·후보 인증 wiki 변경만 담습니다. 기존 로컬 identity-test 페이지에 추가한 export와 새 Edge spec, PG G2 생성은 **검증 fixture**이며 제품 배포물로 통합하지 않습니다. 변경한 기존 fixture도 `before/`에 백업했습니다.

기존 소스·보안 manifest 508개 중 의도한 변경은 transport 4개와 로컬 identity-test fixture 1개입니다. 나머지 503개와 보호 scanner/XML은 일치합니다. 원본에 코드 역복사하지 않았고 새 보고·인계만 추가했습니다.

Node/Vitest worker와 Edge worker는 각각 1개로 제한하고 기존 PG data directory와 Next 캐시를 재사용했습니다. 새 clone·전체 DB 사본·수 GB 모델 산출물은 만들지 않았습니다. inventory의 lease entries는 0이며, 소유하지 않은 lease를 release하지 않았습니다. 새 증거의 파일 수·바이트는 `artifact-size.json`에 적습니다. 기존 PG/Next 캐시 순증은 사전 측정이 없어 분모 모름입니다. 모든 파일·DB 디렉터리는 남겨 두었습니다.

한 일 목록: 지침·wiki·coord snapshot 읽기, 기존 후보 재사용·수정 전 백업, 8건 RED 재현, 요청 세대·watcher 수정, 공개 경계·스트림 쓰기·packet 시험, 전체 웹 회귀·타입·lint, 실제 PG/Edge·화면 확인, 단위/Edge 변이, 필수 관문 실행·Git 환경 실패 구분, 해시·종료·inventory 확인, 패치·보고·인계 작성입니다.

후속은 동작하는 승인된 Git 실행 환경에서 계약·보안 관문을 재실행하고, 최신 tip에 대한 통합 및 별도 검토를 진행하는 것입니다. 이 수정의 로컬 통과를 배포·제품 전체 완료로 간주하지 않습니다.
