===== APPEND TO: final_project_cs/wiki/teams/team-contract/index.md =====
## 계약 호환 규칙

`[실측]` Enum 밖의 문자열은 validator가 거부한다. `contract_version`은 `"MAJOR.MINOR"` 형식이며, 같은 major에서 optional field를 추가하는 변경만 호환된다. major 변경본은 adapter 또는 migration 없이 Registry에 등록하지 않는다.

근거: `docs/handoff/01_계약_Pydantic.md:7-13`

## `Evidence` 필드 계약

`[실측]` 모든 필드는 필수이며 기본값이 없다.

| 필드 | 타입 | 필수 | 제약 |
|---|---|---:|---|
| `evidence_id` | `str` | 예 | — |
| `source_type` | `Literal['customer_message', 'db', 'policy', 'tool_result', 'case_event']` | 예 | 열거값 밖 문자열 거부 |
| `source_id` | `str` | 예 | `source_type='policy'`이면 `"{document_id}#c{chunk_no}"` 형식 |
| `claim` | `str` | 예 | — |
| `value` | `Any` | 예 | — |
| `confidence` | `float` | 예 | `0 <= confidence <= 1` |
| `observed_at` | `datetime` | 예 | — |

`source_type`·`source_id`·`observed_at`은 의무다. 근거 없는 문장을 답변에 넣지 않는다.

근거: `docs/handoff/01_계약_Pydantic.md:43-58`

## `ContextPack` 필수 여부·기본값

`[실측]`

| 필드 | 정확한 타입 | 필수 | 기본값·추가 제약 |
|---|---|---:|---|
| `pack_id` | `UUID` | 예 | — |
| `case_id` | `UUID` | 예 | — |
| `team_id` | `str` | 예 | — |
| `tenant_id` | `str` | 예 | — |
| `knowledge_scope` | `list[str]` | 예 | — |
| `current_state` | `dict[str, Any]` | 예 | — |
| `evidence` | `list[Evidence]` | 아니오 | `default_factory=list`, 최대 40개 |
| `history_summary` | `str` | 아니오 | 기본값 `''`, 최대 10,000자 |
| `similar_cases` | `list[dict[str, Any]]` | 아니오 | `default_factory=list`, 최대 3개 |
| `estimated_input_tokens` | `int` | 예 | `>= 0`, `tiktoken` 실측값만 허용 |
| `degraded` | `bool` | 아니오 | 기본값 `False` |
| `omissions` | `list[str]` | 아니오 | `default_factory=list` |

예산 초과로 자료를 제거하면 `omissions`에 제거한 항목의 이름을 남긴다. `degraded=true`는 RAG 장애 등으로 근거가 부족한 상태이며 평가에서 별도로 집계한다.

근거: `docs/handoff/01_계약_Pydantic.md:60-83`

## `TeamTask` 누락 제약

`[실측]`

| 필드 | 필수 | 기본값·제약 |
|---|---:|---|
| `contract_name` | 아니오 | `Literal['a_cop.team_task']`, 기본값 `'a_cop.team_task'` |
| `contract_version` | 아니오 | `Literal['1.0']`, 기본값 `'1.0'` |
| `task_id` | 예 | `UUID` |
| `run_id` | 예 | `UUID` |
| `case_id` | 예 | `UUID` |
| `team_id` | 예 | `str` |
| `capability` | 예 | `str` |
| `case_version` | 예 | task 발행 시점의 Case version. 결과 merge 충돌 판정값 |
| `input_text` | 예 | `str`, 최소 1자·최대 12,000자 |
| `context` | 예 | `ContextPack` |
| `allowed_tools` | 예 | `list[str]`, `TeamManifest.allowed_tools`의 부분집합 |
| `deadline_at` | 예 | `datetime` |
| `resume` | 아니오 | `bool`, 기본값 `False` |
| `resume_node` | 아니오 | `str \| None`, 기본값 `None` |

`resume_node`가 문자열이면 `validate_input`, `execute_approved_action`, `verify_external_result` 중 하나다. `allowed_tools` 밖의 tool 호출은 거부한다.

근거: `docs/handoff/01_계약_Pydantic.md:85-108`

