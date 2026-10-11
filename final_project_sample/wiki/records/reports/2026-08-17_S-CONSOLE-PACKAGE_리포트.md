# S-CONSOLE-PACKAGE 결과

## 범위

`app/console/`을 선택적 개발 콘솔 진입점으로 만들고, `mount_ui()`의 콘솔
import를 enabled 조건 안으로 지연했다. 기존 고객사 `/ops` 구현과 금지된
basement/domain/application/infrastructure 파일은 변경하지 않았다.

호환성을 위해 기존 `app.presentation.ui.console`·`composer` 모듈은 남겨
두었지만, 새 mount 배선은 `app.console` 진입점을 사용한다. `app.console`
theme은 현재 공용 renderer를 재사용한다.

## 고정한 읽기 계약

상세 표는 [`11_콘솔_읽기_계약.md`](../handoff/11_콘솔_읽기_계약.md)에 있다.
계약 테스트는 실제 `config/project.yaml`, `wiki/records/evidence/DoD-*.md`,
`eval/reports/*.jsonl`을 읽는다. DB 계약은 실제 PostgreSQL의
`information_schema.columns`를 읽어 `agent_runs`, `team_tasks`, `llm_calls`,
`case_events` 컬럼을 확인한다. 각 파일 계약에는 필드 삭제·이름 변경
negative fixture가 있다.

## 설치 대상

`pyproject.toml`에 제품 메타데이터와 `console` optional extra를 추가했다.
같은 저장소에서 제품 wheel은 `app.console`을 제외하고, 콘솔 wheel은
`FINAL_PROJECT_INCLUDE_CONSOLE=1` build flag를 사용하는 방식을 의도했다.
Python의 extras는 이미 만들어진 wheel의 파일 목록을 바꾸지 못하므로,
설치 명령만 바꾸는 것으로는 “코드가 없다”를 보장할 수 없다.

`python -m build`는 환경에 `build` 모듈이 없어 실행하지 못했지만,
동일한 setuptools backend를 사용하는 `pip wheel --no-build-isolation`로
clean product/console 대상을 각각 만들었다. product wheel은
`app/console/*` 0개, console build는 5개였고 product metadata에는
`Provides-Extra: console`이 포함됐다.

## 검증 출력

```text
python -m pytest tests/architecture -q
67 passed

python -m pytest tests/contracts -q
4 passed

python -m pytest tests -q
314 passed, 3 failed, 1 deselected
```

실패 3건은 기존 `tests/integration/rag/test_rag_integration.py`의 OpenAI
embedding 호출이며, 샌드박스에서 `api.openai.com` 네트워크가 차단되어
`httpx.ConnectError`가 발생했다.

실행 smoke:

```text
ui=200
ops=200
```

서버 프로세스는 smoke 직후 종료했다. 콘솔 disabled 계약에서는
`/ui/`가 404이고 `/ops/cases`가 200이며, `app.console` import를 시도하지
않는 테스트도 통과한다.

## 발견한 결함

- 기존 콘솔 코드가 고객 UI `routes.py`와 같은 모듈에 남아 있어 완전한 소스
  이동은 금지된 파일을 건드리지 않고는 끝낼 수 없다. 그래서 허용 범위 안에서
  optional 진입점과 lazy import를 먼저 분리했다.
- 콘솔 전용 theme 조각은 아직 공용 `app.presentation.ui.theme`을 재사용한다.
- 현재 환경의 build cache 때문에 artifact 파일 목록 검증은 CI의 clean
  workspace에서 한 번 더 확인해야 한다.
