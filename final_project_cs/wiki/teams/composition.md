---
type: contract
title: 구성 단위와 조립 선언
description: 컴포넌트·모듈·Port·인스턴스를 어떻게 가르고, 조립 선언에 무엇을 적고 무엇이 실패인가
status: draft
tags: [architecture, contract]
domain: neutral
domain_note: 조립 기제는 도메인 무관이다. 예시로 커머스·여행 Team 이름이 나온다
---

# 구성 단위와 조립 선언

`[실측]` 2026-09-10 에 [index.md](index.md) 에서 떼어냈다. **Team 목록과 조립 기제가 한 문서에 있어 300줄을 넘었고, 둘은 낡는 이유가 다르다** — 목록은 도메인이 바뀌면 낡고 조립 기제는 계약이 바뀌면 낡는다.

`[실측]` `wiki/records/handoff/` 계약 문서와 절 단위로 대조해 **빠져 있던 필드·제약·숫자**를 채웠다. 대조 결과는 [반영률 실측](../../../wiki/governance/migration-scope/coverage.md).

## 구성 단위 구분

`[실측]`

| 단위 | 정의 | 구성기 동작 |
|---|---|---|
| 컴포넌트 | 제거하면 시스템이 성립하지 않는 구성물 | 선택 불가, 항상 포함 |
| 모듈 | 꺼도 나머지 시스템이 동작하는 단위 | 선택 가능 |
| Port | 구현을 교체하는 지점 | 구현체 선택 |
| 인스턴스 | 같은 계약을 만족하며 여러 개 둘 수 있는 항목 | 개수 추가·제거 |

근거: `wiki/records/handoff/08_모듈_컴포넌트_목록.md:7-18`

## 필수 컴포넌트

`[실측]`

| 컴포넌트 | 위치 | 필수 의존 |
|---|---|---|
| Case lifecycle · `transition_case()` | `app/core/transition.py`, `app/core/case_lifecycle/{case,events}.py` | 상태 변경의 단일 진입점; API의 Case 생성·분류가 이벤트에 의존 |
| 계약 모델 | `app/core/contracts.py` | Controller·Team·평가가 `TeamTask`·`TeamResult`·`TeamManifest`·`TeamModule`·`ContextPack`·`Evidence` 사용 |
| Team Registry | `app/core/registry.py` | capability 해석의 유일한 경로 |
| Context Broker | `app/core/context.py` | 12,000 토큰 예산·절삭·`degraded` 신호 |
| DB repository / session | `app/infrastructure/db/` | Source of Truth |
| Outbox 원자성 | `app/infrastructure/messaging/outbox.py` | projection·event·발행을 한 transaction으로 처리 |
| Case service | `app/application/case_service.py` | run/resume, active run 중복 방지, `agent_runs` 기록 |
| Controller | `app/application/controller.py` | 필수 컴포넌트를 연결하는 실행 루프 |
| 설정·가드레일 | `app/core/settings.py`, `config/guardrails.yaml` | 수치의 단일 출처 |

근거: `wiki/records/handoff/08_모듈_컴포넌트_목록.md:22-35`

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

근거: `wiki/records/handoff/08_모듈_컴포넌트_목록.md:38-55`, `wiki/records/handoff/08_모듈_컴포넌트_목록.md:112-128`

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
| 라벨 어휘·프롬프트·provider 호출 | `app/domains/travel_ops/components/core_hooks/feedback.py`(작업 트리. git 에는 아직 `customer_ops/feedback.py`) | 모델 |

근거: `wiki/records/handoff/08_모듈_컴포넌트_목록.md:112-152`

## 모듈 게이트 강제점

`[실측]`

| 모듈 | 강제점 |
|---|---|
| `mcp` | 비활성화 시 `_mcp_principal()`이 거부 |
| `voc` | 판단층과 화면이 거부되거나 등록되지 않음 |
| `graph_store` | 관리자 화면도 어댑터를 직접 생성하지 않고 조립 경계를 통과 |

선언된 모듈에 실제 검사 지점이 있는지는 `tests/contract/test_module_toggles.py`가 검사한다.

`[실측]` [MODULE-TOGGLES 검증 로그](../records/evidence/MODULE-TOGGLES_실효화_검증.md)(2026-08-30)가 선언을 **실제로 바꿔 가며** 확인했다 — `python -m scripts.verify_module_toggles`. `graph_store: false`면 관리자 화면 Ports 표의 `GraphStorePort` 줄이 **`모듈 꺼짐 (graph_store)`**로 뜬다. 빈칸으로 두지 않는다 — **빈칸은 "껐다"와 "고장났다"를 구별해 주지 못한다.** `mcp: false`면 tool 호출이 `ProjectConfigError`다.

