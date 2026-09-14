# S-CONFIGVALIDATE 검증 보강 리포트

## 변경 내용

`active: true` 팀의 `implementation_ref` 검증 책임을 `app/core/project_config.py`의 `_load()` 직후로 두었다.

- `package.module:Class` 형식을 정규식으로 검사한다.
- `importlib.import_module()`과 동적 속성 조회로 실제 모듈과 클래스를 확인한다.
- 대상이 클래스인지 확인하고, 클래스 수준에서 `manifest`와 `execute`가 모두 있는지 확인한다.
- 실패는 `ProjectConfigError`로 올리며 `team_id`, 원본 ref, 실패 원인을 메시지에 포함한다.
- `active: false` 팀은 위 검증 루프에서 즉시 건너뛴다.

검증을 `composition.py`가 아니라 `project_config.py`에 둔 이유는 GUI 저장 결과물인 YAML을 `load_project_config()`하는 시점에 조기에 실패시키기 위해서다. `composition.py`의 기동 시점 검증은 그대로 유지된다.

## Core 격리

Core에 `app.modules`를 정적으로 import하지 않았다. `project_config.py`는 표준 `importlib`만 import하고 문자열 ref를 동적으로 해석한다. 따라서 `tests/contract/test_core_isolation.py`의 AST 기반 금지 import 규칙을 만족한다.

## 테스트

추가한 검증 테스트는 활성+없는 모듈, 활성+없는 클래스명, 활성+계약 불충족, 비활성+없는 모듈, 정상 `config/project.yaml`을 다룬다.

```text
python -m pytest tests/unit/test_project_composition.py -q
15 passed

python -m pytest tests/contract/test_core_isolation.py -q
1 passed
```

전체 테스트 명령은 현재 환경에서 기존 RAG 통합 테스트 3건이 `api.openai.com` 임베딩 호출의 네트워크 권한 차단으로 실패했다.

```text
python -m pytest tests -q
144 passed, 3 failed, 1 deselected
실패: tests/integration/rag/test_rag_integration.py의 기존 검색 테스트 3건
원인: WinError 10013 / OpenAI API 연결 불가
```

RAG 통합 디렉터리를 제외한 나머지는 다음과 같이 통과했다.

```text
python -m pytest tests -q --ignore=tests/integration/rag
143 passed, 1 deselected
```

## 4종 직접 검증 원문

요구된 import 불가 ref 재현의 결과:

```text
거부: ProjectConfigError team 't1' implementation_ref 'app.nonexistent:Missing' cannot be imported: No module named 'app.nonexistent'
```

동일한 로더로 4종을 각각 실행한 결과:

```text
[거부] duplicate team_id ProjectConfigError: ... duplicate team_id in project declaration: t1 ...
[거부] import invalid ref ProjectConfigError: team 't1' implementation_ref 'app.nonexistent:Missing' cannot be imported: No module named 'app.nonexistent'
[거부] unsupported port ProjectConfigError: ... ports.graph_store ... Input should be 'sql', 'age' or 'neo4j' ...
[거부] missing schema ProjectConfigError: ... teams ... Field required ...
```

따라서 기존에 통과하던 import 불가 ref도 `load_project_config()` 단계에서 명시적으로 거부된다.
