# 인계 — 원본 ops 8070·관리자 3300 직접 실행 (2026-10-28)

- 지금 원본에서 실행 중: ops `http://127.0.0.1:8070` 리스너 PID 26564(루트 15464), 관리자 `http://127.0.0.1:3300` 리스너 PID 32620(루트 6576). cwd는 각각 `C:\_proj\final_workspace\final_project_cs`, `...\frontend\apps\admin`. 소유 기록 `scratch/original_runtime_prep/run/owned.json`, 로그 같은 폴더 `20261028-060324-*.log`.
- 정지: `powershell -NoProfile -ExecutionPolicy Bypass -File scratch\original_runtime_prep\stop_ops_admin.ps1 -Go`(기록된 PID+시작시각 일치만). 상태 확인: `scratch\original_switch_20261028\status.ps1`.
- 운영자 `admin` 로그인·프록시/직접 GET·읽기 전용 DB 모두 `travel.booking.enabled=false`(override, admin, revision 2) 일치. 예약 기능만 꺼진 상태이며 앱·API·DB는 실행 중입니다.
- 원본 변경: `final_project_cs/.env`(Git 무시, 백업 있음), 이 인계·보고 2개, index 2곳 한 줄씩, 역사 정정 보고에 보충 절 1개. 소스 코드 변경 0, 커밋 0.
- `next dev` 부수 효과: admin `tsconfig.json` 수정은 추적 원본 바이트로 되돌렸습니다(재기동하면 다시 생길 수 있음). 새로 생긴 `frontend/apps/admin/AGENTS.md`·`CLAUDE.md`(Next 16이 생성)는 삭제 승인 대기로 그대로 두었습니다.
- 남은 것: 원본 `luna_rep2.json` 정정 자료 반입 여부(사용자 결정), 최신 team develop 동기화·날짜 위험 통합(원본 규칙상 이번 제외), 이전 ops 8070은 원 소스가 삭제돼 정확 롤백 불가(근사 절차만).
- 상세: [보고](../../final_project_cs/wiki/records/reports/2026-10-28_original-runtime-ops-admin-switch.md).
