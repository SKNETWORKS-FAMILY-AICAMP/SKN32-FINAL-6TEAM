---
type: report
title: role-eval-ui 프론트엔드 전체 코드 리뷰
status: reviewed
domain: travel
---

# role-eval-ui 프론트엔드 전체 코드 리뷰 — 2026-10-23

## 결론

현재 프론트엔드에서 **코드·호출 경로로 확인한 결함 19건(P1 4건, P2 15건)**을 정리했습니다. 그중 9개 경계는 독립 재현 probe로 확인했습니다. 장시간 네트워크 침묵은 짧은 대기 관찰과 타임아웃 부재를 함께 근거로 삼았으며, 실제 운영 사고 재현이라고 주장하지 않습니다. 추가로 관리자·개발 콘솔의 운영 의존성 3종이 보안 권고에 해당합니다. 의존성 버전 탐지와 실제 공격 가능성은 구분했습니다.

세 앱의 기존 **린트·타입 검사·단위 시험·프로덕션 빌드 12/12 = 100%**가 통과했습니다. 단위 시험은 **1,158/1,158 = 100%**입니다. 이 결과는 아래 경합·계정 교체·비정상 입력 문제가 없다는 뜻이 아닙니다. 관리자 린트는 사용하지 않는 import 경고 1건이 있습니다.

코드 수정·커밋·푸시·배포는 하지 않았습니다. 이 결과물은 리뷰와 재현 자료입니다. 다음 구현은 보안 경계와 실제 동작 오류를 먼저 고친 다음 모듈을 분리하는 순서가 적절합니다.

## 기준·격리·범위

- 기준: **로컬 `role-eval-ui`**, `a38808b39aa0ee27e73fa038c06941ca1661ae68`. 원격 추적 브랜치의 다른 커밋을 섞지 않았습니다.
- 별도 브랜치: **`review/frontend-audit-20261023`**.
- 작업 폴더: **`D:/FinalProject/Dev/fe-audit-20261023`**. `--no-hardlinks` 독립 복제이며 원본 `.git` 객체를 공유하지 않습니다.
- 원본: `D:/FinalProject/Dev/SKN32-FINAL-6TEAM`. 원본 코드·서버·포트·환경 파일에 쓰기 작업을 하지 않았습니다. 리뷰 앱 서버도 띄우지 않았습니다.
- 첫 복제 `D:/FinalProject/Dev/guguroute-frontend-review-20261023`은 긴 경로 checkout 실패 상태로 보존했습니다. 짧은 새 경로에서 `core.longpaths=true`로 정상 복제했습니다.
- 대상: `final_project_cs/frontend`의 고객 웹, 관리자 웹, 개발 콘솔 및 모바일 예약 폴더. 관련 backend API/권한/집계 구현은 계약 검증을 위해 읽었습니다. 별도 Python 개발 도구 `final_project_ui` 및 backend 전체는 이 프론트엔드 리뷰의 전수 대상이 아닙니다.
- 점검 축: 모듈·의존 방향, 보안·인증·개인정보, 오류·재시도·복구, 상태·비동기 경합, API 계약·입력, 하드코딩·데모 경계, 성능·요청 수, 접근성·다국어, 라우팅·SDK 생명주기, 시험 공백, 빌드·CI·의존성, 저장소 산출물.

| 앱 | 제품 TS/TSX/JS 파일 | 코드 줄 | 단위 시험 파일 | 브라우저 spec 파일 | 비고 |
|---|---:|---:|---:|---:|---|
| web | 281 | 31,490 | 123 | 141 | 단위 파일은 코드 줄 집계에서 제외 |
| admin | 25 | 2,337 | 3 | 18 | 실제 API와 데모 어댑터 모두 확인 |
| dev-console | 28 | 1,380 | 4 | 2 | 현재 명시적 샘플 실행 도구 |
| mobile | 0 | 0 | 0 | 0 | 사용자 결정으로 보류된 예약 폴더 |
| 합계 | 334 | 35,207 | 130 | 161 | 파일 수는 코드/분기 커버리지나 전수 실행률이 아님 |

[디스크 집계](../evidence/2026-10-23_frontend-audit/inventory.json). 실행 가능한 3개 앱 모두 검토했지만 모든 소스 줄·가능한 조합이 검증됐다는 의미의 완료율은 만들지 않았습니다.

## 우선순위별 결함

P1은 개인정보·계정 경계 또는 실제 운영 조작의 안전성 때문에 먼저 수정할 항목입니다. P2는 기능 오류·복구 실패·집계 불일치입니다. 상세 문서에는 각 항목의 트리거, 호출 경로, 영향, 수정 방향과 빠진 시험이 있습니다.

