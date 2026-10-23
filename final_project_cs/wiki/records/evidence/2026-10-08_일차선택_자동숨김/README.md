# 일차 선택 줄 자동 숨김 실행 근거

2026-10-08, 로컬 개발 PC의 공유 작업 트리. 실제 Chrome과 mock 서버, 별도 Next 화면 빌드 사용.

- 화면 실행: 웹 폴더에서 node node_modules/@playwright/test/cli.js test -c .tmp/consent-progress.config.ts --reporter=line day-strip-quiet.spec.ts plan-focus.spec.ts.
- 조건: STUB_PORT/LIVE_PORT 지정, PLAYWRIGHT_CHANNEL=chrome, LIVE_SKIP_BUILD=0. DAY_STRIP_SHOTS는 새 화면 산출물 폴더.
- 결과: day-strip-ui-final.log 원문, 6 passed (45.9s). 반복 실행을 합산하지 않음.
- 오류 검사: node node_modules/eslint/bin/eslint.js src/features/plan-check/use-quiet-day-strip.ts src/features/plan-check/plan-check.tsx tests/live/day-strip-quiet.spec.ts; node node_modules/typescript/bin/tsc --noEmit. 두 로그는 오류 없이 종료 코드 0이어서 비어 있음.
- 공개 CS 앱 응답 확인·공개 배포: 안 했음.
- 화면: 휴대폰 375×812 3장, PC 1280×720 1장. 실제 앱 프론트이며 여행 데이터와 단색 지도 타일은 mock 서버 시험용.
