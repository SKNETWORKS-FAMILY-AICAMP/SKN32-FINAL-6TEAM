# v6 실교체 후 시험 guest 인증·소유 GET 재조회

2026-10-25 18:04 KST 실행. 부모 live `proc_f7a4d23e66d5` 실제 localhost/LAN8042 listener PID24140, PPID23792 및 생성시각 `/Date(1792918738607)/` 재확인. 서비스 kill/restart 없음. source-v6 변경 없음.

## 결과와 경계
- 정상 실8042에서 승인된 registered-guest 한 명만 사용했습니다. auth/me·consents·기존 confirmed intake·owned trip 각 1회 × localhost/LAN = **8/8 HTTP200 = 100%**. shadow 호출0, 추가 인증 재시도0.
- 각 응답에서 Origin 정본 반사와 `Access-Control-Allow-Credentials: true`를 확인했습니다. localhost 요청 Origin은 `http://localhost:3100`, LAN은 `http://192.168.0.15:3100`; 각 4경로 모두 일치. CORS는 요청8/8이며 네 종류 Origin을 시험했다는 뜻이 아닙니다. 모든 Set-Cookie 없음.
- auth/me·consents·trip 정제 응답은 localhost/LAN 및 이전 shared-live 정제 SHA와 **3/3 동일**. trip 소유 customer/trip, version 및 items 동등하고 승인 fixture 소유와 일치합니다.
- **intake 정제 전체 응답 SHA는 localhost/LAN 사이에도 다릅니다.** 이전 shared-live SHA와도 불일치. 원문 미저장·메모리 폐기 후 차이 경로를 보존하지 못했으므로 원인/핵심 항목 동등성을 확정하지 않습니다. 정확히 8회 제한 때문에 추가 GET하지 않았습니다. acceptance.json의 엄격한 전체 응답 동등성 판정은 `FAIL`을 그대로 보존합니다. HTTP/인증/소유 여행 읽기 성공을 전체 응답 동등성 PASS로 확대하지 않습니다.

## 안전
- 읽기 전용 독립 DB 연결로 시험 소유 customer·consent_events·trip·itinerary versions/items·intake·sources·claims·review·survey·test scenario의 전후 행수와 SHA를 비교하여 모두 동일했습니다. confirmed intake만 조회했으며 stale 고객 접수 GET은 하지 않았습니다. reaper UPDATE 문은 기존 경로에서 실행될 수 있으나 시험 업무행 변경은 없습니다.
- 전체 web_sessions 행을 메모리에서 비교: 변경 1행이며 승인 fixture의 `last_used_at`만 바뀌었습니다. 세션값·쿠키값·해시는 출력/저장하지 않았습니다. 고객 브라우저 접근0, fixture 재복사/DB쓰기0, verifier DML0.
- **v6 runtime** policy counters 전후 denied/chat_admitted/chat_completed 모두0. 모델·유료·remote 호출0. 날짜/모델/내부 failure 수정 자식 작업과 독립입니다.
- 부모가 이미 확인한 public HTTP14/14·startup loaded341/341을 반복 분모에 넣지 않았습니다. 최초 전환 연결거부/timeout 짧은 공백 기록을 유지하며 무중단이라 하지 않습니다. 이후 lazy import 증가만으로 source drift라 판정하지 않습니다. migration906/DDL 반복0.

## 산출물
프로필 scratch:
- `v6-auth-readback-20261025.py` (검증기, 재실행용이 아님: 정확8회 완료)
- `action-v6-20261025-172901-05e642d6/runtime-v6-serving/auth-readback-owned-20261025/acceptance.json` (안전 JSON: 응답은 SHA만, DB는 행수/SHA만)

이 결과는 시험 guest 한 명의 좁은 인증·소유 읽기 검증입니다. 고객 전체 기능 PASS가 아니며 intake 전체 응답 동등성은 미해결입니다. 과거 비교DB의 risk/address/map/planURL enrichment 차이와 이번 shared-live 비교를 혼동하지 않습니다.
