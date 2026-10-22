---
type: report
title: 프론트엔드 전체 독립 리뷰와 Codex 보고서 대조 (Claude)
status: reviewed
domain: travel
---

# 프론트엔드 전체 독립 리뷰와 Codex 보고서 대조 — 2026-10-23

## 결론

- 브랜치 `review/frontend-audit-20261023`(기준 `a38808b39`)의 `final_project_cs/frontend` 세 앱(web · admin · dev-console)을 Codex 보고서를 읽지 않은 리뷰어 6명이 영역별로 독립 검토했고, 그 결과를 Codex의 [전체 보고서](2026-10-23_frontend-audit.md)·상세 3편과 대조했습니다.
- **통합 결함 43건(P1 5 · P2 38)과 P3 약 86건**을 정리했습니다. 이 중 **35건은 제가 코드를 직접 열어 확인**했고(Codex 19건 전부 + 새 항목 16건), 나머지는 리뷰어가 코드를 읽어 보고한 것입니다(표에 「리뷰어」로 구분).
- **Codex의 19건은 19/19 = 100% 코드 위치·내용이 일치**했습니다. 심각도 판정도 대체로 동의하며, 다른 판단은 §5에 적었습니다.
- Codex가 놓친 것 중 중요한 것: ① git에 추적된 Chromium 브라우저 프로필(History · Login Data · Cookies 파일 127개), ② 세션 만료 뒤 알림 벨 재접속이 게스트 세션을 몰래 만드는 경로, ③ 스트림 호출이 호출자의 AbortSignal을 무시해 언마운트 뒤에도 재접속하는 문제, ④ 로그인 직후 게스트 세션 생성 응답이 회원 세션을 덮는 경합, ⑤ 관리자 사용자 상세의 여행 상태 비교값 불일치(`'진행 중'` vs `active`), ⑥ 실제 모드 관리자의 「데모」 문구가 `/ops` 한 곳이 아니라 차단·한도·발송 확인 메시지에도 있는 점, ⑦ 약관 본문 버전 상수와 서버 버전의 불일치, ⑧ 영어 이용 안내 캡처 9장이 한국어 캡처와 바이트 단위로 같은 점.
- 단위 시험 재실행: web 1,064 · admin 39 · dev-console 55 → **1,158/1,158 = 100%** (Codex 수치와 일치). 코드 수정·커밋·푸시·배포는 0건입니다.

## 1. 기준·방법·범위

| 항목 | 값 |
|---|---|
| 대상 | `D:/FinalProject/Dev/fe-audit-20261023/final_project_cs/frontend/apps/{web,admin,dev-console,mobile}` + `.github/workflows/*` + 계약 대조용 백엔드 `final_project_cs/app/` |
| 독립 리뷰 | 6영역 병렬: web `lib/**`·`app/**` / web `plan-check`·`survey-questions`·`intake-review`·`trip-registration` / web `trip`·`guardian`·`map`·`risk` / web 공통 기능·components·tests·CI·산출물 / admin 전체 / dev-console 전체 + mobile |
| 독립성 | 각 리뷰어에게 `2026-10-23_frontend-audit*.md`를 읽지 말라고 지시. 대조는 제가 마지막에 수행 |
| 점검 축 | 사용자가 지목한 모듈 분리·보안·오류 처리·상태 관리·테스트 누락·하드코딩 + 추가로 API 계약·입력 검증, 비동기 경합, SSE/SDK 생명주기, 성능(중복 요청·재렌더), 접근성, i18n·시간대, 설정·보안 헤더, CI 구성, 저장소 산출물, 의존성, 문서-코드 불일치, 법적 콘텐츠 |
| 실행한 것 | `npx vitest run` 세 앱(TZ=Asia/Seoul) · 리뷰어가 `npx tsc --noEmit`(web) · `npx eslint .`(admin) · `npm audit --omit=dev --package-lock-only`(세 앱) |
| 실행하지 않은 것 | 브라우저 E2E 161 spec · 실서버 · 빌드(Codex 결과 인용) · Codex probe 재실행 |
| 확인 표기 | 「직접」 = 제가 해당 줄을 열어 확인 / 「리뷰어」 = 담당 리뷰어가 코드를 읽어 보고, 제가 재확인하지 않음 / 「추정」 = 코드만으로 발생 조건을 확정하지 못함 |

## 2. 통합 결함 — P1 · P2

ID는 이 보고서의 통합 번호입니다. 「Codex」 열은 Codex 보고서의 ID이며 「—」는 Codex에 없는 항목입니다.

### 2-1. 보안·인증·개인정보 경계

