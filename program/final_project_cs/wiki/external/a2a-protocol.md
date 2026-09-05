---
type: contract
title: A2A
description: 독립 배포된 Agent System에 장기 실행 업무를 위임한다. Port로 로컬과 교체된다
status: draft
tags: [api, agent, contract]
owners: [human:미배정]
---

# A2A

`app/core/remote_team/a2a_executor.py` · `app/presentation/a2a/` · `app/infrastructure/a2a/http_transport.py`

## 무엇인가

**독립 배포된 Agent System에 장기 실행 업무를 위임한다.**

`[실측]` v8 §9-C의 정의가 정확하다.

> **MCP는 도구를 빌려주는 것이고, A2A는 일을 통째로 맡기는 것이다.**
>
> A2A는 REST 위에 **Agent Card(capability 발견), Task 생명주기(장기 실행·추가 입력 요구), Artifact 교환**을 얹은 것이다.
>
> **A2A는 전송 계층이 아니라 상대의 자율성에 대한 규약이다.**

**마지막 문장이 핵심이다.** HTTP를 쓰느냐가 아니라 **상대가 스스로 판단하느냐**가 A2A를 정한다.

| | 상대가 |
|---|---|
| 사람이 만든 클라이언트 | **REST** |
| 에이전트이고 상호작용이 작업 위임 | **A2A** |

MCP와 다르다.

| | MCP | A2A |
|---|---|---|
| 상대 | 개인 AI | 기업 Agent System |
| 무엇 | 도구 호출·자원 접근 | **업무 위임** |
| 있어야 할 것 | — | Agent Card, Task lifecycle, 추가 입력, Artifact |

**단순 데이터 REST 호출은 A2A가 아니다.**

## ★ 판별 기준 — 주도권과 자율성

`[실측]` v8 §9-C에서 이관.

**핵심 질문은 둘이다.** 상대가 대화·판단의 주도권을 쥐는가. 원격 쪽이 **판단하는가 실행만 하는가**.

| 상황 | 원격이 하는 일 | 분류 | Port |
|---|---|---|---|
| ChatGPT가 `get_my_cases()`를 부르고 답변은 ChatGPT가 조립 | 우리 도구를 빌려 씀 | **MCP** | MCP Server |
| 외부 플랫폼이 "이 환불 건 처리해줘"하고 결과를 기다림 | 일을 통째로 위임 | **A2A** (우리가 수주) | A2A Server · Agent Card |
| 우리가 외부 Fraud Review Agent에 판단을 맡김 | **스스로 판단**하고 추가 정보를 요구 | **A2A** (우리가 위임) | `A2ATeamExecutor` |
| 런팟 GPU에 프롬프트 추론·임베딩을 지시 | **지시대로 실행만** | **A2A 아님** | `LLMPort` |
| 내부 워커에 배치 작업을 지시 | **지시대로 실행만** | **A2A 아님** | `MessageBusPort` |
| 런팟에 자체 판단하는 Team을 통째로 올림 | 스스로 판단 | **A2A 맞음** | `A2ATeamExecutor` |

**네 번째와 여섯 번째를 비교하면 명확하다.** 같은 런팟인데 하나는 A2A가 아니고 하나는 맞다. **누가 판단하느냐가 가른다.**

## A2A가 쓰이는 세 경로

| # | 경로 | 예 |
|---|---|---|
| 1 | **우리가 클라이언트** | Return & Refund Team이 사기 여부를 외부 Fraud Review Agent에 맡긴다 |
| 2 | **우리가 서버** | 외부 오케스트레이터가 우리에게 문의를 위임한다. 우리가 Agent Card를 발행 |
| 3 | **우리 Team을 분리 배포** | Team 수가 늘거나 모델·의존성이 달라지면 같은 계약을 유지한 채 `LOCAL`→`A2A` |

**3번이 이 설계의 값진 부분이다.** Team이 무거워지면 **계약을 안 바꾸고 실행 경로만 바꾼다.**

## Port로 교체된다

```python
class A2ATeamExecutor:
    async def execute(self, task: TeamTask) -> TeamResult: ...
```

`LocalTeamExecutor`와 **같은 인터페이스**다. Controller는 어느 쪽인지 모른다.

```
TeamExecutorPort
├─ LocalTeamExecutor   app/core/remote_team/executor.py
└─ A2ATeamExecutor     app/core/remote_team/a2a_executor.py
```

**이게 A2A 경계를 지금 세운 이유다.** 나중에 넣으면 Controller·Registry·계약·상태 매핑을 전부 다시 건드려야 한다. 실행 경로가 코드 전반에 퍼지기 때문이다.

