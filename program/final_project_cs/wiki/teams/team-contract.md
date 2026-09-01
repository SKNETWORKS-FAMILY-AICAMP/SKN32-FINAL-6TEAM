---
type: contract
title: Team 계약
description: TeamTask 입력과 TeamResult 출력의 모양. contract_version 1.0
status: draft
tags: [contract, agent]
owners: [human:미배정]
---

# Team 계약

`app/core/contracts.py`

**Core가 Team에 대해 아는 것은 이 계약뿐이다.** Team의 graph·prompt·retrieval을 import하지 않는다.

## 입력 — `TeamTask`

```python
contract_name: "a_cop.team_task"
contract_version: "1.0"

task_id / run_id / case_id : UUID
team_id      : str
capability   : str          ← 무엇을 하라는 것인가
case_version : int          ← 낙관적 동시성 기준
input_text   : str          1~12,000자
context      : ContextPack  ← 읽기 자료. 여기 있는 것만 쓴다
allowed_tools: list[str]
deadline_at  : datetime
resume       : bool
resume_node  : ResumeNode | None
```

**`context`가 핵심이다.** Team은 여기 담긴 것만 쓴다. 직접 읽지 않는다. → [team-boundary.md](team-boundary.md)

### `ContextPack`

```python
pack_id / case_id / team_id / tenant_id
knowledge_scope : list[str]
current_state   : dict
evidence        : list[Evidence]   최대 40개
history_summary : str              최대 10,000자
similar_cases   : list[dict]       최대 3개
token_budget    : 12000            ← 고정
estimated_input_tokens : int
degraded        : bool             ← 예산 때문에 깎였는가
omissions       : list[str]        ← 무엇이 빠졌는가
```

`[실측]` **`token_budget`이 12,000으로 고정돼 있다.** `Literal[12000]`이라 바꾸려면 계약 변경이다.

**`degraded`와 `omissions`가 중요하다.** 예산 때문에 자료가 깎였으면 Team이 그걸 알고 판단해야 한다. 모르고 답하면 근거 없는 답이 된다.

## 출력 — `TeamResult`

```python
contract_name: "a_cop.team_result"
contract_version: "1.0"

outcome     : completed | waiting | handoff | escalated | failed
answer      : str | None            최대 6,000자
confidence  : float                 0~1
evidence    : list[Evidence]
decisions   : list[dict]
action_proposals : list[ActionProposal]   ← 제안만. 실행 아님
next_action : NextAction
wait_reason : WaitReason | None
required_input_schema : dict | None
handoff_capability    : str | None
failure_code          : str | None
warnings    : list[str]
```

### `NextAction` 값

```
continue · wait_for_input · wait_for_approval · call_tool
handoff · respond · escalate
```

### `ActionProposal`

```python
action_type   : str
arguments     : dict
idempotency_key : str          8~128자
approval_required : bool
risk_level    : low | medium | high
rationale_evidence_ids : list[str]   ← 근거 대조용
```

**`rationale_evidence_ids`가 근거 대조의 입력이다.** 여기 적힌 evidence가 Context/DB에 실재하는지 Core가 확인한다. → [../actions/evidence-check.md](../actions/evidence-check.md)

## 계약이 스스로 검사하는 것

`[실측]` `TeamResult`에 `model_validator`가 있다. 모순된 조합을 만들 수 없다.

| `next_action` | 강제되는 것 |
|---|---|
| `wait_for_input` | `wait_reason == "customer_input"` **그리고** `required_input_schema`가 있어야 함 |
| `wait_for_approval` | `wait_reason == "human_approval"` **그리고** `action_proposals`가 최소 1건 |
| `handoff` | `handoff_capability`가 있어야 함 |

**"승인 대기인데 제안이 없다"는 상태를 만들 수 없다.** 계약이 막는다.

## Case 상태

`CaseStatus`

```
new · classifying · routing · running
waiting_input · waiting_approval · waiting_external · resuming
resolved · escalated · failed · cancelled
```

`TeamResult`의 `outcome`·`next_action`이 Case 상태 전이를 만든다. → [../runtime/case-lifecycle.md](../runtime/case-lifecycle.md)

## 계약을 바꾸려면

**`ConfigDict(extra='forbid')`다.** 필드를 임의로 추가할 수 없다.

바꿀 때 필요한 것.

1. `contract_version` 상향
2. 회귀 테스트
3. 모든 Team 확인

**계약 변경은 비싸다.** 새 정보를 넣을 자리를 먼저 찾는다.

| 넣고 싶은 것 | 기존 자리 |
|---|---|
| 재시도 횟수 | `decisions[]` |
| 검토 이력 | `decisions[]` |
| 반려 사유 | `warnings[]` |
| 에스컬레이션 | `outcome='escalated'` + `next_action` |

## 불변식

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-TEAM-001` | manifest는 프로토콜을 구현한다 | automated | `tests/contract/test_team_contract.py::test_team_manifests_implement_protocol` |
| `INV-CS-TEAM-002` | manifest scope는 정확히 선언된다 | automated | `tests/contract/test_team_contract.py::test_manifest_scopes_are_exact` |

## 관계

- [team-boundary.md](team-boundary.md) — 계약 밖의 규칙
- [team-registry.md](team-registry.md) — 등록
- [../context/context-broker.md](../context/context-broker.md) — `ContextPack`을 만드는 쪽
- [../actions/action-proposal.md](../actions/action-proposal.md) — `ActionProposal`을 받는 쪽
- [../runtime/case-lifecycle.md](../runtime/case-lifecycle.md) — 상태 전이
