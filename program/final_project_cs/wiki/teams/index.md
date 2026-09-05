---
type: guide
title: Teams
description: 업무 책임 단위. Registry 등록형이라 추가해도 Core가 안 바뀐다
status: draft
---

# Teams

`app/modules/customer_ops/`

**Team을 늘리는 일이 리팩토링이 되면 설계가 잘못된 것이다.** Registry 등록만으로 끝나야 한다.

## 읽기 순서

1. [team-contract.md](team-contract/index.md) — 무엇을 구현해야 하는가
2. [team-boundary.md](team-boundary.md) — **무엇을 하면 안 되는가**
3. [team-registry.md](team-registry.md) — 어떻게 등록되는가

## 계약·구조

| 문서 | 답하는 질문 | 코드 |
|---|---|---|
| [team-contract.md](team-contract/index.md) | `TeamTask` / `TeamResult` 모양 | `app/core/contracts.py` |
| [team-boundary.md](team-boundary.md) | Team이 하면 안 되는 것 셋 | — |
| [build-order.md](build-order.md) | 어느 순서로 만드나 | — |
| [common-utils.md](common-utils.md) | 공통 뼈대 (미구현) | — |
| [team-registry.md](team-registry.md) | capability → Team 해석 | `app/core/registry.py` |
| [remote-team-a2a.md](remote-team-a2a.md) | A2A Remote Team 실행 | `app/core/remote_team/` |
| [response-review-design.md](response-review-design.md) | **GEN→REV 내부 설계와 검증 4항목** | `response_review_policy.py` |

## 구현된 Team

`[실측]` `app/modules/customer_ops/`

| Team | 파일 | Pack | 상태 |
|---|---|---|---|
| [voc-store-manager.md](voc-store-manager.md) | `voc_store_manager.py` | CS | **10주 착수 확정** |
| [response-review.md](response-review.md) | `response_review.py` | CS | **10주 착수 확정** |
| [procurement-order.md](procurement-order.md) | `procurement_order_payment.py` | Commerce | 일정 따라 조정 |
| [fulfillment-logistics.md](fulfillment-logistics.md) | `fulfillment_logistics.py` | Commerce | 동 |
| [return-refund.md](return-refund.md) | `return_refund.py` | Commerce | 동 |
| [catalog-verification.md](catalog-verification.md) | `catalog_verification.py` | Commerce (A2A Remote) | 동 |
| — | `feedback.py` | CS | 인라인 분류 |

정책 파일이 따로 있다.

| 파일 | 무엇 |
|---|---|
| `response_review_policy.py` | 검토 정책 |
| `verification_policy.py` | 검증 정책 |

## Team이 하지 않는 것 셋

**이게 경계의 실체다.**

| 규칙 | 왜 |
|---|---|
| side effect를 실행하지 않는다 | 승인 경계 우회, 이중 실행, 감사 누락을 막는다 |
| read 도구를 직접 호출하지 않는다 | Context Broker가 읽기 예산을 통제한다 |
| 다른 Team을 직접 호출하지 않는다 | 의존 그래프가 생기면 교체가 불가능해진다 |

상세는 [team-boundary.md](team-boundary.md).

## Team의 read 도구

`[실측]` Team별 `allowed_tools`

| Team | 허용 도구 |
|---|---|
| Procurement + Order & Payment | `read.order`, `read.account`, `read.policy`, `read.catalog` |
| Return & Refund | `read.order`, `read.return`, `read.policy` |
| Fulfillment & Logistics | `read.order`, `read.shipment`, `read.policy` |
| Catalog & Verification | `read.catalog`, `read.order_items`, `read.policy` |
| Response Review | `read.policy` |

**결제 조회 도구는 없다.** Team 이름에 "Payment"가 있지만 실제 권한은 없다. → [D-001](../../../wiki/decisions/D-001-payment-ownership.md)

## 이 영역의 불변식

