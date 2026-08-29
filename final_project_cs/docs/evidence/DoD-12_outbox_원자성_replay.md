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
| 중복 dedupe 차단 | 통과 (★2026-08-24 제약 컬럼 변경, 아래 참조) |
| worker 1회 실행 | 통과 |
| ★**프로세스 강제 종료 후 재기동 replay** | 부분 해소(★2026-08-24, 아래 참조). 실제 프로세스 kill 시나리오 자체는 여전히 안 돌렸다 |
| provider timeout → `unknown` 유지 | **미검증** — 코드에 경로는 있으나 종단 테스트 없음 |
| `RedisStreamsAdapter` | **구현하지 않음** (v5 §3 Phase 2). Port 만 유지 — 의도된 상태다 |

## ★2026-08-24 갱신 — dedupe 제약에 tenant 경계가 없던 결함 + stale lock 회수 + 사람 해결 워크플로

sample 대조에서 두 가지가 발견돼 이식됐다:

1. **dedupe 제약의 tenant 경계 소실**(제일 중요). 위 근거 2에 적힌
   `outbox UNIQUE(topic, dedupe_key)`는 tenant_id 를 포함하지 않았다 —
   `CLAUDE.md` §1 "모든 query 에 tenant_id 조건을 적용한다" 원칙 위반으로,
   **다른 tenant 가 같은 topic+dedupe_key 를 쓰면 서로의 outbox 행에
   충돌할 수 있었다.** `003_outbox_tenant_scoped_dedupe.sql`로 제약을
   `UNIQUE(tenant_id, topic, dedupe_key)`로 바꾸고, `outbox.py`·
   `transition.py`의 `ON CONFLICT`절도 세 컬럼 기준으로 고쳤다. 서로 다른
   tenant 가 같은 topic+dedupe_key 로 publish 해도 **둘 다 독립적으로
   성공**하는지 `tests/security/`에 재현 테스트를 추가해 확인했다.
   상세: `docs/reports/2026-08-24_S-BASEMENT-03-TENANT-DEDUPE_리포트.md`
2. **stale lock 회수**. `worker.py`가 claim만 하고 죽으면 그 행이 영원히
   `processing`에 갇히던 갭을 메웠다 — 일정 시간 이상 `processing`으로
   멈춘 행을 `unknown`(사람이 볼 수 있는 상태)으로 되돌린다. 자동
   재실행은 여전히 하지 않는다(§원칙 그대로).
3. **unknown 사람 해결 워크플로**. `resolved_at`/`resolved_by`/
   `resolution`/`resolution_note` 컬럼(`005_outbox_resolution.sql`),
   `POST /v1/outbox/{id}/resolve`(기록만 하고 outbox 를 자동 재처리하지
   않음), `/ops/outbox` UI 화면이 새로 생겼다 — 지금까지 "위 갭이
   실행 경로 전체가 없다"고 정직하게 남겨뒀던 것을 실제로 메웠다.
   상세: `docs/reports/2026-08-24_S-BASEMENT-05-OUTBOX-RESOLUTION_리포트.md`,
   `docs/manuals/운영_unknown상태_대응절차.md`
