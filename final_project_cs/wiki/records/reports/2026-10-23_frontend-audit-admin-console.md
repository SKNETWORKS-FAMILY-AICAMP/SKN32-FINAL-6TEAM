# 운영자 앱·개발 콘솔 프론트엔드 코드 리뷰

확인 시각: 2026-10-23 01:22 KST, 캐시 재현 보강 01:27 KST. 대상: `review/frontend-audit-20261023` 격리 사본의 `frontend/apps/admin`, `frontend/apps/dev-console`. 원본·서버·제품 코드는 변경하지 않았습니다. 이 기록은 정적 코드·호출 경로·현재 API 계약 대조와 아래 query-core 캐시 재현 결과입니다. 브라우저·DB·실서버 및 앱 테스트 묶음은 이 하위 검토에서 실행하지 않았습니다.

`admin/src` TS/TSX 파일 28개, `dev-console/src` 32개를 파일 목록으로 식별했습니다(테스트 포함). 파일 수를 전수 동작 검증률로 해석하지 않습니다. 검토 관점: 인증·권한/프록시, 오류 복구, 캐시·상태, API 계약·집계, 데모 분리·하드코딩, 모듈 구조, 접근성·시험 공백.

| 항목 | 진행 | 의미 |
|---|---:|---|
| 앱 진입점·게이트웨이 경로 대조 | 2/2 = 100% | 두 앱의 실제/데모 데이터 경계 확인 |
| 검토 관점별 코드 점검 | 7/7 = 100% | 아래 확정 결함과 개선 제안으로 정리; 화면 실행 보장은 아님 |
| 확정 결함의 코드·호출부 근거 정리 | 8/8 = 100% | 정적 확인; A02는 query-core 최소 재현도 수행 |
| 캐시 계정 경계 최소 재현 | 1/1 = 100% | 설치된 query-core 5.103.1, 서버 없이 합성 데이터 사용 |
| 이 하위 검토의 서버·브라우저 실행 | 0건 | 다른 세션의 서버 사용 유지; 주 검토에서 별도 시험 결과 취합 |

## 우선 고칠 결함

### A01 · P1 · 실제 승인·위임 화면이 모든 처리를 데모라고 안내합니다

- 위치: `frontend/apps/admin/src/features/workflows/screens.tsx:241` (`OpsScreen`), 연결 `components/AdminApp.tsx:122`, `lib/gateway.ts:230-239`.
- 트리거: 실제 로그인 후 `/ops`에서 예약 승인, 위임 부여/회수 또는 발송 확인을 수행합니다.
- 근거: 모드 조건 없이 「모든 처리는 데모 상태에만 반영됩니다」가 출력됩니다. 반면 live Console은 이 화면에 live `onCommand`를 주고, 명령은 `/admin/api/commands`로 전송됩니다. 서버 `app/presentation/admin_api.py:298-323`은 기존 승인·위임·발송 API를 실제로 호출합니다.
- 영향: 운영자가 시험 조작으로 이해하고 실제 고객 승인/위임 상태를 변경할 수 있습니다. 전체 앱 상단의 실제 자료 배너와 화면 내부의 보증이 충돌합니다.
- 방향: 실제/데모 모드별 경고·확인 문구를 분리하고 실제 명령은 실제 영향과 대상을 확인하게 합니다. 실제 모드 `/ops`에서 데모 전용 문구가 없고 명령 종류별 영향을 표시하는 회귀 시험이 필요합니다.

### A02 · P1 · 운영자 교체 후 권한 있는 사용자의 조회 캐시가 남습니다

- 위치: `frontend/apps/admin/src/components/AdminApp.tsx:151` (로그아웃), `:50` (캐시 정책), `features/operations/connected.tsx:25` (Case 조회 키).
- 트리거: `case:read` 권한을 가진 A가 Case를 읽고 로그아웃한 뒤, 같은 탭에서 `ops:introspect`는 있지만 `case:read`가 없는 B가 로그인하여 같은 Case 화면을 엽니다(캐시가 GC되기 전).
- 근거: QueryClient는 로그인 교체에도 유지됩니다. 로그아웃은 `['admin']` 접두만 제거하지만 Case는 `['operation-cases', id]`에 저장됩니다. 운영자 식별자도 키에 없고 기본 `staleTime: Infinity`이므로 B의 새 GET 권한 검증 없이 A의 캐시를 재사용할 수 있습니다. 설정·진단 조회에도 같은 키 구조가 있습니다. 서버는 Case에 별도 `case:read` 권한을 요구합니다(`app/presentation/admin_api.py:229-231,266-271`).
- 영향: 서버 권한 검사는 그대로여도 동일 브라우저의 계정 교체 경계에서 Case 상태·사건 근거가 노출됩니다.
- 실행 근거(01:27 KST): [재현 코드](../evidence/2026-10-23_frontend-audit/admin-cache-probe.mjs), [실행 JSON](../evidence/2026-10-23_frontend-audit/admin-cache-probe.json). 앱의 원문 설정을 확인한 뒤 설치된 `@tanstack/query-core 5.103.1`로 QueryClient와 QueryObserver를 실행했습니다. logout 뒤 admin 캐시는 제거됐지만 Case 캐시는 유지됐고, B의 queryFn 호출은 **0회**, B의 observer는 `success / isStale=false / fetchStatus=idle`로 A의 합성 Case evidence를 반환했습니다. React·브라우저·서버 자체 재현은 아니며 실제 고객 자료는 사용하지 않았습니다.
- 방향: 로그아웃·세션 교체 때 민감 조회를 취소하고 전부 제거하거나 세션별 QueryClient를 교체합니다. 로그인 계정/권한 판을 캐시 키 경계에 포함합니다. A→B 권한 축소 회귀 시험에서 예전 Case가 잠깐도 표시되지 않는지 확인해야 합니다.

