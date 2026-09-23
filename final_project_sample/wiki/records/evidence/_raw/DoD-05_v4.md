# DoD-05 v4 실측 원문

실행 시각: 2026-08-14

명령:

```text
python -m pytest tests/unit/core/test_context_budget.py -v
```

출력 요약:

```text
collected 3 items
3 passed
```

예산 초과 입력 직접 호출 출력:

```text
estimated_input_tokens= 2517
omissions= ['similar_cases:budget:a859268d-cf79-4e61-bf53-9401e087ea44', 'policy_rag:low_score:low#c1']
```
