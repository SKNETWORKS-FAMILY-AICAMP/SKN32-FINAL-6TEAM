# S-CTRL resume 수정 리포트

## 1. 변경 내용

수정 대상은 `app/application/controller.py` 한 곳이다.

- `Controller.run_case()`가 Case 상태가 `resuming`인지 확인한다.
- `wait_reason`을 `RESUME_NODE_FOR_WAIT[wait_reason]`으로 변환한다.
- Team 결과를 적용하기 전에 `EventType.RESUMED`를 발행해 `resuming(5) → running(6)`으로 전이한다.
- 최신 Case를 다시 읽고 TeamTask에 `resume=True`, `resume_node`를 전달한다.
- 전이표, 테스트, 기타 소유 범위 밖 코드는 변경하지 않았다.

## 2. 시나리오 전이 순서

시나리오 1 (승인 후 재개):

```text
classifying(1) → routing(2) → running(3) → waiting_approval(4) → resuming(5) → running(6) → resolved(7)
```

시나리오 2 (읽기 전용 entitlement 불일치):

```text
classifying(1) → routing(2) → running(3) → resolved(4)
```

## 3. 검증 명령 실제 출력

### `python -m pytest tests -q`

```text
........................................................................ [ 67%]
......FFF..........................                                      [100%]
3 failed, 104 passed, 2 warnings in 30.56s
```

실패한 3건은 모두 기존 RAG 통합 테스트이며 `api.openai.com` 임베딩 호출이 샌드박스 네트워크 차단으로 실패했다.

```text
FAILED tests/integration/rag/test_rag_integration.py::test_search_relevance[해지했는데 결제가 됐어요-doc_06]
FAILED tests/integration/rag/test_rag_integration.py::test_search_relevance[Pro로 바꿨는데 기능이 안 보여요-doc_14]
FAILED tests/integration/rag/test_rag_integration.py::test_tenant_isolation_and_scope_filter
httpx.ConnectError: [WinError 10013] 액세스 권한에 의해 숨겨진 소켓에 액세스를 시도했습니다
```

### `python -m pytest tests/integration/controller -v`

```text
============================= test session starts =============================
collecting ... collected 8 items
tests/integration/controller/test_controller_integration.py::test_e2e_cancelled_customer_post_charge_approval_flow PASSED [ 12%]
tests/integration/controller/test_controller_integration.py::test_e2e_free_pro_entitlement_mismatch_is_read_only PASSED [ 25%]
tests/integration/controller/test_controller_integration.py::test_replay_case_is_projection_equivalent PASSED [ 37%]
tests/integration/controller/test_controller_integration.py::test_transition_exception_rolls_back_event_and_outbox PASSED [ 50%]
tests/integration/controller/test_controller_integration.py::test_outbox_duplicate_is_delivered_once PASSED [ 62%]
tests/integration/controller/test_controller_integration.py::test_resume_token_is_single_use_expiring_and_hashed PASSED [ 75%]
tests/integration/controller/test_controller_integration.py::test_loop_guard_rejects_same_tool_and_arguments PASSED [ 87%]
tests/integration/controller/test_controller_integration.py::test_same_expected_version_has_one_success_and_one_state_conflict PASSED [100%]
============================== 8 passed, 1 warning in 17.89s ========================
```

### `python -m scripts.run_outbox_worker --once`

```text
```

Exit code: `0`

### PostgreSQL tenant count

```text
tenants=1
```

