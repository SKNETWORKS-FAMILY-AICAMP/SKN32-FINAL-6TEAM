# DoD-23 consumer idempotency gate

`tests/architecture/test_consumer_idempotency_gate.py`를 추가했다. `app/infrastructure/messaging/**/*.py`의 `Worker`/`Consumer` 접미사 클래스명을 정규식으로 찾아 `PROVEN_IDEMPOTENT_CONSUMERS`와 양방향으로 비교한다.

always-true가 아님을 확인하기 위해 임시 `DummyConsumer`를 추가한 뒤 게이트를 실행했다. 실제 실패 출력에는 `discovered=['DummyConsumer', 'OutboxWorker']`, `undeclared=['DummyConsumer']`가 포함됐고 `1 failed`로 종료됐다. 임시 파일은 확인 후 제거했다.

게이트 정상 실행:

```text
============================= test session starts =============================
collecting ... collected 1 item
tests/architecture/test_consumer_idempotency_gate.py::test_every_messaging_consumer_is_explicitly_proven_idempotent PASSED [100%]
======================== 1 passed, 1 warning in 0.03s =========================
```

전체 스위트 실행 원문:

```text
........................................................................ [ 22%]
........................................................................ [ 44%]
........................................................................ [ 67%]
....................FFF................................................. [ 89%]
..................................                                       [100%]
3 failed, 319 passed, 1 deselected, 2 warnings in 22.73s
```

실패한 3건은 RAG 통합 테스트의 OpenAI embeddings 호출이며, 샌드박스 네트워크 차단 `WinError 10013`으로 실패했다. 게이트 관련 테스트는 통과했다.
