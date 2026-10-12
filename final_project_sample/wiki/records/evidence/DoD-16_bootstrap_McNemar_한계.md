# DoD-16 — bootstrap 95% CI · McNemar · 한계가 report 에 포함된다

- v5 §20 항목 16 / 검증 방법: stats test
- 실행: 2026-08-13 · 재채점본 기준
- 판정: 통과

## 재현 명령

```powershell
python -m eval.stats.make_pairs --input eval/reports/rescored_proposed.jsonl eval/reports/rescored_baseline_b.jsonl --output eval/reports/pairs_PB.jsonl
python -m eval.stats.mcnemar   --input eval/reports/pairs_PB.jsonl
python -m eval.stats.bootstrap --input eval/reports/pairs_PB.jsonl --n 10000
```

## 실제 출력

```
--- Proposed vs B ---
discordant_b=6; discordant_c=40; discordant_total=46;
statistic=23.673913; method=chi-square continuity-corrected; p_value=1.14119009476e-06
paired_n=180; Proposed-B mean diff=1.588889 [0.961111, 2.211111]; 유의하다

--- Proposed vs A ---
discordant_b=0; discordant_c=40; discordant_total=40;
statistic=38.025000; method=chi-square continuity-corrected; p_value=6.98439306152e-10
paired_n=180; Proposed-A mean diff=3.994444 [3.494444, 4.500000]; 유의하다

--- B vs A ---
discordant_b=0; discordant_c=6; discordant_total=6;
statistic=6.000000; method=exact binomial; p_value=0.03125
paired_n=180; B-A mean diff=2.405556 [2.011111, 2.822222]; 유의하다
```

## 판정 근거

| 요구 (v5 §15-5) | 결과 |
|---|---|
| paired bootstrap **10,000회** 95% percentile CI | **통과** — `--n 10000`, seed 고정 |
| McNemar (discordant pair) | **통과** — b/c 셀 수를 함께 보고 |
| ★셀 수 **< 25 면 exact** | **통과** — B vs A 는 discordant 6 → `exact binomial` 로 분기 |
| 평균만 보고하지 않음 | **통과** — `mean diff [CI_low, CI_high]` 형식 |
| CI 가 0 을 걸치면 "유의하지 않다" | **통과** — 판정 문구를 출력에 포함 (세 쌍 모두 0 을 걸치지 않아 "유의하다") |
| p-value 가 0~1 | **통과** |

★비교 지표는 `policy_grounding` 이다 (Proposed-A 평균차 3.994 가 grounding 3.98−0.00 과 일치).

## ★이 항목은 잘못된 수치를 낼 뻔했다

수정 전 McNemar 출력:
```
p_value=38.025000
```

**카이제곱 통계량을 p_value 로 출력**하고 있었다. p 는 0~1 인데 38 이 나왔다.
`(|0-40|-1)^2/40 = 38.025` — 통계량이다. 실제 p 는 `6.98e-10` 이다.
bootstrap 은 `KeyError: 'score'` 로 죽어 있었다.

★**심사 리포트에 실렸다면 즉시 걸렸을 값이다.**
지금은 알려진 값 검증(b=0,c=40 → p<1e-8 / 합 8 → exact / 차이 0 → CI 가 0 포함)이
`eval/tests/` 에 있고, **p_value 가 1 을 넘지 않는지 단언**한다.

## ★한계 (v5 §15-8) — 이 수치가 증명하지 않는 것

- **60건 × 3회 = 180 paired 관측**이다. 통제된 조건에서의 **방향성과 불확실성**만 말한다
- **모집단 일반화를 증명하지 않는다.** golden 60건은 이 프로젝트가 만든 가상 SaaS(Nimbus)
  시나리오이며 실제 고객 문의 분포가 아니다
- **장기 drift·실제 결제 손실률·운영 SLA 를 증명하지 않는다**
- **모든 도메인에서의 우월성을 증명하지 않는다** — 단일 도메인 단일 코퍼스다
- holdout 20건은 과적합 감시용이며 **통계적 대표성을 보장하지 않는다.**
  이번 평가에서 holdout 은 **실행하지 않았다**
- judge 는 LLM 이다. **사람 라벨 20건과의 agreement 를 측정하지 않았다**(v5 §15-4 요구사항 미충족)
- ★**A 군의 낮은 점수에는 rubric 설계 영향이 있다.** `pass_rule` 이
  `safety>=3 and correctness>=3 and total>=16` 인데 grounding 이 0 이면
  나머지 4개가 만점(4×4=16)이어야 겨우 통과한다.
  **RAG 없는 군은 구조적으로 통과가 거의 불가능하다** — "압도적 우위" 로 읽으면 과장이다
