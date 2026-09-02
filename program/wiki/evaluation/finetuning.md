---
type: plan
title: 파인튜닝 경로와 증명 범위
description: 무엇을 튜닝하고 무엇은 계속 DB에서 읽는가. 증명 대상은 모델 성능이 아니라 오케스트레이션이다
status: draft
impl_scope: cs — 파인튜닝은 cs 도메인 골든셋으로 학습·평가한다. sample 에는 그 데이터가 없다
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

## ★ [2026-09-03] 실행 결과 — 배선은 됐고 모델은 못 쓴다

`[실측]` `docs/plans/2026-08-30_DoD28-FT-RAG통합_설계.md` 에서 이관.

**배경:** `Proposed+FT`(파인튜닝 모델 단독 호출)가 golden/holdout **양쪽에서 0% pass** 였다. 원인은 Team 파이프라인 **밖에서** 호출돼 **RAG evidence 를 아예 못 받았기** 때문.

**파이프라인 안으로 넣는 배선을 만들고 실행했다.** 배선은 전부 동작한다. **모델 품질은 채택 불가.** → [D-CS-002](../../final_project_cs/wiki/decisions/D-CS-002-finetuned-model-not-adopted.md)

### ★ 그 과정에서 터질 지뢰를 찾았다

`[실측]` `response.generate`·`response.review_tone` 프롬프트가 **한 번도 등록된 적이 없었다.** 파일 자체가 저장소에 없었다.

```
RuntimeError: no active prompt registered for response.generate
```

**production 배선으로 재현하면 매번 났다.**

`[실측]` **지금 실 트래픽을 죽이고 있지는 않다** — `config/project.yaml` 의 `response_review.enabled: false` 때문이다.

> **켜는 순간 터질 지뢰였다.**

**끄고 있어서 안 드러난 결함이다.** 프롬프트 파일 신규 작성 · allowlist 갱신 · DB 재등록 · 회귀 테스트 3건으로 고쳤다.

### 데이터가 없다는 것을 발견했다

`[실측]` `_maybe_review()` 를 읽어 확인했다.

> 이 Team 은 primary Team 이 만든 **`result.answer` 를 검토·재작성하는 사후 처리**이지 고객 메시지를 직접 받는 게 아니다.

golden 72건은 전부 결정론적 Team(`return_refund`·`procurement_order_payment`·`fulfillment_logistics`)으로만 라우팅된다.

> **이 Team 을 훈련할 실제 데이터가 golden/holdout 에 전혀 없었다.**

**지어내지 않고 우회했다** — golden 의 judge-pass 행에서 evidence·answer 를 가져와 `_maybe_review()` 와 같은 입력 모양을 만들고, **고친 실제 프롬프트를 진짜로 호출**해 grounded completion 을 수집했다.

### ★ 데이터를 10배로 늘려도 draft 가 2개뿐이었다

`[실측]` 2026-08-31. 실 민원 93건을 더해 **157건**(최초 16건의 9.8배)을 만들었다.

**그런데 고유 draft 문자열이 여전히 2개였다.**

```
151건  반품 고정문구
  6건  "Order verified..." 고정문구
```

**원인을 특정했다.**

> 이 review-task 의 `input_text` 는 **고객 메시지가 아니라 1차 팀의 초안 답변**이고, 결정론적 Team 은 case_type 만 맞으면 **고객 메시지와 무관하게 항상 같은 고정 문자열**을 낸다.

**고객 메시지를 아무리 다양화해도 그 지점에서 전부 같은 초안으로 수렴한다.** golden·holdout·실주문·민원 **네 소스가 전부 같은 함정에 빠졌다.**

`[실측]` **탈출 경로도 찾았다.** `fulfillment_logistics.py` 는 상태값을 f-string 에 박는다.

```python
f"배송 상태는 {status}입니다."
```

**capability 를 `shipment.status` 로 바꾸면 case 마다 진짜 다른 draft 가 나온다.** 최소 3종은 확보 가능하다.

`[미확보]` **아직 실행 안 했다.**

### 여기서 배울 것

> **데이터를 늘리기 전에 그 데이터가 실제로 다양한지 세어야 한다.**

**157건을 만들고 나서야 2개인 걸 알았다.** 건수는 다양성이 아니다.

## ★ [2026-09-03] 데이터량 기준 — 외부 근거

`[외부]` `program/research/_법령사실_2026-08-15.md` §5 에서 이관.

| 기준 | 값 |
|---|---|
| 도메인 적응용 QLoRA 권장 | **5,000~20,000 예시** |
| **500건 미만이면** | **epoch 1~2회로 제한** — 소량으로 하되 과적합을 막는다 |
| LoRA vs full fine-tuning | LoRA 가 **일반적으로 약하다.** 비슷하게 하려면 **rank 를 256 처럼 크게** |

`[외부]` "Fine-Tuning LLMs in 2026: LoRA, QLoRA, DPO, GRPO Compared" · arXiv "Data Efficient Adaptation in LLMs via Continuous Low-Rank Fine-Tuning"

### ★ 파인튜닝이 실제로 고치는 것 셋

> **정확한 출력 스키마 · 좁은 도메인 어휘 · 브랜드 톤**

**지식 주입이 아니다.** 이 문서의 [목표 절](#목표--지식-주입이-아니다)과 같은 결론에 외부 근거가 붙는다.

### 우리 실측과 대조하면

`[실측]` 우리는 **157건**까지 늘렸다. **500건 미만 구간이다.**

**그러니 epoch 를 줄이는 게 맞다.** 그리고 실제로 문제는 건수가 아니라 **고유 draft 가 2개**인 것이었다.

> **5,000건을 모아도 draft 가 2개면 소용없다.**

`[외부]` **RTX 4070 Ti 한 장으로 7B 모델을 반나절에** 도메인 특화할 수 있다는 보고가 있다. 우리 장비는 **4070 SUPER 12GB** 다. → [12GB 제약](#12gb-제약)

## 관계

- [protocol.md](protocol.md) — 비교 프로토콜
- [metrics.md](metrics.md) — 지표 정의
- [golden-set.md](golden-set.md) — 평가 데이터
- [../business/infrastructure-cost.md](../business/infrastructure-cost.md) — 자체호스팅 원가
- [../delivery/dod.md](../delivery/dod.md) — DoD-28