## `ActionProposal` 필수 여부·idempotency

`[실측]`

| 필드 | 정확한 타입 | 필수 | 기본값·제약 |
|---|---|---:|---|
| `action_type` | `str` | 예 | — |
| `arguments` | `dict[str, Any]` | 예 | — |
| `idempotency_key` | `str` | 예 | 최소 8자·최대 128자 |
| `approval_required` | `bool` | 예 | — |
| `risk_level` | `Literal['low', 'medium', 'high']` | 예 | 열거값 밖 문자열 거부 |
| `rationale_evidence_ids` | `list[str]` | 아니오 | `default_factory=list` |

최종 `idempotency_key`는 Team이 제안한 값을 그대로 쓰지 않고 서버가 다음 식으로 재계산한다.

```text
sha256(tenant_id + request_id + action_type + business_subject)
```

Controller가 allowlist·scope·승인·idempotency를 검증한다.

근거: `docs/handoff/01_계약_Pydantic.md:110-125`

## `TeamResult` 누락 필드·기본값

`[실측]`

| 필드 | 정확한 타입 | 필수 | 기본값·제약 |
|---|---|---:|---|
| `contract_name` | `Literal['a_cop.team_result']` | 아니오 | 기본값 `'a_cop.team_result'` |
| `contract_version` | `Literal['1.0']` | 아니오 | 기본값 `'1.0'` |
| `task_id` | `UUID` | 예 | — |
| `run_id` | `UUID` | 예 | — |
| `team_id` | `str` | 예 | — |
| `outcome` | `Literal['completed', 'waiting', 'handoff', 'escalated', 'failed']` | 예 | 열거값 밖 문자열 거부 |
| `answer` | `str \| None` | 아니오 | 기본값 `None`, 최대 6,000자 |
| `confidence` | `float` | 예 | `0 <= confidence <= 1` |
| `evidence` | `list[Evidence]` | 아니오 | `default_factory=list` |
| `decisions` | `list[dict[str, Any]]` | 아니오 | `default_factory=list` |
| `action_proposals` | `list[ActionProposal]` | 아니오 | `default_factory=list` |
| `next_action` | `NextAction` | 예 | — |
| `wait_reason` | `Literal['customer_input', 'human_approval', 'external_callback'] \| None` | 아니오 | 기본값 `None` |
| `required_input_schema` | `dict[str, Any] \| None` | 아니오 | 기본값 `None` |
| `handoff_capability` | `str \| None` | 아니오 | 기본값 `None` |
| `failure_code` | `str \| None` | 아니오 | 기본값 `None` |
| `warnings` | `list[str]` | 아니오 | `default_factory=list` |

근거: `docs/handoff/01_계약_Pydantic.md:127-149`

## `TeamResult` 추가 일관성 규칙

`[실측]`

| 조건 | validator가 요구하는 값 |
|---|---|
| `next_action='respond'` | `answer` 필수 |
| `next_action='escalate'` | `failure_code` 또는 `warnings` 필수 |
| `answer is not None` | `evidence`가 비어 있으면 거부 |

근거: `docs/handoff/01_계약_Pydantic.md:151-161`

## `TeamManifest` 필드 계약

`[실측]`

| 필드 | 타입 | 필수 | 기본값·제약 |
|---|---|---:|---|
| `team_id` | `str` | 예 | — |
| `display_name` | `str` | 예 | — |
| `contract_name` | `Literal['a_cop.team_task']` | 예 | — |
| `supported_contract_versions` | `list[str]` | 예 | — |
| `capabilities` | `list[str]` | 예 | 최소 1개 |
| `accepted_case_types` | `list[str]` | 예 | — |
| `required_context` | `list[Literal['case_state', 'policy', 'db_facts', 'history']]` | 예 | 열거값 밖 문자열 거부 |
| `allowed_tools` | `list[str]` | 예 | — |
| `knowledge_scope` | `list[str]` | 예 | — |
| `max_steps` | `int` | 아니오 | 기본값 `6`, `1 <= max_steps <= 12` |
| `active` | `bool` | 아니오 | 기본값 `True` |
| `implementation_revision` | `str` | 예 | — |
| `default_capability` | `str \| None` | 아니오 | 기본값 `None`; 없으면 `capabilities[0]` 사용 |

