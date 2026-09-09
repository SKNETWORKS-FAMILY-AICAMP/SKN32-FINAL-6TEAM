---
type: concept
title: Message Broker
description: Task와 결과를 배달한다. 배달만 하고 흐름은 결정하지 않는다
status: draft
tags: [architecture]
owners: [human:미배정]
domain: neutral
---

# Message Broker

> `[실측 2026-09-01]` **`app/core/case_runtime/`·`access_action/` 은 `__init__.py` 만 남은 빈 패키지다.**
> 2026-08-13 에 중첩 구조로 갔다가 **평면 구조로 되돌아왔다.** 정본은 `app/core/*.py` 다.
> 구조가 또 바뀔 수 있으므로 **작업 전에 실제 경로를 확인한다.**

`app/infrastructure/messaging/` · `app/infrastructure/messaging/ports.py`

## 책임

**배달만 한다.**

```
Top-Level LangGraph → 흐름을 결정
Message Broker      → 배달
```

**둘을 섞으면 안 된다.** Broker가 흐름을 결정하기 시작하면 실행 경로가 두 곳에 생긴다.

## MVP는 in-process queue

결정 근거는 [중앙 허브 D-003](../../../wiki/decisions/D-003-message-broker.md).

```
in-process queue   MVP
Redis Streams      프로덕션 후보
RabbitMQ           기각 — 현재 규모에 운영 복잡도가 불필요
```

`MessageBusPort`로 교체 가능하게 둔다.

## ★ in-process는 함수 호출로 축소될 수 있다

이게 이 설계의 함정이다.

**큐가 프로세스 안에 있으면 그냥 함수를 부르는 것과 같아진다.** 그러면 브로커 경계가 사실상 사라지고, 나중에 진짜 브로커로 바꿀 때 문제가 한꺼번에 드러난다.

그래서 **중복 전달과 retry를 일부러 만든다.**

| 만드는 것 | 왜 |
|---|---|
| 중복 전달 | 진짜 브로커는 at-least-once다 |
| retry | 실패가 정상 상황이다 |
| dead-letter | 계속 실패하는 걸 격리한다 |

**"안 일어날 일"을 미리 일어나게 해서 대응 코드를 검증한다.**

## Core 간 왕복 계약

```
ExecuteAction  →  ActionResult
```

이 두 메시지로 고정한다. 늘리면 경계가 흐려진다.

## outbox와의 관계

| | Message Broker | Outbox |
|---|---|---|
| 무엇 | **내부** 배달 | **외부** 발행 |
| 보장 | 중복 전달 처리 | DB 트랜잭션과 원자성 |
| 죽으면 | 큐 내용 소실 | **DB에 남아 있음** |

**outbox가 in-process의 약점을 보완한다.** 프로세스가 죽어도 발행할 것은 DB에 있다.

→ [../actions/outbox.md](../actions/outbox.md)

## 불변식

consumer 계약이 세 가지를 요구한다. **새 consumer를 추가하면 자동 적용된다.**

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-ACT-001` | 동일 dedupe key는 side effect가 1회다 | automated | `tests/contract/test_consumer_idempotency_contract.py::test_duplicate_dedupe_key_has_one_side_effect` |
| `INV-CS-ACT-002` | 동시 claim도 side effect가 1회다 | automated | `tests/contract/test_consumer_idempotency_contract.py::test_concurrent_claims_have_one_side_effect` |
| `INV-CS-ACT-003` | timeout은 unknown이며 자동 재시도하지 않는다 | automated | `tests/contract/test_consumer_idempotency_contract.py::test_timeout_is_unknown_and_not_automatically_retried` |

→ [../actions/idempotency.md](../actions/idempotency.md)

## tenant 격리

```
tests/integration/messaging/test_outbox_tenant_guard.py
```

**다른 테넌트의 같은 키가 서로를 막으면 안 된다.**

## 구현

```text
app/infrastructure/messaging/
├─ ports.py                            MessageBusPort
├─ outbox.py                           외부 발행
├─ worker.py                           집어서 보내는 쪽
└─ mock_payment_publisher.py           테스트 더블 (파일명 정리 대상)
```

## ★ [2026-09-03] 새 consumer 를 추가할 때 지킬 것

`[실측]` `wiki/records/handoff/12_메시지_컨슈머_멱등성_계약.md` 에서 이관.

> **구현을 완료하기 전에** `tests/contract/test_consumer_idempotency_contract.py` 의 계약 테스트를 **통과시켜야 한다.**

**순서가 규칙이다.** 만들고 나서 테스트를 맞추는 게 아니다.

### 계약이 강제하는 셋

`MessageBrokerPort` 의 `topic`·`dedupe_key` 경계 기준.

| # | 강제 |
|---|---|
| 1 | 같은 `dedupe_key` 를 **두 번 발행·처리해도 side effect 는 한 번만** |
| 2 | 같은 메시지를 **동시에 claim 해도 한 번만** |
| 3 | **timeout·connection 불확실성은 `unknown` 으로 남고 worker 가 자동 재실행하지 않는다** |

**3번이 1·2번과 다른 종류다.** 1·2는 "두 번 하지 마라"이고 3은 **"모르면 결정하지 마라"**다.

### 등록 방식

```
tests 의 consumer_contract_factories 에 자기 adapter 를 등록한다
adapter 는 publish · process_once · status 를 제공한다
```

`[실측]` **금지 사항이 명확하다.**

> 실제 consumer 구현이나 **업무 DB 를 계약 테스트 안에 복제해서는 안 된다.**

**복제하면 테스트가 구현을 따라가서 아무것도 안 막는다.**

### 빠뜨리면 잡히나

`[실측]` sample 쪽에는 **증거 없는 consumer 를 세는 게이트**가 있다. → [`INV-SAMPLE-RUN-001`](../../../final_project_sample/wiki/quality/invariants.md)

`[미확보]` **cs 에도 같은 게이트가 있는지 확인 안 했다.** 없으면 새 consumer 를 등록 안 하고 넘어갈 수 있다.

## 관계

- [agentic-controller.md](agentic-controller.md) — 흐름을 결정하는 쪽
- [../actions/outbox.md](../actions/outbox.md) — 외부 발행
- [../actions/idempotency.md](../actions/idempotency.md) — 중복 방지 계약
- [../../../wiki/decisions/D-003-message-broker.md](../../../wiki/decisions/D-003-message-broker.md) — 왜 in-process인가
