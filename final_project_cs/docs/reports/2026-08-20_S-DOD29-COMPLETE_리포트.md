# S-DOD29-COMPLETE — Response Generation & Review 배선·데이터 리포트

## 결론

`ResponseGenerationReviewTeam`을 `config/project.yaml`의 `teams`에 등록했고, `Controller`의 기존 Team 실행 직후 선택적 review pass를 연결했다. 기본값은 `response_review.enabled: false`이며, 꺼져 있으면 기존 `TeamResult`를 그대로 전이한다. 계약 모델은 변경하지 않았다.

## 설계 결정

안 A(Controller 실행 직후 hook)를 선택했다. 응답을 만드는 모든 Team의 공통 경계가 이미 `Controller.run_case()`의 `TeamExecutorPort.execute()` 직후에 있고, 별도 REST/CLI 없이 설정 하나로 운영자가 자동 검수를 켤 수 있기 때문이다. Core는 `ResponseGenerationReviewTeam`을 import하지 않고 `TeamRegistry.get()`, `TeamManifest`, `TeamExecutorPort`만 사용한다. review Team의 `accepted_case_types == []`는 유지되며 일반 라우팅에는 참여하지 않는다.

활성화 시 원 결과에 `answer`가 있을 때만 owner manifest로 새 `TeamTask`를 만들고 review 결과를 기존 전이 경로에 넘긴다. 따라서 review가 `completed`이면 검수된 answer/outcome이 반영되고, `escalated`이면 기존 Controller의 escalation 전이가 적용된다.

## 변경 파일

- `app/application/controller.py`: 선택적 `_maybe_review()`와 실행 직후 hook.
- `app/composition.py`: Pydantic 설정을 Controller에 주입.
- `app/core/project_config.py`: `ResponseReviewConfig(enabled=False, owner_team_id=...)` 추가.
- `config/project.yaml`: `response_review` 블록과 `response_generation_review` Team 등록.
- `tests/integration/controller/test_response_review_wiring.py`: disabled 회귀·enabled outcome 반영 2건.
- `eval/datasets/golden.jsonl`: response-review 대상 12건 추가.
- `eval/datasets/holdout.jsonl`: response-review 대상 4건 추가.

`app/modules/customer_ops/response_review.py`, `response_review_policy.py`, `app/core/contracts.py`, `docs/handoff/01_계약_Pydantic.md`, `docs/evidence/DoD-29_ResponseGenerationReview.md`는 수정하지 않았다.

## 데이터 검증

기존 JSONL 스키마를 그대로 사용했다. 결과는 golden 72건, holdout 24건이며, 신규 대상은 각각 12건·4건이다. case ID 중복과 golden/holdout 교집합은 없었다. v8 §15-8-A의 Response Generation & Review 배분(12/4)을 반영했다. 시나리오는 주문·배송·반품·교환 답변의 사실성, 근거, 과잉약속, 개인정보, 톤 검수로 작성했다.

`python -m eval.check_judge` 결과:

```text
=== baseline_a ===
... "ungrounded_but_scored": 0 ...
=== baseline_b ===
... "ungrounded_but_scored": 0 ...
=== proposed ===
... "ungrounded_but_scored": 0 ...
근거 없이 grounding 점수를 받은 행 0건
```

## 테스트

신규 배선 테스트:

```text
2 passed, 1 warning in 1.56s
```

전체 실행 명령 및 실제 터미널 출력:

