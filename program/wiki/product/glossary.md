---
type: concept
title: 용어
description: A-COP에서 쓰는 핵심 용어 정의. 문서와 코드가 같은 뜻으로 쓰는지 확인하는 기준
status: draft
tags: [customer-operations]
size_exempt: true
size_exempt_reason: 용어 카탈로그. 검색 대상이므로 한 파일로 유지
---

# 용어

문서와 코드가 같은 단어를 같은 뜻으로 쓰는지 확인하는 기준이다. **여기 정의와 다르게 쓰면 둘 중 하나를 고친다.**

## 핵심 개념

### Case
고객 문의 하나가 만들어내는 **업무 단위**. 생성부터 종료까지 상태를 가지며 여러 Team이 관여할 수 있다.

문의 = Case가 아니다. 한 문의가 여러 Case를 만들 수도, 여러 문의가 한 Case에 붙을 수도 있다.

→ [`case-lifecycle.md`](../../final_project_cs/wiki/runtime/case-lifecycle.md)

### Shared State
Case의 **공식 상태**. 버전을 가지며 모든 갱신은 CAS를 거친다.

**Case의 단일 원천이다.** Team이 따로 상태를 들고 있으면 안 된다.

→ [`shared-state.md`](../../final_project_cs/wiki/runtime/shared-state.md)

### Agent Team
업무 책임 단위. capability·책임·권한·지식·Tool 경계가 독립될 때 만든다.

내부에 Agent가 몇 개인지, LangGraph를 쓰는지는 Team이 결정한다. Core는 관여하지 않는다.

**Team이 하지 않는 것 셋.**
- side effect를 실행하지 않는다 (`ActionProposal`만 반환)
- read Tool을 직접 호출하지 않는다 (Context Broker가 넣어준다)
- 다른 Team을 직접 호출하지 않는다 (Controller가 Task로 변환)

→ [`team-contract.md`](../../final_project_cs/wiki/teams/team-contract.md)

### Capability
Team이 처리할 수 있는 **업무 종류**. `refund.calculate`, `payment.status` 같은 식별자.

Controller가 capability로 Team을 찾는다. Team 이름으로 찾지 않는다.

### Agentic Controller
Case를 어느 Team으로 보낼지 정하고, 재시도·재계획·WAIT/RESUME을 통제하는 상위 오케스트레이션.

**Team을 직접 생성하지 않는다.** 반드시 Registry를 거친다.

→ [`agentic-controller.md`](../../final_project_cs/wiki/runtime/agentic-controller.md)

### Context Broker
Team이 필요로 하는 자료를 읽어서 한 묶음(`ContextPack`)으로 만들어 주는 계층.

Team이 `required_context`를 선언하면 Broker가 예산 안에서 조합한다. 부족하면 Team이 `need_more_context`로 요청한다.

→ [`context-broker.md`](../../final_project_cs/wiki/context/context-broker.md)

### ContextPack
Context Broker가 만든 자료 묶음. Team의 입력이다.

**예산이 있다.** 무한정 담지 않는다.

### ActionProposal
Team이 "이걸 하자"고 제안하는 것. **실행이 아니다.**

Core가 근거를 대조하고, 위험도를 판정하고, 필요하면 사람 승인을 받은 뒤에 실행한다.

→ [`action-proposal.md`](../../final_project_cs/wiki/actions/action-proposal.md)

### Action
바깥 세계를 실제로 바꾸는 동작. 환불 실행, 알림 발송 등.

**A-COP에서 side effect가 일어나는 유일한 경로다.**

### Team Registry
capability를 Team 구현으로 해석하는 곳.

Team을 추가·교체할 때 **Core 코드가 바뀌지 않게** 하는 장치다.

→ [`team-registry.md`](../../final_project_cs/wiki/teams/team-registry.md)

## 구조 용어

### Core (Basement)
도메인을 모르는 공통 실행 기반. Case·Controller·Registry·Port·승인 경계·감사·평가.

**도메인 어휘가 들어오면 테스트가 실패한다.** → `INV-CS-ARCH-001`

### Pack
도메인 지식을 담은 Team 묶음. CS Pack, Commerce Ops Pack.

Core에 남는 것과 Pack으로 가는 것의 판정 기준은 **도메인 지식이 필요하면 Pack, 무관하면 Core**다.

→ [../architecture/pack-model.md](../architecture/pack-model.md)

### Port / Adapter
저장소·외부 시스템을 교체 가능하게 만드는 인터페이스. `GraphStorePort`, `MessageBusPort` 등.

## 연동 용어

### MCP
개인 AI가 우리 Tool과 Resource를 쓰는 경로. ChatGPT·Claude 같은 개인 AI의 실제 연결 방식.

### A2A
독립 배포된 Agent System에 **장기 실행 업무를 위임**하는 경로. Agent Card, Task lifecycle, Artifact가 있다.

**단순 데이터 조회는 A2A가 아니다.** REST다.

### Agent Gateway
외부 요청이 내부로 들어오는 **Trust Boundary**.

## 평가 용어

### 골든셋
평가 기준이 되는 케이스 모음. 현재 72건. `[실측]`

### 근거 정합률
모델이 제안한 필드 중 Context/DB에 실재하고 일치하는 비율.

### 근거 초과율
Context/DB에 없는데 모델이 주장한 비율. **할루시네이션 지표다.**

### 적절한 기권율 / 과잉 기권율
근거가 부족할 때 `escalate`한 비율 / 근거가 충분한데 `escalate`한 비율.

**둘의 균형이 제품의 핵심 값이다.** 기권이 0이면 안전장치가 없는 것이고, 너무 많으면 자동화 이득이 사라진다.

→ [../evaluation/metrics.md](../evaluation/metrics.md)

## 헷갈리기 쉬운 짝

| A | B | 차이 |
|---|---|---|
| Case | 문의 | 문의는 입력, Case는 업무 단위 |
| ActionProposal | Action | 제안 vs 실행 |
| Team | Agent | Team은 책임 단위, Agent는 그 안의 구현 |
| MCP | A2A | 도구 호출 vs 업무 위임 |
| Core | Pack | 도메인 모름 vs 도메인 앎 |
| escalate | handoff | 근거 부족으로 넘김 vs 처음부터 사람 몫 |

## 관계

- [../architecture/core-vs-team.md](../architecture/core-vs-team.md) — Core/Team 경계 판정
- [`final_project_cs/wiki/index.md`](../../final_project_cs/wiki/index.md) — 각 개념의 구현
