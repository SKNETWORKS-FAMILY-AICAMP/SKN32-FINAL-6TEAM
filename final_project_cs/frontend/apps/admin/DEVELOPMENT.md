# 운영자 콘솔 개발 기준

작성: 2026-09-29 · CI 확인: 2026-09-30 · Codex · 구현 기준 `1317a74` + CI 추가 · TeamFlow `ST4F-176`.

이번 구현은 [SCREEN_PLAN.md](SCREEN_PLAN.md) §5의 화면 단계다. 운영 API·인증 연결 완료를 의미하지 않는다. [실행 안내](README.md)에서 설정과 검증 명령을 확인한다.

## 구조

| 위치 | 책임 |
|---|---|
| `src/app` | Next.js App Router 진입, 한국어 문서, 기본 스타일 |
| `src/components/AdminApp.tsx` | 메뉴·로그인 데모·화면 상태·시연 가이드·초기화·조회 캐시 |
| `src/features/overview` | 홈·사용자·한도·사용량·서버 상태 |
| `src/features/workflows` | 문의·공지/점검·운영 기록·임시 운영 |
| `src/lib/model.ts` | 프론트 데이터 및 명령 타입. 확정 HTTP 계약이 아님 |
| `src/lib/gateway.ts` | `AdminGateway`, 명령 입력 검증·메모리 상태·운영 기록 |
| `src/lib/demo/fixtures.ts` | 이름 붙인 가상 데이터·시연 시각·운영자 |
| `src/standalone.tsx` | 같은 React 앱을 단일 HTML에 넣는 진입점 |
| `scripts/export-html.mjs` | CSS·JS를 HTML 한 파일에 포함, 외부 요청 차단 |
| `tests/e2e` | 실행 앱과 오프라인 HTML 브라우저 검증 |
| `tests/unconfigured` | 별도 빌드에서 미설정 모드 검증 |

스택은 기존 개발자 콘솔과 동일한 Next.js 16.3.5·React 19.3.0·TypeScript 5.9.3 strict·TanStack Query·Zod·lucide-react이며, CSS Modules를 사용한다. HTML 번들은 esbuild 0.28.2를 사용한다. 기존 콘솔의 패키지 잠금 버전을 기준으로 의존성을 해결했으며 기존 화면 코드는 이식하지 않았다.

## 지켜야 할 경계

화면은 `ScreenProps.data`로 조회하고 `onCommand`로 변경한다. 실제 HTTP 요청은 없다. 나중에 실제 어댑터를 추가할 때도 UI에서 백엔드 비밀 키를 받지 않는다. 로그인 데모는 인증이 아니며 실제 ID·비밀번호를 수집하지 않는다.

명령은 Zod 검증 후 상태 사본에 적용하고 기록과 함께 반영한다. 실패하면 업무 상태와 운영 기록 모두 바뀌지 않는다. 조회 결과 역시 사본이다. 수정은 메모리에만 유지되며 새로고침·데모 초기화로 사라진다. 날짜는 KST로 해석하고, 가상 운영 시각은 작업마다 1초 전진한다.

채팅과 웹 호출을 구분하고 웹 호출 한도는 구현하지 않는다. 사용자별/여행별 외부 API 비용은 표시하지 않는다. 일·월 예산 중 하나라도 도달하면 감시 상태를 멈춤으로 보여준다. API별 현재 예산과 한국 시각의 데모 그래프는 집계 기준을 따로 표시한다. 실제 UTC 예산을 KST로 변환 구현한 것은 아니다. 공급자 무료 제공량과 운영 상한은 별개다.

운영 차단과 키 폐기를 혼동하지 않는다. 발송 확인은 확인 결론만 추가하며 재발송하지 않는다. 공지/점검의 사용자 웹은 이 앱 안의 미리보기다. 사용자 웹 자체를 변경하지 않았다.

## 검증

`npm run check`는 린트·타입·단위·빌드를 검사한다. 단위 시험은 미설정 모드 거절, 사유 검증, 실패의 원자성, 감사 기록, 차단/해제, 답변/공지 본문, outbox 중복 확인 거절, 일·월 예산 경계를 다룬다.

브라우저 시험은 별도 demo 빌드 후 `npm run test:e2e`로 실행한다. HTML도 먼저 재생성한다. 모드 누락 브라우저 시험은 `.next-unconfigured`에 따로 빌드한다. 브라우저 결과 폴더도 `test-results/e2e`·`test-results/unconfigured`로 분리한다. 시험 중인 빌드를 덮어쓰지 않는다.

GitHub의 [CI (admin)](../../../../.github/workflows/ci-admin.yml)은 demo를 명시한 `check` 빌드를 그대로 E2E에서 사용한다. `export:html` 실행 후 저장된 HTML과 차이가 있으면 실패하여 앱과 시연 파일의 차이를 방지한다. `test:unconfigured`는 환경변수를 빈 값으로 덮어쓰고 별도 빌드하므로 CI의 demo 설정과 분리된다. 실제 백엔드나 비밀 키는 사용하지 않는다.

최초 구현의 실제 결과와 명령·출력은 [작업 리포트](../../../wiki/records/reports/2026-09-29_2313_admin_프론트와_HTML_시나리오.md)와 연결된 evidence에 기록한다. 실제 백엔드 통합·팀원 검토·배포는 미실시다.

## 참고

- [화면 기획](SCREEN_PLAN.md), [와이어프레임 v1.2](mockups/wireframe-v1.2/index.html)
- [개발자 콘솔 package.json](../dev-console/package.json), [package-lock.json](../dev-console/package-lock.json): 의존성 버전과 품질 명령 구성 참고
- [프론트 작업 안내](../../UI_EVAL_WORKSPACE.md)
