# DoD-25 — `ContextPack.degraded=true` 면 자동 실행하지 않는다

- v7 §27 항목 25 / §9-E / 검증 방법: degraded fixture 에서 proposal 이 실행되지 않고 `escalated` 가 되는지
- 실행: 2026-08-16
- 판정: 통과

## 재현 명령

```powershell
python -m pytest tests/integration/controller/test_proposal_guard_blocks.py -q
```

## 실제 출력

```
5 passed

test_core_blocks_proposals_when_context_is_degraded
  DegradedBroker  → ContextPack(degraded=True, omissions=["policy_rag:all"])
  ProposingTeam   → degraded 를 **보지 않고** ActionProposal 을 낸다
  결과:
    action_requests 행 수 = 0
    event_type = guardrail_escalated
    guardrail  = degraded_context_blocks_action
    observed   = ['ContextPack.degraded=true 상태에서 나온 제안은 자동 실행하지 않는다']
```

## 무엇이 바뀌었나

**전에는 Team 이 각자 스스로 검사했다:**

```python
# app/modules/customer_ops/billing.py:56 · technical.py:42
if task.context.degraded:
    return TeamResult(..., outcome="escalated", failure_code="degraded_context", ...)
```

★**이건 Team 의 선의다.** 두 Team 이 지키고 있었을 뿐,
**새 Team 이 그 줄을 빠뜨리면 아무도 막지 않았다.**

> 검사하지 않는 규칙은 지켜지지 않는다.

지금은 `Controller._reject_unverified()` 가 Team 결과를 받은 직후 막는다.
Team 의 자율 검사는 남겨 뒀다 — 빠른 실패는 여전히 좋다.

## 판정 근거

| 요구 | 결과 |
|---|---|
| degraded 면 proposal 이 실행 경로에 안 들어감 | **통과** — `action_requests` 0행 |
| `escalated` 로 전환 | **통과** |
| ★Team 이 검사를 빼먹어도 막힘 | **통과** — degraded 를 안 보는 Team 으로 검증 |
| 기존 Team 의 자율 검사 유지 | **통과** — 196건 전체 통과 |
| degraded 신호 자체가 강제됨 | **통과** — `degraded=True` 인데 `omissions` 가 비면 계약이 거부 (DoD-05) |

## ★대조는 위조할 수 없는 쪽으로 한다

Controller 는 **자기가 만든** `task.context` 를 본다.
Team 이 돌려준 `result.context` 를 쓰면 Team 이 degraded 여부를 스스로 정할 수 있어
검사가 무의미해진다.

## 한계

- degraded 는 지금 **RAG 실패 또는 예산 절삭**에서만 켜진다.
  다른 축(예: DB 조회 부분 실패)은 degraded 로 이어지지 않는다
- 사람이 승인하면 degraded Case 도 진행된다 — **금지되는 것은 "자동" 실행이다.**
  승인 화면에 degraded 배너가 뜨지만, 승인자가 그것을 읽었는지는 시스템이 모른다