근거: `docs/handoff/01_계약_Pydantic.md:163-187`

## 선택적 capability 선택 계약

`[실측]` Team은 다음 메서드를 선택적으로 구현할 수 있다.

```python
def select_capability(intent: str | None, input_text: str) -> str | None: ...
```

Registry는 namespace 매칭보다 먼저 이 값을 묻는다. 반환값이 `None`이거나 메서드가 없으면 기존 규칙을 적용한다. 필수 Protocol 멤버가 아니며 `getattr` 기반 duck-typing으로 감지한다.

근거: `docs/handoff/01_계약_Pydantic.md:189-197`

## `TeamModule` Protocol

`[실측]`

```python
class TeamModule(Protocol):
    manifest: TeamManifest
    async def execute(self, task: TeamTask) -> TeamResult: ...
```

Core가 사용하는 Team 표면은 `manifest`와 `execute()`뿐이다.

근거: `docs/handoff/01_계약_Pydantic.md:199-208`

## `MessageBrokerPort`

`[실측]`

```python
class MessageBrokerPort(Protocol):
    async def publish(self, topic: str, payload: dict, dedupe_key: str) -> str: ...
    async def ack(self, message_id: str) -> None: ...
```

| 구현체 | 상태 |
|---|---|
| `OutboxBrokerAdapter` | MVP 구현체. outbox 테이블과 background worker 사용 |
| `RedisStreamsAdapter` | Phase 2 대상. 같은 Port를 구현하며 현재 본체는 만들지 않음 |

근거: `docs/handoff/01_계약_Pydantic.md:210-219`

## 계약 예외

`[실측]`

| 예외 | 발생 조건 |
|---|---|
| `StateConflict` | optimistic concurrency 실패, affected row 0 |
| `ContractViolation` | 계약 검증 실패 |
| `ToolNotAllowed` | allowlist 밖 tool 호출 |
| `GuardrailExceeded` | step·tool·token·cost 상한 초과 |
| `ScopeDenied` | scope 부족 |

예외를 삼키지 않는다.

근거: `docs/handoff/01_계약_Pydantic.md:221-231`

===== APPEND TO: final_project_cs/wiki/data/schema/index.md =====
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

근거: `docs/handoff/02_DB_스키마.md:7-27`

## DB Enum

`[실측]`

| 타입 | 허용값 |
|---|---|
| `case_status` | `new`, `classifying`, `routing`, `running`, `waiting_input`, `waiting_approval`, `waiting_external`, `resuming`, `resolved`, `escalated`, `failed`, `cancelled` |
| `action_status` | `proposed`, `pending_approval`, `approved`, `rejected`, `executing`, `succeeded`, `failed`, `unknown`, `cancelled` |

근거: `docs/handoff/02_DB_스키마.md:29-35`

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

근거: `docs/handoff/02_DB_스키마.md:37-155`

## 추가 UNIQUE 제약

`[실측]`

| 테이블 | UNIQUE |
|---|---|
| `customers` | `UNIQUE(tenant_id, external_id)` |
| `prompts` | `UNIQUE(prompt_key, sha256)` |
| `knowledge_chunks` | `UNIQUE(document_id, chunk_no)` |
| `feedback_analytics_reports` | `UNIQUE(tenant_id, period_start, period_end)` |

근거: `docs/handoff/02_DB_스키마.md:41-47`, `docs/handoff/02_DB_스키마.md:121-155`

## Core 인덱스

`[실측]`

| 인덱스 | 정의 |
|---|---|
| `knowledge_chunks_embedding_idx` | `knowledge_chunks USING hnsw (embedding vector_cosine_ops)` |
| `cases_tenant_customer_idx` | `customer_cases(tenant_id, customer_id)` |
| `events_case_version_idx` | `case_events(case_id, aggregate_version)` |

근거: `docs/handoff/02_DB_스키마.md:157-160`

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

근거: `docs/handoff/02_DB_스키마.md:179-189`

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

근거: `docs/handoff/02_DB_스키마.md:191-201`

## RAG 검색 계약

`[실측]`

