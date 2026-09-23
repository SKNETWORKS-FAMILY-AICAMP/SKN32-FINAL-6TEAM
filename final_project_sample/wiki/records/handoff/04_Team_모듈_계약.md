# 04 — Team 모듈 계약

- 개정 이력: 2026-08-12 15:07 최초 작성 (v5 §14, §7-5)
- 소유: **S-TEAM** (`app/modules/customer_ops/{billing,technical}.py`, `app/tools/**`, `prompts/{billing,technical}/**`)
- 계약 모델: `01_계약_Pydantic.md`

## 0. Team 이 지켜야 할 3가지

1. **`TeamModule` Protocol 을 구현한다** — `manifest` 속성 + `async def execute(task: TeamTask) -> TeamResult`
2. **side effect 를 실행하지 않는다** — `ActionProposal` 만 반환한다
3. **근거 없이 답하지 않는다** — `answer` 를 채우면 `evidence` 가 비면 안 된다

★Core 는 Team 내부를 `import` 하지 않고, Team 도 `app/core/transition.py` 를 직접 호출하지 않는다.
Team 은 **입력(TeamTask)을 받아 출력(TeamResult)을 돌려주는 순수 경계**다. 상태 변경은 Controller 몫이다.

## 1. Billing/Subscription Team (v5 §14-1)

```python
manifest = TeamManifest(
    team_id='billing_subscription',
    display_name='Billing/Subscription Team',
    contract_name='a_cop.team_task',
    supported_contract_versions=['1.0'],
    capabilities=['billing.investigate', 'billing.refund_propose', 'subscription.explain'],
    accepted_case_types=['billing'],
    required_context=['case_state', 'policy', 'db_facts', 'history'],
    allowed_tools=['read.subscription', 'read.payment_history', 'read.policy'],
    knowledge_scope=['billing', 'subscription', 'refund'],
    max_steps=6, active=True, implementation_revision='...')
```

| 항목 | 내용 |
|---|---|
| 책임 | 결제·구독 상태 비교, 정책 근거 제시, 환불 proposal |
| prompt 3종 | `classify_billing`, `explain_billing`, `propose_refund` |
| read tool | subscription / payment_history / policy |
| write | ★`refund.request` **proposal 만**. 실제 환불 실행 없음 |
| 대표 시나리오 | **구독 해지 후 추가 결제** — 결제 이력·정책 확인 → 환불 요청을 승인 대기로 |

## 2. Technical Entitlement Team (v5 §14-2)

```python
manifest = TeamManifest(
    team_id='technical_entitlement',
    display_name='Technical Entitlement Team',
    contract_name='a_cop.team_task',
    supported_contract_versions=['1.0'],
    capabilities=['entitlement.diagnose', 'entitlement.propose_support_action'],
    accepted_case_types=['technical'],
    required_context=['case_state', 'policy', 'db_facts', 'history'],
    allowed_tools=['read.entitlement', 'read.account', 'read.incident', 'read.policy'],
    knowledge_scope=['entitlement', 'incident', 'technical'],
    max_steps=6, active=True, implementation_revision='...')
```

| 항목 | 내용 |
|---|---|
| 책임 | entitlement·계정·incident·정책 비교, 원인 분류, 해결 절차 제시 |
| prompt 3종 | `classify_entitlement`, `diagnose_entitlement`, `propose_support_action` |
| write | ★**실권한 변경 없음**. proposal 과 evidence 만 반환 |
| 대표 시나리오 | **Free/Pro 권한 동기화 오류** — entitlement·incident·정책 비교 후 해결 절차 제시 |

## 3. Response Generation & Review Team (DoD-29)

```python
manifest = TeamManifest(
    team_id='response_generation_review',
    display_name='Response Generation & Review Team',
    contract_name='a_cop.team_task',
    supported_contract_versions=['1.0'],
    capabilities=['response.generate_review'],
    accepted_case_types=[],
    required_context=['case_state', 'policy', 'db_facts', 'history'],
    allowed_tools=['read.policy'],
    knowledge_scope=['response_review'],
    max_steps=4, active=True, implementation_revision='...')
```

