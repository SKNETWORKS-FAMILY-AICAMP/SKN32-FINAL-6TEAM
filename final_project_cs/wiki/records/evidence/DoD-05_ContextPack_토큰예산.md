# DoD-05 — ContextPack 이 12,000 input token 을 넘지 않고 omissions 를 기록한다

- v5 §20 항목 5 / 검증 방법: token counter
- 최초 판정: 2026-08-12 **부분 통과** (절삭 동작 미관측)
- 재측정: 2026-08-14 · 실측 원문 `wiki/records/evidence/_raw/DoD-05_v4.md`
- 판정: 통과

## 재현 명령

```powershell
python -m pytest tests/unit/core/test_context_budget.py -v
python  # ContextBroker.build() 를 예산 초과 입력으로 직접 호출
```

## 실제 출력

```
collected 3 items
3 passed

estimated_input_tokens = 2517
omissions = ['similar_cases:budget:a859268d-cf79-4e61-bf53-9401e087ea44',
             'policy_rag:low_score:low#c1']
```

## 판정 근거

| 요구 (v5 §9-1) | 결과 |
|---|---|
| 예산 초과 팩이 만들어지지 않는다 | **통과** — 계약 validator 가 `>12000` 을 거부 |
| ★**절삭이 실제로 일어난다** | **통과** — 초과 입력에서 `estimated_input_tokens=2517` 로 줄었고 `omissions` 가 채워졌다 |
| ★**제거 순서가 계약대로** | **통과** — `similar_cases` 가 **먼저**, `policy_rag:low_score` 가 나중. `config/guardrails.yaml` 의 `eviction_order`(similar_cases → history → 낮은 점수 RAG → 중복 fact)와 일치 |
| ★`case_state` 는 제거되지 않는다 | **통과** — omissions 에 없다 |
| 낮은 score 부터 제거 | **통과** — `low#c1`(낮은 점수 청크)이 빠졌다 |
| `degraded` 신호 강제 | **통과** — `degraded=True` 인데 `omissions` 가 비면 계약이 거부 |
| tiktoken 실측 | **통과** — 문자수 어림이 아니다 |

## 최초 판정에서 무엇이 바뀌었나

2026-08-12 에는 "계약이 초과 팩을 **거부한다**" 만 확인됐고,
"Broker 가 넘칠 입력을 **올바른 순서로 잘라 넘지 않는 팩을 만든다**" 는 증명되지 않았다.
그때 판정에 이렇게 적었다:

> 계약이 "예산을 넘은 팩" 을 거부한다는 것과
> **Broker 가 넘칠 입력을 올바른 순서로 잘라 넘지 않는 팩을 만든다**는 것은 다른 주장이다.

그 뒤 전역 제거 순서를 구현하고 `tests/unit/core/test_context_budget.py` 를 추가했다.
이번 재측정으로 **두 번째 주장이 관측**됐다.

## 한계

- 이번 실측의 초과 입력은 **테스트가 만든 fixture** 다. 실제 운영 규모의 Case state·
  history·RAG 조합에서의 절삭은 관측되지 않았다
- `history_detail` 과 `duplicate_tool_facts` 제거는 이번 출력에 나타나지 않았다
  (그 섹션이 예산을 넘지 않았기 때문). **네 단계 전부를 한 입력에서 관측하지는 못했다**