| ID | 우선 | 결함 | 위치 | 확인 | Codex |
|---|---|---|---|---|---|
| F-01 | P1 | OSM 경로선 툴팁에 서버 장소명을 문자열로 `bindTooltip` → Leaflet이 `innerHTML`로 삽입 (DOM XSS 경로) | `web/src/features/map/providers/osm.ts:204,208` ← `route-lines.ts:38` ← `lib/live/route-shapes.ts` | 직접 | WSEC-01 |
| F-02 | P1 | 다른 탭에서 A→B 로그인 뒤 A 화면의 쓰기가 `csrf_failed` → `probeSession(force)`로 B 토큰을 받아 **같은 body 재전송** | `web/src/lib/live/client.ts:329-332` | 직접 | WSEC-02 |
| F-03 | P1 | 관리자 로그아웃이 `['admin']` 키만 지우고 `QueryClient`(staleTime Infinity)는 공유 → 다음 운영자가 `operation-cases`·`operation-settings`·`diagnostics`·`users`·`user-messages` 등 캐시를 **서버 조회 없이** 열람 | `admin/src/components/AdminApp.tsx:50,151`, `features/operations/connected.tsx:13,25`, `source-policy.tsx:36-53` | 직접 | A02 |
| F-04 | P1 | 실제 모드에서 「데모」 문구·`demo.operator`가 그대로: `/ops` 공지(「모든 처리는 데모 상태에만 반영」) + **차단·예외 한도·발송 확인 성공 메시지도 「데모에 반영」** + 「오늘만 · 데모」 옵션 라벨 + 담당자 목록·「내 담당」·답변 후 담당 값·헤더 표시가 `DEMO_OPERATOR` → 실 DB에 `assignee: "demo.operator"` 저장 가능 | `admin/src/features/workflows/screens.tsx:76,87,113,155,241,255`, `overview/screens.tsx:141,144,249`, `AdminApp.tsx:132` ↔ `app/application/admin_service.py:234-237` | 직접(76·113·241·백엔드) / 리뷰어(141·144·155·249·255·132) | A01 + A05 (Codex는 `/ops` 공지와 담당자만) |
| F-05 | P1 | **Chromium 브라우저 프로필 127파일(6.8 MB)이 git에 추적**: `Default/History`, `History-journal`, `Default/Login Data`, `Login Data For Account`, `Network/Cookies`, `Extension/**`, `GrShaderCache` | `web/mockups/merge-conflicts-2026-10-08-v1/.render-temp/playwright_chromiumdev_profile-Wjwnor/**` | 직접(`git ls-files` 127건 · History·Login Data 확인) · 파일 내용은 열지 않음 | — (Codex는 「임시 브라우저 프로필 127개」 바이트만 집계하고 「비밀값 유출 미확인」) |
| F-06 | P2 | 이전 요청의 늦은 401이 요청 세대 확인 없이 현재 세션을 null로 | `client.ts:301-304` | 직접 | WSEC-03 |
| F-07 | P2 | `ensureSession`의 게스트 생성 POST에 `beganWith` 가드가 없어, 그 사이 소셜 로그인으로 회원 세션이 들어오면 **늦은 응답이 게스트 세션으로 덮음**(메모리 CSRF ≠ 쿠키 → 쓰기 실패·메뉴 「게스트」) | `client.ts:278-291` (대조: `probeSession` 239-262는 가드 있음) | 직접 | — |
| F-08 | P2 | 세션 만료 뒤 여행 알림 벨 재접속이 `sessionInit → ensureSession`을 거쳐 **새 게스트 세션을 몰래 생성**. 서버가 남의 여행에 404를 주므로 게스트 1개 생성 뒤 `unsupported → polling`으로 빠지고 화면은 오류만 보임(무한 루프는 아님) | `lib/live/events.ts:73-77,84`, `features/trip/use-trip-events.ts:69-95` ↔ `trip_api.py` 404 `not_found` | 직접(경로) · 1회 생성은 추정 | — (Codex W3는 「침묵」만) |
| F-09 | P2 | 접수 SSE `watchIntake`가 401/403/429를 모두 `"unsupported"`로 접어 폴링으로 보냄 → 만료 세션으로 GET 폴링 | `lib/live/stream.ts:221` | 직접 | — (W4와 다른 문제) |
| F-10 | P2 | 로그아웃이 등록 초안 `tripilot.web.registration-draft.v1`(sessionStorage) · 채팅 사본 `tripilot.web.live.messages:<tripId>` · 위치 캐시를 정리하지 않음 | `features/account/session-card.tsx:70-80`, `trip-registration.tsx:31-40`, `lib/live/gateway.ts`(messages), `lib/location.ts` | 직접(초안) / 리뷰어(채팅·위치) | WSEC-04 (+채팅·위치는 새 항목) |
| F-11 | P2 | 로그인 전 초안(계획 원문 + 파일)을 IndexedDB에 **만료 없이** 보관하고, 돌아온 경로와 무관하게 다음에 등록 화면을 연 사람에게 복원 후 삭제 | `features/trip-registration/login-draft.ts`, `trip-registration.tsx:137-145` | 직접 | — |
| F-12 | P2 | 사람 확인(Turnstile) 뒤 소셜 로그인 시작 요청이 반복 전송될 수 있음: `mutationFn`이 `location.assign` 뒤 resolve → `isPending` false → `go` 참조가 매 렌더 새것이라 effect 재실행 → `POST /auth/{provider}/start` 재호출(nonce 덮임 → 티켓 불일치 가능) | `features/account/social-accounts.tsx:46-64` | 직접(코드) · 발생은 네트워크 타이밍 추정 | — |
| F-13 | P2 | Turnstile 복구 불가 3종: ① 실패한 `<script>`를 제거하지 않아 재마운트가 끝난 이벤트를 영구 대기 ② `load` 뒤 `window.turnstile` 없음은 `loading` 캐시를 비우지 않음 ③ 실패 시 소셜 버튼 전부 잠긴 채 재시도 버튼 없음 | `features/human-check/human-check.tsx:28-37,81`, `social-accounts.tsx:81` | 직접(①) / 리뷰어(②③) | WSEC-05 (①만) |

### 2-2. SSE · 스트림 · 네트워크

| ID | 우선 | 결함 | 위치 | 확인 | Codex |
|---|---|---|---|---|---|
| F-14 | P2 | SSE 파서: CRLF가 청크 경계에서 갈리면 빈 줄이 생겨 완료 payload가 다른 이벤트로 분리. 현재 서버는 `\n`만 쓰므로 잠복 결함 | `lib/live/events.ts:50` | 직접 | W2 |
| F-15 | P2 | 여행 벨 `watchTrip`에 헤더·heartbeat 타임아웃 없음, `: ping`은 파서가 버려 생존 신호로 안 씀 → 반쯤 끊긴 연결에서 영구 대기(벨 모드라 폴링도 꺼짐) | `events.ts:84-98` | 직접 | W3 |
| F-16 | P2 | 접수 SSE 응답 헤더 대기에 타이머 없음(watchdog은 reader 생성 뒤에만) | `stream.ts:218-224,232` | 직접 | W4 |
| F-17 | P2 | `attempt()`가 자기 `AbortController`만 쓰고 `init.signal`을 덮어써 **호출자가 취소 불가** → 계획 짜기·채팅·후보 스트림(최대 120 s)·동의 읽기가 언마운트·언어 전환·여행 삭제 뒤에도 최대 5회 재접속, 죽은 컴포넌트의 setState 호출 | `stream.ts:70-78`, `features/plan-check/use-server-review.ts:150` (`streamCandidates`에 signal 자리 비어 있음) | 직접(stream) / 리뷰어(use-server-review) | — |
| F-18 | P2 | 스트림 호출은 `csrf_failed`를 재탐색·재시도하지 않음(`api()`와 비대칭) → F-07과 겹치면 로그인 직후 첫 채팅 실패 | `stream.ts:92` | 직접 | — |
| F-19 | P2 | 2xx + 비JSON 본문(빈 본문·HTML) → `response.json()`의 `SyntaxError` 원문이 `role="alert"`로 고객·운영자에게 노출. admin은 `response.ok` 검사 전에 `json()` 호출 | `client.ts:327`, `stream.ts:94`, `admin/src/lib/gateway.ts:168-177` | 직접 | — |
| F-20 | P2 | 접수 스트림 파서 계약 드리프트: 이동수단 허용값에 `taxi` 없음, 검사행에 `risk` 없음 → 스트림으로 온 택시 구간은 `mode:null` (서버 `MOVE_MODES`에는 taxi 있음) | `lib/live/intake-events.ts:61,122` ↔ `app/.../components/intake/review.py:905` | 직접(상수) · 서버가 스트림에 taxi를 내보내는지는 추정 | — |

