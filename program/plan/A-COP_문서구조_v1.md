# A-COP 문서 구조 v1

## 1. 전체 트리

### 1-1. 중앙 허브 — `program/wiki/`

코드 커밋과 무관하게 움직이는 지식. 제품·일정·평가·사업·결정.

```text
program/wiki/
├─ quickstart.md              # 진입점. 30초 안에 전체를 파악
├─ index.md                   # 영역 지도
├─ log.md                     # 문서 변경 이력
│
├─ product/
│  ├─ index.md
│  ├─ positioning.md          # 무엇을 파는가, 무엇을 팔지 않는가
│  ├─ problem.md              # 페인포인트 3층
│  ├─ personas.md             # 페르소나 3인
│  ├─ scope.md                # In/Out of Scope
│  └─ glossary.md             # Case, Team, Capability, Action...
│
├─ business/
│  ├─ index.md
│  ├─ unit-economics.md       # 건당 원가, 사람 vs A-COP
│  ├─ infrastructure-cost.md  # API·GPU·전기·트래픽
│  ├─ market.md               # TAM/SAM, 컨택센터 규모
│  └─ pricing.md              # 가격안
│
├─ architecture/
│  ├─ index.md
│  ├─ system-context.md       # 시스템 경계와 외부 행위자
│  ├─ repository-map.md       # 저장소 6개의 역할과 관계
│  ├─ core-vs-team.md         # 무엇이 Core에 남고 무엇이 Team으로 가는가
│  └─ pack-model.md           # Runtime + CS Pack + Commerce Ops Pack
│
├─ delivery/
│  ├─ index.md
│  ├─ timeline.md             # 선행 + 1W~9W
│  ├─ milestones/
│  │  ├─ index.md
│  │  ├─ midterm-2026-09-15.md
│  │  └─ final-2026-10-26.md
│  ├─ dod.md                  # 완료 기준 29항목
│  └─ roles.md                # 6명의 소유 경계
│
├─ evaluation/
│  ├─ index.md
│  ├─ metrics.md              # 지표와 산식
│  ├─ protocol.md             # A/B/Proposed, 60+20, 통계
│  ├─ golden-set.md           # 골든셋 구성과 분포
│  └─ judge.md                # LLM-as-Judge 루브릭
│
├─ research/
│  ├─ index.md
│  ├─ graphrag.md
│  ├─ a2a-adoption.md
│  └─ mt-benchmark.md
│
├─ decisions/
│  ├─ index.md
│  ├─ log.md
│  ├─ D-001-payment-ownership.md      # 결제는 쇼핑몰이 소유한다
│  ├─ D-002-graph-store-gate.md       # SqlGraphAdapter가 MVP
│  ├─ D-003-message-broker.md         # in-process queue, RabbitMQ 기각
│  ├─ D-004-self-hosting-rationale.md # 원가 아니라 규제 논거
│  └─ D-005-composer-ownership.md
│
└─ governance/
   ├─ index.md
   ├─ document-standard.md    # 이 표준 자체
   ├─ front-matter.md         # 필드 규격
   ├─ evidence-grades.md      # [실측]/[외부]/[추정]/[미확보]
   └─ review-policy.md
```

### 1-2. 코드 저장소 — `final_project_cs/wiki/`

코드와 같은 커밋에서 바뀌어야 하는 지식.

