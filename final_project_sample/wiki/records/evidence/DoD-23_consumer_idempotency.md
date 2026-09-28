# DoD-23 — 모든 consumer 가 at-least-once 하에서 idempotent 하다

- v7 §27 항목 23 / 검증 방법: 동일 message 를 2회 전달하는 duplicate/replay integration test
- 실행: 2026-08-16
- 판정: **부분 통과** — 발행측은 증명됐고, consumer 측은 대상이 하나뿐이다

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

## ★왜 부분 통과인가

v7 은 **"모든 consumer"** 라고 쓴다. 그런데 이 시스템의 consumer 는 지금
**outbox worker 하나뿐이다.** MCP·A2A·외부 소비자가 메시지를 받아 처리하는 경로가 없다.

★**"consumer 가 하나뿐이라 전부 통과" 는 "전부 검증했다" 와 다르다.**
consumer 가 늘어나면 각각에 같은 검사가 필요하고, 지금은 그 검사를 강제하는 장치가 없다.

또한 REST 생성 경로의 idempotency(동일 요청 10회 → 1행)는 DoD-11 에서 따로 증명했다.
이 항목은 **메시지 소비** 쪽이다.

## 재측정 조건

1. consumer 가 늘어날 때 각각에 duplicate 전달 테스트를 붙인다
2. 새 consumer 가 그 테스트 없이 추가되지 못하게 하는 게이트를 만든다
   (★검사하지 않는 규칙은 지켜지지 않는다)

## 게이트 추가

consumer 집합을 소스 스캔하고 명시된 검증 목록과 정확히 비교하는 게이트를 추가했다:
`tests/architecture/test_consumer_idempotency_gate.py`

재현 명령:

```powershell
python -m pytest tests/architecture/test_consumer_idempotency_gate.py -v
```

실제 출력:

```
============================= test session starts =============================
collecting ... collected 1 item
tests/architecture/test_consumer_idempotency_gate.py::test_every_messaging_consumer_is_explicitly_proven_idempotent PASSED [100%]
======================== 1 passed, 1 warning in 0.03s =========================
```

판정은 consumer가 하나뿐이라는 사실이 바뀌지 않았으므로 여전히 **부분 통과**다. 게이트의 실제 검출 여부는 임시 `DummyConsumer`를 추가하고 목록을 갱신하지 않은 상태에서 실행해 `1 failed` 및 `undeclared=['DummyConsumer']`가 출력되는 것으로 확인했다.
