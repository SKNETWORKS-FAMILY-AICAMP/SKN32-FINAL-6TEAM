# A-COP Mandate + Outcome 기술 구현 계획서
## 기존 A-COP 아키텍처 유지 · Agent 시대의 위임과 완료 의미 모델만 확장

**문서 목적**  
기존 A-COP의 `Customer Case / Shared State / Agentic Controller / Agent Team Registry / Context Broker / Tool·Action Layer / MCP / A2A / Approval / Audit` 구조는 변경하지 않는다.  
본 계획서는 기존 구조에 없던 의미 모델인 **Mandate**와 **Outcome**만 최소 확장하여, “Agent가 고객 대신 어디까지 행동할 수 있는가”와 “무엇이 되어야 Case가 성공적으로 끝났는가”를 시스템적으로 표현하는 방법을 정의한다.

---

# 0. 3줄 결론

1. **기존 A-COP 아키텍처는 그대로 사용한다.** 새 최상위 컴포넌트나 새 Agent Team을 만들지 않는다.
2. **Mandate**는 고객이 AI에게 위임한 목표·조건·행동 범위를, **Outcome**은 Case의 성공 조건을 표현하는 Case-level 의미 모델이다.
3. MVP는 `Mandate + Outcome`만 구현하고, Commitment와 Resolution Proof는 기존 `case_events / action_result / evidence / audit`로 우선 흡수한다.

---

# 1. 왜 이 확장이 필요한가

## 1.1 기존 A-COP이 이미 해결하는 것

기존 구조는 이미 다음 질문에 답한다.

- 외부 사용자·Personal AI·Remote Agent가 어떻게 들어오는가?
- 어떤 Agent Team이 어떤 Capability를 처리하는가?
- 여러 Agent Team이 어떻게 Shared State를 공유하는가?
- 어떤 Context/RAG/Memory를 제공할 것인가?
- 실제 Tool/Action은 어떻게 권한·승인·Idempotency·Audit 아래 실행되는가?
- Local Team과 Remote A2A Team을 어떻게 동일 Case lifecycle에서 처리하는가?

따라서 이 부분을 다시 설계할 이유는 없다.

## 1.2 아직 명시적으로 답하지 못하는 질문

기존 A-COP만으로는 다음 의미가 약하다.

### 질문 A — 사용자는 Agent에게 정확히 무엇을 맡겼는가?
OAuth Scope가 `refund.request`를 허용한다고 해서 사용자가 “모든 환불을 알아서 처리해도 된다”고 위임한 것은 아니다.

예:
- 5만원 이하 환불은 자동 진행
- 5만원 초과면 사용자 확인
- 포인트 보상은 거절
- 원결제수단 환불만 허용
- 주문 취소는 허용하지만 구독 해지는 금지

이것은 **인증/인가 문제보다 상위의 사용자 의도·위임 문제**다.

### 질문 B — 언제 Case를 끝내도 되는가?
`refund.request()` 성공은 고객 목표 달성과 다를 수 있다.

예:
`환불 요청 접수 → PG 승인 → 카드사 반영 → 고객에게 실제 환불`

따라서 `Tool 호출 성공`과 별개로 **고객 목표가 충족된 종료 조건**이 필요하다.

---

# 2. 외부 기술 흐름과의 정합성 — 웹 리서치

> 아래 항목은 A-COP이 그대로 복제한다는 의미가 아니라, Mandate/Outcome 확장이 실제 산업의 Agentic Commerce·Agent Interoperability 흐름과 정합적인지 검증하기 위한 근거다.

## 2.1 AP2 — Mandate를 별도 신뢰 객체로 취급

Google의 2026년 Agent Protocols 가이드는 **Agent Payments Protocol(AP2)**가 typed mandate를 사용해 사용자의 의도를 증명하는 계층을 추가한다고 설명한다.  
이는 “API를 호출할 수 있는 기술적 권한”과 “사용자가 이 행동을 실제로 의도·위임했는가”가 별개라는 점을 보여준다.

**A-COP 시사점**
- OAuth Scope = 시스템 접근 권한
- Mandate = 사용자 목표·제약·위임 의도
- 둘을 하나의 필드로 합치지 않는다.

## 2.2 UCP — Commerce를 capability lifecycle로 표준화

Google의 **Universal Commerce Protocol(UCP)**은 상품 탐색부터 구매 과정까지 Commerce lifecycle을 strongly typed request/response capability로 다루며 REST, MCP, A2A 등 여러 transport와 결합할 수 있도록 설계되었다.

