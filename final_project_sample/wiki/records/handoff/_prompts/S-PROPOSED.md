# 구현 지시 — Proposed 러너가 실제 시스템을 타게 한다

## 0. 결함 (실측 2026-08-13, 540행 전량 완료)

| 군 | 성공 | citations valid/invalid | grounding 평균 | personalization 평균 |
|---|---:|---|---:|---:|
| A | 0/180 | 0 / 8 | 0.00 | — |
| B | **115/180** | **8 / 0** | **2.67** | 2.03 |
| **Proposed** | **0/180** | **0 / 0** | **0.00** | **0.21** |

★**Proposed 가 인용을 하나도 만들지 않는다**(claimed 자체가 0).
answer 도 케이스와 무관한 정형 스텁이다:

> "구독과 결제 이력을 확인했습니다. 정책 근거를 바탕으로 안내할 수 있습니다."

B 의 answer 와 비교하면 차이가 분명하다:

> "It appears that you were charged for your Pro plan after cancellation. We will investigate..."

**Proposed 러너가 실제 시스템을 타지 않는다.**
상세: `wiki/records/reports/debugs/2026-08-13_1500_Proposed군이_실제시스템을_돌리지_않는다.md`

★Proposed 는 **이 프로젝트가 만든 것 그 자체**다. baseline B 보다 낮은 것은
결과가 아니라 **측정 실패**다. 이대로 두면 "Context Broker + Team 을 붙였더니 나빠졌다"는
**정반대 결론**이 나온다.

## 1. 소유 범위

```
eval/runners/proposed.py
eval/runners/common.py       (필요한 만큼만)
wiki/records/reports/ , wiki/records/history/
```
★그 밖 **전부 금지**: `app/**`(★읽기만), `tests/**`, `knowledge/**`,
`config/**`, `scripts/**`, `wiki/records/handoff/**`, `wiki/records/evidence/**`, `wiki/records/submission/**`.
★`eval/reports/raw_*.jsonl` 를 **지우지 마라** — A/B 결과는 유효하다.

## 2. 고칠 것

### 2-1. 실제 경로를 탄다

Proposed 는 v5 §15-1 상 **Case lifecycle + Context Broker + 2 Teams + approval** 이다.
러너가 다음을 실제로 호출해야 한다:

1. `app.infrastructure.rag.retriever.search_policy()` — 정책 검색
2. `app.core.context.ContextBroker.build()` — ContextPack 조립
3. `app.modules.customer_ops.billing.BillingSubscriptionTeam` /
   `.technical.TechnicalEntitlementTeam` 의 `execute(task)`
   (또는 `app.core.remote_team.executor.LocalTeamExecutor` 경유 — 이쪽이 더 낫다)

★**고정 문구를 만들지 마라.** `TeamResult.answer` 를 그대로 쓴다.

### 2-2. ★인용을 실어라

`ContextPack.evidence` 중 `source_type == 'policy'` 인 항목의 `source_id` 는
**이미 `doc_NN#cM` 형식**이다(`app/core/context.py` 의 `PolicyChunk.source_id`).

그걸 **그대로** `prediction['policy_evidence']` 에 넣는다.
`TeamResult.evidence` 에도 policy 항목이 있으면 합친다.

### 2-3. 실패를 숨기지 마라

Team 실행이 실패하거나 `ContextPack.degraded=True` 면
`degraded` 필드에 **그대로 기록**한다. 성공으로 만들지 마라.

## 3. ★자체 검증 — 이게 통과해야 완료다

```powershell
python -m eval.runners.proposed --dataset eval/datasets/golden.jsonl --repeats 1 --seed 7 --provider openai --limit 3 --concurrency 3 --output eval/reports/chk_p.jsonl
```

```powershell
python -c "import json;rows=[json.loads(l) for l in open('eval/reports/chk_p.jsonl',encoding='utf-8')];[print(r['case_id'], 'valid=',len(r.get('citations',{}).get('valid',[])), 'grounding=',r['judge']['policy_grounding'], '|', str(r['prediction'].get('answer'))[:60]) for r in rows]"
```

기대:
- ★`valid` 가 **0 이 아니다**
- ★`grounding` 이 **0 이 아니다**
- ★**answer 가 케이스마다 다르다** (같은 문구가 반복되면 여전히 스텁이다)

★이 조건을 만족하지 못하면 **완료가 아니다.**

## 4. ★전량 실행은 하지 마라

이 환경은 외부 네트워크가 막혀 있어 **당신 프로세스에서는 OpenAI 호출이 실패한다**
(`APIConnectionError`). §3 검증이 그 이유로 실패하면 **그 사실을 리포트에 적고 멈춰라.**
코드만 고쳐 두면 전량 실행은 다른 환경에서 한다.

★mock 으로 돌려놓고 "완료" 라고 쓰지 마라.

## 5. 리포트

`wiki/records/reports/2026-08-13_S-PROPOSED_리포트.md` — 변경 파일,
§3 출력(또는 실패 출력), Proposed 가 실제로 호출하는 모듈 목록.

## 6. 하지 말 것
- ❌ 고정 문구 answer
- ❌ 인용 없이 grounding 을 받으려는 우회
- ❌ `app/**` 수정 (읽기만)
- ❌ 기존 `raw_baseline_*.jsonl` 삭제
- ❌ 실패를 성공으로 기록
- ❌ 전량 실행 / mock 보고