```sql
SELECT chunk_id, content, metadata_json,
       1 - (embedding <=> :query_embedding) AS score
FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)
WHERE kd.tenant_id = :tenant_id AND kd.scope = ANY(:allowed_scopes)
ORDER BY embedding <=> :query_embedding LIMIT 8;
```

근거: `docs/handoff/02_DB_스키마.md:203-211`

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

근거: `docs/handoff/02_DB_스키마.md:213-228`

## 테스트 데이터 정리 계약

`[실측]` 통합 테스트는 `acop` DB를 사용하되 테스트 전용 tenant를 사용하고 fixture teardown에서 자신이 만든 행을 삭제한다. seed 데이터를 오염시켜서는 안 된다.

근거: `docs/handoff/02_DB_스키마.md:230-235`

===== APPEND TO: final_project_cs/wiki/external/rest-api.md =====
## `/v1/*` 표면 상한과 scope

`[실측]` 외부 AI용 `/v1/*` endpoint는 정확히 5개다. `/v1/` 아래에 여섯 번째 경로가 생기면 계약 위반이다.

| 메서드 | 경로 | 필수 scope |
|---|---|---|
| `POST` | `/v1/cases` | `case:write` |
| `GET` | `/v1/cases` | `case:read` |
| `GET` | `/v1/cases/{case_id}` | `case:read` |
| `POST` | `/v1/cases/{case_id}/messages` | `case:write` |
| `POST` | `/v1/cases/{case_id}/actions/{action_id}/approve` | `action:approve` |

다음 경로는 5개를 셀 때 제외한다.

| 경로 | 성격 |
|---|---|
| `/health` | 상태 확인 |
| `/ui/*` | 운영 화면 |
| `/openapi.json`, `/docs`, `/redoc` | FastAPI 기본 제공 |

`/ui/*`는 쓰기를 직접 수행하지 않는다. 승인은 `/v1/cases/{case_id}/actions/{action_id}/approve`를 호출한다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:18-45`

## `POST /v1/cases` 요청·응답 필드

`[실측]`

요청:

| 필드 | JSON 타입 | 예시 | 필수 여부 |
|---|---|---|---|
| `request_id` | string | `"req_01"` | `[미확보]` |
| `idempotency_key` | string | `"idem_01"` | `[미확보]` |
| `tenant_id` | string | `"demo"` | `[미확보]` |
| `customer_id` | string | `"cust_01"` | `[미확보]` |
| `message` | string | `"배송완료로 떴는데 상품을 못 받았어요"` | `[미확보]` |
| `channel` | string | `"personal_ai"` | `[미확보]`; `personal_ai \| mcp \| web \| api` 중 하나 |

성공 응답 상태 코드는 `201`이다.

| 응답 필드 | JSON 타입 | 예시 |
|---|---|---|
| `case_id` | string | `"case_01"` |
| `status` | string | `"classifying"` |
| `version` | number | `1` |
| `intent` | string | `"shipping"` |
| `issue_code` | string | `"shipping_delivered_not_received"` |
| `sentiment` | string | `"negative"` |
| `links.self` | string | `"/v1/cases/case_01"` |

`idempotency_key`는 서버가 재계산하며 클라이언트 값은 `request_id` 재료일 뿐이다. 같은 키로 재요청하면 새 Case를 만들지 않고 기존 결과를 그대로 반환한다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:47-67`

## `GET /v1/cases` 쿼리 계약

`[실측]`

| 쿼리 필드 | 필수 | 기본값·제약 |
|---|---:|---|
| `customer_id` | 예 | 호출자의 소유 범위 검사 |
| `status` | 아니오 | `[미확보]` 허용값 |
| `limit` | 아니오 | 기본값 `20`, 최대 `100` |
| `cursor` | 아니오 | `[미확보]` 형식 |

호출자의 tenant·customer 범위 밖 Case를 반환하지 않는다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:68-71`

## `GET /v1/cases/{case_id}` 응답 계약

`[실측]`

| 필드 | 형태·예시 |
|---|---|
| `case_id` | `"case_01"` |
| `status` | `"waiting_approval"` |
| `version` | `7` |
| `answer` | `"환불 요청을 준비했습니다."` |
| `pending_actions[]` | `{"action_id":"a_01","action_type":"refund.request","approval_required":true}` |
| `evidence[]` | `{"source_type":"policy","source_id":"doc_04#c12","claim":"..."}` |

`evidence`는 masked 상태로 반환한다. 원문 PII를 응답에 싣지 않으며, `answer`가 있는데 `evidence`가 비어 있으면 계약 위반이다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:73-84`