### 2-3. 상태 관리 · 비동기 경합 (고객 웹)

| ID | 우선 | 결함 | 위치 | 확인 | Codex |
|---|---|---|---|---|---|
| F-21 | P2 | 항로 지킴이 실패 롤백이 `Trip` 전체 스냅샷을 되돌려 SSE로 갱신된 최신 판(일정·version)까지 과거로 | `features/guardian/trip-guardian.tsx:50-66` | 직접 | W1 |
| F-22 | P2 | 결과 화면 카드 질문이 「후보를 찾는 중…」에 **영구 고정**: `askKeys` 변경 시 cleanup이 `live=false`로 응답을 버리고, 재실행은 `cardAsks[id].key === key`라 `continue` | `features/plan-check/plan-check.tsx:1263-1288` | 직접 | — |
| F-23 | P2 | 검색으로 고른 `source:"search"` 카드가 후보 스트림의 다음 `onLive`·최종 갱신에 통째로 덮여 사라짐 | `plan-check.tsx:759-764, 1875-1879` | 리뷰어 | — |
| F-24 | P2 | 편집 응답 `apply(setQueryData)` 전에 `cancelQueries`가 없어 떠 있던 3분 재조회 GET이 옛 revision으로 덮을 수 있음 → 다음 편집 409 `stale_revision` | `features/intake-review/intake-review.tsx:154-156`, `use-server-review.ts:159-162` | 리뷰어 · 라이브러리 동작은 추정 | — |
| F-25 | P2 | 언어 전환 시 옛 언어가 남음: `alternatives`·`moveWays`·`warmed`·`candidateNotes` ref 캐시와 `["route-shapes", tripId, version]`·`["location-stops", tripId]` 쿼리 키에 `language` 없음 | `use-server-review.ts:78-94`, `features/trip/use-route-shapes.ts:12-13`, `features/map/use-my-location.ts:121` | 직접(route-shapes) / 리뷰어(나머지) | — |
| F-26 | P2 | 대안 사진을 첫 목록(onFirst)과 최종 목록에서 같은 장소에 2회씩 조회, `infoOf`에 캐시 없음 → 후보 3개 기준 6회, 호출처 4곳이라 반복 | `use-server-review.ts:184-196, 296, 309-310` | 직접 | W5 |

### 2-4. 지도 · SDK

| ID | 우선 | 결함 | 위치 | 확인 | Codex |
|---|---|---|---|---|---|
| F-27 | P2 | Google·Naver 어댑터가 `update()` 4번째 인자 `selectedLineId`를 받지 않아 선택 경로 강조 없음. 그 외 provider 차이: 히트라인·툴팁 OSM만, `userMoved`/resize 재맞춤 OSM만, `zoomBy` 클램프 OSM만, reduced-motion OSM만, Naver만 `maxZoom 16` | `providers/google.ts:223`, `naver.ts:225` ↔ `model.ts:109`, `live-map.tsx:75` | 직접(시그니처) / 리뷰어(차이 목록) | WSEC-06 (강조만) |
| F-28 | P2 | SDK 인증 실패는 모듈 수명 동안 `authError`로 고정되는데 오류 오버레이의 「지도 다시 불러오기」는 같은 `create`를 다시 불러 **항상 같은 실패** | `providers/sdk-loader.ts:40`, `live-map.tsx:196` | 직접 | — |

### 2-5. 관리자 웹

