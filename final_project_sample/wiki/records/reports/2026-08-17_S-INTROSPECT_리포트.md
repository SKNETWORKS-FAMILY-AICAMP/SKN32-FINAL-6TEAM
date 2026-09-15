# S-INTROSPECT 구현 리포트

## 변경 범위

- `app/introspection/contract.py`에 `contract_version: "1.0"` 기반 read-only 제품 상태 projection을 추가했다.
- 구성 revision, 모듈 on/off, Port 선택, Team manifest 요약, 조립된 executor 이름, guardrails, LLM 메타데이터를 plain data로 반환한다.
- API key 원문은 반환하지 않고 `sk-****` 또는 `missing`으로 마스킹한다.
- `app/console/admin.py`는 composition 조립을 직접 호출하지 않고 introspection projection을 소비한다.
- `app/console/{console,composer,theme}.py`는 실제 콘솔 구현을 보유하며 `app.console.theme`를 사용한다.
- 제품 wheel은 `app/console`을 제외하고, `FINAL_PROJECT_INCLUDE_CONSOLE=1` wheel은 포함한다.

## 검증 출력

패키지 빌드 임시 디렉터리: `C:\Users\PLAYDA~1\AppData\Local\Temp\s-introspect-build`.

```text
product wheel: app/console present = False
console wheel: app/console present = True
```

```text
python -m pytest tests/console tests/contracts/test_introspection_contract.py -q
4 passed
```

콘솔 관련 회귀 범위도 확인했다.

```text
python -m pytest tests/console tests/contracts/test_introspection_contract.py tests/e2e/test_console_dashboard.py tests/e2e/test_composer_structure.py -q
25 passed
```

전체 테스트 실행 결과:

```text
python -m pytest tests -q
316 passed, 3 failed, 1 deselected
```

실패한 3건은 기존 RAG 통합 테스트가 `api.openai.com` embeddings를 호출해 샌드박스 네트워크 정책으로 차단된 건이다. 변경 영역 테스트 실패는 없었다.

```text
ops=200
```

Uvicorn으로 `app.presentation.api.app:app --port 8057`을 기동한 뒤 `/ops/cases`를 조회했다.

Negative fixture 실행도 실제 실패를 확인했다.

```text
NEGATIVE_FIXTURE_FAILED_AS_EXPECTED: ProjectConfigError:
... ports.graph_store ... Field required ...
```

이 fixture는 `ports.graph_store` 필드를 제거한 프로젝트 선언이며 canonical loader가 거부했다.