```text
final_project_cs/wiki/
├─ quickstart.md
├─ index.md
├─ log.md
│
├─ runtime/                   # Core 실행 기반
│  ├─ index.md
│  ├─ case-lifecycle.md       # Case 상태 기계
│  ├─ agentic-controller.md   # 라우팅, 재계획, WAIT/RESUME
│  ├─ shared-state.md         # Case의 단일 원천, CAS
│  ├─ conflict-retry.md       # 버전 충돌 처리
│  └─ message-broker.md       # 배달 보장, 중복 처리
│
├─ teams/                     # 업무 책임 단위
│  ├─ index.md
│  ├─ team-contract.md        # TeamTask / TeamResult 계약
│  ├─ team-registry.md        # capability → Team 해석
│  ├─ team-boundary.md        # Team이 하면 안 되는 것
│  ├─ remote-team-a2a.md      # A2A Remote Team 실행
│  ├─ voc-store-manager.md
│  ├─ response-review.md
│  ├─ procurement-order.md
│  ├─ fulfillment-logistics.md
│  ├─ return-refund.md
│  └─ catalog-verification.md
│
├─ context/                   # 읽기 경로
│  ├─ index.md
│  ├─ context-broker.md       # required_context → ContextPack
│  ├─ rag-retrieval.md
│  ├─ memory.md
│  └─ context-budget.md       # 예산과 절단 규칙
│
├─ actions/                   # 쓰기 경로
│  ├─ index.md
│  ├─ action-proposal.md      # Team은 제안만 한다
│  ├─ tool-gateway.md         # read/write 도구 경계
│  ├─ approval.md             # human-in-the-loop 승인
│  ├─ idempotency.md          # 동일 요청 10회 = 1 side effect
│  ├─ outbox.md               # 발행 경계
│  └─ evidence-check.md       # 근거 대조, 할루시네이션 방어
│
├─ external/                  # 바깥과 만나는 면
│  ├─ index.md
│  ├─ rest-api.md
│  ├─ mcp-tools.md            # Personal AI 경로
│  ├─ a2a-protocol.md         # 기업 Agent 경로
│  └─ auth-boundary.md        # Trust Boundary
│
├─ data/
│  ├─ index.md
│  ├─ schema.md               # 테이블 관계. DDL 전문은 링크
│  ├─ migrations.md
│  └─ tenancy.md              # tenant 격리
│
├─ quality/
│  ├─ index.md
│  ├─ invariants.md           # ★ 불변식 카탈로그. 테스트와 연결
│  ├─ test-map.md             # 무엇을 어디서 검사하는가
│  ├─ eval-harness.md
│  └─ blind-spots.md          # 테스트 사각지대 (자동 생성)
│
├─ operations/
│  ├─ index.md
│  ├─ local-setup.md
│  ├─ run.md
│  └─ troubleshooting.md
│
└─ decisions/
   ├─ index.md
   └─ log.md
```

### 1-3. 나머지 저장소

```text
final_project_sample/wiki/      # 계약 선검증만
├─ quickstart.md
├─ index.md
└─ contracts/
   ├─ index.md
   └─ validated/              # cs로 이식 확정된 계약만

datasets/wiki/
├─ index.md
├─ catalog.md                 # 데이터셋 목록과 용도
└─ generation.md              # REPORT 재생성 방법

acop_dojo/wiki/
├─ index.md
├─ guide.md
└─ generation.md
```

---

## 2. `quickstart.md`

가장 중요한 파일이다. 이것만 읽고 어디로 갈지 정할 수 있어야 한다.

### 2-1. 중앙 허브 quickstart

````markdown
---
type: guide
title: A-COP 시작하기
description: A-COP이 무엇이고 어느 문서부터 읽어야 하는지 알려주는 진입점
---

# A-COP 시작하기

A-COP은 고객 응대를 구성하는 B2B Agentic Operations Platform이다.
Case를 만들고, 업무별 Agent Team이 협업하고, 위험한 동작은 사람이 승인한다.

## 30초 요약

| | |
|---|---|
| 무엇 | 멀티에이전트 고객운영의 통제·검증층 |
| 핵심 주장 | 동작하게 만들기는 쉽다. 믿을 수 있게 만들기가 어렵다 |
| 릴리스 대상 | `final_project_cs` |
| 일정 | 중간발표 2026-09-15 · 최종 2026-10-26 |

## 지금 무엇을 하려는가