| ID | 우선 | 결함 | 위치 | 확인 | Codex |
|---|---|---|---|---|---|
| F-29 | P2 | 세션 만료(401) 뒤: `liveRequest`가 일반 `Error`만 던지고 세션 쿼리를 무효화하지 않음, 로그아웃은 `POST /logout` 401로 throw → `void onLogout()`이 삼킴 → 새로고침 전 재로그인 불가 | `AdminApp.tsx:145-152`, `lib/gateway.ts:168-177, 226-229` | 직접 | A03 |
| F-30 | P2 | 루트 `['admin']` snapshot이 `staleTime: Infinity`·포커스 갱신 꺼짐·주기 갱신 없음 → 새 문의·승인 대기·공지 상태·`data.clock` 기준 날짜 경계가 고정. 다른 운영자의 답변을 모른 채 중복 답변 가능(백엔드 `reply`는 중복 거절 없음) | `AdminApp.tsx:50,66,84-89` | 직접 | A04 |
| F-31 | P2 | snapshot의 `LIMIT 500`(사용자·감사·승인·바깥함)을 전체처럼 집계·필터: 홈 「한도에 걸린 사용자」·「우리 서버 호출」, 문의 상세 「이 사용자 오늘」, 사용자 상세 「운영 기록」, 감사 「전체」 기간 — 잘림 표시 없음 | `overview/screens.tsx:79,103,114,138,157`, `workflows/screens.tsx:119,229-230` ↔ `admin_snapshot.py:28,48-51` | 직접(28·51·229) / 리뷰어(나머지) | A06 + A07 |
| F-32 | P2 | 백엔드 `web = sum(counts)`가 `message`를 포함하는데 홈은 `chat + web` → 채팅 이중 계산, 「② 채팅 / ③ 웹」 분해 합이 총계와 불일치 | `overview/screens.tsx:114,270` ↔ `admin_snapshot.py:35` | 직접 | A08 |
| F-33 | P2 | 사용자 상세 「진행 중 여행」이 `trip.status === '진행 중'`인데 백엔드는 `active`를 그대로 줌 → 실제 모드에서 항상 0개, 표에는 영문 원값(`trip-detail.tsx:17`에는 매핑이 있음) | `overview/screens.tsx:154,156` ↔ `admin_snapshot.py:27` | 직접 | — |
| F-34 | P2 | `daily`는 「고객 채팅 메시지 수 · 최근 14일」(`watch: None`)인데 화면은 「외부 API 호출 · 감시/채팅 조회 · 30일/이번 달」로 표시, 14일 초과 선택도 안내 없음 | `overview/screens.tsx:201-230, 260-266` ↔ `admin_snapshot.py:57` | 직접 | — |
| F-35 | P2 | 실제 연결 브라우저 시험 `tests/live/*` 13파일 33건이 **어떤 CI에도 없음**. live config에 `ADMIN_OPS_API_URL` 없음(프록시 시험 2건은 외부 env 없이는 실패 추정), live/unconfigured 포트 3302 충돌, `channel: 'msedge'/'chrome'` 고정 | `.github/workflows/ci-admin.yml:48-61`, `admin/playwright.*.config.ts` | 리뷰어 | — (Codex는 live spec이 mock이라는 점만) |

### 2-6. 테스트 · CI · 산출물 · 의존성 · 콘텐츠

| ID | 우선 | 결함 | 위치 | 확인 | Codex |
|---|---|---|---|---|---|
| F-36 | P2 | dev-console(및 mobile)이 어떤 워크플로에도 없음 → check·Playwright 12건이 손으로만 | `.github/workflows/` 4파일에 `dev-console` 0건 | 직접(리뷰어 2명 교차) | 「CI 공백」 언급 |
| F-37 | P2 | `maps.spec.ts`가 `MAP_TEST_PROVIDER`가 google/naver일 때만 실행되는데 CI는 설정하지 않음 → Google·Naver 어댑터 시험 0회 | `web/tests/live/maps.spec.ts:26`, `ci-web.yml` | 리뷰어 | 「지도 회귀 공백」 언급 |
| F-38 | P2 | 대용량 산출물 추적: `apps/web/mockups` 816파일 122 MB(png 531 · html 106 · webm 10 · mp4 2), `apps/web/.vitest/json/output.json` 281 KB(`.gitignore`에 없음), `public/images` 홈 PNG 4장 7.6 MB와 mockups 중복 사본. 실제 긴 경로 checkout 실패도 발생 | `git ls-files` | 리뷰어(집계) | 「저장소 산출물」(frontend 전체 844파일 124 MB 기준) |
| F-39 | P2 | admin·dev-console `next 16.3.5` 운영 의존성 권고 3종(critical 1 · high 2, next/og RCE · Image SSRF · sharp · source-map-js). 두 앱 모두 `next/og`·`next/image` 미사용, 루프백 바인딩이라 직접 악용 경로는 좁음. fix 가능 16.4.2. `npm run check`에 audit 단계 없음 | `admin/package.json:18`, `dev-console/package.json:20` | 리뷰어 2명 실측 | 동일 |
| F-40 | P2 | 약관 본문의 버전·시행일이 상수(`TERMS_VERSION "2026-10-19.1"`, `TERMS_EFFECTIVE`)인데 동의 기록은 서버 `termsVersion()`(`…+retN`)으로 저장, 전문 해시 키는 서버 버전 + 본문은 상수 버전 → 고객이 본 글의 버전 표기와 기록이 어긋남 | `features/consent/terms-content.ts:17,21,486,782,1043`, `consent-sync.ts:36,84-86`, `terms-viewer.tsx:45` | 직접(상수) / 리뷰어(연결) | — |
| F-41 | P2 | 영어 이용 안내 캡처 9장이 한국어 캡처와 **md5 동일** → 영어 UI의 소개·이용 방법에 한국어 화면 | `public/images/guguroute-guide-{en,ko}-*.jpg`, `features/intro/guide-steps.ts:44` | 직접(md5 1쌍) / 리뷰어(7쌍) | — |
| F-42 | P2 | 한국어 고정 문구 다수: 지도 UI·컨트롤·오류(`live-map.tsx`, `map-controls.tsx`, `sdk-loader.ts`), 시간 편집기 오류 9곳(`use-time-edit.ts:168-189`), lib 오류 문장(`auth.ts`, `agent-keys.ts`, `risks.ts`, `move-options.ts`), 영어 문장 속 「분」·「시간」·「원」, Google SDK `language:"ko"` 고정, `pin.ts:247`이 한국어 `aria-label`을 셀렉터로 사용 | 각 파일 | 리뷰어 | 「국제화」 언급(Google ko·지도 문구) |
| F-43 | P2 | `TERMS_STATUS = "reviewed"`가 변호사 검토 없이 안내문을 내린 상태를 「검토됨」으로 표현(주석이 스스로 인정) — 운영 판단 사항이나 코드 상태값이 사실과 다름 | `terms-content.ts:19` | 직접 | — |

## 3. P3 — 품질·유지보수 (리뷰어 보고 통합, 영역별)

직접 재확인하지 않은 항목이 대부분입니다. 줄 번호는 리뷰어 보고값입니다.

