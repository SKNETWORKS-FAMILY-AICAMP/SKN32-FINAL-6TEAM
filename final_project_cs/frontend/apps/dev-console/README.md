# triPilot 개발팀 콘솔

액티비티·요식업·이동 팀과 코어 개발자가 테스트 입력, 도구 응답, 비교값, 최종 출력을 확인하는 독립 프론트엔드다. 운영자 업무 화면과 구분한다. 2026-09-21 사용자 승인 목업을 기준으로 구현했다.

**현재 명시적 샘플 모드다.** 실제 Core·에이전트·모델·외부 API 호출은 없다. 실행 기록과 저장한 사례는 현재 브라우저 탭의 `sessionStorage`에 보관한다. 같은 탭에서 새로고침은 가능하지만 다른 브라우저나 팀원에게 URL을 보내 기록을 공유하는 기능은 아니다.

## 실행

Node.js 22와 npm을 사용한다. Windows PowerShell 기준:

```powershell
cd D:\FinalProject\Dev\triPilot\frontend\apps\dev-console
npm ci
Copy-Item .env.example .env.local
npm run dev
```

환경 파일이 이미 있으면 기존 설정을 확인하고 필요한 값을 추가한다. 화면은 [http://127.0.0.1:3200](http://127.0.0.1:3200)에서 연다. 사용자 웹(3100)과 별개로 실행한다.

`NEXT_PUBLIC_CONSOLE_DATA_MODE=demo`를 명시해야 샘플 어댑터가 동작한다. 설정이 없거나 다른 값이면 연결 미설정 오류를 표시한다. API 연결 실패를 데모 성공으로 바꾸지 않는다. 환경 변경 후 개발 서버를 다시 시작하고, 배포용 앱은 다시 빌드한다.

## 화면

| 주소 | 기능 |
|---|---|
| `/teams` | 세 팀 선택, 시각·소요 시간·이동수단·샘플 버전·응답 조건 설정, 실행, 단계별 상세 |
| `/integration` | 코어 요청 전달, 요식업·이동 병렬 처리, 이동 결과를 받은 액티비티 판정, 코어 취합 |
| `/cases` | 기본·저장 사례, 입력 불러오기, 같은 입력의 A/B 비교, 실행 상세 연결 |
| `/runs/[runId]` | 저장된 실행 입력·조회값·비교·출력, 실패, 같은 입력의 새 실행, 사례 저장 |
| `/connections` | 내 PC/공용 서버 연결 구조와 미연결 항목 안내. 실제 설정 변경 기능은 아님 |

첫 화면을 열기만 해서는 실행을 만들지 않는다. `샘플 테스트 실행`을 누르면 4초 동안 샘플 단계가 진행된다. 도구 실패 조건은 2초에 실패하며 결과를 반환하지 않는다. 정상 완료와 기대 결과 일치 여부는 별도 상태다. 같은 실패 조건으로 재실행하면 다시 실패한다. 정상 흐름을 확인하려면 응답 조건을 변경하고 새 테스트를 실행한다.

샘플 A/B는 실제 모델·코드 버전이 아니다. A는 액티비티의 입장 마감 검사를 누락하고, B는 입장 마감과 관람 종료를 확인한다. 요식업·이동 로직은 두 버전에서 같다. 가상 장소와 고정 응답을 사용하며 실제 업무 규칙으로 채택한 것이 아니다.

## 개발·검증

```powershell
npm run lint
npm run typecheck
npm test
npm run build
$env:PLAYWRIGHT_CHANNEL = 'chrome'
npm run test:e2e
```

`npm run check`는 린트·타입·단위 검사·빌드를 실행한다. Playwright는 빌드된 앱을 3201 포트에 실행한다. 설치된 Chrome이 없으면 `npx playwright install chromium`으로 브라우저를 설치하고 `PLAYWRIGHT_CHANNEL`을 설정하지 않는다. 테스트용 서버를 개발 포트에서 실행하지 않는다.

구조와 개발 방식은 [DEVELOPMENT.md](DEVELOPMENT.md), 코어·팀 연결 항목은 [API_CONTRACT.md](API_CONTRACT.md)를 따른다. 기존 Python 콘솔과 백엔드는 수정하지 않았다.
