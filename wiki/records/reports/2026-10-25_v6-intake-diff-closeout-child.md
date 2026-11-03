# v6 owned intake localhost/LAN 차이 확정 보충 closeout

2026-10-25 18:10 KST. **authentry PASS, intake core match=true, full parity=false**입니다. 기존 `2026-10-25_v6-owned-auth-readback-child.md`와 원본 acceptance FAIL은 그대로 보존합니다.

## 실측
- 동일 승인 confirmed owned fixture만 localhost/LAN 각 1회, 추가 정상 GET **2/2=100% HTTP200·CORS 일치**입니다. 재시도0, 합계2회이며 허용 예비2회는 쓰지 않았습니다.
- localhost 요청 09:10:25.618808–09:10:26.835134 UTC, LAN 요청 09:10:26.835134–09:10:27.989498 UTC. 요청별 route template·공개 origin·status·pair diffpath count=3은 안전 JSON에 보존했습니다.
- 전체 raw JSON을 private 프로세스 메모리에서 재귀 비교한 차이는 정확히 다음 **3개**입니다. 원문 값·URL query/서명·쿠키/세션 해시 미출력, raw 응답 저장0입니다.
  - `/review/items/0/risk/checked_at` (str → str)
  - `/review/items/1/risk/checked_at` (str → str)
  - `/review/risk_checked_at` (str → str)
- host별 plan/map/action URL 차이0, generated_at/heartbeat 차이0입니다. 각 차이의 JSON pointer·key·type·좌우 SHA는 difference.json에 남겼습니다.

## 원인과 명시 core projection
`source-v6/final_project_cs/app/domains/travel_ops/components/intake/review.py:1184–1195`는 저장된 review를 읽은 뒤 요청마다 `risks.decorate`를 호출합니다. `risks.py:55–67`의 기본 시각은 `datetime.now(KST)`, `113–118`은 risk 관측 시각을 응답에 붙이며 `287–293`은 risk 원본 checked_at이 없으면 요청의 now를 씁니다. 따라서 이번 3개는 **요청 시점 risk 장식 metadata**입니다. URL origin 차이, 모델 출력 차이, 업무 revision 변이가 아닙니다. cached GET도 관측 시각이 같다는 계약은 아닙니다.

계약 `final_project_cs/wiki/external/rest-endpoints/web-intakes.md:20,37–46,130–139`를 확인했습니다. projection은 **전체 JSON에서 위 정확한 3 pointer만 제외**합니다. identity·trip/intake·revision·day/date/time·items·sources/claims·question·dining·risk 판정과 나머지 모든 알 수 없는 필드도 유지합니다. 전체 재귀 diff가 위 3개뿐이므로 이 projection은 동등합니다. 임의 hash 마스킹으로 성공을 만든 것이 아니며 원문 폐기 후 core hash를 지어내지도 않았습니다. full parity는 계속 false입니다.

## 안전과 현재 runtime
- 양 host listener PID24140, PPID23792, 생성시각 `/Date(1792918738607)/`, 부모 handle `proc_f7a4d23e66d5`와 일치했습니다. review 모듈 startup provenance SHA와 disk SHA 일치, 원인 소스 SHA는 closeout.json에 보존했습니다. risks는 lazy import이므로 startup provenance에 없다는 한계를 유지합니다.
- 독립 readonly DB 연결로 승인 업무11표 전후 count/SHA 동일: 변경0. 전체 session 비교 변경1행이며 승인 fixture `last_used_at`만 바뀌었습니다. verifier DB DML0입니다.
- **새 v6 serving runtime** `policy-counters.json` 전후 denied/chat_admitted/chat_completed 모두0입니다. 다른 date child/model owner counter와 혼합하지 않았습니다. 모델·paid·remote 요청0, 제품/sharedschema/고객state 수정0, kill/restart0입니다.
- genuine fixture private 경로 ACL은 SYSTEM·Administrators·현재 사용자만 상속 허용임을 확인한 뒤 raw response를 파일이 아닌 private 메모리에서만 비교했습니다.

## 안전 증거 실명
프로필 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/` 아래:
- `v6-intake-diff-closeout.py` — 실행 완료, 자동 재실행 금지(2 GET 완료)
- `v6-intake-closeout-classify.py` — 추가 HTTP 없는 분류기
- `action-v6-20261025-172901-05e642d6/runtime-v6-serving/intake-diff-closeout-20261025/difference.json` — 최초 실제 재귀 diff, 미분류 상태 보존
- 같은 디렉터리 `closeout.json` — 근거 기반 최종 분류·projection·안전 판정

이 결과는 이번 동일 runtime pair의 core 동등성만 닫습니다. 이전 shared-live raw intake가 없으므로 그 과거 불일치 원인까지 소급 확정하지 않습니다. 고객 전체 기능 PASS도 아닙니다.