**web `lib/**`·`app/**`** (13): `lib → features` 역방향 import 4곳(`lib/gateway.ts:1`, `lib/live/gateway.ts:1`, `consents.ts:1` 값 import, `intake.ts:1`) · `intake-events.ts:229-257`의 `watchIntake`는 죽은 코드(같은 이름 구현이 `stream.ts`에) · `plan-download.ts:24-29`·`trip-title.tsx:73` `plan_url`에 호스트 검증 없음(`mapLink`·텔레그램·디스코드는 허용 목록) · `telegram-connect.ts`·`discord-connect.ts`가 프로덕션에서도 `http://localhost` 허용 · `intake.ts`·`intake-review.ts`·`extras.ts` 큰 응답이 `as T`만(zod 4.6.5 설치됐으나 lib에서 import 0건) · `client.ts:23` API_BASE 기본값 `http://127.0.0.1:8042`로 조용히 폴백 · `risks.ts:85` POST에 `Content-Type` 없음 · `gateway.ts:210` `conversation()`이 읽기 실패를 전부 삼키고 로컬 사본 표시 · `recovery.ts:594` 404 판정이 status만 · `probeSession(force)`가 진행 중 탐색이 있으면 강제되지 않음(`client.ts:238`) · `start/page.tsx` `returnTo` 정규화가 feature 안에 · `next.config.ts`에 보안 헤더(CSP·frame-ancestors·Referrer-Policy·Permissions-Policy) 없음, Caddyfile에도 없음 · 레거시 `tripilot.web.user-key.v1` 채택 경로 잔존(제거 시점 결정 필요).

**web `plan-check` 외** (17): 서버 표시 문자열(`mode_label`·`grade "추정"`)을 코드가 식별자로 매칭(`plan-rows.tsx:443-460`, `move-mode.tsx`) — `modeKey`가 있는데 안 씀 · 헤더 검색창 `maxLength` 없음(`place-search-header.tsx:26`) · 사진 URL `http:` 허용 → 혼합 콘텐츠(`from-review.ts:34-40`) · 파일 크기 클라이언트 검증 없음(`trip-registration.tsx:394-408`) · 토스트 「되돌리기」가 생성 시점 판단으로 고정 → 늦게 누르면 `cannot_undo` · 삭제→복구 뒤 변경 없는데 「다시 제출」 켜짐 · 매 렌더 `heldAt`/`JSON.stringify` 전체 비교(`plan-check.tsx:255`, `model.ts:399-443`) · `DEFAULT_STAY_MIN`·끼니 창·서울 경계 상수 중복(서버 값 복제) · 폴백 `actions` 객체 매 렌더 재생성(`intake-review.tsx:277-295`) · 이동수단·늦춤 조회 실패가 무음 「옵션 없음」·재시도 없음(`plan-check.tsx:1232,1276`) · `hasRecommendation` 재시도 타이머 cleanup 누락 · 「다시 제출」 삭제 루프 부분 실패 시 반쯤 갱신(`:1132-1139`, 서버는 edits[] 일괄 수신 가능) · 날짜 탭 `tablist`에 `aria-controls`/`tabpanel` 없음, `<input type="time" autoFocus>` · 설문 목록이 줄면 `at` 범위 초과 · 드라이런 실패 시 같은 요청 즉시 재전송(`use-server-review.ts:417`) · 매 키 입력마다 12,000자 sessionStorage 저장 · `sendTimes("before", …)` 인자 의미 혼동 · plan-check ↔ intake-review 양방향 import.

**web `trip`·`map`** (12): `trip-screen.tsx` 871줄에 시트 제스처·스와이프·catch-up·지도 픽·진행 보고·알림 센터·announce가 한 컴포넌트(useState 30+) · Google/Naver는 데이터가 조금만 바뀌어도 마커 전부 재생성, 재배치는 `idle`에서만(OSM은 핀별 diff) · Naver 경로선 click 리스너 미해제 · `ownVersions` 예측이 빗나가면 변경 막대+결과 토스트 동시(추정) · 서울 중심·줌·색·`v:"weekly"` 상수 3 provider 중복 · `TripView` 매 렌더 `update()`+`relayout()`(인라인 콜백·`toMapPoints` 매번 새 배열) · 제안 선택 중 알림 3초 폴링 최대 90초(SSE 있어도) · 지도 버튼 툴팁 이중 낭독, 경로선 키보드 접근 불가 · 「n분 전 확인」 기기 시계 기준 · 지도 키 referrer 제한은 코드로 확인 불가(배포 기록 확인 필요) · `GoogleMap` 결정 effect `deps []`(의도, 기록만).

**admin** (11): 프록시 기본 포트 8070 이중 정의, 미설정 시 조용히 폴백(`route.ts:26`) · 명령 성공 뒤 `refetch()` 실패가 성공 토스트와 동시 · `UnlimitedModeSwitch` `role="alertdialog"` div — 포커스 이동·가둠·Escape 없음(`api-limits.tsx:88-92`) · 메시지 페이지 크기 20 프론트 고정(`user-conversations.tsx:29`) · `toLocaleString('ko-KR')`에 `timeZone` 없음(`connected.tsx:27`, `simulation.tsx`) · LLM 토큰 합계가 null을 0으로(`screens.tsx:266`) · 실제 모드 감사 작업 종류가 영문 키·JSON 원문 · `usageExempt`가 snapshot에 없어 QA 계정이 한도 도달로 보일 수 있음(추정) · `MAX_QUOTA`·`UNSET_BUDGET_CAP`·`WATCH_CHECKS`·`USER_PAGE_SIZE`·`NEAR_CAP_PERCENT("팀 합의 전")` 백엔드 상수 복제 · `AdminGateway`가 `snapshot/execute/reset`뿐이라 화면이 `operation*` 함수를 직접 import하고 `isDemoMode` 분기 14회 · `screens.tsx:4` 미사용 import 경고.

