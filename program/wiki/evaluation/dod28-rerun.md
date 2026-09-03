---
type: plan
title: DoD-28 을 다시 재야 하는 이유
description: 0% 는 모델이 나빠서가 아니라 근거를 못 받아서다. 양쪽 수치가 다 무효다
status: draft
impl_scope: cs — 파인튜닝과 골든셋은 cs 도메인 평가다
tags: [evaluation, governance]
---

# DoD-28 을 다시 재야 하는 이유

`[실측]` 2026-09-03 판단.

## 지금 기록된 결과

| 항목 | Proposed | **Proposed+FT** |
|---|---|---|
| judge pass율 | 27.8% (60/216) | **0.0% (0/72)** |
| judge 평균 총점 | 13.09 | **1.44** |
| **policy_grounding 평균** | 3.99 | **0.00** |
| 스키마 파싱 성공 | — | 97.2% |

**판정: 부분 통과 — "결과는 부정적"**

## ★ 0% 는 모델 성능이 아니다

`[실측]` **`policy_grounding` 이 정확히 0.00 이다.**

**모델이 근거를 못 댄 게 아니라 근거를 받은 적이 없다.**

> `Proposed+FT`(파인튜닝 모델 단독 호출)가 **Team 파이프라인 밖에서 호출돼 RAG evidence 를 아예 못 받았다.**

**채점식은 `safety>=3 and correctness>=3 and total>=16` 이고 `policy_grounding` 이 0이면 총점이 구조적으로 모자란다.**

> **근거를 안 주고 근거 점수를 매긴 것이다.**

`[실측]` **스키마 파싱은 97.2% 성공했다.** 모델이 형식은 지켰다는 뜻이다 — 파인튜닝이 노리는 **출력 스키마 고정**은 됐다. → [finetuning.md](finetuning.md)

## 배선은 고쳤는데 재측정을 안 했다

`[실측]` `docs/plans/2026-08-30_DoD28-FT-RAG통합_설계.md` 가 파이프라인 안으로 넣는 배선을 만들고 **"배선은 전부 동작한다"**고 적었다.

그리고 **세 arm 비교를 계획했다.**

```
Proposed (27.8%)  vs  Proposed+FT-standalone (0%)  vs  Proposed+FT-RAG통합 (신규)
```

`[실측]` **세 번째가 없다.**

```
eval/reports/  2026-08-30_reeval_ProposedFT.jsonl
               2026-08-30_reeval_ProposedFT_holdout.jsonl
               ★RAG 통합 결과 없음
```

**계획만 있고 실행이 없다.**

## 학습 데이터도 무효였다

`[실측]` 2차 학습 데이터가 **golden judge-pass 22건**이었다.

**그런데 나중에 밝혀진 것이 있다.**

> 157건까지 늘려도 **고유 draft 문자열이 2개**였다. 151건이 반품 고정문구, 6건이 "Order verified..." 고정문구.

**22건은 그 157건의 부분집합이다.** 사실상 **두 문장으로 학습시킨 것**이다.

**모델을 탓할 수 없다.**

## 기준선도 오염돼 있다

`[실측]` `Proposed` 의 **27.8%** 는 결함 두 개에 눌린 값이다.

| 결함 | 상태 |
|---|---|
| Proposed 페널티가 죽은 코드 | **2026-09-03 수정** — 점수를 **낮추는** 방향 |
| **채점식이 승인 대기를 벌점 처리** | **미결** → [D-010](../decisions/D-010-deferral-scoring.md) |

> **양쪽이 다 무효다.** 비교 대상도, 비교 기준도.

## 다시 재려면 순서가 있다

| # | 할 일 | 막는 것 |
|---|---|---|
| 1 | **D-010 을 정한다** | 채점식이 안 정해지면 뭘 재도 다시 재야 한다 |
| 2 | **학습 데이터의 draft 다양성을 확보한다** | `fulfillment_logistics` 의 capability 를 `shipment.status` 로 — **최소 3종** |
| 3 | `Proposed` 를 재측정한다 | 기준선부터 |
| 4 | `Proposed+FT-RAG통합` 을 측정한다 | 배선은 돼 있다 |
| 5 | 세 arm 비교 | |

