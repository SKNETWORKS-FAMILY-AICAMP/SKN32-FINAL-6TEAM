# DoD-08 — Billing/Technical Team 이 TeamModule Protocol·manifest 호환 검사를 통과한다

- v5 §20 항목 8 / 검증 방법: contract test
- 실행: 2026-08-12 23:20 · 실측 원문 `wiki/records/evidence/_raw/DoD-08.md`
- 판정: 통과

## ★2026-09-06 갱신 — 판정은 유효하고, 낡은 이름·수치·경로만 현행으로 고쳤다


★**이 evidence 가 증명한 대상이 사라졌다.** 제목과 판정 근거 1 이
`BillingSubscriptionTeam`·`TechnicalEntitlementTeam` 의 manifest 인데
**둘 다 2026-08-18 에 퇴역한 Team 이다**(v8 §10, `CLAUDE.md` 머리말).
21·13 처럼 "라벨만 옛것" 인 경우와 다르다.

| 낡았던 것 | 지금 (실측 2026-09-06) |
|---|---|
| 대상 Team 둘 | **없다.** 지금 등록 Team 은 여섯 |
| 재현 출력 `3 passed` | **3 passed** (같다 — 계약 테스트는 Team 목록을 순회한다) |

```powershell
python -m pytest tests/contract/test_team_contract.py tests/contract/test_core_isolation.py -q
→ 3 passed
```

지금 이 검사가 실제로 도는 대상 여섯:

```
catalog_verification · fulfillment_logistics · procurement_order_payment
response_review · return_refund · voc_store_manager
```

★**남는 것은 기제다.** 이 DoD 가 요구한 것은 "특정 Team 둘이 통과한다" 가
아니라 **"등록된 Team 이 `TeamModule` Protocol 과 manifest 계약을 지킨다"**
이고, 계약 테스트가 등록 목록을 순회하므로 Team 이 바뀌어도 성립한다.
그래서 판정은 유효하되, **이 문서의 옛 출력을 「지금 그렇다」로 읽으면 안 된다.**

2026-09-06 에 그 기제를 한 겹 더 두껍게 했다 —
`tests/contract/test_team_tool_discipline.py` 가 여섯 Team 의 인프라 직접
import 를 AST 로 막고, tool allowlist 가 런타임에 실제로 차단하는지 본다
(DoD-22 의 근거가 없던 것을 채우며 함께 만들었다).


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

`wiki/records/handoff/04_Team_모듈_계약.md` §1·§2 의 `allowed_tools` 와 정확히 일치한다.
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