**같은 로그의 `voc: false` → 기동 거부는 그때는 "통과"였고 이틀 뒤 결함으로 재판정됐다.** → [../quality/dod-evidence-drift.md](../quality/dod-evidence-drift.md)

`[실측]` 그 작업 전(2026-08-30)엔 **여섯 모듈 중 셋만 실제로 코드를 갈랐다** — `mcp`·`voc`는 `require_module` 호출처가 0건, `graph_store`는 게이트가 있어도 관리자 화면이 `SqlGraphAdapter`를 직접 만들어 우회했다. 위 표는 그걸 고친 뒤의 상태다. 설계 판단의 경위는 [../../../wiki/governance/drift-case-voc.md](../../../wiki/governance/drift-case-voc.md).

근거: `wiki/records/handoff/08_모듈_컴포넌트_목록.md:57-68`

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

근거: `wiki/records/handoff/08_모듈_컴포넌트_목록.md:156-165`

## 가변 인스턴스 계약

`[실측]`

| 종류 | 원본 실측 인스턴스 | 추가 조건 |
|---|---|---|
| Agent Team | `OrderShippingTeam`, `ReturnExchangeTeam` | `TeamModule` Protocol 구현 + Registry 등록 |

Agent Team만 개수가 2개에서 3개·4개 등으로 변할 수 있다. Team은 `manifest`와 `execute()`를 만족해야 하며 Core는 `_capability()`의 Registry 조회로 Team을 찾는다.

근거: `wiki/records/handoff/08_모듈_컴포넌트_목록.md:169-177`

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

`[실측]` **이 파일이 생긴 이유가 있다.** 2026-08-12 [DoD-04](../records/evidence/DoD-04_checkpoint_projection_분리.md) 첫 측정에서 `agent_runs`가 비어 있었다 — `create_app()`이 Controller·Registry·Executor를 조립하지 않아 REST 요청이 Controller를 타지 않았다. 조립 지점을 한 곳에 모으려고 만든 게 `composition.py`이고, 그 조립기가 뒤에 인자 개수만 보고 배선하는 결함을 한 번 더 냈다. → [../quality/blind-spots.md](../quality/blind-spots.md)

근거: `wiki/records/handoff/08_모듈_컴포넌트_목록.md:181-210`

## 구성 검증 실패 조건

`[실측]`

| 실패 조건 | 판정 |
|---|---|
| `enabled: true`인데 구현이 없음 | 빌드 실패 |
| `active: true`인데 `implementation_ref`를 import할 수 없음 | 빌드 실패 |
| `team_id` 중복 | 빌드 실패 |
| 같은 capability를 두 Team이 주장 | 빌드 실패 |
| 비활성화한 모듈을 호출하는 경로가 남음 | 빌드 실패 |
| 미구현 port 선택 — `redis_streams`·`age`·`neo4j` | **조립 실패** (`tests/unit/test_project_composition.py`) |
| `team_executor: a2a`인데 `a2a_executor` 모듈이 꺼져 있음 | **선택 불가** — 순서가 강제된다 |

`[실측]` 아래 두 줄은 [DoD-20](../records/evidence/DoD-20_Port교체_Controller불변.md)이 확인한 것이다. `local → a2a` 교체는 `project.yaml` 선언으로 되고 Controller 코드 변경은 0이다 — 다만 **"불변"은 코드가 안 바뀐다는 뜻이지 성능·타임아웃 특성이 같다는 뜻이 아니고**, 교체 후 실제 원격 실행까지 돌린 건 아니다(선언이 바뀌고 조립이 통과하는 것까지). 그 다음 단계는 [../external/a2a-protocol.md](../external/a2a-protocol.md)의 Controller 종단 미확보 항목이다.

미구현 Team은 `active: false`로 둔다. Registry에는 이름이 남지만 라우팅 대상에서는 제외된다.

근거: `wiki/records/handoff/08_모듈_컴포넌트_목록.md:213-221`

## 만드는 순서 · 공통 뼈대

만드는 순서는 [build-order.md](build-order.md). 반복되는 네 가지를 조합형 유틸로 빼는 설계는 [common-utils.md](common-utils.md)에 있고 `[정정 2026-09-10]` 「아직 구현은 없다」(09-03)는 낡았다 — **`app/domains/travel_ops/instances/_shared/_base.py` 가 생겼다**(작업 트리, 커밋 전). common-utils 설계의 네 가지를 다 담았는지는 대조하지 않았다.

## 폴더 구조

`[2026-10-06]` 업무 도메인 코드는 `app/domains/<도메인>/` 에만 있고, 그 안을 위의 구성 단위대로 칸을 나눴다 — [D-CS-013](../decisions/D-CS-013-domain-folder-layout.md).

