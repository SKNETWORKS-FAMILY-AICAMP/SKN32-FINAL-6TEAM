# v6 승인 시험 guest 실8042 재조회

정본 보고서: [상위 기록](../../../../wiki/records/reports/2026-10-25_v6-owned-auth-readback-child.md).

실제 부모 PID24140 localhost/LAN8042, auth/me·consents·confirmed intake·owned trip 각1회: HTTP **8/8=100%**, CORS credentials8/8. auth/consents/trip 정제SHA는 양쪽·이전 shared-live와 동일하며 소유·version·items 일치. intake 전체 정제SHA는 양쪽/이전과 다르며 원인 미확정으로 엄격 parity FAIL 유지. 전체 고객 기능 PASS 아님.

시험 소유 업무11개 표 전후 fingerprint 동일. 전체 세션 비교에서 승인 guest last_used_at 1행만 변경. v6 runtime 모델counter 전후0. 고객브라우저/fixture copy/모델/유료/remote/서비스 stop·restart/제품코드변경/DDL0. 상세 safe JSON과 실행기 경로는 상위 보고서 참조.