| ID | 우선순위 | 결함과 발생 조건 | 핵심 코드 위치 | 확인 근거 |
|---|---|---|---|---|
| WSEC-01 | P1 | 서버 장소명이 OSM 경로 툴팁의 HTML로 들어가 DOM XSS 경로가 됨 | `web/src/features/map/providers/osm.ts:208` | 실제 parser→title builder→설치된 Leaflet innerHTML 대입 probe. 브라우저 이벤트 실행은 미실행 |
| WSEC-02 | P1 | 다른 탭에서 A→B 로그인 후 A 화면의 계정 쓰기를 B의 CSRF로 자동 재전송 | `web/src/lib/live/client.ts:329` | 실제 api 함수에 두 세션을 대입해 동일 body 재전송 확인 |
| A02 | P1 | A 로그아웃 후 권한이 적은 B가 A의 Case 캐시를 서버 조회 없이 재사용 | `admin/src/components/AdminApp.tsx:151`, `operations/connected.tsx:25` | 실제 query-core 5.103.1에서 B 조회 0회·A 자료 반환 재현 |
| A01 | P1 | 실제 승인·위임 화면에 “모든 처리는 데모 상태에만” 안내가 남음 | `admin/src/features/workflows/screens.tsx:241` | live onCommand→실제 backend 승인/위임 호출 경로 대조 |
| WSEC-03 | P2 | 이전 요청의 늦은 401이 방금 로그인한 새 세션을 null로 만듦 | `web/src/lib/live/client.ts:301` | 실제 함수 probe |
| WSEC-04 | P2 | 로그아웃 후 같은 탭의 새 사용자가 이전 사용자의 미전송 계획 초안을 봄 | `web/src/features/account/session-card.tsx:70` | 로그아웃 cleanup·sessionStorage load/save 경로 대조 |
| WSEC-05 | P2 | Turnstile script 실패 뒤 화면에 재진입하면 끝난 script의 이벤트를 다시 기다림 | `web/src/features/human-check/human-check.tsx` | 실패 script 재사용 및 timeout/정리 부재 확인 |
| WSEC-06 | P2 | Google/Naver adapter가 selectedLineId를 버려 선택한 경로를 강조하지 않음 | `web/src/features/map/providers/google.ts:223`, `naver.ts:225` | 공통 controller 계약과 세 provider 비교 |
| W1 | P2 | Guardian 변경 실패가 SSE로 갱신된 최신 여행 전체를 이전 판으로 복원 | `web/src/features/guardian/trip-guardian.tsx:66` | 실제 callback에서 version 2→1 확인 |
| W2 | P2 | SSE의 CRLF가 청크 경계에서 나뉘면 완료 payload가 다른 이벤트로 분리 | `web/src/lib/live/events.ts:50` | 실제 parser 출력이 빈 result + message로 바뀜 |
| W3 | P2 | 여행 SSE가 ready 뒤 침묵하면 재접속·polling이 멈춘 상태로 남음 | `web/src/lib/live/events.ts:91` | reader 대기 probe + 헤더/heartbeat 제한 부재 |
| W4 | P2 | 접수 SSE의 응답 헤더 대기가 끝나지 않으면 polling 복구로 넘어가지 못함 | `web/src/lib/live/stream.ts:218` | watchdog 5ms에도 헤더 대기 35ms 뒤 미완료 |
| W5 | P2 | 대안 사진 첫/최종 목록이 같은 장소를 중복 조회해 검색 한도를 소비 | `web/src/features/plan-check/use-server-review.ts:296` | 후보 3개 첫 열기 6회, 두 번 열기 총12회 사진 HTTP 호출 |
| A03 | P2 | 운영자 세션 만료 후 캐시가 authenticated를 유지해 화면 내 재로그인 복구가 막힘 | `admin/src/components/AdminApp.tsx:145` | 401 처리·로그아웃 성공 후에만 refetch하는 경로 대조 |
| A04 | P2 | 관리자 snapshot이 무한 신선도로 남아 외부 문의·변경·날짜 경계가 갱신되지 않음 | `admin/src/components/AdminApp.tsx:50` | 상시 마운트 쿼리/무기한 staleTime/포커스 갱신 꺼짐 |
| A05 | P2 | 실제 문의의 “내 담당” 및 답변 후 담당 값으로 demo.operator 사용 | `admin/src/features/workflows/screens.tsx:76` | 실제 actor 응답과 후속 상태 저장 assignee 대조 |
| A06 | P2 | 감사 “전체”·기간 검색이 최신500건 안에서만 되어 과거 기록을 없다고 표시 | `admin/src/features/workflows/screens.tsx:229` | backend LIMIT 500 + 프론트 배열 필터 |
| A07 | P2 | 사용자501명 이후 전체 사용량·한도 영향 집계가 최근500명만 계산 | `admin/src/features/overview/screens.tsx:114` | snapshot 사용자 제한과 전체처럼 표시하는 집계 비교 |
| A08 | P2 | web 사용량에 포함된 chat를 다시 더해 호출 합계를 이중 계산 | `admin/src/features/overview/screens.tsx:114` | backend web=sum(counts), UI=chat+web 대조 |