`[실측]` **Port를 둔 값이 한 번 증명됐다.** [DoD-26](../../../../final_project_cs/docs/evidence/DoD-26_A2A_Catalog_왕복.md) — 처음엔 고정 dict를 돌려주는 더미 Transport였고, 실제 원격 앱에 HTTP로 말하는 `http_transport.py`로 갈아 끼울 때 **`A2ATeamExecutor`는 한 줄도 안 바꿨다.**

`GraphStorePort`와 대비된다 — 그건 저장소 교체 문제라 구현을 미룰 수 있다. → [../../../wiki/decisions/D-002-graph-store-gate.md](../../../wiki/decisions/D-002-graph-store-gate.md)

## 실행 흐름

`[실측]` `a2a_executor.py`의 메서드 구성.

```text
_submit          Task 제출
   ↓
_poll            상태 폴링
   ↓
_status          원격 상태 읽기
   ↓
_map             TeamResult 로 정규화
```

두 가지 안전장치가 있다.

| 메서드 | 무엇 |
|---|---|
| `_call_within_deadline` | `TeamTask.deadline_at` 안에서만 기다린다 |
| `_cancel_best_effort` | 마감을 넘기면 원격에 취소를 시도한다 |
| `_failed` | 실패를 `TeamResult`로 정규화 |

**best effort라고 이름에 적혀 있다.** 취소가 보장되지 않는다는 뜻이고, 그래서 원격 결과를 나중에 받아도 안전해야 한다.

`[실측]` **`_call_within_deadline`이 처음엔 반쪽짜리였다** ([DoD-27](../../../../final_project_cs/docs/evidence/DoD-27_A2A_실패_취소_인증.md) 2026-08-24 갱신). deadline은 **루프 반복 사이에서만** 확인되고 있었다 — `submit()`이나 `poll()` 호출 자체가 응답 없이 오래 걸리면(hung) 그 한 번의 호출은 안 끊겨서 선언된 deadline을 훨씬 넘길 수 있었다. `final_project_sample` 대조로 발견해, 각 원격 호출을 `asyncio.wait_for(call, timeout=deadline_at - now())`로 감싸도록 고쳤다 — 10초 hang하는 mock에 30ms deadline을 줘도 0.5초 안에 `remote_deadline_exceeded`로 끝나고 `_cancel_best_effort`가 실제로 호출되는지까지 재현 테스트로 확인했다.

**이걸로 `final_project_sample`과의 대조가 잡은 결함이 세 번째다** — DoD-03의 `agent_runs` 동시성, DoD-12의 outbox tenant dedupe에 이어 같은 방법이 또 통했다.

## 결과를 정규화한다

원격이 무엇을 주든 `TeamResult`로 바꾼다. **Controller는 A2A인지 로컬인지 모른 채 같은 상태 기계를 돈다.**

### 이중 상태 머신을 Adapter가 흡수한다

A2A Task는 자체 생명주기를 갖는다. **매핑은 Adapter가 하고 Controller는 Case 상태만 본다.**

`[실측]` v8 §9-C

| 원격 Task 상태 | 우리 Case 상태 | Adapter 처리 |
|---|---|---|
| 진행 중 | `running` | deadline까지 상태를 조회 |
| 추가 입력 필요 | `waiting_input` | 질문을 `need_more_context`로 정규화 |
| 완료 | `resolved` 또는 후속 판단 | Artifact를 `TeamResult`로 정규화 |
| 실패 | `escalated` (`failure_code=remote_task_failed`) | 재시도 한도 초과 시 근거와 함께 넘김 |
| 취소 | `escalated` (`failure_code=cancelled_by_caller`) | 취소 사유와 `task_id` 기록 |
| **알 수 없음** | **`escalated` + 결과 `unknown`** | **임의로 완료 처리하지 않는다** |

**마지막 줄이 핵심이다.** deadline 초과나 조회 실패를 완료로 추정하지 않는다. [`idempotency.md`](../actions/idempotency.md)의 `INV-CS-ACT-003`과 같은 원칙이다.

### ★ [2026-09-05] 취소는 새 상태가 아니라 실패의 한 종류로 기록된다

`[실측]` [DoD-27](../../../../final_project_cs/docs/evidence/DoD-27_A2A_실패_취소_인증.md). `outcome`에 `"cancelled"`라는 값을 **추가하지 않았다** — 계약 Literal을 늘리면 전이표·리듀서·저장까지 파급되기 때문이다. 대신 `outcome="escalated"` + `failure_code="cancelled_by_caller"` + 경고 문구("원격 Task가 취소됐다 — 실패와 구분해서 읽어야 한다")로 남긴다.

