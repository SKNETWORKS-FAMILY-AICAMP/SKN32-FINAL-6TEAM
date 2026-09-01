---
type: concept
title: 포지셔닝
description: A-COP은 자동응답 제품이 아니라 멀티에이전트 고객운영의 통제·검증층이다
status: draft
tags: [customer-operations]
---

# 포지셔닝

## 원라이너

> 멀티에이전트를 **동작하게** 만드는 건 어렵지 않습니다. **믿을 수 있게** 만드는 게 어렵습니다.

## 제품 정의

A-COP은 **하나의 A-COP Runtime 위에 CS Pack과 Commerce Ops Pack을 교체·확장하는 B2B Agentic Operations Platform**이다.

소비자는 자기 Agent 하나로 상품·주문·배송·CS를 이용하고, 운영자는 Case·Action·승인·근거·평가를 한 화면에서 감독한다.

10주에는 자동화 CS와 제한된 Commerce 검증 사이트를 구현한다. 전면 사이트 생성·판매와 재고·발주·배송·정산 자동화는 vision으로 둔다.

## 말하지 않는 것

**"LLM으로 고객 문의를 자동응답한다"로 설명하면 시장의 기존 제품과 구분되지 않는다.**

A-COP이 주장하는 것은 새로운 모델도 새로운 RAG도 아니다. **멀티에이전트 고객운영의 통제·검증층**이다.

그래서 자동화율을 앞세우지 않는다. 대신 두 가지를 함께 제시한다.

- **잘못 자동화하지 않는 지점** — 근거가 부족하면 사람에게 넘긴다
- **인계 품질** — 넘길 때 무엇을 함께 넘기는가

이 선택이 [../business/pricing.md](../business/pricing.md)의 가격 논거를 결정한다. 절감액이 아니라 **오류 비용**으로 판다.

## 양면 구조

**소비자 면.** 자기 Agent 하나로 상품·주문·배송·문의를 잇는다. Commerce MCP + CS MCP.

**운영자 면.** human-on-the-loop다. 고위험 Action만 사람이 승인하고(human-in-the-loop), 나머지는 자동 처리하되 운영자는 이상 신호를 감독한다.

**감독이 성립하려면 "이상"이 정의돼 있어야 한다.** 이상은 수치의 절대값이 아니라 **기준선 대비 정해진 변화가 생긴 상태**로 정의한다. 내부 단계에서 fixture 기준선을 만들고, 알파부터 유형·시간대별 baseline을 저장한다. 정확한 임계값은 실제 분포 측정 후 확정한다. `[미확보]`

## 제공 형태는 도구다

Team은 Registry 등록형이므로 **도입 기업이 자사 업무 Team을 추가해도 Core 코드는 바뀌지 않는다.** 기업이 자기 Team을 꽂아 쓰는 플랫폼이다.

이 선택이 [../architecture/core-vs-team.md](../architecture/core-vs-team.md)의 모듈화 설계와 계약 불변성을 **상업적 근거**로 만든다.

구축을 누가 하느냐는 이 성질과 별개다. 도입 기업이 직접 구성할 수도 있고 우리가 맡을 수도 있다. 어느 쪽이든 결과물은 플랫폼 위의 선언으로 남아 나중에 기업이 이어받을 수 있다.

## 자체호스팅의 논거

자체호스팅은 차별점이지만 **원가 절감이 아니다.**

`[실측]` 모델 조직(상담원 12명, 월 10,500건) 기준 건당 비교.

| | 건당 | API 대비 |
|---|---|---|
| API (gpt-4o-mini) | 3.03원 | 1.0배 |
| 온프레미스 | 10.9원 | 3.6배 |
| 클라우드 GPU 임대 | 42.8원 | 14.1배 |

원가로 뒤집히는 지점은 상담원 약 43명이다. **그 아래에서 자체호스팅을 택하는 이유는 하나뿐이다 — 고객 데이터를 밖으로 내보낼 수 없어서다.**

자체호스팅을 원가 절감으로 팔면 계산할 줄 아는 상대에게 바로 반박당한다. **규제·보안 요건이 1차 논거다.** 상세는 [../business/infrastructure-cost.md](../business/infrastructure-cost.md).

## 가격 정책

`[미확보]` 아직 정하지 않았다. 안 3개와 판단 근거는 [../business/pricing.md](../business/pricing.md).

## 관계

- [problem.md](problem.md) — 이 포지셔닝이 답하려는 문제
- [personas.md](personas.md) — 누구에게 이 말을 하는가
- [scope.md](scope.md) — 10주에 어디까지
- [../business/unit-economics.md](../business/unit-economics.md) — 원가와 절감 구조
- [../architecture/pack-model.md](../architecture/pack-model.md) — Runtime + Pack 구조

## 결정

이 포지셔닝에서 파생된 결정들.

- [../decisions/D-001-payment-ownership.md](../decisions/D-001-payment-ownership.md) — 결제를 갖지 않는다
- [../decisions/D-004-self-hosting-rationale.md](../decisions/D-004-self-hosting-rationale.md) — 자체호스팅은 규제 논거
