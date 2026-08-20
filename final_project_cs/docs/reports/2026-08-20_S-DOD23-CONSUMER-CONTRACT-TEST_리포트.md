# S-DOD23-CONSUMER-CONTRACT-TEST 리포트

## 결과

재사용 가능한 consumer idempotency contract test를 추가하고 현재
`OutboxWorker`를 첫 번째 parameterized consumer로 등록했다.

- 변경 전 기준선: 사용자가 제시한 기준은 `329 passed, 0 failed`였으나, 이
  환경의 실제 실행은 `320 passed, 4 failed, 11 errors, 3 deselected`였다.
- 신규 계약 테스트: `3 passed`.
- 구현 변경: 새 consumer를 만들지 않았고 `worker.py`와
  `docs/evidence/DoD-23_consumer_idempotency.md`는 수정하지 않았다.

## 계약 범위

`tests/contract/test_consumer_idempotency_contract.py`는 다음을
parameterized consumer fixture에 대해 검사한다.

1. 동일 `dedupe_key` 2회 처리 → side effect 1회
2. 동시 claim race → side effect 1회
3. timeout → `unknown`, attempts 1, 자동 재실행 없음

새 consumer는 `consumer_contract_factories`에 동등한 adapter를 등록하고
동일 계약을 통과해야 한다. 개발자용 규칙은
`docs/handoff/12_메시지_컨슈머_멱등성_계약.md`에 기록했다.

## 전체 검증 명령

```powershell
python -m pytest -q -m "not live"
```

### 변경 전 실제 출력

```text
4 failed, 320 passed, 3 deselected, 11 errors in 39.93s
```

실패/오류는 신규 변경과 무관한 기존 환경 상태였다. 주요 원인은 OpenAI
네트워크 차단, pytest temp/cache 디렉터리 권한 거부, 기존 architecture
검사 실패다.

### 변경 후 실제 출력

```text
.............................................................................. [ 21%]
..........................................................EEEEEEEEEE..... [ 42%]
.............................................................................. [ 63%]
FF............................................................................ [ 85%]
..................................................                           [100%]
3 failed, 324 passed, 3 deselected, 11 errors in 43.83s
```

전체 실행의 실패 목록은 다음과 같다.

```text
FAILED tests/integration/rag/test_rag_integration.py::test_search_relevance[배송완료로 뜨는데 못 받았어요-doc_01]
FAILED tests/integration/rag/test_rag_integration.py::test_search_relevance[주문은 3개인데 반품을 5개 신청했어요-doc_14]
FAILED tests/integration/rag/test_rag_integration.py::test_tenant_isolation_and_scope_filter
ERROR eval/tests/test_holdout_labeling.py::test_template_with_predictions_fills_candidate_answer
ERROR tests/e2e/test_composer_write_channel.py::test_requires_authentication
ERROR tests/e2e/test_composer_write_channel.py::test_wrong_scope_is_rejected
ERROR tests/e2e/test_composer_write_channel.py::test_write_channel_survives_ops_ui_being_disabled
ERROR tests/e2e/test_composer_write_channel.py::test_validate_does_not_write_the_file
ERROR tests/e2e/test_composer_write_channel.py::test_apply_rejects_unimplementable_reference
ERROR tests/e2e/test_composer_write_channel.py::test_apply_writes_an_audit_event_with_actor_and_revision
ERROR tests/e2e/test_composer_write_channel.py::test_expired_token_is_rejected
ERROR tests/e2e/test_composer_write_channel.py::test_forged_signature_is_rejected
ERROR tests/e2e/test_composer_write_channel.py::test_token_issue_and_current_endpoint
ERROR tests/e2e/test_composer_write_channel.py::test_concurrent_apply_one_wins_one_gets_409
```

## pass 수 변화

실제 환경 기준으로 `320 passed`에서 `324 passed`로 `+4 passed` 변했다.
실패는 `4`에서 `3`으로 `-1 failed` 변했고, 오류는 `11`로 유지됐다.
사용자 제공 기준선 `329 passed, 0 failed`과의 차이는 실행 환경의 기존
실패/오류를 포함한 것이다. 신규 계약 테스트 3개는 별도 실행에서
`3 passed`였다.
