# 2026-08-12 S-CTRL tests

- `tests/integration/controller/`에 8개 통합 테스트를 추가했다.
- fake Team, fake policy retriever, fake context broker를 사용해 신규 Controller 테스트의 LLM·임베딩 외부 호출을 제거했다.
- replay 동치성, transition/outbox 원자성, outbox dedupe/worker 1회 전달, resume token hash·일회성·TTL, loop guard, optimistic concurrency를 검증했다.
- 실행 결과: Controller `1 failed, 7 passed, skipped 0`; 전체 `4 failed, 103 passed, skipped 0`; `tenants=1`.
- 실패 원인: 승인 후 `resuming`에서 `completed`를 직접 적용하는 Controller 전이 결함 1건. 기존 RAG 테스트의 OpenAI embedding 네트워크 의존 실패 3건.
- 제품 코드와 기존 테스트는 수정하지 않았다.