## 추가 메시지 resume 제약

`[실측]`

| 항목 | 제약 |
|---|---|
| 상태 전이 | `waiting_input` → `resuming` |
| resume token 저장 | 원문이 아니라 hash만 저장 |
| TTL | `24h` |
| 사용 횟수 | 일회성 |
| 중복 처리 | 동일 `event_id` 재처리는 idempotent |
| TTL 만료 | 자동 진행 금지; `escalated` + 운영자 알림 |

`[미확보]` 원본은 이 endpoint의 요청 body 필드 이름을 밝히지 않는다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:86-90`

## 승인 요청·감사 계약

`[실측]`

요청:

```json
{"decision":"approved","approver_id":"op_01","note":"정책 확인함"}
```

| 필드 | 제약 |
|---|---|
| `decision` | `approved \| rejected` |
| `approver_id` | `[미확보]` 필수 여부·타입 제약 |
| `note` | `[미확보]` 필수 여부·길이 제약 |

승인 event와 before/after hash를 audit에 기록한다. audit에는 API key 원문이나 결제 식별자 원문을 기록하지 않는다. 승인 후 실행은 idempotent해야 하며 동일 요청 10회에 side effect는 1회다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:92-99`

## 오류 응답 계약

`[실측]`

| HTTP | 조건 | `error.code` |
|---:|---|---|
| `400` | 스키마 위반 | `contract_violation` |
| `401` | API key 없음 또는 무효 | `unauthenticated` |
| `403` | scope 부족 또는 ownership 불일치 | `scope_denied` |
| `404` | 존재하지 않거나 볼 권한이 없는 리소스 | `not_found` |
| `409` | optimistic concurrency 충돌 | `state_conflict` |
| `422` | 허용되지 않은 상태 전이 | `invalid_transition` |
| `429` | 일일 비용 또는 호출 상한 | `guardrail_exceeded` |