| ID | 불변식 | 판정 |
|---|---|---|
| `INV-CS-TEAM-001` | Team manifest는 프로토콜을 구현한다 | automated |
| `INV-CS-TEAM-002` | manifest의 scope는 정확히 선언된다 | automated |
| `INV-CS-TEAM-003` | Team은 side effect를 실행하지 않는다 | **review** |
| `INV-CS-TEAM-004` | Team은 read 도구를 직접 호출하지 않는다 | **review** |
| `INV-CS-TEAM-005` | Team은 다른 Team을 직접 호출하지 않는다 | **review** |

`[미확보]` **003~005가 자동 판정이 아니다.** 설계의 핵심 규칙인데 사람이 리뷰에서 잡아야 한다.

## sample의 Team

`final_project_sample`에 Billing/Technical 2종이 있다. **10주 착수 목록에 없다.**

Team-플러그인 아키텍처가 실제로 동작한다는 증거(Core 격리 위반 0)로만 남긴다.

## 인접 영역

- [../runtime/agentic-controller.md](../runtime/agentic-controller.md) — Team을 호출하는 쪽
- [../context/index.md](../context/index.md) — Team의 입력을 만드는 곳
- [../actions/action-proposal.md](../actions/action-proposal.md) — Team의 출력이 가는 곳
- [../../../program/wiki/architecture/core-vs-team.md](../../../wiki/architecture/core-vs-team.md) — Team 자격 판정
---

# 계약 원문에서 보강 (2026-09-03)

`[실측]` `docs/handoff/` 계약 문서와 절 단위로 대조해 **빠져 있던 필드·제약·숫자**를 채웠다. 대조 결과는 [반영률 실측](../../../wiki/governance/migration-scope/coverage.md).

## 구성 단위 구분

`[실측]`

| 단위 | 정의 | 구성기 동작 |
|---|---|---|
| 컴포넌트 | 제거하면 시스템이 성립하지 않는 구성물 | 선택 불가, 항상 포함 |
| 모듈 | 꺼도 나머지 시스템이 동작하는 단위 | 선택 가능 |
| Port | 구현을 교체하는 지점 | 구현체 선택 |
| 인스턴스 | 같은 계약을 만족하며 여러 개 둘 수 있는 항목 | 개수 추가·제거 |

근거: `docs/handoff/08_모듈_컴포넌트_목록.md:7-18`

## 필수 컴포넌트

`[실측]`

| 컴포넌트 | 위치 | 필수 의존 |
|---|---|---|
| Case lifecycle · `transition_case()` | `app/core/transition.py`, `app/domain/{case,events}.py` | 상태 변경의 단일 진입점; API의 Case 생성·분류가 이벤트에 의존 |
| 계약 모델 | `app/core/contracts.py` | Controller·Team·평가가 `TeamTask`·`TeamResult`·`TeamManifest`·`TeamModule`·`ContextPack`·`Evidence` 사용 |
| Team Registry | `app/core/registry.py` | capability 해석의 유일한 경로 |
| Context Broker | `app/core/context.py` | 12,000 토큰 예산·절삭·`degraded` 신호 |
| DB repository / session | `app/infrastructure/db/` | Source of Truth |
| Outbox 원자성 | `app/infrastructure/messaging/outbox.py` | projection·event·발행을 한 transaction으로 처리 |
| Case service | `app/application/case_service.py` | run/resume, active run 중복 방지, `agent_runs` 기록 |
| Controller | `app/application/controller.py` | 필수 컴포넌트를 연결하는 실행 루프 |
| 설정·가드레일 | `app/core/settings.py`, `config/guardrails.yaml` | 수치의 단일 출처 |

근거: `docs/handoff/08_모듈_컴포넌트_목록.md:22-35`

## 토글 가능한 모듈

`[실측]`

