---
type: contract
title: Team 경계
description: Team이 하면 안 되는 것 셋. 이 설계의 핵심 규칙인데 아직 사람 리뷰에 의존한다
status: draft
tags: [architecture, contract]
owners: [human:미배정]
domain: neutral
---

# Team 경계

> `[실측 2026-09-01]` **`app/core/case_runtime/`·`access_action/` 은 `__init__.py` 만 남은 빈 패키지다.**
> 2026-08-13 에 중첩 구조로 갔다가 **평면 구조로 되돌아왔다.** 정본은 `app/core/*.py` 다.
> 구조가 또 바뀔 수 있으므로 **작업 전에 실제 경로를 확인한다.**

**Team이 무엇을 하는가보다 무엇을 하지 않는가가 중요하다.**

셋이다. 셋 다 어기면 시스템의 보증이 무너진다.

---

## 1. side effect를 실행하지 않는다

Team은 `ActionProposal`만 반환한다. 실행은 [../actions/index.md](../actions/index.md)가 한다.

### 어기면

| 무너지는 것 | 어떻게 |
|---|---|
| 승인 경계 | 고위험 Action이 사람 승인 없이 실행된다 |
| 중복 방지 | 같은 요청이 두 번 실행된다 |
| 감사 | 누가 무엇을 했는지 기록이 없다 |

**셋 중 하나만 무너져도 이 제품의 주장이 무의미해진다.** [중앙 허브 포지셔닝](../../../wiki/product/positioning.md)이 "통제·검증층"인데 통제가 우회 가능하면 팔 게 없다.

### 판정

`INV-CS-TEAM-003` — **`review`.** 자동 판정이 없다.

`[미확보]` 자동화 방법을 찾아야 한다. Team 모듈이 `app/core/` (평면) 아래를 import하는지 검사하는 테스트가 가능해 보인다.

---

## 2. read 도구를 직접 호출하지 않는다

Context Broker가 `required_context`에 따라 읽어서 `ContextPack`에 넣어준다. 부족하면 `need_more_context`로 요청한다.

### 왜

**읽기 예산을 Core가 통제하기 위해서다.**

Team이 직접 읽으면 컨텍스트가 무한정 커진다. `[실측]` 이게 실제로 문제를 일으켰다.

```
Broker 우회 → evidence 중복 → 중앙값 10,670 토큰 → 12GB VRAM OOM
```

상세는 [../context/index.md](../context/index.md).

### 허용 도구는 선언된다

`[실측]` Team별 `allowed_tools`가 코드에 명시돼 있다.

| Team | 허용 도구 |
|---|---|
| Procurement + Order & Payment | `read.order`, `read.account`, `read.policy`, `read.catalog` |
| Return & Refund | `read.order`, `read.return`, `read.policy` |
| Fulfillment & Logistics | `read.order`, `read.shipment`, `read.policy` |
| Catalog & Verification | `read.catalog`, `read.order_items`, `read.policy` |
| Response Review | `read.policy` |

**선언은 있는데 "직접 호출하지 않는다"는 강제가 없다.**

### 판정

`INV-CS-TEAM-004` — **`review`.**

`INV-CS-TEAM-002`(`manifest scope가 정확하다`)는 automated이지만, 그건 **선언이 맞는지**를 보지 **실제 호출 경로**를 보지 않는다.

---

## 3. 다른 Team을 직접 호출하지 않는다

Controller가 Task로 변환해 수행한다.

### 왜

**의존 그래프가 생기면 교체가 불가능해진다.**

Team A가 Team B를 호출하면 B를 바꿀 때 A도 봐야 한다. Registry 등록형의 의미가 사라진다.

VOC & Store Manager가 다른 Team에 위임할 때도 마찬가지다. **VOC는 "위임 제안"을 `TeamResult`로 반환하고, Controller가 그걸 Task로 만든다.**

### 판정

`INV-CS-TEAM-005` — **`review`.**

---

## 자동 판정이 없다는 문제

**셋 다 `review`다.** 설계의 핵심 규칙인데 사람이 리뷰에서 잡아야 한다.

| ID | 불변식 | 판정 |
|---|---|---|
| `INV-CS-TEAM-003` | side effect를 실행하지 않는다 | review |
| `INV-CS-TEAM-004` | read 도구를 직접 호출하지 않는다 | review |
| `INV-CS-TEAM-005` | 다른 Team을 직접 호출하지 않는다 | review |

자동 판정이 있는 것은 계약 형태뿐이다.

| ID | 불변식 | 판정 |
|---|---|---|
| `INV-CS-TEAM-001` | manifest가 프로토콜을 구현한다 | automated |
| `INV-CS-TEAM-002` | manifest scope가 정확하다 | automated |

**형태는 검사하는데 행위는 검사하지 않는다.**

### 자동화 제안 `[추정]`

import 기반 정적 검사로 셋 다 잡을 수 있어 보인다.

