# 구현 계획서
## A-COP: AI 연동형 모듈형 에이전틱 고객운영 플랫폼
### (부트캠프 주제 대응: 다중 에이전트 서빙 기반 고객 피드백 분석 및 맞춤형 응대 자동화 시스템)

---

## 0. 한 줄 요약
본 프로젝트는 고객 피드백을 Customer Case로 관리하고, 업무별 Agent Team Module이 Shared State·RAG·Memory를 기반으로 협업하는 모듈형 Agentic Customer Operations Platform을 구축한다.

사용자의 Personal AI는 REST/MCP를 통해 우리 Tool과 Resource를 사용할 수 있고, 독립적으로 배포된 Agent System은 A2A를 통해 업무 Task를 위임받을 수 있다. Context Broker는 Vector RAG와 관계 조회(GraphStorePort)를 결합해 관련 문서뿐 아니라 Case·Issue·Policy·Agent Team·Action 사이의 연결 근거까지 Context Pack에 포함한다.

PostgreSQL은 Case/Action 상태와 Transaction의 유일한 Source of Truth로 유지한다. GraphStorePort의 MVP 구현체는 SqlGraphAdapter이며, 별도 Graph Store는 Phase 2 비교 대상으로 남긴다.

---

## 1. 프로젝트명 정리

### 1-1. 짧게 부를 이름
- **A-COP**
- 풀네임: **AI 연동형 모듈형 에이전틱 고객운영 플랫폼**

### 1-2. 부트캠프 주제와의 연결 문장
- 본 프로젝트는 *다중 에이전트 서빙 기반 고객 피드백 분석 및 맞춤형 응대 자동화 시스템* 주제를 기반으로,
  **고객 피드백 분석 → 고객 Case 생성 → 전문 Agent Team 협업 → 맞춤형 응대 및 후속 처리**까지 확장한 구조이다.

---

## 2. 문제 정의

기존 고객지원 자동화 시스템은 대체로 다음 형태에 머무른다.

1. 고객 문의 수집
2. 감성/의도/이슈 분류
3. 관련 문서 검색(RAG)
4. 답변 생성
5. 답변 검수

이 구조는 일정 수준의 자동응대는 가능하지만, 다음과 같은 한계가 있다.

- **고정 파이프라인 한계**: 실제 고객 문제는 결제, 계정, 기술지원, 정책 등 여러 업무에 걸칠 수 있다.
- **상태 기반 처리 부족**: 고객 문제는 단일 답변으로 끝나지 않고, 확인 요청·재처리·보류·승인 등 상태 변화가 필요하다.
- **멀티에이전트 필요성 부족**: 단순히 단계별 LLM 호출에 Agent 이름만 붙이면 멀티에이전트의 당위성이 약하다.
- **외부 AI 연동 부재**: 사용자는 이미 ChatGPT, Claude, Gemini 같은 개인 AI를 사용하고 있으며, 우리 서비스는 사람 UI만 제공하는 구조가 일반적이다.

---

## 3. 프로젝트 목표

### 핵심 목표
1. 고객 피드백을 분석하여 **Customer Case**를 생성한다.
2. 고객 문제의 성격에 따라 **전문 Agent Team**에 동적으로 배정한다.
3. Agent Team은 **기업 지식(RAG)**, **과거 처리 이력(Memory)**, **실시간 상태(Shared State)** 를 바탕으로 협업한다.
4. 단순 응답 생성이 아니라 **조회 → 판단 → 후속 작업 요청 → 응답/에스컬레이션**까지 처리한다.
5. 사용자가 자기 개인 AI를 통해 접근할 수 있도록 **Agent API / MCP 인터페이스**를 제공한다.
6. 전체 시스템을 **모듈화된 Basement 구조**로 설계하여 향후 다른 도메인에도 재사용 가능하게 한다.

---

## 4. 핵심 아이디어

### 4-1. 기존 방식
고객 문의 → 분석 → 검색 → 답변 → 검수

### 4-2. 제안 방식
고객 문의 → **Case 생성** → **Context 구성** → **전문 Agent Team 협업** → **공유 상태 갱신** → **재계획 / 승인 / 응답**

### 4-3. 상위 개념
- **Basement(Core)**: Agent, Tool, State, Memory, RAG, Workflow를 공통 실행 기반으로 제공
- **Domain Module**: Customer Operations 도메인 로직 구현
- **External AI Access**: 개인 AI가 우리 Agent API / MCP를 통해 서비스 접근

---

## 5. 시스템 범위

### In Scope
- 고객 피드백 수집 및 정규화
- 감성 분석 / 의도 분류 / 이슈 분류
- Customer Case 생성 및 상태 관리
- 요구사항 분석을 통해 확정되는 업무 책임 단위 Agent Team Module
- 기업 지식 RAG
- 과거 처리 이력 기반 Memory
- Shared State 및 Agent 협업
- Human Approval(일부 작업)
- 외부 AI Agent용 API / MCP 인터페이스
- 웹 대시보드(운영자용)

### Out of Scope
- OCR / 이미지 판독 / 영상 분석
- 실제 복잡한 물류·택배 사진 판정
- 다수 도메인 완전 지원
- Production-scale 분산 시스템
- 모든 외부 AI 플랫폼별 정식 배포

---

## 6. 타깃 도메인(권장)
범위를 안정적으로 통제하기 위해 **가상의 SaaS 서비스 고객운영 시나리오**를 1차 도메인으로 권장한다.

### 예시 이슈
- 구독 해지 후 추가 결제
- Free/Pro 권한 동기화 오류
- Seat 수와 요금 불일치
- 환불 요청 가능 여부
- 반복되는 장애/불만 피드백 탐지

이 도메인은 OCR/이미지 없이 **DB/API/텍스트 정책만으로 정답과 상태를 구성**할 수 있다.

---

## 7. Agent Team Module 구성 원칙

Agent Team의 이름과 개수는 미리 고정하지 않는다.  
먼저 고객지원 업무를 Capability 단위로 분석한 뒤, 서로 다른 책임·권한·지식·Tool을 가져야 할 업무를 독립 Team Module로 정의한다.

### 7-1. Team Module 공통 원칙
- 각 Team은 하나의 독립 업무 목표(Capability)를 가진다.
- Team 내부 Agent 수는 고정하지 않는다.
- Team 내부에서 LangGraph/Subgraph를 사용할 수도 있고 사용하지 않을 수도 있다.
- Team별 RAG/Memory/Tool/Prompt 정책을 독립적으로 구성할 수 있다.
- Core는 Team 내부 구현을 모르고 Team Contract의 입력/출력만 사용한다.

### 7-2. 가능한 Team 예시
아래는 최종 확정 팀이 아니라 업무 분리 예시다.
- 구독/결제 문제 처리 Team
- 계정/권한/기술지원 Team
- 고객 피드백/VOC 분석 Team
- Complaint / Retention / Fraud Review 등 추가 Team

