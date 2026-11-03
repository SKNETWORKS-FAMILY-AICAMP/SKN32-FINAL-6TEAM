# 원본 직접 실행 준비 (ops 8070 · admin 3300) — 2026-10-28

**준비 완료, 기동 0회.** `triPilot-실행.bat check` rc=0. admin `npm ci` 신규·web `npm ci` 재설치(Node 24.22.1 arm64, SWC arm64, lock 불변, gitignore 대상). Python은 기존 프로필 venv 3.12.15 재사용, ops·고객 앱 import smoke OK.

남은 요건: `.env` DB URL 비밀번호 부재(기동 시 비공개 DB 설정을 프로세스 env로 주입), `ACOP_OPS_API_KEYS` 없음, 운영자 비밀번호 원문 없음, 포트 4개 기존 점유, venv에 python-docx·openpyxl 없음, web `.gitignore`에 `.next-batch/` 없음.

상세: [루트 인계](../../../wiki/handoff/2026-10-28_original-runtime-prep-ops-admin.md). RUNBOOK은 프로필 scratch `original_runtime_prep/RUNBOOK.md`.
