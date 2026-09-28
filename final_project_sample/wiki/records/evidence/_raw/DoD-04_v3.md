# DoD-04 재측정 원문

## 재현 명령

fake classifier와 fake Team을 주입한 앱에 REST Case 생성 요청을 보내고 다음을 조회했다.

```text
POST /v1/cases
SELECT run_id, graph_revision, status FROM agent_runs WHERE tenant_id='<measurement>' AND case_id='<created case_id>' ORDER BY started_at;
SELECT DISTINCT graph_revision FROM agent_runs WHERE tenant_id='<measurement>' AND case_id='<created case_id>';
CaseService.checkpoint(..., node_name='measurement', runtime_state={'case_version':4})
```

## 실제 출력

```text
DOD04_rest_status= 201
DOD04_rest_body= {'case_id': 'fe8c928c-0623-400f-9da5-5c04763fac79', 'status': 'resolved', 'version': 4, 'intent': 'billing', 'issue_code': 'payment_failed', 'sentiment': 'negative', 'links': {'self': '/v1/cases/fe8c928c-0623-400f-9da5-5c04763fac79'}, 'run_id': 'b15a6f96-7255-4c30-a8ec-1978b5162ad4', 'next_action': 'respond', 'resume_token': None}
DOD04_agent_runs= [('b15a6f96-7255-4c30-a8ec-1978b5162ad4', 'measurement-v3', 'succeeded')]
DOD04_graph_revision_values= ['measurement-v3']
DOD04_distinct_graph_revision= 1
DOD04_checkpoint_keys= ['case_id', 'run_id', 'graph_revision', 'node_name', 'runtime_state']
```

## 관측 사실

- REST 응답 상태 코드는 `201`이었다.
- 조회된 `agent_runs` 행은 1개였다.
- `graph_revision` 출력값은 `measurement-v3` 1개였고 distinct 개수는 `1`이었다.
- checkpoint 키 출력 순서는 `case_id`, `run_id`, `graph_revision`, `node_name`, `runtime_state`였다.

## 확인하지 못한 것

- 외부 LLM 호출은 하지 않았다. fake classifier와 fake Team을 주입했다.