### 7-3. Agentic Controller
- 역할: Case 분배, 상태 전이, WAIT/RESUME, 재처리, 승인 요청, Agent Team 결과 통합
- 주요 입력: Shared State, classification/capability result, TeamResult
- 주요 출력: assignment, replan, next action, end/wait decision

---

## 8. Basement(Core) 설계

### 8-1. Agent Gateway
외부 사용자/Personal AI 요청이 내부 시스템으로 들어오는 **Trust Boundary**이다.
- OAuth Access Token 검증
- user/client 식별
- Scope 검사
- 요청 위험도 확인
- 승인된 요청만 Customer Case Layer로 전달

### 8-2. Customer Case Layer
한 번의 메시지를 장기 실행 가능한 **업무 Case**로 변환한다.
- case_id
- 현재 status / owner
- event/history
- approval state
- resume/checkpoint
- version

### 8-3. Agent Team Registry / Team Contract
Capability에 맞는 Team Module을 탐색하고 교체 가능성을 보장한다.
- Team Registry: team_id, capabilities, version, 활성 상태, scope 관리
- Team Contract: 표준 입력/출력 규칙
- Core는 Team 내부 구현을 직접 알지 않는다.

### 8-4. Context Broker
Agent가 판단하는 데 필요한 Context를 **선택·조합·정규화·압축**해 Context Pack으로 제공한다.
- RAG / Knowledge
- DB Current State
- Case History
- Memory
- Team별 Knowledge Scope

### 8-5. Message Broker
Message Broker의 사용과 Task/Event 설계는 **Coordination 계층의 책임**이다. Message Broker의 실제 구현은 **Infrastructure 계층의 책임**이다.

Agentic Controller가 어느 Team에 무엇을 보낼지 결정한다. Broker는 판단하지 않고 전달만 한다.
Controller는 `redis.xadd(...)`를 직접 호출하지 않는다. `message_bus.publish(task)`를 호출한다.
구현은 `InMemoryMessageBus` / `RedisMessageBus` / `RabbitMQMessageBus` 중 하나를 Adapter로 꽂는다.

| 계층 | 책임 |
|---|---|
| Application/Coordination | Agentic Controller, Top-Level LangGraph, Routing, Replan, WAIT/RESUME, Task/Event Contract, MessageBus Port |
| Infrastructure | Redis / Redis Streams / RabbitMQ Adapter |

Message Broker는 Agent Team 전용 부속이 아니라 Coordination이 사용하는 컴포넌트다.

### 8-6. Shared State
여러 Team이 같은 Customer Case를 이어서 처리하기 위한 **공식 단일 상태**이다.
- evidence
- decisions
- open_tasks
- owner
- status
- version
- approval state

Team별 Episodic Memory와 다르다.  
Shared State는 “현재 Case의 공식 상태”, Memory는 “과거 경험/지식”이다.

### 8-7. Tool / Action Layer
Agent가 DB나 외부 시스템을 직접 수정하지 않고 **Business Capability API**를 통해 작업하도록 통제한다.
- Tool 권한/Scope
- Idempotency
- Human Approval 여부
- Audit Log
- 실제 외부 side effect 실행

### 8-8. Agentic Controller / Orchestration
- Capability 기반 Team routing
- WAIT / RESUME
- Replan / Retry
- Human Approval
- 다른 Team handoff
- 완료/종료 판단

Top-Level LangGraph는 이 계층에 위치하며, 각 Agent Team은 별도의 Subgraph를 가질 수 있다.

---

## 8-A. Message Broker와 Context Broker 분리

### Message Broker
Coordination 계층이 정의한 Task와 Event를 내부 Worker에게 전달한다.

- Controller: `message_bus.publish(task)` 호출
- MessageBus Port: 전달 계약 제공
- Adapter: InMemoryMessageBus / RedisMessageBus / RabbitMQMessageBus 구현
- Broker: Queue, Retry, Event 전달을 수행하며 Team 선택이나 실행 순서를 판단하지 않음

MVP에서는 In-Process Queue로 시작할 수 있다. 이후 Redis Streams 또는 RabbitMQ Adapter로 교체한다.

### Context Broker
Agent가 판단할 때 필요한 **정보를 선택·조합·압축하여 Context Pack으로 제공**한다.

주요 책임:
- RAG 검색
- DB 상태 조회
- 현재 Case 상태
- 과거 유사 처리 Memory
- Agent별 Knowledge Scope 적용
- Context 최소화

즉:
- Message Broker = **업무/이벤트를 운반**
- Context Broker = **판단에 필요한 정보를 구성**

둘을 하나의 컴포넌트로 합치지 않는다.

### 8-A-1. 계층 경계

```text
Application / Coordination
  Agentic Controller · Top-Level LangGraph · Routing · Replan · WAIT/RESUME
  Task/Event Contract · MessageBus Port
              │
              ▼
Infrastructure
  InMemoryMessageBus · Redis/Redis Streams Adapter · RabbitMQ Adapter
```

Controller는 `redis.xadd(...)` 같은 구현 세부사항을 알지 않는다.

### 8-A-2. 전달 보장과 중복 처리 규칙

모든 consumer는 at-least-once 전제로 동작한다. 진입점에서 처리한 `message_id`를 기록하고 중복이면 스킵한다. In-Process Queue에서는 중복이 자연 발생하지 않으므로, 중복 전달과 재시도를 강제로 발생시키는 테스트를 둔다.

---

## 8-B. Agent Team 플러그인/모듈화 계획

모든 Agent Team은 시스템에 하드코딩되는 고정 팀이 아니라 **등록형 Team Module**로 구성한다.

모듈형 Basement의 실행 경계는 세 Port를 같은 원칙으로 둔다.

```text
MessageBusPort    → InMemoryMessageBus / RedisMessageBus / RabbitMQMessageBus
GraphStorePort    → SqlGraphAdapter / AgeGraphAdapter / Neo4jGraphAdapter
TeamExecutorPort  → LocalTeamExecutor / A2ATeamExecutor
```

`TeamExecutorPort`는 Team을 어디서 실행하는지와 Controller의 판단을 분리한다.

```python
from typing import Protocol

class TeamExecutorPort(Protocol):
    async def execute(self, task: TeamTask, deadline_s: int) -> TeamResult: ...
    async def cancel(self, task_id: str) -> None: ...
    async def status(self, task_id: str) -> str: ...
```

- `LocalTeamExecutor`: `MessageBusPort`로 Task를 발행하고 내부 Agent Team Slot이 처리한다.
- `A2ATeamExecutor`: A2A Adapter로 Remote Agent System에 Task를 위임한다.
- Controller는 두 구현을 구분하지 않는다. Registry의 `execution_type`을 보고 Executor를 고르는 일은 Registry/Factory의 책임이다.
- 두 경로의 결과는 모두 `TeamResult`로 정규화되어 Shared State에 반영된다.

