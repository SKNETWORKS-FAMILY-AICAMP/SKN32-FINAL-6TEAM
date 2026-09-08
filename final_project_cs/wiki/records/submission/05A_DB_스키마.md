# DB 스키마

## 테이블 구성

v5 §8 핵심 테이블은 14개다.

`tenants`, `customers`, `customer_cases`, `case_events`, `agent_runs`, `team_tasks`, `action_requests`, `action_approvals`, `outbox`, `llm_calls`, `prompts`, `feedback_analytics_reports`, `knowledge_documents`, `knowledge_chunks`

시나리오용 mock 테이블은 4개다.

`subscriptions`, `payments`, `entitlements`, `incidents`

현재 DB seed 실측은 `tenants=1`, `demo_customers=10`, `knowledge_documents=25`, `knowledge_chunks=300`이다. mock 테이블은 실제 provider가 아니라 seed용이다.

## 정합성을 지키는 UNIQUE 3종

| 제약 | 막는 문제 |
|---|---|
| `case_events(case_id, aggregate_version)` | 한 Case의 같은 aggregate version에 이벤트를 두 번 기록하는 것 |
| `outbox(topic, dedupe_key)` | 같은 메시지를 outbox에 중복 적재·전달하는 것 |
| `action_requests(tenant_id, idempotency_key)` | 같은 tenant의 동일 요청이 side effect를 여러 번 만드는 것 |

이 제약들은 애플리케이션 단언만이 아니라 DB가 직접 집행하는 정합성 경계다.

## 근거

- `wiki/records/reports/2026-08-12_S-DB_스키마_마이그레이션_리포트.md`
- `wiki/records/reports/2026-08-12_1630_P0-P1_및_Codex1차_검수_리포트.md`
- `wiki/records/evidence/DoD-03_동시성_appendonly_replay.md`
- `wiki/records/evidence/DoD-12_outbox_원자성_replay.md`
- `wiki/records/evidence/DoD-11_action_idempotency_승인.md`
