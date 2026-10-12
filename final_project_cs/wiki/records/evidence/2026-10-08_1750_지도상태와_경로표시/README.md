# 지도 상태와 경로 표시 — 실행 근거

로컬 작업 트리 기준. 확인 시 Git HEAD는 `38f9e08cb08cafba6ce2f66ff7b08c19788cf1d1`이며 변경 코드는 아직 그 커밋에 포함되지 않았다. 실제 Chrome, 시험용 여행 자료 및 지도 타일을 쓰는 mock 서버, 웹 빌드 폴더 `.next-consent-progress`, 단일 화면 시험 작업자, Node 메모리 상한 1536MB 조건이다. 공개 서비스 응답 시험이 아니다.

최종 원문:

- [단위시험 51/51](map-status-unit-complete.log).
- [화면 묶음 26/26](map-status-ui-complete.log).
- [다시 제출 회귀 1/1](map-status-recheck-final.log).
- [경로 여백 보완 뒤 1/1](map-status-route-spacing-final.log).
- [ESLint](map-status-lint-final.log), [타입 검사](map-status-type-final.log): 종료값 0.

중간 실패 로그도 보존했다. `map-status-reset-instrument.log`는 초기화가 첫 일정의 시간 두 값만 보내던 실측 요청이다. `map-status-source-reset-repair.log`는 전체 일정 기준으로 수정한 뒤 세 일정의 시간 여섯 값이 복구된 요청을 기록한다. `map-status-lint-complete.log`의 시험 harness 지적은 호출 한 줄에 한정해 Node 시험이라는 사유를 적은 뒤 최종 ESLint로 재확인했다. 처음 sandbox 캐시 접근 실패도 단위시험 실패 원문에 남아 있다.

## 재현

웹 작업 폴더에서 아래 명령을 실행한다. 설치된 Chrome을 사용한다. `reproduction.config.ts.txt`와 `reproduction-serve.mjs.txt`는 이번 실행 설정의 사본이며 실제 실행 경로는 `.tmp/consent-progress.config.ts`와 `.tmp/consent-serve.mjs`다.

```powershell
$env:STUB_PORT='8068'
$env:LIVE_PORT='3128'
$env:PLAYWRIGHT_CHANNEL='chrome'
$env:LIVE_SKIP_BUILD='0'
$env:NODE_OPTIONS='--max-old-space-size=1536'
node node_modules/@playwright/test/cli.js test -c .tmp/consent-progress.config.ts --reporter=line tests/live/map-status-bar.spec.ts tests/live/plan-check-map-detail.spec.ts tests/live/day-strip-quiet.spec.ts tests/live/plan-focus.spec.ts tests/live/loading-handoff.spec.ts
$env:LIVE_SKIP_BUILD='1'
node node_modules/@playwright/test/cli.js test -c .tmp/consent-progress.config.ts --reporter=line tests/live/plan-check-redesign.spec.ts -g '고친 게 있으면'
node node_modules/vitest/vitest.mjs run src/features/map/route-labels.test.ts src/features/map/map-geometry.test.ts src/features/map/route-lines.test.ts src/features/plan-check/use-reveal.test.ts src/features/plan-check/model.test.ts
```

화면 촬영은 `MAP_STATUS_SHOTS`에 새 출력 폴더를 지정한다. 기존 출력 폴더를 지정할 때는 먼저 원본을 백업한다. 이 실행에서 빌드가 자동 추가한 `.next-consent-progress/types/**/*.ts`, `.next-consent-progress/dev/types/**/*.ts` 두 줄은 마지막 타입 검사 전에 제거했다.