| Port | 교체 가능한 구현 | 교체 기준 |
|---|---|---|
| `MessageBusPort` | `InMemoryMessageBus` / `RedisMessageBus` / `RabbitMQMessageBus` | 내부 Task/Event 전달 요구 |
| `GraphStorePort` | `SqlGraphAdapter` / `AgeGraphAdapter` / `Neo4jGraphAdapter` | 관계 조회 깊이와 운영 비용 |
| `TeamExecutorPort` | `LocalTeamExecutor` / `A2ATeamExecutor` | 같은 Team을 내부 실행할지 원격 위임할지 |

**A2A 경계를 지금 세우는 이유**는 A2A를 나중에 넣으면 Controller, Registry, `TeamResult` 정규화, 상태 매핑을 모두 다시 건드려야 하기 때문이다. 실행 경로는 코드 전반에 퍼지기 때문에 경계를 나중에 세우는 비용이 더 크다. 반면 `GraphStorePort`는 저장소 교체 문제라 Port만 두면 구현을 뒤로 미룰 수 있다.

| 항목 | 지금 경계를 세우는 비용 | 나중에 넣는 비용 | 판단 |
|---|---|---|---|
| TeamExecutorPort / A2A | 낮음 (인터페이스 + Registry 필드) | 높음 (Controller·Registry·정규화·상태매핑 전면 수정) | 지금 세운다 |
| GraphStorePort | 낮음 | 낮음 (어댑터 교체) | Port만 두고 구현은 미룬다 |
| MessageBusPort | 낮음 | 중간 | 지금 세운다 |

Core는 각 Agent Team의 내부 구현에 의존하지 않고 다음 공통 Contract만 사용한다.

```text
AgentTeam
├ team_id
├ capabilities[]
├ accepted_case_types[]
├ required_context[]
├ allowed_tools[]
├ knowledge_scope[]
├ input_schema
├ output_schema
└ execute(case_context) -> TeamResult
```

### Agent Team Registry
- 등록된 Team Module 목록 관리
- Capability 기반 Team 탐색
- Team Version 관리
- 활성/비활성 관리
- Agentic Controller가 Case에 맞는 Team을 동적으로 선택

### Team 내부 자유도
각 Team은 다음을 독립적으로 결정할 수 있다.
- Single-Agent / Multi-Agent
- 자체 LangGraph/Subgraph
- 자체 Prompt
- Tool 조합
- Knowledge Scope
- Retrieval / Rerank 전략
- Episodic Memory 정책
- Rule/ML/LLM 혼합

### Platform과 Team의 경계
Platform은 Team별 업무 로직을 대신 만들지 않는다.

**Platform 공통 제공**
- Team Contract / Registry
- Case / Shared State
- Tool 권한 경계
- Vector/Search/Memory Store Port
- 기본 Adapter
- Auth / Audit / Observability

**각 Agent Team 소유**
- 어떤 문서를 검색할지
- 검색/Rerank 전략
- 무엇을 Memory에 저장할지
- 내부 Agent/Graph 구성
- Tool 호출 정책
- TeamResult 생성 규칙

즉, Team을 완전히 독립 서비스처럼 방치하는 것이 아니라  
공통 보안·상태·관측·저장 기반의 중복 구현은 제거하면서 업무 로직의 독립성은 유지한다.

### 권장 구조
```text
app/
├ core/
│  ├ contracts/
│  ├ registry/
│  ├ state/
│  ├ orchestration/
│  ├ context/
│  ├ messaging/
│  └ tools/
└ modules/
   └ customer_ops/
      └ team_modules/
         ├ team_a/
         │  ├ graph/
         │  ├ agents/
         │  ├ tools/
         │  ├ retrieval/
         │  ├ memory/
         │  └ prompts/
         └ team_b/
```

---

## 8-C. Agent/Team 경합과 동시성 처리 책임

Coordination은 Agent/Team 간 실행 경합을 조정하고, Shared State와 Tool Layer는 그 조정이 실패하거나 동시에 요청이 들어와도 상태와 실제 Action의 일관성이 깨지지 않도록 보장한다.

| 경합 종류 | 담당 |
|---|---|
| Team A vs Team B 실행 충돌 | Coordination |
| 동일 Case의 ownership / scheduling | Coordination |
| Message 중복 / retry / delivery | Coordination 정책 + Message Broker |
| Team 내부 Agent A vs Agent B | 각 Agent Team 내부 |
| 같은 Shared State 동시 수정 | State Repository / DB (version, CAS) |
| 같은 Action 중복 실행 | Tool / Action Layer (idempotency key) |
| DB 레코드 동시 변경 | Transaction / CAS / Lock |
| 여러 Team 결과 병합 | Coordination |

Team 내부 Agent 간 경합은 Top-Level Controller가 관리하지 않는다. Team을 하나의 실행 단위로 본다.

Team은 read Tool을 직접 호출하지 않는다. Context Broker가 `TeamManifest.required_context`를 Registry에서 읽고 필요한 데이터를 미리 조회하여 Context Pack에 넣는다. 추가 정보가 필요하면 Team은 `TeamResult.need_more_context`를 반환하고 Controller가 Context를 보강하여 재실행한다.

Team은 쓰기 작업을 실행하지 않고 `ActionProposal`만 반환한다. 실행은 Controller가 Core 2에 위임한다. 두 Core의 접점은 다음 두 계약으로 고정한다.

```text
Core1 → Core2: ExecuteAction(action_proposal, idempotency_key)
Core2 → Core1: ActionResult(status, provider_ref, error_code)
```

변경 전 흐름은 `Team → Core2 Action → Core1 State`였다. 변경 후 흐름은 `Team → Core1 Controller → Core2 Action → Core1 State`다. 이 구조는 토큰 예산과 중복 조회를 통제하고 평가 입력을 고정한다. Team 개발자는 Core 2 인터페이스를 직접 보지 않아도 된다.

Shared State 변경 계약은 다음과 같다.

```text
요청: SharedStateUpdate { case_id, expected_version, state_patch }
결과: UpdateResult = SUCCESS | CONFLICT | NOT_FOUND
```

Coordination은 `CONFLICT`를 받으면 최신 State를 재로드한다. 결과가 아직 유효하면 Retry하고, 그렇지 않으면 Replan한다.

---

## 9. 외부 소비자 AI 연동 구조

### 핵심 개념
사용자는 반드시 우리 웹 UI를 통해서만 문의를 처리하지 않아도 된다.  
자신이 사용하는 **ChatGPT / Claude / Gemini** 같은 개인 AI가  
우리 서비스의 **API/MCP**에 연결되어 고객을 대신해 문의·조회·작업 요청을 할 수 있다.

### 예시
사용자:
> "지난달 구독 해지했는데 이번 달에도 결제됐어. 확인해서 처리해줘."

개인 AI:
1. get_my_subscription()
2. get_payment_history()
3. open_support_case()
4. request_refund() (승인 필요 시 사용자 확인)

