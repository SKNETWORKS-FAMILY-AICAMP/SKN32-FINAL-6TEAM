---
type: decision
title: judge 를 v1 에서 v3 로 바꾸고 현행 도메인 산출물을 다시 매긴다
description: v1 의 policy_grounding 은 분산 0 인 상수였다. 군 순위가 보존되는 것을 확인하고 갈아탔다
status: draft
impl_scope: cs — 평가 하네스는 cs 소유다
tags: [evaluation, testing]
domain: neutral
---

# D-014 judge 를 v1 에서 v3 로 바꾸고 현행 도메인 산출물을 다시 매긴다

`[실측]` **2026-09-06 결정·시행.** 팀 승인을 받은 것으로 진행했다.

## 문제

`judge_v1.txt` 의 `policy_grounding` 축이 **아무것도 재고 있지 않았다.**

```
holdout 72행    policy_grounding = 4     (전부)
golden  216행   policy_grounding = 4     (214/216, 99%)
다른 네 축은 전부 변한다 — correctness 1~4 · next_action 0~4 · safety 2~4
```

원인은 프롬프트가 **한쪽만 강제**한 것이다.

```
인용이 없으면   MUST be 0                                    ← 강한 규칙, 지켜진다
인용이 있으면   score from the supplied policy-grounded record ← 답변이 그 근거를
                                                               쓰는지 묻지 않는다
```

그래서 이 축은 **0~4 눈금을 쓴 이진 플래그**였다. 대표 수치로 인용돼 온
"grounding 0.00 / 2.22 / 3.98" 은 근거의 질이 아니라 **「인용이 붙었나」** 였다.

DoD-15 에 당장 걸렸다 — 상수 축의 kappa 는 1.0 아니면 0.0 두 값만 나온다.
사람이 24건 중 하나라도 4 가 아닌 점수를 주면 즉시 0.0 이 된다.

근거: `final_project_cs/wiki/records/reports/debugs/2026-09-06_judge의_policy_grounding이_상수다.md`

## 무엇을 재고 결정했나

`judge_v1` 에서 **grounding 문장 하나만** 바꾼 판 둘을 만들어 같은 72건
(golden 현행 도메인, 답변 고정)을 세 채점자로 매겼다.

| | grounding 변별 | **안 바꾼 네 축 이동** |
|---|---|---|
| v1 | 2종 · 최빈 99% | — |
| v2 (금지 표현) | 5종 · 51% | **1.12** |
| **v3 (중립 어조)** | **4종 · 58%** | **0.63** |

★**한 축만 따로는 못 고친다.** grounding 만 건드렸는데 나머지 네 축이 같이
움직인다. 어조를 낮추면 절반이 되지만 0 은 아니다. 그래서 이건 프롬프트 한 줄
교체가 아니라 **재기준선**이다.

### 갈아탈 수 있다고 판단한 근거 — 순위 보존

★**v1 점수와 v3 점수를 직접 비교하지 않는다.** 채점자를 바꾸면 모든 점수가 같이
움직이므로 그 비교는 뜻이 없다. 물어야 할 것은 **같은 채점자 안에서 군 사이의
결론이 보존되는가** 다.

```
judge-v1   A 0.0%  ·  B 98.6%  ·  Proposed 27.8%     → B > Proposed > A
judge-v3   A 0.0%  ·  B 46.8%  ·  Proposed 11.6%     → B > Proposed > A
```

**순위가 보존됐다.** 그래서 갈아타도 군 사이의 결론이 흔들리지 않는다.
뒤집혔다면 결론 자체가 채점자에 달려 있었다는 뜻이라 갈아타기 전에 원인을
찾아야 했다.

## 결정

1. **`judge_v3.txt` 를 기본 채점자로 한다.** `eval/rescore.py` ·
   `eval/runners/common.py` 의 기본값을 바꿨다.
2. **현행 도메인 산출물 720행을 v3 로 다시 매겼다** — A·B·Proposed 각 216 +
   holdout 72. 옛 v1 산출물은 **지우지 않고** 그대로 둔다(무엇으로 매겼는지가
   기록이다).
3. `JUDGE_PROMPT_VERSION` 을 **프롬프트 파일에서 읽게** 했다. 손으로 적혀 있던
   탓에 실제로 v3 파일을 읽으면서 `judge-v1` 이라고 적을 뻔했다.
4. **옛 도메인 산출물(2026-08-17 무효화분)은 다시 매기지 않는다.** 이미 다른
   이유로 못 쓰는 값이다.

## 효과

```
holdout grounding   1종(100%)  →  3종(최빈 49%)   ← DoD-15 가 이 축을 잴 수 있게 됐다
golden  grounding   2종( 99%)  →  4종(최빈 60%)
```

## ★이 결정에 포함되지 않은 것

재기준선을 하다 **별개의 큰 것**이 드러났다 — **B(고정 워크플로 + 정책 검색)가
Proposed 를 이긴다.** 두 채점자 모두에서, 그리고 grounding 을 뺀 **모든 축에서**
그렇다. 이건 채점자 교체와 무관하게 존재하던 사실이고, 이 결정으로 판정하지
않는다. 별도 리포트로 남겼다 —
`final_project_cs/wiki/records/reports/debugs/2026-09-06_B가_Proposed를_이긴다.md`

## 되돌리려면

`eval/rescore.py` · `eval/runners/common.py` 의 경로를 `judge_v1.txt` 로 되돌리면
된다. v1 산출물이 그대로 있으므로 비교 기준도 남아 있다.