**dev-console** (16): Playwright가 demo 빌드를 전제하나 강제하지 않음, `start --port 3200 --port 3201` 중복 플래그 · `error.tsx`가 `error` 객체를 버리고 모드 무관 문구, `global-error.tsx` 없음 · sessionStorage 누적 상한·초기화 UI 없음, 350 ms 폴링마다 전체 `JSON.parse`+Zod · 미설정 모드 footer·연결 화면 「샘플」 문구 누수 · role 없는 div에 `aria-label` 4곳, 탭 UI `tablist` 없음 · `button:disabled { cursor: wait }` 전역 · 교통수단 라벨 맵 3곳 중복, `matchedOccurrence` 재구현 · 「00시부터 14시까지」 고정 문구 ↔ `hourlyCounts` 길이 · `management-gateway.ts`가 `gateway.ts`의 모듈 레벨 데모 생성 끌어옴 · draft 저장 순서로 한 렌더 불일치(추정), 무효 `storage` 이벤트 구독 · `/runs/<id>` 링크 인코딩 불일치 · 보안 헤더 없음 · README 특정 PC 절대 경로, `UI_EVAL_WORKSPACE.md` 작업 위치 표가 새 콘솔 미반영, DEVELOPMENT.md 모듈 표 4파일 누락 · `@tripilot/*` package name이 이름 변경 예외 목록에 없음(세 앱 공통 결정 필요) · 컴포넌트 단위 시험 0건 · 재시도 뒤 「새 테스트」 전환 시 편집값 초기화 설명 없음.

**web 공통·CI·설정** (17): 구글 버튼이 로그인 상황에도 `mode="link"`(「연결」 문구) · `ci-web.yml` 머리 주석·job 이름 stale(e2e job 없음), `timeout-minutes`·`permissions` 블록 없음, `NEXT_PUBLIC_DATA_MODE: demo` 주석이 현재 `data-mode.ts`와 불일치 · 프로필 수정 화면 저장 버튼 `disabled` 고정인데 입력·검증은 동작, 더티 경고 없음 · 날짜 포맷 5가지 혼재(ISO slice·브라우저 TZ·KST 슬라이싱·`toLocaleString`) · 이용 방법 chip `tablist` 미완성, `<li onClick>` · 로그아웃 완료 뒤 초점이 body로 · 메뉴 drawer 초점 가두기가 disabled 요소 포함, 배경 `inert` 없음 · 소셜 `authorize_url` 검증이 `https?://`뿐(디스코드는 호스트 allowlist) · 영어 장식 문구가 한국어 UI에도, `copy[language]`와 `t(ko,en)` 두 방식 공존 · 텔레그램/웹훅 헬퍼·페이저·확인 다이얼로그 중복 구현, `components/ui`에 Pager/Dialog 없음 · `tsconfig.json`에 옛 `.next-*` 빌드 폴더 11개 include, `.gitignore`에 `.next-*`·`.render-temp/`·`.vitest/` 없음 · `react-hooks/exhaustive-deps` 비활성 13곳, 프로젝트 ESLint 규칙 없음(`any` 0건은 긍정) · account 7/0·human-check 1/0·intro 2/0·components 6/0 단위 시험, vitest `environment: node`라 컴포넌트 렌더 시험 구조적으로 없음 · 온보딩 자유 입력이 localStorage(로그아웃 시 정리됨, 로그아웃 없이 떠나면 잔존) · 문의 작성이 세션 없는 방문자에게 게스트 생성(추정: 의도) · 11px 이하 글자 126건 · 공지 배너 `aria-live` 15초 갱신(참고).

## 4. 긍정 확인 (리뷰어 6명 교차)

- 세션: HttpOnly 쿠키 + 메모리 CSRF, 쓰기에만 헤더, 키·쿠키 동시 전송 금지, `probeSession`의 늦은 응답 가드와 `session-race.test.ts`, 티켓 즉시 제거·nonce 32바이트·`localPath()` 이중 검증(open redirect 없음), 모든 fetch에 `AbortSignal.timeout`.
- 관리자 프록시: 경로 허용 목록·UUID/sha256 정규식·조회 전용 405·쿠키 2종만 전달·`redirect:'manual'`·15초 타임아웃·루프백 origin 강제(단위·live 시험 있음). 데모는 모드 값이 정확히 `demo`일 때만, 연결 실패가 데모로 바뀌지 않음.
- 채팅: `isPending` 차단 + 같은 `request_id` 재사용(중복 적용 없음), SSE가 먼저 판을 올리면 메시지만 덧붙임, 한글 조합 중 Enter 방지. 제안 선택 실패는 고객 말로 바꾸고 `onSettled`에서 재읽기.
- 되돌리기: 전부-아니면-없음, 값 기준 비교, 서버 원자 호출. revision 경합은 409 → `reread()`.
- 외부 링크 `rel="noopener noreferrer"` 일관, 채팅 링크 https만, `mapLink` 접두 검사, `safePhotoUrl`. `innerHTML`·`console.*`·`any` 사용 0건(웹 lib·app·plan-check). `NEXT_PUBLIC_*`는 공개 값만.
- 접근성: 다이얼로그 3종 Escape·초점 가두기·복귀, 알림 센터 `aria-modal`+`inert`, 일차 칩 `tablist` 화살표 이동, 핀 `aria-pressed`, 색 대비 AA 이상(계산값). dev-console skip link·`prefers-reduced-motion`·44px 타깃.
- dev-console 데모 저장소: `strict()` + 유일성·참조 무결성 superRefine, 손상 데이터를 초기화하지 않고 throw, 용량 초과 시 성공 위장 없음.

## 5. Codex 보고서 대조

### 5-1. Codex 19건의 재검증

