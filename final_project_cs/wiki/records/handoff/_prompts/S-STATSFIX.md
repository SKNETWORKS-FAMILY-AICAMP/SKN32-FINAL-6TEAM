# 구현 지시 — 통계 모듈 결함 2건 (p-value 가 38 이다)

## 0. 결함

재채점 결과로 통계를 돌린 실측:

```
=== McNemar ===
discordant_b=0; discordant_c=40; discordant_total=40;
method=chi-square continuity-corrected; p_value=38.025000

=== bootstrap ===
KeyError: 'score'   (eval/stats/bootstrap.py:10)
```

### 결함 1 (★심각) — 카이제곱 **통계량**을 p_value 로 출력한다

`p_value=38.025` 는 **불가능하다.** p 는 0~1 이다.

`(|b-c|-1)^2 / (b+c) = (|0-40|-1)^2 / 40 = 39^2/40 = 38.025` —
이건 **검정통계량**이지 p-value 가 아니다. 실제 p 는 `chi2.sf(38.025, df=1) ≈ 7e-10` 이다.

★이 수치가 심사 리포트에 실렸다면 **즉시 걸렸을 것**이다.

### 결함 2 — bootstrap 이 `pairs.jsonl` 을 못 읽는다

`eval/stats/bootstrap.py:10` 이 `row["score"]` 를 찾는데
`make_pairs` 가 만든 행에 그 키가 없다. 두 모듈의 스키마가 어긋나 있다.

## 1. 현재 데이터 (이걸로 검증하라)

```
eval/reports/rescored_baseline_a.jsonl    180행  성공  0/180  grounding 0.00  총점중앙  9
eval/reports/rescored_baseline_b.jsonl    180행  성공  6/180  grounding 2.22  총점중앙 12
eval/reports/rescored_proposed.jsonl      180행  성공 40/180  grounding 3.98  총점중앙 13
eval/reports/pairs.jsonl                  180행  (x=Proposed, y=A)
```

## 2. 소유 범위

```
eval/stats/**
eval/tests/**
wiki/records/reports/ , wiki/records/history/
```
★금지: `app/**`, `tests/**`, `knowledge/**`, `config/**`, `scripts/**`,
`eval/runners/**`, `eval/reports/rescored_*.jsonl`(★결과 원본),
`wiki/records/handoff/**`, `wiki/records/evidence/**`, `wiki/records/submission/**`.

## 3. 고칠 것

### 3-1. McNemar 가 **진짜 p-value** 를 낸다

- 통계량과 p-value 를 **각각** 출력한다 (`statistic=`, `p_value=`)
- ★`p_value` 는 반드시 **0 ≤ p ≤ 1**
- 연속성 보정 카이제곱: `scipy.stats.chi2.sf(statistic, df=1)`
- ★**discordant 셀 합이 25 미만이면 exact**(`scipy.stats.binomtest(b, b+c, 0.5)`)
  — v5 §15-5 가 정한 규칙이다. `config/guardrails.yaml` 의
  `evaluation.mcnemar_exact_threshold: 25` 를 읽어라
- ★어느 방법을 썼는지 출력에 남긴다

### 3-2. bootstrap 이 `pairs.jsonl` 스키마를 읽는다

`make_pairs` 출력 형식을 **직접 확인**하고 거기에 맞춘다.
`--metric` 으로 지표를 고를 수 있게 하되 **기본값이 실제 존재하는 키**여야 한다.

- paired bootstrap **10,000회**, 95% percentile CI (`config/guardrails.yaml`)
- seed 고정
- ★출력 형식: `mean diff [CI_low, CI_high]`
- ★**CI 가 0 을 걸치면 "유의하지 않다"** 를 출력에 명시한다

### 3-3. 세 군을 모두 비교할 수 있게 한다

Proposed vs A, Proposed vs B, B vs A — 세 쌍 전부.
`make_pairs` 가 `--x`/`--y` 로 쌍을 고르게 되어 있으니 그대로 쓰되,
**bootstrap·mcnemar 가 그 출력을 받아야 한다.**

## 4. ★자체 검증 — 알려진 값으로 확인하라

`eval/tests/` 에 추가:

1. **b=0, c=40** 을 넣으면 `statistic≈38.025`, `p_value < 1e-8` (0~1 범위 안)
2. **b=3, c=5** (합 8 < 25) → **exact 로 분기**하고 p 가 0~1
3. bootstrap 에 **차이가 0인 입력** → CI 가 0 을 포함하고
   "유의하지 않다" 가 출력된다
4. bootstrap 에 **모두 +1 인 입력** → mean diff 1.0, CI 가 0 을 포함하지 않는다

★**p_value 가 1 을 넘는 경우가 없는지 검사하는 단언을 넣어라.**

## 5. 완료 조건

```powershell
python -m eval.stats.make_pairs --input eval/reports/rescored_proposed.jsonl eval/reports/rescored_baseline_b.jsonl --output eval/reports/pairs_pb.jsonl
python -m eval.stats.bootstrap --input eval/reports/pairs_pb.jsonl --n 10000
python -m eval.stats.mcnemar --input eval/reports/pairs_pb.jsonl
python -m pytest eval/tests -q
```

기대: bootstrap 이 죽지 않고 `mean diff [lo, hi]` 를 내며,
mcnemar 의 `p_value` 가 **0~1 범위**. eval 테스트 통과.

★LLM 호출은 없다. 이 작업은 **당신 환경에서 전부 실행 가능하다.** 반드시 돌려라.

## 6. 리포트

`wiki/records/reports/2026-08-13_S-STATSFIX_리포트.md` — 두 결함의 원인,
§5 명령의 **실제 출력 원문**, 세 쌍(Proposed-A, Proposed-B, B-A)의 결과.

## 7. 하지 말 것
- ❌ 통계량을 p_value 로 출력
- ❌ exact 분기 생략
- ❌ CI 가 0 을 걸치는데 "유의하다" 로 쓰기
- ❌ `rescored_*.jsonl` 수정
- ❌ 돌려보지 않고 "완료"