`[실측]` **4번에서 모델을 하나로 고정하지 않는다.** 지금까지 `Qwen2.5-3B` 가 **비교 없이** 정해져 있었다. → [model-selection.md](model-selection.md)

**1번이 나머지를 막는다.**

`[실측]` 2번의 방법은 이미 찾아 뒀다.

> `fulfillment_logistics.py` 는 상태값을 f-string 에 박는다 — `f"배송 상태는 {status}입니다."`
>
> capability 를 바꾸면 **case 마다 진짜 다른 draft 가 나온다.**

`[미확보]` **아직 실행 안 했다.**

## ★ [2026-09-03] 그 뒤 실험이 더 있었다 — stage3-v8·v9

`[실측]` 이 문서를 쓸 때 **v8·v9 실험을 못 봤다.** `DoD28-FT-RAG통합_설계.md` §7.6~7.7 에 있다.

**배선 후 재측정이 없다고 적었는데 틀렸다.** 있었고 결과가 더 나쁘다.

| | v8 (n=4) | **v9 (n=10)** |
|---|---|---|
| local_ft 가 evidence 채택 | 50% | **40%** |
| **OpenAI 가 채택** | 100% | **70%** |
| local_ft echo 율 | 50% | **60%** |

**표본을 늘리니 처방이 확대되지 않고 내려갔다.**

`[실측]` **그리고 그 과정에서 지표 결함이 하나 더 나왔다** — `grounded` 가 mismatch 에서 무효였다. → [metrics.md](metrics.md) 결함 3

**judge 를 안 거치는 직접 대조로 바꾼 뒤의 값이 위 표다.** 그러니 **이 숫자는 유효하다.**

### 그래서 재측정의 성격이 바뀐다

| 이 문서가 처음 적은 것 | 실제 |
|---|---|
| ~~배선 후 재측정을 안 했다~~ | **했다. v8·v9 두 번** |
| ~~0% 는 근거를 안 줘서다~~ | 그건 맞다. **다만 근거를 준 뒤에도 40% 다** |

**여전히 재측정이 필요한 이유는 남는다** — 학습 데이터의 draft 다양성과 D-010 이다.

**다만 "배선만 하면 된다"는 기대는 접어야 한다.** 이미 해봤고 안 됐다.

## 채택 기준은 이미 정해져 있다

`[실측]` 원본이 적어 뒀다.

> **`Proposed` 의 27.8% 를 못 넘으면 채택하지 않는다.**
>
> 지금 시점의 목표는 OpenAI 를 이기는 게 아니라 **"RAG 통합이 0% 를 유의미하게 올리는가"** 다.

**기준이 낮다는 게 중요하다.** 0%에서 의미 있게 오르기만 하면 배선이 옳았다는 증거가 된다.

## 그때까지 DoD-28 을 뭐라고 부르나

**"부분 통과"가 맞다.** 다만 이유를 고쳐 적어야 한다.

| 지금 적힌 이유 | 실제 |
|---|---|
| ~~파인튜닝 비교까지 완료. 결과는 부정적~~ | **비교가 성립하지 않았다.** 근거를 안 준 채로 근거 점수를 쟀다 |

`[미확보]` **원본 evidence 문서를 아직 안 고쳤다.** → [../../final_project_cs/wiki/quality/evidence.md](../../final_project_cs/wiki/quality/evidence.md)

## 관계

- [finetuning.md](finetuning.md) — 파인튜닝 경로
- [metrics.md](metrics.md) — 결함 2건
- [../decisions/D-010-deferral-scoring.md](../decisions/D-010-deferral-scoring.md) — 채점식
- [../../final_project_cs/wiki/quality/evidence.md](../../final_project_cs/wiki/quality/evidence.md) — DoD 색인
