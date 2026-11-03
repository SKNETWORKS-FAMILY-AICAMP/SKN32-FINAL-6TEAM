# 인계 — 예약 OFF 8경로 원본 적용 (2026-10-25)

- 원본 변경: 8경로(수정 5·신규 3), 워킹트리만. index·HEAD·push 변경 0. 백업·복원 매니페스트 `scratch/booking-apply-20261025/backup-full/RESTORE_MANIFEST.json`.
- 소유자 서버 3300(PID3888)/8070(PID6896)은 건드리지 않았고 옛 스냅샷 그대로입니다. 최신 원본 반영 교체는 admin-testmode-20261025 소유 세션의 인계·승인이 필요합니다.
- 남은 한 가지: 정식 로그인 + 프록시 GET. 비밀번호를 비공개 stdin으로만 `servctl.py final-login`에 넘기면 새 loopback 포트에 서버를 띄워 읽기 전용 확인 후 스스로 정리합니다(명령은 보고서 5절).
- 상세·해시·수치: [보고서](../records/reports/2026-10-25_booking-off-eight-path-apply.md)

**결과 2026-10-25 21:47**: 정식 로그인 완료(admin, session→login→session 200, 프록시 settings GET 2회 200). 프록시 = 직접 GET = 읽기 전용 DB 일치: `travel.booking.enabled` false · override · updated_by admin · revision 2, DB 감사 이벤트 1건(이벤트 revision 1 ≤ 상태 revision 2). runtime_limit* 3표 지문 전후 동일(설정 쓰기 0), PATCH·계정 변경 0. fresh 사본 loopback ops 55684 / admin 55685은 종료 후 LISTEN 0, 소유자 3300(PID3888)/8070(PID6896) 그대로. 사본↔원본 런타임 1,481파일 차이 0(원본에만 새 시험 2개 `test_llm_f3_acceptance.py`·`test_llm_overflow_f3.py` — 다른 세션 추가분, 서버 실행과 무관). 첫 시도는 stdin 미전달로 로그인 미실행(보존). 증거 `scratch/booking-apply-20261025/RESULT-final-login.json`·`serving-acceptance-final-login.json`.
