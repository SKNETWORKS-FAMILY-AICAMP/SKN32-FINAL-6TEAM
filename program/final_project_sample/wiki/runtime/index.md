---
type: guide
title: Case가 어떻게 흘러가나
description: basement의 실행 기반. 도메인을 모르는 채로 상태·동시성·멱등을 다룬다
status: draft
tags: [architecture, state]
---

# 런타임 — Case가 어떻게 흘러가나

**여기 있는 것은 전부 도메인을 모른다.** 그래서 cs가 나가도 그대로 돈다.

## 구성

`[실측]` `acop_basement/core/`

| 파일 | 무엇 |
|---|---|
| `transition.py` | 상태 전이. 유일한 쓰기 경로 |
| `contracts.py` | Core↔Team 계약 타입 |
| `registry.py` | capability → Team 해석 |
| `idempotency.py` | 중복 실행 방지 키 |
| `context.py` | ContextPack 조립·예산 |
| `verification.py` | 제안 대조. **도메인 선언을 주입받는다** |
| `redaction.py` | PII 가리기 |
| `audit_store.py` | 감사 기록 |
| `config_store.py` | 중앙 설정 |
| `settings.py`·`project_config.py` | 설정 로딩 |

하위 패키지도 있다.

```
case_runtime/  access_action/  graph_retrieval/  remote_team/  shared/
```

## `verification.py`가 도메인 무관인 방식

**정책을 코드에 박지 않고 주입받는다.**

```python
VerificationPolicy(
    references={...},   # 어느 필드가 어느 컬렉션을 가리키나
    quantities=(...),   # 어느 필드가 어느 한도에 걸리나
    opaque=...,         # 대조 수단이 아직 없는 것
    ignored=...,        # 대조 대상이 아닌 자유 필드
)
```

**이 네 칸이 도메인이고, 나머지가 엔진이다.** → [../quality/index.md](../quality/index.md)

## 문서

| 문서 | 답하는 질문 | 핵심 |
|---|---|---|
| [case-lifecycle.md](case-lifecycle.md) | 상태가 몇 개이고 어떻게 옮겨가나 | 12개. `transition_case()` 가 유일 진입점 |
| [shared-state.md](shared-state.md) | 동시에 두 곳이 쓰면 | version 조건부 UPDATE. 진 쪽은 `StateConflict` |
| [conflict-retry.md](conflict-retry.md) | 충돌하면 몇 번 다시 하나 | **경로에 따라 다르다.** 아홉 곳 중 세 곳만 재시도한다 |
| [idempotency.md](idempotency.md) | 같은 요청이 두 번 오면 | Team 이 준 키를 안 쓴다. 서버가 다시 계산한다 |
| [context-pack.md](context-pack.md) | 맥락을 어떻게 조립하나 | 예산 초과분은 정해진 순서로 버린다 |
| [agentic-controller.md](agentic-controller.md) | Controller 가 Case 를 어떻게 굴리나 | 시계가 둘이다 |
| [message-broker.md](message-broker.md) | 메시지를 어떻게 내보내나 | **지금은 아무 데도 안 보낸다** |

`[실측]` **다섯 문서는 sample 코드만 읽고 썼다.** cs wiki 를 열지 않았다 — 열면 경로만 바꾼 사본이 나온다.

### 아직 안 쓴 것

| 문서 | 답할 질문 |
|---|---|
| — | 없다. 다섯 문서로 이 영역은 닫혔다 |

## 여기서 드러난 것 둘

`[실측]` 문서를 쓰다 코드에서 나온 관찰이다.

**재시도가 전이 경로마다 다르다.** `_transition_with_retry()` 를 쓰는 곳은 `routed`·`routing_failed`·`valid_input` **셋뿐**이고, 나머지 여섯 곳은 `transition_case()` 를 직접 부른다.

> **"충돌은 항상 N회 재시도한다"는 규칙은 없다.**

**`transition_case()` 에 호출 주체 검사가 없다.** `actor_type` 은 제한된 Enum 이 아니라 임의 문자열이고 `actor_id` 는 선택값이다.

`[미확보]` **"단일 진입점"이라고 적혀 있지만 누가 부를 수 있는지는 함수가 강제하지 않는다.** 어디서 검사하는지 확인하지 못했다.

## 관계

- [../index.md](../index.md) — 지식 지도
- [`../../../wiki/architecture/concurrency.md](../../../wiki/architecture/concurrency.md) — 동시성 계약
- [`../../../wiki/architecture/core-design.md](../../../wiki/architecture/core-design.md) — Core 설계
