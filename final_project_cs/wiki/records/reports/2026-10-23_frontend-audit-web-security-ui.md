---
type: report
title: 프론트엔드 전체 리뷰 — 고객 웹 인증·보안·지도·공통 UI
status: reviewed
domain: travel
---

# 프론트엔드 전체 리뷰 — 고객 웹 인증·보안·지도·공통 UI

- 확인일: 2026-10-23 01:10~01:31 KST. 시간은 검토 구간이며 운영 실행 시각이 아닙니다.
- 대상: `review/frontend-audit-20261023`, 격리 사본 `D:\FinalProject\Dev\fe-audit-20261023`의 `final_project_cs/frontend/apps/web`입니다.
- 범위: 인증/CSRF/브라우저 저장소, 동의·위치 수집 경계, 외부 URL, 지도 DOM/SDK, 공통 UI 접근성, 설정과 관련 테스트입니다. 여행 편집·검증 상태 흐름 및 관리자 앱은 병렬 보고서에서 다룹니다.
- 적용 규칙: 루트와 cs의 AGENTS/CLAUDE, cs RULE, 코드 경로 안내 및 D-CS-012를 읽었습니다. 전역 `C:\Users\u\.codex\AGENTS.md`, `C:\Users\u\.claude\CLAUDE.md`는 존재하지 않았습니다.
- 소스 수정·서버 시작·실서비스 데이터 생성·배포는 하지 않았습니다. 새 보고서와 독립 재현 probe만 추가했습니다. 기존 파일 덮어쓰기 대상은 없습니다.

| 검증 종류 | 결과 | 해석 |
|---|---|---|
| 독립 소스 재현 probe | 최초·안전 이동 후 각각 3/3 = 100% 재현 | **현재 결함 동작을 확인하는 assertion**이므로 제품 안전성 통과를 뜻하지 않습니다 |
| 브라우저/실서버 공격 재현 | 0/1 = 0%, 미실행 | 실제 계정/네트워크를 사용하지 않았습니다 |
| 전체 lint/typecheck/unit/build | 총괄 보고서 참조 | 이 보고서의 probe와 분리합니다 |

## 확인된 결함

### WSEC-01 · P1 · OSM 경로 툴팁이 서버 문자열을 HTML로 실행합니다