| 불변식 | 검사 방법 |
|---|---|
| 003 | Team 모듈이 `access_action/` 을 import하는가 |
| 004 | Team 모듈이 `tools/` 를 직접 import하는가 |
| 005 | Team 모듈이 다른 Team 모듈을 import하는가 |

`tests/architecture/test_basement_is_domain_free.py`가 이미 import 검사를 하므로 같은 방식을 쓸 수 있다.

**우선순위가 높다.** 이 셋이 자동화되면 이 저장소 불변식의 사람 판정이 7개에서 4개로 준다.

---

## Team이 하는 것

경계 밖은 자유다.

| 자유 | |
|---|---|
| 내부 Agent 수 | Team이 정한다 |
| LangGraph·Subgraph 사용 | Team이 정한다 |
| 프롬프트 구성 | Team이 정한다 |
| 재처리 로직 | Team이 정한다 |

**Core는 `TeamManifest`와 표준 Contract만 본다.** Team의 graph·prompt·retrieval을 import하지 않는다.

## ★ [2026-09-03] Team 이 지켜야 할 세 가지

`[실측]` `wiki/records/handoff/04_Team_모듈_계약.md` §0 에서 이관.

| # | 지킬 것 |
|---|---|
| 1 | **`TeamModule` Protocol 을 구현한다** — `manifest` 속성 + `async def execute(task) -> TeamResult` |
| 2 | **side effect 를 실행하지 않는다** — `ActionProposal` 만 반환 |
| 3 | **근거 없이 답하지 않는다** — `answer` 를 채우면 `evidence` 가 비면 안 된다 |

**양쪽에서 막는다.**

> Core 는 Team 내부를 `import` 하지 않고, **Team 도 `transition.py` 를 직접 호출하지 않는다.**

> **Team 은 입력을 받아 출력을 돌려주는 순수 경계다. 상태 변경은 Controller 몫이다.**

## ★ prompt 감사 추적이 배선되지 않았다

`[실측]` 2026-08-17 발견. **2026-09-03에도 그대로다.**

**설계는 이렇다.**

```
프롬프트를 파일(prompts/<team>/<key>.v<N>.md)로 두고
prompts 테이블에 sha256 과 함께 등록한다
llm_calls.prompt_id 가 FK 로 걸린다
```

> **어떤 프롬프트가 만든 답인지 추적 가능해야 한다.**

### ★ 그 사이 배선됐다 — 2026-09-03 확인

`[실측]` **원본은 "호출부 0건"이라 적고 있는데 지금은 다르다.**

| 호출부 | 어디 |
|---|---|
| `record_llm_call` | `infrastructure/llm/openai.py:88` · `local_ft.py:87` |
| `register_prompt_files` | `scripts/register_prompts.py:14` |
| `create_llm_call` | `infrastructure/db/repository.py:58` |

**감사 실패를 삼키지 않는다.**

```python
except Exception as exc:
    raise AuditWriteError(f"failed to record LLM call for {prompt_key}") from exc
```

> **기록에 실패하면 호출 자체가 실패한다.** 답은 냈는데 기록이 없는 상태를 안 만든다.

**낡은 문서를 그대로 옮겼으면 없는 결함을 적을 뻔했다.** → [../../../wiki/governance/migration-scope/coverage.md](../../../wiki/governance/migration-scope/coverage.md)

### 왜 이게 문제인가

`[실측]` 설계가 걸려던 제약 둘.

```
UNIQUE(prompt_key, version) · UNIQUE(prompt_key, sha256)
```

> **프롬프트를 고치면 버전을 올린다. 같은 버전의 내용을 덮어쓰면 평가 재현성이 깨진다.**

`[실측]` **제약은 지금 걸린다.** `tests/unit/test_prompt_key_registration.py` 가 `ALLOWED_PROMPT_KEYS` 와 실제 파일을 대조한다.

**"조용히 건너뛰는 것"을 막는 테스트다** — 등록 목록에 없는 키는 `register_prompt_files()` 가 말없이 지나친다.

`[미확보]` **옛 도메인 프롬프트 12개**(`prompts/billing/`·`prompts/technical/`)가 미배선 상태로 남아 있다. 커머스용으로 재작성되지 않았다.

**→ [../../../wiki/evaluation/protocol.md](../../../wiki/evaluation/protocol.md) 의 재현성 요구와 어긋난다.**

## 관계

- [team-contract.md](team-contract/index.md) — 무엇을 구현해야 하는가
- [team-registry.md](team-registry.md) — 어떻게 등록되는가
- [../actions/action-proposal.md](../actions/action-proposal.md) — Team의 출력
- [../context/context-broker.md](../context/context-broker.md) — Team의 입력
- [../quality/invariants.md](../quality/invariants.md) — 불변식 전체
- [../../../wiki/architecture/core-vs-team.md](../../../wiki/architecture/core-vs-team.md) — 경계 판정 기준
