# final_project_cs 구현 현황

이 문서는 **2026-08-19 시점의 스냅샷**이다. 코드가 바뀌면 이 문서는 낡는다. 갱신하려면 같은 조사 범위로 `final_project_cs/`를 다시 읽고 이 파일을 재생성한다.

대상은 `final_project_cs/`이다. `final_project_sample/`은 조사하지 않았다. 테스트는 실행하지 않았다.

## 1. 디렉터리 구조

`app/`은 구성 루트, 애플리케이션 런타임, 도메인, 인프라, 모듈, 프레젠테이션을 나누어 둔다.

| 경로 | 역할 |
|---|---|
| `app/` | 애플리케이션 패키지와 구성 루트다. |
| `app/application/` | Controller와 CaseService 등 유스케이스 실행을 조정한다. |
| `app/core/` | 계약, 상태 전이, Registry, ContextBroker, 포트, 검증 규칙을 둔다. |
| `app/core/access_action/` | 접근·Action 관련 하위 경계가 있는 디렉터리다. |
| `app/core/case_runtime/` | Case runtime 기능을 case, context, contracts, orchestration 등으로 나눈 디렉터리다. |
| `app/core/graph_retrieval/` | GraphStore 포트를 둔다. |
| `app/core/remote_team/` | Local/A2A Team Executor 포트를 둔다. |
| `app/domain/` | `CaseProjection`, 이벤트 타입, 순수 상태 전이 함수를 둔다. |
| `app/infrastructure/` | DB, RAG, GraphStore, LLM, 메시징, A2A 전송 구현체를 둔다. |
| `app/infrastructure/db/` | psycopg 세션, Repository, 마이그레이션을 둔다. |
| `app/infrastructure/a2a/` | A2A HTTP transport를 둔다. |
| `app/infrastructure/graphstore/` | SQL Graph adapter를 둔다. |
| `app/infrastructure/messaging/` | Outbox broker와 worker를 둔다. |
| `app/infrastructure/rag/` | 정책 검색 구현을 둔다. |
| `app/infrastructure/llm/` | OpenAI Team LLM과 LLM 호출 기록을 둔다. |
| `app/modules/` | 도메인별 Team 모듈을 둔다. |
| `app/modules/customer_ops/` | VOC, feedback 분류, response review, 커머스 검증 정책을 둔다. |
| `app/modules/customer_ops/team_modules/` | local/remote Team 예시 하위 구조가 남아 있다. |
| `app/presentation/` | 외부 HTTP, MCP, A2A, 운영 UI 경계를 둔다. |
| `app/presentation/api/` | FastAPI Case, Composer API와 MCP 모듈을 둔다. |
| `app/presentation/a2a/` | Agent card와 원격 Agent FastAPI 구현을 둔다. |
| `app/presentation/ui/` | `/ui` 운영 화면과 HTML 렌더링을 둔다. |
| `app/presentation/schemas/` | 프레젠테이션 스키마 디렉터리다. 현재 파일 목록에는 별도 소스가 없다. |
| `app/tools/` | Team이 사용하는 이름 있는 읽기 도구와 prompt 등록 함수를 둔다. |

## 2. 등록된 구성요소

`config/project.yaml`에는 모듈 6개, 포트 3개, Team 1개가 선언되어 있다.

### Team

| team_id | active | implementation_ref | 클래스 존재 |
|---|---:|---|---:|
| `voc_store_manager` | true | `app.modules.customer_ops:VocStoreManagerTeam` | 있음 (`app/modules/customer_ops/voc_store_manager.py:12`) |

### 모듈

| 모듈 | enabled |
|---|---:|
| `vector_rag` | true |
| `graph_store` | true |
| `a2a_executor` | false |
| `mcp` | true |
| `voc` | true |
| `ops_ui` | true |

### Port와 구현체

| Port 설정 | 현행 구현체 | 근거 |
|---|---|---|
| `team_executor: local` | `LocalTeamExecutor` | `app/core/remote_team/executor.py:12` |
| `message_broker: outbox` | `OutboxBrokerAdapter` | `app/infrastructure/messaging/outbox.py:12` |
| `graph_store: sql` | `SqlGraphAdapter` | `app/infrastructure/graphstore/sql_adapter.py:6` |