**A-COP 시사점**
- A-COP의 REST/MCP/A2A 구조를 다시 만들 필요가 없다.
- 도메인별 commerce capability는 기존 Tool/Action Layer와 Team Contract에 얹으면 된다.
- Mandate/Outcome은 transport가 아니라 Case semantics에 있어야 한다.

## 2.3 A2A — 독립 Agent 간 Task/Result를 위한 계층

A2A v1.0은 Agent Card를 통해 identity, endpoint, capability/skill, authentication metadata를 표현하고 독립 Agent System 간 Task 협업을 제공한다.

**A-COP 시사점**
- Remote Agent 협업은 기존 A2A Adapter/Registry가 담당한다.
- Mandate를 A2A 자체와 동일시하지 않는다.
- 필요한 경우 Remote TeamTask에 Mandate의 “해당 Task에 필요한 최소 subset”만 전달한다.

## 2.4 MCP — Tool/Resource 접근과 Authorization

MCP는 LLM application과 외부 tool/resource를 연결하는 프로토콜이며 HTTP 기반 authorization 흐름을 제공한다. 2026-07-28 릴리스는 stateless core와 authorization hardening 방향을 포함한다.

**A-COP 시사점**
- Personal AI의 Tool 접근은 기존 MCP Gateway가 담당.
- Mandate는 MCP transport 자체가 아니라, MCP 요청을 Case로 정규화한 뒤 적용되는 business intent layer다.

## 2.5 Visa / Mastercard — Agent identity, permission, intent가 별도 문제로 부상

Visa Trusted Agent Protocol은 merchant가 legitimate AI agent를 식별하고 검증하는 방향을 제공한다. Mastercard는 2026년 **Verifiable Intent**를 user authorization·accountability를 위한 별도 trust layer로 설명하고, Agent Pay for Machines에서는 credentialing·permissioning·transaction controls를 명시한다.

**A-COP 시사점**
- “Agent인가?”와 “무엇을 위임받았는가?”를 분리해야 한다.
- 향후 실제 결제·구매까지 확장할 경우 Mandate의 서명/증명 가능성을 고려할 가치가 있다.

---

# 3. 설계 원칙

## 원칙 1 — 새 컴포넌트를 만들지 않는다
`Mandate Service`, `Outcome Service`, `Commitment Ledger Service` 같은 새 최상위 서비스를 MVP에 만들지 않는다.

## 원칙 2 — Case의 의미 모델로 추가한다
Mandate와 Outcome은 `Customer Case`가 가진 domain object/value object로 둔다.

## 원칙 3 — 인증·인가와 위임을 분리한다
- OAuth Scope: 호출 가능한 시스템 capability
- Tool Permission: 특정 Tool에 대한 서비스 정책
- Approval: 고위험 action의 실행 전 확인
- Mandate: 사용자가 이번 목표에서 Agent에게 위임한 범위

## 원칙 4 — Action success와 Outcome success를 분리한다
- Action success: API/Tool 호출 성공
- Outcome success: 고객 목표의 성공 조건 충족

## 원칙 5 — 기존 구조로 표현 가능한 것은 기존 구조를 쓴다
- 약속 기록 → `case_events`
- 실행 결과 → `action_requests/action_results`
- 근거 → `evidence`
- 감사 → `audit`
- 최종 검증 → Outcome evaluator가 기존 state/evidence/action result를 읽어 판단

---

# 4. 신규 개념 1 — Customer Mandate

## 4.1 정의

**Customer Mandate**는 고객이 Personal AI 또는 기업 측 Agent에게 위임한 **목표, 허용 행동, 금지 행동, 조건, 승인 경계, 유효기간**을 구조화한 Case-level 객체다.

### 핵심 질문
> “이 Agent는 이 고객을 대신해, 이 Case에서 무엇을 어디까지 결정하고 실행해도 되는가?”

## 4.2 Scope와의 차이

| 항목 | OAuth / Tool Scope | Mandate |
|---|---|---|
| 관점 | 시스템 | 사용자 |
| 질문 | 이 Client가 어떤 API를 호출할 수 있는가? | 사용자가 이번 목표에서 무엇을 위임했는가? |
| 예 | `refund.request` | “5만원 이하만 자동 환불” |
| 수명 | Token/Connection 중심 | Case/Goal 중심 |
| 변경 | Auth policy | 사용자 의도/조건 변경 |
| 실패 시 | 401/403 | 재승인 / 사용자 확인 / replanning |

