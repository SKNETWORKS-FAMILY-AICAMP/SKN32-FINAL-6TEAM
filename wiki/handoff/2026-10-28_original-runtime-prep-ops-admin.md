# 원본 직접 실행 준비 (ops 8070 · admin 3300) — 2026-10-28

**준비 완료, 기동 0회.** 원본 `triPilot-실행.bat check` rc=0 (venv 3.12.15 + Node 24.22.1 arm64 PATH). 서버 중지·기동, 소스·lock·tracked 파일 변경 없음.

- 설치: `final_project_cs/frontend/apps/admin` `npm ci` 신규(next 16.3.5, SWC arm64), `apps/web` `npm ci` 재설치(기존 x64 전용 node_modules는 프로필 scratch `original_runtime_prep/web_node_modules_x64_backup_20261028`로 이동 보존). 둘 다 gitignore 대상, lock sha256 불변.
- Python: 기존 프로필 venv `api-runtime-20261025-014236`(3.12.15) 재사용. ops·고객 앱 import smoke OK(원본 모듈만 로드). python-docx·openpyxl 미설치(업로드 .docx/.xlsx만 영향).
- 남은 요건: 원본 `.env` DB URL은 비밀번호가 없어 연결 실패 → 기동 시 비공개 DB 설정을 프로세스 환경변수로 주입(읽기 전용 연결 확인 OK). `ACOP_OPS_API_KEYS` 없음(admin 화면엔 불필요). 운영자 `admin` 항목 존재, 비밀번호 원문 없음. 네 포트 모두 기존 scratch 런타임이 점유 중이므로 전체 묶음 실행은 충돌 실패; 3300·8070만 별도 스크립트로 교체 권장. web `.gitignore`에 `.next-batch/` 없음.
- RUNBOOK·시작/종료 스크립트·변경 목록: 프로필 scratch `original_runtime_prep/{RUNBOOK.md,start_ops_admin.ps1,stop_ops_admin.ps1,ORIGINAL_CHANGES.md}`.