### A03 · P2 · 세션이 만료되면 재로그인으로 돌아갈 수 없습니다

- 위치: `frontend/apps/admin/src/components/AdminApp.tsx:145-152`, `lib/gateway.ts:168-175,226-228`.
- 트리거: 화면을 연 채 운영 세션 쿠키가 만료되거나 다른 탭에서 로그아웃한 뒤 읽기/변경 요청 또는 로그아웃을 누릅니다.
- 근거: `operator-session`은 기본 무한 신선도·포커스 재조회 꺼짐을 상속합니다. `liveRequest`는 401을 일반 Error로 던질 뿐 세션 쿼리를 무효화하지 않습니다. 로그아웃도 `operatorLogout()` 성공 후에만 `session.refetch()`를 실행하는데 서버 `/logout`은 유효한 세션을 요구하여 이미 만료됐으면 401입니다. UI의 `void onLogout()`에는 catch가 없습니다.
- 영향: 캐시의 `authenticated: true` 때문에 로그인 폼이 나오지 않고 실패 화면/오래된 화면에 남습니다. 새로고침 전에는 화면 내 복구 경로가 막힙니다.
- 방향: HTTP 오류에 상태·코드를 보존하고 401에 공통 세션 만료 처리를 적용합니다. 로그아웃의 이미 만료된 세션도 로컬 상태를 폐기하게 합니다. 만료→조회/변경→로그아웃 각각에서 재로그인 가능 여부를 시험해야 합니다.

### A04 · P2 · 문의·승인·사용량 스냅샷이 페이지를 떠나기 전까지 갱신되지 않습니다

- 위치: `frontend/apps/admin/src/components/AdminApp.tsx:50,66,84-89`.
- 트리거: 로그인 후 고객이 새 문의를 보내거나 다른 운영자가 상태/한도를 변경합니다. 현재 운영자가 메뉴를 오가거나 창에 다시 포커스합니다.
- 근거: 루트 `['admin']` 쿼리는 항상 마운트되어 있고 `staleTime: Infinity`, `refetchOnWindowFocus: false`입니다. 주기 재조회가 없으며 자신이 `onCommand`로 저장할 때에만 refetch합니다. 문의함·홈·감사 화면에는 해당 snapshot의 명시적 새로 읽기도 없습니다.
- 영향: 새 문의와 승인 대기가 보이지 않고, 날짜가 바뀌어도 전날 집계 시계·공지 상태·오늘 한도를 계속 표시합니다. 운영자 본인의 추가 저장 또는 전체 페이지 새로고침이 있어야 갱신됩니다.
- 방향: demo와 live의 캐시 정책을 분리하고 live snapshot에 적절한 갱신/수동 새로 읽기/갱신 시각을 제공합니다. 클라이언트의 미저장 편집은 서버 상태 갱신과 분리합니다. 외부 문의 추가 후 snapshot만 변경되는 회귀 시험이 필요합니다.

### A05 · P2 · 실제 문의 담당자로 demo.operator를 저장할 수 있습니다