- 위치: `frontend/apps/web/src/features/map/providers/osm.ts:204`, `:208`의 `bindTooltip(line.title, ...)`.
- 데이터 흐름: 서버 `app/domains/travel_ops/instances/mobility/route_shape.py:369`, `:412`가 `place.name` 또는 `title`을 `from/to`로 반환합니다. `lib/live/route-shapes.ts:112`가 그 문자열을 보존하고, `features/map/route-lines.ts:37`이 툴팁 제목으로 합칩니다. 등록 입력 `entry/trip_api.py:157`, `:174`는 장소명/제목에 최소 길이만 확인하며 HTML을 제거하지 않습니다.
- 트리거: 외부 계획/저장된 장소명에 HTML 이벤트 속성이 들어 있는 경로를 OSM 지도에서 열고 선 위에 포인터를 올립니다. 예를 들어 무해한 DOM 표시만 하는 `<img src="x" onerror="document.body.dataset.audit=1">`도 문자열로 보존됩니다.
- 영향: React의 텍스트 escaping을 거치지 않는 DOM XSS 경로입니다. 실행된 스크립트는 그 페이지의 권한으로 DOM과 API를 사용할 수 있습니다. HttpOnly 쿠키 자체를 읽는다는 뜻은 아닙니다. 다른 사용자에게 입력을 주입하는 공유 경로와 운영 CSP 우회까지 실행해 본 것은 아닙니다.
- 확인: 설치된 Leaflet **1.9.4** `node_modules/leaflet/src/layer/DivOverlay.js`의 `_updateContent()`는 문자열에 `node.innerHTML = content`를 실행합니다. 독립 probe는 실제 서버 응답 parser → 제목 builder → 해당 설치 파일의 함수 본문 실행을 거쳐 공격 문자열이 `innerHTML`에 들어가는 것을 확인했습니다. 브라우저 이벤트 자체 실행은 미실행입니다. [Leaflet 공식 Tooltip 설명](https://leafletjs.com/reference.html#tooltip)도 문자열을 HTML로 해석하며 `HTMLElement.textContent` 사용을 안내합니다.
- 수정: 두 호출 모두 공통 `tooltipText()`에서 새 DOM 요소의 `textContent`에 제목을 넣어 전달합니다. 제목은 서식이 필요 없는 텍스트이므로 HTML 허용 범위를 도입할 이유가 없습니다.
- 누락 테스트: 실제 Leaflet DOM에서 HTML 포함 장소명을 표시한 후 HTML 요소/이벤트가 만들어지지 않고 원문 텍스트만 나오는 회귀 테스트가 필요합니다.

### WSEC-02 · P1 · 다른 탭에서 계정을 바꾼 뒤 이전 계정의 쓰기를 새 계정에 재전송합니다

- 위치: `frontend/apps/web/src/lib/live/client.ts:329-331`.
- 트리거: 탭 A에서 사용자 A의 알림/계정 화면을 열어 둔 채, 탭 B에서 로그아웃 후 사용자 B로 로그인합니다. 쿠키는 브라우저 전체에서 B로 바뀌지만 탭 A의 메모리 세션/화면은 A입니다. 탭 A에서 웹훅 변경 같은 쓰기를 실행하면 A의 CSRF + B 쿠키로 403이 나고, `api()`가 B의 `/auth/me` 응답을 받아 **같은 body**를 자동 재전송합니다.
- 영향: A의 화면에서 작성한 알림 채널·동의·에이전트 키 등의 계정 범위 변경이 B에게 적용될 수 있습니다. 여행 ID를 받는 API의 소유권 검사를 우회한다는 주장은 아닙니다. `/v1/web/profile`처럼 현재 사용자만 기준으로 삼는 API가 직접 영향권입니다(`lib/live/profile.ts:73-79`).
- 근거: `WebSession`은 kind/CSRF/만료 정보만 가지고 사용자·세션 세대를 비교하지 않습니다. `subscribeSession()`은 같은 window 이벤트만 듣습니다. 서버 `web_cookie.py:176-185`는 쿠키 세션의 CSRF와 비교하므로 첫 403은 정상 방어입니다. 프론트의 자동 재전송이 사용자 교체를 무시합니다.
- 확인: 독립 probe에서 첫 PUT 헤더 `csrf-account-a`, 403 뒤 `/auth/me`가 `csrf-account-b`, 둘째 PUT이 B 토큰과 최초 body 그대로 전송되는 것을 확인했습니다.
- 수정: 사용자 식별을 노출하지 않는 안정적인 세션/주체 식별자를 API에 포함하고, 쓰기 시작 시점과 refresh 후의 주체가 같을 때만 재시도해야 합니다. 달라지면 진행 중 쓰기를 중단하고 캐시·민감한 입력을 정리한 뒤 새 계정 화면을 읽습니다. 탭 간 로그인/로그아웃 통지도 필요합니다.
- 누락 테스트: 동일 브라우저 context의 두 page에서 A→B 전환 중 `PUT profile`, 동의 저장, 키 생성이 B에게 재실행되지 않는 테스트가 필요합니다.

### WSEC-03 · P2 · 이전 요청의 늦은 401이 새 로그인 세션을 지웁니다

- 위치: `frontend/apps/web/src/lib/live/client.ts:301-304`, 호출부 `:334`.
- 트리거: 세션 A에서 보낸 API 요청을 지연시킨 후 새 세션 B를 받아 `takeSession(B)`가 끝난 다음, A의 요청에서 `unauthenticated`가 도착합니다.
- 영향: `sessionChecked()`는 요청 세대를 확인하지 않고 현재 snapshot을 null로 바꿉니다. 화면은 방금 완료한 로그인을 만료로 취급하며 다음 요청은 불필요한 게스트 생성 경로로 들어갑니다. 쿠키와 프론트 인증 상태가 어긋납니다.
- 확인: 독립 probe에서 현재 세션을 B로 바꾼 뒤 A 요청에 401을 반환하자 `currentSession() === null`이 됐습니다. 기존 `session-race.test.ts`는 `/auth/me`의 늦은 응답만 방어하며 일반 `api()` 요청은 검사하지 않습니다.
- 수정: 요청 시작 세션/세대를 `sessionChecked()`까지 전달하고 현재와 같을 때만 만료 처리합니다. 스트림에서 같은 함수를 부르는 경로에도 적용합니다.
- 누락 테스트: API/스트림 각각의 늦은 401, 세션 생성 중 로그인 교체, 로그아웃 직후 늦은 응답을 다뤄야 합니다.

### WSEC-04 · P2 · 로그아웃 후 같은 탭에서 이전 사용자의 계획 초안이 다시 보입니다

- 위치: `frontend/apps/web/src/features/account/session-card.tsx:70-80`, `features/trip-registration/trip-registration.tsx:31-40`, `:173`, `:235`.
- 트리거: 사용자 A가 여행 계획서에 개인 일정/숙소 정보를 입력하고 전송 전에 마이페이지로 이동해 로그아웃합니다. 같은 탭에서 사용자 B가 로그인한 후 새 여행을 엽니다.
- 영향: 초안 저장 키 `tripilot.web.registration-draft.v1`에는 계정 구분이 없습니다. 로그아웃은 QueryClient, 동의, 온보딩만 비우고 sessionStorage 초안은 남겨서 B의 새 여행 입력에 A의 내용이 보입니다. 브라우저 탭을 닫아야 지워지는 sessionStorage 성질만으로 로그아웃 개인정보 경계를 보장할 수 없습니다.
- 확인 범위: 소스 호출 경로를 확인했습니다. 브라우저 두 계정 재현은 미실행입니다. `clearRegistrationDraft()`는 등록 완료용 함수로 존재하지만 로그아웃에서 호출하지 않습니다.
- 수정: 로그아웃의 공통 cleanup에서 등록 초안, 로그인 인계용 메모리 초안, 채팅 임시 저장 등 사용자 데이터 저장소를 정리하거나 세션 주체별로 분리합니다. 게스트→회원의 의도된 초안 승계와 명시적 로그아웃을 구분합니다.
- 누락 테스트: 같은 탭에서 미전송 초안 작성→로그아웃→다른 계정 로그인→새 여행 빈 입력 확인. 실제 등록 후 초안 정리 테스트만으로는 잡히지 않습니다.

### WSEC-05 · P2 · Turnstile 스크립트 실패 뒤 SPA 재진입으로 복구되지 않습니다

- 위치: `frontend/apps/web/src/features/human-check/human-check.tsx:28-37`.
- 트리거: Turnstile script가 일시 네트워크 오류를 내고, 네트워크 회복 후 페이지 이동·언어 변경 등으로 HumanCheck가 다시 마운트됩니다.
- 영향: error 콜백은 `loading = null`만 설정하고 실패한 `<script id="cf-turnstile-api">`를 제거하지 않습니다. 재시도는 같은 요소를 찾아 listener만 붙이며 이미 연결됐으므로 append도 하지 않습니다. 이전 load/error 이벤트는 다시 오지 않아 새 Promise가 영구 대기합니다. 사람 확인이 필요한 가입/등록이 전체 페이지 새로고침 전에는 막힙니다. 처음 연결이 무기한 지연된 경우에도 timeout이 없습니다.
- 확인 범위: loader의 상태/이벤트 경로 정적 확인. 실제 Cloudflare 네트워크 장애 주입은 미실행입니다.
- 수정: 실패·timeout 시 script와 listener 및 shared promise를 정리하고, 재시도 때 새 script를 생성합니다. 이미 구현된 지도 `providers/sdk-loader.ts`의 제한시간·시도 정리 패턴을 공통으로 활용할 수 있습니다.
- 누락 테스트: script error 후 remount에서 새 script가 추가되는지, load 이벤트 미도착 시 명시적 오류가 되는지, 이전 시도의 늦은 load가 새 시도 상태를 덮지 않는지 확인해야 합니다.

### WSEC-06 · P2 · Google·Naver 지도는 선택한 이동 경로를 강조하지 않습니다

- 위치: `frontend/apps/web/src/features/map/providers/google.ts:223-225`, `providers/naver.ts:225-227`.
- 트리거: Google/Naver 제공자로 여행 지도에서 이동 구간을 선택합니다. `LiveMap`은 `selectedLineId`를 controller update의 네 번째 인자로 전달합니다(`live-map.tsx:73-76`).
- 영향: 두 adapter는 세 번째 인자까지만 받아 네 번째 인자를 버립니다. 선이 여러 개 겹칠 때 현재 상세 패널에 해당하는 경로를 구분할 선택 색/두께가 나타나지 않습니다. `model.ts:87-88,109`의 제공자 공통 계약을 OSM만 구현한 상태입니다.
- 확인 범위: 세 adapter의 update와 line styling 코드를 대조했습니다. 실제 상용 지도 SDK 실행은 미실행입니다.
- 수정: Google/Naver에도 선 ID→SDK layer 추적 및 선택 변경 시 스타일 갱신을 넣고 제공자별 공통 conformance 테스트를 둡니다.
- 누락 테스트: geometry가 같고 selectedLineId만 바뀔 때 선 스타일이 바뀌는 동일 테스트를 OSM/Google/Naver에 적용합니다.

## 구조 개선과 추가 검토 항목

| 영역 | 관찰 및 권장 조치 |
|---|---|
| 인증·상태 생명주기 | API 인증, 이벤트, query cache 정리, 동의/초안 cleanup이 client/SignOut/SocialDone/ConsentGate에 흩어졌습니다. `sessionGeneration`과 `onPrincipalChanged`를 공통 경계로 두고 세션 전환 하나에서 취소·초기화가 완결되게 하는 것이 WSEC-02~04의 공통 해결 방향입니다. |
| 비밀값의 메모리 수명 | AgentKeys의 `make` mutation은 키를 반환한 전체 응답을 TanStack mutation result로 보유합니다(`agent-keys.tsx:40-43`). `setCreated(null)`은 그 mutation result를 비우지 않습니다. `gcTime`, `reset`, unmount cleanup 및 민감 응답을 mutation cache에 남기지 않는 반환 형태를 검토해야 합니다. 저장소/로그 유출까지 확인한 것은 아닙니다. |
| SDK 로더 | 지도에는 timeout/실패 복구가 있고 Turnstile에는 없습니다. 외부 script 관리 생명주기를 공유하되 제공자 인증 callback 차이는 adapter로 남기는 것이 적절합니다. |
| 지도 중복 구현 | 좌표/마커 배치·선 색·내 위치·cleanup이 세 provider에 반복되며 선택선 기능부터 차이가 생겼습니다. 공통 상태 계산과 SDK 부수효과를 나누고 adapter 계약 테스트를 강화합니다. 지도 키 자체는 공개 웹 SDK key이므로 노출만으로 비밀 유출로 분류하지 않았습니다. 허용 origin/quotas는 운영 설정 확인 대상입니다. |
| 오류 처리 | `useLocationStays()`가 조회 실패를 빈 stays로 표현하고 `syncDiscordWebhook()`은 일부 실패를 삼킵니다. 모르는 상태와 실제 빈 상태를 구분하고 사용자 영향이 있을 때 마지막 성공 시각/재시도 상태를 노출할 필요가 있습니다. |
| 하드코딩·다국어 | 지도 공통 UI/공급자 오류/route label에 한국어가 직접 있고 Google loader는 `language: "ko"` 고정입니다. 공개 영어 UI의 지원 범위를 정한 뒤 label/SDK 언어를 동기화해야 합니다. 서울 기본 중심값·픽셀 간격·지오메트리 상수는 도메인/디자인 상수이므로 하드코딩이라는 이유만으로 결함 판정하지 않았습니다. |
| 입력 계약 | route-shapes parser의 `Number(null)`/`Number("")`는 0이 됩니다. 불완전 좌표/거리 데이터를 유효한 0으로 표현하지 않도록 wire schema를 명확히 해야 합니다. 정상 백엔드가 이 값을 보내는 사례는 이번에 재현하지 않았습니다. |
| 보안 헤더 | next.config와 저장소 Caddyfile에는 고객 웹 CSP/frame-ancestors가 없습니다. 배포 상위 프록시가 별도로 설정할 수 있어 운영 취약점으로 확정하지 않았습니다. 실제 응답 헤더를 점검하고 inline theme script·지도/Turnstile과 양립하는 정책을 검토해야 합니다. |
| 접근성 | 네이버 핀의 Enter/Space, OSM keyboard marker, 로그아웃 dialog 초기 초점/Tab trap, 약관 native dialog는 구현돼 있습니다. 화면읽기 프로그램·200% 확대·고대비·모션 감소·지도의 route line 대체 탐색은 실행 확인이 필요합니다. 코드에 aria 속성이 있다는 이유로 접근성 통과라고 판정하지 않았습니다. |
| 외부 URL | OAuth returnTo의 localPath는 이중 슬래시·역슬래시·제어문자 및 origin을 확인합니다. 서버 authorize_url은 http(s) 여부만 확인하므로 provider 허용 목록 강화는 방어 보완 대상으로 남깁니다. 서버 응답을 변조할 능력이 필요한 조건을 생략해 단독 open redirect 취약점으로 확정하지 않았습니다. |

## 재현 산출물과 남은 일

독립 probe는 저장소 루트 `evidence/2026-10-23_frontend-audit/web-security/security-boundaries.test.ts` 및 동 디렉터리 `vitest.config.ts`에 있습니다. 최초 실행은 web/audit 아래에서 3/3 재현했으며 이후 메인 lint/TypeScript 집계에 들어가지 않도록 정확한 원본·대상 경로가 격리 사본 하위임을 확인하고 안전 이동했습니다. 이동 후 01:28:43 KST 실행도 3/3 재현(exit 0, 4.46초)했으며 기록은 동 디렉터리 `result.txt`입니다. Vite의 미래 configLoader 기본값 관련 경고 1개는 현재 실행을 막지 않았습니다. 파일 삭제는 하지 않았고 빈 원 디렉터리는 남습니다.

`[2026-10-23 02:27 KST 위치 이동 — Claude]` probe를 기록 폴더 [web-security/](../evidence/2026-10-23_frontend-audit/web-security/)로 옮기고 상대 경로만 고쳤습니다. 이동 뒤 재실행도 3/3 재현, exit 0 — [재실행 기록](../evidence/2026-10-23_frontend-audit/web-security/result-after-move.txt). 위 문단은 이동 전 기록입니다.

재실행 명령(격리 사본 루트, 이동 뒤 경로):

```powershell
node final_project_cs/frontend/apps/web/node_modules/vitest/vitest.mjs run --config final_project_cs/wiki/records/evidence/2026-10-23_frontend-audit/web-security/vitest.config.ts
```

이번에는 근거가 확실한 결함 6개를 기록했습니다. 수정·회귀 검증·운영 반영은 모두 남아 있습니다. 특히 WSEC-01은 HTML 문자열→DOM sink를, WSEC-02~03은 실제 클라이언트 함수의 계정 교체 동작을 재현했으며 고객 데이터를 사용하지 않았습니다. 브라우저에서 실제 스크립트 실행, 두 탭의 실제 cookie 교체, 전체 지도 제공자·접근성 종단 확인은 후속 검증 범위입니다.
