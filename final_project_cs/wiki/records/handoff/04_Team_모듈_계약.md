# 04 — Team 모듈 계약

- 개정 이력: 2026-08-12 15:07 최초 작성 (v5 §14, §7-5) · 2026-08-17 커머스 도메인
  실제 코드(`OrderShippingTeam`/`ReturnExchangeTeam`)로 예시 갱신 — 엔진(`app/core`)은
  그대로이고 어휘만 바뀌었다(`app/modules/customer_ops/verification_policy.py` 의
  도메인 교체 원칙과 동일)
- 소유: **S-TEAM** (`app/modules/customer_ops/{order_shipping,return_exchange}.py`, `app/tools/**`)
- 계약 모델: `01_계약_Pydantic.md`

## 0. Team 이 지켜야 할 3가지

1. **`TeamModule` Protocol 을 구현한다** — `manifest` 속성 + `async def execute(task: TeamTask) -> TeamResult`
2. **side effect 를 실행하지 않는다** — `ActionProposal` 만 반환한다
3. **근거 없이 답하지 않는다** — `answer` 를 채우면 `evidence` 가 비면 안 된다

★Core 는 Team 내부를 `import` 하지 않고, Team 도 `app/core/transition.py` 를 직접 호출하지 않는다.
Team 은 **입력(TeamTask)을 받아 출력(TeamResult)을 돌려주는 순수 경계**다. 상태 변경은 Controller 몫이다.

## 1. Order/Shipping Team (실제 코드: `app/modules/customer_ops/order_shipping.py`)

```python
manifest = TeamManifest(
    team_id='order_shipping',
    display_name='Order/Shipping Team',
    contract_name='a_cop.team_task',
    supported_contract_versions=['1.0'],
    capabilities=['order.investigate', 'refund.propose'],
    accepted_case_types=['order', 'shipping'],
    required_context=['case_state', 'policy', 'db_facts', 'history'],
    allowed_tools=['read.order', 'read.shipment', 'read.policy'],
    knowledge_scope=['order', 'shipping', 'refund'],
    max_steps=6, active=True, implementation_revision='...')
```

| 항목 | 내용 |
|---|---|
| 책임 | 주문·배송 상태 비교, 정책 근거 제시, 환불 proposal |
| write | ★`refund.request` **proposal 만**. 실제 환불 실행 없음 |
| 대표 시나리오 | **배송완료로 표시됐으나 미수령** — 배송 이력·정책 확인 → 환불 요청을 승인 대기로 |

## 2. Return/Exchange Team (실제 코드: `app/modules/customer_ops/return_exchange.py`)

```python
manifest = TeamManifest(
    team_id='return_exchange',
    display_name='Return/Exchange Team',
    contract_name='a_cop.team_task',
    supported_contract_versions=['1.0'],
    capabilities=['return.diagnose', 'return.propose_action'],
    accepted_case_types=['return', 'exchange'],
    required_context=['case_state', 'policy', 'db_facts', 'history'],
    allowed_tools=['read.order', 'read.return', 'read.policy'],
    knowledge_scope=['return', 'exchange', 'order'],
    max_steps=6, active=True, implementation_revision='...')
```

| 항목 | 내용 |
|---|---|
| 책임 | 주문·반품 상태·정책 비교, 반품/교환 가능 여부 판단, 처리 절차 제시 |
| write | ★`return.accept` **proposal 만**. 실제 반품 승인 실행 없음 |
| 대표 시나리오 | **반품 수량이 주문 수량을 초과** — 주문·반품 이력·정책 비교 후 처리 절차 제시 |

## 3. prompt 등록 규칙 — ★설계됐으나 실 런타임에 배선되지 않았다 (2026-08-17 발견)

아래는 **원래 의도된 설계**다. 실제로 지금 두 Team 은 `self.llm.complete(prompt_key, ...)`
를 호출하고, `OpenAITeamLLM.complete()`(`app/infrastructure/llm/openai.py`)는
`prompt_key` 를 그 자리에서 조립한 JSON 안에 라벨로만 넣을 뿐 `prompts` 테이블을
전혀 참조하지 않는다. `create_llm_call`/`record_llm_call`/`register_prompt_files`
호출부는 **0건**이다 — 아래 규칙은 현재 미구현 상태다.
상세: `wiki/records/reports/debugs/2026-08-17_2340_프롬프트_감사추적_미연결.md`.
(`prompts/billing/`·`prompts/technical/` 옛 도메인 프롬프트 파일 12개도 이 미배선
상태로 남아 있다 — 커머스용으로 재작성되지 않았다.)

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