- 위치: `frontend/apps/admin/src/features/workflows/screens.tsx:76,87,113`.
- 트리거: 실제 운영자가 문의에 답변하고 이어서 상태 변경을 저장하거나 「내 담당」 필터를 선택합니다.
- 근거: 담당 후보와 「내 담당」 값이 `DEMO_OPERATOR`이며 답변 성공 후 `setAssignee(DEMO_OPERATOR)`를 수행합니다. 실제 서버는 답변의 assignee를 로그인 actor로 설정하지만(`app/application/admin_service.py:234`), 다음 `inquiry-status`에서는 브라우저가 전송한 assignee를 그대로 저장합니다(`:237`). `ScreenProps`에는 현재 운영자 id가 없습니다.
- 영향: 「내 담당」이 실제 본인 문의를 놓치고, 후속 상태 저장이 실제 담당을 가상 계정으로 덮어쓸 수 있습니다.
- 방향: 인증된 운영자를 ScreenProps/컨텍스트로 넘기고 데모 상수는 데모 게이트웨이 안에 둡니다. 서버 응답의 담당자를 반영하고 후보 계정은 검증된 목록을 사용합니다. `real-operator`로 답변→상태 저장→내 담당 조회를 묶은 시험이 필요합니다.

### A06 · P2 · 운영 기록 「전체」/기간 검색이 최신 500건 안에서만 수행됩니다

- 위치: `frontend/apps/admin/src/features/workflows/screens.tsx:229-230`; 서버 `app/domains/travel_ops/modules/web_account/admin_snapshot.py:51`.
- 트리거: 감사 기록이 500건을 초과한 상태에서 과거 운영자/고객/기간을 찾습니다.
- 근거: 서버는 `ORDER BY seq DESC LIMIT 500`을 반환하고, 프론트는 받은 배열을 필터할 뿐 후속 조회·커서가 없습니다. UI는 「전체」「30일」로 표시하며 잘린 범위 경고도 없습니다.
- 영향: DB에 존재하는 변경을 「선택한 조건의 운영 기록이 없습니다」라고 표시합니다. 감사 추적과 장애 원인 확인을 놓칩니다.
- 방향: 감사 전용 서버 필터/페이지 API를 만들거나 적어도 최근 500건만 조회함을 명시하고 이전 기록으로 이어가는 수단을 제공합니다. 501번째 기록에 대한 검색 시험을 추가해야 합니다.

### A07 · P2 · 사용자 500명 이후 홈·한도 변경 영향 수치가 누락됩니다

- 위치: `frontend/apps/admin/src/features/overview/screens.tsx:79,102,114,195,270`; 서버 `app/domains/travel_ops/modules/web_account/admin_snapshot.py:28`.
- 트리거: 고객이 501명 이상이고 오래전에 가입한 고객에게 사용량/한도 도달 상태가 있습니다.
- 근거: snapshot users는 가입 최신 500명만 반환합니다. 홈 「한도에 걸린 사용자」, 「우리 서버 호출」, 한도 저장 전 영향 미리보기는 그 배열만 셉니다. 별도 사용자 목록 API가 전체 고객을 페이지 조회하도록 개선되어 있지만 이 집계에는 쓰이지 않습니다.
- 영향: 전체 운영 수치와 한도 변경 영향이 작게 표시되어 목록 화면의 전체 결과와 충돌합니다.
- 방향: 전체 고객 대상 집계를 서버에서 별도로 반환합니다. 상세 목록 페이지 크기와 집계 분모를 분리합니다. 누락된 501번째 사용자가 유일한 한도 도달자일 때 홈 1명/영향 1명인 시험이 필요합니다.

### A08 · P2 · 홈의 서버 호출 합계가 채팅 횟수를 두 번 셉니다

- 위치: `frontend/apps/admin/src/features/overview/screens.tsx:114`; 서버 `app/domains/travel_ops/modules/web_account/admin_snapshot.py:35`.
- 트리거: 실제 고객에게 `message` 사용량이 1건 이상 있습니다.
- 근거: 서버는 `chat=counts.get('message',0)`, `web=sum(counts.values())`로 채팅을 이미 web에 포함합니다. 홈은 `user.chat + user.web`으로 합산합니다. 데모 fixture는 chat/web을 서로 다른 수처럼 구성해 이 계약 차이를 숨깁니다.
- 영향: message 3건, 다른 웹 작업 7건이라면 저장된 웹 작업 총합 10을 홈에서는 13으로 표시합니다. 또한 이 값은 HTTP 전체 계측이 아닌 web_usage 작업 집계이므로 측정 대상 표기도 맞춰야 합니다.
- 방향: 응답 계약에서 web을 전체/비채팅 중 하나로 명시하고 합계와 레이블을 일치시킵니다. 실제 backend 응답 형상의 fixture로 집계 시험을 추가해야 합니다.

## 구조·검증 개선 제안

아래 항목은 추가 확정 장애로 세지 않았습니다.

