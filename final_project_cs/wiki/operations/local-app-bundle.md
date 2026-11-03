---
type: guide
title: 로컬 고객·관리자 앱 묶음 실행
status: draft
domain: travel
---

# 로컬 고객·관리자 앱 묶음 실행

2026-10-25 격리 구현 계약. 실제 기동·DB·외부 제공처·모델·배포는 별도 승인입니다.

v2 정정: 이전 추출 PowerShell 7개 통과는 전체 cmd bootstrap 통과가 아니었습니다. 시작·종료 배치는 첫 ASCII 물리 줄 안에서 bootstrap과 종료를 끝내고 본문은 UTF-8로 읽습니다. `chcp` 후 LF 배치를 재개하지 않으며 LF·CRLF와 전달 바이트를 전체 cmd로 시험합니다. pause 없이 명시적으로 성공 0·실패 1을 반환합니다. 단일 줄에서 인자 없는 `exit /b`만 쓰면 PowerShell 실패가 0으로 바뀌는 추가 결함도 음성 회귀로 수정했습니다. [독립검토 후속 보고서](../records/reports/2026-10-25_local-admin-3300-v2.md).

- 기본 묶음은 고객 API `127.0.0.1:8042`, 운영 API `127.0.0.1:8070`, 고객 웹 `127.0.0.1:3100`, 제품 관리자 웹 `127.0.0.1:3300`입니다. Composer 개발 콘솔과 다릅니다.
- `triPilot-실행.bat check`는 파일·실행기와 계획만 점검합니다. 앱 import, 포트 접속, 서비스 시작·종료, DB, 모델, 마이그레이션을 수행하지 않습니다. 설정값·계정·키도 출력하지 않습니다.
- `%USERPROFILE%\.acop-ops\start-acop.ps1`가 있으면 기존 고객 API·감시·알림 기동 경로를 보존합니다. 없으면 README의 `python -m uvicorn app.presentation.api.app:app --host 127.0.0.1 --port 8042 --reload`를 사용한다고 명시합니다. 이 경우 감시·알림 작업자는 자동 추가하지 않습니다.
- 운영 API 포트는 `--host 127.0.0.1 --port 8070`으로 지정해 기존 `ACOP_OPS_PORT`와 웹의 `ADMIN_OPS_API_URL`이 어긋나지 않게 합니다.
- 공유 DB를 시작/종료하거나 스키마를 바꾸지 않습니다. 준비된 비공개 `.env`·`.env.apikeys`·운영자 계정·API 권한키를 재사용하며 자격증명을 생성하지 않습니다.
- 이미 열린 포트는 정상 앱으로 재사용하지 않고 **충돌 실패**로 반환하며 소유·종료하지 않습니다. 네 포트를 시작 전에 모두 검사하고 각 시작 직전에도 다시 검사합니다.
- 준비상태는 새로 시작한 PID/시작시각의 생존, listener PID가 그 프로세스 또는 자손임, 기존 앱 HTTP 계약의 성공을 모두 요구합니다. 고객 API `/health`는 `status=ok`, 운영 API는 추가로 `app=ops`, 두 웹은 루트 HTTP 200을 확인합니다. 앱 응답은 tenant·로그인·DB 설정 확인을 대신하지 않습니다. 마지막에 네 프로세스·포트·HTTP를 다시 검사하며 핵심 앱 사망·준비 실패·비소유 listener는 최종 실패입니다.
- 종료는 이 배치가 기록한 PID와 시작 시각이 모두 맞는 프로세스 트리에만 적용합니다. 실패 시 소유 기록을 남기고 별도 종료 명령으로 정리합니다. 기존 listener를 종료하거나 상태에 편입하지 않습니다.
- 개인 시작 스크립트 실행은 그 스크립트가 가진 감시·알림 등 부수효과도 포함하므로 승인 전에 별도 확인합니다.

## 준비와 명령

README의 DB·Python·환경변수 준비를 완료하고 두 프론트 폴더 각각 `npm ci`를 수행합니다(기존 `.env.local` 덮어쓰기 금지). 관리자에는 `NEXT_PUBLIC_ADMIN_DATA_MODE=live`, `ADMIN_OPS_API_URL=http://127.0.0.1:8070`을 지정합니다. 운영자 계정은 서버 `ACOP_UI_OPERATORS`, 기존 권한키는 `ACOP_OPS_API_KEYS`를 사용합니다. 값은 공개하지 않습니다.

프로젝트 루트 PowerShell에서:

```powershell
.\triPilot-실행.bat check  # 서비스 없는 사전 점검
.\triPilot-실행.bat        # 별도 승인 후 네 프로세스 기동
.\triPilot-종료.bat        # 이 배치 소유 프로세스만 종료
```

이 PC의 격리 빌드·시험은 [검증 기록](../records/reports/2026-10-25_local-admin-3300.md)에 기록합니다. 실제 HTTP·로그인·DB 저장 확인은 실행 승인 후의 별도 단계입니다.
