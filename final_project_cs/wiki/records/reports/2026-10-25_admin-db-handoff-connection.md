# 관리자 DB 인계 연결 현재 상태

확인 시각: 2026-10-25T12:03:21.390391+09:00

## 결론
지정 인계 DB 연결과 관리자 재기동은 검증했습니다. **현재 direct API 예약 값은 false/default·revision0이며, 명시 저장·로그인 수락은 아직 완료되지 않았습니다.** DB 인계 필드가 부족한 것이 아니라 기존 admin 로그인 비밀값의 안전한 전달만 현재 실행 세션에 없습니다. vault list는 저장 항목0이며 기존 비공개 설정에는 PBKDF2 hash만 있습니다. 비밀번호 추측·재설정·서명쿠키 직접발급·인증 우회는 하지 않았습니다.

| 수용 범위 | 결과 |
|---|---|
| V10 지정 인계 → DB 정확 식별 | 확인 |
| 별도 read-only cluster/app-role 검증 | 확인 |
| 관리자3300 + ops8070 실제 HTTP | 확인 |
| 정식 로그인 → revision GET → OFF PATCH → fresh GET | 차단: 기존 credential private 전달 필요 |
| proxy/direct OFF 일치 및 독립DB 영속 OFF | 미실행 |

## 정확 DB와 완료 범위
shared_ownership_reconciliation/HANDOFF.md·reconciliation.json → V10 지정 보고서 → service-v10-20261025T113749/HANDOFF.json·service-identity.json 및 db-shared-20261025/HANDOFF.json을 읽었습니다. 인계는 **현재 PC native Windows PostgreSQL**이며 WSL/타PC/원격 DB를 가정하지 않았습니다. 이미 살아 있는 PID22972의 endpoint127.0.0.1:5433/acop_cs, datadir C:/_proj/postgresql/data/guguroute-16, system_identifier7700321712607772424, guguroute_app non-superuser가 실제 read-only 연결과 일치했습니다. private 설정 위치는 C:/_proj/postgresql/run/private/app.env입니다(본문 비공개). 별도 관리자 인증보관 파일을 읽어 cluster identity만 read-only 대조했으며 비밀값을 증거에 저장하지 않았습니다.

DB 설치·기동·restore·seed·migration·schema 수정0. shared905/archives/vector 차이는 해결한 것으로 승격하지 않습니다.

## 런타임 수정 및 실제 결과
기존 proc_e2281686a331/proc_b9462df91396 handle과3300/8070 listener는 모두 없었습니다. 무관 PID 종료 없이 기존 local_admin_3300_v2 후보를 재기동했습니다. 제품/공유backend 원본과 후보의 .env/.env.apikeys는 수정하지 않고, 새 scratch 런처가 지정 private app.env의 DB URL만 프로세스 환경 두 DB 설정에 주입합니다. DB endpoint/role guard 및 외부 네트워크 차단을 유지했습니다.

첫 launch_ops.py exit1은 PermissionError: Windows asyncio ProactorEventLoop → socket._fallback_socketpair의 내부 wakeup socket connect를 새 네트워크 가드가 차단한 것입니다. Settings validation/DB auth/DB endpoint/port collision 실패가 아닙니다. 표준 라이브러리 해당 정확 frame만 허용해 ops-retry1로 재기동했고 첫 실패 trace/log를 보존했습니다.

- ops: proc_4906d16bd1bd, listenerPID24596, cwd=C:\Users\kcxsz\AppData\Local\hermes\profiles\guguroute\cache\scratch\local_admin_3300_v2\repo\final_project_cs, 부모 handed_off 확인
- admin: proc_c18061b7c7aa, listenerPID27004, cwd=동일 후보/frontend/apps/admin, 부모 handed_off 확인
- GET8070/health200, GET3300/settings200
- GET8070 및3300/admin/api/session 각200, configured=true/authenticated=false
- GET3300/admin/api/settings/limits401(정상 인증경계)
- 기존 limits:read scope key를 메모리에서만 사용한 GET8070/admin/limits200: travel.booking.enabled=false, source=default, revision0, updated_by/at=null

GET 설정 API는 기존 코드의 _revision가 state행 INSERT ON CONFLICT DO NOTHING을 수행할 수 있는 정식 제품 API입니다. 이는 read-only SQL probe와 구분합니다. 예약값 명시 PATCH는0입니다.

## 이어받을 정확 작업
accept_off.py는 기존 계정 credential JSON을 private stdin으로만 받아 실제3300 proxy의 GET session → POST login → GET session → settings GET/revision → false PATCH → freshGET, direct8070 일치, 별도 read-only DB value/revision/audit1 검증을 수행하도록 작성했습니다. 아직 실제 인증/저장 실행은 아니며 빈stdin 실행은 exit2 INPUT_REQUIRED로 검증했습니다. 비밀 JSON을 명령줄/보고서/채팅에 적지 말고 부모가 가진 승인된 비공개 전달 경로로만 공급해야 합니다. 현재 계정 hash로 로그인 재료를 대신하거나 API키로 proxy로그인을 우회하지 마세요.

## 증거
active-profile scratch/admin_db_handoff_connection/: db-readonly-verification.json, http-readonly.json, listener-discovery.json, ops-startup.json, ops-failure.json, ops.log, ops-retry1.log, admin.log, HANDOFF.json, authenticated-acceptance.json(INPUT_REQUIRED), accept_off.py, manifest.json. 소스 SHA 전후 일치·후보 private env SHA 유지. 이 서비스는 scratch 런처/후보/runtime 의존입니다.


## 2026-10-25 보충 — 예약 OFF 실저장 완료

[실측] 이전 인증 입력 대기·명시OFF 미완료는 후속 정식 로그인/저장·fresh proxy/direct GET·독립 read-only DB 확인으로 해소됐습니다. false/override, revision1, admin, audit1; acceptance_rc=0(부모 전달). 현재 PC native5433이며 이전 WSL 요구와 다릅니다. DB 위치 추가 변경 없음.

## 관계 — 보충

- [완료 근거와 남은 범위](../../../../wiki/records/reports/2026-10-25_admin-db-handoff-connection.md)
