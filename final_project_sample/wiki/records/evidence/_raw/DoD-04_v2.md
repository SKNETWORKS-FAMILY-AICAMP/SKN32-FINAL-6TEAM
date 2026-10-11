# DoD-04 재측정 원문 (수집: 구현 담당, 판정 없음)

## 재현 명령
```powershell
@'
from uuid import UUID
from app.application.case_service import CaseService
checkpoint=CaseService(graph_revision='measurement-v2').checkpoint(case_id=UUID('00000000-0000-0000-0000-000000000004'),run_id=UUID('00000000-0000-0000-0000-000000000044'),node_name='classify',runtime_state={'case_version':2,'status':'routing'})
print('checkpoint_keys=',list(checkpoint.keys()))
print('checkpoint=',checkpoint)
'@ | python
$psql="$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe"; & $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -P pager=off -c "SELECT count(*) AS agent_runs_rows FROM agent_runs WHERE tenant_id='demo'; SELECT graph_revision,status FROM agent_runs WHERE tenant_id='demo' ORDER BY started_at;"
```

## 실제 출력
```
checkpoint_keys= ['case_id', 'run_id', 'graph_revision', 'node_name', 'runtime_state']
checkpoint= {'case_id': '00000000-0000-0000-0000-000000000004', 'run_id': '00000000-0000-0000-0000-000000000044', 'graph_revision': 'measurement-v2', 'node_name': 'classify', 'runtime_state': {'case_version': 2, 'status': 'routing'}}
 agent_runs_rows 
-----------------
               0
(1 row)

 graph_revision | status 
----------------+--------
(0 rows)
```

## 관측 사실
- `checkpoint_keys`에는 5개 키가 출력되었다.
- `agent_runs_rows`의 `demo` 조회값은 `0`이다.
- `demo`의 `graph_revision,status` 조회 결과는 0행이다.

## 확인하지 못한 것
- `demo` tenant의 `agent_runs` 비어 있지 않은 실행 행은 확인하지 못했다.
