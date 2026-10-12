# 01 — 계약: Pydantic 모델

- 개정 이력: 2026-08-12 15:07 최초 작성 (v5 §7 을 실행 가능한 형태로 정리)
- 구현체: `app/core/contracts.py` (**소유: Claude-Core**. 다른 스트림은 읽기만 한다)
- ★이 문서와 `app/core/contracts.py` 가 어긋나면 **결함**이다. 바꿀 때는 **이 문서를 먼저** 고친다.

## 0. 전 모델 공통 규칙

- 모든 계약 모델은 `model_config = ConfigDict(extra='forbid')`.
  조용한 필드 유입을 막는다. 우회(`extra='allow'`, `**kwargs` 통과)는 계약 위반이다.
- Enum 밖의 문자열은 validator 가 거부한다.
- `contract_version` 은 `"MAJOR.MINOR"`. **같은 major 의 optional field 추가만 호환**이다(v5 §7-4).
  major 변경은 adapter 또는 migration 없이 registry 에 등록하지 않는다.

## 1. Enum

```python
class CaseStatus(str, Enum):
    NEW = 'new'
    CLASSIFYING = 'classifying'
    ROUTING = 'routing'
    RUNNING = 'running'
    WAITING_INPUT = 'waiting_input'
    WAITING_APPROVAL = 'waiting_approval'
    WAITING_EXTERNAL = 'waiting_external'
    RESUMING = 'resuming'
    RESOLVED = 'resolved'
    ESCALATED = 'escalated'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class NextAction(str, Enum):
    CONTINUE = 'continue'
    WAIT_FOR_INPUT = 'wait_for_input'
    WAIT_FOR_APPROVAL = 'wait_for_approval'
    CALL_TOOL = 'call_tool'
    HANDOFF = 'handoff'
    RESPOND = 'respond'
    ESCALATE = 'escalate'
```

## 2. Evidence — 모든 주장에 출처를 붙인다

```python
class Evidence(BaseModel):
    model_config = ConfigDict(extra='forbid')
    evidence_id: str
    source_type: Literal['customer_message', 'db', 'policy', 'tool_result', 'case_event']
    source_id: str
    claim: str
    value: Any
    confidence: float = Field(ge=0, le=1)
    observed_at: datetime
```

★`source_type`·`source_id`·`observed_at` 은 **의무**다. 근거 없는 문장을 답변에 넣지 않는다
(`CLAUDE.md` §0.1). `policy` 근거의 `source_id` 는 `"{document_id}#c{chunk_no}"` 형식을 쓴다.

## 3. ContextPack

```python
class ContextPack(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pack_id: UUID
    case_id: UUID
    team_id: str
    tenant_id: str
    knowledge_scope: list[str]
    current_state: dict[str, Any]
    evidence: list[Evidence] = Field(default_factory=list, max_length=40)
    history_summary: str = Field(default='', max_length=10000)
    similar_cases: list[dict[str, Any]] = Field(default_factory=list, max_length=3)
    token_budget: Literal[12000] = 12000
    estimated_input_tokens: int = Field(ge=0)
    degraded: bool = False
    omissions: list[str] = Field(default_factory=list)
```

- `estimated_input_tokens` 는 **`tiktoken` 실측**이다. 문자수÷4 같은 추정 금지.
- 예산 초과로 무언가를 뺐으면 **`omissions` 에 이름을 남긴다.** 신호 없는 축소는 폴백이다.
- `degraded=true` 는 RAG 장애 등으로 근거가 부족한 상태 — 평가에서 **별도 집계**한다.
- 예산·제거 순서는 `06_가드레일_수치.md` §1.

## 4. TeamTask

```python
class TeamTask(BaseModel):
    model_config = ConfigDict(extra='forbid')
    contract_name: Literal['a_cop.team_task'] = 'a_cop.team_task'
    contract_version: Literal['1.0'] = '1.0'
    task_id: UUID
    run_id: UUID
    case_id: UUID
    team_id: str
    capability: str
    case_version: int
    input_text: str = Field(min_length=1, max_length=12000)
    context: ContextPack
    allowed_tools: list[str]
    deadline_at: datetime
    resume: bool = False
    resume_node: str | None = None
```

