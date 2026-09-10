---
type: runbook
title: unknown 상태 대응 절차
description: 돈이 나갔는지 모르는 상태를 사람이 확인하고 닫는 절차. 추정하지 않는다
status: draft
tags: [architecture, security]
owners: [human:미배정]
domain: neutral
---

# unknown 상태 대응 절차

`[실측]` `wiki/records/manuals/운영_unknown상태_대응절차.md`에서 이관.

**사고가 났을 때 따라가는 문서다.** 처음 읽는 문서가 아니다.

## 적용 범위

**`unknown`은 Case 상태가 아니다.** `customer_cases.status` enum에 없다.

**outbox·action 의 상태다.** provider 호출이 timeout 됐을 때 남는다.

## 규칙 셋

```
① 성공·실패를 추정하지 않는다
② 자동 재실행하지 않는다
③ 사람이 확인해서 닫는다
```

**돈이 나갔는지 모르는 상태다.** 운영 UI에서 **가장 센 위험색**으로 표시한다.

→ [../actions/idempotency.md](../actions/idempotency.md)의 `INV-CS-ACT-003`

## ① 발견

| 경로 | 무엇 |
|---|---|
| SQL | **tenant 한정**으로 outbox 조회 |
| `/ops/outbox` | 화면 |
| Case 화면 | 연결된 Case |
| trace 화면 | 실행 경로 |

**tenant 조건 없는 조회는 그 자체가 보안 결함이다.** → [../data/tenancy.md](../data/tenancy.md)

## ② 사람이 확인할 것

```
provider 업무 식별자
Case 상태
이벤트 이력
★ provider 공식 콘솔의 실제 결과
```

**마지막이 판정 근거다.** 우리 DB만 봐서는 알 수 없다.

## ③ 결과별 조치

### 완료로 확인된 경우

`EventType.VALID_CALLBACK`을 `transition_case()`로 호출한다.

```
필수 payload : provider_ref
전이         : waiting_external → resuming
이후         : EventType.RESUMED 가 resuming → running
```

**사람이 확인한 근거를 `state_patch`에 남긴다.**

### 미완료로 확인된 경우

`EventType.WAIT_EXPIRED`

### 확인 불가

**유지하고 escalation 한다.** 억지로 닫지 않는다.

## ★ 운영자용 API 가 없다

`[실측]` **저장소에 Case 전이를 수행하는 운영자용 HTTP API나 CLI가 없다.**

수동 실행은 실제 코드의 함수·이벤트·payload 계약을 직접 쓴다.

```python
from app.domain.events import EventType
from app.infrastructure.db.session import get_connection
from app.core.transition import transition_case
```

**실행 전에 Case 의 최신 version 을 읽는다.** CAS 라 version 이 안 맞으면 충돌한다.

unknown outbox 의 확인 결과는 `/ops/outbox` 화면과 `/v1/outbox/{message_id}/resolve` API 로 기록한다.

`[미확보]` **운영자용 전이 API 가 없는 것은 개선 대상이다.** 지금은 사람이 Python 을 실행해야 한다.

## 금지

| 하지 않는다 | 왜 |
|---|---|
| **Case·event·outbox 를 직접 수정** | `case_events` 는 append-only. projection 이 어긋난다 |
| **timeout 뒤 worker 재실행** | **이중 실행이 날 수 있다** — 그래서 막는다. `[실측 2026-09-10]` 지금 worker 는 **`status='pending'` 만 집는다**(`messaging/worker.py:42`) — `unknown` 은 자동으로 다시 집히지 않는다. **이 규칙이 코드로 지켜지고 있다는 뜻이다.** 누가 `unknown` 을 손으로 `pending` 으로 되돌리면 그때 이중 실행이 난다 |

**두 번째가 이 문서의 존재 이유다.** 재실행하고 싶은 충동을 규칙으로 막는다.

## 근거 파일

```
app/infrastructure/messaging/worker.py
app/infrastructure/db/migrations/005_outbox_resolution.sql
app/domain/events.py
app/core/transition.py
app/presentation/api/  ·  app/presentation/ui/
```

## 관계

- [troubleshooting.md](troubleshooting.md) — 다른 증상들
- [../actions/idempotency.md](../actions/idempotency.md) — timeout 을 왜 재시도 안 하나
- [../actions/outbox.md](../actions/outbox.md) — outbox 구조
- [../runtime/case-lifecycle.md](../runtime/case-lifecycle.md) — 전이 규칙
