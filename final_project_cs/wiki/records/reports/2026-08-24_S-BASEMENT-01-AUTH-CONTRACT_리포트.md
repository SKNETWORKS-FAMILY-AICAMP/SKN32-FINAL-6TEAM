# S-BASEMENT-01-AUTH-CONTRACT 구현 리포트

작성일: 2026-08-24

## 적용 내용

### 1. resume 토큰 인증

`POST /v1/cases/{case_id}/messages`는 더 이상 고객 메시지를 토큰 해시로 사용하지 않는다. 요청에 `token`을 필수로 받고, 실제 발급 토큰을 `Controller.resume()`에 전달한다. Controller가 `CaseService.validate_resume()`를 통해 저장된 해시, 만료, single-use를 검증하며, 실패는 `invalid_resume_token`(401)으로 반환한다. `controller.py`의 WAIT_EXPIRED/commit 로직은 수정하지 않았다.

재현 회귀 테스트:

- `test_message_route_passes_issued_resume_token_to_controller`: 메시지 본문이 `issued-token`이어도 요청 token이 위조이면 401이고, 실제 token만 Controller로 전달되는지 확인한다.
- 수정 전 구현은 메시지 본문을 SHA-256 해시해 직접 `VALID_INPUT`을 발생시켰으므로 이 계약을 만족하지 못한다.

### 2. MCP `open_support_case` 멱등성

MCP 요청 ID를 기반으로 REST와 동일한 원리의 dedupe key를 계산하고, `action_requests`를 먼저 조회한다. 기존 행이 있으면 기존 Case를 반환하며, 신규 요청만 Case와 `mcp.open_support_case` 감사 행을 생성한다.

`test_same_mcp_open_request_ten_times_has_one_case_and_action_request`에서 동일 요청 10회가 Case 1개와 action_requests 1행인지 확인한다.

### 3. Team tool-scope

`LocalTeamExecutor.execute()`가 Registry에서 가져온 manifest의 `allowed_tools`와 `task.allowed_tools`를 비교한다. task scope가 manifest scope의 부분집합이 아니면 `ToolScopeViolation`을 발생시키고 Team module을 호출하지 않는다. 정상 Controller 경로처럼 manifest scope를 그대로 전달하는 호출은 유지된다.

`test_local_executor_rejects_task_tools_outside_manifest`와 기존 direct-call 동등성 테스트로 거부·정상 흐름을 모두 확인한다.

## 변경 파일

- `app/presentation/api/cases.py`
- `app/core/remote_team/executor.py`
- `app/core/remote_team/__init__.py`
- `tests/integration/api/test_api_runtime.py`
- `tests/unit/ports/test_team_ports.py`

`final_project_sample/`은 읽기만 했으며 수정하지 않았다. `app/application/controller.py`도 수정하지 않았다.

## 검증 결과

### 관련 targeted suite

```text
23 passed, 1 warning in 17.11s
```

### 요청한 전체 비-live suite

저장소 내부의 pytest 임시 디렉터리를 사용해 환경의 전역 Temp 권한 문제를 피한 재실행 결과다. 명령의 테스트 선택 조건은 요청과 동일하다.

```text
python -m pytest -q -m "not live" --tb=no --basetemp .pytest-basetemp
...
=========================== short test summary info ===========================
FAILED tests/integration/api/test_openapi_surface.py::test_v1_surface_is_documented_when_it_grows
FAILED tests/integration/rag/test_rag_integration.py::test_search_relevance[\ubc30\uc1a1\uc644\ub8cc\ub85c \ub5a4\ub370 \ubabb \ubc1b\uc558\uc5b4\uc694-doc_01]
FAILED tests/integration/rag/test_rag_integration.py::test_search_relevance[\uc8fc\ubb38\uc740 3\uac1c\uc778\ub370 \ubc18\ud488\uc744 5\uac1c \uc2e0\uccad\ud588\uc5b4\uc694-doc_14]
FAILED tests/integration/rag/test_rag_integration.py::test_tenant_isolation_and_scope_filter
4 failed, 369 passed, 3 deselected, 20 warnings in 49.52s
```

실패 원인:

- OpenAPI 테스트: 이번 작업과 무관한 기존 문서 누락 `/v1/outbox/{message_id}/resolve`.
- RAG 3건: `not live` 선택에도 OpenAI embeddings 외부 호출을 수행하며, 실행 환경의 네트워크 정책에서 `api.openai.com` 연결이 차단됨.

추가로 사용자가 지정한 옵션을 그대로 실행한 첫 시도에서는 전역 pytest Temp 디렉터리 접근 거부가 다수 발생했다. 이후 `--basetemp .pytest-basetemp`로 재검증했고, 변경 관련 targeted suite는 전부 통과했다.
