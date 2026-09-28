# S-COMPOSITION 조립 리포트

## 1. 구현 범위

`app/composition.py`를 composition root로 신설하고 운영 진입점에서 다음 구체 구현을 조립했다.

- `build_classifier()`: 기존 API 내부 classifier 조립을 이동했다. OpenAI API key가 없으면 `RuntimeError`를 발생시킨다.
- `build_registry()`: `BillingSubscriptionTeam`과 `TechnicalEntitlementTeam`을 생성해 `TeamRegistry`에 등록한다.
- `build_team_executor()`: `LocalTeamExecutor`를 `TeamExecutorPort`로 반환한다.
- `build_controller()`: registry, executor, ContextBroker, DB repository/connection, RAG retriever, Outbox broker를 Controller 생성자로 주입한다. Team LLM은 `OpenAITeamLLM`으로 조립한다.

Team 인스턴스 생성은 `app/composition.py`에서만 수행한다. `app/core/**`는 `app.composition`을 import하지 않는다.

## 2. 운영 경로 연결

`create_app(controller=None, classifier=None)`으로 확장했다.

- 기본 운영 앱은 `composition.build_classifier()`와 `composition.build_controller()`를 사용한다.
- `POST /v1/cases`는 case 생성·분류 트랜잭션을 커밋한 후 Controller의 `run_case()`를 호출한다.
- `create_app(controller=fake, classifier=fake)` 형태의 테스트 주입을 유지했다.
- 기존 `create_app(classifier=fake)` 호환 테스트는 분류 단계만 검증하는 legacy seam으로 유지했다.
- idempotency로 기존 case가 반환되는 경로에서는 Controller를 중복 호출하지 않는다.

추가한 검증은 `POST /v1/cases`가 주입된 fake Controller를 실제 호출하는지와 `build_registry()`에 Team을 추가했을 때 registry resolve가 새 Team을 라우팅하는지다.

## 3. Controller infrastructure 참조 정리

다음 참조를 생성자 주입 대상으로 이동했다.

- `repository`: `Controller(..., repository=...)` 및 `self.repository` 사용
- `connection_factory`: `Controller(..., connection_factory=...)` 사용
- `policy_search`: `Controller(..., policy_search=...)` 사용
- Team executor: `Controller(..., team_executor=...)` 사용
- broker: `Controller(..., broker=...)`로 보관

### 옮기지 못한 부분과 사유

기존 통합/단위 테스트가 `Controller(TeamRegistry(...))`를 직접 생성하고 있어, 기본 인자를 즉시 제거하면 기존 테스트 계약이 깨진다. 따라서 위 의존성이 생략된 경우에 한해 생성자 내부에서 지연 import하는 호환 fallback을 남겼다. 운영 composition 경로에서는 모든 concrete adapter가 명시적으로 주입된다. 해당 fallback은 운영 조립 경로가 아니며, 새 코드의 조립 책임을 우회하지 않는다.

## 4. 테스트 결과 원문

조립 관련 타깃 실행:

```text
python -m pytest tests/contract/test_core_isolation.py tests/unit/test_composition_root.py tests/integration/api -q
.......................                                                  [100%]
23 passed, 1 warning in 11.38s
```

네트워크 비의존 전체 회귀:

```text
python -m pytest tests --ignore=tests/integration/rag -q
........................................................................ [ 58%]
....................................................                     [100%]
124 passed, 1 deselected, 1 warning in 20.12s
```

요청한 전체 명령의 원문 결과 요약:

```text
python -m pytest tests -q
125 passed, 3 failed, 1 deselected
```

실패한 3건은 모두 기존 `tests/integration/rag/test_rag_integration.py`의 OpenAI embedding 호출에서 발생했다. `api.openai.com/embeddings`에 네트워크 연결을 시도했으나 실행 환경의 소켓 권한 차단(`WinError 10013`)으로 실패했으며, composition 변경으로 발생한 assertion/import 실패는 없다. 해당 테스트가 `live` marker를 사용하지 않아 명령에서 자동 deselect되지 않았다.