우리 플랫폼:
- 인증 확인
- Case 생성
- Billing Agent Team 처리
- 결과 반환

### 보안 원칙
- DB 직접 노출 금지
- SQL 실행형 도구 금지
- 사용자 Scope 기반 권한 제어
- 읽기/쓰기 도구 분리
- 환불/해지 등 쓰기 작업은 승인 단계 고려

---

## 9-C. MCP / A2A / Message Broker 역할 분리

MCP는 도구를 빌려주는 것이고, A2A는 일을 통째로 맡기는 것이다. MCP tool 호출은 짧고 stateless에 가깝지만, A2A Task는 장기 실행이며 자체 생명주기를 가진다.

MCP는 도구·Resource를 제공하는 수직 연결이고, A2A는 Agent System 사이의 업무 위임이다. REST API로 데이터를 주고받는 것 자체는 A2A가 아니다. A2A는 REST 위에 Agent Card(capability 발견), Task 생명주기(장기 실행·추가 입력 요구), Artifact 교환을 얹은 것이다. 상대가 사람이 만든 클라이언트면 REST, 상대가 에이전트이고 상호작용이 작업 위임이면 A2A다. A2A는 전송 계층이 아니라 상대의 자율성에 대한 규약이다.

### A2A가 쓰이는 세 경로

1. **우리가 A2A 클라이언트**: Billing Team이 환불을 판단할 때 사기 여부를 외부 Fraud Review Agent에 맡긴다. Agent Card로 capability를 발견하고 Task를 보내 Artifact를 받는다.
2. **우리가 A2A 서버**: 외부 오케스트레이터가 우리에게 SaaS 고객 문의를 위임한다. 우리는 Agent Card를 발행한다.
3. **우리 Team을 분리 배포하는 통로**: Team 수가 늘어 한 프로세스에 담기 어렵거나 Team별 모델·의존성이 달라지면 같은 Registry와 같은 `TeamResult` 계약을 유지한 채 실행 경로만 `LOCAL`에서 `A2A`로 바꾼다.

### A2A인지 판별하는 기준

핵심 질문은 주도권과 자율성이다. 상대가 대화·판단의 주도권을 쥐는가, 원격 쪽이 판단하는가 실행만 하는가를 확인한다.

| 상황 | 원격 쪽이 하는 일 | 분류 | 우리 설계의 Port |
|---|---|---|---|
| ChatGPT가 `get_my_cases()`를 호출하고 답변은 ChatGPT가 조립 | 우리 도구를 빌려 씀 | **MCP** (우리가 도구 제공자) | MCP Server |
| 외부 에이전트 플랫폼이 “이 환불 건 처리해줘”하고 결과를 기다림 | 일을 통째로 위임 | **A2A** (우리가 수주) | A2A Server / Agent Card |
| 우리가 외부 Fraud Review Agent에 Case 판단을 맡김 | 스스로 판단하고 추가 정보를 요구할 수 있음 | **A2A** (우리가 위임) | `TeamExecutorPort → A2ATeamExecutor` |
| 런팟 GPU에 프롬프트 추론·임베딩을 지시 | 지시대로 실행만 함 | **A2A 아님. LLM 추론** | `LLMPort` |
| 내부 워커에 배치 작업을 지시 | 지시대로 실행만 함 | **A2A 아님. 워커** | `MessageBusPort` |
| 런팟에 자체 판단하는 Agent Team을 통째로 올림 | 스스로 판단 | **A2A 맞음** | `TeamExecutorPort → A2ATeamExecutor` |

### Personal AI 경로와 기업용 Agent 경로

구조만 보면 우리 Case는 `waiting_approval`, `waiting_input` 같은 장기 상태를 가지므로 A2A Task 생명주기와 모양이 같다. 사실상 우리 Case가 A2A Task에 대응한다. 그럼에도 MVP에서 개인 AI 경로를 MCP로 두는 이유는 2026년 현재 확인 가능한 공식 통합 사례가 Azure AI Foundry, Copilot Studio, AWS Bedrock AgentCore, Google Vertex AI 같은 기업용 Agent 플랫폼에 집중되어 있고, ChatGPT·Claude 같은 개인 AI의 외부 서비스 연결은 MCP가 실제 사용 경로이기 때문이다.[^6][^7][^8][^9][^10] 이는 개인 AI가 A2A를 영원히 지원하지 않는다는 뜻이 아니라 MVP의 연결 대상을 구분하는 판단이다.

| 사용 주체 | 위임 경로 | MVP 판단 |
|---|---|---|
| 개인이 쓰는 ChatGPT·Claude | 사용자의 Tool/Resource 접근 | MCP |
| 고객사의 Agent 플랫폼 | Case 업무를 우리 Agent에 위임 | A2A |

두 경로를 모두 유지한다. 개인 AI는 MCP, 고객사의 Agent 플랫폼이 대신 위임하는 경우는 A2A다.

### A2A Task와 Case 상태 매핑

A2A Task는 자체 생명주기를 가지므로 우리 Case 상태와 이중 상태 머신이 된다. 매핑은 Adapter가 수행하고 Controller는 Case 상태만 본다.

| Remote Task 상태(의미) | 우리 Case 상태 | Adapter 처리 |
|---|---|---|
| 진행 중 | `running` | Task를 추적하고 deadline까지 상태를 조회한다. |
| 추가 입력 필요 | `waiting_input` | 필요한 질문을 `TeamResult.need_more_context`로 정규화한다. |
| 완료 | `resolved` 또는 후속 판단 | Artifact를 `TeamResult`로 정규화하고 Controller가 다음 판단을 한다. |
| 실패 | `escalated` | 재시도 한도를 넘으면 오류 근거와 함께 운영자/다음 Team으로 넘긴다. |
| 취소 | `cancelled` | 취소 사유와 `task_id`를 기록한다. |
| 상태·결과를 알 수 없음 | `escalated` + 원격 결과 `unknown` | deadline 초과 또는 조회 실패 시 임의로 완료 처리하지 않는다. |

타임아웃은 `deadline_s`를 기준으로 하고, 네트워크 단절·일시 오류에만 지수 백오프 재시도를 적용한다. 재시도 횟수와 상한 시간은 Adapter 설정으로 둔다. deadline이 지나거나 원격 결과를 확인할 수 없으면 결과를 `unknown`으로 두고 Case를 `escalated`로 남긴다. 중복 Task를 막기 위해 `case_id`와 idempotency key를 함께 사용한다.

### MVP 범위

- 지금 구현: `TeamExecutorPort`, Registry의 `execution_type`/`agent_card_url`/`a2a_endpoint`/`auth_scheme`, A2A Task 상태와 Case 상태 매핑 규칙, `TeamResult` 정규화, 우리가 만든 더미 Remote Agent 1개
- 나중 과제: 실제 외부 조직 상호운용, Signed Agent Card 검증, 다자 위임

