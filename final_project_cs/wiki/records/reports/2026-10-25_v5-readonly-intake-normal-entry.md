# v5 intake GET readonly 원인 및 정상 writable 입구 실측 (2026-10-25)

- 제품 패치 없음. frozen v2/v5 `view`, `reap_stalled` 함수 해시 동일.
- shadow 원본 로그는 critical/access_log=false로 traceback을 보존하지 않았습니다. 동일 frozen 정상 API 경로·저장된 실 guest cookie·readonly DB 조건 재현에서 `web_intake_view → view:523 → reap_stalled:506 → execute`, PostgreSQL **25006 ReadOnlySqlTransaction**을 확인했습니다. 원본 로그 stack이라고 과장하지 않습니다.
- reaper는 무조건 UPDATE를 발행하지만 **tenant_id + intake_id 한 건 범위**, 전역 고객 reap가 아닙니다. customer 소유권 SELECT는 그 뒤입니다. 기존 v2 계약이며 새 회귀로 판정하지 않습니다.
- shared old reading 3행 원문 fingerprint 전후 동일. swap/startup 전역 reap 없음. 해당 stale 접수를 GET하면 기존 계약대로 fatal/stalled 및 해당 접수의 비고객 revision1 claim 정리가 일어날 수 있습니다.
- approved improved DB 전용 새 tenant, 원본에서 최소 owned fixture + 진짜 cookie/session row 및 필요한 FK만 복사했습니다. 원본 DB direct write/기존 compare row 삭제/전역 복원/새 cookie forge 0. consent_current가 view라 1차 copy는 transaction rollback, 두 번째 missing place FK도 rollback 후 최소 참조 place 2행만 복사했습니다.
- **실 loopback writable API :50487**: auth/me·consents·intake·trip **4 경로 × 2회 = 8/8 HTTP200 (100%)**. live **8/8 (100%)**; shadow **6/8 (75%)**, 같은 intake만 두 번 500. 종전 7/8은 live4+shadow4 합산이지 shadow 단독 7/8이 아닙니다.
- copied business rows GET 전후 hash 불변, session은 허용 last_used_at만 변경. core 여행 항목/소유권 일치. 모델 생성 0, 외부 호출 차단, autostart/warmup 없음. 실제 mobility dataset 경로 유지.
- **전체 응답 동등은 아님**: comparison operational dataset 차이로 review risk enrichment, 주소/map/plan URL 차이를 메타 경로로 보존했습니다. 따라서 auth 정상 writable 입구는 검증했으나 전체 readiness green으로 바꾸지 않았고 원래 READY_AUTH_FINAL은 보존했습니다. Dining 미해결은 별도입니다.

## 증거와 인계

C:\Users\kcxsz\AppData\Local\hermes\profiles\guguroute\cache\scratch\public-web-binding-v5-20261025-162650-c2dac8ce\runtime-v5-serving\normal-writable-20261025

`readonly-api-stack.json`, `discovery.json`, `copy.json`, `acceptance.json`, `response-diff-paths.json`, `current-processes.json`, `AUTH_ENTRY_CLOSEOUT.json`.

live proc_80625bd70a7a/8042, readonly shadow proc_2c0489f2c2ec/61695 유지. 정상 compare proc_75ec7b9e64d0/50487은 부모 인계. live 종료 권한 없음. final/rollback 명령과 생성시각/리스너 PID는 AUTH_ENTRY_CLOSEOUT에 있습니다. 부모가 교체 직전 lineage 재검증해야 합니다.