`a2a_executor` 모듈은 존재하지만 설정상 비활성이다. `ResponseGenerationReviewTeam`은 소스와 manifest가 있으나 `project.yaml`의 Team 목록에는 등록되어 있지 않다.

## 3. 계약 모델

`app/core/contracts.py`의 Pydantic 계약 모델은 6개다. `CustomerCase`라는 Pydantic 모델은 없다.

| 클래스 | 주요 필드 | 줄 |
|---|---|---:|
| `Evidence` | `evidence_id`, `source_type`, `source_id`, `claim`, `value`, `confidence`, `observed_at` | 94 |
| `ContextPack` | `pack_id`, `case_id`, `team_id`, `tenant_id`, `knowledge_scope`, `current_state`, `evidence`, `token_budget`, `degraded`, `omissions` | 122 |
| `TeamTask` | `task_id`, `run_id`, `case_id`, `team_id`, `capability`, `case_version`, `input_text`, `context`, `allowed_tools`, `deadline_at`, `resume`, `resume_node` | 165 |
| `ActionProposal` | `action_type`, `arguments`, `idempotency_key`, `approval_required`, `risk_level`, `rationale_evidence_ids` | 201 |
| `TeamResult` | `task_id`, `run_id`, `team_id`, `outcome`, `answer`, `confidence`, `evidence`, `decisions`, `action_proposals`, `next_action`, `wait_reason`, `failure_code` | 223 |
| `TeamManifest` | `team_id`, `display_name`, `contract_name`, `supported_contract_versions`, `capabilities`, `accepted_case_types`, `required_context`, `allowed_tools`, `knowledge_scope`, `active`, `implementation_revision` | 303 |

같은 파일에는 `CaseStatus` enum(53), `NextAction` enum(68), `TeamModule` Protocol(321), `MessageBrokerPort` Protocol(339)도 있다. 예외 클래스는 `StateConflict`, `ContractViolation`, `ToolNotAllowed`, `GuardrailExceeded`, `ScopeDenied`, `InvalidTransition`이다.

`app/domain/`에는 `CaseProjection` dataclass(25)와 `EventType` enum(16)가 있다. `CaseProjection`은 `customer_cases` 테이블의 런타임 투영이며 필드는 `status`, `version`, `state_json`, `intent`, `issue_code`, `sentiment`, `owner_team_id`다.

## 4. Core 런타임 클래스

### Registry

`TeamRegistry`는 `app/core/registry.py:29`에 있다.

| 공개 메서드 | 줄 |
|---|---:|
| `__init__(self, teams: list[TeamModule] \| None = None, *, contract_version: str = "1.0") -> None` | 32 |
| `register(self, team: TeamModule) -> TeamManifest` | 38 |
| `get(self, team_id: str) -> RegisteredTeam` | 48 |
| `resolve(self, *, case_type: str, intent: str \| None = None) -> RegisteredTeam` | 54 |
| `capability_for(entry: RegisteredTeam, intent: str \| None = None) -> str` | 82 |
| `manifests(self) -> tuple[TeamManifest, ...]` | 91 |

### Controller

`Controller`는 `app/application/controller.py:26`에 있다.

| 공개 메서드 | 줄 |
|---|---:|
| `__init__(self, registry: TeamRegistry, *, context_broker: ContextBroker \| None = None, policy_search: Callable[..., list[Any]] \| None = None, connection_factory: Callable \| None = None, repository: Any \| None = None, case_service: CaseService \| None = None, graph_revision: str = "controller-v1", team_executor: Any \| None = None, broker: Any \| None = None, verification_policy: Any \| None = None, fact_queries: Any = ()) -> None` | 27 |
| `run_case(self, *, tenant_id: str, case_id: UUID, actor_id: str = "controller") -> dict[str, Any]` | 107 |
| `resume(self, *, tenant_id: str, case_id: UUID, token: str, actor_id: str = "controller", event_id: str \| None = None) -> dict[str, Any]` | 259 |