### Agent Team Registry 확장

```text
team_id
capabilities[]
execution_type: LOCAL | A2A
version
entrypoint
agent_card_url
a2a_endpoint
auth_scheme
allowed_tools[]
knowledge_scope[]
status
```

- LOCAL: Message Broker를 통해 내부 Agent Team Slot 실행
- A2A: A2A Adapter를 통해 Remote Agent System 호출
- 두 실행 결과는 TeamResult로 정규화하여 Shared State에 반영

---

## 9-D. Graph DB / GraphRAG 활용 계획

GraphRAG에는 두 종류가 있다.

1. 비정형 문서에서 LLM으로 지식 그래프를 추출하는 방식은 채택하지 않는다. 우리 관계는 PostgreSQL FK로 이미 정형화되어 있어 다시 추출할 이유가 없다. 외부 리서치에서는 Vector RAG 대비 3~5배 비용, 엔티티·관계 환각 위험, 엔터프라이즈 RAG 구현의 72~80%가 프로덕션에 도달하지 못했다는 분석이 보고되었다. 이 수치는 외부 리서치 인용이며 우리 환경 측정치가 아니다.[^1][^2]
2. 이미 정형화된 관계를 그래프로 질의하는 방식은 채택한다. 다만 MVP 저장소는 PostgreSQL이다.

현재 시나리오 A와 B의 관계 질의는 깊이 1~2이며 JOIN과 집계로 정확히 계산된다. 시나리오 C의 반복 VOC 급증은 `GROUP BY`, `HAVING`, 윈도 함수가 그래프보다 적합하다. “그거 그냥 JOIN 아니냐”는 질문에는 “현재 규모에서는 맞다”고 답한다. 관계형 데이터를 그래프 의미로 조회하지만, 전용 Graph DB가 필요한 규모는 아니다.

Graph가 실제로 유리해지는 지점은 다음과 같다.

- **A2A 위임 토폴로지**: Remote Agent System에 Task를 위임하면 관계가 외부로 뻗는다. “이 Case를 어떤 Agent들이 어떤 순서로 거쳤고 각 단계에서 무슨 Artifact가 나왔는가”는 깊이가 가변인 경로 질의다. Capability 기반 라우팅에서 처리 가능한 Team이 없을 때 누구에게 위임 가능한가를 찾는 것도 그래프 탐색이다.
- **설명가능성 경로**: `Case → Evidence → KnowledgeDocument → Policy → Decision → Action`을 거슬러 올라가는 근거 추적은 경로 깊이가 고정되지 않는다.

그래도 지금은 전용 Graph Store를 도입하지 않는다. MVP는 Team 2개와 Remote PoC 1개이며 위임 깊이는 2다. 깊이 2에는 그래프 저장소가 필요 없다.

판단이 뒤집히는 조건은 다음과 같다.

- Remote A2A Agent가 2개 이상 되어 위임 깊이가 3 이상이 될 때
- 정책에 계층 상속(글로벌 → 제품 → 지역 오버라이드)이 생길 때
- 사전 정의한 multi-hop 질의에서 SQL 경로의 근거 포함률이 목표에 못 미칠 때

### Port / Adapter 설계

```python
from typing import Protocol

class GraphStorePort(Protocol):
    async def neighbors(self, node_id: str, edge_types: list[str], depth: int = 1) -> list[dict]: ...
    async def path(self, src: str, dst: str, max_depth: int = 4) -> list[dict]: ...
    async def subgraph(self, root_id: str, depth: int = 2) -> dict: ...
```

- MVP: `SqlGraphAdapter`가 PostgreSQL JOIN과 재귀 CTE로 구현한다.
- Phase 2: `AgeGraphAdapter` 또는 `Neo4jGraphAdapter`를 같은 Port에 꽂아 동일 질의로 성능을 비교한다.
- Apache AGE도 검토했다. PostgreSQL 확장이라 같은 DB 안에서 openCypher 질의를 수행하고 Projection 동기화가 필요 없다. 대신 생태계가 작고 깊은 탐색이 Neo4j보다 느리다는 외부 리서치 근거가 있어 비교 대상으로 둔다.[^3]

별도 Graph Store를 사용하면 다음 숨은 비용이 추가된다. 25~40인·일은 Graph DB를 띄우는 비용이 아니라 Projection 동기화와 검증을 포함한 추가 작업량이다.

| 작업 | 추가 비용(인·일) |
|---|---:|
| Graph 모델·Adapter·쿼리 설계 | 4~6 |
| 초기 Projection과 seed | 3~5 |
| 변경 이벤트 또는 주기 동기화 | 5~8 |
| 재시도·중복·순서 역전·삭제 반영 테스트 | 4~6 |
| Context Pack 결합 | 3~5 |
| 모니터링·불일치 검증·발표 시각화 | 4~6 |
| **합계** | **25~40** |

이중 저장소에서는 Projection lag, 삭제 반영 누락, 순서 역전, 재시도 중복, PostgreSQL과 Graph 간 불일치 검증이 운영 책임이 된다. PostgreSQL은 유일한 Source of Truth로 유지한다.

### 8~9주차 비교 실험

8~9주차에 일정 여유가 있으면 같은 `GraphStorePort`에 두 Adapter를 꽂고 동일 질의셋으로 비교한다. 대상은 `SqlGraphAdapter`와 `AgeGraphAdapter` 또는 `Neo4jGraphAdapter`다.

| 측정 항목 | 기준 |
|---|---|
| 근거 포함률 | multi-hop 질의 결과가 필요한 근거를 포함하는 비율 |
| p95 지연 | 동일 환경과 동일 질의셋의 95백분위 지연 |
| 구현·운영 인·일 | Adapter, 배포, 동기화, 검증에 든 추가 작업량 |
| Projection lag | 별도 저장소를 사용한 경우 commit부터 반영까지의 지연 |

결과와 무관하게 “어떤 상황에 Graph DB를 써야 하는가” 판단 기준표를 최종 산출물로 낸다.

### Graph DB 판단 기준표

| 판단 항목 | SQL이 낫다 | Graph가 낫다 | 전환 임계 조건 |
|---|---|---|---|
| 관계 깊이 | 깊이 1~2, FK가 명확함 | 깊이 3 이상, 경로 깊이가 가변임 | A2A 위임 깊이 3 이상이 반복 발생 |
| 스키마 안정성 | 테이블과 FK가 자주 바뀌지 않음 | 관계·노드 종류가 자주 늘고 런타임에 탐색해야 함 | 계층 상속 또는 동적 edge가 운영 요구가 됨 |
| 관계의 위치 | 관계가 PostgreSQL에 이미 있음 | 관계가 여러 외부 Agent와 Artifact에 분산됨 | 단일 SQL Source of Truth로 경로를 복원하기 어려움 |
| 경로 질의 빈도 | 고정 질의와 집계가 중심임 | 임의 multi-hop 경로 질의가 핵심임 | 사전 정의 질의의 SQL 근거 포함률이 목표 미달 |
| 시각화 요구 | 표·고정 경로로 충분함 | 사용자가 임의로 이웃과 경로를 탐색해야 함 | 경로 탐색 UI가 핵심 평가 항목이 됨 |
| 팀 규모 | 6명, 25~40인·일 추가가 부담됨 | Graph 운영 담당자가 별도 있음 | 운영 담당자와 장애 대응 시간이 확보됨 |
| 운영 인력 | PostgreSQL 운영 인력만 있음 | Graph 운영·동기화·검증 담당이 있음 | lag·불일치·재처리 지표를 지속 관리할 수 있음 |