| 하려는 일 | 여기부터 |
|---|---|
| 제품이 뭔지 알고 싶다 | [product/positioning.md](product/positioning.md) |
| 코드를 고치려 한다 | [../../final_project_cs/wiki/quickstart.md](../final_project_cs/wiki/quickstart.md) |
| Team을 추가하려 한다 | [architecture/core-vs-team.md](architecture/core-vs-team.md) → cs의 `teams/team-contract.md` |
| 평가를 돌리려 한다 | [evaluation/protocol.md](evaluation/protocol.md) |
| 왜 이렇게 설계했는지 궁금하다 | [decisions/index.md](decisions/index.md) |
| 사업성 숫자가 필요하다 | [business/unit-economics.md](business/unit-economics.md) |
| 발표 자료를 만든다 | [delivery/milestones/index.md](delivery/milestones/index.md) |

## 저장소 지도

| 저장소 | 역할 | wiki |
|---|---|---|
| `program` | 계획·결정·평가 기준 | 여기 |
| `final_project_cs` | 릴리스 대상 | [wiki](../final_project_cs/wiki/index.md) |
| `final_project_sample` | 계약 선검증 | [wiki](../final_project_sample/wiki/index.md) |
| `acop_dojo` | 학습 도장 | [wiki](../acop_dojo/wiki/index.md) |
| `datasets` | 데이터 | [wiki](../datasets/wiki/index.md) |

자세한 관계는 [architecture/repository-map.md](architecture/repository-map.md).

## 사실이 충돌하면

1. 실행되는 테스트 결과
2. 해당 저장소 `CLAUDE.md`의 사실 표
3. `status: stable` 문서
4. 중앙 허브 문서
5. `status: draft` 문서

## 규칙

문서를 쓰기 전에 [governance/document-standard.md](governance/document-standard.md)를 읽는다.
````

### 2-2. 코드 저장소 quickstart

````markdown
---
type: guide
title: final_project_cs 시작하기
description: A-COP 릴리스 대상 저장소의 구조와 작업별 진입점
---

# final_project_cs 시작하기

A-COP의 릴리스 대상이다. Core(실행 기반)와 Team(업무 모듈)이 Registry로 분리돼 있다.

## 한 장으로 보는 구조

```text
외부 요청 (REST / MCP / A2A)
  ↓  external/auth-boundary.md
Agent Gateway
  ↓
Agentic Controller ──── Team Registry ──── Agent Team
  │   runtime/            teams/              teams/
  │                                             │
  ├── Context Broker ─── 읽기                    │ ActionProposal
  │     context/                                 ↓
  └── Shared State ←──────────────────── Action Layer
        runtime/                            actions/
                                               │ 승인
                                               ↓
                                            Outbox
```

## 작업별 진입점

| 하려는 일 | 여기부터 | 반드시 같이 읽을 것 |
|---|---|---|
| Team 추가 | [teams/team-contract.md](teams/team-contract.md) | [teams/team-boundary.md](teams/team-boundary.md) |
| Team 로직 수정 | 해당 `teams/<team>.md` | [actions/action-proposal.md](actions/action-proposal.md) |
| 읽기 자료 바꾸기 | [context/context-broker.md](context/context-broker.md) | [context/context-budget.md](context/context-budget.md) |
| 쓰기 동작 추가 | [actions/tool-gateway.md](actions/tool-gateway.md) | [actions/idempotency.md](actions/idempotency.md), [actions/approval.md](actions/approval.md) |
| Case 상태 건드리기 | [runtime/shared-state.md](runtime/shared-state.md) | [runtime/conflict-retry.md](runtime/conflict-retry.md) |
| 스키마 변경 | [data/schema.md](data/schema.md) | [data/migrations.md](data/migrations.md) |
| API 추가 | [external/rest-api.md](external/rest-api.md) | [external/auth-boundary.md](external/auth-boundary.md) |
| 평가 돌리기 | [quality/eval-harness.md](quality/eval-harness.md) | |

## 고치기 전에 반드시 확인

[quality/invariants.md](quality/invariants.md) — 깨면 안 되는 규칙 목록이다.
대부분 테스트가 강제하므로 어기면 CI가 실패한다.

특히 자주 걸리는 것 넷.

