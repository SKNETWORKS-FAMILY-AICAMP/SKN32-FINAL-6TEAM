---
type: concept
title: Outbox
description: 외부 발행을 보장하는 경계. tenant별 중복 제거와 해소 상태를 갖는다
status: draft
tags: [architecture, contract]
owners: [human:미배정]
---

# Outbox

`app/infrastructure/messaging/` · `outbox` 테이블

## 왜 필요한가

**DB 커밋과 외부 발행을 한 트랜잭션에 묶을 수 없다.**

```
❌ DB 커밋 → (프로세스 죽음) → 발행 안 됨
❌ 발행 → (DB 롤백) → 발행만 됨
```

그래서 **발행할 것을 DB에 먼저 쓴다.** 같은 트랜잭션이므로 원자적이다. worker가 나중에 집어서 실제로 보낸다.

## 테이블

`[실측]` `001_schema.sql` + `003` + `005`

```sql
outbox (
  message_id, tenant_id, topic, dedupe_key, payload_json,
  status DEFAULT 'pending', attempts DEFAULT 0,
  available_at, locked_at, last_error,
  UNIQUE (topic, dedupe_key)
)
```

| 칸 | 무엇 |
|---|---|
| `dedupe_key` | 중복 발행 방지 |
| `status` | pending / 처리됨 |
| `attempts` | 재시도 횟수 |
| `available_at` | 언제부터 집어도 되는가 (백오프) |
| `locked_at` | worker가 집었음 |
| `last_error` | 왜 실패했는가 |

## tenant 격리

`003_outbox_tenant_scoped_dedupe.sql`이 중복 제거 범위를 tenant로 한정한다.

**다른 테넌트의 같은 `dedupe_key`가 서로를 막으면 안 된다.**

```
tests/integration/messaging/test_outbox_tenant_guard.py
```

## 해소

`005_outbox_resolution.sql`. 발행이 끝난 항목을 어떻게 정리하는가.

```
tests/integration/api/test_outbox_resolution.py
```

## MockProviderPublisher

`app/infrastructure/messaging/mock_payment_publisher.py`

**결제 연동이 아니다.** outbox worker가 publisher 경계를 연습하기 위한 테스트 더블이고 네트워크 I/O가 없다.

`[실측]` **파일명과 클래스명이 어긋나 있다.** 클래스는 `MockProviderPublisher`로 도메인 중립화됐는데 파일명이 안 따라왔다.

파일명만 보고 "결제 연동이 있다"고 오해할 수 있다. 정리 대상이다. → [../../../wiki/decisions/D-001-payment-ownership.md](../../../wiki/decisions/D-001-payment-ownership.md) 조치 4

## in-process 전제

MVP는 in-process queue다. → [../../../wiki/decisions/D-003-message-broker.md](../../../wiki/decisions/D-003-message-broker.md)

**outbox가 그 결정의 보완책이다.** 프로세스가 죽어도 발행할 것이 DB에 남아 있다.

## 불변식

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-ACT-001` | 동일 dedupe key는 side effect가 1회다 | automated | `tests/contract/test_consumer_idempotency_contract.py::test_duplicate_dedupe_key_has_one_side_effect` |
| `INV-CS-ACT-002` | 동시 claim도 side effect가 1회다 | automated | `tests/contract/test_consumer_idempotency_contract.py::test_concurrent_claims_have_one_side_effect` |
| `INV-CS-ACT-003` | timeout은 unknown이며 자동 재시도하지 않는다 | automated | `tests/contract/test_consumer_idempotency_contract.py::test_timeout_is_unknown_and_not_automatically_retried` |

**`attempts`가 있다고 무한 재시도하지 않는다.** provider timeout은 `unknown`으로 남기고 사람이 판단한다.

## 관계

- [idempotency.md](idempotency.md) — 중복 방지 계약
- [tool-gateway.md](tool-gateway.md) — 실행 지점
- [../runtime/message-broker.md](../runtime/message-broker.md) — 내부 배달
- [../data/schema.md](../data/schema.md) — 테이블 정의