| 설정 이름 | 모듈 | 위치 | 끄면 제거되는 기능·표면 |
|---|---|---|---|
| `graph_store` | GraphStore | `app/core/graph_retrieval/port.py`, `app/infrastructure/graphstore/sql_adapter.py` | `neighbors`·`path`·`subgraph` 질의와 관리자 화면 Graph 섹션 |
| `a2a_executor` | A2A Executor | `app/core/remote_team/a2a_executor.py`, `app/presentation/a2a/` | 원격 Agent 위임·Agent Card·`/a2a/*` |
| `mcp` | MCP | `app/presentation/api/mcp.py` | 개인 AI read-only tool 3종과 MCP scope |
| `vector_rag` | Vector RAG | `app/infrastructure/rag/retriever.py` | 정책 검색·knowledge 적재; `ContextPack.degraded`로 전환 |
| `ops_ui` | 운영 UI | `app/presentation/ui/` | Case·Trace·Approval·VOC 화면과 `/ui/*` |
| `voc` | VOC 판단층·화면 | VOC Team, VOC 화면 | VOC Team 판단층과 VOC 화면 |

모듈을 끄면 그것을 호출하는 경로도 함께 제거한다. 호출 경로가 남으면 조용히 넘어가지 않고 명시적으로 실패한다.

근거: `docs/handoff/08_모듈_컴포넌트_목록.md:38-55`, `docs/handoff/08_모듈_컴포넌트_목록.md:112-128`

## `voc` 경계

`[실측]` `voc: false`가 끄는 것은 판단층과 화면뿐이다.

| 기능 | 소유 | `voc` 게이트 |
|---|---|---|
| 인라인 분류 `build_classifier` | 코어 1 | 없음 |
| 일일 집계 배치 `app/application/feedback_job.py` | 코어 1 | 없음 |
| VOC Team 판단층 | 모델 | 있음 |
| VOC 화면 | — | 있음 |

인라인 분류는 다음 두 부분으로 분리한다.

| 책임 | 위치 | 소유 |
|---|---|---|
| 호출 시점·실패 처리·상태 전이 | `app/application/classification.py` | 코어 1 |
| 라벨 어휘·프롬프트·provider 호출 | `app/modules/customer_ops/feedback.py` | 모델 |

근거: `docs/handoff/08_모듈_컴포넌트_목록.md:112-152`

## 모듈 게이트 강제점

`[실측]`

| 모듈 | 강제점 |
|---|---|
| `mcp` | 비활성화 시 `_mcp_principal()`이 거부 |
| `voc` | 판단층과 화면이 거부되거나 등록되지 않음 |
| `graph_store` | 관리자 화면도 어댑터를 직접 생성하지 않고 조립 경계를 통과 |

선언된 모듈에 실제 검사 지점이 있는지는 `tests/contract/test_module_toggles.py`가 검사한다.

근거: `docs/handoff/08_모듈_컴포넌트_목록.md:57-68`

## 교체 가능한 Port

`[실측]`

| Port | 정의 | 현재 구현 | 대안 |
|---|---|---|---|
| `TeamExecutorPort` | `app/core/remote_team/executor.py` | `LocalTeamExecutor` | `A2ATeamExecutor` |
| `MessageBrokerPort` | `app/core/contracts.py` | `OutboxBrokerAdapter` | `RedisStreamsAdapter` — Phase 2, 미구현 |
| `GraphStorePort` | `app/core/graph_retrieval/port.py` | `SqlGraphAdapter` — JOIN·재귀 CTE | AGE·Neo4j — Phase 2 |
| 정책 검색 함수 | `build_controller(policy_search_fn=...)` | `search_policy` — pgvector | 주입으로 교체 |
| LLM | `app/infrastructure/llm/openai.py` | `OpenAITeamLLM` | provider 교체 |
| 분류기 | `build_classifier()` | `feedback.classify` | 주입으로 교체 |

근거: `docs/handoff/08_모듈_컴포넌트_목록.md:156-165`

## 가변 인스턴스 계약

`[실측]`

| 종류 | 원본 실측 인스턴스 | 추가 조건 |
|---|---|---|
| Agent Team | `OrderShippingTeam`, `ReturnExchangeTeam` | `TeamModule` Protocol 구현 + Registry 등록 |

Agent Team만 개수가 2개에서 3개·4개 등으로 변할 수 있다. Team은 `manifest`와 `execute()`를 만족해야 하며 Core는 `_capability()`의 Registry 조회로 Team을 찾는다.

