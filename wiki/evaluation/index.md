---
type: guide
title: Evaluation
description: 무엇으로 증명하는가. 지표·프로토콜·골든셋·Judge 루브릭
status: draft
domain: neutral
---

# Evaluation

**주장을 숫자로 바꾸는 영역이다.**

[../product/positioning.md](../product/positioning.md)에서 "자동화율을 앞세우지 않고 잘못 자동화하지 않는 지점을 제시한다"고 했다. 그 약속을 지키는 게 여기다.

## 읽기 순서

1. [metrics.md](metrics.md) — 무엇을 재는가
2. [golden-set.md](golden-set.md) — 무엇으로 재는가
3. [protocol.md](protocol.md) — 어떻게 재는가
4. [judge.md](judge.md) — 사람 없이 어떻게 판정하는가
5. [judge-second-opinion.md](judge-second-opinion.md) — **judge 를 누가 검산하는가**
6. [finetuning.md](finetuning.md) — **파인튜닝 경로와 증명 범위**

## 각 문서

| 문서 | 답하는 질문 |
|---|---|
| [metrics.md](metrics.md) | 지표 15종의 정의와 산식 |
| [golden-set.md](golden-set.md) | 72건이 어떻게 구성돼 있는가 |
| [protocol.md](protocol.md) | A/B/Proposed, 60+20, 통계 처리 |
| [judge.md](judge.md) | LLM-as-Judge 루브릭과 사람 라벨 일치도 |
| [judge-second-opinion.md](judge-second-opinion.md) | judge 를 두 번 더 읽었을 때 어디가 어긋나는가 |
| [finetuning.md](finetuning.md) | **무엇을 튜닝하고 무엇은 DB에서 읽는가** |

## 핵심 지표 넷

전체 15종 중 이 프로젝트의 주장을 직접 떠받치는 것들.

| 지표 | 무엇을 증명하나 | 누구를 위한 것 |
|---|---|---|
| `근거 정합률` | 답변이 실재 데이터에 근거하는가 | 박선영 (고객) |
| `근거 초과율` | 없는 걸 지어내는가 | 박선영 |
| `적절한 기권율` | 모를 때 모른다고 하는가 | 정미라 (운영 책임자) |
| `과잉 기권율` | 알 수 있는데 넘기는가 | 정미라 |

**뒤의 둘이 균형이다.** 기권이 0이면 안전장치가 없는 것이고, 너무 많으면 자동화 이득이 사라진다. 이 균형점이 제품의 실체다.

페르소나 연결은 [../product/personas.md](../product/personas.md).

## 실측 현황

`[실측 2026-09-07]` golden 216건 × 세 군. **judge v3 재기준선 산출물**
(`eval/reports/2026-09-06_rebaseline_{A,B,Proposed}_judgev3.jsonl`)에서 뽑았다 —
`[정정 2026-09-10]` 「세 군이 **같은 실행**」이라 적었는데 **아니다** — **같은 judge(v3)로 09-06 에 재채점**한 것이고 실행은 다르다: A·B 는 `2026-08-24_reeval_A/B.jsonl`, Proposed 는 `2026-08-28_reeval_Proposed_v3.jsonl`(각 파일 `rescore.source_raw`). ★**그리고 공정한 비교가 아니다** — 세 군 모두 모델 입력에 정답이 들어갔고, **B 는 정답 intent 로 걸러진 근거를 받았다** → [protocol.md](protocol.md) 「정답이 모델 입력에 들어간다」. 환율 1,400원 고정.

| | Baseline A | Baseline B | Proposed |
|---|---|---|---|
| 건당 비용 | **0.33원** ($0.000239) | **1.20원** ($0.000855) | **3.03원** ($0.002165) |
| 입력 토큰 (평균) | 1,023 | 4,665 | 8,968 |
| 출력 토큰 (평균) | 143 | 259 | 1,366 |
| p50 지연 | **2.6초** | **4.2초** | 20.0초 |
| p95 지연 | **3.3초** | **5.5초** | 32.2초 |

### ★ Baseline 빈칸이 채워졌다 (2026-09-07)

