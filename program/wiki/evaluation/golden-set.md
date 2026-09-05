---
type: concept
title: 골든셋
description: 평가 기준 72건의 구성과 분포. 페르소나·페인포인트가 여기서 나왔다
status: draft
impl_scope: cs — 골든셋은 cs 도메인 문항이다. sample 은 계약 테스트로 검증한다
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

### ★ [2026-09-04] "worried/confused 50%"를 검증하려 했다 — 못 했다

`[실측]` **골든셋만의 성질인지 일반 특성인지 판별하려 했다.** `datasets/voc/aihub_71603_aspect_sentiment` 로 대조를 시도했다.

**대조가 안 됐다.** 두 데이터가 **다른 축**을 잰다.

| | 무엇을 재나 | 라벨 |
|---|---|---|
| **golden.jsonl** | **상담 중 감정·불확실성 상태** | worried · confused · frustrated · negative · neutral |
| **aihub_71603** | **제품에 대한 만족도** (리뷰) | positive · neutral · negative |

**"이 상품 배송은 느렸지만 품질은 좋았다"의 긍정/부정과, "이거 어떻게 하는 건지 모르겠어요"의 불안·혼란은 서로 다른 질문이다.** 하나는 대상(제품)에 대한 평가고 하나는 화자(고객)의 상태다.

`[미확보]` **상담 중 감정·불확실성 상태를 라벨링한 공개 데이터를 못 찾았다.** `aihub_30716`(콜센터 QA) 도 `sentiment_raw` 필드가 전부 `null` 이라 못 쓴다.

**그래서 "worried/confused 50%가 골든셋만의 특성인지 일반적인지"는 여전히 모른다.** 이 wiki 안의 데이터로는 답할 수 없다.

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

`[실측]` v8 §15

**골든 60건은 다섯 종류를 포함한다.**

```
정상 · 모호 · PII · 승인 필요 · degraded
```

| 종류 | 왜 필요한가 |
|---|---|
| 정상 | 기본 |
| **모호** | `적절한 기권율`을 재려면 필요 |
| **PII** | 마스킹이 실제로 동작하는지 |
| **승인 필요** | 승인 경계가 걸리는지 |
| **degraded** | 자료가 깎였을 때 자동 실행 안 하는지 (`INV`·DoD-25) |

**뒤의 넷이 이 프로젝트다.** 정상 케이스만 넣으면 "잘못 자동화하지 않는다"를 증명할 수 없다.

| 원칙 | 이유 |
|---|---|
| 실제 데이터에서 파생 | 지어낸 케이스는 실제 분포를 반영 못 한다 |
| holdout 분리 | 60 + 20 |

## ★ 라벨링 절차 — 두 명 독립 + 제3자 조정

`[실측]` v8 §15가 정한 것.

> **두 명이 독립 라벨링하고 불일치는 제3자가 조정한다.**

**혼자 라벨링하면 자기 기준에 맞춰 읽게 된다.** 이 프로젝트가 [type 분류 검증](../governance/type-verification/index.md)에서 실제로 겪은 일이다 — 혼자 판정한 4.5%가 독립 판정에서 28.9%로 드러났다.

**같은 원칙이 골든셋에도 적용된다.**

`[미확보]` **지금 골든셋이 이 절차로 만들어졌는지 확인 안 됐다.** 일치율 기록이 없다.

### holdout은 만지지 않는다

**prompt 수정에 사용하지 않는다.** 만지는 순간 holdout이 아니다.

## ★ [2026-09-04] 자체 정정 — "실제 분포 40/20/20/20"이 틀렸다

`[실측]` **하루 전에 이 절이 "실제 데이터는 order 40%"라고 적었다. 틀렸다.**

`aihub_30716_callcenter_qa` 의 1,500건을 다시 열어 `source_category` 별 건수를 셌다.

```
주문   300   결제   300   배송   300   반품   300   교환   300
```

**전부 300건씩이다.** REPORT.md 가 스스로 적어 뒀다.

> **카테고리별 고객 turn 300건씩(seed=7) 무작위 샘플링**

**이건 자연 빈도가 아니라 층화표집이다.** 그리고 `주문`과 `결제` **두 카테고리가 둘 다 `order` 로 매핑**돼서 600(300+300)이 된 것이다 — **`order` 문의가 실제로 2배 많아서가 아니다.**

| intent | source_category | 건수 |
|---|---|---:|
| **order** | 주문 + 결제 (**두 카테고리**) | 600 |
| shipping | 배송 (한 카테고리) | 300 |
| return | 반품 (한 카테고리) | 300 |
| exchange | 교환 (한 카테고리) | 300 |