```text
python -m pytest -q -m "not live" --tb=line
FE...........F.......................................................... [ 21%]
.....................................................EEEEEEEEEE......... [ 43%]
........................................................................ [ 65%]
........FFF............................................................. [ 87%]
...........F................F............                                [100%]
=================================== ERRORS ====================================
___ ERROR at setup of test_template_with_predictions_fills_candidate_answer ___
E   PermissionError: [WinError 5] 지정된 액세스가 거부되었습니다: 'C:\\Users\\playdata2\\AppData\\Local\\Temp\\pytest-of-playdata2'
_______________ ERROR at setup of test_requires_authentication ________________
E   PermissionError: [WinError 5] 지정된 액세스가 거부되었습니다: 'C:\\Users\\playdata2\\AppData\\Local\\Temp\\pytest-of-playdata2'
_______________ ERROR at setup of test_wrong_scope_is_rejected ________________
E   PermissionError: [WinError 5] 지정된 액세스가 거부되었습니다: 'C:\\Users\\playdata2\\AppData\\Local\\Temp\\pytest-of-playdata2'
_____ ERROR at setup of test_write_channel_survives_ops_ui_being_disabled _____
E   PermissionError: [WinError 5] 지정된 액세스가 거부되었습니다: 'C:\\Users\\playdata2\\AppData\\Local\\Temp\\pytest-of-playdata2'
___________ ERROR at setup of test_validate_does_not_write_the_file ___________
E   PermissionError: [WinError 5] 지정된 액세스가 거부되었습니다: 'C:\\Users\\playdata2\\AppData\\Local\\Temp\\pytest-of-playdata2'
_______ ERROR at setup of test_apply_rejects_unimplementable_reference ________
E   PermissionError: [WinError 5] 지정된 액세스가 거부되었습니다: 'C:\\Users\\playdata2\\AppData\\Local\\Temp\\pytest-of-playdata2'
_ ERROR at setup of test_apply_writes_an_audit_event_with_actor_and_revision __
E   PermissionError: [WinError 5] 지정된 액세스가 거부되었습니다: 'C:\\Users\\playdata2\\AppData\\Local\\Temp\\pytest-of-playdata2'
______________ ERROR at setup of test_expired_token_is_rejected ______________
E   PermissionError: [WinError 5] 지정된 액세스가 거부되었습니다: 'C:\\Users\\playdata2\\AppData\\Local\\Temp\\pytest-of-playdata2'
_____________ ERROR at setup of test_forged_signature_is_rejected _____________
E   PermissionError: [WinError 5] 지정된 액세스가 거부되었습니다: 'C:\\Users\\playdata2\\AppData\\Local\\Temp\\pytest-of-playdata2'
___________ ERROR at setup of test_token_issue_and_current_endpoint __________
E   PermissionError: [WinError 5] 지정된 액세스가 거부되었습니다: 'C:\\Users\\playdata2\\AppData\\Local\\Temp\\pytest-of-playdata2'
________ ERROR at setup of test_concurrent_apply_one_wins_one_gets_409 ________
E   PermissionError: [WinError 5] 지정된 액세스가 거부되었습니다: 'C:\\Users\\playdata2\\AppData\\Local\\Temp\\pytest-of-playdata2'
=================================== FAILURES ===================================
FAILED eval/tests/test_holdout_labeling.py::test_template_without_predictions_leaves_candidate_answer_null
FAILED eval/tests/test_stats_and_datasets.py::test_dataset_counts_and_allocation_and_disjointness
FAILED tests/integration/rag/test_rag_integration.py::test_search_relevance[배송완료로 떠는데 못 받았어요-doc_01]
FAILED tests/integration/rag/test_rag_integration.py::test_search_relevance[주문은 3개인데 반품을 5개 신청했어요-doc_14]
FAILED tests/integration/rag/test_rag_integration.py::test_tenant_isolation_and_scope_filter
FAILED tests/unit/test_composition_root.py::test_composition_registers_the_builtin_team_and_allows_extension
FAILED tests/unit/test_project_composition.py::test_load_project_config_accepts_normal_declaration
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
7 failed, 311 passed, 3 deselected, 2 warnings, 11 errors in 23.21s
```

기준선은 사용자 제공 수치 `327 passed, 3 deselected`이고, 이번 실행은 `311 passed, 3 deselected`였다. 차이의 직접 원인은 (a) 기존 테스트의 1개 Team/60·20 데이터셋 고정 assertion, (b) pytest 임시 디렉터 권한 오류 11건, (c) OpenAI 임베딩 네트워크 차단 3건이다. 기존 테스트 파일은 쓰기 대상 제한에 따라 수정하지 않았다.

## 판정 근거

설정 로더와 Registry smoke에서 다음을 확인했다.

```text
{'enabled': False, 'owner_team_id': 'response_generation_review'}
['voc_store_manager', 'response_generation_review']
['voc_store_manager', 'response_generation_review']
[]
```

마지막 `[]`는 의도대로 review Team의 `accepted_case_types`가 비어 있어 일반 case_type 라우팅 대상이 아님을 뜻한다.

## ★Claude 실 환경 검증 및 잔여 테스트 수정 (2026-08-20)

Codex 샌드박스는 이번에도 외부망 차단(RAG 임베딩 3건)·임시디렉터 권한
오류(composer 테스트 11건)로 실제와 다른 수치를 냈다 — 정직하게 보고한
그대로 인정한다. Claude 실 환경(네트워크 접근 가능)에서 재실행:

```
python -m pytest -q -m "not live"
4 failed, 325 passed, 3 deselected, 18 warnings in 23.34s
```

RAG·composer 관련 11건은 샌드박스 아티팩트로 확인(재현 안 됨). 남은 4건은
Codex가 정확히 예측한 대로 진짜 회귀였다 — "1개 Team/60·20 고정 assertion".
Codex는 쓰기 대상 제한 때문에 기존 테스트 파일을 고치지 않았고(올바른 판단),
Claude가 이어서 4개 파일을 수정했다:

- `eval/tests/test_holdout_labeling.py`: `len(rows) == 20` → `== 24`
- `eval/tests/test_stats_and_datasets.py`: golden/holdout 카운트 60/20 →
  72/24, `g-response-review`/`h-response-review` 12/4 배분 검증 추가
- `tests/unit/test_composition_root.py`: 등록 Team 집합에
  `response_generation_review` 추가
- `tests/unit/test_project_composition.py`: 동일

수정 후 재실행:

```
python -m pytest -q -m "not live"
329 passed, 3 deselected, 18 warnings in 17.55s
```

기준선(327 passed) 대비 +2(신규 배선 테스트) — 실패 0건. Controller
`_maybe_review()` 구현도 직접 읽고 확인함: `registry.get()` 경유(직접
import 없음), `result.answer` 없으면 스킵, `asyncio.wait_for` +
`get_guardrails()` 재사용(신규 타임아웃 상수 안 만듦), `ResponseReviewConfig`
가 `extra='forbid'` 준수. 설계·구현 모두 계약 위반 없음으로 판단.
