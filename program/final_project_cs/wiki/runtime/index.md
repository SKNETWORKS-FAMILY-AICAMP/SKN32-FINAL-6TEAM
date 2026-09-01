---
type: guide
title: Runtime
description: Case가 만들어지고 흘러가고 끝나는 실행 기반. 이 영역은 도메인을 모른다
status: draft
---

# Runtime

`app/core/case_runtime/`

Case의 생명주기와 그것을 움직이는 Core 구성요소.

**이 영역은 도메인을 모른다.** 환불이든 배송이든 여기서는 다 같은 Case다. 도메인 어휘가 들어오면 `INV-CS-ARCH-001`이 실패한다.

## 읽기 순서

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

## 코드 구조

```text
app/core/case_runtime/
├─ case/           Case 엔티티와 상태
├─ concurrency/    CAS, 버전 충돌
├─ context/        ContextPack 조립
├─ contracts/      계약 정의
├─ messaging/      메시지 배달
└─ orchestration/  Controller
```

관련 루트 파일.

| 파일 | 무엇 |
|---|---|
| `app/core/transition.py` | 상태 전이 규칙 (232줄) |
| `app/core/contracts.py` | 계약 정의 (346줄) |
| `app/core/context.py` | 컨텍스트 (282줄) |
| `app/core/registry.py` | Team Registry (93줄) |

## 이 영역의 불변식

| ID | 불변식 | 판정 | 상태 |
|---|---|---|---|
| `INV-CS-RT-001` | Shared State가 Case의 단일 원천이다 | review | **자동화 필요** |
| `INV-CS-RT-002` | 모든 상태 변경은 version을 증가시킨다 | review | **자동화 필요** |
| `INV-CS-RT-003` | 동시 갱신은 CAS를 거친다 | review | **자동화 필요** |
| `INV-CS-RT-004` | 실패한 갱신은 부분 변경을 남기지 않는다 | review | **자동화 필요** |

`[미확보]` **넷 다 테스트로 강제되지 않는다.** 이 저장소 불변식 카탈로그의 가장 큰 구멍이다. Case 상태가 제품의 중심인데 자동 판정이 없다.

→ [../quality/invariants.md](../quality/invariants.md)

## 인접 영역

- [../teams/index.md](../teams/index.md) — Controller가 Task를 넘기는 곳
- [../context/index.md](../context/index.md) — 읽기 자료를 만드는 곳
- [../actions/index.md](../actions/index.md) — 쓰기가 실제로 일어나는 곳
- [../data/index.md](../data/index.md) — 상태가 저장되는 곳

## 관련 결정

- [D-003 Message Broker는 in-process queue](../../../wiki/decisions/D-003-message-broker.md)