**2026-08-17 도메인 교체로 이전 측정이 전부 무효가 됐고**, 그 뒤 Proposed 만
재측정돼 A·B 가 `[미확보]`로 남아 있었다. **새로 돌린 게 아니라** 2026-09-06
judge v3 재기준선이 세 군을 다 돌려 놨는데 그 산출물에서 비용·지연을 안 꺼낸
것이었다. 행마다 `cost_usd`·`latency_ms`·토큰이 들어 있다.

### ★ 같은 실행의 judge 결과를 나란히 놔야 한다

`[실측 2026-09-07]` 위 표만 보면 Proposed 는 A 보다 **9.1배 비싸고 7.7배 느리다.**
그 값으로 무엇을 샀는지 같이 봐야 한다.

| | Baseline A | Baseline B | Proposed |
|---|---|---|---|
| judge pass | 0.0% (0/216) | **46.8% (101/216)** | 11.6% (25/216) |
| 평균 총점 | 5.00 | **14.71** | 10.15 |
| 유효 인용이 있는 행 | 0 | 216 | 216 |
| 지어낸 인용 | 0 | 0 | 0 |

★**Proposed 가 이기지 않는다. B 가 이긴다** — 더 싸고(2.5배) 더 빠른데(4.8배)
judge 점수가 더 높다. 2026-09-06 재기준선에서 나온 결과이고(`5bf0a31`) **감추지 않는다.**

**그러면 무엇으로 Proposed 를 주장하나.** judge 는 답변 품질을 재지 *무엇을 자동으로
실행하지 않았는지*를 안 잰다. A 는 인용이 아예 0행이라 근거 없는 답을 하고, B 는
인용을 붙이지만 승인 경계·기권·Action 제안이 없다. 그 셋은 [metrics.md](metrics.md)의
네 지표와 방어 지표가 재는 것이지 judge 총점이 재는 것이 아니다.

### 세 군을 기권 라벨로 재 봤다 (2026-09-07)

`[실측]` 골든셋의 `expected_next_action` 이 곧 "미뤄야 할 때"의 라벨이다
(`wait_for_approval` 15건 × 3회 = 45, `respond` 40건 × 3회 = 120).

| | Baseline A | Baseline B | Proposed |
|---|---|---|---|
| **적절한 기권율** (미뤄야 할 45건 중 실제로 미룸) | 46.7% (21/45) | 46.7% (21/45) | **60.0% (27/45)** |
| **과잉 기권율** (답해야 할 120건 중 미룸) | **0.0%** (0/120) | **0.0%** (0/120) | **30.0%** (36/120) |
| 기권할 때 근거를 붙였나 | **0%** (0/21) | 100% (21/21) | 100% (27/27) |

★**미뤄야 할 것을 6건 더 잡는 대신, 답해도 될 120건 중 36건을 붙든다.**
그런데 그 36행을 열어 보니 **고유 12건 × 3회**이고 **12건 전부 `degraded`** 였다.
그중 8건은 Return & Refund 가 **Mock** 이라 승인 제안만 내게 만들어져 있어서다.
**과잉 기권 30% 는 대부분 Mock 을 재고 있다** → [metrics.md](metrics.md).
진짜로 따져 볼 것은 실패 코드가 붙은 4건뿐이다.

★**A 는 기권할 때 근거를 한 번도 안 붙인다**(0/21). 미루기는 하는데 왜 미루는지
대지 못한다. 승인자가 받아 볼 것이 없다는 뜻이다.

### ★ A 와 B 는 같은 판단을 내린다

`[실측 2026-09-07]` A 와 B 의 `next_action` 이 **72/72 완전히 같다.** `intent` 도
72/72 같다. 그런데 `answer` 는 **0/72** 만 같다 — 다른 실행이고 문장은 전부 다르다.

**RAG 근거를 줘도 무엇을 할지에 대한 판단은 한 건도 안 바뀐다.** 바뀌는 것은
답변 문장과 인용이 붙느냐뿐이다. B 의 judge 점수가 A 보다 높은 것(14.71 vs 5.00)은
**같은 결정에 더 나은 문장과 근거를 붙였기 때문**이지 더 잘 판단해서가 아니다.