### 역할과 적용 단계

- Vector Search: 의미적으로 비슷한 문서와 Entity 탐색
- 관계 조회(GraphStorePort): PostgreSQL의 정확한 Case·Issue·Policy·Product·Team·Action 관계 탐색
- Context Broker: Vector Search와 관계 조회, DB 상태, Memory를 Context Pack으로 조합

```text
Customer -REPORTED-> Case
Case -HAS_ISSUE-> Issue
Issue -AFFECTS-> Product
Product -GOVERNED_BY-> Policy
Case -HANDLED_BY-> AgentTeam
Case -TRIGGERED-> Action
Case -USED_EVIDENCE-> KnowledgeDocument
```

적용 순서는 PostgreSQL + pgvector Vector RAG, `SqlGraphAdapter`, Remote A2A Team 1개 PoC 순서다. Phase 2 비교는 8~9주차 여유가 있을 때 수행한다.

---

## 10. 핵심 사용자 시나리오

### 시나리오 A: 구독 해지 후 추가 결제
1. 고객이 문의하거나 개인 AI를 통해 요청
2. 감성/의도/이슈 분류
3. Billing Case 생성
4. Billing Agent Team이 결제 이력/구독 상태/정책 조회
5. 환불 가능 여부 판단
6. 결과를 고객에게 응답
7. 필요 시 Human Approval 후 환불 요청 처리

### 시나리오 B: Free/Pro 권한 동기화 오류
1. 고객이 "Free로 바꿨는데 Pro 기능이 남아 있어요" 문의
2. Technical Case 생성
3. Technical Agent Team이 entitlement state, account state, incident history 확인
4. 원인 후보(동기화 실패, 캐시 문제, 구독 상태 불일치) 분석
5. 해결책 제시 또는 내부 조치 요청
6. 결과 공유 및 종료

### 시나리오 C: 반복 불만 탐지
1. VOC Agent Team이 일정 기간 고객 문의/리뷰 분석
2. 비슷한 이슈가 반복되는지 cluster / trend 분석
3. 관리용 리포트 생성
4. 특정 이슈 급증 시 Technical Team에 알림

---

## 11. 데이터 구조 초안

### 주요 테이블
- users
- external_ai_clients
- api_tokens / oauth_connections
- customer_feedback
- customer_cases
- case_events
- agent_teams
- agent_runs
- knowledge_documents
- memory_items
- action_requests
- action_approvals
- voc_reports

### 핵심 관계
- user 1:N customer_cases
- customer_cases 1:N case_events
- customer_cases 1:N agent_runs
- knowledge_documents N:1 domain/module
- action_requests 1:1 or N:1 approval records

---

## 12. 기술 스택(권장)

### Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy
- PostgreSQL

### Agent / Orchestration
- LangGraph 1.0 (2025년 10월 릴리스, 상위 workflow 및 상태 흐름)
- 체크포인터: `AsyncPostgresSaver`
- `InMemorySaver`는 사용하지 않는다. 재시작 시 진행 상태가 사라질 수 있다.
- `thread_id = case_id`로 매핑한다.
- LangChain 또는 자체 경량 RAG 모듈
- OpenAI / Anthropic / Google 모델 API (선택)

### Retrieval / Memory
- pgvector 또는 Chroma
- BM25 + Vector Hybrid Retrieval
- RAG document pipeline

### Frontend
- React
- TypeScript
- Tailwind CSS (선택)
- 상태 시각화 대시보드

### Dev / Infra
- Docker
- GitHub Actions
- pytest
- ERD / Mermaid 또는 SVG 기반 시각화

### External Agent Integration
- REST API / OpenAPI
- MCP Server
- A2A Adapter / Agent Card / Remote Task
- OAuth 2.0
- GraphStorePort (MVP: SQL Adapter, Phase 2: AGE/Neo4j 비교)

---

## 13. 클린 아키텍처 기반 폴더 구조(권장)

```text
project/
├ app/
│  ├ presentation/
│  │  ├ api/
│  │  ├ web/
│  │  └ schemas/
│  ├ application/
│  │  ├ usecases/
│  │  ├ services/
│  │  ├ workflows/
│  │  └ orchestrators/
│  ├ domain/
│  │  ├ entities/
│  │  ├ value_objects/
│  │  ├ repositories/
│  │  └ policies/
│  ├ infrastructure/
│  │  ├ db/
│  │  ├ vectorstore/
│  │  ├ llm/
│  │  ├ adapters/
│  │  └ integrations/
│  └ modules/
│     └ customer_ops/
│        ├ agents/
│        ├ tools/
│        ├ prompts/
│        ├ knowledge/
│        └ workflows/
├ tests/
├ docs/
├ scripts/
└ docker/
```

---

## 14. 구현 단계 계획(8~10주)

### 1단계: 기획 / 데이터 설계
- 프로젝트 범위 확정
- 도메인(SaaS Customer Ops) 확정
- Case 시나리오 정의
- ERD 및 상태 전이 설계

### 1~2주차 Core 1 착수 계획

Core 1이 1주차에 내놓는 것은 동작하는 Core가 아니라 계약과 가짜 구현이다.

| 기간 | Core 1 산출물 |
|---|---|
| Day 1~3 | `core/contracts/` — TeamTask, TeamResult, ContextPack, ActionProposal, ActionResult, SharedStateUpdate, UpdateResult, CaseStatus |
| Day 4~5 | `core/fake/` — FakeController(고정 라우팅), FakeContextBroker(픽스처 JSON), FakeMessageBus(동기 호출), InMemoryStateRepo(dict + version) |

나머지 5명은 Core 구현을 기다리지 않고 다음 작업을 진행한다.

| 담당 | 1~2주차 작업 |
|---|---|
| E | 정책/FAQ 25건 작성, seed DB 생성기, 청킹·임베딩 파이프라인. 1~2주차 최대 작업량으로 둔다. |
| C | Billing mock Tool, 픽스처 기반 Team 그래프 골격, pytest 단독 실행 |
| D | Technical mock Tool, 픽스처 기반 Team 그래프 골격, pytest 단독 실행 |
| Core 2 | Agent Gateway, API key/scope, REST 스켈레톤(mock Case 반환) |
| F | Case 목록·상세 화면을 고정 JSON 픽스처로 선구현, golden 데이터셋 스키마 |

