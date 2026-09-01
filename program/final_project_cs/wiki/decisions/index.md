---
type: guide
title: Decisions (cs)
description: 이 저장소에만 영향을 주는 결정. 여러 저장소에 걸친 것은 중앙 허브에 있다
status: draft
---

# Decisions (cs)

**이 저장소 안에서 끝나는 결정**만 여기 둔다.

여러 저장소가 당사자인 결정은 [중앙 허브](../../../wiki/decisions/index.md)에 있다.

## 어디에 두는가

| 질문 | 배치 |
|---|---|
| 이 저장소 코드만 바뀌면 되는가 | 여기 |
| 다른 저장소도 고쳐야 하는가 | 중앙 허브 |
| 제품·사업 판단인가 | 중앙 허브 |

## 목록

`[미확보]` 아직 없다. 기존 `docs/plans/`에서 이관 대상을 골라야 한다.

## 중앙 허브의 결정 중 이 저장소에 영향을 주는 것

| ID | 결정 | 여기서 무엇이 바뀌나 |
|---|---|---|
| [D-001](../../../wiki/decisions/D-001-payment-ownership.md) | 결제는 쇼핑몰이 소유 | 환불 계산식을 대조 구조로 변경, `read.payment` 추가 |
| [D-002](../../../wiki/decisions/D-002-graph-store-gate.md) | Graph Store는 게이트 통과 시에만 | `GraphStorePort` 유지, `SqlGraphAdapter`가 MVP |
| [D-003](../../../wiki/decisions/D-003-message-broker.md) | in-process queue | `MessageBusPort` 유지, 중복 전달·retry 테스트 필요 |
| [D-004](../../../wiki/decisions/D-004-self-hosting-rationale.md) | 자체호스팅은 규제 논거 | 3B 추론 실측 필요 |

## 관계

- [../../../program/wiki/decisions/index.md](../../../wiki/decisions/index.md) — 중앙 허브 결정
- [../log.md](../log.md) — 변경 이력