`[미확보]` 세 군 다 `gpt-4o-mini` · `temperature=0` · `seed=7` 이라 분류가 같게
나왔을 수 있다. 다른 모델·다른 seed 로도 같은지는 안 봤다.

### ★ Proposed 의 통과는 거의 전부 "답을 안 낸 건" 이다

`[실측 2026-09-07]` Mock 경고가 붙은 60행을 빼고 다시 세면 **Proposed 가 더 나빠진다.**

| | 전체 216행 | Mock 행 제외 156행 | Mock 행 60행 |
|---|---|---|---|
| Proposed pass | 11.6% (25) | **1.3% (2)** | **38.3% (23)** |
| Baseline B pass | 46.8% (101) | **46.8% (73)** | — |

**Proposed 의 통과 25건 중 23건(92%)이 Mock 행에서 나온다.** 그 23건은 전부
`next_action = wait_for_approval` 이고 **`answer` 가 `null`** 이다. 축 평균은
`correctness 4.00 · policy_grounding 4.00 · next_action 4.00 · safety 3.91` 이다.

★**채점자가 답이 없는 건에 `correctness` 만점을 준다.** 다음 행동이 기대와 맞고
인용이 유효하면 본문이 없어도 4점이다. [D-010](../decisions/D-010-deferral-scoring.md)
은 "채점자는 답변 본문이 없으니 `correctness` 를 낮게 준다"를 전제로 세워졌는데,
**실측은 정반대다.** 이로써 그 전제는 세 번째로 반증됐다(통과율·근거·이 축).

★**그래서 지금 헤드라인은 이렇게 읽어야 한다** — 실제로 답을 낸 156행에서
Proposed 는 1.3%, B 는 46.8% 다. **답하는 일에서는 아직 단순 RAG 에 크게 진다.**
감추지 않는다.

`[미확보]` 답이 없는 건에 만점을 주는 것이 루브릭 의도인지 채점자의 해석인지
안 가렸다. `judge_v3.txt` 는 `correctness` 에 "답변 내용이 사실로 맞는가" 만 적어
두고 **답이 없을 때를 안 정한다.** 정하지 않은 것을 채점자가 메우고 있다.

★judge 총점 자체도 조심해서 읽는다. `policy_grounding` 이 독립 읽기 둘과 3점 넘게
어긋나 있고 위쪽에 쏠려 있다 → [judge-second-opinion.md](judge-second-opinion.md).
B 와 Proposed 의 grounding 은 3.48 · 3.32 로 거의 같아서, 이 축이 부풀어 있다면
두 군의 격차는 다른 네 축에서 온 것이다.

그래서 **"A-COP이 단순 LLM보다 낫다"를 지금은 수치로 말할 수 없다.** 비교군이 없으면 평가 설계 자체가 반쪽이다.

**중간발표 전에 재측정해야 한다.** 명령은 [protocol.md](protocol.md).

**지연은 여전히 약점이다.** 상세는 [../business/infrastructure-cost.md](../business/infrastructure-cost.md).

## 미확보

| 항목 | 필요한 것 |
|---|---|
| 3B 자체호스팅 모델의 정확도 | 골든셋 72건 재평가 |
| 4-bit 양자화 후 정확도 | AWQ/GPTQ 적용 후 재평가 |
| 사람 라벨 일치도 | 20건 사람 라벨 필요 |

## 인접 영역

- [../product/personas.md](../product/personas.md) — 지표가 누구의 개선을 증명하는가
- [../business/unit-economics.md](../business/unit-economics.md) — 오류율이 돈으로 환산된다
- [`cs/quality/eval-harness.md`](../../final_project_cs/wiki/quality/eval-harness.md) — 실행 방법
- [`sample/wiki/quality/`](../../final_project_sample/wiki/quality/index.md) — sample 에도 `eval/` 이 있다. 계약 테스트가 주력이다
- [dod28-rerun.md](dod28-rerun.md) — **DoD-28 을 다시 재야 하는 이유.** 0% 는 근거를 안 준 결과다

- [model-selection.md](model-selection.md) — **응답 모델 후보를 고르는 기준.** 지금까지 이게 없었다

- [classification-accuracy.md](classification-accuracy.md) — **분류 정확도.** intent 100%인데 next_action 52.8%

