# 구현 지시 — Proposed 의 **answer 가 여전히 스텁**이다 (인용만 고쳐졌다)

## 0. 부분 수정됐고, 나머지가 더 위험하다

지난 수정으로 **인용은 고쳐졌다**:
```
citations: claimed 8 / valid 8 / invalid 0
  ['doc_10#c7','doc_07#c11','doc_11#c9','doc_02#c11','doc_02#c5','doc_12#c3','doc_12#c7','doc_09#c10']
success: True  score: 18
```

★**그러나 answer 가 여전히 고정 문구다.** 4건을 돌려 실측:
```
행수 4 | 고유 answer 1
  - 구독과 결제 이력을 확인했습니다. 정책 근거를 바탕으로 안내할 수 있습니다.
```

`S-PROPOSED.md` §3 이 명시한 조건을 만족하지 못했다:
> ★**answer 가 케이스마다 다르다** (같은 문구가 반복되면 여전히 스텁이다)

## 1. ★왜 이게 더 위험한가

인용이 유효해져서 `policy_grounding` 이 높게 나온다. 그래서 **점수가 오른다**(score 18).
이 상태로 540런을 돌리면 Proposed 가 baseline 을 이기는 결과가 나오는데,
그건 **답변 품질이 아니라 검색 배선을 측정한 것**이다.

★**틀린 결과보다 나쁘다.** 틀린 결과는 이상하게 보여서 잡히지만,
그럴듯하게 높은 결과는 그대로 리포트에 실린다.

이 프로젝트에서 같은 종류를 이미 겪었다 — 코퍼스 v3 이 무작위 토큰을 주입해
유사도 지표만 낮췄던 일(`wiki/records/reports/debugs/2026-08-12_1720_*`).
**지표를 만족시키는 것과 목표를 달성하는 것은 다르다.**

## 2. 소유 범위

```
eval/runners/proposed.py
eval/runners/common.py       (필요한 만큼만)
wiki/records/reports/ , wiki/records/history/
```
★`app/**` 는 **읽기만**. `tests/**`, `knowledge/**`, `config/**`, `scripts/**`,
`wiki/records/handoff/**`, `wiki/records/evidence/**`, `wiki/records/submission/**` 금지.
★`eval/reports/raw_baseline_*.jsonl` 을 **지우지 마라**.

## 3. 고칠 것 — `TeamResult.answer` 를 그대로 쓴다

Proposed 는 v5 §15-1 상 **Case lifecycle + Context Broker + 2 Teams** 다.

1. `ContextBroker.build()` 로 만든 `ContextPack` 을 담아 `TeamTask` 를 만든다
2. ★**실제 Team 을 호출**한다:
   - `app.core.remote_team.executor.LocalTeamExecutor` 경유 (권장) 또는
   - `BillingSubscriptionTeam` / `TechnicalEntitlementTeam` 의 `execute(task)`
3. ★**돌아온 `TeamResult.answer` 를 그대로** `prediction['answer']` 에 넣는다.
   **문자열을 새로 만들지 마라.**
4. `TeamResult.next_action` 도 그대로 반영한다

★Team 이 LLM 을 호출하도록 **실제 LLM 을 주입**한다. Team 은 `llm` 인자를 받는다
(`BillingSubscriptionTeam(tools, llm)`). fake 를 넣으면 스텁이 나온다 — 그게 지금 상태다.

★Team 이 `escalate` 하거나 `degraded` 면 **그대로 기록**한다. 성공으로 만들지 마라.

## 4. ★자체 검증 — 이게 통과해야 완료다

```powershell
python -m eval.runners.proposed --dataset eval/datasets/golden.jsonl --repeats 1 --seed 7 --provider openai --limit 4 --concurrency 4 --output eval/reports/chk_p.jsonl
```

```powershell
python -c "
import json
rows=[json.loads(l) for l in open('eval/reports/chk_p.jsonl',encoding='utf-8')]
ans=[str((r.get('prediction') or {}).get('answer')) for r in rows]
print('행수',len(rows),'| 고유 answer',len(set(ans)))
for a in ans: print('  -',a[:80])
"
```

기대:
- ★**고유 answer 가 행수와 같다** (4행이면 4개가 서로 달라야 한다)
- ★answer 가 **케이스 내용을 반영**한다 (해지 후 결제 건과 권한 불일치 건의 답이 달라야 한다)
- `citations.valid` 는 계속 비어 있지 않다 (지금 상태 유지)

★**고유 answer 가 1이면 완료가 아니다.**

## 5. 네트워크

이 환경은 외부 네트워크가 막혀 있어 **당신 프로세스에서는 OpenAI 호출이 실패한다**
(`APIConnectionError`). §4 검증이 그 이유로 실패하면 **그 사실을 리포트에 적고 멈춰라.**
코드만 고쳐 두면 실행은 다른 환경에서 한다.

★**fake LLM 으로 돌려놓고 "완료" 라고 쓰지 마라.** 그게 지금 문제의 원인이다.

## 6. 리포트

`wiki/records/reports/2026-08-13_S-PROPOSED2_리포트.md` — 변경 파일, §4 출력(또는 실패 출력),
Proposed 가 실제로 호출하는 모듈과 **LLM 주입 방식**.

## 7. 하지 말 것
- ❌ answer 문자열을 러너가 만들기
- ❌ Team 에 fake LLM 주입
- ❌ 인용만 맞춰 점수를 올리기
- ❌ `app/**` 수정
- ❌ 기존 baseline 결과 삭제
- ❌ 전량 실행 / mock 보고
