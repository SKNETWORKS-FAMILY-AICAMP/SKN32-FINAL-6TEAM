# DoD-23 — 모든 consumer 가 at-least-once 하에서 idempotent 하다

- v7 §27 항목 23 / 검증 방법: 동일 message 를 2회 전달하는 duplicate/replay integration test
- 실행: 2026-08-16, 재측정: 2026-08-20
- 판정: **통과** (2026-08-20 갱신 — 근거: `docs/reports/2026-08-20_S-DOD23-CONSUMER-CONTRACT-TEST_리포트.md`)

## 재현 명령

```powershell
python -m pytest tests/integration/controller/test_controller_integration.py -q -k "outbox or duplicate"
```

## 실제 출력

```
2 passed

test_outbox_duplicate_is_delivered_once
  같은 (topic, dedupe_key) 로 2회 publish
    → 두 번째는 새 message_id 를 만들지 않고 dedupe key 를 돌려준다
  worker.process_once() → True   (1건 배달)
  worker.process_once() → False  (더 없음)
  delivered 길이 = 1              ← ★2회 발행, 1회 배달

test_outbox_write_is_atomic_with_the_transition
  전이 도중 예외 → case_events 0행, outbox 0행 (둘 다 롤백)
```

## 통과한 것

| 요구 | 결과 |
|---|---|
| 중복 발행이 1회 배달로 수렴 | **통과** — `UNIQUE(topic, dedupe_key)` |
| 전이와 발행의 원자성 | **통과** — 같은 트랜잭션 |
| 재전달(replay) 시 side effect 1회 | **통과** — `SELECT … FOR UPDATE SKIP LOCKED` + status 전이 |
| ★timeout 은 `unknown` 으로 남고 재실행 안 함 | **통과** — DoD-11 참조 |

## ★왜 부분 통과였는가 (2026-08-16 시점)

v7 은 **"모든 consumer"** 라고 쓴다. 그런데 이 시스템의 consumer 는
**outbox worker 하나뿐이었다.** MCP·A2A·외부 소비자가 메시지를 받아 처리하는
경로가 없다. "consumer 가 하나뿐이라 전부 통과"는 "전부 검증했다"와
다르다 — consumer 가 늘어나면 각각에 같은 검사가 필요한데, 그걸 강제하는
장치가 없었다.

## ★2026-08-20 갱신 — 재측정 조건 충족

`tests/contract/test_consumer_idempotency_contract.py` 신규 — 임의의
consumer 구현체를 `consumer_contract_factories` 튜플에 등록하면 자동으로
3개 계약 테스트(중복 dedupe_key 1회 배달, 동시 race 방지, timeout→`unknown`
+자동재실행 없음)를 강제로 통과해야 한다. 지금은 `OutboxWorker` 하나만
등록돼 있고 3건 다 통과했다. 재사용 규칙 문서는
`docs/handoff/12_메시지_컨슈머_멱등성_계약.md`.

★**consumer 가 하나뿐이라는 사실 자체는 안 바뀌었다.** 바뀐 건 "다음
consumer 가 이 검사 없이 추가될 수 없다"는 것 — 이게 v7 요구("모든
consumer")를 미래형으로 충족시키는 구조다. 실제 두 번째 consumer(Fulfillment
&Logistics, Return&Refund 등)가 붙을 때 이 계약을 통과하는지가 진짜
증명이다.