- `case_version` 은 task 발행 시점의 Case version. Team 결과를 merge 할 때 이 값으로 충돌을 판정한다.
- `allowed_tools` 는 `TeamManifest.allowed_tools` 의 부분집합이다. **밖의 tool 호출은 거부**된다.
- `resume_node` 는 `validate_input | execute_approved_action | verify_external_result` 중 하나.

## 5. ActionProposal — Team 은 제안까지만 한다

```python
class ActionProposal(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action_type: str
    arguments: dict[str, Any]
    idempotency_key: str = Field(min_length=8, max_length=128)
    approval_required: bool
    risk_level: Literal['low', 'medium', 'high']
    rationale_evidence_ids: list[str] = Field(default_factory=list)
```

★**Team 은 side effect 를 실행하지 않는다**(`CLAUDE.md` §0.2). Controller 가 allowlist·scope·승인·idempotency 를 검증한다.
★`idempotency_key` 는 Team 이 제안한 값이 아니라 **서버가 재계산한 값**이 최종이다
(`sha256(tenant_id + request_id + action_type + business_subject)`, v5 §10-1).

## 6. TeamResult

```python
class TeamResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    contract_name: Literal['a_cop.team_result'] = 'a_cop.team_result'
    contract_version: Literal['1.0'] = '1.0'
    task_id: UUID
    run_id: UUID
    team_id: str
    outcome: Literal['completed', 'waiting', 'handoff', 'escalated', 'failed']
    answer: str | None = Field(default=None, max_length=6000)
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    action_proposals: list[ActionProposal] = Field(default_factory=list)
    next_action: NextAction
    wait_reason: Literal['customer_input', 'human_approval', 'external_callback'] | None = None
    required_input_schema: dict[str, Any] | None = None
    handoff_capability: str | None = None
    failure_code: str | None = None
    warnings: list[str] = Field(default_factory=list)
```

**일관성 규칙** (validator 로 강제한다):

| `next_action` | 반드시 채워야 하는 것 |
|---|---|
| `wait_for_input` | `wait_reason='customer_input'`, `required_input_schema` |
| `wait_for_approval` | `wait_reason='human_approval'`, `action_proposals` 최소 1건 |
| `handoff` | `handoff_capability` |
| `respond` | `answer` |
| `escalate` | `failure_code` 또는 `warnings` |

★`answer` 가 있는데 `evidence` 가 비어 있으면 **거부**한다(`CLAUDE.md` §0.1).

## 7. TeamManifest

```python
class TeamManifest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    team_id: str
    display_name: str
    contract_name: Literal['a_cop.team_task']
    supported_contract_versions: list[str]
    capabilities: list[str] = Field(min_length=1)
    accepted_case_types: list[str]
    required_context: list[Literal['case_state', 'policy', 'db_facts', 'history']]
    allowed_tools: list[str]
    knowledge_scope: list[str]
    max_steps: int = Field(default=6, ge=1, le=12)
    active: bool = True
    implementation_revision: str
```

## 8. TeamModule Protocol — Core 가 Team 을 보는 유일한 창

```python
class TeamModule(Protocol):
    manifest: TeamManifest
    async def execute(self, task: TeamTask) -> TeamResult: ...
```

★**Core 는 Team 내부(graph · prompt · retrieval)를 `import` 하지 않는다.** `manifest` 와 `execute()` 만 쓴다.
이 경계는 `tests/contract/test_core_isolation.py` 가 import 검사로 강제한다.

## 9. Port (Phase 2 교체 지점)

```python
class MessageBrokerPort(Protocol):
    async def publish(self, topic: str, payload: dict, dedupe_key: str) -> str: ...
    async def ack(self, message_id: str) -> None: ...
```

MVP 구현체는 `OutboxBrokerAdapter`(outbox 테이블 + background worker).
`RedisStreamsAdapter` 는 **같은 Port 를 구현하는 Phase 2 대상**이며 지금 본체를 만들지 않는다.

## 10. 예외

```python
class StateConflict(Exception): ...        # optimistic concurrency 실패 (affected row 0)
class ContractViolation(Exception): ...    # 계약 검증 실패
class ToolNotAllowed(Exception): ...       # allowlist 밖 tool 호출
class GuardrailExceeded(Exception): ...    # step/tool/token/cost 상한 초과
class ScopeDenied(Exception): ...          # scope 부족
```

★**예외를 삼키지 않는다.** 폴백 금지(`RULE.md` §3.2).
