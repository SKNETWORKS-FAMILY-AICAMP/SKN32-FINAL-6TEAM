# 구현 지시 — 평가 러너가 judge 프롬프트를 arm 에 쓰고 있다

## 0. 결함 (실측 2026-08-12)

`--provider openai` 로 arm A 를 3건 돌린 결과:

```
success False | cost 7.635e-05 | latency 2626.009 | in_tok 261 | err None
prediction: {'correctness': 0, 'policy_grounding': 0, 'next_action': 0,
             'safety': 0, 'personalization': 0, 'total': 0, 'pass': False, 'reasons': []}
config: { "arm": "A", ..., "prompt_version": "judge-v1", "prompt_snapshot": "judge-v1" }
```

★**LLM 호출 자체는 정상**이다(latency 2.6초, 실제 토큰 소모).
문제는 **arm 러너가 judge 프롬프트를 쓴다**는 것이다. 그래서:

- `prompt_version` 이 arm 과 무관하게 `judge-v1`
- arm 이 답변(`intent`/`issue_code`/`answer`)이 아니라 **rubric 점수**를 낸다
- 그 rubric 이 전부 0 이라 `success=False` 가 된다

## 1. 소유 범위

```
eval/**
prompts/judge/**
```
★그 밖 **전부 금지**: `app/**`, `tests/**`, `knowledge/**`, `scripts/**`, `docs/**`, `config/**`.

## 2. 고칠 것 — arm 과 judge 를 분리한다

### 2-1. arm 러너는 **예측(prediction)** 을 만든다

각 arm 이 **자기 프롬프트**로 LLM 을 호출해 아래를 산출한다:

```json
{"intent": "...", "issue_code": "...", "sentiment": "...",
 "next_action": "...", "answer": "...", "policy_evidence": ["doc_06#c3", ...]}
```

| arm | 어떻게 |
|---|---|
| A | 단일 LLM 호출 + 원문 prompt + 최소 DB 조회. **RAG 없음** |
| B | 고정 rule/workflow + `search_policy()` 정책 retrieval. Team 없음 |
| Proposed | `ContextBroker` + `BillingSubscriptionTeam`/`TechnicalEntitlementTeam` |

- ★`prompt_version` 은 **arm 별로 다르게** 기록한다 (`baseline-a-v1`, `baseline-b-v1`, `proposed-v1`)
- ★Proposed 는 실제 Team 을 호출한다. 못 하면 리포트에 적고 **부분 실행**으로 남겨라

### 2-2. judge 는 **별도 단계**다

arm 이 끝난 뒤, judge 프롬프트로 각 예측을 채점한다:
`eval/judge/rubric.json` 기준 5종 0~4, `safety>=3 and correctness>=3 and total>=16`.
judge 결과는 `score`/`success` 로 들어가고 `judge_prompt_version` 을 따로 기록한다.

### 2-3. success 판정

`success` 는 judge 의 `pass` 다. **rubric 이 비어 있으면 success 가 아니라 오류**로 기록하라
(지금처럼 전부 0 이 나오면서 조용히 False 가 되면 실패 원인을 알 수 없다).

## 3. 자체 검증 — 반드시 통과해야 완료다

```powershell
python -m eval.runners.baseline_a --dataset eval/datasets/golden.jsonl --repeats 1 --seed 7 --provider openai --limit 3 --concurrency 3 --output eval/reports/probe.jsonl
python -c "import json;r=[json.loads(l) for l in open('eval/reports/probe.jsonl',encoding='utf-8')][0];print('prompt_version=',r['config']['prompt_version']);print('pred_keys=',sorted(r['prediction'].keys()));print('cost=',r.get('cost_usd'),'in_tok=',r.get('input_tokens'))"
```

기대:
- `prompt_version` 이 **`judge-v1` 이 아니다**
- `pred_keys` 에 `intent`·`answer` 가 있다 (rubric 키가 아니다)
- `cost > 0`, `input_tokens > 0`

★**이 조건을 만족하지 못하면 완료가 아니다.** 만족할 때까지 고쳐라.

## 4. ★전량 실행은 하지 마라

네트워크가 막힌 환경이라 **당신 프로세스에서는 OpenAI 호출이 실패한다**
(`APIConnectionError`). 위 §3 검증도 실패하면 **그 사실을 리포트에 적고 멈춰라** —
코드만 고쳐 두면 실행은 다른 환경에서 한다.

★mock 으로 돌려놓고 "완료" 라고 쓰지 마라. `--provider mock` 은 smoke 용으로만 유지한다.

## 5. 리포트

`wiki/records/reports/2026-08-12_평가러너_프롬프트배선_수정.md` — 변경 파일,
§3 명령의 실제 출력(또는 실패 출력), arm 별 프롬프트 파일 경로.

## 6. 하지 말 것
- ❌ arm 과 judge 가 같은 프롬프트를 쓰게 두기
- ❌ rubric 이 비었는데 조용히 `success=False`
- ❌ 소유 범위 밖 수정
- ❌ mock 결과를 실제 실행으로 보고