근거: `docs/handoff/08_모듈_컴포넌트_목록.md:169-177`

## 구성 선언 필드

`[실측]`

```yaml
modules:
  vector_rag:    { enabled: true }
  graph_store:   { enabled: true }
  a2a_executor:  { enabled: false }
  mcp:           { enabled: true }
  voc:           { enabled: true }
  ops_ui:        { enabled: true }
ports:
  team_executor: local
  message_broker: outbox
  graph_store: sql
teams:
  - { team_id: order_shipping,  active: true,  implementation_ref: "app.modules.customer_ops:OrderShippingTeam" }
  - { team_id: return_exchange, active: true,  implementation_ref: "app.modules.customer_ops:ReturnExchangeTeam" }
```

| Port 설정 | 허용 선택지 |
|---|---|
| `team_executor` | `local \| a2a` |
| `message_broker` | `outbox \| redis_streams` — `redis_streams`는 Phase 2 |
| `graph_store` | `sql \| age \| neo4j` — `neo4j`는 Phase 2 |

`app/composition.py`는 `load_project_config()`와 `importlib`로 `teams[].implementation_ref`를 동적으로 읽는다.

`[실측]` **이 파일이 생긴 이유가 있다.** 2026-08-12 [DoD-04](../../../../final_project_cs/docs/evidence/DoD-04_checkpoint_projection_분리.md) 첫 측정에서 `agent_runs`가 비어 있었다 — `create_app()`이 Controller·Registry·Executor를 조립하지 않아 REST 요청이 Controller를 타지 않았다. 조립 지점을 한 곳에 모으려고 만든 게 `composition.py`이고, 그 조립기가 뒤에 인자 개수만 보고 배선하는 결함을 한 번 더 냈다. → [../quality/blind-spots.md](../quality/blind-spots.md)

근거: `docs/handoff/08_모듈_컴포넌트_목록.md:181-210`

## 구성 검증 실패 조건

`[실측]`

| 실패 조건 | 판정 |
|---|---|
| `enabled: true`인데 구현이 없음 | 빌드 실패 |
| `active: true`인데 `implementation_ref`를 import할 수 없음 | 빌드 실패 |
| `team_id` 중복 | 빌드 실패 |
| 같은 capability를 두 Team이 주장 | 빌드 실패 |
| 비활성화한 모듈을 호출하는 경로가 남음 | 빌드 실패 |
| 미구현 port 선택 — `redis_streams`·`age`·`neo4j` | **조립 실패** (`tests/e2e/test_project_composition.py`) |
| `team_executor: a2a`인데 `a2a_executor` 모듈이 꺼져 있음 | **선택 불가** — 순서가 강제된다 |

`[실측]` 아래 두 줄은 [DoD-20](../../../../final_project_cs/docs/evidence/DoD-20_Port교체_Controller불변.md)이 확인한 것이다. `local → a2a` 교체는 `project.yaml` 선언으로 되고 Controller 코드 변경은 0이다 — 다만 **"불변"은 코드가 안 바뀐다는 뜻이지 성능·타임아웃 특성이 같다는 뜻이 아니고**, 교체 후 실제 원격 실행까지 돌린 건 아니다(선언이 바뀌고 조립이 통과하는 것까지). 그 다음 단계는 [../external/a2a-protocol.md](../external/a2a-protocol.md)의 Controller 종단 미확보 항목이다.

미구현 Team은 `active: false`로 둔다. Registry에는 이름이 남지만 라우팅 대상에서는 제외된다.

근거: `docs/handoff/08_모듈_컴포넌트_목록.md:213-221`

## 만드는 순서

**여섯 중 무엇을 먼저 하나는 [build-order.md](build-order.md) 에 있다.**

## 공통 뼈대

`[실측]` **반복되는 네 가지를 조합형 유틸로 빼는 설계가 있다.** 아직 구현은 없다.

> **`app/modules/customer_ops/team_utils.py` — 2026-09-03 확인 결과 없음.**

전문은 [common-utils.md](common-utils.md).