- Team은 side effect를 실행하지 않는다. `ActionProposal`만 반환한다
- Team은 read 도구를 직접 호출하지 않는다. Context Broker가 넣어준다
- Core는 Team 내부를 import하지 않는다
- Core 계층에 도메인 어휘를 넣지 않는다

## 자주 쓰는 명령

```bash
pytest tests/architecture     # 계층 경계 검사
pytest tests/contracts        # 계약 검사
python -m eval.run --arm Proposed
```
````

---

## 3. `index.md`

목차가 아니다. **읽는 사람이 어디로 갈지 판단할 재료**를 준다.

### 3-1. 중앙 허브 루트 index

````markdown
---
type: guide
title: A-COP 지식 허브
description: 중앙 허브의 6개 영역과 각 영역이 답하는 질문
---

# A-COP 지식 허브

처음이면 [quickstart.md](quickstart.md)부터 본다.

## 영역

### [product/](product/index.md) — 무엇을 만드는가
포지셔닝, 페인포인트, 페르소나, 범위, 용어.
"이게 왜 필요한가"에 답해야 할 때 여기부터.

### [business/](business/index.md) — 얼마짜리인가
건당 원가, 인프라 비용, 시장 규모, 가격안.
사람 1건 4,100~4,846원 · A-COP 병행 1,133원이 여기서 나온다.

### [architecture/](architecture/index.md) — 어떻게 나뉘는가
시스템 경계, 저장소 6개의 관계, Core와 Team의 분리 기준, Pack 모델.
구현 세부는 각 코드 저장소 wiki에 있고 여기는 경계만 다룬다.

### [delivery/](delivery/index.md) — 언제 무엇을 내는가
일정, 마일스톤, DoD 29항목, 6명의 소유 경계.

### [evaluation/](evaluation/index.md) — 무엇으로 증명하는가
지표와 산식, A/B/Proposed 프로토콜, 골든셋, Judge 루브릭.

### [research/](research/index.md) — 무엇을 알아봤는가
외부 조사와 비교 분석. 결정이 끝난 것은 여기 없고 `decisions/`에 있다.

### [decisions/](decisions/index.md) — 왜 그렇게 했는가
되돌리려면 근거가 필요한 선택들. 기각한 대안도 함께 적는다.

### [governance/](governance/index.md) — 어떻게 쓰는가
문서 표준, front matter 규격, 근거 등급, 리뷰 정책.

## 코드 저장소

| 저장소 | 무엇이 있나 |
|---|---|
| [final_project_cs](../final_project_cs/wiki/index.md) | Core·Team 구현, 계약, 불변식, 평가 하네스 |
| [final_project_sample](../final_project_sample/wiki/index.md) | cs로 이식 확정된 계약만 |
| [datasets](../datasets/wiki/index.md) | 데이터셋 의미와 재생성 방법 |
| [acop_dojo](../acop_dojo/wiki/index.md) | 학습 도장 사용법 |

## 미결정

지금 답이 없는 것들. 정해지면 `decisions/`로 옮긴다.

| 항목 | 무엇이 필요한가 |
|---|---|
| 가격 정책 | 오류 1건당 손실 실측 |
| 자체호스팅 채택 | 3B 모델 추론 처리량·정확도 실측 |
| 음성 채널 | 별도 원가 산정 |

## 최근 변경

[log.md](log.md) 참조.
````

### 3-2. 영역 index — `runtime/`

````markdown
---
type: guide
title: Runtime
description: Case가 만들어지고 흘러가고 끝나는 실행 기반. Core에 속하며 도메인을 모른다
---

# Runtime

Case의 생명주기와 그것을 움직이는 Core 구성요소.
**이 영역은 도메인을 모른다.** 환불이든 배송이든 여기서는 다 같은 Case다.

## 읽기 순서

처음이면 위에서 아래로.

1. [case-lifecycle.md](case-lifecycle.md) — Case가 어떤 상태를 지나는가
2. [shared-state.md](shared-state.md) — 그 상태를 어디에 어떻게 저장하는가
3. [agentic-controller.md](agentic-controller.md) — 누가 다음 단계를 정하는가
4. [conflict-retry.md](conflict-retry.md) — 동시에 고치려 하면 어떻게 되는가
5. [message-broker.md](message-broker.md) — 메시지를 어떻게 배달하는가

