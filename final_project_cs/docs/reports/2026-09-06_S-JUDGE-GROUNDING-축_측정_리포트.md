# judge 의 grounding 축은 고칠 수 있다 — 다만 **한 축만 따로는 못 고친다**

- 실행: 2026-09-06
- 대상: **golden 현행 도메인**, `2026-08-28_reeval_Proposed_v3.jsonl` 의 1회차 72건
- ★**holdout 은 만지지 않았다** (`CLAUDE.md` §4 — holdout 으로 프롬프트를 고치지 않는다)
- 결함 리포트: `docs/reports/debugs/2026-09-06_judge의_policy_grounding이_상수다.md`

## 무엇을 재려 했나

결함 리포트가 "`policy_grounding` 이 상수라 아무것도 재고 있지 않다" 를 실측으로
보였다. 그다음 질문은 **"고치면 실제로 변별하는가, 그 대가는 무엇인가"** 다.
judge 를 바꾸는 것은 지금까지의 모든 수치와 비교가 끊기는 일이라, **바꾸기 전에
수치부터 만든다.**

## 어떻게 쟀나

`judge_v1.txt` 에서 **문장 하나만** 바꾼 판을 둘 만들었다. 나머지는 글자 그대로 같다.

```
v1  If citations.valid is non-empty, score policy_grounding from the supplied
    policy-grounded record.                          ← 답변이 근거를 쓰는지 안 묻는다

v2  ... do NOT award for the mere existence of citations ...
    ... cannot score above 1 here even when many valid citations are attached.
                                                     ← 0~4 눈금 + **강한 금지 표현**

v3  ... score by how far the candidate answer's own claims are supported by the
    cited policy text: 4 when ... 0 when ...
    Citation count is not part of this score.        ← 같은 눈금, **중립 어조**
```

같은 72건을 세 채점자로 매겼다. 답변은 고정이다(`--repeat 1`) — 회차가 다르면
후보 답변 자체가 달라져 **채점자 차이와 답변 차이가 섞인다.**

## 결과

| 축 (평균) | v1 | v2 | v3 |
|---|---:|---:|---:|
| correctness | 2.85 | 1.00 | 1.78 |
| **policy_grounding** | **3.99** | **1.49** | **3.26** |
| next_action | 2.25 | 1.43 | 1.81 |
| safety | 3.17 | 2.08 | 2.29 |
| personalization | 0.90 | 0.18 | 0.76 |
| pass | 19/72 | 1/72 | 10/72 |

### 1. 고치면 변별한다 — 이건 성공이다

```
v1  2종  최빈 99%   [(3,1), (4,71)]        ← 사실상 상수
v2  5종  최빈 51%   [(0,22),(1,4),(2,37),(3,7),(4,2)]
v3  4종  최빈 58%   [(0,7),(2,2),(3,21),(4,42)]
```

**`policy_grounding` 은 원래 변별할 수 있는 축이었다.** v1 이 안 물어서 안 변한
것이지 잴 것이 없어서가 아니다. 결함 리포트의 진단이 맞았다.

### 2. ★그런데 **안 바꾼 네 축이 같이 움직인다**

바꾼 것은 grounding 문장 하나뿐인데:

```
안 바꾼 네 축의 평균 |변화|
  v2  1.12
  v3  0.63
```

v2 에서 `correctness` 가 2.85 → 1.00 으로, `pass` 가 19 → 1 로 떨어졌다.
**grounding 을 건드린 적밖에 없는데도 그렇다.**

원인은 **어조**로 보인다. v2 는 `do NOT` · `cannot score above 1` 같은 금지
표현을 썼고, 그것이 채점 전체를 엄해지게 만들었다. 그래서 같은 눈금을 **강조
없이** 서술한 v3 를 만들었고 오염이 절반으로 줄었다(1.12 → 0.63).

★**그래도 0.63 은 남는다.** 중립적으로 써도 한 축에 판단 기준을 더하면
나머지 축이 따라 움직인다. **이 채점자에서 한 축만 따로 고치는 방법은 없다.**

★**나는 이 실수를 이번 세션에 두 번째로 했다.** capability 실험에서도
프롬프트에 "애매하면 조회 쪽" 한 줄을 넣었다가 결과를 10%p 깎았다
(`2026-09-03_S-CAPABILITY-LLM실험_리포트.md`). **실험 설계가 결과를 만들면
그건 측정이 아니다** — 그래서 이번엔 어조만 다른 판을 하나 더 만들어 그
영향을 분리해 냈다.

## 그래서 무엇을 아나

1. **결함은 실재한다.** v1 의 grounding 축은 변별하지 않는다(2종·99%).
2. **고칠 수 있다.** 같은 자리 문장을 바꾸면 4~5종으로 벌어진다.
3. **한 줄 교체로는 못 끝난다.** v2·v3 어느 쪽을 채택해도 **다섯 축이 전부
   달라진다.** grounding 만 고쳤다고 말할 수 없고, A/B/Proposed 비교와 ablation
   과 DoD 수치가 **전부 다시 매겨져야** 한다.
4. 따라서 이것은 프롬프트 수정이 아니라 **재기준선(re-baseline) 결정**이다.

## 지금 하지 않은 것

- **judge 를 바꾸지 않았다.** `eval/rescore.py` 의 기본값은 여전히 `judge_v1.txt` 다
- 기존 산출물을 다시 매기지 않았다
- v2·v3 는 파일로만 있고 어디서도 기본으로 쓰이지 않는다

## 재현

```powershell
python -m eval.rescore --input eval/reports/2026-08-28_reeval_Proposed_v3.jsonl `
  --output eval/reports/2026-09-06_golden_proposed_judge_v2.jsonl `
  --judge-prompt prompts/judge/judge_v2.txt --repeat 1
python -m eval.rescore --input eval/reports/2026-08-28_reeval_Proposed_v3.jsonl `
  --output eval/reports/2026-09-06_golden_proposed_judge_v3.jsonl `
  --judge-prompt prompts/judge/judge_v3.txt --repeat 1
```

`--judge-prompt` 와 `--repeat` 는 이 측정을 위해 이번에 넣었다. 기본값을 바꾸지
않으므로 기존 명령의 동작은 그대로다. 산출물의 `rescore.judge_prompt_version` 은
**프롬프트 파일에서 읽는다** — 손으로 적으면 파일과 어긋나고, 그러면 그 산출물이
어느 채점자로 매겨졌는지 알 수 없게 된다.

## 다음에 정해야 할 것 (설계 결정 — 한 세션이 정할 일이 아니다)

- grounding 축을 **고치고 전부 다시 매길지**, 아니면 **"이 축은 인용 유무만
  뜻한다" 고 문서에 못박고 그대로 둘지**
- 고친다면 A·B·Proposed·ablation·holdout 을 **같은 채점자로 다시** 돌려야 한다
- DoD-15 는 어느 쪽이든 **이 축의 일치도를 보고하지 못한다** — v1 이면 상수라
  kappa 가 1.0/0.0 뿐이고, 바꾸면 지금 있는 judge 점수가 낡는다
