# v6 백엔드 실제 교체

## 변경·실검증
부모가 tracked `proc_80625bd70a7a`의 bash6704→26640→listener25900 계보·생성시각·양쪽8042 소유를 다시 확인했습니다. 공유 DB 읽기 전용 활성 게이트는 현재 접수0·Dining running0·미종료 모델0·idle=true였습니다. 3개 과거 잔류행은 소유권 근거 및 fingerprint로 평가에서만 제외했으며 고객 DB 상태는 고치지 않았습니다.

v6 preflight RC0 확인 후 정확한 기존 소유 프로세스만 종료하고 v6를 기동했습니다. 기동 직후 연결 거부 및 readiness timeout 1회가 있었고 재시도 뒤 양쪽 준비 완료를 확인했습니다. 무중단 전환이라고 주장하지 않습니다.

- 현재 부모 API handle `proc_f7a4d23e66d5`, 실제 listener PID24140.
- localhost/LAN8042 핵심 HTTP 각7/7, 전체14/14 기대 상태 일치(auth/me 미인증401 포함).
- 실제 로드 모듈341/341 SHA 일치.
- `plan_test_mode=true`; 선택 public-web 검색은 명시OFF.
- v6 정확 회귀1344/1344, 별도HTTP4/4는 사전 candidate 결과입니다.
- 합친 제품 수정은 기존 comment7 생성 anchor·comment8 대안 준비 순서·설문 전달 및 v6 edit_intent 분수/clock schema2hunk입니다. 검증 분모를 전체 고객 기능 성공으로 확대하지 않습니다.
- 증거: 프로필 scratch `action-v6-20261025-172901-05e642d6/runtime-v6-serving/PARENT_SWAP_PUBLIC_VERIFIED.json`, `SOURCE_V6_PARENT_SWAP.json`.

## 인증 관문 연결
v5 정상 비교DB GET8/8(4경로×2)과 live8/8로 인증 입구 검증을 완료했습니다. 이전 shadow는 read-only UPDATE25006 때문에6/8 실패 기록을 보존합니다. v6 intake handler 해시는 v5와 동일합니다. v6 교체 후 실제 인증 재조회는 다음 독립 절에서 수행합니다. 전체 risk/address/map/planURL 응답 동등성은 미확인입니다.

## 남은 결함
49 수용행은13 pass·7 fail·29blocked이며 영업시간 내 추가 별도1행도 날짜 오저장 실패입니다. 날짜 저장과 내부 failure/검증 오류의 고객 출력 누출은 별도 새 자식이 각각 수정 중입니다. Dining 약72초·근거 실패, Activity 운영자료/alias 및 실검색 공급자, 전체49행 실행기 완성은 미완료입니다. 모델 단일 소유자는 날짜 수정 자식이며 게이트는 새 runtime의 counters를 사용해야 합니다.

## 롤백·프런트
rollback candidate 명령은 위 인계 JSON, 실제 교체 전 실행본 v2는 `latest-serving-6c345-20261025/runtime-v2/launch-final.py`로 보존되어 있습니다. 추가 실패 시 검증된 rollback 대상을 명시하여 수행하고 조용히 대체하지 않습니다. 프런트 v5 parent handles localhost `proc_85a6dc785a17` / LAN `proc_95fa8f2297ba` 유지. 제품 코드 하드코딩·새 fallback 추가 없음; 주소/모델/포트는 승인된 실행 manifest 구성입니다.
