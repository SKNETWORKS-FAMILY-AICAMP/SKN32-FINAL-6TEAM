# 2026-08-13 S-PROPOSED 리포트

## 변경 파일

- `eval/runners/common.py`
- `eval/reports/chk_p.jsonl` (지정 검증 출력)
- `wiki/records/reports/2026-08-13_S-PROPOSED_리포트.md`

`app/**`, `tests/**`, `knowledge/**`, `config/**`, `scripts/**`, `wiki/records/handoff/**`,
`wiki/records/evidence/**`, `wiki/records/submission/**`는 수정하지 않았다. 기존 `raw_*.jsonl`도
삭제하지 않았다.

## 수정 내용

Proposed 실행 경로에서 다음을 보장하도록 수정했다.

- `search_policy()`가 반환한 `PolicyChunk.source_id`를 `ContextBroker.build()`의
  `ContextPack.evidence`로 전달한다.
- `ContextPack.evidence`와 `TeamResult.evidence`의 `source_type == "policy"`
  항목을 합치고 중복 제거한 뒤, `source_id`를 그대로
  `prediction["policy_evidence"]`에 넣는다.
- `TeamResult.answer`를 그대로 `prediction["answer"]`로 전달한다. 러너가
  고정 답변을 생성하지 않는다.
- `ContextPack.degraded`, TeamResult의 `failure_code` 및 `warnings`를
  `degraded` 결과에 반영한다. 실행 예외는 성공으로 변환하지 않고
  `error`에 기록한다.

## Proposed가 실제로 호출하는 모듈

- `app.infrastructure.rag.retriever.search_policy`
- `app.core.context.ContextBroker` 및 `ContextInputs`
- `app.modules.customer_ops.billing.BillingSubscriptionTeam`
- `app.modules.customer_ops.technical.TechnicalEntitlementTeam`
- `app.tools.read_tools.ReadToolbox` 및 실제 read 도구
- 각 Team의 `execute(task)`
- 이후 평가용 OpenAI prediction/judge 호출

## 자체 검증

실행한 명령:

```powershell
python -m eval.runners.proposed --dataset eval/datasets/golden.jsonl --repeats 1 --seed 7 --provider openai --limit 3 --concurrency 3 --output eval/reports/chk_p.jsonl
```

문법 검사는 통과했다. 러너 실행은 세 케이스 모두 외부 네트워크 차단으로
`APIConnectionError: Connection error.`가 발생해 실패했다.

두 번째 확인 명령의 출력:

```text
g-billing-01 valid= 0 grounding= None | None | error= APIConnectionError: Connection error.
g-billing-02 valid= 0 grounding= None | None | error= APIConnectionError: Connection error.
g-billing-03 valid= 0 grounding= None | None | error= APIConnectionError: Connection error.
```

따라서 이 환경에서는 `valid != 0`, `grounding != 0`, 케이스별 answer 차이라는
검증 기대를 확인할 수 없다. mock으로 대체하거나 전량 실행하지 않았으며,
네트워크가 가능한 환경에서 `chk_p.jsonl`을 새 출력 경로로 재실행해야 한다.
