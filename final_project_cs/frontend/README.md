# triPilot 서비스 프론트엔드

사용자 웹·개발팀 콘솔·서비스 관리자 웹을 개발할 공간이다. 전체 담당과 기존 콘솔·평가 코드의 위치는 [UI·검증 작업 안내](https://github.com/roroblack/A-COP/blob/role-ui-eval/UI_EVAL_WORKSPACE.md)를 본다.

**개발 우선순위(2026-09-14 사용자 결정): 웹 1순위 → Personal Agent / MCP 2순위 → 모바일 앱 3순위 보류.** 웹은 PC·모바일 브라우저를 포함한다. 앱은 배포 시 개발자 등록 문제로 이번 개발·배포 범위에서 제외하며, 프로젝트 종료까지 적용하지 않을 가능성이 높다. 재개 여부·시점은 미정이다.

2순위 agent는 외부 Personal Agent / MCP 접점이다. 웹 채팅·여행 검증에 필요한 백엔드 Agent Runtime은 웹 구현에 필요한 범위에서 함께 연결한다.

| 앱 | 위치 | 기술스택 | 상태 |
|---|---|---|---|
| 사용자 웹 | [apps/web](apps/web/README.md) | Next.js 16 + React 19 + TypeScript | 웹 MVP 1차 5개 화면 구현, 명시적인 데모 어댑터로 실행 |
| 개발팀 콘솔 | [apps/dev-console](apps/dev-console/README.md) | Next.js 16 + React 19 + TypeScript | 팀별·코어 통합 테스트, 사례·A/B 비교, 샘플 어댑터 구현 |
| 관리자 웹 | [apps/admin](apps/admin/README.md) | Next.js + React + TypeScript | 웹 개발 범위. 폴더 준비, 앱 초기화 전 |
| 모바일 앱 | [apps/mobile](apps/mobile/README.md) | Expo + React Native + TypeScript — 기존 선택 보존 | 3순위 보류. 폴더만 예약, 이번 초기화·개발·배포 제외 |

## 기존 프로그램과 연결

- 백엔드는 `../final_project_cs/app`에 있다. 프론트가 사용할 API를 통해 연결한다.
- 기존 개발자 콘솔은 `../final_project_ui`에 있다. 관리자 웹과 콘솔의 목적을 구분하고, 기능을 옮길 때 재사용 범위를 정한다.
- 새 개발팀 콘솔은 `apps/dev-console`에서 별도 실행한다. 개발 포트는 3200이며 기존 Python 콘솔을 변경하거나 이식하지 않았다. [개발 기준](apps/dev-console/DEVELOPMENT.md)과 [연결 계약 협의안](apps/dev-console/API_CONTRACT.md)을 따른다.
- 평가 프로그램은 `../final_project_cs/eval`에 있다. 화면 코드와 별개로 실행하고 결과를 표시한다.

## 앱별 개발 기준

사용자 웹은 Node.js 22·npm, 개발 포트 3100을 사용한다. CSS Modules·공통 토큰·재사용 UI·기능 모듈·데이터 어댑터로 구성하며, [개발 기준](apps/web/DEVELOPMENT.md)과 [실행 안내](apps/web/README.md)를 따른다. 로그인·회원가입·서비스 결제는 웹 MVP 1차에 포함하지 않는다. 실제 여행 API 연동은 아직 완료하지 않았다.

관리자 웹 초기화 시 다음을 정한다. 모바일 앱은 보류 상태다.

1. 패키지 관리자·지원 Node.js 버전·프레임워크 버전과 잠금 파일.
2. 웹·관리자의 개발 포트와 API 주소·인증 연결 방법.
3. 첫 화면에 필요한 API 계약과 모의 응답.
4. 앱 실행·빌드·검증 명령.

공통 코드가 실제로 생기면 `packages/`를 추가한다. 백엔드 계약과 중복되는 타입이나 업무 규칙을 먼저 복제하지 않는다.
