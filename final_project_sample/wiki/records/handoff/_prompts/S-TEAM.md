# Codex — 스트림 S-TEAM (Billing / Technical Agent Team)

## 0. 먼저 읽을 것
1. `RULE.md` §3.1·§3.2·§3.3·§3.4
2. `CLAUDE.md` ★§0.1(근거 없으면 답하지 않는다) ★§0.2(승인 없이 실행하지 않는다)
3. `wiki/records/handoff/04_Team_모듈_계약.md` ← **이번 작업의 계약**
4. `wiki/records/handoff/01_계약_Pydantic.md` · `06_가드레일_수치.md` §2
5. **구현돼 있는 것 (읽어라. 고치지 마라)**: `app/core/contracts.py`,
   `app/core/context.py`(ContextBroker·PolicyChunk), `app/infrastructure/rag/retriever.py`(`search_policy`),
   `app/infrastructure/db/repository.py`, `app/core/settings.py`
6. `../A-COP_구현계획서_v5.md` §14 — 읽기 전용, **수정 금지**

## 1. 소유 범위 (여기에만 쓴다)
```
app/modules/customer_ops/billing.py
app/modules/customer_ops/technical.py
app/modules/customer_ops/__init__.py
app/tools/**
prompts/billing/** , prompts/technical/**
tests/unit/teams/** , tests/contract/test_team_contract.py , tests/contract/test_core_isolation.py
wiki/records/reports/ , wiki/records/history/
```
★그 밖 금지. 특히 `app/core/**`, `app/presentation/**`, `knowledge/**`,
`app/modules/customer_ops/feedback.py`(다른 세션 작업 중), `eval/**`.

## 2. 만들 것

### 2-1. 두 TeamModule
`wiki/records/handoff/04` §1·§2 의 manifest **그대로**. `TeamModule` Protocol 구현:
`manifest` 속성 + `async def execute(self, task: TeamTask) -> TeamResult`.

- **BillingSubscriptionTeam** — 결제·구독 비교, 정책 근거, `refund.request` **proposal 만**
- **TechnicalEntitlementTeam** — entitlement·계정·incident·정책 비교, 원인 분류, 해결 절차

### 2-2. read tool (`app/tools/read_tools.py`)
`read.subscription` `read.payment_history` `read.policy` `read.entitlement` `read.account` `read.incident`

- ★tenant/customer 범위는 **인자가 아니라 `TeamTask.context`** 에서 받는다. 임의 tenant 조회 불가
- ★**LLM 이 자유 SQL 을 쓰지 않는다.** 이름 붙은 함수만
- `read.policy` 는 `search_policy()` 를 쓴다
- allowlist 밖 호출 → `ToolNotAllowed`
- loop guard: 동일 tool + 정규화 arguments 가 **2회 반복 → escalate** (`06` §2)

### 2-3. prompt (`prompts/{billing,technical}/<key>.v1.md`)
`classify_billing` `explain_billing` `propose_refund` /
`classify_entitlement` `diagnose_entitlement` `propose_support_action`

- `prompts` 테이블에 `sha256` 과 함께 등록하는 함수를 제공한다
  (`UNIQUE(prompt_key,version)`·`UNIQUE(prompt_key,sha256)`)
- ★LLM 호출은 `llm_calls` 에 `prompt_id` FK 로 기록한다

### 2-4. ★반드시 지킬 출력 규칙 (계약 validator 가 거부한다)
| 상황 | outcome | next_action | 함께 채울 것 |
|---|---|---|---|
| 정상 | completed | respond | `answer` + **`evidence` 비면 안 됨** |
| 정보 부족 | waiting | wait_for_input | `wait_reason='customer_input'`, `required_input_schema` |
| 승인 필요 | waiting | wait_for_approval | `wait_reason='human_approval'`, `action_proposals`≥1 |
| 타 Team | handoff | handoff | `handoff_capability` |
| 정책 근거 없음 | escalated | escalate | `failure_code` |

★`approval_required=True` 제안을 내면서 `next_action != wait_for_approval` 이면 **계약이 거부**한다.
★`ContextPack.degraded=True` 면 **확정 답변을 내지 마라** → escalate.
★`ActionProposal.rationale_evidence_ids` 는 **그 결과의 evidence 안에** 있어야 한다.

## 3. 테스트
- `tests/contract/test_team_contract.py` — 두 Team 이 Protocol·manifest 호환
- `tests/contract/test_core_isolation.py` — ★`app/core/**` 가 `app.modules` 를 **import 하지 않음**
  (AST 또는 import 스캔)
- `tests/unit/teams/` — 시나리오별 TeamResult 일관성:
  1. 해지 후 추가 결제 → `wait_for_approval` + `refund.request` proposal
  2. Free/Pro 권한 불일치 → 진단 결과 + 해결 절차, **실권한 변경 없음**
  3. `degraded=True` ContextPack → **escalate** (확정 답변 금지)
  4. allowlist 밖 tool → `ToolNotAllowed`
  5. 동일 tool 2회 반복 → escalate
- ★LLM 을 테스트에서 실제 호출하지 마라. **주입 가능한 fake LLM** 으로 결정적으로 돌린다
- ★테스트 전용 tenant 사용, teardown 에서 삭제. `demo` 를 지우지 마라

## 4. 완료 조건 (실제로 돌리고 출력을 붙인다)
```powershell
python -m pytest tests -q            # 기존 78건이 계속 통과 + skip 0
python -m pytest tests/unit/teams tests/contract -q
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe" -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```
기대: 전부 통과, **skipped 0**, `tenants=1`.

## 5. 리포트
`wiki/records/reports/2026-08-12_S-TEAM_리포트.md` — §4 **실제 출력 원문**, manifest 2종, prompt 6종 목록.
`wiki/records/history/2026-08-12_S-TEAM.md` 이력 추가.

## 6. 하지 말 것
- ❌ Team 이 side effect 실행 (환불·권한 변경). proposal 만
- ❌ 근거(evidence) 없는 `answer`
- ❌ `degraded` 상태에서 확정 답변
- ❌ `transition_case()` 를 Team 이 직접 호출 (Controller 몫)
- ❌ `pytest.skip` 으로 넘기기 — 데이터 없으면 **fail**
- ❌ 소유 범위 밖 수정 / 계획서 수정
- ❌ 명령을 돌리지 않고 "동작함" 이라고 쓰기
