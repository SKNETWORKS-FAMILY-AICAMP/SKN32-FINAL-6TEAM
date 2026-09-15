# Codex — S-EVAL **실제 LLM 실행** (mock → openai) + 동시 실행

## 0. 현재 상태 — 정직했지만 요청한 것이 아니다

지난 실행은 **fixture 였다.** 데이터에 그렇게 적혀 있어 숨기지는 않았다:

```
"provider": "mock", "answer": "Fixture prediction; not an LLM judgment."
cost_usd 합계 = 0.0 (540건 전부) · latency_ms = 0.02 · DB llm_calls = 0건
eval/runners/common.py:91
  raise RuntimeError("OpenAI provider adapter is intentionally not enabled in this smoke harness")
```

★**v5 §20 DoD 15·16 은 이걸로 채워지지 않는다.** 실제 LLM 실행이 필요하다.

## 1. 소유 범위
```
eval/**
prompts/judge/**
wiki/records/reports/ , wiki/records/history/
```
★그 밖 **전부 금지**. `app/**`, `tests/**`, `knowledge/**`, `scripts/**`, `wiki/records/evidence/**`.

## 2. 할 일

### 2-1. `--provider openai` 실경로 구현 (`eval/runners/common.py`)
- 설정은 **`app.core.settings.get_settings()`** 로 읽는다.
  ★`os.getenv` 금지 — `.env` 값이 안 보인다(S-API 가 이걸로 전면 장애를 냈다)
- 모델 `settings.llm_model`(gpt-4o-mini), `temperature=0.0`, `seed=7`
- 각 군의 실제 동작:
  | 군 | 무엇을 하나 |
  |---|---|
  | A | 단일 LLM 호출 + 원문 prompt + 최소 DB 조회 |
  | B | 고정 rule/workflow + `search_policy()` 정책 retrieval, Team 없음 |
  | Proposed | `ContextBroker` + 두 TeamModule + approval 경로 |
- ★**Proposed 는 실제 Team 을 호출**한다 (`app/modules/customer_ops/{billing,technical}.py`).
  못 하면 그 사실을 리포트에 적고 **부분 실행**으로 남겨라. 가짜로 채우지 마라
- `--provider mock` 은 그대로 유지 (smoke 용)

### 2-2. ★동시 실행 (시간이 촉박하다)
- `--concurrency N` 옵션 추가, **기본 8**. `asyncio` 또는 `ThreadPoolExecutor`
- ★**결정성 유지**: 결과는 `case_id`·`repeat` 로 정렬해서 기록한다. 실행 순서가 결과를 바꾸면 안 된다
- rate limit(429) 은 지수 백오프로 재시도하되, **재시도 횟수를 결과에 기록**하라

### 2-3. 실제 측정값 기록
각 행에 **실측**을 넣는다. 0 이나 상수를 넣지 마라:
`input_tokens`, `output_tokens`, `latency_ms`, `cost_usd`, `retries`
- ★비용은 **실제 토큰 × 단가**로 계산: gpt-4o-mini input $0.15/1M, output $0.60/1M
  (2026-08 시점 가정임을 리포트에 명시)

## 3. 실행 순서

```powershell
# 1) 비용 산출 먼저
python -m eval.runners.baseline_a --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7 --provider openai --dry-run
python -m eval.runners.baseline_b --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7 --provider openai --dry-run
python -m eval.runners.proposed  --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7 --provider openai --dry-run
```
★합계 예상 비용이 **$10 초과면 실행하지 말고 멈추고 보고**하라.

```powershell
# 2) 소규모 검증 (5건) — 진짜 호출인지 먼저 확인
python -m eval.runners.baseline_a --dataset eval/datasets/golden.jsonl --repeats 1 --seed 7 --provider openai --limit 5 --concurrency 5
```
★이 시점에 `cost_usd > 0`, `latency_ms > 100`, `input_tokens > 0` 이어야 한다.
0 이면 여전히 mock 이다 — 고쳐라.

```powershell
# 3) 전량
python -m eval.runners.baseline_a --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7 --provider openai --concurrency 8
python -m eval.runners.baseline_b --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7 --provider openai --concurrency 8
python -m eval.runners.proposed  --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7 --provider openai --concurrency 8
```

```powershell
# 4) 통계
python -m eval.stats.bootstrap --input eval/reports/raw.jsonl --n 10000
python -m eval.stats.mcnemar --input eval/reports/pairs.jsonl
```

★**holdout 20건은 돌리지 마라.**
★실패한 Case 는 실패로 기록한다. 재시도로 성공시켜 성공률을 부풀리지 마라.

## 4. 자체 검증 (완료 전에 반드시)

```powershell
python -c "import json;rows=[json.loads(l) for l in open('eval/reports/raw.jsonl',encoding='utf-8')];print('n=',len(rows));print('mock행=',sum(1 for r in rows if r['config']['provider']!='openai'));print('cost합=',sum(r.get('cost_usd',0) for r in rows));print('latency중앙=',sorted(r['latency_ms'] for r in rows)[len(rows)//2])"
```
기대: `n=540`, **`mock행=0`**, `cost합 > 0`, `latency중앙 > 100`.
★이 조건을 만족하지 못하면 **완료가 아니다.**

## 5. 리포트

`eval/reports/2026-08-12_평가결과_리포트.md`:
1. 실행 조건 (model·temperature·seed·dataset·prompt snapshot·concurrency·실행시각)
2. 지표표 (v5 §15-3) — ★**모든 수치에 분모** (`0.85 (51/60)`)
3. bootstrap CI · McNemar — ★**CI 가 0 을 걸치면 "유의하지 않다"**
4. degraded 케이스 별도 집계
5. ★**한계 (v5 §15-8)** — 60건×3회는 방향성과 불확실성만 말한다. 모집단 일반화·장기 drift·
   실제 손실률·모든 도메인 우월성·운영 SLA 를 증명하지 않는다
6. **실제 비용·호출 수·재시도 수**

`wiki/records/reports/2026-08-12_S-EVAL_실제실행_리포트.md` 에 §3~§4 **출력 원문**,
`wiki/records/history/2026-08-12_S-EVAL_live.md` 이력.

## 6. 하지 말 것
- ❌ mock 으로 돌리고 완료 보고
- ❌ `os.getenv` 로 키 읽기
- ❌ 비용·토큰·latency 에 0 이나 상수 채우기
- ❌ holdout 실행
- ❌ 실패를 재시도로 덮기
- ❌ 평균만 보고 / CI 가 0 을 걸치는데 "우수"
- ❌ 한계 서술 생략
- ❌ 소유 범위 밖 수정
