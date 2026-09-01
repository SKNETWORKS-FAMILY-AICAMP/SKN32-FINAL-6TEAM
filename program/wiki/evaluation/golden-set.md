---
type: concept
title: 골든셋
description: 평가 기준 72건의 구성과 분포. 페르소나·페인포인트가 여기서 나왔다
status: draft
tags: [evaluation, data]
owners: [human:미배정]
sources:
  - id: S1
    title: 골든셋 72건
    resource: ../../../final_project_cs/eval/datasets/golden.jsonl
---

# 골든셋

평가의 기준이 되는 케이스 모음. **72건이다.** `[실측:S1]`

이 분포가 [../product/problem.md](../product/problem.md)의 페인포인트와 [../product/personas.md](../product/personas.md)의 페르소나를 만들었다. 지어낸 게 아니라 여기서 나왔다.

## 감정 분포

| 감정 | 건수 | 비율 |
|---|---|---|
| worried (불안) | 21 | 29% |
| neutral | 20 | 28% |
| confused (혼란) | 15 | 21% |
| frustrated | 9 | 13% |
| negative | 7 | 10% |

**불안 + 혼란이 절반이다.** 화난 고객보다 모르겠는 고객이 많다.

제품 방향이 여기서 갈린다 — **달래는 게 아니라 알려주는 것**이다.

## 후속 동작 분포

| 후속 동작 | 건수 | 비율 |
|---|---|---|
| respond (즉답) | 40 | 56% |
| wait_for_approval (승인 대기) | 15 | 21% |
| wait_for_input (입력 대기) | 13 | 18% |
| escalate | 3 | 4% |
| handoff | 1 | 1% |

**39%가 승인·입력 대기로 사람에게 돌아온다.**

이 숫자가 두 가지를 결정한다.

1. **완전 자동화를 약속할 수 없다.** [../business/unit-economics.md](../business/unit-economics.md)의 "인원 감축을 팔지 않는다"가 여기서 나온다
2. **승인 경계가 제품의 일부다.** 버그가 아니라 기능이다

## 채널 분포

| 채널 | 건수 | 비율 |
|---|---|---|
| web | 23 | 32% |
| chat | 23 | 32% |
| email | 17 | 24% |
| phone | 9 | 12% |

**chat 32%가 현재 지연으로는 어렵다.** p50 20~34초라 실시간 채팅에 못 쓴다. → [../product/scope.md](../product/scope.md)

**phone 12%는 음성이라 별도 원가 산정이 필요하다.** 텍스트 기준 결론을 여기 연장하면 안 된다.

## 금액 관련 케이스

| capability | 건수 |
|---|---|
| `return.request` | 13 |
| `return.check_eligibility` | 10 |
| `refund.calculate` | 7 |
| **소계** | **30 (42%)** |

**42%가 금액이 걸린 케이스다.** 이게 [../decisions/D-001-payment-ownership.md](../decisions/D-001-payment-ownership.md)에서 결제 구성 읽기가 필요한 이유이고, 환불 계산식 결함이 위험한 이유다.

## 구성 원칙

| 원칙 | 이유 |
|---|---|
| 실제 데이터에서 파생 | 지어낸 케이스는 실제 분포를 반영 못 한다 |
| 근거 부족 케이스 포함 | `적절한 기권율`을 재려면 필요 |
| 근거 충분 케이스 포함 | `과잉 기권율`을 재려면 필요 |
| holdout 분리 | 60 + 20 |

## 한계

`[미확보]` 세 가지를 인정한다.

1. **72건은 적다.** 세부 분류별로는 표본이 한 자리수다
2. **실제 알파 로그가 아니다.** 운영 전환 전이라 실 고객 응대 데이터가 없다
3. **시나리오 획일성.** 파인튜닝 평가에서 지적된 문제다

## 관계

- [metrics.md](metrics.md) — 이 데이터로 재는 지표
- [protocol.md](protocol.md) — 60 + 20 분리와 반복
- [../product/problem.md](../product/problem.md) — 이 분포의 해석
- [../product/personas.md](../product/personas.md) — 페르소나별 대응 케이스
