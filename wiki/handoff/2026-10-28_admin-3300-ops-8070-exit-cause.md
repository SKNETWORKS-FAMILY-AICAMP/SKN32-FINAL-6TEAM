# 관리자 3300·ops 8070 종료 원인 — 2026-10-28

- 원인: 06:02 원본 전환 세션이 의도적으로 taskkill했다(`scratch/original_switch_20261028`). 파일 삭제(10-27 19:46 수동 scratch 정리 `_cleanup3b.py`)가 원인이 아니다. 지금은 원본 작업트리 서버(8070 PID26564, 3300 PID32620)가 200으로 동작하고, acop_cs에는 4fee819 migration 객체 표본 10/10이 있다. 거부형 복원 런처는 `scratch/admin-restore-20261028-0612`에 있고, 기동하지 않았다. [보고서](../records/reports/2026-10-28_admin-3300-ops-8070-exit-cause.md)
