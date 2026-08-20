# S-PAYMENT-TIMEOUT-MOCK — 결제 provider timeout 을 실제로 겪어보는 통합테스트

## 0. 배경

- `docs/release_checklist.md` §5-3 — "실제 결제 provider 어댑터 없음 — 진짜
  결제 timeout 은 겪어 보지 않았다." 지금까지 `unknown` 상태는 단위테스트
  수준에서만 검증됐지, 실제 outbox publish 경로에서 결제류 provider 가
  타임아웃 나는 걸 end-to-end 로 겪어본 적이 없다.
- `app/infrastructure/messaging/worker.py` 의 `OutboxWorker.process_once()`
  가 `self.publisher(...)` 호출에서 `TimeoutError`/`ConnectionError` 를
  잡으면 `outbox.status='unknown'` 으로 기록하고 재큐잉하지 않는다(방금
  검증된 사실 — `docs/manuals/운영_unknown상태_대응절차.md` 참고, 이 문서를
  먼저 읽어라).
- `app/infrastructure/messaging/ports.py` 의 `MessageBrokerPort` 가 현재
  유일한 관련 포트다. 결제 전용 어댑터/포트는 아직 없다.
- **진짜 결제 게이트웨이에 연결하는 게 아니다.** "결제 provider 처럼
  동작하되 의도적으로 타임아웃을 낼 수 있는 mock publisher"를 만들어서,
  `unknown` 경로를 실제 코드 경로로 한 번 완주시키는 게 목표다.

## 1. 할 일

1. `MessageBrokerPort` 를 구현하는 mock 결제 publisher 를 만든다 — 이름은
   예를 들어 `MockPaymentGatewayPublisher` 류로, `publish()` 호출 시 설정에
   따라 (a) 정상 응답 (b) `TimeoutError` 발생 (c) `ConnectionError` 발생
   중 하나를 시뮬레이션할 수 있게 한다. 실제 네트워크 호출은 없다 — 순수
   인메모리 시뮬레이션이다.
2. 통합 테스트를 작성해 다음 전체 흐름을 실제로 완주시켜라:
   - 결제류 topic 으로 outbox 메시지 발행 → mock publisher 가 타임아웃 시뮬레이션
   - `OutboxWorker.process_once()` 실행 → `outbox.status` 가 실제로
     `'unknown'` 으로 바뀌고 `last_error` 가 기록되는지 DB 에서 직접 확인
   - 같은 메시지가 이후 `pending` 조회에 다시 걸리지 않는지 확인(재큐잉
     안 됨 — 자동 재실행 금지 원칙 실측)
   - `docs/manuals/운영_unknown상태_대응절차.md` 에 적힌 SQL 조회 패턴이
     실제로 이 메시지를 찾아내는지 확인
   - 사람이 확인 후 `transition_case()` 로 `VALID_CALLBACK` 또는
     `WAIT_EXPIRED` 를 호출하는 시나리오까지 테스트로 재현(Case 가 있는
     경우) — 절차서 §4 의 코드 예시를 그대로 테스트 안에서 실행해봐라.
3. 정상 케이스(타임아웃 없음)도 대조군으로 1건 넣어서, mock publisher 가
   평소엔 정상 동작한다는 것도 같이 증명해라.

## 2. 쓰기 대상

- `app/infrastructure/messaging/mock_payment_publisher.py` (신규,
  이름은 위 제안에서 벗어나도 되지만 `mock`/`payment` 의도가 드러나야 한다)
- `tests/integration/messaging/test_payment_timeout_unknown.py` (신규)
- `docs/reports/2026-08-20_S-PAYMENT-TIMEOUT-MOCK_리포트.md` (신규)

## 3. 하지 말 것

- 실제 결제 게이트웨이 SDK 연동, 실제 네트워크 호출
- `worker.py` 의 기존 timeout 처리 로직 수정(이미 올바르게 동작함 —
  건드리지 않는다)
- 자동 재시도 로직 추가(이 프로젝트 원칙과 정면 충돌)
- `docs/release_checklist.md` 직접 수정(Claude 가 검증 후 갱신한다)

## 4. 검증

- `python -m pytest -q -m "not live"` 전체 실행 결과를 리포트에 실제
  출력 그대로 붙여라. 실행 전후 pass 수 변화를 명시해라(현재 329 passed,
  0 failed).
