# DoD-05 재측정 원문 (수집: 구현 담당, 판정 없음)

## 재현 명령
```powershell
python -m pytest tests\unit\core\test_context_budget.py -q
@'
from uuid import UUID
from app.core.context import ContextBroker, ContextInputs, PolicyChunk
x=ContextInputs(case_id=UUID('00000000-0000-0000-0000-000000000005'),tenant_id='measure',team_id='measure',knowledge_scope=['billing'],system_instruction='answer with evidence',current_state={'status':'routing','version':2},similar_cases=[{'case_id':'sim-1','body':'similar '*2000}],history_entries=['history '*500],policy_chunks=[PolicyChunk('high',1,'high policy '*1000,0.99,'billing'),PolicyChunk('low',1,'low policy '*1000,0.10,'billing')])
p=ContextBroker().build(x)
print('estimated_input_tokens=',p.estimated_input_tokens)
print('omissions=',p.omissions)
'@ | python -
```

## 실제 출력
```
...                                                                      [100%]
… warning 상세 6줄 생략
3 passed, 1 warning in 0.58s
estimated_input_tokens= 2517
omissions= ['similar_cases:budget:sim-1', 'policy_rag:low_score:low#c1']
```

## 관측 사실
- `tests\unit\core\test_context_budget.py` 출력의 집계는 `3 passed, 1 warning`이다.
- `estimated_input_tokens` 출력값은 `2517`이다.
- `omissions` 출력 순서는 `similar_cases:budget:sim-1`, `policy_rag:low_score:low#c1`이다.

## 확인하지 못한 것
- 위 입력과 다른 입력 조합의 절삭 순서는 확인하지 못했다.