| 항목 | 내용 |
|---|---|
| 책임 | 모든 Case의 최종 응답 문장을 생성하고 검토하는 횡단 관심사 |
| 흐름 | 톤 결정 규칙 → GEN 초안 → 결정론 REV → LLM 톤 REV → 완료 |
| 결정론 REV | 금칙어, PII, `refund_amount`·`policy_ref` 사실 대조. `app/core/verification.py`의 범용 엔진과 도메인 정책 선언을 재사용 |
| 재시도 | 결정론 실패는 최초 시도 뒤 최대 3회 재시도. PII는 재시도 없이 즉시 `escalated` |
| 톤 실패 | 재시도하지 않고 `warnings[]`에 기록 |
| 출력 매핑 | `final_response_text`→`answer`, `status`→`outcome`, 재시도/이력→`decisions[]`, 반려 사유→`warnings[]`, escalation→`outcome='escalated'` + `next_action=escalate` |
| 라우팅 | `accepted_case_types=[]`; Controller 자동 배선은 이 범위에 포함하지 않음 |

도메인 금칙어·PII 정규식·톤 프로파일은 `response_review_policy.py`가 소유한다. Team은 manifest와 `async execute(task) -> TeamResult`만 제공하며 side effect를 실행하지 않는다.

## 4. prompt 등록 규칙

- 프롬프트는 파일(`prompts/<team>/<key>.v<N>.md`)로 두고 **`prompts` 테이블에 `sha256` 과 함께 등록**한다.
- `llm_calls.prompt_id` 가 FK 로 걸린다 — **어떤 프롬프트가 만든 답인지 추적 가능해야 한다**(v5 §8).
- `UNIQUE(prompt_key, version)`, `UNIQUE(prompt_key, sha256)` — 같은 내용을 다른 버전으로 두 번 등록할 수 없다.
- 프롬프트를 고치면 **버전을 올린다.** 같은 버전의 내용을 덮어쓰면 평가 재현성이 깨진다.

## 4. tool 규칙

- `TeamManifest.allowed_tools` **밖의 tool 호출은 거부**된다(`ToolNotAllowed`).
- read tool 은 `tenant_id` + `customer_id` 범위를 **인자가 아니라 TeamTask.context 에서** 받는다.
  Team 이 임의 tenant 를 조회할 수 없어야 한다.
- ★**LLM 이 자유 SQL 을 쓰지 않는다.** tool 은 이름이 붙은 함수뿐이다.
- loop guard: 동일 tool + 정규화 arguments signature 가 **2회 반복되면 `escalated`**(`06` §2).
- Case 당 tool call **12회**, Team task **6회**, graph step **12** 상한.

## 5. 실패·대기 처리

| 상황 | `outcome` | `next_action` | 함께 채울 것 |
|---|---|---|---|
| 정상 답변 | `completed` | `respond` | `answer` + `evidence` |
| 고객 정보 부족 | `waiting` | `wait_for_input` | `wait_reason='customer_input'`, `required_input_schema` |
| 승인 필요 | `waiting` | `wait_for_approval` | `wait_reason='human_approval'`, `action_proposals` ≥1 |
| 다른 Team 필요 | `handoff` | `handoff` | `handoff_capability` |
| 정책 근거 없음 | `escalated` | `escalate` | `failure_code`, `warnings` |
| 재시도 소진 | `failed` | `escalate` | `failure_code` |

★**정책 근거를 못 찾았을 때 일반 지식으로 답을 만들지 않는다.** `escalate` 가 정답이다
(`CLAUDE.md` §0.1). `ContextPack.degraded=true` 인 상태에서 확정 답변을 내지 않는다.

## 6. 검증 (DoD 8)

```powershell
python -m pytest tests/contract/test_team_contract.py -q    # Protocol + manifest 호환
python -m pytest tests/contract/test_core_isolation.py -q   # Core 가 Team 내부를 import 하지 않음
python -m pytest tests/unit/teams -q                        # 시나리오별 TeamResult 일관성
```

각 Team golden 20건(v5 §3 In) 결과는 S-EVAL 이 `eval/` 에서 돌린다.
