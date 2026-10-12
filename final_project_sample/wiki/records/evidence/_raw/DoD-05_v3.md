# DoD-05 재측정 원문

## 재현 명령

```powershell
python -m pytest tests\unit\core\test_context_budget.py -v
```

예산 초과 `ContextInputs`를 만들어 `ContextBroker.build()`를 직접 호출하고 token·omissions를 출력했다.

## 실제 출력

```text
collecting ... collected 3 items
tests/unit/core/test_context_budget.py::test_context_broker_eviction_is_budgeted_and_ordered PASSED [ 33%]
tests/unit/core/test_context_budget.py::test_context_broker_rejects_untruncatable_sections[system_instruction-...] PASSED [ 66%]
tests/unit/core/test_context_budget.py::test_context_broker_rejects_untruncatable_sections[current_state-value1] PASSED [100%]
======================== 3 passed, 1 warning in 2.59s =========================
estimated_input_tokens= 2517
omissions= ['similar_cases:budget:sim-1', 'policy_rag:low_score:low#c1']
```

## 관측 사실

- pytest 수집 항목 수는 `3`이었다.
- 마지막 집계는 `3 passed, 1 warning in 2.59s`였다.
- `estimated_input_tokens`는 `2517`이었다.
- `omissions` 순서는 `similar_cases:budget:sim-1`, `policy_rag:low_score:low#c1`이었다.

## 확인하지 못한 것

- 위 직접 입력 조합 이외의 모든 ContextInputs 조합은 실행하지 않았다.

