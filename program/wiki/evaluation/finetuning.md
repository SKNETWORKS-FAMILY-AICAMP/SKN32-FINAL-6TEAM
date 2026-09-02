---
type: plan
title: 파인튜닝 경로와 증명 범위
description: 무엇을 튜닝하고 무엇은 계속 DB에서 읽는가. 증명 대상은 모델 성능이 아니라 오케스트레이션이다
status: draft
tags: [evaluation, data]
owners: [human:미배정]
---

# 파인튜닝 경로와 증명 범위

`[실측]` v8 §15-8·§15-8-A에서 이관.

## ★ 무엇을 증명하려는 게 아닌가

> **A-COP의 증명 대상은 모델 성능이 아니라 오케스트레이션이다.**

**모델을 교체해도** Case lifecycle·Context Broker·Team routing·approval·idempotency·WAIT/RESUME가 유지되는지가 핵심이다.

**파인튜닝은 그 주장을 흔들지 않는 선에서만 한다.**

## 목표 — 지식 주입이 아니다

| 맞추는 것 | 맞추지 않는 것 |
|---|---|
| 출력 스키마 | **정책의 진실값** |
| 주문·취소·환불·배송 도메인 어휘 | **현재 주문 상태** |
| 근거·승인·보류를 표시하는 톤 | **금액** |

**오른쪽 셋은 계속 Context Broker와 DB에서 읽는다.**

모델이 정책이나 금액을 "외우면" 데이터가 바뀔 때 조용히 틀린다. **그게 이 프로젝트가 가장 경계하는 것이다.**

## 2단계

| 단계 | 데이터 | 제약 |
|---|---|---|
| **1차** | 고객지원 공개 데이터 중 주문·취소·환불·배송 표현. **라이선스 확인 후** 선별하고 한국어로 재작성 | — |
| **2차** | 내부·알파의 **비식별화** Case. 성공·실패·보류·사람 수정 결과와 함께 | **500건 미만이면 epoch 1~2회로 제한** |

**500건 제한이 중요하다.** 적은 데이터로 많이 돌리면 외운다.

## 데이터 2트랙

**섞으면 안 된다.**

| 트랙 | 주 소스 | 무엇을 |
|---|---|---|
| **도메인 사실** | 실제 스마트스토어 주문·반품·취소·교환·리뷰 | 사실 관계 |
| **표현·의도** | Bitext, Kaggle Customer Service Conversations | 문장 다양성·intent 표현 |

**표현 트랙으로 주문·가격·환불 사실을 주입하지 않는다.**

`[실측]` Olist는 **주 소스가 아니다.** 스키마·관계 fixture와 비교 기준이다.

**원문이나 개인정보는 문서에 옮기지 않는다.**

## 모듈별 배분

`[실측]` v8 §15-8-A

| 모듈 | 도메인 사실 트랙 | 표현·의도 트랙 |
|---|---|---|
| Procurement + Order & Payment | 스마트스토어 주문·결제·취소 Case, Olist 관계 | Bitext 주문취소·조회, Kaggle 주문·계정 |
| Fulfillment & Logistics | 배송·지연·교환 상태, Olist 배송일·리뷰 관계 | Kaggle 배송·주문조회 |
| VOC & Store Manager | Case event·리뷰·반복 불만 집계 | Kaggle 상품불만·계정문제. **alert 정답은 도메인 트랙에서** |
| Response Generation & Review | 각 모듈의 근거·정책·ActionProposal | Bitext·Kaggle 문장·톤 다양화 |
| Catalog & Verification | 상품·SKU·Variant·가격, Olist 관계 | **검증 사실은 공개 문장에서 학습하지 않음** |
| Return & Refund | 반품·교환·환불·증빙·정책 Case | Bitext 환불 intent. **현재 Mock이라 평가 배분 0** |

**VOC와 Catalog 행의 단서가 중요하다.** 표현은 공개 데이터로 배우되 **정답은 도메인 데이터에서만** 온다.

## 비교 방법

```
1차·2차 각각  Proposed  vs  Proposed+FT
같은 golden 60 · holdout 20
```

**1차 목표 지표는 둘이다.**

| 지표 | 왜 이것인가 |
|---|---|
| **스키마 준수율** | 파인튜닝이 맞추려는 것이 출력 형태다 |
| **근거 정합률** | 지식을 외우지 않았는지 본다 |

함께 기록할 것 — `근거 초과율` · `적절한 기권율` · `과잉 기권율`

**holdout으로 학습 데이터나 prompt를 다시 고치지 않는다.**

## 리포트에 반드시 넣을 것

```
분모 · model · temperature · seed
prompt version · dataset hash · bootstrap 95% CI
```

**분모가 첫 줄인 게 의도적이다.** 비율만 적으면 몇 건 중 몇 건인지 모른다.

## 현재 상태

`[실측]` 2026-08-30 기준

| | |
|---|---|
| 베이스 모델 | `Qwen/Qwen2.5-3B-Instruct` + LoRA |
| 1차 (공개) | AI Hub K쇼핑 콜센터 QA 1,500건. 376스텝 완료 |
| 2차 | **알파 실데이터가 없어** golden 재측정 judge 통과분 22건으로 대체 |
| **결과** | **`Proposed+FT`가 golden·holdout 양쪽에서 0% pass** |

**2차가 계획대로 안 됐다.** v8이 말한 "알파 실데이터"는 운영 전환 이후에나 생긴다.

**그리고 결과가 부정적이다.** 원인 분석은 `docs/plans/2026-08-30_DoD28-FT-RAG통합_설계.md`.

## 12GB 제약

`[실측]` 학습이 세 번 막혔다. 프로덕션 입력 중앙값 10,670토큰인데 12GB에서 1,024토큰으로 깎아야 돌았다.

→ [../business/infrastructure-cost.md](../business/infrastructure-cost.md) §3

## 관계

- [protocol.md](protocol.md) — 비교 프로토콜
- [metrics.md](metrics.md) — 지표 정의
- [golden-set.md](golden-set.md) — 평가 데이터
- [../business/infrastructure-cost.md](../business/infrastructure-cost.md) — 자체호스팅 원가
- [../delivery/dod.md](../delivery/dod.md) — DoD-28
