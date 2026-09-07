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

| ID | 결정 | 상태 | 영향 |
|---|---|---|---|
| [D-CS-001](D-CS-001-composer-ui-removal.md) | `/ui/composer` 폐기 | draft | 인증 경계 |
| [D-CS-002](D-CS-002-finetuned-model-not-adopted.md) | **파인튜닝 모델 채택 안 함** | draft | 평가·자체호스팅 |
| [D-CS-003](D-CS-003-composer-scope.md) | **Composer 범위 — 세 층** | draft | Composer·UI |
| [D-CS-004](D-CS-004-composer-boundary.md) | 모듈 7종·Port 3종·Core 9종 경계 | draft | Composer |

`[미확보]` `docs/plans/`·`docs/reports/`에서 이관 대상을 더 골라야 한다.

**후보** — 코드만 보면 되돌릴 위험이 있는 것들.

| 후보 | 왜 결정으로 남겨야 하나 |
|---|---|
| 프롬프트 allowlist fail-closed | "왜 없으면 죽게 했지" 하고 완화하기 쉽다 |
| `payment.status`가 DB를 안 읽음 | "구현 안 된 것"으로 오해하기 쉽다 |
| Context 예산 12,000 고정 | "늘리면 되지" 하고 바꾸기 쉽다 |
| timeout을 재시도 안 함 | "재시도 넣어야지" 하고 추가하기 쉽다 |

**네 개 다 "개선처럼 보이는 되돌리기"다.** 결정 문서가 없으면 에이전트가 특히 잘 되돌린다.

## 번호

`D-CS-<3자리>-<주제>.md`

중앙 허브의 `D-<3자리>`와 구분하려고 `CS`를 넣는다. 번호는 재사용하지 않는다.

## 중앙 허브의 결정 중 이 저장소에 영향을 주는 것

| ID | 결정 | 여기서 무엇이 바뀌나 |
|---|---|---|
| [D-001](../../../wiki/decisions/D-001-payment-ownership.md) | 결제는 쇼핑몰이 소유 | 환불 계산식을 대조 구조로 변경, `read.payment` 추가 |
| [D-002](../../../wiki/decisions/D-002-graph-store-gate.md) | Graph Store는 게이트 통과 시에만 | `GraphStorePort` 유지, `SqlGraphAdapter`가 MVP |
| [D-003](../../../wiki/decisions/D-003-message-broker.md) | in-process queue | `MessageBusPort` 유지, 중복 전달·retry 테스트 필요 |
| [D-004](../../../wiki/decisions/D-004-self-hosting-rationale.md) | 자체호스팅은 규제 논거 | 3B 추론 실측 필요 |

## 관계

- [../../../wiki/decisions/index.md](../../../wiki/decisions/index.md) — 중앙 허브 결정
- [../log.md](../log.md) — 변경 이력
