---
type: contract
title: Team 계약 필드 명세
description: TeamTask·TeamResult·Evidence·Manifest 의 필드·필수 여부·기본값 전체
status: draft
tags: [contract, architecture]
---

# Team 계약 필드 명세

`[실측]` `docs/handoff/` 계약 원문에서 절 단위로 옮겼다. **개념 설명은 [index.md](../index.md) 에 있다.**

`[실측]` `docs/handoff/` 계약 문서와 절 단위로 대조해 **빠져 있던 필드·제약·숫자**를 채웠다. 대조 결과는 [반영률 실측](../../../../wiki/governance/migration-scope/coverage.md).

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

## 관계

- [index.md](../index.md) — 개념
- [../../../wiki/governance/migration-scope/coverage.md](../../../../wiki/governance/migration-scope/coverage.md) — 반영률
