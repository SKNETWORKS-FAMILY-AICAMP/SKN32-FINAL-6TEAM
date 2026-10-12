# S-STATSFIX 통계 모듈 결함 수정 리포트

## 1. 원인과 수정

기존 McNemar 구현은 연속성 보정 카이제곱 통계량 `(abs(b-c)-1)^2/(b+c)`를 그대로 `p_value`로 출력했습니다. 이제 통계량을 별도로 출력하고 `scipy.stats.chi2.sf(statistic, df=1)`로 p-value를 계산합니다. `p_value`가 0~1인지 단언하며, `config/guardrails.yaml`의 `evaluation.mcnemar_exact_threshold`를 읽어 discordant 합이 25 미만이면 `scipy.stats.binomtest` exact 검정을 사용하고 방법을 출력합니다.

기존 bootstrap은 `row["score"]`와 `row["arm"]`을 기대했지만 `make_pairs`는 성공 여부만 저장했습니다. 이제 쌍 파일에 `x_success/y_success`, `x_score/y_score`, `x_grounding/y_grounding`을 저장합니다. 입력 파일의 실제 arm 이름을 자동 추론하므로 Proposed-A, Proposed-B, B-A를 모두 지원합니다. 기본 metric은 실제 존재하는 `score`이고 `--metric`으로 선택할 수 있으며, seed 기본값은 7, bootstrap 기본 반복은 10,000회입니다. 출력은 `mean diff=값 [CI_low, CI_high]`이고 CI가 0을 포함하면 `유의하지 않다 (CI가 0을 포함)`을 출력합니다.

재채점 원본 `eval/reports/rescored_*.jsonl`은 변경하지 않았습니다.

## 2. 자체 검증

- `b=0, c=40`: statistic `38.025`, p-value `<1e-8`, p-value 0~1
- `b=3, c=5`: exact 분기, p-value 0~1
- bootstrap 차이 0: CI가 0을 포함
- bootstrap 차이 +1: mean diff `1.0`, CI가 0을 포함하지 않음

## 3. 세 쌍 결과

| 비교 | Bootstrap (score) | McNemar |
|---|---|---|
| Proposed-A | mean diff=3.994444 [3.494444, 4.500000], 유의하다 | b=0, c=40, statistic=38.025000, chi-square continuity-corrected, p=6.98439306152e-10 |
| Proposed-B | mean diff=1.588889 [0.961111, 2.211111], 유의하다 | b=6, c=40, statistic=23.673913, chi-square continuity-corrected, p=1.14119009476e-06 |
| B-A | mean diff=2.405556 [2.011111, 2.822222], 유의하다 | b=0, c=6, statistic=6.000000, exact binomial, p=0.03125 |

## 4. 완료 조건 실제 출력 원문

```text
{"output": "eval/reports/pairs_pb.jsonl", "rows": 180, "x": "Proposed", "y": "B"}
paired_n=180; Proposed-B mean diff=1.588889 [0.961111, 2.211111]; 유의하다
discordant_b=6; discordant_c=40; discordant_total=46; statistic=23.673913; method=chi-square continuity-corrected; p_value=1.14119009476e-06
.......                                                                  [100%]
7 passed, 1 warning in 2.97s
```

pytest의 경고는 `.pytest_cache` 생성 권한 경고이며 테스트 실패가 아닙니다.
