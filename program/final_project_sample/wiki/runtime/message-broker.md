---
type: concept
title: 메시지를 어떻게 내보내나
description: outbox 에 쌓고 worker 가 집어 간다. 실패를 실패로 남기고 자동 재실행하지 않는다
status: draft
tags: [architecture, state]
---

# 메시지를 어떻게 내보내나

**상태 전이와 메시지 발행이 한 트랜잭션 안에서 일어난다.** 그래서 "상태는 바뀌었는데 알림이 안 나갔다"가 생기지 않는다.

```
transition_case()  →  customer_cases UPDATE
                   →  case_events append
                   →  outbox insert          ← 여기까지 한 트랜잭션
                                             ↓
                   OutboxWorker 가 나중에 집어 간다
```

`[실측]` Controller 가 결과에 따라 outbox 메시지를 만들어 넘긴다. `application/controller.py:168-170`

## ★ 지금은 아무 데도 안 보낸다

`[실측]` `scripts/run_outbox_worker.py` 의 `publish()` 가 이렇다.

```python
def publish(message: dict) -> None:
    # Transport is intentionally an injected boundary in Phase 1.
    return None
```

**행을 저장하고 delivered 로 표시하는 것까지가 지금의 배달 의미다.**

> **`delivered` 가 "보냈다"를 뜻하지 않는다.** 실제 전송은 주입되는 경계다.

**이걸 모르고 지표를 읽으면 안 된다.** 배달률 100%는 "worker 가 집어서 표시했다"는 뜻이다.

## 중복을 어떻게 막나

`[실측]` `core/transition.py:81-90`

```sql
INSERT INTO outbox (tenant_id, topic, dedupe_key, payload_json)
VALUES (…) ON CONFLICT (tenant_id, topic, dedupe_key) DO NOTHING
```

**중복이면 새 행도 안 생기고 `TransitionResult.published` 에 message ID 도 안 붙는다.**

### `tenant_id` 가 키에 들어간 이유

`[실측]` 코드 주석이 적어 뒀다.

> 버그사냥 2026-08-17 — 예전엔 `tenant_id` 가 빠져 있어 **서로 다른 tenant 가 같은 `(topic, dedupe_key)` 를 쓰면 뒤의 것이 조용히 버려질 수 있었다.**

**조용히 버려지는 종류라 테스트로는 안 잡혔다.**

## ★ worker 가 죽으면 — 자동으로 다시 하지 않는다

`[실측]` `infrastructure/messaging/worker.py:27-45` 의 `_reclaim_stale_processing()`.

```
claim 커밋 후 · publisher() 완료 전에 워커가 죽는다
   ↓
그 행은 영영 'processing' 에 멈춘다 — 재시작한 워커는 'pending' 만 본다
```

**실제로 났던 버그다(2026-08-17).**

고친 방식이 중요하다.

> 실제로 배달됐는지 모르므로 **provider timeout 과 같은 근거로 `unknown` 으로 되돌린다** — **자동 재실행하지 않는다.**
>
> 사람이 `/ops/outbox` 에서 결론짓는다.

**모르는 것을 성공으로도 실패로도 치지 않는다.** → [../quality/verification.md](../quality/verification.md)

## tenant 별로 나눠 돌릴 수 있다

`[실측]` `OutboxWorker(tenant_id=...)`. 기본값 `None` 은 전체다.

**두 가지 이유로 필요했다.**

| 이유 | |
|---|---|
| **운영** | 전체를 집으면 한 tenant 의 적체가 다른 tenant 를 굶긴다 (head-of-line) |
| **테스트** | worker 가 **가장 오래된 pending 을 tenant 무관하게** 집어서 남의 행을 문다 |

`[실측]` 두 번째가 실제로 났다.

> `zz_foreign` tenant 의 pending 1행을 심자 `test_provider_timeout_stays_unknown_and_is_not_retried` 가 **즉시 실패**했다.

**쇼핑몰 복사본에서 먼저 드러났고 여기서 재현해 함께 고쳤다.**

## 빈 패키지

`[실측]` `core/case_runtime/messaging/` 에 `.py` 가 없다. **실제 구현은 `infrastructure/messaging/` 에 있다.**

## 관계

- [shared-state.md](shared-state.md) — 한 트랜잭션 안의 세 쓰기
- [case-lifecycle.md](case-lifecycle.md) — 상태 전이
- [../operations/run.md](../operations/run.md) — `/ops/outbox` 화면
