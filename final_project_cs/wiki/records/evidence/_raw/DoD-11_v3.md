# DoD-11 재측정 원문

## 재현 명령

```powershell
python -m pytest tests\integration\api tests\integration\controller -v
git grep -n -i "provider.*timeout\|timeout.*provider\|unknown" -- app tests scripts
```

fake Team을 주입한 별도 tenant에 동일 생성 요청을 10회 보내고 `action_requests`를 DB에서 조회했다. 첫 실행은 approval을 반환하게 하고 approve REST 요청 뒤 Controller를 다시 실행했다.

## 실제 출력

```text
collecting ... collected 33 items
tests/integration/api/test_api_runtime.py ... PASSED [ 63%]
tests/integration/api/test_openapi_surface.py ... PASSED [ 63%]
tests/integration/controller/test_controller_integration.py ... PASSED [100%]
======================== 33 passed, 1 warning in 12.21s =========================
DOD11_same_request_statuses= [201, 201, 201, 201, 201, 201, 201, 201, 201, 201]
DOD11_action_requests_count= 2
DOD11_before_approve= ('waiting_approval', 4)
DOD11_approve_body= {'case_id': '5d069b9d-737a-44fe-a379-3fc2b6a1bed5', 'status': 'resuming', 'version': 5, 'intent': 'billing', 'issue_code': 'payment_failed', 'sentiment': 'negative', 'links': {'self': '/v1/cases/5d069b9d-737a-44fe-a379-3fc2b6a1bed5'}}
DOD11_after_approve_db= ('resuming', 5)
DOD11_resume_body= {'case_id': '5d069b9d-737a-44fe-a379-3fc2b6a1bed5', 'run_id': '64df1221-42b0-49c5-ad17-d098524c4f39', 'status': 'resolved', 'version': 7, 'next_action': 'respond', 'resume_token': None}
DOD11_after_resume_db= ('resolved', 7)
DOD11_event_versions= [('created', 1), ('classified', 2), ('routed', 3), ('approval_required', 4), ('approved', 5), ('resumed', 6), ('completed', 7)]
app/infrastructure/messaging/worker.py:28: UPDATE outbox SET status='unknown' ...
app/infrastructure/db/migrations/001_schema.sql:8: CREATE TYPE action_status AS ENUM (...,'unknown',...)
```

## 관측 사실

- 통합 명령은 `33`개 항목을 수집했고 마지막 집계는 `33 passed, 1 warning in 12.21s`였다.
- 동일 요청 10회의 HTTP 상태 코드는 모두 `201`이었다.
- 해당 Case의 `action_requests` 행 수는 `2`였다.
- 상태·버전 출력 순서는 `waiting_approval/4`, `resuming/5`, `resolved/7`이었다.
- event aggregate version 출력은 `1`부터 `7`까지였다.
- `git grep` 출력에는 worker의 `status='unknown'` 업데이트와 DB enum의 `unknown` 값이 있었다.

## 확인하지 못한 것

- 실제 provider 네트워크 timeout을 발생시키는 호출은 하지 않았다.