- `AdminApp`가 수동 주소 라우팅, 로그인, 전역 snapshot, 안내/메뉴를 모두 담당하고 `overview/screens.tsx`, `workflows/screens.tsx`가 여러 화면·폼을 묶습니다. 먼저 인증 상태/캐시 수명, 앱 라우팅, 사용자·문의·공지·감사 게이트웨이를 나누면 위 결함을 독립적으로 시험할 수 있습니다. 단순 줄 수 때문에 무조건 분할하자는 뜻은 아닙니다.
- admin `liveRequest<T>`의 `as T`와 각 화면의 로컬 응답 타입은 런타임 계약 검증을 제공하지 않습니다. 핵심 응답의 Zod/OpenAPI 스키마 및 상태코드가 있는 오류 객체를 경계에서 처리하면 malformed JSON·401·403·409·timeout을 화면별로 일관되게 다룰 수 있습니다.
- admin의 전역 snapshot은 홈에 들어갈 때 문의 원문/답변/감사 전후 값 등 다른 화면 자료까지 읽습니다. 건수가 늘면 네트워크·메모리·렌더링 비용이 함께 증가합니다. 목록/상세/집계 분리와 서버 페이지 처리가 적절합니다. 정확한 응답 크기·실사용 성능은 측정하지 않았습니다.
- 권한 scopes를 화면에서 활용하지 않습니다. 서버는 권한을 검증하지만 권한 없는 메뉴/저장 버튼이 항상 나타나고 일부 화면은 불필요하게 snapshot의 ops:introspect 성공에 종속됩니다. 사용 가능한 기능을 권한별로 표현하고 직접 URL에서 403도 구별해 안내하는 편이 좋습니다.
- `UnlimitedModeSwitch`의 `role="alertdialog"`는 네이티브 dialog가 아닌 div이며 열린 뒤 초점 이동·복귀가 없습니다. QA 삭제 화면은 네이티브 dialog/초점 복귀를 구현하고 있습니다. 공통 dialog 및 키보드/스크린리더 검증을 적용할 후보입니다. 실제 보조기기 확인 전 접근성 통과/실패 전체 판정은 하지 않았습니다.
- 운영 폼·게이트웨이의 사유/내용 제한, 한국 시각 표시 유틸리티, 오류·성공 피드백이 중복됩니다. 값/시간대/검증을 공통 계약에서 읽도록 정리하고 계약에 확정된 제한과 데모 전용 수치를 구분해야 합니다.
- `dev-console`은 계약상 명시적인 샘플 어댑터이며 unconfigured 때 실패를 보여줍니다. 실제 API 미연결이나 고정 샘플 장소/시간을 현행 결함으로 과장하지 않았습니다. 실 API를 붙일 때 인증·생성 요청 멱등성·실행 이벤트 순서·취소/timeout·샘플 기록과 실측 기록의 저장 분리가 출시 조건입니다.
- dev-console의 sessionStorage 실행/비교 기록은 모두 한 JSON에 계속 누적되고 읽을 때 전체 Zod 검증을 합니다. 크기 제한/보관 정책/내보내기 또는 복구 기능이 없으므로 장기 반복 사용 비용을 측정한 뒤 개선할 수 있습니다. 현재 저장 실패는 명시적 오류로 처리하여 무음 손실이라고 보지는 않았습니다.

## 시험에서 확인한 공백과 남은 확인

`tests/live/admin.spec.ts`의 실제 모드 시험도 `createDemoSnapshot()`을 기반으로 하며 정상 로그인·로그아웃만 확인합니다. 위의 권한 축소 로그인, 세션 만료, 외부 갱신, 실제 담당자 반영, 500건 경계, 실제 집계 응답 계약은 이 검토에서 읽은 해당 시험에 없습니다. `live`라는 디렉터리 이름만으로 실서버 시험이라고 판단하지 않았습니다(Playwright `page.route` mock 사용).

프록시는 경로 허용 목록, loopback 원본 제한, 쿠키 허용 목록, CSRF 전달, GET 전용 여행 조회, 15초 timeout을 갖추고 있습니다. 확인한 코드만으로 SSRF·CSRF 우회가 있다고 보고하지 않았습니다. 외부 의존성 취약점 데이터베이스 조회·공개망 배포 설정·보안 헤더·쿠키 Secure 동작은 이번 정적 검토 범위에서 검증하지 않았습니다.

실행한 명령은 파일 목록 `rg --files`, 호출부/시험 문자열 `rg -n`, PowerShell `Get-Content` 읽기, 본 보고서 추가와 `node final_project_cs/wiki/records/evidence/2026-10-23_frontend-audit/admin-cache-probe.mjs`입니다. 최소 재현 1건이 성공 종료했습니다. 앱 테스트 실행 결과는 주 검토 보고서에 합칩니다. 제품 코드 수정·커밋·푸시·배포는 0건입니다. 최초 보고서에 캐시 근거를 추가하기 전 사본은 [admin-report-before-cache-probe.md](../evidence/2026-10-23_frontend-audit/admin-report-before-cache-probe.md)에 보존했습니다.