## 각 문서

| 문서 | 책임 | 건드리면 위험한 것 |
|---|---|---|
| [case-lifecycle.md](case-lifecycle.md) | Case 상태 기계와 전이 규칙 | 상태를 추가하면 Controller·평가·UI가 전부 영향 |
| [shared-state.md](shared-state.md) | Case의 단일 원천, 버전, CAS | 우회 경로를 만들면 이중 장부 |
| [agentic-controller.md](agentic-controller.md) | 라우팅, 재계획, WAIT/RESUME | Team을 직접 생성하면 Registry가 무의미 |
| [conflict-retry.md](conflict-retry.md) | 버전 충돌 판정과 재시도 | 낙관적 동시성 전제를 깨면 교착 |
| [message-broker.md](message-broker.md) | 배달 보장, 중복 처리 | in-process 전제를 깨면 재현 불가 |

## 이 영역의 불변식

전체 목록은 [../quality/invariants.md](../quality/invariants.md).

| ID | 불변식 | 판정 |
|---|---|---|
| `INV-CS-RT-001` | Shared State가 Case의 단일 원천이다 | automated |
| `INV-CS-RT-002` | 모든 변경은 version을 증가시킨다 | automated |
| `INV-CS-RT-003` | 동시 갱신은 CAS를 거친다 | automated |
| `INV-CS-RT-004` | 실패한 갱신은 부분 변경을 남기지 않는다 | automated |

## 인접 영역

- [../teams/index.md](../teams/index.md) — Controller가 Task를 넘기는 곳
- [../context/index.md](../context/index.md) — 읽기 자료를 만드는 곳
- [../actions/index.md](../actions/index.md) — 쓰기가 실제로 일어나는 곳

## 구현 위치

```text
app/core/
app/runtime/
tests/architecture/
```
````

### 3-3. 영역 index — `actions/`

````markdown
---
type: guide
title: Actions
description: 바깥 세계를 실제로 바꾸는 유일한 경로. 제안·승인·실행·발행이 여기서 갈린다
---

# Actions

**A-COP에서 side effect가 일어나는 유일한 곳이다.**
Team은 여기에 제안만 하고, 실행은 Core가 한다.

## 왜 분리했는가

Team이 직접 실행하면 세 가지가 무너진다.
승인 경계를 우회할 수 있고, 같은 요청이 두 번 실행될 수 있고, 감사 기록이 남지 않는다.

결정 근거는 [../../../program/wiki/decisions/index.md](../../../wiki/decisions/index.md).

## 흐름

```text
Team
 └→ ActionProposal          action-proposal.md
      ↓
    근거 대조                evidence-check.md   ← 여기서 걸리면 escalate
      ↓
    위험도 판정
      ├→ 저위험: 자동 실행
      └→ 고위험: 사람 승인   approval.md
             ↓
        Action 실행          tool-gateway.md
             ↓ (동일 키 = 1회)  idempotency.md
        Outbox 발행          outbox.md
```

## 각 문서

| 문서 | 답하는 질문 |
|---|---|
| [action-proposal.md](action-proposal.md) | Team이 무엇을 어떤 모양으로 반환하는가 |
| [evidence-check.md](evidence-check.md) | 근거 없는 주장을 어떻게 걸러내는가 |
| [approval.md](approval.md) | 무엇이 사람 승인 대상인가 |
| [tool-gateway.md](tool-gateway.md) | 어떤 도구를 누가 쓸 수 있는가 |
| [idempotency.md](idempotency.md) | 같은 요청이 여러 번 와도 한 번만 실행되게 |
| [outbox.md](outbox.md) | 외부 발행을 어떻게 보장하는가 |

## 이 영역의 불변식