`ContextBroker`는 `app/core/context.py:90`에 있다. 공개 메서드는 `__init__(self) -> None`(93), `build(self, inputs: ContextInputs) -> ContextPack`(195)이다.

`LocalTeamExecutor`는 `app/core/remote_team/executor.py:12`에 있다. 공개 메서드는 `__init__(self, registry)`(15), `execute(self, task: TeamTask) -> TeamResult`(18)다. `TeamExecutorPort`의 같은 시그니처가 8~9줄에 있다.

상태 전이의 단일 함수는 `transition_case(...) -> TransitionResult`이며 `app/core/transition.py:116`에 있다. 공개 인자는 `conn`, `tenant_id`, `case_id`, `expected_version`, `event_type`, `payload`, `actor_type`, `actor_id`, `outbox`다. 이벤트 재생 함수는 `replay_case(conn, *, tenant_id: str, case_id: UUID) -> CaseProjection`이며 215줄이다.

전이 결과 모델은 `OutboxMessage`(36)와 `TransitionResult`(45) dataclass다. 상태 전이의 도메인 함수는 `next_status`(119), `allowed_events`(124), `allowed_next_statuses`(129)다.

## 5. 진입점

### REST

현행 REST 진입점은 18개다. API 10개, 운영 UI 8개로 셌다.

| 경로 | 메서드 | 핸들러 | 파일:줄 |
|---|---|---|---|
| `/health` | GET | `health` | `app/presentation/api/app.py:42` |
| `/v1/cases` | POST | `create` | `app/presentation/api/cases.py:67` |
| `/v1/cases` | GET | `list_cases` | `app/presentation/api/cases.py:109` |
| `/v1/cases/{case_id}` | GET | `detail` | `app/presentation/api/cases.py:115` |
| `/v1/cases/{case_id}/messages` | POST | `message` | `app/presentation/api/cases.py:123` |
| `/v1/cases/{case_id}/actions/{action_id}/approve` | POST | `approve` | `app/presentation/api/cases.py:135` |
| `/auth/token` | POST | `token` | `app/presentation/composer_auth.py:74` |
| `/composer/current` | GET | `current` | `app/presentation/api/composer.py:44` |
| `/composer/validate` | POST | `validate` | `app/presentation/api/composer.py:50` |
| `/composer/apply` | POST | `apply` | `app/presentation/api/composer.py:59` |
| `/` | GET | `_root` | `app/presentation/ui/__init__.py:38` |
| `/ui/admin` | GET | `admin` | `app/presentation/ui/routes.py:137` |
| `/ui/cases` | GET | `cases` | `app/presentation/ui/routes.py:210` |
| `/ui/cases/{case_id}` | GET | `case_detail` | `app/presentation/ui/routes.py:253` |
| `/ui/cases/{case_id}/trace` | GET | `trace` | `app/presentation/ui/routes.py:288` |
| `/ui/approvals` | GET | `approvals` | `app/presentation/ui/routes.py:311` |
| `/ui/approvals/{case_id}/{action_id}` | POST | 인라인 approval handler | `app/presentation/ui/routes.py:359` |
| `/ui/voc` | GET | `voc` | `app/presentation/ui/routes.py:380` |

### MCP

`app/presentation/api/mcp.py`에 `FastMCP("A-COP")`가 있다. 등록 도구는 3개이며 모두 `required_scope: mcp:read`다.

| 도구 | 시그니처 | 줄 |
|---|---|---:|
| `get_my_cases` | `(customer_id: str, limit: int = 20) -> list[dict]` | 8 |
| `get_case_detail` | `(customer_id: str, case_id: str) -> dict` | 13 |
| `open_support_case` | `(customer_id: str, message: str, channel: str = "mcp") -> dict` | 18 |

MCP resource 등록은 확인되지 않았다.

### A2A

`app/presentation/a2a/remote_agent.py`에는 Agent card 1개와 task 경로 4개가 있다. `/.well-known/agent-card.json` GET(66), `/a2a/tasks` POST(71), `/a2a/tasks/{task_id}` GET(91), `/a2a/tasks/{task_id}/input` POST(107), `/a2a/tasks/{task_id}/cancel` POST(126)이다. Agent card 생성 함수는 `app/presentation/a2a/agent_card.py:4`의 `build_agent_card`다. 설정상 `a2a_executor`는 비활성이다.

