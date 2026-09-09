---
type: concept
title: Outbox
description: 외부 발행을 보장하는 경계. tenant별 중복 제거와 해소 상태를 갖는다
status: draft
tags: [architecture, contract]
owners: [human:미배정]
domain: neutral
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
  UNIQUE (tenant_id, topic, dedupe_key)
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

`[실측]` **이 제약, 원래는 `tenant_id`가 없었다.** [DoD-12](../records/evidence/DoD-12_outbox_원자성_replay.md). `UNIQUE(topic, dedupe_key)`뿐이었던 시절엔 **다른 tenant가 같은 topic+dedupe_key로 발행하면 서로의 outbox 행에 충돌할 수 있었다** — [CLAUDE.md](../../CLAUDE.md) "모든 query에 tenant_id 조건을 적용한다" 원칙 위반이다. `final_project_sample`과 대조하다가(2026-08-24) 발견해 지금의 세 컬럼 제약으로 옮겼다.

**단일 저장소 안 대조가 아니라 다른 구현체(`final_project_sample`)와 비교해서 찾은 결함이다.** 같은 계약을 두 번 구현하면 한쪽만 가진 결함이 드러난다.

## 해소

`005_outbox_resolution.sql`. 발행이 끝난 항목을 어떻게 정리하는가.

```
tests/integration/api/test_outbox_resolution.py
```

`[실측]` **`unknown` 행을 사람이 정리하는 화면·API가 있다** ([DoD-11](../records/evidence/DoD-11_action_idempotency_승인.md) 2026-08-24 추가).

```
POST /v1/outbox/{id}/resolve     기록만 한다. 자동 재처리 안 함
/ops/outbox                      운영 UI
worker.py                        stale `processing` 행을 unknown 으로 회수
```

**여기서도 자동 재실행은 하지 않는다.** `unknown`을 해소한다는 건 "사람이 봤고 판단했다"는 기록이지, 시스템이 대신 재시도하는 게 아니다. → `wiki/records/manuals/운영_unknown상태_대응절차.md`

## ★ 여기서 증명한 것은 outbox 발행까지다 — provider 실행 경로는 없다

`[실측]` [DoD-11](../records/evidence/DoD-11_action_idempotency_승인.md)이 스스로 밝힌 경계.

**`app/` 전체에서 `action_requests.status`를 `executing`/`succeeded`/`failed`/`unknown`으로 바꾸는 코드가 한 곳도 없다.** enum에 값만 있다.

> **이것은 결함이 아니라 설계다.** Team은 side effect를 실행하지 않는다([CLAUDE.md §0.2](../../CLAUDE.md)). 승인 이후 실제 결제사 호출은 MVP 범위 밖이다.

**그래서 이 문서·[idempotency.md](idempotency.md)가 증명하는 "timeout → unknown, 자동 재시도 안 함"은 outbox/메시지 발행 경로에 대한 증명이다.** 실제 결제 provider 호출은 아직 겪어 본 적이 없다 — 그 경로가 붙는 시점에 같은 검사를 다시 해야 한다. → [../../../wiki/decisions/D-001-payment-ownership.md](../../../wiki/decisions/D-001-payment-ownership.md)

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
- [../data/schema/index.md](../data/schema/index.md) — 테이블 정의
