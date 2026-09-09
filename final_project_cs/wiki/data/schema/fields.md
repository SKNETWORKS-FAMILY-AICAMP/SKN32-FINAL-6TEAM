---
type: contract
title: 스키마 필드 명세
description: 테이블별 컬럼·타입·제약·인덱스 전체. handoff 계약 원문에서 옮겼다
status: draft
tags: [data, contract]
domain: neutral
---

# 스키마 필드 명세

`[실측]` `wiki/records/handoff/` 계약 원문에서 절 단위로 옮겼다. **개념 설명은 [index.md](index.md) 에 있다.**

`[실측]` `wiki/records/handoff/` 계약 문서와 절 단위로 대조해 **빠져 있던 필드·제약·숫자**를 채웠다. 대조 결과는 [반영률 실측](../../../../wiki/governance/migration-scope/coverage.md).

## DB 실행 계약

`[실측]`

| 항목 | 값 |
|---|---|
| 서버 | PostgreSQL `16.14`, `127.0.0.1:5433` |
| 기동 방식 | conda env `pgv`의 `postgres.exe`; Windows 서비스 아님 |
| `psql` | `%USERPROFILE%\anaconda3\envs\pgv\Library\bin\psql.exe`; PATH에 없음 |
| DB 이름 | `acop`; 기존 `insurance_*`·`mall_vec` DB 변경 금지 |
| extension | `vector 0.8.3`, `pgcrypto 1.3`; 별도 `CREATE` 필요 |
| Docker | 실행 환경에 없음; `docker/compose.yml`은 재현 문서용이며 실행 경로에서 제외 |

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
```

근거: `wiki/records/handoff/02_DB_스키마.md:7-27`

## DB Enum

`[실측]`

| 타입 | 허용값 |
|---|---|
| `case_status` | `new`, `classifying`, `routing`, `running`, `waiting_input`, `waiting_approval`, `waiting_external`, `resuming`, `resolved`, `escalated`, `failed`, `cancelled` |
| `action_status` | `proposed`, `pending_approval`, `approved`, `rejected`, `executing`, `succeeded`, `failed`, `unknown`, `cancelled` |

근거: `wiki/records/handoff/02_DB_스키마.md:29-35`

## Core 테이블 컬럼 계약

`[실측]`

| 테이블 | 컬럼 | 타입 | NULL·키·기본값 |
|---|---|---|---|
| `tenants` | `tenant_id` | `text` | `PRIMARY KEY` |
| `tenants` | `name` | `text` | `NOT NULL` |
| `customers` | `customer_id` | `uuid` | `PRIMARY KEY DEFAULT gen_random_uuid()` |
| `customers` | `tenant_id` | `text` | `NOT NULL REFERENCES tenants` |
| `customers` | `external_id` | `text` | `NOT NULL` |
| `customers` | `email_hash` | `text` | NULL 허용 |
| `customers` | `created_at` | `timestamptz` | `NOT NULL DEFAULT now()` |
| `customer_cases` | `case_id` | `uuid` | `PRIMARY KEY DEFAULT gen_random_uuid()` |
| `customer_cases` | `tenant_id` | `text` | `NOT NULL` |
| `customer_cases` | `customer_id` | `uuid` | `NOT NULL REFERENCES customers` |
| `customer_cases` | `status` | `case_status` | `NOT NULL` |
| `customer_cases` | `subject` | `text` | `NOT NULL` |
| `customer_cases` | `state_json` | `jsonb` | `NOT NULL DEFAULT '{}'` |
| `customer_cases` | `intent` | `text` | NULL 허용 |
| `customer_cases` | `issue_code` | `text` | NULL 허용 |
| `customer_cases` | `sentiment` | `text` | NULL 허용 |
| `customer_cases` | `owner_team_id` | `text` | NULL 허용 |
| `customer_cases` | `version` | `int` | `NOT NULL DEFAULT 0` |
| `customer_cases` | `created_at` | `timestamptz` | `NOT NULL DEFAULT now()` |
| `customer_cases` | `updated_at` | `timestamptz` | `NOT NULL DEFAULT now()` |
| `case_events` | `event_id` | `uuid` | `PRIMARY KEY DEFAULT gen_random_uuid()` |
| `case_events` | `tenant_id` | `text` | `NOT NULL` |
| `case_events` | `case_id` | `uuid` | `NOT NULL REFERENCES customer_cases` |
| `case_events` | `aggregate_version` | `int` | `NOT NULL` |
| `case_events` | `event_type` | `text` | `NOT NULL` |
| `case_events` | `payload_json` | `jsonb` | `NOT NULL` |
| `case_events` | `actor_type` | `text` | `NOT NULL` |
| `case_events` | `actor_id` | `text` | NULL 허용 |
| `case_events` | `created_at` | `timestamptz` | `NOT NULL DEFAULT now()` |
| `agent_runs` | `run_id` | `uuid` | `PRIMARY KEY DEFAULT gen_random_uuid()` |
| `agent_runs` | `tenant_id` | `text` | `NOT NULL` |
| `agent_runs` | `case_id` | `uuid` | `NOT NULL REFERENCES customer_cases` |
| `agent_runs` | `graph_revision` | `text` | `NOT NULL` |
| `agent_runs` | `status` | `text` | `NOT NULL` |
| `agent_runs` | `attempt` | `int` | `NOT NULL DEFAULT 0` |
| `agent_runs` | `started_at` | `timestamptz` | NULL 허용 |
| `agent_runs` | `finished_at` | `timestamptz` | NULL 허용 |
| `team_tasks` | `task_id` | `uuid` | `PRIMARY KEY DEFAULT gen_random_uuid()` |
| `team_tasks` | `run_id` | `uuid` | `NOT NULL REFERENCES agent_runs` |
| `team_tasks` | `team_id` | `text` | `NOT NULL` |
| `team_tasks` | `contract_version` | `text` | `NOT NULL` |
| `team_tasks` | `payload_json` | `jsonb` | `NOT NULL` |
| `team_tasks` | `status` | `text` | `NOT NULL` |
| `team_tasks` | `created_at` | `timestamptz` | `NOT NULL DEFAULT now()` |
| `action_requests` | `action_id` | `uuid` | `PRIMARY KEY DEFAULT gen_random_uuid()` |
| `action_requests` | `tenant_id` | `text` | `NOT NULL` |
| `action_requests` | `case_id` | `uuid` | `NOT NULL REFERENCES customer_cases` |
| `action_requests` | `action_type` | `text` | `NOT NULL` |
| `action_requests` | `arguments_json` | `jsonb` | `NOT NULL` |
| `action_requests` | `idempotency_key` | `text` | `NOT NULL` |
| `action_requests` | `status` | `action_status` | `NOT NULL` |
| `action_requests` | `provider_ref` | `text` | NULL 허용 |
| `action_requests` | `created_at` | `timestamptz` | `NOT NULL DEFAULT now()` |
| `action_approvals` | `approval_id` | `uuid` | `PRIMARY KEY DEFAULT gen_random_uuid()` |
| `action_approvals` | `action_id` | `uuid` | `NOT NULL REFERENCES action_requests` |
| `action_approvals` | `approver_id` | `text` | NULL 허용 |
| `action_approvals` | `decision` | `text` | `NOT NULL` |
| `action_approvals` | `decided_at` | `timestamptz` | NULL 허용 |
| `outbox` | `message_id` | `uuid` | `PRIMARY KEY DEFAULT gen_random_uuid()` |
| `outbox` | `tenant_id` | `text` | `NOT NULL` |
| `outbox` | `topic` | `text` | `NOT NULL` |
| `outbox` | `dedupe_key` | `text` | `NOT NULL` |
| `outbox` | `payload_json` | `jsonb` | `NOT NULL` |
| `outbox` | `status` | `text` | `NOT NULL DEFAULT 'pending'` |
| `outbox` | `attempts` | `int` | `NOT NULL DEFAULT 0` |
| `outbox` | `available_at` | `timestamptz` | `NOT NULL DEFAULT now()` |
| `outbox` | `locked_at` | `timestamptz` | NULL 허용 |
| `outbox` | `last_error` | `text` | NULL 허용 |
| `prompts` | `prompt_id` | `uuid` | `PRIMARY KEY DEFAULT gen_random_uuid()` |
| `prompts` | `prompt_key` | `text` | `NOT NULL` |
| `prompts` | `version` | `text` | `NOT NULL` |
| `prompts` | `template` | `text` | `NOT NULL` |
| `prompts` | `sha256` | `text` | `NOT NULL` |
| `prompts` | `model_family` | `text` | `NOT NULL` |
| `prompts` | `active` | `boolean` | `NOT NULL DEFAULT false` |
| `prompts` | `created_at` | `timestamptz` | `NOT NULL DEFAULT now()` |
| `llm_calls` | `call_id` | `uuid` | `PRIMARY KEY DEFAULT gen_random_uuid()` |
| `llm_calls` | `run_id` | `uuid` | NULL 허용, `REFERENCES agent_runs` |
| `llm_calls` | `prompt_id` | `uuid` | `NOT NULL REFERENCES prompts` |
| `llm_calls` | `provider` | `text` | `NOT NULL` |
| `llm_calls` | `model` | `text` | `NOT NULL` |
| `llm_calls` | `input_tokens` | `int` | NULL 허용 |
| `llm_calls` | `output_tokens` | `int` | NULL 허용 |
| `llm_calls` | `latency_ms` | `int` | NULL 허용 |
| `llm_calls` | `cost_microusd` | `bigint` | NULL 허용 |
| `llm_calls` | `response_json` | `jsonb` | NULL 허용 |
| `llm_calls` | `created_at` | `timestamptz` | `NOT NULL DEFAULT now()` |
| `knowledge_documents` | `document_id` | `uuid` | `PRIMARY KEY DEFAULT gen_random_uuid()` |
| `knowledge_documents` | `tenant_id` | `text` | `NOT NULL` |
| `knowledge_documents` | `title` | `text` | `NOT NULL` |
| `knowledge_documents` | `source_uri` | `text` | `NOT NULL` |
| `knowledge_documents` | `scope` | `text` | `NOT NULL` |
| `knowledge_documents` | `version` | `text` | `NOT NULL` |
| `knowledge_documents` | `pii_class` | `text` | `NOT NULL` |
| `knowledge_documents` | `created_at` | `timestamptz` | `NOT NULL DEFAULT now()` |
| `knowledge_chunks` | `chunk_id` | `uuid` | `PRIMARY KEY DEFAULT gen_random_uuid()` |
| `knowledge_chunks` | `document_id` | `uuid` | `NOT NULL REFERENCES knowledge_documents` |
| `knowledge_chunks` | `chunk_no` | `int` | `NOT NULL` |
| `knowledge_chunks` | `content` | `text` | `NOT NULL` |
| `knowledge_chunks` | `metadata_json` | `jsonb` | `NOT NULL` |
| `knowledge_chunks` | `embedding` | `vector(1536)` | `NOT NULL` |
| `feedback_analytics_reports` | `report_id` | `uuid` | `PRIMARY KEY DEFAULT gen_random_uuid()` |
| `feedback_analytics_reports` | `tenant_id` | `text` | `NOT NULL` |
| `feedback_analytics_reports` | `period_start` | `date` | `NOT NULL` |
| `feedback_analytics_reports` | `period_end` | `date` | `NOT NULL` |
| `feedback_analytics_reports` | `metrics_json` | `jsonb` | `NOT NULL` |
| `feedback_analytics_reports` | `alerts_json` | `jsonb` | `NOT NULL` |
| `feedback_analytics_reports` | `created_at` | `timestamptz` | `NOT NULL DEFAULT now()` |

`[미확보]` 원본 DDL은 FK의 `ON DELETE`·`ON UPDATE` 동작을 지정하지 않는다.

근거: `wiki/records/handoff/02_DB_스키마.md:37-155`

## 추가 UNIQUE 제약

`[실측]`

| 테이블 | UNIQUE |
|---|---|
| `customers` | `UNIQUE(tenant_id, external_id)` |
| `prompts` | `UNIQUE(prompt_key, sha256)` |
| `knowledge_chunks` | `UNIQUE(document_id, chunk_no)` |
| `feedback_analytics_reports` | `UNIQUE(tenant_id, period_start, period_end)` |

근거: `wiki/records/handoff/02_DB_스키마.md:41-47`, `wiki/records/handoff/02_DB_스키마.md:121-155`

## Core 인덱스

`[실측]`

| 인덱스 | 정의 |
|---|---|
| `knowledge_chunks_embedding_idx` | `knowledge_chunks USING hnsw (embedding vector_cosine_ops)` |
| `cases_tenant_customer_idx` | `customer_cases(tenant_id, customer_id)` |
| `events_case_version_idx` | `case_events(case_id, aggregate_version)` |

근거: `wiki/records/handoff/02_DB_스키마.md:157-160`

## 낙관적 동시성 충돌 처리

`[실측]`

```sql
UPDATE customer_cases
SET status = :status, state_json = :state_json,
    owner_team_id = :owner_team_id, version = version + 1, updated_at = now()
