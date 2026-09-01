---
type: decision
title: Message Broker는 in-process queue
description: MVP는 in-process queue를 쓰고 MessageBusPort로 교체 가능하게 둔다. RabbitMQ는 기각
status: draft
tags: [architecture]
owners: [human:미배정]
---

# D-003 Message Broker는 in-process queue

## 맥락

Team 간 Task 전달과 Action 결과 전파에 메시지 전달이 필요하다. 어떤 브로커를 쓸지 정해야 했다.

## 결정

> **MVP는 in-process queue를 쓴다. `MessageBusPort`로 교체 가능하게 둔다.**

프로덕션 배포에서는 Redis Streams 등을 쓸 수 있다.

## 선택지와 이유

| 안 | 채택 | 이유 |
|---|---|---|
| **in-process queue** | ✅ MVP | 현재 규모에 운영 복잡도가 불필요 |
| Redis Streams | 프로덕션 후보 | 지금은 과함 |
| RabbitMQ | ❌ | **현재 규모에서 운영 복잡도가 불필요하다** |
| 브로커 없이 직접 호출 | ❌ | 경계가 사라져 나중에 못 바꾼다 |

## ★ 이 결정이 문서로 남아야 하는 이유

**코드만 보면 이렇게 읽힌다.**

> "왜 Redis 안 쓰고 in-memory로 만들었지? 개선해야겠다."

그리고 마음대로 Redis를 붙인다. 특히 에이전트가 그런다.

**문서가 있으면 "의도적인 MVP 결정이구나"를 이해한다.** 이게 결정 문서가 필요한 전형적인 경우다.

## 결과

- `MessageBusPort` 인터페이스를 둔다
- Top-Level LangGraph가 흐름을 결정하고 **Broker는 배달만 한다**
- Core 간 왕복은 `ExecuteAction` / `ActionResult`로 고정한다

## 주의점

**in-process queue는 함수 호출로 축소될 수 있다.** 그러면 브로커 경계가 사실상 사라지고, 나중에 진짜 브로커로 바꿀 때 문제가 드러난다.

그래서 **중복 전달과 retry를 일부러 만든다.** 전달 보장과 중복 처리는 consumer 규칙과 강제 테스트로 검증한다.

| 검증 | 방법 |
|---|---|
| 중복 전달 처리 | 같은 메시지 2회 전달 시 1회만 처리 |
| retry | 실패 후 재전달 |
| idempotency | 동일 요청 10회 = 1 side effect |

## 못 하게 되는 것

- 다중 인스턴스 배포를 MVP에서 못 한다
- 프로세스가 죽으면 큐에 있던 메시지가 사라진다 (outbox가 이를 보완)

## 관계

- [`message-broker.md`](../../final_project_cs/wiki/runtime/message-broker.md) — 구현
- [`outbox.md`](../../final_project_cs/wiki/actions/outbox.md) — 발행 보장
- [`idempotency.md`](../../final_project_cs/wiki/actions/idempotency.md) — 중복 실행 방지
