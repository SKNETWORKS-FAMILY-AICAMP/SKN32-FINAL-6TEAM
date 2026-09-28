# S-PROJECTYAML 구현 리포트

## 범위

`config/project.yaml`을 조립의 단일 입력으로 만들고, 선언을 읽는 Core 설정 모델과 composition 동적 조립을 추가했다. 변경 범위는 요청된 `config/`, `app/composition.py`, `app/core/project_config.py`, `tests/`, `wiki/records/reports/` 안으로 제한했다.

## 선언 스키마

- `modules`: 모듈 ID별 `{enabled: bool}`. 현재 선언은 `vector_rag`, `graph_store`, `a2a_executor`, `mcp`, `voc`, `ops_ui`, `composer_ui`를 포함한다.
- `ports`: `team_executor`는 `local | a2a`, `message_broker`는 `outbox | redis_streams`, `graph_store`는 `sql | age | neo4j`로 제한한다. Phase 2 값은 선언은 가능하지만 구현 시 명시적으로 실패한다.
- `teams`: `team_id`, `active`, `implementation_ref`를 필수로 한다. 중복 `team_id`는 설정 검증 단계에서 실패한다.

`app/core/project_config.py`는 YAML과 Pydantic만 import한다. `app.modules`, `app.presentation`, `app.infrastructure`는 import하지 않고 `implementation_ref` 문자열만 보관한다. 파일 부재와 YAML/스키마 오류는 `ProjectConfigError` 또는 명시적 검증 오류로 실패하며 기본값 폴백은 없다.

## composition 변경 전후

변경 전 `build_registry()`는 `BillingSubscriptionTeam`, `TechnicalEntitlementTeam`을 직접 import하고 고정 등록했다. 변경 후에는 `load_project_config()`로 선언을 읽고, 각 `implementation_ref`를 `importlib`로 로드해 인스턴스화한 뒤 등록한다.

- 선언의 `active: false`는 구현체 manifest에 그대로 반영되어 manifest에는 남고 `TeamRegistry.resolve()` 라우팅 대상에서는 제외된다.
- 기존 `tools`, `llm`, `registry`, `team_executor`, `broker`, `policy_search_fn` 주입 경로를 유지했다.
- `ports.team_executor`는 `local` 또는 주입된 A2A transport/resolver를 선택한다.
- `build_graph_store()`는 `graph_store.enabled: false`이면 조립하지 않고 명확히 실패한다. `build_broker()`는 현재 `outbox`만 조립한다.

## 빌드 검증 실패 메시지

검증 테스트에서 확인한 대표 메시지는 다음과 같다.

1. enabled 모듈 구현 부재: `enabled module has no implementation: future_module`
2. active Team import 실패: `active team 'billing_subscription' implementation_ref cannot be imported: nope:Missing (...)`
3. 중복 Team/capability: `duplicate team_id in project declaration: ...`, `duplicate capability 'billing.investigate' claimed by teams 'one' and 'two'`
4. 꺼진/미지원 Port: `module 'graph_store' is disabled; cannot assemble GraphStore adapter`, `port graph_store=age is declared but not implemented`, `port message_broker=redis_streams is declared but not implemented`

## 검증 결과

추가한 조립 계약 테스트와 기존 조립/Core 격리 테스트:

```text
11 passed
```

요청된 Registry 확인 명령:

```text
registered: ['billing_subscription', 'technical_entitlement']
```

최종 전체 실행 원문 요약:

```text
3 failed, 138 passed, 1 deselected, 2 warnings in 23.47s
```

실패한 3건은 기존 `tests/integration/rag/test_rag_integration.py`의 OpenAI embedding 호출이며, 이번 조립 변경과 무관하게 `api.openai.com` 네트워크 연결이 정책상 거부되어 `openai.APIConnectionError`가 발생했다. 조립 관련 추가 테스트는 모두 통과했다. `1 deselected`는 기존 `pytest.ini`의 `addopts = -m "not live"`에 따른 live 테스트 제외다.