## 6. 데이터 스키마

마이그레이션에는 18개 테이블이 있다. `001_schema.sql`에 14개, `002_domain_commerce.sql`에 4개다.

| 테이블 | 핵심 컬럼 |
|---|---|
| `tenants` | `tenant_id`, `name` |
| `customers` | `customer_id`, `tenant_id`, `external_id`, `email_hash`, `created_at` |
| `customer_cases` | `case_id`, `tenant_id`, `customer_id`, `status`, `subject`, `state_json`, `intent`, `issue_code`, `sentiment`, `owner_team_id`, `version`, `created_at`, `updated_at` |
| `case_events` | `event_id`, `tenant_id`, `case_id`, `aggregate_version`, `event_type`, `payload_json`, `actor_type`, `actor_id`, `created_at` |
| `agent_runs` | `run_id`, `tenant_id`, `case_id`, `graph_revision`, `status`, `attempt`, `started_at`, `finished_at` |
| `team_tasks` | `task_id`, `run_id`, `team_id`, `contract_version`, `payload_json`, `status`, `created_at` |
| `action_requests` | `action_id`, `tenant_id`, `case_id`, `action_type`, `arguments_json`, `idempotency_key`, `status`, `provider_ref`, `created_at` |
| `action_approvals` | `approval_id`, `action_id`, `approver_id`, `decision`, `decided_at` |
| `outbox` | `message_id`, `tenant_id`, `topic`, `dedupe_key`, `payload_json`, `status`, `attempts`, `available_at`, `locked_at`, `last_error` |
| `prompts` | `prompt_id`, `prompt_key`, `version`, `template`, `sha256`, `model_family`, `active`, `created_at` |
| `llm_calls` | `call_id`, `run_id`, `prompt_id`, `provider`, `model`, token·latency·cost 컬럼, `response_json`, `created_at` |
| `knowledge_documents` | `document_id`, `tenant_id`, `title`, `source_uri`, `scope`, `version`, `pii_class`, `created_at` |
| `knowledge_chunks` | `chunk_id`, `document_id`, `chunk_no`, `content`, `metadata_json`, `embedding` |
| `feedback_analytics_reports` | `report_id`, `tenant_id`, `period_start`, `period_end`, `metrics_json`, `alerts_json`, `created_at` |
| `orders` | `order_id`, `tenant_id`, `customer_id`, `order_no`, `total_cents`, `item_count`, `status`, `ordered_at` |
| `order_items` | `order_item_id`, `tenant_id`, `order_id`, `sku`, `name`, `quantity`, `unit_cents` |
| `shipments` | `shipment_id`, `tenant_id`, `customer_id`, `order_id`, `carrier`, `tracking_no`, `status`, `shipped_at`, `delivered_at` |
| `returns` | `return_id`, `tenant_id`, `customer_id`, `order_id`, `reason_code`, `quantity`, `status`, `requested_at` |

계획서 §22의 DDL은 14개 테이블을 정의한다. 첫 14개 테이블과 컬럼 정의는 `001_schema.sql`에 대응한다. 현행 migrations에는 계획서 §22에 없는 `orders`, `order_items`, `shipments`, `returns`가 추가되어 총 18개다. 계획서 §22의 14개 정의에는 이 4개가 없다.

## 7. 테스트

`tests/`에는 `test_*.py` 기준 테스트 파일 43개가 있다. 테스트는 실행하지 않았다.

| 분류 | 파일 수 | 검증 내용 |
|---|---:|---|
| unit | 15 | reducer, ContextBroker budget, proposal verification, Team, VOC, graph 축, composition, prompt registration |
| contract | 4 | 계약 모델, 상태표, Team 계약, Core isolation |
| integration | 14 | API, Controller, DB, Graph, LLM audit, RAG, A2A 왕복 |
| e2e | 3 | Composer write channel, 운영 UI, root landing |
| security | 2 | scope 계약, PII redaction |
| live | 3 | classifier, LLM, response review live smoke |
| architecture | 2 | basement domain-free 경계, 다른 도메인 제공 경계 |

