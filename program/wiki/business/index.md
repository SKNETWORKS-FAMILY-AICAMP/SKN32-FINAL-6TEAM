---
type: guide
title: Business
description: 얼마짜리인가. 건당 원가·인프라 비용·시장 규모·가격안
status: draft
---

# Business

## 결론 세 줄

`[실측]`·`[외부]` 근거는 각 문서에

1. 사람이 문의 1건 처리하는 데 **4,100~4,846원**이 든다. 급여는 그중 67%뿐이고 나머지는 보험·퇴직금·좌석·이직·관리다.
2. A-COP을 넣으면 건당 **1,132원**이 된다. 그중 LLM 비용은 **3.03원**, 전체의 0.27%다.
3. **비용의 99.7%는 여전히 사람이다.** LLM 단가를 깎는 최적화는 의미가 없고, **사람 시간을 줄이거나 오류를 줄이는 것**만 의미가 있다.

## 읽기 순서

1. [unit-economics.md](unit-economics.md) — 사람 vs A-COP 건당 비교
2. [infrastructure-cost.md](infrastructure-cost.md) — API·GPU·전기·트래픽
3. [market.md](market.md) — 시장 규모
4. [pricing.md](pricing.md) — 가격안 3개

## 각 문서

| 문서 | 답하는 질문 |
|---|---|
| [unit-economics.md](unit-economics.md) | 상담원을 쓸 때와 A-COP을 쓸 때 건당 얼마인가 |
| [infrastructure-cost.md](infrastructure-cost.md) | API·GPU 중 뭘 쓰고 얼마 드는가 |
| [market.md](market.md) | 시장이 얼마나 큰가 |
| [pricing.md](pricing.md) | 우리가 얼마를 받아야 하는가 |

## 팔지 말아야 할 논거

**절감액으로 팔면 자기모순이다.** [../product/positioning.md](../product/positioning.md)에서 자동화율을 앞세우지 않기로 했는데, 절감액은 자동화율에서 나온다.

그리고 실제로 인원이 줄지 않는다. `[실측]` 골든셋에서 39%가 승인·입력 대기로 사람에게 돌아오고 5%는 구조적으로 사람 몫이다.

**주력 논거는 오류 비용이다.**

| 축 | 산식 | 우리 축인가 |
|---|---|---|
| 처리 비용 | 건당 처리시간 × 인건비 | 보조 |
| **오류 비용** | **오류율 × 건당 오류 손실** | **★ 주력** |
| 도입·운영 비용 | LLM + 승인 대기 인건비 + 인프라 | 우리가 받는 값 |

## 이 영역의 약점

숫자가 많지만 **가장 중요한 입력 셋이 전부 `[추정]`이다.**

| 항목 | 상태 | 어떻게 채우나 |
|---|---|---|
| 검토·승인 1건 소요시간 | `[추정]` 2.36분 | 내부 실험. 반나절 |
| 오류 1건당 손실 | `[추정]` 3만원 | 분쟁 사례집 금액 집계. 하루 |
| 도입 전 오류율 | `[미확보]` | 도입 기업 사내 데이터 |

**2.36분이 흔들리면 72% 절감이 통째로 흔들린다.** 이 표를 상한선으로만 제시한다.

## 인접 영역

- [../product/personas.md](../product/personas.md) — 정미라 조직이 모델 조직이다
- [../product/positioning.md](../product/positioning.md) — 무엇으로 파는가
- [../decisions/D-004-self-hosting-rationale.md](../decisions/D-004-self-hosting-rationale.md) — 자체호스팅 논거