## 4.3 최소 데이터 모델

```json
{
  "mandate_id": "MND-1001",
  "case_id": "CASE-1204",
  "goal": "잘못 배송된 상품을 정상 상품으로 교환",
  "allowed_actions": [
    "order.read",
    "return.request",
    "exchange.request"
  ],
  "forbidden_actions": [
    "refund.to_points",
    "membership.cancel"
  ],
  "constraints": {
    "max_extra_payment_krw": 10000,
    "latest_completion_at": "2026-08-20T23:59:59+09:00"
  },
  "approval_rules": [
    {
      "when": "extra_payment_krw > 10000",
      "action": "REQUIRE_USER_APPROVAL"
    }
  ],
  "status": "ACTIVE",
  "version": 1
}
```

## 4.4 권장 상태

```text
DRAFT
  ↓
ACTIVE
  ├─→ REVISED → ACTIVE
  ├─→ SUSPENDED → ACTIVE
  ├─→ REVOKED
  └─→ EXPIRED
```

## 4.5 실행 시 검증 순서

```text
Agent가 Action 제안
   ↓
1. OAuth/Agent Scope 확인
   ↓
2. Tool Policy 확인
   ↓
3. Mandate 허용 범위 확인
   ↓
4. Constraint 확인
   ↓
5. Approval Rule 확인
   ↓
6. 기존 Human Approval Gateway
   ↓
7. Idempotency
   ↓
8. Tool 실행
   ↓
9. Audit
```

**중요:** Mandate가 기존 Approval을 대체하지 않는다.

---

# 5. 신규 개념 2 — Outcome

## 5.1 정의

**Outcome**은 고객이 원하는 최종 상태와, Case를 성공적으로 종료하기 위해 만족해야 하는 **검증 가능한 성공 조건**을 구조화한 객체다.

### 핵심 질문
> “무엇이 실제로 일어나야 이 Case를 해결됐다고 말할 수 있는가?”

## 5.2 최소 데이터 모델

```json
{
  "outcome_id": "OUT-1001",
  "case_id": "CASE-1204",
  "target": "replacement_received",
  "success_conditions": [
    {
      "key": "replacement_order_created",
      "type": "STATE",
      "required": true
    },
    {
      "key": "replacement_delivered",
      "type": "EXTERNAL_EVENT",
      "required": true
    }
  ],
  "status": "IN_PROGRESS",
  "evaluated_at": null
}
```

## 5.3 Outcome 상태

```text
DEFINED
  ↓
IN_PROGRESS
  ├─→ BLOCKED
  ├─→ PARTIALLY_MET
  ├─→ FAILED
  └─→ SATISFIED
```

`Case CLOSED`는 기본적으로 `Outcome SATISFIED` 이후에만 가능하게 한다.

단, 다음 예외는 정책적으로 허용할 수 있다.
- 고객 취소
- 해결 불가
- 정책상 거절
- 고객 응답 없음 timeout

이 경우 Case 종료 사유를 별도 기록한다.

## 5.4 성공 조건 타입

MVP에서는 4개면 충분하다.

| Type | 의미 | 예 |
|---|---|---|
| `STATE` | 내부 DB 상태 | 주문 상태=cancelled |
| `ACTION_RESULT` | Tool 결과 | refund API accepted |
| `EXTERNAL_EVENT` | 외부 시스템 이벤트 | 배송 완료 webhook |
| `USER_CONFIRMATION` | 사용자 확인 | “문제 해결됨” 승인 |

---

# 6. Commitment / Resolution Proof는 어떻게 할 것인가

## 6.1 MVP에서는 독립 모델로 만들지 않는다

### Commitment
기업/Agent가 고객에게 한 약속은 우선 `case_events`에 기록한다.

예:
```json
{
  "event_type": "COMMITMENT_CREATED",
  "payload": {
    "statement": "8월 20일까지 교환 상품 출고",
    "due_at": "2026-08-20T18:00:00+09:00"
  }
}
```

### Resolution Proof
독립 Proof 테이블을 만들지 않고 기존:
- action result
- webhook/event
- evidence
- audit log
를 Outcome evaluator가 읽는다.

향후 법적/금융적 증명 수준이 필요할 때만 별도 signed proof/receipt 모델로 승격한다.