오류 body에 stack trace·SQL·내부 경로를 넣지 않는다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:101-114`

## 인증 형식

`[실측]`

| 항목 | 계약 |
|---|---|
| MVP 인증 | hashed API key + scope |
| Header | `Authorization: Bearer <api_key>` |
| OAuth2/OIDC | Phase 2; MVP에서 구현하지 않음 |
| scope 검증 | scope × endpoint 전체 unauthorized matrix 테스트 |

근거: `docs/handoff/03_REST_MCP_인터페이스.md:116-121`

## OpenAPI 일치 조건

`[실측]` `/openapi.json`은 계약된 `/v1/*` endpoint 5개와 일치해야 한다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:150-153`

===== APPEND TO: final_project_cs/wiki/external/mcp-tools.md =====
## 비동기 도구 시그니처

`[실측]` 세 도구의 계약 시그니처는 `async def`다.

```python
async def get_my_cases(customer_id: str, limit: int = 20) -> list[dict]: ...
async def get_case_detail(customer_id: str, case_id: str) -> dict: ...
async def open_support_case(customer_id: str, message: str, channel: str = 'mcp') -> dict: ...
```

근거: `docs/handoff/03_REST_MCP_인터페이스.md:123-136`

## MCP ownership·응답 제약

`[실측]`

| 항목 | 제약 |
|---|---|
| ownership | 세 도구 모두 `customer_id` 소유 검사를 매 호출 수행 |
| 응답 | REST와 동일하게 masked |
| evidence | 내부 evidence 원문과 PII 노출 금지 |
| `open_support_case` | Case 생성과 분류 시작까지만 수행 |

근거: `docs/handoff/03_REST_MCP_인터페이스.md:138-148`

===== APPEND TO: final_project_cs/wiki/teams/index.md =====
## 구성 단위 구분

`[실측]`

| 단위 | 정의 | 구성기 동작 |
|---|---|---|
| 컴포넌트 | 제거하면 시스템이 성립하지 않는 구성물 | 선택 불가, 항상 포함 |
| 모듈 | 꺼도 나머지 시스템이 동작하는 단위 | 선택 가능 |
| Port | 구현을 교체하는 지점 | 구현체 선택 |
| 인스턴스 | 같은 계약을 만족하며 여러 개 둘 수 있는 항목 | 개수 추가·제거 |

근거: `docs/handoff/08_모듈_컴포넌트_목록.md:7-18`

## 필수 컴포넌트

`[실측]`

| 컴포넌트 | 위치 | 필수 의존 |
|---|---|---|
| Case lifecycle · `transition_case()` | `app/core/transition.py`, `app/domain/{case,events}.py` | 상태 변경의 단일 진입점; API의 Case 생성·분류가 이벤트에 의존 |
| 계약 모델 | `app/core/contracts.py` | Controller·Team·평가가 `TeamTask`·`TeamResult`·`TeamManifest`·`TeamModule`·`ContextPack`·`Evidence` 사용 |
| Team Registry | `app/core/registry.py` | capability 해석의 유일한 경로 |
| Context Broker | `app/core/context.py` | 12,000 토큰 예산·절삭·`degraded` 신호 |
| DB repository / session | `app/infrastructure/db/` | Source of Truth |
| Outbox 원자성 | `app/infrastructure/messaging/outbox.py` | projection·event·발행을 한 transaction으로 처리 |
| Case service | `app/application/case_service.py` | run/resume, active run 중복 방지, `agent_runs` 기록 |
| Controller | `app/application/controller.py` | 필수 컴포넌트를 연결하는 실행 루프 |
| 설정·가드레일 | `app/core/settings.py`, `config/guardrails.yaml` | 수치의 단일 출처 |

근거: `docs/handoff/08_모듈_컴포넌트_목록.md:22-35`

## 토글 가능한 모듈

`[실측]`

| 설정 이름 | 모듈 | 위치 | 끄면 제거되는 기능·표면 |
|---|---|---|---|
| `graph_store` | GraphStore | `app/core/graph_retrieval/port.py`, `app/infrastructure/graphstore/sql_adapter.py` | `neighbors`·`path`·`subgraph` 질의와 관리자 화면 Graph 섹션 |
| `a2a_executor` | A2A Executor | `app/core/remote_team/a2a_executor.py`, `app/presentation/a2a/` | 원격 Agent 위임·Agent Card·`/a2a/*` |
| `mcp` | MCP | `app/presentation/api/mcp.py` | 개인 AI read-only tool 3종과 MCP scope |
| `vector_rag` | Vector RAG | `app/infrastructure/rag/retriever.py` | 정책 검색·knowledge 적재; `ContextPack.degraded`로 전환 |
| `ops_ui` | 운영 UI | `app/presentation/ui/` | Case·Trace·Approval·VOC 화면과 `/ui/*` |
| `voc` | VOC 판단층·화면 | VOC Team, VOC 화면 | VOC Team 판단층과 VOC 화면 |

모듈을 끄면 그것을 호출하는 경로도 함께 제거한다. 호출 경로가 남으면 조용히 넘어가지 않고 명시적으로 실패한다.

근거: `docs/handoff/08_모듈_컴포넌트_목록.md:38-55`, `docs/handoff/08_모듈_컴포넌트_목록.md:112-128`

## `voc` 경계

`[실측]` `voc: false`가 끄는 것은 판단층과 화면뿐이다.

| 기능 | 소유 | `voc` 게이트 |
|---|---|---|
| 인라인 분류 `build_classifier` | 코어 1 | 없음 |
| 일일 집계 배치 `app/application/feedback_job.py` | 코어 1 | 없음 |
| VOC Team 판단층 | 모델 | 있음 |
| VOC 화면 | — | 있음 |

인라인 분류는 다음 두 부분으로 분리한다.

| 책임 | 위치 | 소유 |
|---|---|---|
| 호출 시점·실패 처리·상태 전이 | `app/application/classification.py` | 코어 1 |
| 라벨 어휘·프롬프트·provider 호출 | `app/modules/customer_ops/feedback.py` | 모델 |

근거: `docs/handoff/08_모듈_컴포넌트_목록.md:112-152`

## 모듈 게이트 강제점

`[실측]`

| 모듈 | 강제점 |
|---|---|
| `mcp` | 비활성화 시 `_mcp_principal()`이 거부 |
| `voc` | 판단층과 화면이 거부되거나 등록되지 않음 |
| `graph_store` | 관리자 화면도 어댑터를 직접 생성하지 않고 조립 경계를 통과 |

선언된 모듈에 실제 검사 지점이 있는지는 `tests/contract/test_module_toggles.py`가 검사한다.

근거: `docs/handoff/08_모듈_컴포넌트_목록.md:57-68`

## 교체 가능한 Port

`[실측]`

| Port | 정의 | 현재 구현 | 대안 |
|---|---|---|---|
| `TeamExecutorPort` | `app/core/remote_team/executor.py` | `LocalTeamExecutor` | `A2ATeamExecutor` |
| `MessageBrokerPort` | `app/core/contracts.py` | `OutboxBrokerAdapter` | `RedisStreamsAdapter` — Phase 2, 미구현 |
| `GraphStorePort` | `app/core/graph_retrieval/port.py` | `SqlGraphAdapter` — JOIN·재귀 CTE | AGE·Neo4j — Phase 2 |
| 정책 검색 함수 | `build_controller(policy_search_fn=...)` | `search_policy` — pgvector | 주입으로 교체 |
| LLM | `app/infrastructure/llm/openai.py` | `OpenAITeamLLM` | provider 교체 |
| 분류기 | `build_classifier()` | `feedback.classify` | 주입으로 교체 |

근거: `docs/handoff/08_모듈_컴포넌트_목록.md:156-165`

## 가변 인스턴스 계약

`[실측]`

| 종류 | 원본 실측 인스턴스 | 추가 조건 |
|---|---|---|
| Agent Team | `OrderShippingTeam`, `ReturnExchangeTeam` | `TeamModule` Protocol 구현 + Registry 등록 |

Agent Team만 개수가 2개에서 3개·4개 등으로 변할 수 있다. Team은 `manifest`와 `execute()`를 만족해야 하며 Core는 `_capability()`의 Registry 조회로 Team을 찾는다.

근거: `docs/handoff/08_모듈_컴포넌트_목록.md:169-177`

## 구성 선언 필드

`[실측]`

```yaml
modules:
  vector_rag:    { enabled: true }
  graph_store:   { enabled: true }
  a2a_executor:  { enabled: false }
  mcp:           { enabled: true }
  voc:           { enabled: true }
  ops_ui:        { enabled: true }
ports:
  team_executor: local
  message_broker: outbox
  graph_store: sql
teams:
  - { team_id: order_shipping,  active: true,  implementation_ref: "app.modules.customer_ops:OrderShippingTeam" }
  - { team_id: return_exchange, active: true,  implementation_ref: "app.modules.customer_ops:ReturnExchangeTeam" }
```

| Port 설정 | 허용 선택지 |
|---|---|
| `team_executor` | `local \| a2a` |
| `message_broker` | `outbox \| redis_streams` — `redis_streams`는 Phase 2 |
| `graph_store` | `sql \| age \| neo4j` — `neo4j`는 Phase 2 |

`app/composition.py`는 `load_project_config()`와 `importlib`로 `teams[].implementation_ref`를 동적으로 읽는다.

근거: `docs/handoff/08_모듈_컴포넌트_목록.md:181-210`

## 구성 검증 실패 조건

`[실측]`

| 실패 조건 | 판정 |
|---|---|
| `enabled: true`인데 구현이 없음 | 빌드 실패 |
| `active: true`인데 `implementation_ref`를 import할 수 없음 | 빌드 실패 |
| `team_id` 중복 | 빌드 실패 |
| 같은 capability를 두 Team이 주장 | 빌드 실패 |
| 비활성화한 모듈을 호출하는 경로가 남음 | 빌드 실패 |

미구현 Team은 `active: false`로 둔다. Registry에는 이름이 남지만 라우팅 대상에서는 제외된다.

근거: `docs/handoff/08_모듈_컴포넌트_목록.md:213-221`