# 카드와 출처 배치 — 실행 증거

## 실행 결과

| 실행 | 결과 | 범위 |
|---|---|---|
| 첫 빌드 | 실패 | 새 시험 코드의 nullable body 타입 오류. 앱 실행 전 중단 |
| 타입 원인 확인 | 실패 | `card-footer-types-first.log`: TS2531 1건 |
| 새 화면 시험 | 7/7 통과 | `card-footer-second.log` |
| 추가 회귀 시험 첫 실행 | 16/19 통과 | `card-footer-regression.log`: 출처가 항상 펼쳐져 있다는 옛 기대, 숨김 중 클릭, GET·SSE 시험 자료 불일치 보정 |
| 최종 빌드와 회귀 시험 | 20/20 통과 | `card-footer-final-browser.log` |
| ESLint | 종료 코드 0 | 선택한 소스 2개·시험 5개. `card-footer-final-lint.log`는 오류가 없어서 빈 출력 |
| TypeScript | 종료 코드 0 | 웹 전체 `tsc --noEmit`. `card-footer-final-types.log`는 오류가 없어서 빈 출력 |

서로 다른 화면 시험은 **25/25** 통과다. 새 화면 시험 7개와 최종 회귀 시험 20개 중 출처 시험 2개가 중복이므로 `7 + 20 - 2 = 25`다. 최종 회귀 시험은 전환 관측과 접은 목록에서 긴 제목 마커 다시 열기를 추가 검증한다. 실패했던 실행도 위 로그로 보존했다.

## 재실행

웹 앱 폴더에서 아래 환경을 사용한다. 외부 지도 타일이나 실제 고객 API는 호출하지 않는다.

```powershell
$env:NODE_OPTIONS='--max-old-space-size=1536'
$env:STUB_PORT='8068'
$env:LIVE_PORT='3128'
$env:PLAYWRIGHT_CHANNEL='chrome'
$env:LIVE_SKIP_BUILD='0'
node node_modules/@playwright/test/cli.js test -c .tmp/consent-progress.config.ts --reporter=line tests/live/card-status-footer.spec.ts tests/live/plan-focus.spec.ts
```

최종 회귀 시험 대상은 `card-status-footer`, `plan-focus`, `plan-check-redesign`, `plan-check-screen`, `server-review`, `plan-check-map-detail`, `day-strip-quiet`, `map-status-bar`다. 최종 로그의 20개 시험명이 선택 범위를 보여 준다. 설정과 실행 스크립트의 당시 내용은 [설정 보존본](reproduce-config.ts.txt), [실행 스크립트 보존본](reproduce-serve.mjs.txt)에 있다.

브라우저 시험 빌드는 `.next-consent-progress`를 사용한다. Next가 임시로 추가한 해당 폴더의 타입 참조 2줄만 원래대로 되돌린 후 최종 타입 검사를 했다.

## 화면

[실제 프론트엔드 촬영 모음](../../../../frontend/apps/web/mockups/card-status-footer-2026-10-08-v1/index.html). 휴대폰 폭 375px, 중간 폭 514px, PC 폭 1280px에서 촬영했다. 붉은 지도는 mock 서버 시험용 타일이다.

mock 서버 시험 25/25 (화면 반응).

실서버 확인 (서버 응답): 안 했음 — 이번 카드·출처 변경의 공개 앱 응답은 확인하지 않았다. 별도 채팅 읽기 전용 진단과 구분한다.