WHERE tenant_id = :tenant_id AND case_id = :case_id AND version = :expected_version
RETURNING version;
```

affected row가 0이면 `StateConflict`다. 최신 Case를 다시 읽고 최대 2회 재계산한다.

근거: `wiki/records/handoff/02_DB_스키마.md:179-189`

## Outbox worker claim 계약

`[실측]`

```sql
SELECT * FROM outbox
WHERE status = 'pending' AND available_at <= now()
ORDER BY available_at
FOR UPDATE SKIP LOCKED
LIMIT :batch;
```

provider timeout을 성공으로 추정하지 않는다. `unknown` 또는 재시도 대상으로 남긴다.

근거: `wiki/records/handoff/02_DB_스키마.md:191-201`

## RAG 검색 계약

`[실측]`

```sql
SELECT chunk_id, content, metadata_json,
       1 - (embedding <=> :query_embedding) AS score
FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)
WHERE kd.tenant_id = :tenant_id AND kd.scope = ANY(:allowed_scopes)
ORDER BY embedding <=> :query_embedding LIMIT 8;
```

근거: `wiki/records/handoff/02_DB_스키마.md:203-211`

## Seed 데이터 수량 계약

`[실측]`

| 대상 | 건수 | 필수 조건 |
|---|---:|---|
| tenant | 1 | `demo` |
| customer | 10 | `cust_01`부터 `cust_10` |
| 구독 mock | 10 | Free/Pro, 해지 이력 포함 |
| 결제 이력 mock | 30+ | 해지 후 추가 결제 사례 포함 |
| entitlement mock | 10 | Free/Pro 권한 동기화 오류 사례 포함 |
| incident mock | 3 | 권한 동기화 장애 |

mock provider 데이터는 실결제와 무관하다. 위 건수는 축소할 수 없으며 적재 후 실제 행 수를 세어 리포트에 기록한다.

근거: `wiki/records/handoff/02_DB_스키마.md:213-228`

## 테스트 데이터 정리 계약

`[실측]` 통합 테스트는 `acop` DB를 사용하되 테스트 전용 tenant를 사용하고 fixture teardown에서 자신이 만든 행을 삭제한다. seed 데이터를 오염시켜서는 안 된다.

근거: `wiki/records/handoff/02_DB_스키마.md:230-235`

## 관계

- [index.md](index.md) — 개념
- [../../../wiki/governance/migration-scope/coverage.md](../../../../wiki/governance/migration-scope/coverage.md) — 반영률
