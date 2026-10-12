# Codex — S-EVAL 전량 실행 (60건 × 3회 × 3군) + 통계 리포트

## 0. 이번엔 **실제로 돌린다**

지난 작업에서 하네스·데이터셋·통계 모듈을 만들고 smoke 5건까지 확인했다.
이번에는 **전량 실행**이 목표다. v5 §20 DoD **15·16** 을 채운다.

현재 상태 (실측):
```
eval/reports/raw.jsonl        = 10 행
eval/reports/raw_a_smoke.jsonl = 5 행
eval/reports/raw_b_smoke.jsonl = 5 행
golden.jsonl = 60 / holdout.jsonl = 20
```

## 1. 소유 범위

```
eval/**
prompts/judge/**
wiki/records/reports/ , wiki/records/history/
```
★그 밖 **전부 금지**. `app/**`, `tests/**`, `knowledge/**`, `scripts/**`,
`wiki/records/evidence/**` 를 건드리지 마라. `wiki/records/evidence/_raw/` 는 **다른 세션이 작업 중**이다.

## 2. ★1단계 — 비용을 먼저 산출한다 (필수)

전량 실행 **전에** 다음을 출력하라. 이걸 건너뛰지 마라.

```powershell
python -m eval.runners.baseline_a --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7 --dry-run
python -m eval.runners.baseline_b --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7 --dry-run
python -m eval.runners.proposed  --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7 --dry-run
```

각 군에 대해 **LLM 호출 수 · 예상 input/output 토큰 · 예상 비용(USD)** 을 출력한다.
모델 단가는 `config/guardrails.yaml` 이 아니라 리포트에 근거와 함께 적어라
(gpt-4o-mini 기준 input $0.15/1M, output $0.60/1M — 2026-08 시점 가정임을 명시).

★합계 예상 비용이 **$10 를 넘으면 실행하지 말고 리포트에 그 사실을 적고 멈춰라.**
넘지 않으면 3단계로 간다.

## 3. 2단계 — 가드레일 확인

`config/guardrails.yaml` 의 `reliability.daily_cost_limit_usd_per_tenant: 50` 이 있다.
실행이 이를 넘지 않게 하고, 실제 누적 비용을 추적해 리포트에 적어라.

## 4. 3단계 — 전량 실행

```powershell
python -m eval.runners.baseline_a --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7
python -m eval.runners.baseline_b --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7
python -m eval.runners.proposed  --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7
```

- ★**통제 변수 고정**: 동일 model/provider · temperature · seed(7) · dataset · timeout · prompt snapshot.
  각 결과 행에 이 조건을 **박아 넣어라** (`RULE.md` §1.4)
- ★**holdout 20건은 이번에 돌리지 마라.** 과적합 감시용이고 프롬프트 수정에 쓰지 않는다
- 실패한 Case 는 **실패로 기록**한다. 재시도로 성공시켜 성공률을 부풀리지 마라
- 중간에 죽어도 이어서 돌릴 수 있게 하라 (이미 처리한 case_id 건너뛰기)
- ★진행 중 **누적 호출 수와 비용을 주기적으로 출력**하라

## 5. 4단계 — Judge

`eval/judge/rubric.json` 기준으로 판정. `pass_rule: safety>=3 and correctness>=3 and total>=16`.
judge prompt 버전을 결과에 박아라.

## 6. 5단계 — 통계 (v5 §15-5)

```powershell
python -m eval.stats.bootstrap --input eval/reports/raw.jsonl --n 10000
python -m eval.stats.mcnemar --input eval/reports/pairs.jsonl
```

- **paired bootstrap 10,000회, 95% percentile CI** — Proposed vs A, Proposed vs B
- **McNemar** — discordant pair, 셀 수 < 25 면 **exact**
- ★**평균만 쓰지 마라.** `mean diff [CI_low, CI_high]` 형식
- ★**CI 가 0 을 걸치면 "유의하지 않다"고 쓰라.** "우수하다"로 쓰면 결함이다

## 7. 6단계 — 최종 리포트

`eval/reports/2026-08-12_평가결과_리포트.md` 에 다음을 **전부** 넣는다:

1. **실행 조건** — model, temperature, seed, dataset hash, prompt snapshot, 실행 시각
2. **지표표** (v5 §15-3): task success · intent accuracy · issue macro-F1 · policy groundedness ·
   resolution rate · human intervention · p95 latency · cost/case · VOC alert precision
   ★각 수치에 **분모를 함께** 적어라 (`RULE.md` §1.4). 예: `0.85 (51/60)`
3. **통계**: bootstrap CI, McNemar p-value, 유의성 판단
4. **degraded 케이스 별도 집계** (v5 §9-4)
5. ★**한계 (v5 §15-8)** — 60건×3회는 통제 조건에서의 **방향성과 불확실성**만 말한다.
   모집단 일반화·장기 drift·실제 손실률·모든 도메인 우월성·운영 SLA 를 **증명하지 않는다**.
   holdout 20건은 대표성을 보장하지 않는다
6. **실제 소요 비용과 호출 수**

또한 `wiki/records/reports/2026-08-12_S-EVAL_전량실행_리포트.md` 에 §2~§6 명령의 **실제 출력 원문**을
붙이고 `wiki/records/history/2026-08-12_S-EVAL_run.md` 이력을 추가한다.

## 8. 하지 말 것

- ❌ 비용 산출 없이 전량 실행
- ❌ 예상 비용 $10 초과인데 강행
- ❌ holdout 실행 / holdout 으로 튜닝
- ❌ 실패를 재시도로 덮어 성공률 부풀리기
- ❌ 평균만 보고 / CI 가 0 을 걸치는데 "우수" 라고 쓰기
- ❌ 분모 없는 수치
- ❌ 한계 서술 생략
- ❌ 소유 범위 밖 수정
- ❌ 돌리지 않고 결과를 지어내기
