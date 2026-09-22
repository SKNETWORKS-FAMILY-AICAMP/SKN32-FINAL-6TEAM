---
type: contract
title: Team 계약 필드 명세
description: TeamTask·TeamResult·Evidence·Manifest 의 필드·필수 여부·기본값 전체
status: draft
tags: [contract, architecture]
domain: neutral
---

# Team 계약 필드 명세

`[실측]` `wiki/records/handoff/` 계약 원문에서 절 단위로 옮겼다. **개념 설명은 [index.md](../index.md) 에 있다.**

`[실측]` `wiki/records/handoff/` 계약 문서와 절 단위로 대조해 **빠져 있던 필드·제약·숫자**를 채웠다. 대조 결과는 [반영률 실측](../../../../wiki/governance/migration-scope/coverage.md).

## 계약 호환 규칙

`[실측]` Enum 밖의 문자열은 validator가 거부한다. `contract_version`은 `"MAJOR.MINOR"` 형식이며, 같은 major에서 optional field를 추가하는 변경만 호환된다. major 변경본은 adapter 또는 migration 없이 Registry에 등록하지 않는다.

근거: `wiki/records/handoff/01_계약_Pydantic.md:7-13`

## `Evidence` 필드 계약

`[실측]` 모든 필드는 필수이며 기본값이 없다.

| 필드 | 타입 | 필수 | 제약 |
|---|---|---:|---|
| `evidence_id` | `str` | 예 | — |
| `source_type` | `Literal['customer_message', 'db', 'policy', 'tool_result', 'case_event', 'remote_agent']` | 예 | 열거값 밖 문자열 거부. ★`[정정 2026-09-10]` **여섯째 `remote_agent` 가 빠져 있었다**(`contracts.py:108`) — A2A 원격이 돌려준 근거를 구분하는 값이다 |
| `source_id` | `str` | 예 | `source_type='policy'`이면 `"{document_id}#c{chunk_no}"` 형식 |
| `claim` | `str` | 예 | — |
| `value` | `Any` | 예 | — |
| `confidence` | `float` | 예 | `0 <= confidence <= 1` |
| `observed_at` | `datetime` | 예 | — |

`source_type`·`source_id`·`observed_at`은 의무다. 근거 없는 문장을 답변에 넣지 않는다.

`[실측 2026-09-10]` **`ContextPack.token_budget: Literal[12000] = 12000`** 도 이 표에 빠져 있었다(`contracts.py:141`). **값이 하나로 고정된 필드**라 바꿀 수 없다 — 예산을 늘리려면 계약을 고쳐야 한다는 뜻이다.

근거: `wiki/records/handoff/01_계약_Pydantic.md:43-58`

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

근거: `wiki/records/handoff/01_계약_Pydantic.md:60-83`

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

근거: `wiki/records/handoff/01_계약_Pydantic.md:85-108`

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

근거: `wiki/records/handoff/01_계약_Pydantic.md:110-125`

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

근거: `wiki/records/handoff/01_계약_Pydantic.md:127-149`

## `TeamResult` 추가 일관성 규칙

`[실측]`

| 조건 | validator가 요구하는 값 |
|---|---|
| `next_action='respond'` | `answer` 필수 |
| `next_action='escalate'` | `failure_code` 또는 `warnings` 필수 |
| `answer is not None` | `evidence`가 비어 있으면 거부 |

근거: `wiki/records/handoff/01_계약_Pydantic.md:151-161`

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
| `policy_optional_capabilities` | `list[str]` | 아니오 | 기본값 `[]`; 값은 `capabilities` 안의 이름이어야 한다 |

### ★ `[2026-09-22]` `policy_optional_capabilities` — 왜 생겼나

`required_context` 는 **Team 단위**인데 정책 근거가 필요한지는 **capability 마다 다르다.**

| 예 | 정책이 필요한가 |
|---|---|
| `activity.check_cancelable` · `check_feasible` | **필요하다.** 취소 기한·위약금·기상 사유 판정이 규정 해석이다 |
| `activity.itinerary` (감시가 연 일정 관리) | **아니다.** 예보·운행·영업 같은 **실시간 사실**로 판단한다 |

한 Team 이 둘을 다 갖고 있어서, `policy` 를 선언하면 일정 관리까지 정책 0건에 막히고
빼면 취소 판정이 근거 없이 답하게 된다. 2026-09-17 에는 **빼는 쪽**을 골랐고(코퍼스에
여행 문서가 0건이었다), 그 때문에 정책 근거가 필요한 capability 도 RAG 없이 돌았다.

그래서 **예외 목록을 Team 이 선언한다.** Controller 는 이렇게 읽는다.

```
정책 RAG 를 돈다  =  "policy" in required_context  AND  선택된 capability ∉ policy_optional_capabilities
```

★**예외 목록은 「근거 없이 답해도 된다」는 뜻이 아니다.** 그 capability 는 근거를
**도구(`read.disruptions`·`read.place` …)로 직접 가져와** `TeamResult.evidence` 에 싣는다.
근거 없는 문장 금지(`CLAUDE.md` §0.1)는 그대로다 — 근거의 **출처**가 다를 뿐이다.

★계약 필드가 **늘었다.** 같은 major 의 optional 필드 추가라 `contract_version` 은 1.0 그대로다
(v6 §21). 안 적은 Team 은 예전과 똑같이 돈다.

근거: `wiki/records/handoff/01_계약_Pydantic.md:163-187`

## 선택적 capability 선택 계약

`[실측]` Team은 다음 메서드를 선택적으로 구현할 수 있다.

```python
def select_capability(intent: str | None, input_text: str) -> str | None: ...
```

Registry는 namespace 매칭보다 먼저 이 값을 묻는다. 반환값이 `None`이거나 메서드가 없으면 기존 규칙을 적용한다. 필수 Protocol 멤버가 아니며 `getattr` 기반 duck-typing으로 감지한다.

근거: `wiki/records/handoff/01_계약_Pydantic.md:189-197`

## `TeamModule` Protocol

`[실측]`

```python
class TeamModule(Protocol):
    manifest: TeamManifest
    async def execute(self, task: TeamTask) -> TeamResult: ...
```

Core가 사용하는 Team 표면은 `manifest`와 `execute()`뿐이다.

근거: `wiki/records/handoff/01_계약_Pydantic.md:199-208`

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

근거: `wiki/records/handoff/01_계약_Pydantic.md:210-219`

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

근거: `wiki/records/handoff/01_계약_Pydantic.md:221-231`

## 관계

- [index.md](../index.md) — 개념
- [../../../wiki/governance/migration-scope/coverage.md](../../../../wiki/governance/migration-scope/coverage.md) — 반영률
