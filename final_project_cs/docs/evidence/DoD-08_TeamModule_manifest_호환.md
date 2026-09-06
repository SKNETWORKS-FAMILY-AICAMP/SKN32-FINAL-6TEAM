# DoD-08 — Billing/Technical Team 이 TeamModule Protocol·manifest 호환 검사를 통과한다

- v5 §20 항목 8 / 검증 방법: contract test
- 실행: 2026-08-12 23:20 · 실측 원문 `docs/evidence/_raw/DoD-08.md`
- 판정: 통과

> ★2026-09-06 낡음 확인 — 제목의 Billing/Technical Team은 2026-08-18에 퇴역했다. `BillingSubscriptionTeam`·`TechnicalEntitlementTeam` manifest는 없다. 남는 건 기제(manifest 계약 테스트·Core 격리 AST)뿐이라 현행 Team으로 다시 써야 한다. 대조 기록: `program/final_project_cs/wiki/quality/dod-evidence-drift.md`

## 재현 명령

```powershell
python -m pytest tests/contract/test_team_contract.py tests/contract/test_core_isolation.py -q
```

## 실제 출력

```
3 passed, 1 warning in 1.15s
```

## 판정 근거 1 — manifest 가 계약과 일치 (Claude 독립 확인)

```
BillingSubscriptionTeam(self, tools: 'ReadToolbox', llm: 'LLM | None' = None)
  manifest: billing_subscription
  allowed_tools = ['read.subscription', 'read.payment_history', 'read.policy']

TechnicalEntitlementTeam(self, tools: 'ReadToolbox', llm: 'Any | None' = None)
  manifest: technical_entitlement
  allowed_tools = ['read.entitlement', 'read.account', 'read.incident', 'read.policy']
```

`docs/handoff/04_Team_모듈_계약.md` §1·§2 의 `allowed_tools` 와 정확히 일치한다.
LLM 이 **주입 가능**하므로 테스트가 결정적으로 돌아간다(실제 호출 없음).

## 판정 근거 2 — ★Core 격리 (Claude 독립 AST 검사)

`app/core/**` 의 모든 `.py` 를 AST 로 파싱해 `app.modules` / `app.presentation` /
`app.infrastructure` import 를 찾았다:

```
위반: 없음 (Core 가 Team/API/DB 를 import 하지 않음)
```

v5 §7-5 — "Core 는 Team 내부 graph/prompt/retrieval 을 import 하지 않고
manifest 와 `execute()` 만 사용한다"가 지켜진다.
S-CTRL 이 Registry 를 추가한 뒤에도 **재검사해서 위반 0** 을 확인했다.

## 판정 근거 3 — 계약 validator 가 안전 규칙을 강제한다

`tests/contract/test_contracts.py`(21건)가 다음을 거부함을 증명한다:
- 근거(evidence) 없는 `answer`
- `approval_required=True` 제안이 있는데 `next_action != wait_for_approval`
- 결과에 없는 evidence 를 근거로 든 `ActionProposal`

즉 **"승인 없이 실행하지 않는다"가 문서가 아니라 계약이 거부하는 것**이다(`CLAUDE.md` §0.2).

## 한계

- Team 이 **실제 LLM 으로** 두 시나리오를 처리한 결과는 이 항목이 아니라
  DoD-15/16(평가)에서 측정한다. 여기서는 계약 준수만 본다.
- 각 Team golden 20건(v5 §3 In) 대조는 평가 하네스 몫이다.