**`order` 가 두 배로 보이는 건 매핑에서 카테고리 두 개를 합쳤기 때문이다.** 표집 설계 자체가 균등(카테고리당 300)이었다.

### 그래서 이 데이터로는 "실제 분포"를 말할 수 없다

`[미확보]` **원본 콜센터 QA 전체(수십만 건)에서 각 카테고리가 실제로 몇 %인지는 이 표본에 없다.** 300건씩 뽑았으니 표본 안에서는 어차피 균등하다.

**골든셋의 균등 분할과 이 데이터의 균등 표집을 비교하는 것 자체가 의미 없다.** 둘 다 설계된 균등이지 자연 분포가 아니다.

**어제 이 문단을 쓸 때 `source_category` 를 안 보고 `mapped_intent` 합계만 봐서 틀렸다.** REPORT.md 를 먼저 읽었어야 했다.

## 인수 검사 — 기계가 보는 아홉 가지

`[실측]` [EVAL-DATASETS 검증](../../../final_project_cs/docs/evidence/DoD-EVAL-DATASETS_검증.md). 2026-08-17 쇼핑몰 도메인으로 다시 쓴 golden/holdout을 `scripts/verify_eval_datasets.py`가 받았다. 그때 기준 golden 60 · holdout 20이다(DoD-29 추가분 전).

| # | 검사 | 실패 조건 |
|---|---|---|
| 1 | 건수 | golden 60 / holdout 20 아님 |
| 2 | 스키마 | 8필드 정확히, 타입 |
| 3 | `expected_intent` | `order`·`shipping`·`return`·`exchange` 밖의 값 — **라우팅 가능한 값만** |
| 4 | `case_id` | `g-<intent>-NN`/`h-<intent>-NN` 형식, 80건 유일 |
| 5 | **`doc_ref`** | 25문서 실제 색인(`_doc_index.json`)과 문서 ID·섹션 제목 **문자열 완전일치.** 없는 문서·섹션을 인용하면 실패 |
| 6 | 한국어 | 글자 중 한글 50% 미만 |
| 7 | 커버리지 | 그 intent scope의 모든 문서가 golden에서 2회 이상 인용돼야 |
| 8 | 다양성 하한 | `wait_for_approval` ≥3 · degraded/unavailable ≥3 · negative/frustrated ≥5 |
| 9 | 중복 | golden/holdout 간 `case_id`·`message` 완전 중복 |

**5번이 이 검사의 핵심이다.** 골든셋이 코퍼스에 없는 근거를 정답으로 들면 judge가 그걸 기준으로 채점한다 — [protocol.md](protocol.md)의 "judge가 환각 인용에 점수" 사고와 같은 뿌리다.

### Codex가 쓴 데이터를 그대로 받지 않았다

`[실측]` 골든셋은 Codex 산출물이다. 받을 때 넷을 했다 — `git status`로 소유 범위 밖 파일 변경이 없는지, 검증 스크립트를 **Codex 실행과 별개로 직접 재실행**해 다양성 수치가 정확히 일치하는지, 무작위 12건을 사람이 읽어 `message`↔`doc_ref`↔`expected_next_action`이 의미적으로 맞는지, 그리고 **단위 붙은 숫자 주장을 정규식으로 전수 추출** — 80건 중 1건(`g-return-01`의 "7일")뿐이었고 코퍼스 `doc_11`의 청약철회 기한과 일치했다. 나머지는 숫자를 지어내지 않고 시나리오만 서술한다.

`[실측]` 이 재작성이 **낡은 테스트 단언 하나**를 드러냈다 — `test_dataset_counts_and_allocation_and_disjointness`가 옛 도메인 배분(`g-billing`/`g-technical`/`g-feedback` 20건씩)을 단언하고 있었다. 데이터셋 결함이 아니라 테스트가 낡은 것이었다.

## 한계

`[미확보]` 넷을 인정한다.

1. **72건은 적다.** 세부 분류별로는 표본이 한 자리수다
2. **실제 알파 로그가 아니다.** 운영 전환 전이라 실 고객 응대 데이터가 없다
3. **시나리오 획일성.** 파인튜닝 평가에서 지적된 문제다
4. **intent 비율이 실제 문의 분포와 다르다.** 균등 분할이지 비례 표집이 아니다 (위)

## 관계

- [metrics.md](metrics.md) — 이 데이터로 재는 지표
- [protocol.md](protocol.md) — 60 + 20 분리와 반복
- [../product/problem.md](../product/problem.md) — 이 분포의 해석
- [../product/personas.md](../product/personas.md) — 페르소나별 대응 케이스
