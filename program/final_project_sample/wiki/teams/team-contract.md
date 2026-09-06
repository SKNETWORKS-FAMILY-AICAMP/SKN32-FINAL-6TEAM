---
type: concept
title: Team 입출력 계약
description: Team이 받는 작업과 반환하는 결과, 그리고 필수 필드를 설명한다.
status: draft
tags: [architecture, contract, api]
---

Team은 `manifest`를 공개하고 `execute(TeamTask) -> TeamResult`를 비동기로 구현하는 객체다. `[실측]` Core가 요구하는 표면은 이 두 가지뿐이다. (`acop_basement/core/contracts.py:320`)

```python
@runtime_checkable
class TeamModule(Protocol):
    manifest: TeamManifest

    async def execute(self, task: TeamTask) -> TeamResult: ...
```

근거: `acop_basement/core/contracts.py:320`

## Team의 선언

`TeamManifest`는 Team의 식별자, 처리 범위와 실행 한도를 선언한다. 정의되지 않은 추가 필드는 허용되지 않는다. `[실측]` (`acop_basement/core/contracts.py:303`)

| 구분 | 필드 |
|---|---|
| 생성 시 필수 `[실측]` | `team_id`, `display_name`, `contract_name`, `supported_contract_versions`, `capabilities`, `accepted_case_types`, `required_context`, `allowed_tools`, `knowledge_scope`, `implementation_revision` |
| 기본값이 있는 필드 `[실측]` | `max_steps=6`, `active=True` |
| 고정값 `[실측]` | `contract_name`은 `"a_cop.team_task"` |
| 제한값 `[실측]` | `capabilities`는 최소 1개, `max_steps`는 1 이상 12 이하 |
| `required_context` 허용값 `[실측]` | `"case_state"`, `"policy"`, `"db_facts"`, `"history"` |

근거: `acop_basement/core/contracts.py:303`

선언형 구현은 선언값으로 manifest를 만들되 `contract_name="a_cop.team_task"`, 지원 버전 `["1.0"]`, `active=True`, 구현 리비전 `"declarative.v1"`을 직접 채운다. `[실측]` (`acop_basement/teams/declarative.py:63`)

계약 테스트는 Team 인스턴스가 `TeamModule`로 인식되는지, manifest가 `TeamManifest`인지, 계약 이름·지원 버전·실행 단계·활성 상태가 기대값인지 검사한다. `[실측]` 이 테스트는 `execute()`를 호출해 반환 형식까지 검사하지는 않는다. (`tests/contract/test_team_contract.py:7`)

## Team이 받는 값

`execute()`의 입력은 `TeamTask` 한 건이다. `[실측]` (`acop_basement/core/contracts.py:330`)

| 구분 | 필드 |
|---|---|
| 생성 시 필수 `[실측]` | `task_id`, `run_id`, `case_id`, `team_id`, `capability`, `case_version`, `input_text`, `context`, `allowed_tools`, `deadline_at` |
| 기본값이 있는 필드 `[실측]` | `contract_name="a_cop.team_task"`, `contract_version="1.0"`, `resume=False`, `resume_node=None` |
| 제한값 `[실측]` | `input_text`는 1자 이상 12,000자 이하 |

근거: `acop_basement/core/contracts.py:165`

`context`는 `ContextPack`이다. 생성 시 필수 필드는 `pack_id`, `case_id`, `team_id`, `tenant_id`, `knowledge_scope`, `current_state`, `estimated_input_tokens`다. `[실측]` (`acop_basement/core/contracts.py:122`)

`ContextPack.token_budget`은 `12000`으로 고정된다. `estimated_input_tokens`가 이를 넘으면 검증에 실패하고, `degraded=True`이면 비어 있지 않은 `omissions`가 필요하다. `[실측]` (`acop_basement/core/contracts.py:141`, `acop_basement/core/contracts.py:146`)

다음 입력 정합성도 모델 생성 시 검사된다. `[실측]`

- `resume=True`이면 `resume_node`가 있어야 한다. (`acop_basement/core/contracts.py:185`)
- `resume=False`이면 `resume_node`가 없어야 한다. (`acop_basement/core/contracts.py:187`)
- `TeamTask`와 `ContextPack`의 `case_id`가 같아야 한다. (`acop_basement/core/contracts.py:189`)
- `TeamTask`와 `ContextPack`의 `team_id`가 같아야 한다. (`acop_basement/core/contracts.py:191`)

계약 테스트는 빈 `input_text`, 잘못된 resume 조합, 서로 다른 `case_id`를 실제 거부 대상으로 둔다. `[실측]` (`tests/contract/test_contracts.py:230`, `tests/contract/test_contracts.py:240`, `tests/contract/test_contracts.py:246`)

## Team이 돌려주는 값

`execute()`의 반환값은 `TeamResult`다. `[실측]` (`acop_basement/core/contracts.py:330`)

| 구분 | 필드 |
|---|---|
| 생성 시 필수 `[실측]` | `task_id`, `run_id`, `team_id`, `outcome`, `confidence`, `next_action` |
| 기본값이 있는 식별 필드 `[실측]` | `contract_name="a_cop.team_result"`, `contract_version="1.0"` |
| 기본값이 있는 내용 필드 `[실측]` | `answer=None`, `evidence=[]`, `decisions=[]`, `action_proposals=[]`, `wait_reason=None`, `required_input_schema=None`, `handoff_capability=None`, `failure_code=None`, `warnings=[]` |
| `outcome` 허용값 `[실측]` | `"completed"`, `"waiting"`, `"handoff"`, `"escalated"`, `"failed"` |
| 제한값 `[실측]` | `answer`는 최대 6,000자, `confidence`는 0 이상 1 이하 |

근거: `acop_basement/core/contracts.py:223`

`next_action`에 따라 다음 필드가 조건부로 필요하다. `[실측]`

- `WAIT_FOR_INPUT`: `wait_reason="customer_input"`과 `required_input_schema`
- `WAIT_FOR_APPROVAL`: `wait_reason="human_approval"`과 하나 이상의 `action_proposals`
- `HANDOFF`: `handoff_capability`
- `RESPOND`: 비어 있지 않은 `answer`
- `ESCALATE`: `failure_code` 또는 하나 이상의 `warnings`

근거: `acop_basement/core/contracts.py:244`

답변이 있으면 하나 이상의 `evidence`가 필요하다. 제안의 `rationale_evidence_ids`는 같은 결과의 evidence를 가리켜야 한다. `[실측]` (`acop_basement/core/contracts.py:272`, `acop_basement/core/contracts.py:287`)

선언형 구현은 근거가 없거나 초안을 만들지 못하면 `outcome="escalated"`인 결과를 돌려주고, 초안 생성에 성공하면 `outcome="completed"`, `next_action=RESPOND`, `confidence=0.6`인 결과를 돌려준다. `[실측]` (`acop_basement/teams/declarative.py:128`, `acop_basement/teams/declarative.py:138`, `acop_basement/teams/declarative.py:157`)

## 관계

- [Team 경계](team-boundary.md)
- [Team 레지스트리](team-registry.md)
