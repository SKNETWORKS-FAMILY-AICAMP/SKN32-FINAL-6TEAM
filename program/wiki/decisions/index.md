---
type: guide
title: Decisions
description: 되돌리려면 근거가 필요한 선택들. 기각한 대안도 함께 기록한다
status: draft
---

# Decisions

**왜 그렇게 했는가**를 남기는 곳이다.

문서가 없으면 나중에 누군가 코드만 보고 "왜 이렇게 했지, 고쳐야겠다" 하면서 되돌린다. 특히 에이전트가 그런다. 그래서 **기각한 대안을 함께 적는다.**

## 무엇이 여기 오는가

| 온다 | 안 온다 |
|---|---|
| 되돌리려면 근거가 필요한 선택 | 명백한 구현 선택 |
| 대안이 실제로 있었던 것 | 대안이 없던 것 |
| 여러 저장소에 영향 | 한 파일 안에서 끝나는 것 |
| 나중에 "왜 안 했지"가 나올 것 | 조사 자료 (→ `research/`) |

**조사와 결정을 구분한다.** 알아본 것은 `research/`, 정한 것은 여기다. 결정 문서가 조사 문서를 `sources`로 참조한다.

## 목록

| ID | 결정 | 상태 | 영향 |
|---|---|---|---|
| [D-001](D-001-payment-ownership.md) | 결제 실행은 검증 쇼핑몰이 소유한다 | draft | cs, 검증 쇼핑몰 |
| [D-002](D-002-graph-store-gate.md) | Graph Store는 채택 게이트 통과 시에만 | draft | cs |
| [D-003](D-003-message-broker.md) | Message Broker는 in-process queue | draft | cs |
| [D-004](D-004-self-hosting-rationale.md) | 자체호스팅은 원가가 아니라 규제 논거 | draft | 사업·제품 |

## 결정 문서 골격

```markdown
## 맥락           어떤 상황에서 이 판단이 필요했는가
## 결정           한 문장
## 선택지와 이유   표. 채택 여부와 이유
## 결과           무엇이 바뀌는가. 무엇을 못 하게 되는가
## 근거           [실측] 코드 위치 · [외부] 출처
```

**"결과"에 "무엇을 못 하게 되는가"를 반드시 쓴다.** 결정은 항상 무언가를 포기하는 것이고, 그걸 안 적으면 나중에 왜 막혔는지 모른다.

## 번호

`D-<3자리>-<주제>.md`. 번호는 재사용하지 않는다. 폐기된 결정도 번호를 유지하고 `status: deprecated`로 바꾼다.

## 미결정

아직 답이 없는 것. 정해지면 여기로 온다.

| 항목 | 무엇이 필요한가 | 어디 |
|---|---|---|
| 가격 정책 | 오류 1건당 손실 실측 | [../business/pricing.md](../business/pricing.md) |
| 자체호스팅 채택 | 3B 추론 처리량·정확도 실측 | [../business/infrastructure-cost.md](../business/infrastructure-cost.md) |
| 환불 계산 전환 시점 | 검증 쇼핑몰과 계약 협의 | [D-001](D-001-payment-ownership.md) |
| 음성 채널 | 별도 원가 산정 | [../product/scope.md](../product/scope.md) |

## 인접 영역

- [../research/index.md](../research/index.md) — 결정의 재료가 된 조사
- [../product/index.md](../product/index.md) — 제품 결정이 여기서 나온다
- [../log.md](../log.md) — 결정이 추가된 시점