| Codex ID | 코드 위치 일치 | 내 판정 | 비고 |
|---|---|---|---|
| WSEC-01 | ✔ `osm.ts:204,208` | P1 동의 | F-01 |
| WSEC-02 | ✔ `client.ts:329-332` | P1 동의 | F-02 |
| WSEC-03 | ✔ `client.ts:301` | P2 동의 | F-06. 같은 원인의 F-07(`ensureSession` 가드 없음)은 Codex에 없음 |
| WSEC-04 | ✔ `session-card.tsx:70-80` | P2 동의 | F-10. 채팅 사본·위치 캐시도 같은 문제 |
| WSEC-05 | ✔ `human-check.tsx:28-37` | P2 동의 | F-13. `load` 뒤 `turnstile` 없음 캐시, 버튼 잠김은 Codex에 없음 |
| WSEC-06 | ✔ `google.ts:223`, `naver.ts:225` | P2 동의 | F-27. provider 차이가 강조 외 5가지 더 있음 |
| W1 | ✔ `trip-guardian.tsx:66` | P2 동의 | F-21 |
| W2 | ✔ `events.ts:50` | P2 동의(잠복) | F-14. 현재 서버는 LF만 사용 — Codex도 「모든 운영 응답이 CRLF라는 주장은 하지 않음」으로 명시 |
| W3 | ✔ `events.ts:91` | P2 동의 | F-15. 「침묵」 외에 세션 만료 뒤 게스트 생성(F-08)은 Codex에 없음 |
| W4 | ✔ `stream.ts:218` | P2 동의 | F-16. 401/403 → polling(F-09)은 별개 |
| W5 | ✔ `use-server-review.ts:296,309` | P2 동의 | F-26. `infoOf`에 캐시 없음 직접 확인 |
| A01 | ✔ `workflows/screens.tsx:241` | P1 동의 | F-04. 범위가 더 넓음(차단·한도·발송 확인 메시지, 옵션 라벨, 헤더) |
| A02 | ✔ `AdminApp.tsx:50,151` | P1 동의 | F-03. 남는 키가 `operation-cases` 외 10종 이상 |
| A03 | ✔ `AdminApp.tsx:145-152`, `gateway.ts:168-177` | P2 동의 | F-29 |
| A04 | ✔ `AdminApp.tsx:50` | P2 동의 | F-30. 중복 답변 가능성(백엔드 reply 중복 거절 없음) 추가 |
| A05 | ✔ `workflows/screens.tsx:76,87,113` | P2 → F-04로 통합(P1) | 실 DB `assignee` 저장 가능이라 A01과 같은 경계 |
| A06 | ✔ `screens.tsx:229`, `admin_snapshot.py:51` | P2 동의 | F-31 |
| A07 | ✔ `overview/screens.tsx:114`, `admin_snapshot.py:28` | P2 동의 | F-31. 문의 상세·사용자 상세 운영 기록도 같은 제한 |
| A08 | ✔ `overview/screens.tsx:114`, `admin_snapshot.py:35` | P2 동의 | F-32. 리뷰어는 P1로 봤으나 표시 오류라 P2 유지 |

**19/19 = 100% 일치.** 줄 번호·백엔드 대조·probe 근거 모두 실제 코드와 맞고, 주장 범위(「브라우저 이벤트 실행 미실행」「실사고 재현 아님」)를 절제한 점이 정확합니다.

### 5-2. Codex가 놓친 것 (이 보고서의 새 P1·P2)

| ID | 축 | 왜 놓쳤다고 보는가 |
|---|---|---|
| F-05 추적된 브라우저 프로필 | 저장소 보안 | Codex는 바이트만 집계하고 「비밀값 유출 미확인」으로 넘김. 파일명(History·Login Data·Cookies)만으로도 즉시 조치 대상 |
| F-07 `ensureSession` 경합 | 세션 | `probeSession`의 가드만 보고 형제 함수를 대조하지 않음 |
| F-08 벨 재접속의 게스트 생성 | 세션 | `watchTrip`의 `sessionInit` 호출 의미를 추적하지 않음 |
| F-09 접수 SSE 401/403 → polling | 오류 분기 | W4(헤더 대기)에 집중 |
| F-11 IndexedDB 로그인 초안 | 개인정보 | sessionStorage 초안(WSEC-04)만 봄 |
| F-12 소셜 시작 반복 전송 | 상태 | `social-accounts.tsx` effect 의존성 미검토 |
| F-17 스트림 abort 무시 | 생명주기 | 재접속 정책은 봤으나 호출자 취소 경로는 안 봄 |
| F-18 스트림 csrf 비대칭 | 세션 | `api()`만 대조 |
| F-19 비JSON → SyntaxError 노출 | 오류 처리 | 「`as T` 캐스팅」 일반론으로만 언급 |
| F-20 파서 taxi/risk 드리프트 | API 계약 | 서버 enum과 프론트 상수 대조 없음 |
| F-22 카드 질문 영구 로딩 · F-23 검색 카드 덮임 · F-24 apply vs GET | plan-check 경합 | Codex는 plan-check를 모듈 분리 제안으로만 다룸 |
| F-25 언어 키 누락 | i18n·캐시 | — |
| F-28 지도 인증 실패 재시도 | SDK | sdk-loader 긍정 평가만 |
| F-33 `'진행 중'` vs `active` · F-34 daily 의미 | admin 계약 | 백엔드 대조를 집계 필드 3개에만 적용 |
| F-35 admin live spec CI 밖 | CI | — |
| F-40·F-43 약관 버전·상태 · F-41 영어 캡처 | 콘텐츠 | 약관을 「콘텐츠 파일」로 분류하고 내용 대조 생략 |

### 5-3. Codex에만 있고 독립 리뷰가 놓친 것

독립 리뷰어 6명이 Codex의 19건 중 **직접 보고하지 못한 것은 W4(접수 SSE 헤더 대기 타이머)·WSEC-04(등록 초안)·A06/A07의 세부 2건** 정도이며, 제가 코드로 재확인해 통합 목록에 넣었습니다. 이는 Codex 보고서가 실제로 유효한 발견을 담고 있음을 뜻합니다.

### 5-4. 수치 대조

| 항목 | Codex | 이번 | 판정 |
|---|---|---|---|
| 단위 시험 | 1,158/1,158 | 1,158/1,158 (web 1,064 · admin 39 · dev-console 55) | 일치 |
| lint/typecheck/build | 12/12 통과 | 재실행 안 함(web tsc·admin eslint만 리뷰어 실행, 통과) | 인용 |
| npm audit 운영 의존성 | web 0 · admin 3 · dev-console 3 | 동일 | 일치 |
| 추적 산출물 | frontend 1,629파일 중 mockups 844개 123,960,222 B · 프로필 127개 6,829,217 B | `apps/web`만: mockups 816개 122,483,152 B · 프로필 127개 6,829,193 B | 분모 다름(Codex는 admin·dev-console mockups 포함). 프로필 수 127 일치 |
| 결함 수 | 19 (P1 4 · P2 15) | 43 (P1 5 · P2 38) + P3 약 86 | 통합 기준 차이 — Codex는 「코드·호출 경로로 확인한 결함」만, 이번은 품질 항목까지 |