1주차 금요일을 Contract Freeze Day로 정한다. 이후 계약 변경은 PR과 전원 합의를 거친다. 3주차 끝에 mock Team으로 Case 1건이 `new → resolved`를 관통하지 못하면 병목으로 판정한다.

### 2단계: Core Basement MVP
- Agent Registry
- `TeamExecutorPort`와 `LocalTeamExecutor` / `A2ATeamExecutor`
- MessageBusPort, GraphStorePort의 공통 Adapter 계약
- Tool Registry
- Shared State
- Context Broker
- 기본 Workflow

### 3단계: Customer Ops Module 구현
- Billing Agent Team
- Technical Support Agent Team
- VOC Agent Team
- FAQ / 정책 RAG

### 4단계: 외부 AI Agent API
- 사용자 인증
- OpenAPI 문서
- 주요 business capability API
- 가능 시 MCP 시범 구현

### 5단계: 운영자 웹 대시보드
- Case 목록
- 상태 전이
- Agent Run 결과
- VOC 리포트
- 승인 UI

### 6단계: 평가 / 고도화
- Baseline 비교
- 응답 정확도/유효성
- 재처리 성공률
- Human intervention 감소 여부
- 8~9주차: 같은 Agent Team을 같은 입력·같은 seed로 LOCAL과 A2A에서 각각 실행하고 `TeamResult`를 비교한다. Core 코드를 바꾸지 않고 두 결과가 동일한 스키마·판정·근거를 내는지 검증한다. 이 시연이 모듈형 Basement와 Team 수 확장성의 직접 증거다.
- 발표용 시연 시나리오 정리

---

## 15. 평가 계획

### Baseline A
- 단일 LLM + 단순 RAG

### Baseline B
- 고정형 멀티에이전트 파이프라인
  - 분석 → 검색 → 생성 → 검수

### Proposed
- Shared State + Context Broker + 전문 Agent Team + External AI API

### 평가 지표
- 문의 처리 성공률
- 응답 품질
- 정책 일관성
- Case 재처리 성공률
- 평균 처리 단계 수
- Human intervention 빈도
- VOC 이상징후 탐지 품질
- 외부 AI 연동 성공률

---

## 16. 팀 역할 제안 — 6명 기준

### 전체 배분
- **Core 1 · Case Runtime & Coordination — 1명**
- **Core 2 · Access & Action Platform — 1명**
- **Agent Team Module 개발 — 3명**
- **UX / Observability / Evaluation — 1명**

코드의 책임 경계와 사람의 담당 경계를 똑같이 만들 필요는 없다.

### Core 1 · Case Runtime & Coordination — 1명
- Customer Case, Lifecycle, Shared State, State Repository
- version, CAS/Optimistic Concurrency
- Agentic Controller, Top-Level LangGraph, Routing, Ownership
- Retry/replan/Cancel, WAIT/RESUME
- Agent Team Registry, Team Contract
- Message Broker(Task/Event, Queue, Retry)

### Core 2 · Access & Action Platform — 1명
- Agent Gateway
- OAuth/Token/Scope/Client Identity
- REST/MCP, A2A Adapter
- Tool/Action Gateway, Business API
- Action Permission, Human Approval
- Idempotency, Audit, 외부 시스템 연동

### Agent Team Module 개발 — 3명
최종 Agent Team 종류와 개수는 요구사항 분석 후 결정한다.
- Team 내부 Agent/Subgraph
- Prompt/Tool 조합
- Knowledge Scope
- Retrieval / Rerank
- Episodic Memory 정책
- Team 단위 테스트/재처리 시나리오

배치 예:
- Team 3개 → 각 1명
- Team 2개 → 2명 + 1명
- 복잡한 Team 하나에 2명 배치 가능

### UX / Observability / Evaluation — 1명
- 사용자/운영자 Web UI
- Case 상태 / Agent Trace / Approval 화면
- Baseline vs Agentic 평가 Harness
- 성공률 / Tool 호출 / 재처리 / latency / cost 지표
- 통합 데모 / 평가 리포트

### DB 소유

| 담당 | 소유 데이터 |
|---|---|
| Core 1 | `customer_cases`, `case_events`, `shared_state`, `agent_runs` |
| Core 2 | `external_ai_clients`, `oauth_connections`, `action_requests`, `action_approvals`, `audit_logs` |
| 공통 합의 | SQLAlchemy 설정, Alembic, DB Connection, Base Repository |

백엔드 담당자 1명이 모든 DB 코드를 맡는 역할은 두지 않는다.

CAS와 Idempotency는 대상이 다르다. Core 1은 같은 Case 상태를 두 작업이 동시에 수정하는 상황을 version/CAS로 다룬다.
Core 2는 같은 환불을 두 번 실행하려는 상황을 idempotency key로 막는다.
따라서 두 책임은 겹치지 않는다.

### 책임 경계
- 어느 Team을 언제 호출하는가? → Core 1
- 외부 AI가 어떤 권한으로 어떻게 들어오는가? → Core 2
- 선택된 Team 안에서 문제를 어떻게 푸는가? → Agent Team 개발자 3명
- 사용자가 무엇을 보고 시스템 품질을 어떻게 측정하는가? → UX/Evaluation 1명

### Alembic 규칙

DB를 Core 1과 Core 2가 나눠 갖되 Alembic revision은 단일 브랜치로 유지한다.

- revision 생성 전 main을 rebase한다. 두 사람이 같은 시점에 revision을 만들지 않는다.
- 머지 충돌이 나면 `alembic merge`로 봉합하지 않고 revision 순서를 재정렬한다.
- CI에서 `alembic upgrade head` → `downgrade -1` → `upgrade head`를 검증한다.

---

## 17. 사용자 본인 역할 어필 문장 예시

> 저는 개별 Agent 하나의 기능 구현보다는, 각 Agent Team이 공유 상태와 기업 지식을 기반으로 협업할 수 있도록 전체 Agentic AI 실행 구조를 설계하고 구현하는 역할을 맡고 싶습니다. 구체적으로는 Shared State, Context Broker, Agent Registry, Tool/API Gateway, External AI Agent 연동, 상위 Workflow와 평가 구조를 담당하겠습니다.

---

## 18. 예상 리스크와 대응

### 리스크 1. 범위 과대
- 대응: 도메인 1개(SaaS), Agent Team 3개로 제한

### 리스크 2. 멀티에이전트 복잡성 과다
- 대응: Team 내부는 단순화, 상위 Controller 중심 설계

### 리스크 3. 외부 AI 연동 범위 과대
- 대응: REST/OpenAPI 우선, MCP는 시범 수준

### 리스크 4. RAG 품질 저하
- 대응: FAQ/정책 문서 중심의 소규모 고품질 corpus 구축

---

## 18-A. 결정사항의 주의점