| ID | 불변식 | 판정 |
|---|---|---|
| `INV-CS-ACT-001` | Team은 side effect를 실행하지 않는다 | automated |
| `INV-CS-ACT-002` | 동일 idempotency key는 1회만 실행된다 | automated |
| `INV-CS-ACT-003` | 고위험 Action은 승인 없이 실행되지 않는다 | automated |
| `INV-CS-ACT-004` | 근거 대조를 통과하지 못한 제안은 실행되지 않는다 | automated |

## 인접 영역

- [../teams/team-boundary.md](../teams/team-boundary.md) — Team이 하면 안 되는 것
- [../runtime/shared-state.md](../runtime/shared-state.md) — 실행 결과가 반영되는 곳

## 구현 위치

```text
app/core/actions/
app/infrastructure/messaging/
tests/contracts/
```
````

---

## 4. 문서 본문 골격

### 4-1. 공통 (모든 concept 문서)

```markdown
---
type: concept
title: Shared State
description: Customer Case의 공식 상태. 버전을 가지며 모든 갱신은 CAS를 거친다
tags: [runtime, state, concurrency]
status: stable
owners: [human:서유현]
---

# Shared State

## 책임
무엇을 담당하는가. 3줄 이내.

## 경계
무엇을 하지 않는가. 이게 책임보다 중요할 때가 많다.

## 불변식
| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|

## 관계
- [인접 문서](path.md) — 어떤 관계인지 한 줄

## 결정
왜 이렇게 설계했는가. 기각한 대안이 있으면 함께.

## 구현
`app/runtime/state/` — 코드를 다시 적지 않는다. 위치만 가리킨다.

## 실패 사례
무엇이 잘못될 수 있고 그때 어떻게 되는가.
```

### 4-2. `decision` 문서

```markdown
---
type: decision
title: 결제 소유 경계
description: 결제 실행은 검증 쇼핑몰이 소유하고 A-COP은 구성을 읽어 대조만 한다
status: stable
owners: [human:최연우]
---

# D-001 결제 소유 경계

## 맥락
어떤 상황에서 이 판단이 필요했는가.

## 결정
한 문장으로. 굵게.

## 선택지와 이유
| 안 | 채택 | 이유 |
|---|---|---|

## 결과
이 결정으로 무엇이 바뀌는가. 무엇을 못 하게 되는가.

## 근거
[실측] 코드 위치 · [외부] 출처 링크
```

---

## 5. 하네스 연결

### 5-1. `CLAUDE.md` — 라우터로만 쓴다

지식을 넣지 않는다. **어디를 볼지만** 알려준다.

```markdown
# A-COP

문서는 `program/wiki/`와 각 저장소 `wiki/`에 있다.
**작업 전에 해당 wiki의 `quickstart.md`를 먼저 읽는다.**

## 어디를 볼 것인가

| 하려는 일 | 먼저 읽을 것 |
|---|---|
| 제품·범위·용어 | `program/wiki/product/index.md` |
| 일정·DoD | `program/wiki/delivery/index.md` |
| 왜 그렇게 했는지 | `program/wiki/decisions/index.md` |
| 코드 수정 | `final_project_cs/wiki/quickstart.md` |
| Team 추가·수정 | `final_project_cs/wiki/teams/index.md` |
| 쓰기 동작 | `final_project_cs/wiki/actions/index.md` |
| 스키마 | `final_project_cs/wiki/data/index.md` |

## 코드를 고치기 전에

`final_project_cs/wiki/quality/invariants.md`를 확인한다.
여기 있는 규칙은 대부분 테스트가 강제한다.

## 기준 사실

이 표가 여러 문서에 반복되는 값의 단일 출처다.

| 사실 | 현재 값 | 정본 | 확인일 |
|---|---|---|---|
| 문서 기준선 | v8 | `program/wiki/index.md` | 2026-09-01 |
| CS Pack Team | VOC & Store Manager, Response Generation & Review | `program/wiki/architecture/pack-model.md` | 2026-09-01 |
| DoD 항목 수 | 29 | `program/wiki/delivery/dod.md` | 2026-09-01 |

## 문서를 쓸 때

`program/wiki/governance/document-standard.md`를 따른다.
```

