# DoD-04 실측 원문 (수집: Codex, 판정 없음)

## 재현 명령
```powershell
@' ... '@ | python
```

## 실제 출력
```
checkpoint= {'case_id': '3016b98c-13cc-4ae9-94e8-54dbf7957ad6', 'run_id': 'f5eba89a-c158-4b60-b7bb-cd453b2617ed', 'graph_revision': 'measurement-v1', 'node_name': 'classify', 'runtime_state': {'x': 'runtime'}}
agent_runs_columns= ['run_id', 'tenant_id', 'case_id', 'graph_revision', 'status', 'attempt', 'started_at', 'finished_at']
graph_revision_rows= []
EXIT=0
```

## 관측 사실
- checkpoint 출력 키는 `case_id`, `run_id`, `graph_revision`, `node_name`, `runtime_state`이다.
- `agent_runs` 컬럼 목록에 `graph_revision`이 포함되어 있다.
- demo tenant의 `graph_revision_rows` 조회 결과는 빈 목록이다.

## 확인하지 못한 것
- checkpoint를 저장소에서 업무 상태로 되돌리는 별도 실행 결과는 확인하지 못했다.