| 결정사항 | 주의할 점 |
|---|---|
| Message Broker를 Coordination이 소유 | Controller가 Broker의 전달 보장에 의존하기 쉽다. 전달 보장과 중복 처리는 8-A의 consumer 규칙과 강제 테스트로 검증한다. |
| MVP에서 in-process queue 사용 | Broker가 사실상 함수 호출이 될 수 있다. 중복 전달과 재시도를 강제로 발생시키는 테스트를 둔다. |
| Top-Level LangGraph와 Message Broker 병행 | Top-Level LangGraph는 Case 내부 흐름을 결정하고, Message Broker는 결정된 Team 실행을 배달한다. Broker는 다음에 무엇을 할지 결정하지 않는다. |
| Core 1의 넓은 범위 | Case, State, CAS, Controller, Graph, Registry, Broker가 병목이 되면 Team 개발 3명이 모두 막힌다. 1~2주차에 Contract를 확정하고 stub Core를 내놓는다. |
| Core 간 왕복 계약 | Team은 Context Pack을 읽고 ActionProposal만 반환한다. Controller가 Core 2에 `ExecuteAction`을 요청하고 `ActionResult`를 Core 1 State에 반영한다. 이 계약을 1주차에 고정한다. |
| DB 소유 분리 | Alembic revision이 두 갈래로 갈라질 수 있다. 마이그레이션은 단일 브랜치와 순서 합의 규칙으로 관리한다. |
| A2A Task 도입 | A2A Task와 Case 상태가 이중 상태 머신이 된다. 매핑 규칙을 정하고, 우리 더미 Remote Agent 1개로 PoC하는 선까지로 범위를 둔다. |
| GraphRAG 채택 | 채택 게이트를 통과하지 못하면 버린다. 버리는 것도 평가 결과로 보고한다. |

---

## 19. 엑셀 입력용 요약(이미지 구조 대응)

| 번호 | 팀 이름 | 팀원 | 프로젝트 주제 | 프로젝트 주제 설명 | 활용 기술 스택 |
|---|---|---|---|---|---|
| 6 | A-COP Lab *(예시)* | [팀원명 입력] | 다중 에이전트 서빙 기반 고객 피드백 분석 및 맞춤형 응대 자동화 시스템 | 고객 리뷰·문의·상담 로그를 분석하여 감성·의도·이슈를 분류하고, 요구사항에 따라 구성되는 업무별 전문 Agent Team Module이 Shared State와 기업 지식(RAG)을 기반으로 협업하여 맞춤형 응대를 수행하는 Agentic Customer Operations Platform을 구축한다. 또한 사용자가 ChatGPT·Claude·Gemini 같은 개인 AI를 통해 우리 서비스의 Agent API/MCP에 접속하여 문의·조회·작업 요청을 수행할 수 있도록 외부 AI 연동 인터페이스를 제공한다. | Python, FastAPI, PostgreSQL, pgvector, React, LangGraph, RAG, OpenAPI, OAuth2, Docker |

### 엑셀 셀에 더 짧게 넣는 버전
- **프로젝트 주제(짧은 별칭)**: A-COP: AI 연동형 모듈형 에이전틱 고객운영 플랫폼
- **프로젝트 주제 설명(짧은 버전)**: 고객 피드백 분석과 맞춤형 응대를 위해 업무별 Agent Team Module이 Shared State·RAG·Memory를 기반으로 협업하는 모듈형 Agentic Customer Operations Platform. 개인 AI(ChatGPT/Claude/Gemini) 연동 API 제공.
- **활용 기술 스택(짧은 버전)**: FastAPI, React, PostgreSQL, pgvector, LangGraph, RAG/관계 조회, MCP, A2A, OpenAPI, OAuth2, Redis/RabbitMQ, Docker

---

## 20. 최종 정리

이 프로젝트의 차별점은 다음과 같다.

1. **부트캠프 주제를 유지한다.**
2. **단순 LLM 파이프라인이 아니라 실제 업무 단위 Agent Team을 둔다.**
3. **고객 응답뿐 아니라 상태 기반 운영(Case)을 다룬다.**
4. **RAG를 답변용 검색이 아니라 Agent Context 제공 계층으로 사용한다.**
5. **개인 AI가 고객을 대신해 우리 서비스에 접속하는 구조까지 고려한다.**
6. **향후 다른 도메인에도 확장 가능한 모듈형 Basement 구조를 설계한다.**

---

## 참고 출처

확인일: 2026-08-12. 아래 수치와 외부 표준 관련 내용은 외부 리서치 인용이며 우리 환경 측정치가 아니다.

[^1]: `program/research/_research_facts.md`의 GraphRAG 리서치 요약. Vector RAG 대비 3~5배 비용, 단일 사실 조회의 낮은 효용, LLM 추출의 엔티티·관계 환각 위험을 정리한다.
[^2]: `program/research/_research_facts.md`의 2026년 엔터프라이즈 RAG 분석 요약. 구현의 72~80%가 프로덕션에 도달하지 못하며 graph 구축 오버헤드가 반복 원인이라는 내용을 담는다.
[^3]: `program/research/graphrag_decision.md`의 Graph Store 비용·대안 검토. Apache AGE는 본 문서의 비교 실험에서 검증할 후보이며, AGE의 생태계와 깊은 탐색 성능 평가는 외부 리서치 근거로 기록한다.
[^4]: `program/research/_research_facts.md`의 A2A 리서치 요약. Linux Foundation 이관, 스펙 1.0, 150개 이상 조직 참여와 주요 클라우드 통합 내용을 담는다.
[^5]: `program/research/_research_facts.md`의 A2A·AAIF 리서치 요약. 2025년 12월 AAIF 신설과 MCP·A2A 공동 거버넌스 내용을 담는다.
[^6]: [Microsoft Foundry: Connect to an A2A agent endpoint](https://learn.microsoft.com/en-gb/azure/foundry/agents/how-to/tools/agent-to-agent?view=foundry). Foundry Agent Service의 A2A endpoint 제공과 연결 사례를 확인했다.
[^7]: [Amazon Bedrock AgentCore: Deploy A2A servers](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a.html). AgentCore Runtime의 A2A 서버 배포, Agent Card, 장기 실행 Agent 지원을 확인했다.
[^8]: [Google Cloud: A2A protocol documentation](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/develop/a2a). Vertex AI Agent Engine의 A2A 지원 여부를 확인한 공식 문서다.
[^9]: [Anthropic: Model Context Protocol](https://platform.claude.com/docs/en/docs/mcp). Claude 제품과 Messages API에서 MCP 연결을 지원하는 공식 문서다.
[^10]: [Microsoft Copilot Studio: Connect to an agent over A2A](https://learn.microsoft.com/en-us/microsoft-copilot-studio/add-agent-agent-to-agent). Copilot Studio가 A2A Agent에 Task를 위임하는 공식 문서다.
