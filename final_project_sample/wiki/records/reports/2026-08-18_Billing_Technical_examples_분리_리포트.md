# Billing/Technical 예시 모듈 분리 작업 리포트

## 작업 목표

v8 §10에서 10주 착수 목록에서 제외된 `BillingSubscriptionTeam`과 `TechnicalEntitlementTeam`을 프로덕션 import/config 경로 밖의 `examples/`로 분리했다. 구현 코드는 삭제하지 않고 플러그인 구조 예시로 보존했다.

## 변경 내역

- 이동: `app/modules/customer_ops/billing.py` → `examples/customer_ops/billing.py`
- 이동: `app/modules/customer_ops/technical.py` → `examples/customer_ops/technical.py`
- 추가: `examples/__init__.py`, `examples/customer_ops/__init__.py`
- 업무 로직 테스트 이동: `tests/unit/teams/test_team_scenarios.py` → `examples/tests/test_team_scenarios.py`
- `config/project.yaml`에서 `billing_subscription`·`technical_entitlement` 두 선언을 완전히 삭제. `feedback_analytics` 선언은 유지.
- `app/modules/customer_ops/__init__.py`에서 옛 Team export 제거.
- `.dockerignore`를 추가해 `examples/`가 이미지에 포함되지 않도록 제외.
- `CLAUDE.md`의 Agent Team 행을 예시 보존 상태로 갱신. VOC/Response 행은 수정하지 않음.

## 지정 테스트 분류 및 처리

요청 목록에는 “12개”라고 적혀 있으나 실제 나열된 파일은 10개였다.

### (a) Team 플러그인 계약/조립 검증 — 프로덕션 테스트에 유지

- `tests/contract/test_contracts.py`: Core 계약 fixture의 Team ID를 중립 fixture로 변경.
- `tests/contract/test_team_contract.py`: 현재 production Team인 `feedback_analytics`의 manifest 계약을 검증.
- `tests/e2e/test_composer_ui.py`: 현재 config의 `feedback_analytics`와 테스트용 등록 Team을 사용하도록 변경.
- `tests/e2e/test_introspection_endpoint.py`: 조립 상태 기대값을 `feedback_analytics` 하나로 변경.
- `tests/integration/api/test_api_runtime.py`: 런타임 경로는 중립 `demo_team` fake Team으로 유지.
- `tests/unit/core/test_case_reducer.py`: reducer 계약 fixture의 owner/capability를 중립 값으로 변경.
- `tests/unit/infrastructure/test_graph_v7_axes.py`: 그래프 축 검증의 Team 노드를 `demo_team` fixture로 변경.
- `tests/unit/test_composition_root.py`: built-in 조립 기대값을 `feedback_analytics`로 변경.
- `tests/unit/test_project_composition.py`: active/inactive 조립 동작을 `feedback_analytics`와 fake fixture로 검증.

### (b) 옛 Team 업무 로직 검증 — examples로 이동

- `tests/unit/teams/test_team_scenarios.py`는 구독 해지 후 환불 승인 제안, entitlement 불일치 판정, degraded context escalation, tool allowlist/repetition guard를 검증하므로 `examples/tests/test_team_scenarios.py`로 이동.

## 검증 결과 원문

변경 범위 회귀 테스트:

```text
125 passed, 1 warning in 9.06s
```

전체 테스트 실행 명령:

```text
python -m pytest -q
```

전체 테스트 결과 원문 요약:

```text
........................................................................ [ 19%]
........................................................................ [ 39%]
........................................................................ [ 59%]
.............................................FFF...E.................... [ 79%]
........................................................................ [ 98%]
....                                                                     [100%]
3 failed, 360 passed, 1 deselected, 2 warnings, 1 error in 35.14s
```

실패/오류는 성공으로 간주하지 않았다.

- 3 failures: `tests/integration/rag/test_rag_integration.py`의 3개 테스트. OpenAI embeddings 호출이 현재 실행 환경의 네트워크 권한으로 차단되어 `WinError 10013`/`httpx.ConnectError` 발생.
- 1 error: `tests/unit/application/test_composer_service.py::test_staged_file_is_removed_when_os_replace_fails` setup. pytest 임시 디렉터리 `C:\Users\playdata2\AppData\Local\Temp\pytest-of-playdata2` 접근이 `WinError 5`로 거부됨.

추가로 `pytest --collect-only -q`는 `364/365 tests collected (1 deselected)`를 확인했다.

## 별도 확인 사항

`app/modules/customer_ops/response_review.py`와 `response_review_policy.py`는 이번 작업에서 변경하지 않았다. `response_review.py`의 Response Generation & Review Team은 현재 `config/project.yaml`에 등록되어 있지 않다. 이는 별도 처리 이슈이며, 이번 작업 범위에서는 등록 여부를 건드리지 않았다.

`feedback_team.py`와 `feedback_analytics` config 선언도 변경하지 않았다.