파일명으로 확인되는 세부 대상에는 `test_case_reducer.py`의 상태 전이·replay, `test_project_composition.py`의 등록·비활성·Port 조립, `test_openapi_surface.py`의 경로·scope, `test_remote_round_trip.py`의 Agent card·입력·실패·취소·인증, `test_prompt_registration.py`의 prompt allowlist와 빈 디렉터리가 있다.

아키텍처 경계 테스트는 `tests/architecture/test_basement_is_domain_free.py`, `tests/architecture/test_engine_serves_another_domain.py`, `tests/contract/test_core_isolation.py`에 있다.

## 8. 프롬프트

`prompts/`에는 4개 파일이 있다.

| 경로 | 버전 체계 |
|---|---|
| `prompts/judge/judge_v1.txt` | `v1` |
| `prompts/judge/arms/baseline_a_v1.txt` | `v1` |
| `prompts/judge/arms/baseline_b_v1.txt` | `v1` |
| `prompts/judge/arms/proposed_v1.txt` | `v1` |

코드의 `ALLOWED_PROMPT_KEYS`는 `app/tools/read_tools.py:117`에서 빈 `frozenset()`이다. 따라서 등록 허용 목록은 비어 있다. 등록 함수는 `*/**/*.v*.md`만 탐색하므로 현재의 `.txt` 4개는 이 함수의 후보 패턴에도 포함되지 않는다. 런타임 LLM은 DB `prompts`에서 `prompt_key`별 active row를 읽는다.

## 9. 미사용·잔존물

- `app/modules/customer_ops/response_review.py`의 `ResponseGenerationReviewTeam`은 존재하지만 `config/project.yaml`의 Team 목록에 없다.
- `app/modules/customer_ops/response_review_policy.py`는 소스에 있으나 현행 Team 선언은 없다.
- `legacy/final_project_cs/team_modules_v1/customer_ops/order_shipping.py`와 `return_exchange.py`는 legacy에만 있다. 현행 `config/project.yaml`에는 두 Team이 없다.
- `legacy/final_project_cs/team_modules_v1/prompts/order_shipping/`와 `return_exchange/`에는 `answer.v1.md`, `answer.repair.v1.md`가 있다.
- `app/modules/customer_ops/__pycache__/order_shipping.cpython-312.pyc`와 `return_exchange.cpython-312.pyc`가 있으나 대응하는 현행 `.py` 소스는 없다.
- `app/modules/customer_ops/__pycache__/response_review.cpython-312.pyc`와 `response_review_policy.cpython-312.pyc`는 소스가 함께 있다.
- `app/presentation/schemas/`는 디렉터리가 있으나 현재 파일 목록에 별도 소스가 없다.
- `app/core/case_runtime/`와 그 하위 분류 디렉터리에는 현재 `rg --files` 기준 별도 `.py` 파일이 없다.
- `app/modules/customer_ops/team_modules/`와 그 하위 `local_team_a`, `local_team_b`, `remote_team_demo`에는 현재 `rg --files` 기준 `.py` 파일이 없다.

## 출력 요약

1. 보고서 파일: [`program/research/_cs_구현현황.md`](C:/Users/playdata2/Documents/final_workspace/program/research/_cs_구현현황.md)
2. 정리한 항목 수: Team 1개, 계약 Pydantic 모델 6개, REST 엔드포인트 18개, MCP 도구 3개, A2A HTTP 경로 5개, 테이블 18개, 테스트 파일 43개
3. 계획서와 다른 점 중 눈에 띄는 5개

   - 계획서 §22는 14개 테이블을 정의하지만 migrations에는 18개가 있다.
   - `orders`가 계획서 §22에는 없고 `002_domain_commerce.sql`에 있다.
   - `order_items`가 계획서 §22에는 없고 `002_domain_commerce.sql`에 있다.
   - `shipments`가 계획서 §22에는 없고 `002_domain_commerce.sql`에 있다.
   - `returns`가 계획서 §22에는 없고 `002_domain_commerce.sql`에 있다.
