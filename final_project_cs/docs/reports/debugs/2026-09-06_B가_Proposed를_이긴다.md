# 현행 도메인에서 B(고정 워크플로)가 Proposed 를 이긴다 — 모든 축에서

## 미해결

- 발견: 2026-09-06, judge 재기준선(D-014) 도중
- 판정: **실재하는 관측. 원인 미확정.**
- 위험도: **높음** — 이 제품의 핵심 주장("Case lifecycle + Context Broker +
  Team 구성이 낫다")을 정면으로 부정하는 수치다. 다만 **같은 모양이 과거에
  다섯 번 나왔고 그때마다 하네스 결함이었다**(아래 §이력).

## 실측

현행 쇼핑몰 도메인, 각 군 216행(72 case × 3회). **채점자를 바꿔도 같다.**

```
judge-v1   A pass  0.0%  ·  B 98.6%  ·  Proposed 27.8%
judge-v3   A pass  0.0%  ·  B 46.8%  ·  Proposed 11.6%
```

judge-v3 축별 평균:

| 축 | B | Proposed | 차이 |
|---|---:|---:|---:|
| correctness | 3.34 | 1.85 | **−1.49** |
| policy_grounding | 3.48 | 3.32 | −0.16 |
| next_action | 2.69 | 1.76 | −0.93 |
| safety | 3.30 | 2.32 | −0.98 |
| personalization | 1.91 | 0.80 | **−1.11** |

★**grounding 만 거의 동률이다.** 나머지는 고르게 진다.

## "기권을 벌한다" 는 설명은 맞지 않는다

Proposed 프롬프트는 `Preserve any escalation or degraded-context outcome;
do not claim a successful resolution when the Team did not provide one` 이다.
Team 이 기권하면 기권을 지켜야 하므로 **기권이 벌 받는 것 아닌가**를 먼저 봤다.

```
두 군이 낸 next_action
  B         respond 102 · call_tool 45 · wait_for_input 39 · wait_for_approval 21 · escalate 6 · handoff 3
  Proposed  respond 114 · wait_for_approval 60 · escalate 42

Proposed 가 기권한 건 102        total  B 14.28 / P  8.24     pass  B 48.0% / P 22.5%
Proposed 가 기권 안 한 건 114    total  B 15.10 / P 11.86     pass  B 45.6% / P  1.8%
```

**기권하지 않은 114건에서도 진다.** 그러므로 기권 페널티가 주된 설명이 아니다.
(기권 안 한 쪽의 `pass` 가 1.8% 로 더 낮은 것은 `pass` 규칙이
`correctness>=3` 을 요구하는데 Proposed 가 그 문턱을 거의 못 넘기 때문이다.)

## B 는 순진한 기준선이 아니다

```
baseline_b_v1.txt
  "fixed support workflow and policy-retrieval response generator.
   ... use only the retrieved policy evidence supplied in INPUT_RECORD"
```

**B 도 RAG 근거를 받는다.** 그래서 grounding 이 거의 동률인 것이 설명된다 —
옛 도메인에서 Proposed 3.98 대 B 2.22 로 벌어졌던 것은 **B 가 인용을 늘 달지
못했기** 때문이지 근거의 질 차이가 아니었다(그 축이 상수였다는 것이 D-014 다).

## ★같은 모양이 다섯 번 있었고 매번 하네스 결함이었다

`docs/evidence/DoD-15_AB_Proposed_60x3_holdout.md` 의 실패 이력:

| 회차 | 관측 | 실제 원인 |
|---|---|---|
| 3 | A 35/180 · B 0/180 | judge 가 **환각 인용에 점수** |
| 4 | Proposed 0/180 | **실제 시스템 미실행** — Team 이 하드코딩 문구를 씀 |
| 5 | **B 115/180 · Proposed 0/180** | `next_action` 이 **어휘 일치**를 쟀다 — 계약을 지킨 쪽이 벌점 |

**5회차가 지금과 같은 모양이다.** 그때는 golden 이 자유형 라벨을 기대하는데
Proposed 는 계약 Enum 을 내서 생긴 일이었다(그 뒤 데이터셋이 Enum 어휘로
재작성돼 닫혔다 — `2026-08-13_1800_next_action_지표가_어휘일치를_잰다.md`).

★**그래서 "Proposed 가 실제로 나쁘다" 고 단정하지 않는다.** 이 저장소에서
이 모양은 다섯 번 중 다섯 번 **재는 쪽**이 틀렸다.

## 다음에 확인할 것 (순서대로)

1. **후보 답변을 눈으로 본다.** 같은 case 에서 B 와 Proposed 의 `answer` 를
   나란히 놓고 읽는다. Proposed 답변이 짧고 정형적이면 **LLM 채점자의
   장황함 선호**가 원인일 수 있다 — 그건 제품 결함이 아니라 지표 결함이다.
2. **`correctness` 가 왜 1.85 인지** 사례로 확인한다. 사실이 틀린 것인지,
   "답을 안 준 것"을 틀렸다고 본 것인지 가른다.
3. Proposed 가 **실제 Team 을 도는지** 다시 확인한다(4회차 재발 여부).
   `team_result` 는 216/216 채워져 있으나 내용이 유효한지는 별개다.
4. 위 셋이 전부 무해하면 **그때 비로소 제품 쪽 문제로 본다.**

## 지금 하지 않은 것

- 판정하지 않았다. `CLAUDE.md` 상태표와 DoD-15 evidence 를 고치지 않았다 —
  원인을 모르는 수치로 결론을 바꾸면 **오진 위에 수정을 쌓는 것**이다.
- 재기준선(D-014)과 **묶지 않았다.** 그 결정은 "채점자를 바꿔도 순위가
  보존된다" 였고, 이 관측은 **채점자와 무관하게** 양쪽에 다 있다.
