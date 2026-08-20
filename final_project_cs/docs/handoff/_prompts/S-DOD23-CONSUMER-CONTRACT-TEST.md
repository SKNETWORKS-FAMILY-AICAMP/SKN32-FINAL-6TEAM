# S-DOD23-CONSUMER-CONTRACT-TEST — 미래 consumer 도 idempotency 를 강제로 통과해야 하는 재사용 테스트

## 0. 배경

- `docs/evidence/DoD-23_consumer_idempotency.md` — 지금 consumer 는
  `OutboxWorker` 딱 1종뿐이고, 이건 idempotency 가 잘 증명돼 있다
  (`UNIQUE(topic, dedupe_key)`, `SELECT ... FOR UPDATE SKIP LOCKED`,
  동일요청 10회→1행). 진짜 갭은 "지금 부족하다"가 아니라 **"나중에 두
  번째 consumer 가 생겼을 때 같은 검증 없이 나갈 수 있다"** 는 것이다.
- 이 작업은 새 consumer 를 만드는 게 아니다 — **미래의 어떤 consumer 든
  반드시 통과해야 하는 재사용 가능한 계약 테스트(contract test)** 를
  만드는 것이다. `app/infrastructure/messaging/ports.py` 의
  `MessageBrokerPort` 를 읽어라.

## 1. 할 일

1. `tests/contract/test_consumer_idempotency_contract.py` 류의 재사용
   가능한 pytest fixture/parametrize 기반 계약 테스트를 만든다. 이 테스트는
   "이 프로토콜(`MessageBrokerPort` 또는 동등한 consumer 인터페이스)을
   구현하는 아무 consumer 나 넣으면" 다음을 검증해야 한다:
   - 동일 `dedupe_key` 메시지를 2회 처리 시도해도 side effect 는 1회만
     일어난다
   - 동시 처리 시도(레이스) 에서도 중복 실행이 안 된다
   - timeout 시 `unknown` 류 상태로 남고 자동 재실행되지 않는다(worker
     의 기존 동작과 일치해야 함)
2. 기존 `OutboxWorker` 를 이 계약 테스트에 실제로 통과시켜서, 계약 테스트
   자체가 유효하다는 것을 증명한다 — 계약 테스트를 만들어놓고 아무것도
   안 돌려보면 의미가 없다.
3. `docs/handoff/`(정확한 위치는 기존 계약 문서들 배치 규칙을 따라라)에
   짧은 문서를 하나 추가한다 — "새 message consumer 를 추가하려면 이
   계약 테스트를 통과해야 한다"는 규칙을 다음 개발자(개발자1/2 가 담당할
   Fulfillment&Logistics, Return&Refund 등)가 찾을 수 있는 곳에 남긴다.

## 2. 쓰기 대상

- `tests/contract/test_consumer_idempotency_contract.py` (신규)
- `docs/handoff/` 아래 신규 문서 1개(파일명은 기존 `0N_주제.md` 넘버링
  관례를 따르되, 다음 번호를 실제로 확인하고 정해라)
- `docs/reports/2026-08-20_S-DOD23-CONSUMER-CONTRACT-TEST_리포트.md` (신규)

## 3. 하지 말 것

- 새로운 consumer 구현체를 만들지 않는다(범위 밖 — 다른 개발자 담당)
- `OutboxWorker`/`worker.py` 의 기존 로직을 수정하지 않는다(이미 올바르게
  동작함 — 계약 테스트가 이걸 증명하는 용도로만 써라)
- `docs/evidence/DoD-23_consumer_idempotency.md` 직접 수정(Claude 가
  검증 후 갱신한다)

## 4. 검증

- `python -m pytest -q -m "not live"` 전체 실행 결과를 리포트에 실제
  출력 그대로 붙여라. 실행 전후 pass 수 변화를 명시해라(현재 329 passed,
  0 failed).