### 5-2. front matter 규격

필수는 `type` 하나. `status: stable`로 올릴 때만 나머지가 필수가 된다.

| 필드 | draft | stable |
|---|---|---|
| `type` | 필수 | 필수 |
| `title` | 권장 | 필수 |
| `description` | 권장 | 필수 |
| `tags` | 선택 | 권장 |
| `status` | 선택 | 필수 |
| `owners` | 선택 | 필수 |

`type` 목록 — 8개로 시작한다.

```text
concept    개념·책임·구조
decision   선택과 이유
plan       일정·작업·DoD
contract   API·스키마·저장소 간 약속
guide      사용법·온보딩·진입점
report     특정 시점의 결과
research   조사와 비교
dataset    데이터 의미와 제약
```

`index.md`와 `log.md`는 `type: guide`를 쓴다.

### 5-3. 커스텀 룰 — 문서 작성 규칙

`governance/document-standard.md`에 넣을 것.

```markdown
## 하면 안 되는 것

1. 코드를 문장으로 옮겨 적지 않는다. 코드를 읽으면 아는 것은 문서에 없어도 된다
2. 한 파일에 두 개 이상의 개념을 넣지 않는다
3. 자동 생성 문서를 손으로 고치지 않는다
4. 같은 사실을 두 문서에 적지 않는다. 한쪽이 소유하고 다른 쪽은 링크한다
5. `CLAUDE.md`에 지식을 넣지 않는다. 라우터와 기준 사실 표만

## 반드시 하는 것

1. 주장에 근거 등급을 붙인다 — `[실측]` `[외부]` `[추정]` `[미확보]`
2. 불변식은 ID와 테스트 경로를 함께 적는다
3. 인접 문서로 링크를 건다. 링크 없는 문서는 찾아지지 않는다
4. 결정에는 기각한 대안을 함께 적는다
5. 모르는 것은 `[미확보]`로 적는다. 빈칸으로 두지 않는다
```

### 5-4. 불변식과 테스트 연결

문서 쪽 — `quality/invariants.md`

```markdown
| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-ARCH-001` | Core 계층은 도메인 어휘에 의존하지 않는다 | automated | `tests/architecture/test_basement_is_domain_free.py` |
| `INV-CS-ACT-001` | Team은 side effect를 실행하지 않는다 | automated | `tests/architecture/test_team_has_no_side_effect.py` |
```

코드 쪽 — 역방향 표식

```python
# invariant: INV-CS-ARCH-001
def test_basement_layers_do_not_know_the_business_domain():
    ...
```

CI가 검사하는 것 넷.

1. 문서의 `automated` 테스트 경로가 실재하는가
2. 그 테스트에 같은 `invariant:` 표식이 있는가
3. 코드의 ID가 문서 카탈로그에 있는가
4. ID가 중복되지 않는가

`INV-<REPO>-<영역>-<번호>`. REPO는 `CS`, `SAMPLE`, `HUB`, `DOJO`, `DATA`.

### 5-5. CI 검사

```yaml
# .github/workflows/docs.yml
- front matter에 type이 있는가
- status: stable인데 title/description/owners가 없는가
- 상대경로 링크가 깨졌는가
- 불변식 양방향 표식이 맞는가
- index.md가 없는 폴더가 있는가
```

지금 손으로 하고 나중에 자동화할 것 — 문서 신선도, `log.md` 갱신, 중복 사실 탐지.

---

## 6. 안 넣은 것과 이유

| 항목 | 이유 |
|---|---|
| `stale_after` (문서 만료 표시) | 이관 직후 수백 개가 한꺼번에 만료로 뜬다. 나중에 켠다 |
| type 13개 | 8개로 시작한다. 늘리기는 쉽고 줄이기는 어렵다 |
| OpenWiki CLI 자동 생성 | 이 저장소 가치의 상당 부분이 "미결정"과 "왜"인데 코드에서 안 나온다 |
| 숫자 접두사 폴더 | 읽기 순서는 `index.md`가 담당한다 |
