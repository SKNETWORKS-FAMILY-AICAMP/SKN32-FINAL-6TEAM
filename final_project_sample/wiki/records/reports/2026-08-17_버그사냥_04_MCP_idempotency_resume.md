# 버그사냥 04 — MCP·idempotency·resume

### `app/presentation/api/cases.py:214-224` — MCP open_support_case가 같은 논리 요청을 매번 새 Case로 만든다
- 시나리오: 같은 `customer_id`, `message`, `channel`로 `open_support_case`를 두 번 호출한다. 216행에서 동일한 request_id를 계산하지만 이후 사용하지 않고, 221행에서 매번 `create_case()`를 호출한다. 따라서 같은 MCP 재시도 요청이 서로 다른 Case 두 개가 된다. 또한 `CreateCase`의 idempotency 키나 `action_requests` 조회·기록도 하지 않는다.
- 왜 기존 테스트가 못 잡는가: `tests/integration/api/test_api_runtime.py:137-150`과 `:213-224`는 호출 후 Case가 하나 생기고 `action_requests/payments/subscriptions`가 변하지 않는지만 본다. 동일 인자로 두 번 호출해 Case 수와 반환 ID가 달라지는지 검증하지 않는다. MCP tool metadata의 `mcp:read` 검사와 실제 Case 생성 경로도 서로 다른 테스트가 본다.
- 재현 시도: 재현 안 해봄, 코드 읽기로만 판단. `request_id`가 계산되지만 사용되지 않고 `create_case()`가 무조건 실행되는 코드 경로가 확인된다.
- 위험도: 높음

### `app/presentation/api/cases.py:116-126` — messages 엔드포인트가 resume token 없이 임의 입력으로 대기 Case를 재개한다
- 시나리오: `case:write` Principal이 `POST /v1/cases/{case_id}/messages`에 임의의 `request_id`와 `message`를 보낸다. 이 엔드포인트는 `CaseService.validate_resume()`를 호출하지 않고, message의 SHA-256을 `resume_token_hash`로 넣은 `VALID_INPUT` 이벤트를 바로 발행한다. 실제 resume token을 몰라도 `waiting_input → resuming` 전이가 가능하며, 24시간 만료와 일회성 사용도 이 REST 경로에서는 강제되지 않는다.
- 왜 기존 테스트가 못 잡는가: `tests/integration/controller/test_controller_integration.py:324-338`은 `CaseService.validate_resume()`만 손으로 만든 `case`에 대해 테스트하고, `app/application/controller.py:259-280`의 Controller resume 경로도 별도로 테스트한다. 반면 REST messages 테스트(`tests/integration/api/test_api_runtime.py:202-210`)는 대기 상태가 아닌 Case에서 `expected_version` 충돌만 확인해 실제 핸들러 입력과 token 검증을 연결하지 않는다.
- 재현 시도: 재현 안 해봄, 코드 읽기로만 판단. 핸들러에 token 필드가 없고 `validate_resume()` 호출도 없음을 확인했다.
- 위험도: 높음

### `app/application/case_service.py:68-75` — 같은 event_id면 만료·재사용 token 검사를 건너뛴다
- 시나리오: 이전 resume에서 `last_resume_event_id`가 저장된 Case에 대해, 만료됐거나 이미 `resume_token_used=True`인 token과 같은 `event_id`를 다시 `Controller.resume()`에 전달한다. `validate_resume()`는 token hash·사용 여부·expiry를 보기 전에 70-71행에서 `idempotent`를 반환하므로, 만료·재사용 token도 유효한 재시도로 받아들인다. 현재는 재실행 대신 idempotent 응답이지만, “24h TTL·일회성” 검증이 해당 경로에서 사실상 우회된다.
- 왜 기존 테스트가 못 잡는가: `tests/integration/controller/test_controller_integration.py:324-338`은 정상 token 뒤에 `resume_token_used=True` 또는 만료 시각을 넣지만 `event_id`를 주지 않는다. `event_id`가 이미 저장된 상태에서 만료·재사용을 함께 검사하는 테스트가 없다.
- 재현 시도: 재현 안 해봄, 코드 읽기로만 판단. `event_id` early return이 expiry/used 검사보다 앞선 것을 확인했다.
- 위험도: 보통

### `app/core/idempotency.py:8-11` — 구분자 없는 문자열 결합으로 서로 다른 요청이 같은 key가 될 수 있다
- 시나리오: `(tenant_id="ab", request_id="c", action_type="d", business_subject="e")`와 `(tenant_id="a", request_id="bc", action_type="d", business_subject="e")`는 서로 다른 논리 요청이지만 10행의 결합 결과가 모두 `abcde`라 같은 SHA-256 key를 낸다. 필드에 공백·대소문자·표현형 차이가 있어도 정규화하지 않아 호출자가 다른 입력 형태를 쓰면 같은 논리 요청이 중복 key가 되거나 반대로 다른 key가 될 수 있다.
- 왜 기존 테스트가 못 잡는가: `tests/integration/controller/test_controller_integration.py:216-223`은 action_type과 business_subject를 각각 바꿨을 때 key가 달라지는지만 확인한다. 경계가 모호한 필드 분할이나 실제 API가 전달하는 UUID/string·공백·대소문자 입력을 함수 테스트와 함께 검증하지 않는다.
- 재현 시도: 실제 함수의 동일 결과를 확인했다. 두 입력의 결합 문자열이 모두 `abcde`이므로 SHA-256 결과도 동일하다.
- 위험도: 보통

## 검증

코드는 수정하지 않았다. `python -m pytest -q` 실행 결과는 `338 passed, 3 failed, 1 deselected`였다. 실패 3건은 `tests/integration/rag/test_rag_integration.py`의 OpenAI embeddings 호출이 `api.openai.com` 연결 권한 오류(`WinError 10013`)로 실패한 것이며, 이번 작업의 소스 변경으로 발생한 실패는 확인되지 않았다.
