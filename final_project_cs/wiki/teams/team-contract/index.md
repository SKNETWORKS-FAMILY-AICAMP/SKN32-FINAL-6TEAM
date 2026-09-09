---
type: contract
title: Team 계약
description: TeamTask 입력과 TeamResult 출력의 모양. contract_version 1.0
status: draft
tags: [contract, agent]
owners: [human:미배정]
domain: neutral
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

**`context`가 핵심이다.** Team은 여기 담긴 것만 쓴다. 직접 읽지 않는다. → [team-boundary.md](../team-boundary.md)

### ★ `allowed_tools`는 과도기 호환 필드다

`[실측]` v8 §21이 명시한다.

> `allowed_tools`는 **현재 코드와의 과도기 호환 필드**다. 실행 규칙상 Team이 이 목록을 사용해 직접 호출하지 않는다.

**계약에 남아 있지만 Team이 쓰라고 있는 게 아니다.** 실제 용도는 둘이다.

| 쓰는 곳 | 무엇에 |
|---|---|
| Context Broker | **read 계획**을 세울 때의 상한 |
| Action Layer | **write 권한 검증**의 입력 |

**필드가 있다고 Team이 호출해도 된다는 뜻이 아니다.** 이게 `INV-CS-TEAM-004`가 아직 `review`인 이유이기도 하다 — 계약이 필드를 허용하는 형태라 정적 검사로 잡기 애매하다.

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

**`rationale_evidence_ids`가 근거 대조의 입력이다.** 여기 적힌 evidence가 Context/DB에 실재하는지 Core가 확인한다. → [../actions/evidence-check.md](../../actions/evidence-check.md)

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

`TeamResult`의 `outcome`·`next_action`이 Case 상태 전이를 만든다. → [../runtime/case-lifecycle.md](../../runtime/case-lifecycle.md)

## 계약을 바꾸려면

**`ConfigDict(extra='forbid')`다.** 필드를 임의로 추가할 수 없다.

## 원본 계약 문서(`handoff/04`)에서 낡은 것

`[실측]` 2026-09-06 대조. 규칙 부분(Team이 지킬 셋 · tool 규칙 · `outcome`/`next_action` 조합표)은 지금도 맞고 이 문서가 그걸 담고 있다. **예시와 상태 서술은 낡았다.**

| 원본이 적은 것 | 지금 |
|---|---|
| §1·§2 예시 Team = `OrderShippingTeam`·`ReturnExchangeTeam` | **둘 다 2026-08-18~19에 퇴역**해 `legacy/`로 갔다. 현행 여섯 Team은 [../index.md](../index.md) |
| §3 "prompt 등록 규칙은 설계됐으나 실 런타임에 배선되지 않았다(2026-08-17)" | 2026-08-18 배선됐고, 08-19 레거시 격리로 다시 깨졌다가 08-30 재수정 — `openai.py`가 `record_llm_call`을 부른다. → [../../../../wiki/governance/migration-scope/status.md](../../../../wiki/governance/migration-scope/status.md) |
| §3 "`prompts/billing/`·`prompts/technical/` 12개가 미배선 상태로 남아 있다" | 옛 도메인 프롬프트 12개는 `legacy/final_project_sample/prompts/`로 이동됐다 |

**계약 문서의 규칙은 오래가고 예시는 빨리 낡는다.** 원본을 읽을 땐 §0·§4·§5만 믿는다.

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

---

## 필드 전체 명세

`[실측]` 2026-09-03. 계약 원문의 필드·타입·제약을 전부 옮겼다.

→ **[fields.md](fields.md)**

**여기는 개념이고 거기는 명세다.** 구현할 때는 그쪽을 본다.