**이전엔 실패와 취소를 아예 구분하지 않았다.** executor가 `{"failed","error","cancelled"}`를 전부 `remote_task_failed`로 뭉갰다 — **누가 멈췄는지**(원격이 못 함 vs. 우리가 그만둠)가 사라졌었다. 지금은 `failure_code`로 구분된다.

`[실측]` **한 번 잘못 셀 뻔했다.** 최초 검토에서 "cancel" 검색이 38건 나왔는데, 그건 대부분 `resolved --cancelled_by_user--> cancelled`(고객이 Case를 취소하는 것)였다 — v7이 요구한 **원격 Task 취소**와는 다른 사건이었다. **코드에 낱말이 있는 것과 그 경로가 실제로 밟히는 것은 다르다.**

### 재시도 범위

```
deadline_s 기준
네트워크 단절·일시 오류에만 지수 백오프
재시도 횟수·상한은 Adapter 설정
```

**중복 Task를 막으려고 `case_id`와 idempotency key를 함께 쓴다.**

## ★ 원격 Artifact를 그대로 믿지 않는다

원격 Agent가 완료 시 `verification_report`와 `evidence_manifest` Artifact를 반환한다.

**그 근거 식별자를 Context/DB와 대조한 뒤에** Shared State에 저장한다.

**우리 Team의 제안을 대조하는 것과 같은 규칙이다.** 원격이라고 예외를 두지 않는다.

→ [../actions/evidence-check.md](../actions/evidence-check.md)

### ★ `Evidence.source_type = "remote_agent"` — 계약을 하나 늘렸다

`[실측]` [DoD-26](../../../../final_project_cs/docs/evidence/DoD-26_A2A_Catalog_왕복.md). 원격이 돌려준 근거를 `tool_result`로 뭉개면 **우리 시스템이 확인한 사실**과 **남의 시스템이 그렇다고 말한 것**이 구분되지 않는다. 신뢰도가 다르고 근거 대조에서도 다르게 다뤄야 한다.

**테스트가 이 구멍을 먼저 잡았다** — `remote_agent`가 Literal에 없어 validation이 거부했다. 계약을 늘리는 쪽으로 고쳤다. `outcome`에 `cancelled`를 안 넣은 것([위](#-2026-09-05-취소는-새-상태가-아니라-실패의-한-종류로-기록된다))과 반대 결정인데, 기준은 같다 — **구분이 사라지면 안전에 영향이 있는가.** 취소는 `failure_code`로 구분되지만, 원격 근거는 `source_type`이 아니면 구분할 곳이 없다.

## Agent Card

`app/presentation/a2a/agent_card.py`

우리가 어떤 capability를 제공하는지 알리는 문서다. 상대가 이걸 보고 위임할지 정한다.

## 더미 Remote Agent

`app/presentation/a2a/remote_agent.py`

**A-COP 본체가 아니라 왕복 검증용 상대역이다.** Core 도메인 격리 테스트의 예외 목록에 이유와 함께 올라 있다.

```
tests/integration/a2a/test_remote_round_trip.py
```

MVP 범위는 **Remote A2A PoC 1개**다.

## 지금 범위

| | 상태 |
|---|---|
| Port 경계 | **완료** — Local↔A2A 교체점 |
| Agent Card | 완료 |
| 왕복 검증 | 더미 1개 — Agent Card 발견 → `working` → `input-required` → `POST /input` 재개 → Artifact. **in-process**(`httpx.ASGITransport`)라 상태코드·헤더·직렬화는 실제로 타지만 네트워크 단절·부분 응답·TLS는 재현 안 됨 |
| **Controller 종단** (`waiting_external` → resume) | `[미확보]` **아직.** 관측된 건 Executor·Transport 층의 왕복이다. 위 매핑 표의 `waiting_external` 행은 설계이지 실측이 아니다 |
| capability로 여러 원격 중 고르기 | 없음. 원격이 하나뿐이다 |
| 실제 외부 Agent 연동 | `[미확보]` |

Catalog & Verification Team이 A2A Remote 후보다. → [../teams/remote-team-a2a.md](../teams/remote-team-a2a.md)

## 관계

- [mcp-tools.md](mcp-tools.md) — 개인 AI 경로
- [rest-api.md](rest-api.md) — 일반 요청
- [../teams/remote-team-a2a.md](../teams/remote-team-a2a.md) — 원격 Team 실행
- [../runtime/agentic-controller.md](../runtime/agentic-controller.md) — Port를 쓰는 쪽
- [../../../wiki/research/a2a-adoption.md](../../../wiki/research/a2a-adoption.md) — 채택 근거