상세: [인증·보안·공통 UI 6건](2026-10-23_frontend-audit-web-security-ui.md) · [상태·비동기 5건](2026-10-23_frontend-audit-web-state.md) · [관리자·개발 콘솔 8건](2026-10-23_frontend-audit-admin-console.md).

## 운영 의존성 검사 — 코드 결함 19건과 별도

각 앱에서 `npm audit --omit=dev --package-lock-only --json`을 실행했습니다. 실제 잠금 파일 기준이며 자동 업그레이드는 하지 않았습니다.

| 앱 | Next / sharp / source-map-js | 운영 의존성 권고 대상 패키지 수 |
|---|---|---|
| web | 16.4.0 / 0.35.5 / 1.2.2 | 0 |
| admin | 16.3.5 / 0.35.4 / 1.2.1 | 3: critical 1, high 2 |
| dev-console | 16.3.5 / 0.35.4 / 1.2.1 | 3: critical 1, high 2 |

admin과 dev-console의 3종은 같은 패키지 묶음입니다. 서로 다른 취약점 6종으로 합산하지 않았습니다. audit의 critical은 패키지 권고의 최대 심각도이며 현재 앱의 실증 공격 위험도와 동일하지 않습니다.

- Next ImageResponse RCE 권고는 공격자가 제어하는 SVG를 Node `next/og`로 렌더링해야 합니다. 두 앱에서 해당 사용을 찾지 못했으므로 RCE가 재현됐다고 판단하지 않습니다. [공급자 보안 권고](https://github.com/vercel/next.js/security/advisories/GHSA-vcvr-r3jv-pc5j).
- Image Optimization SSRF 권고는 `images.remotePatterns` 조건이 필요합니다. 두 앱의 현재 next.config에는 이 설정이 없어 이 특정 경로는 해당하지 않습니다. 다른 Next 캐시·개발서버 권고의 배포 조건은 별도 확인 대상입니다. [공급자 보안 권고](https://github.com/vercel/next.js/security/advisories/GHSA-cjq9-62q9-8jv4).
- sharp 권고는 librsvg 및 런타임 조건의 영향을 받습니다. Windows 로컬 빌드 통과로 Linux 배포 영향을 결론내리지 않습니다. 패치 버전은 0.35.5입니다. [공급자 보안 권고](https://github.com/lovell/sharp/security/advisories/GHSA-wq5f-xc86-pv6w).
- source-map-js의 비정상 indexed source map 오프셋 처리 문제는 1.2.2에서 수정됐습니다. 두 앱에서 공격자 source map을 받는 경로를 확인하지 못했습니다. [유지관리자 수정 PR](https://github.com/7rulnik/source-map-js/pull/79).

보안 패치가 반영된 의존성으로 정렬하고 잠금 파일을 다시 생성한 뒤 세 앱 check와 필요한 브라우저 시험을 실행하는 작업을 권장합니다. web의 0건 결과도 미공개 취약점·앱 자체 결함이 없다는 보증이 아닙니다. devDependencies는 이번 audit에서 제외했습니다.

원본 결과: [web](../evidence/2026-10-23_frontend-audit/web-dependency-audit.json) · [admin](../evidence/2026-10-23_frontend-audit/admin-dependency-audit.json) · [dev-console](../evidence/2026-10-23_frontend-audit/dev-console-dependency-audit.json).

## 모듈 분리·공통화 제안

| 현재 결합 지점 | 분리할 책임 | 유지할 불변식/시험 |
|---|---|---|
| plan-check.tsx 2,108줄 | 화면 상태 reducer, 질문 진행, 편집 명령 순서, 제스처/시간 편집, 표시 패널 | 사용자 편집과 서버 revision/선택을 한 방향으로 반영; 늦은 응답이 새 판을 덮지 않음 |
| use-server-review.ts 527줄 | intake 저장·undo, 후보 스트림·검색, 사진 조회 캐시 | 같은 ref의 in-flight 요청 공유; revision/언어 전환·해제 시 결과 폐기 |
| trip-screen.tsx 871줄 | 여행 view model, 일정/채팅/알림, 시트·지도 인터랙션 | 제스처 변경과 도메인 mutation이 서로 상태를 덮지 않음 |
| client·SignOut·SocialDone·ConsentGate | 인증 주체/세대와 취소·캐시·초안 cleanup을 한 생명주기로 통합 | 계정이 바뀐 쓰기 재전송 금지, 이전 계정 응답/저장소 유입 금지 |
| events.ts·stream.ts·follow hooks | SSE parser, transport timeout/heartbeat, reconnect 정책 | 읽기 재접속과 쓰기 재실행 구분; 모든 청크 경계 보존 |
| AdminApp·overview/workflows 화면 묶음 | 인증, 라우팅, 사용자/문의/공지/감사 query와 mutation, 서버 집계 | live/de​​mo 경계·권한별 캐시·최신성·전체 집계 범위 명시 |
| 지도 provider 3종 | 공통 선택·색·좌표 상태 계산과 SDK 부수효과 adapter | 같은 계약 시험을 세 제공자에 실행; selectedLineId 포함 |

파일 줄 수만으로 분리하지 않습니다. 특히 약관 콘텐츠 1,162줄은 콘텐츠 파일이므로 거대 상태 컴포넌트와 같은 기준으로 보지 않았습니다. 서울·7일·4인 제한과 공개 지도 SDK 키도 현재 계약/공개 설정이라는 이유를 확인한 뒤 단순 하드코딩 결함에서 제외했습니다.

## 추가로 점검한 품질 항목

- **CI 공백:** 현재 workflow는 web/admin을 대상으로 하며 dev-console check 연결이 없습니다. 개발 콘솔 변경에도 최소 check를 연결하되 저장소 결정대로 role 브랜치에 새 자동 CI를 붙이지 않고 develop/main 정책 안에서 설계해야 합니다.
- **지도 회귀 공백:** web CI는 기본 OSM으로만 test:live를 실행합니다. `maps.spec.ts`는 MAP_TEST_PROVIDER가 google/naver일 때만 실행하므로 현 matrix의 shard4개가 세 제공자를 검증하는 것은 아닙니다. provider별 별도 빌드·계약 시험을 추가할 후보입니다.
- **테스트 구성:** 130개 단위 파일과 브라우저 spec161개가 있어 시험이 전반적으로 없다고 판단하지 않습니다. 실제 React 대신 슬롯을 흉내 낸 hook 시험의 빈틈은 실제 React+QueryClient 통합 시험으로 보완합니다. 계정교체/늦은401/응답역전/중간 끊김/SDK오류/501번째 레코드가 우선입니다.
- **API 경계:** generic `as T`만으로 받는 live 응답에 최소 wire schema를 두고, malformed JSON·401·403·409·429·timeout을 다른 상태로 표현합니다. 백엔드 집계와 분모를 프론트에서 다시 추정하지 않습니다.
- **성능:** 사진 중복 호출은 실측 결함입니다. 관리자 전체 snapshot에 원문/감사/목록이 함께 실리는 구조, 샘플 콘솔 sessionStorage 누적은 확장성 개선 대상입니다. 번들 크기·Core Web Vitals·실제 모바일 성능은 측정하지 않았습니다. 배경 이미지는 이미 Next Image/getImageProps를 사용하므로 원본 파일 크기를 전송량으로 오인하지 않았습니다.
- **접근성:** 기존 native dialog·초점 복귀·키보드 핀 지원은 확인했습니다. admin `UnlimitedModeSwitch`의 div alertdialog 초점 처리, 지도 경로의 키보드 대체 탐색, 200% 확대·화면읽기·고대비는 후속 실제 화면 검사 대상으로 남겼습니다. WCAG 전체 통과 판정을 하지 않았습니다.
- **오류·관측:** 동의한 위치의 stays 조회 실패를 빈 목록으로 표현하는 곳, 일부 webhook 동기화 실패의 무음 처리가 있습니다. 로딩/없음/실패/오래된 성공값을 구분하고 마지막 성공 시각·사용자 재시도·민감정보 없는 오류 코드를 붙일 필요가 있습니다.
- **국제화·시간:** Google SDK의 한국어 고정과 일부 지도 문구를 영어 UI 범위와 대조해야 합니다. 서울 기준 날짜와 브라우저 로컬 날짜의 자정 경계 테스트가 필요합니다. 이번 실행 TZ는 Asia/Seoul입니다.
- **운영 보안 설정:** 프록시 허용 목록·쿠키 허용 목록·CSRF 전달은 이미 있습니다. 실응답 CSP/보안 헤더, 쿠키 Secure, 공개 지도 키의 허용 origin·quota는 운영 설정을 읽지 않아 미확인입니다.
- **저장소 산출물:** frontend 추적 파일1,629개 중 mockups844개/123,960,222바이트, 임시 브라우저 프로필127개/6,829,217바이트가 포함돼 있습니다. 실제 긴 경로 checkout 실패도 발생했습니다. 향후 캡처 프로필을 Git에 추가하지 않도록 제외 규칙을 마련하고 기존 자료는 보존 위치·정책을 정한 후 처리해야 합니다. 이번에 삭제/추적 해제하지 않았고 비밀값 유출도 확인하지 않았습니다. [집계](../evidence/2026-10-23_frontend-audit/tracked-assets.json).

## 실행 검증과 한계

| 앱 | lint | typecheck | unit | build |
|---|---|---|---|---|
| web | 통과 | 통과 | 1,064/1,064 = 100% | 통과 |
| admin | 통과, 경고1 | 통과 | 39/39 = 100% | 통과 |
| dev-console | 통과 | 통과 | 55/55 = 100% | 통과 |

환경: Windows, Node22.23.1, npm10.9.8, 앱별 package-lock 기준 `npm ci --ignore-scripts --no-audit --no-fund`, `TZ=Asia/Seoul`. 처음 오프라인 설치는 cache miss, 불완전 설치에 대한 npm install은 내부 edgesOut 오류로 실패했습니다. 해당 폴더는 격리 사본의 `.review-install-incomplete`에 보존했고 새 npm ci는 세 앱 모두 성공했습니다. 설치 실패를 소스 결함으로 세지 않았습니다.

앱별 `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`를 각각 실행해 실패가 뒤 단계 실행을 가리지 않게 했습니다. `.env.local`·실서버 비밀값을 복사하지 않았으므로 빌드 통과는 실제 API/지도 설정의 운영 검증을 뜻하지 않습니다. 브라우저 E2E161개 spec 및 실서버 시험은 실행하지 않았습니다. 병합·구현 작업이 아니므로 전체 backend 통합 관문도 실행하지 않았습니다.

- [web 검사 exit 기록](../evidence/2026-10-23_frontend-audit/web-checks.json) · [unit 로그](../evidence/2026-10-23_frontend-audit/web-test.log)
- [admin 검사 exit 기록](../evidence/2026-10-23_frontend-audit/admin-checks.json) · [unit 로그](../evidence/2026-10-23_frontend-audit/admin-test.log)
- [dev-console 검사 exit 기록](../evidence/2026-10-23_frontend-audit/dev-console-checks.json) · [unit 로그](../evidence/2026-10-23_frontend-audit/dev-console-test.log)
- [상태 probe5개 결과](../evidence/2026-10-23_frontend-audit/web-state/web-state-probe-result.json)
- [보안 probe3개 결과](../evidence/2026-10-23_frontend-audit/web-security/result.txt)
- [관리자 캐시 probe1개 결과](../evidence/2026-10-23_frontend-audit/admin-cache-probe.json)

probe의 통과는 **결함이 존재한다는 assertion이 충족됐다는 의미**입니다. 결함 수정 후에는 반대 기대값으로 회귀 시험을 만들어야 합니다.

## 권장 구현 순서

1. WSEC-01/02와 A01/02: HTML sink, 계정별 쓰기·캐시 경계, 실제 명령 안내를 먼저 고칩니다. 각 항목의 재현을 안전한 기대값으로 바꿔 회귀 시험에 넣습니다.
2. WSEC-03/04, W1~W4, A03/04: 세션/응답 세대, 민감 초안 정리, 부분 rollback, SSE 타임아웃·복구를 통합합니다.
3. W5, A05~A08, WSEC-05/06: 중복 요청, 실제 담당자/집계 계약, SDK 복구·지도 제공자 동작 차이를 고칩니다. 의존성 패치도 이와 별도 변경으로 검증합니다.
4. 그 뒤 상태 소유권과 API 계약이 고정된 단위부터 컴포넌트·훅을 분리하고 CI/접근성/성능 검증을 확장합니다.

수정 완료 0/19 = 0%입니다. 이번 요청의 리뷰 산출물은 완료됐고 결함 구현·운영 반영은 별개로 남아 있습니다.
