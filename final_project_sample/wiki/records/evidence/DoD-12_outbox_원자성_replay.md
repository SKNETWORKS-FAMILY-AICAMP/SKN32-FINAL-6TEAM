# DoD-12 — outbox insert 가 projection transaction 과 원자적이고 worker replay 가능

- v5 §20 항목 12 / 검증 방법: failure injection test
- 실행: 2026-08-12 22:50 · 커밋 `cbb75e6`
- 판정: **통과**

## 재현

```powershell
python -m pytest tests/integration/controller -v
python -m scripts.run_outbox_worker --once
```

## 근거 1 — ★원자성 (failure injection)

`test_transition_exception_rolls_back_event_and_outbox`

transition 도중 예외를 주입해 롤백되면 **`case_events` 와 `outbox` 둘 다 행이 없다.**
하나만 남으면 실패로 판정한다 — 그게 원자성이 깨진 상태다.

구조적 근거: `app/core/transition.py:transition_case()` 가 한 함수 안에서
① projection UPDATE(version 가드) ② `case_events` append ③ `outbox` insert 를 수행하고,
**commit 하지 않는다.** 호출자가 `with conn.transaction():` 으로 경계를 잡으므로
셋 중 하나라도 실패하면 전부 롤백된다 (v5 §6-4).

## 근거 2 — 중복 전달 차단

`test_outbox_duplicate_is_delivered_once` / `tests/integration/db/...::test_outbox_dedupe`

같은 `(topic, dedupe_key)` 2회 발행 → **행 1개**, worker **1회만** 전달.

실체는 DDL 제약 `outbox UNIQUE(topic, dedupe_key)` 이고 DB 직접 조회로 실재를 확인했다
(`outbox_topic_dedupe_key_key`). `transition_case` 는 `ON CONFLICT DO NOTHING` 으로
insert 하고 **실제 insert 된 message_id 만** `published` 에 담는다 — 중복이면 빈 리스트다.

> 2026-08-17: 버그사냥 01(당시 tenant_id 미포함 확인)·08(실제 반영)에서
> `UNIQUE(tenant_id, topic, dedupe_key)` 로 넓혔다 —
> `migrations/005_outbox_dedupe_key_tenant_scoped.sql`, 제약명은
> `outbox_tenant_topic_dedupe_key_key` 로 바뀌었다. 서로 다른 tenant 가
> 같은 `(topic, dedupe_key)` 를 써도 서로의 메시지를 지우지 않는다. 이
> 근거의 판정(중복 전달 차단)은 안 바뀐다 — 같은 tenant 안에서의 dedupe 는
> 그대로다. 상세: `wiki/records/reports/debugs/2026-08-17_버그사냥_08_미해결3건_처리.md`.

## 근거 3 — worker claim 과 dead-letter

- claim: `SELECT ... FOR UPDATE SKIP LOCKED` (정적 확인 1곳)
- 실패 row 는 **dead-letter 상태로 남긴다** (삭제하지 않는다)
- `python -m scripts.run_outbox_worker --once` 실행 성공

## 실제 출력

```
python -m pytest tests -q
107 passed in 25.14s      (skipped 0, failed 0)

tenants=1
```

## 한계 · 미검증

| 항목 | 상태 |
|---|---|
| transaction 원자성 (예외 주입) | 통과 |
| 중복 dedupe 차단 | 통과 |
| worker 1회 실행 | 통과 |
| ★**프로세스 강제 종료 후 재기동 replay** | **미검증** — 테스트는 예외 주입으로 롤백을 만든다. 실제 프로세스 kill 후 재시작 시나리오는 돌리지 않았다 |
| provider timeout → `unknown` 유지 | **미검증** — 코드에 경로는 있으나 종단 테스트 없음 |
| `RedisStreamsAdapter` | **구현하지 않음** (v5 §3 Phase 2). Port 만 유지 — 의도된 상태다 |