```
app/domains/travel_ops/
├─ modules/      모듈 — 꺼도 나머지가 도는 기능 (web_account · mcp · live_progress)
├─ instances/    인스턴스 — 에이전트 팀. 팀 하나 = 폴더 하나 (activity · dining · mobility · booking_handoff · locked + _shared)
├─ components/   컴포넌트 — 빼면 여행 서비스가 안 도는 부품 (itinerary · planning · places · intake · conversation · actions · booking · watch · customer · core_hooks · team_hooks)
├─ ports/        Port — 바꿔 끼우는 자리 (data_sources)
├─ entry/        고객 입구 — HTTP 경로
└─ scenarios/    시연 · 하루 대조 시험용 조립
```

★위 「필수 컴포넌트」 표는 **플랫폼 코어**(여행을 모르는 공통 층 — `app/core` · `app/application` · `app/infrastructure` · `app/presentation`)의 필수 부품이다. 여행 묶음 안의 `components/` 는 **여행 서비스의 필수 부품**이라 층이 다르다.

칸끼리 누가 누구를 부르는지는 `tests/architecture/test_travel_ops_cells.py` 가 센다. **2026-10-06 네 줄 모두 0** — 팀 → 다른 팀 속 0 · 필수 부품 → 팀 속 0 · 필수 부품 → 끌 수 있는 기능 0 · 바꿔 끼우는 자리 → … 0. 옮긴 날에는 20곳이 어기고 있었고(14 · 4 · 2), 같은 날 끼움 자리 일곱으로 **방향을 뒤집어** 없앴다.

## 끼움 자리 — 기능과 팀이 **조립 때 꽂는다** `[2026-10-06]`

부품이 기능·팀을 직접 import 하면 그 기능을 끄거나 팀을 빼는 순간 부품이 깨진다. 방향을 뒤집어 **부품은 자리만 알고, 꽂는 쪽이 조립 때 등록**한다(의존성 역전 · 포트와 어댑터, 조립 루트는 `app/composition.py`).

| 자리 | 부품이 묻는 것 | 꽂는 쪽 | 아무도 안 꽂으면 |
|---|---|---|---|
| `components/itinerary/trip_scope.py` | 감시 · 안내 대상 좁히기 | 웹 계정(게스트 제외) | `TRUE` — 전부 감시 |
| `components/settings_hook.py` | 운영자가 화면에서 바꾼 값 | 웹 남용 방어 설정 | `None` — 가드레일 기본값 |
| `components/progress_hook.py` | 진행 알림 포장(SSE) | 실시간 진행 | `[]` — 실시간 화면만 없다 |
| `components/team_hooks/legs.py` | 이동 시간 · 노선 · 사고 · 도보 상한 | 이동 팀 | 계산기 `None`(어림값) |
| `components/team_hooks/dining_ledger.py` | 근처 식당 · 시간대 영업 판정 · 이름 찾기 | 요식 팀 | 판정 `None`(모름) |
| `components/team_hooks/similarity.py` | 활동 유사도 · 설문 선호 · 거리 우선 | 활동 팀 | 점수 `None`(거리만) |
| `components/team_hooks/watch_planners.py` | 항목 종류별 감시 판정 | 세 팀 | `None` — 그 종류는 안 한다 |

꽂는 함수는 둘이다 — `wire_optional_features()`(끌 수 있는 기능)와 `wire_domain_teams()`(팀). 컨트롤러를 만들 때와 HTTP 입구를 만들 때 **양쪽에서** 부른다. 시험도 조립된 상태로 돌게 `tests/conftest.py` 가 매번 팀 배선을 부른다.

★**미등록일 때의 답은 새로 만든 기본값이 아니다.** 일곱 모두 그 기능·팀이 조립에 없을 때 부품이 이미 가지고 있던 길이다. 영업 여부를 모르면서 「열었다」로 답하지 않고, 다른 팀 계산으로 대신하지도 않는다.

★함수를 등록할 때 **객체를 쥐지 않고 부를 때 모듈에서 읽는다** — 이동 계산기는 켜짐/꺼짐이 실행 중에 바뀌고(`wiring.configure`), 시험이 팀 함수를 바꿔 끼우기도 한다. `core_hooks/` 는 방향이 반대다(여행이 **플랫폼 코어**에 꽂는 어휘 — 분류 · 대조 선언 · 대상 확인기 · 라우팅 재배분).

## 관계

- [index.md](index.md) — Team 목록과 경계
- [build-order.md](build-order.md) — 만드는 순서
- [common-utils.md](common-utils.md) — 공통 뼈대
- [../../../wiki/decisions/D-015-implementation-catalog.md](../../../wiki/decisions/D-015-implementation-catalog.md) — **구현 카탈로그를 손으로 유지하지 않는다**