---

# 7. 기존 A-COP 아키텍처와의 관계

## 7.1 변경 없음

다음 기존 컴포넌트는 그대로 둔다.

```text
Agent Gateway
Customer Case Layer
Context Broker
Agentic Controller
Agent Team Registry
Agent Team Slot
Message Broker
Shared State
Tool / Action Layer
MCP
A2A
GraphRAG / Vector RAG
Audit / Approval / Idempotency
```

## 7.2 논리적 확장만 추가

```text
Customer Case
├─ 기존: status / owner / evidence / open_tasks / approval / version
├─ 신규: mandate
└─ 신규: outcome
```

즉:

```text
기존 A-COP = Agent가 어떻게 협업하고 실행되는가(HOW)
Mandate     = 무엇을 어디까지 대신해도 되는가(AUTHORIZED INTENT)
Outcome     = 무엇이 되어야 끝나는가(SUCCESS)
```

---

# 8. 데이터 모델 변경안

## 8.1 권장 방식: 별도 테이블 2개

`customer_cases`에 JSONB를 바로 박는 것보다 version/history/evaluation을 고려해 별도 테이블을 권장한다.

### customer_mandates

```sql
CREATE TABLE customer_mandates (
    mandate_id UUID PRIMARY KEY,
    case_id UUID NOT NULL REFERENCES customer_cases(case_id),
    goal TEXT NOT NULL,
    allowed_actions JSONB NOT NULL DEFAULT '[]',
    forbidden_actions JSONB NOT NULL DEFAULT '[]',
    constraints JSONB NOT NULL DEFAULT '{}',
    approval_rules JSONB NOT NULL DEFAULT '[]',
    status VARCHAR(20) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### case_outcomes

```sql
CREATE TABLE case_outcomes (
    outcome_id UUID PRIMARY KEY,
    case_id UUID NOT NULL REFERENCES customer_cases(case_id),
    target VARCHAR(100) NOT NULL,
    success_conditions JSONB NOT NULL,
    status VARCHAR(30) NOT NULL,
    last_evaluation JSONB,
    evaluated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 인덱스

```sql
CREATE UNIQUE INDEX ux_active_mandate_per_case
ON customer_mandates(case_id)
WHERE status = 'ACTIVE';

CREATE INDEX ix_outcome_case_status
ON case_outcomes(case_id, status);
```

---

# 9. Domain / Application 설계

## 9.1 폴더 추가 — 최소 변경

```text
app/
├─ core/
│  └─ case_runtime/
│     ├─ case/
│     │  ├─ mandate.py          # 신규 Value/Entity
│     │  ├─ outcome.py          # 신규 Value/Entity
│     │  └─ ...
│     ├─ orchestration/
│     │  ├─ controller.py
│     │  ├─ mandate_guard.py    # 작은 Policy 객체
│     │  ├─ outcome_evaluator.py# 작은 Policy 객체
│     │  └─ ...
│     └─ state/
│        └─ ...
└─ infrastructure/
   └─ db/
      ├─ mandate_repository.py
      └─ outcome_repository.py
```

**주의:** `mandate_guard.py`와 `outcome_evaluator.py`는 신규 Platform Component가 아니라 Case Runtime 내부 policy/service다.

## 9.2 Pydantic 모델 예시

```python
from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field

class MandateStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"

class ApprovalRule(BaseModel):
    expression: str
    action: str = "REQUIRE_USER_APPROVAL"

class CustomerMandate(BaseModel):
    mandate_id: str
    case_id: str
    goal: str
    allowed_actions: list[str]
    forbidden_actions: list[str] = Field(default_factory=list)
    constraints: dict[str, object] = Field(default_factory=dict)
    approval_rules: list[ApprovalRule] = Field(default_factory=list)
    status: MandateStatus
    version: int

class OutcomeCondition(BaseModel):
    key: str
    type: str
    required: bool = True
    parameters: dict[str, object] = Field(default_factory=dict)

class CaseOutcome(BaseModel):
    outcome_id: str
    case_id: str
    target: str
    success_conditions: list[OutcomeCondition]
    status: str
    evaluated_at: datetime | None = None
```

실제 구현에서는 constraint expression을 임의 Python `eval()`로 처리하지 않는다.  
Rule DSL 또는 명시적 operator schema를 사용한다.

---

# 10. API 계획

## 10.1 Human / Personal AI 공통 Case API

```http
POST   /v1/cases
GET    /v1/cases/{case_id}
POST   /v1/cases/{case_id}/mandate
PATCH  /v1/cases/{case_id}/mandate
POST   /v1/cases/{case_id}/mandate/revoke
GET    /v1/cases/{case_id}/outcome
POST   /v1/cases/{case_id}/approve
```

## 10.2 MCP Tool 노출 예시

```text
case.open
case.get

mandate.get
mandate.update
mandate.revoke

order.search
order.get
order.cancel

return.request
exchange.request
refund.request

shipment.track
```

**원칙:** MCP에 `mandate.override` 같은 무제한 우회 Tool을 만들지 않는다.

## 10.3 A2A 전달 원칙

Remote Agent에 전체 Mandate를 무조건 전달하지 않는다.

```text
Full Mandate
   ↓ Task projection
Remote Task Mandate View
   ├─ goal subset
   ├─ allowed action subset
   ├─ relevant constraints
   └─ approval boundary
```

최소 권한·최소 공개 원칙을 적용한다.

---

# 11. Orchestration 변경

기존 Top-Level Graph를 갈아엎지 않고 Guard/Evaluate 노드 2개만 논리적으로 추가한다.

```text
Case Intake
   ↓
Mandate Resolve / Validate
   ↓
기존 Context Broker
   ↓
기존 Controller / Team Routing
   ↓
Agent Team Result
   ↓
Action Proposal
   ↓
Mandate Guard
   ├─ DENY → Replan / User Notice
   ├─ APPROVAL_REQUIRED → 기존 Approval
   └─ ALLOW
          ↓
      기존 Tool/Action Layer
          ↓
      Shared State / Event
          ↓
      Outcome Evaluate
          ├─ SATISFIED → Close
          ├─ IN_PROGRESS → WAIT/RESUME
          └─ FAILED/BLOCKED → replan/Escalate
```

---

# 12. Mandate Guard 규칙

## 12.1 판정 결과

```text
ALLOW
DENY
REQUIRE_APPROVAL
MANDATE_EXPIRED
MANDATE_REVOKED
CONSTRAINT_VIOLATION
```

## 12.2 판정 pseudo-code

```python
def evaluate_action(action, mandate, actor_scope, tool_policy):
    if not actor_scope.allows(action.name):
        return "DENY"

    if not tool_policy.allows(action):
        return "DENY"

    if mandate.status != "ACTIVE":
        return "DENY"

    if action.name in mandate.forbidden_actions:
        return "DENY"

    if action.name not in mandate.allowed_actions:
        return "REQUIRE_APPROVAL"

    if violates_constraints(action, mandate.constraints):
        return "REQUIRE_APPROVAL"

    if matches_approval_rule(action, mandate.approval_rules):
        return "REQUIRE_APPROVAL"

    return "ALLOW"
```

---

# 13. Outcome Evaluator 규칙

## 13.1 평가 입력

- current Shared State
- Action results
- Case events
- 외부 webhook/event
- 사용자 확인
- 필요 시 DB Current State

## 13.2 평가 결과

```text
SATISFIED
IN_PROGRESS
PARTIALLY_MET
BLOCKED
FAILED
```

## 13.3 예 — 환불

```text
Target: refund_completed

조건:
1. refund_requested         → ACTION_RESULT
2. payment_provider_accepted→ EXTERNAL_EVENT
3. refunded_amount == 39000 → STATE

모두 만족 → SATISFIED
```

---

# 14. Commerce 적용 예시

## 14.1 사용자 명령

> “지난주 산 키보드가 다른 모델로 왔어. 추가 비용 1만원 이하라면 알아서 교환하고, 그 이상이면 나한테 물어봐.”

## 14.2 Mandate

```json
{
  "goal": "ordered_product_received",
  "allowed_actions": [
    "order.read",
    "return.request",
    "exchange.request",
    "shipment.track"
  ],
  "constraints": {
    "max_extra_payment_krw": 10000
  }
}
```

## 14.3 Outcome

```json
{
  "target": "correct_product_received",
  "success_conditions": [
    "return_accepted",
    "replacement_order_created",
    "replacement_delivered"
  ]
}
```

## 14.4 실행

```text
Personal AI
  ↓ MCP
A-COP Case
  ↓
Commerce Agent Team
  ↓
교환 Action Proposal
  ↓
Mandate Guard
  ↓ 7,000원 추가
ALLOW
  ↓
기존 Tool / Action Layer
  ↓
교환 접수
  ↓
배송 Event 대기
  ↓
replacement_delivered
  ↓
Outcome SATISFIED
  ↓
Case CLOSED
```

---

# 15. 보안·거버넌스

## 필수

- Mandate versioning
- revoke 가능
- 만료 시간 선택 지원
- 각 Action마다 mandate_id + version을 Audit에 기록
- Mandate 변경은 actor identity 기록
- Remote A2A 전달은 subset projection
- high-risk action은 기존 Human Approval 유지
- constraint evaluator에서 arbitrary code execution 금지
- stale mandate version으로 Action 실행 금지
- Case closure 사유와 Outcome 상태를 함께 기록

## 향후

- signed mandate
- verifiable intent / non-repudiation
- policy-as-code
- agent credential
- payment-specific delegated authority

---

# 16. Observability

각 Agent trace에 다음 필드를 추가한다.

```text
case_id
mandate_id
mandate_version
proposed_action
mandate_decision
approval_required
action_id
outcome_id
outcome_status_before
outcome_status_after
evidence_refs
```

운영자 화면에서 최소한 다음을 보여준다.

1. 고객 목표
2. Agent 위임 범위
3. 현재 처리 단계
4. Agent가 제안한 Action
5. Mandate 판정
6. 승인 대기 여부
7. Outcome 충족률
8. Case 종료 이유

---

# 17. 평가 계획

## 17.1 Baseline

### Baseline A — 기존 A-COP
- OAuth Scope
- Tool Permission
- Approval
- Case lifecycle
- 별도 Mandate/Outcome 없음

### Proposed — A-COP + Mandate/Outcome
- 위임 의미 검증
- 성공 조건 기반 종료

## 17.2 핵심 지표

| 지표 | 정의 |
|---|---|
| Unauthorized Intent Action Rate | 시스템 Scope는 허용하지만 사용자 위임에는 벗어난 Action 비율 |
| Approval Precision | 실제 승인 필요 Action 중 올바르게 승인 요청한 비율 |
| Outcome Completion Rate | 목표 성공조건을 실제 충족한 Case 비율 |
| Premature Closure Rate | Outcome 미충족인데 Case를 닫은 비율 |
| Replan Success Rate | Mandate/Outcome 충돌 후 대체 계획으로 해결한 비율 |
| Human Intervention Rate | 전체 Case 중 사람 개입 비율 |
| Mean Steps to Outcome | Outcome 달성까지 평균 단계 수 |
| Mandate Violation Rate | 위임 조건 위반 Action 비율 — 목표 0 |

---

# 18. 테스트 계획

## Unit
- Mandate allowed/forbidden action
- 금액 제한
- 만료/revoke
- version conflict
- Outcome condition evaluator
- partial/satisfied/failed

## Integration
- MCP → Case → Mandate → Action
- Approval required → RESUME
- external event → Outcome SATISFIED
- A2A subset mandate projection
- stale mandate version 차단

## E2E
1. 자동 교환 성공
2. 금액 초과 → 사용자 승인
3. Mandate revoke 중간 발생
4. Tool 성공했지만 Outcome 미완료 → WAIT
5. Remote A2A Team이 권한 밖 Action 요청 → DENY
6. 배송 완료 Event 후 Case 자동 종료

## Regression
기존 A-COP Case에 Mandate가 없을 때:
- `mandate_mode = LEGACY`
- 기존 흐름이 그대로 동작하도록 feature flag 제공

---

# 19. 구현 단계 — 8~10주 프로젝트에 맞춘 최소 증분

## P0 — 설계 / 2~3일
- Mandate/Outcome schema 확정
- Case lifecycle 영향 정의
- Rule operator 5~8개 정의
- API contract 확정

## P1 — Mandate / 4~5일
- DB migration
- repository
- domain model
- Mandate Guard
- REST endpoint
- audit 연결

## P2 — Outcome / 4~5일
- DB migration
- evaluator
- Action/Event 연결
- Case close guard

## P3 — MCP / A2A 연결 / 3~4일
- MCP mandate tools
- RemoteTask mandate projection
- trace

## P4 — UX / Evaluation / 4~5일
- Mandate/Outcome 시각화
- 시나리오 3~5개
- baseline 비교

**전체 신규 기능 순수 작업량:** 기존 Core가 안정화되어 있다는 전제에서 약 2~3주 내 병렬 흡수 가능한 범위로 설계한다.

---

# 20. 하지 않을 것

- 별도 Mandate Microservice
- 별도 Outcome Microservice
- 블록체인/원장
- 복잡한 정책 DSL
- 법적 전자서명 시스템
- 범용 결제 프로토콜 자체 구현
- AP2/UCP 자체 재구현
- Commitment 전용 데이터베이스
- Resolution Proof 전용 인프라
- 모든 도메인 공통 ontology

---

# 21. 향후 확장 조건

다음 조건이 생기면 확장한다.

### Commitment를 독립 모델로 승격
- 기업의 약속 기한/SLA 위반을 자동 추적해야 함
- Agent 발화가 계약적 의미를 가짐
- 보상 정책까지 자동화

### Resolution Proof를 독립 모델로 승격
- 금융/보험/법률 등 강한 증명 필요
- 외부 기관 증명서/서명 검증 필요
- 분쟁 대응을 위한 tamper-evident evidence 요구

### Signed Mandate
- 실제 결제·구매를 Personal AI가 수행
- 금액/상품/merchant 범위를 암호학적으로 증명할 필요
- cross-company agent delegation이 확대

---

# 22. Definition of Done

- [ ] 기존 A-COP Top-Level Architecture 변경 없음
- [ ] Case에 Mandate/Outcome 관계 추가
- [ ] Mandate 허용/금지/조건/승인 판정 동작
- [ ] Mandate revoke/versioning 동작
- [ ] Action 실행 전 Mandate Guard 통과 필수
- [ ] Outcome success condition 평가 가능
- [ ] Outcome 미충족 시 정상 Case close 차단
- [ ] 외부 event로 Outcome 재평가
- [ ] MCP 요청에도 동일 정책 적용
- [ ] A2A Remote Task에는 최소 Mandate subset만 전달
- [ ] Audit에서 어떤 Mandate version으로 Action했는지 추적
- [ ] E2E 시나리오 5개 이상
- [ ] 기존 A-COP baseline 대비 평가 리포트

---

# 23. 최종 아키텍처 판단

```text
A-COP 기존 구조
────────────────────────────────
HOW
Agent Gateway
Case
Controller
Context
Team
State
Tool
MCP / A2A
Approval / Audit
────────────────────────────────

신규 의미 모델
────────────────────────────────
AUTHORIZED INTENT = Mandate
SUCCESS           = Outcome
────────────────────────────────
```

**결론:**  
A-COP을 CS 전용으로 재설계하지 않는다.  
Mandate와 Outcome은 쇼핑·여행·SaaS·보험 등 어떤 Agentic 업무에도 재사용 가능한 **범용 Case semantics**로 추가한다.

---

# 24. 웹 리서치 출처

1. Google Developers Blog — *Developer's Guide to AI Agent Protocols* (2026-03-18)  
   https://developers.googleblog.com/developers-guide-to-ai-agent-protocols/

2. Google Developers Blog — *Under the Hood: Universal Commerce Protocol (UCP)* (2026-01-11)  
   https://developers.googleblog.com/under-the-hood-universal-commerce-protocol-ucp/

3. A2A Protocol — *Specification / Core Concepts / v1.0*  
   https://a2a-protocol.org/latest/specification/  
   https://a2a-protocol.org/latest/topics/key-concepts/

4. Model Context Protocol — *Specification / Authorization*  
   https://modelcontextprotocol.io/specification/2025-11-25  
   https://modelcontextprotocol.io/specification/draft/basic/authorization

5. Model Context Protocol Blog — *The 2026-07-28 Specification*  
   https://blog.modelcontextprotocol.io/posts/2026-07-28/

6. Visa — *Trusted Agent Protocol / Intelligent Commerce*  
   https://developer.visa.com/capabilities/trusted-agent-protocol/overview  
   https://www.visa.com/en-us/solutions/intelligent-commerce

7. Mastercard — *How Verifiable Intent builds trust in agentic AI commerce* (2026-03-05)  
   https://www.mastercard.com/global/en/news-and-trends/stories/2026/verifiable-intent.html

8. Mastercard — *Agent Pay for Machines* (2026-06-10)  
   https://www.mastercard.com/global/en/news-and-trends/press/2026/june/mastercard-launches-agent-pay-for-machines.html

---

**문서 버전:** 1.0  
**작성 기준일:** 2026-08-15