### 5-5. Codex 보고서에 대한 총평

- **정확성**: 적은 것은 모두 맞습니다. 근거 표기·probe·한계 명시가 모범적입니다.
- **범위의 빈틈**: 세션 상태 머신의 형제 함수(`ensureSession`·`sessionInit`·스트림 경로) 대조, 호출자 취소 경로, 관리자 화면의 백엔드 값 대조(상태 enum·일별 집계 의미·데모 문구 전수), 저장소 추적 파일의 **이름**, 콘텐츠 파일(약관·캡처)의 내용 정합성이 빠졌습니다.
- **구조 제안**: Codex의 모듈 분리 표(plan-check·use-server-review·trip-screen·client/SignOut·events/stream·AdminApp·provider 3종)는 이번 리뷰어들의 제안과 일치합니다. 이번 리뷰는 여기에 「lib → features 역방향 import 4곳과 plan-check ↔ intake-review 양방향 의존을 먼저 끊고 ESLint `no-restricted-imports`로 고정」, 「`AdminGateway`에 users/conversations/tripDetail을 넣어 데모 분기를 화면에서 제거」를 더합니다.

## 6. 권장 구현 순서

1. **경계부터**: F-05(프로필 추적 해제 + `.gitignore` + 이력 제거 판단), F-01(툴팁 `textContent`), F-02·F-06·F-07·F-18(세션 세대 + 주체 비교를 `api`/`streamApi` 공통으로), F-03(관리자 로그아웃 `client.clear()` 또는 운영자별 QueryClient), F-04(실제 모드 데모 문구·`DEMO_OPERATOR` 전수 제거, `operatorId`를 ScreenProps로).
2. **세션·스트림 생명주기 한 PR**: F-08·F-09·F-15·F-16·F-17(401/403 분기 · heartbeat watchdog · 헤더 타이머 · `AbortSignal.any`), F-10·F-11(로그아웃 cleanup과 초안 만료), F-12·F-13(Turnstile·소셜 시작 재전송), F-19(비JSON 포장), F-14·F-20(파서).
3. **상태 경합**: F-21(필드만 롤백), F-22·F-23·F-24·F-25·F-26(plan-check 캐시·언어·취소를 `candidate-cache.ts`로 분리하며 함께), F-27·F-28(provider 공통 `lines.ts`·인증 실패 폴백).
4. **관리자 계약**: F-29·F-30(401 처리·유한 staleTime·수동 새로 읽기), F-31·F-32·F-33·F-34(백엔드가 `truncated/total`·상태 라벨·`web` 포함 관계·`daily` 의미를 계약으로 주고 프론트가 그대로 표시).
5. **CI·산출물·콘텐츠**: F-35·F-36·F-37(admin live·dev-console·지도 provider matrix를 main 전체 검사에), F-38(LFS/ignore), F-39(next 16.4.2 + audit 단계), F-40·F-41·F-42·F-43.
6. 그 뒤 §3의 P3와 모듈 분리.

## 7. 확인 범위와 한계

- 정적 코드 리뷰 + 단위 시험 재실행입니다. 브라우저 E2E·실서버·Codex probe 재실행은 하지 않았습니다. 「리뷰어」 표기 항목의 줄 번호는 리뷰어 보고값이며 제가 재확인하지 않았습니다(제가 표본 확인한 리뷰어 줄 번호 16건은 모두 맞았습니다).
- F-08의 「게스트 1개 생성 뒤 폴링」은 서버가 남의 여행에 404를 준다는 코드로 추론했고 실행하지 않았습니다. F-12·F-24는 타이밍·라이브러리 동작에 따라 발생합니다.
- F-05의 프로필 파일 내용(쿠키·로그인 데이터 실제 값)은 열지 않았습니다. 공개 저장소에 올라갔는지는 원본 원격에서 확인해야 합니다.
- 심각도는 제 판단이며 팀 결정이 아닙니다.
- 수정 완료 **0/43 = 0%**. 제품 코드 수정·커밋·푸시·배포 0건. 이 보고서와 wiki 색인·인계 한 줄만 추가했습니다.

## 8. 작업 기록

- **02:27 KST 증거 위치 정리(사용자 지시)**: Codex가 저장소 루트 `evidence/`와 `final_project_cs/evidence/`에 둔 probe 5파일을 [web-security/](../evidence/2026-10-23_frontend-audit/web-security/)·[web-state/](../evidence/2026-10-23_frontend-audit/web-state/)로 복사했습니다(`cmp` 5/5 동일). 상대 경로만 새 깊이에 맞게 고쳤습니다. 원래 위치의 파일은 삭제 승인 규칙에 따라 지우지 않았고 커밋에서만 뺐습니다.
- **재실행**: web-security 3/3 재현·exit 0([기록](../evidence/2026-10-23_frontend-audit/web-security/result-after-move.txt)). web-state 5개 결과는 시각 외 저장본과 동일([결과](../evidence/2026-10-23_frontend-audit/web-state/web-state-probe-result-after-move.json)).
- **보고서 링크 수정**: Codex 보고서 3편의 probe 링크·재실행 명령을 새 경로로 바꾸고 이동 주석을 달았습니다. 수정 전 사본은 [link-move-backup/](../evidence/2026-10-23_frontend-audit/link-move-backup/)에 있습니다. 6편 상대 링크 깨짐 0건.
- **커밋·푸시**: 리뷰 문서만 `review/frontend-audit-20261023`에 커밋해 팀 저장소 GitHub에 같은 이름으로 푸시했습니다. role-eval-ui 병합은 다른 PC의 시험 수정이 매니저에 병합되고 role-eval-ui가 최신이 된 뒤 하기로 했습니다(사용자 결정).
