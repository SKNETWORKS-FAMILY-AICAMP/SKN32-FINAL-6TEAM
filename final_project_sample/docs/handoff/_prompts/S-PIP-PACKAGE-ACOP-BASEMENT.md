# S-PIP-PACKAGE-ACOP-BASEMENT — basement를 `acop_basement` pip 패키지로 전환 (실제 리팩터, 큰 변경)

## 배경 — 최종 목표 아키텍처 (다른 세션에서 확정, 이 저장소는 1/3 담당)

```
sample(이 저장소)   → acop_basement 라는 이름의 pip 설치 가능 패키지를 만드는 소스
final_project_ui   → acop_basement 를 pip install 해서 쓰고, Composer 기능을 전담
final_project_cs   → acop_basement 를 pip install 해서 자기 도메인 Team만 갖는 릴리스 대상
```

지금 `app/`이 이 저장소와 `final_project_cs` 양쪽에서 똑같이 최상위 패키지
이름이라, `final_project_cs`가 `pip install`을 해도 자기 로컬 `app/`이
설치된 패키지를 가려버려 의존성이 성립하지 않는다(2026-08-18 Claude·Codex
자문에서 이미 확인한 사실). 그래서 basement 부분을 `app`이 아닌
`acop_basement`라는 새 최상위 패키지로 옮긴다.

또한 Composer(쓰기 API)는 최종적으로 `final_project_ui`로 이관되므로, 이번
리네임에서 **Composer 전용 3개 파일은 `acop_basement` 패키지 밖으로 뺀다**
(삭제 아님 — 임시 위치에 격리, 최종 이관은 `final_project_ui` 쪽 작업).

이번 세션에 이미 끝낸 선행 작업(그대로 활용해라, 다시 하지 마라):
- `docs/handoff/10` §0 경계표, `tests/architecture/test_basement_is_domain_free.py`
  가 이미 `tools`·`introspection`을 basement로 확정해 놨다(`BASEMENT_DIRS`에
  이미 들어 있다).
- `scripts/basement_manifest.py`의 `BASEMENT_COMPONENTS`가 이미 basement
  5대 컴포넌트 경로를 선언하고 있다 — 이번 스트림에서 `acop_basement/`
  기준으로 갱신해라.

## ★안전 수칙 — 이번 스트림은 저장소 전체에 영향을 준다

- **커밋은 지금 상태(662d23e)가 깨끗한 기준점이다.** 뭔가 크게 잘못돼도
  Claude가 `git diff`로 전체를 검토할 수 있게, **한 번에 끝내려 하지 말고
  단계마다(아래 1→2→3→4) 중간에 `python -m pytest -q --ignore=tests/integration/rag`
  를 돌려서 그 단계가 실제로 안 깨졌는지 확인하고 다음 단계로 가라.**
- **`final_project_cs`·`final_project_ui`·이 저장소 밖의 어떤 디렉터리도
  건드리지 마라.** 이 스트림은 `final_project_sample/` 안에서만 논다.
- 이 저장소가 지금 다른 세션에 의해서도 동시에 편집되고 있을 수 있다
  (`CLAUDE.md`, `app/presentation/ui/**`, `config/project.yaml`,
  `docs/handoff/08`·`09`, `docs/release_checklist.md`, `tests/e2e/test_audience_boundary.py`
  등이 미커밋 상태로 남아 있다 — `git status`로 확인해라). **그 파일들은
  건드리지 마라.** 겹치면(예: `app/presentation/ui/**`가 이번 이동 대상과
  겹친다) 그 파일의 **네 작업(경로 이동)만** 하고 그 파일의 **다른 내용
  변경은 건드리지 마라** — 즉 git 그대로 최신 내용을 유지한 채 위치만
  옮긴다.

## 1단계 — Composer 3파일을 basement 패키지 밖으로 격리

1. 새 디렉터리 `app/composer_staging/`을 만든다. `app/composer_staging/README.md`
   에 짧게 적는다: "이 디렉터리는 `acop_basement` 패키지 경계 밖이다.
   Composer 쓰기 API는 최종적으로 `final_project_ui`로 이관된다
   (2026-08-18 설계 결정). 지금은 로컬 개발·현재 배포에서만 쓰기 위해
   임시로 여기 둔다."
2. 이동:
   - `app/application/composer_service.py` → `app/composer_staging/composer_service.py`
   - `app/presentation/api/composer.py` → `app/composer_staging/api_composer.py`
   - `app/presentation/composer_auth.py` → `app/composer_staging/composer_auth.py`
3. `app/presentation/api/app.py`의 import 3줄만 새 경로로 고친다
   (`from app.composer_staging.composer_service import ...`,
   `from app.composer_staging.api_composer import router as composer_write_router`,
   `from app.composer_staging.composer_auth import router as composer_auth_router`).
   **`create_app()`의 동작(라우터 등록 여부·순서)은 그대로 유지한다** —
   이번엔 옮기기만 한다, 선택적 마운트로 바꾸지 않는다(그건 별도
   "customer-runtime/composer-control 분리" 스트림의 몫이다,
   `docs/plans/2026-08-18_Composer_배포_경계_분리_계획.md` §4 참고).
4. 옛 경로(`app.composer_staging.composer_service`, `app.composer_staging.api_composer`,
   `app.composer_staging.composer_auth`)를 참조하던 **모든** 파일을 새 경로로
   고친다 — `rg -rln "app\.application\.composer_service|app\.presentation\.api\.composer|app\.presentation\.composer_auth"` 로 전부 찾아라(테스트 포함).
5. **여기서 멈춰서 검증**: `python -m pytest -q --ignore=tests/integration/rag`
   가 이 스트림 시작 전과 같은 수(또는 그 근처, 다른 동시 세션 변화는
   제외)로 통과하는지 확인하고 다음 단계로 간다.

## 2단계 — basement 5+2 컴포넌트를 `acop_basement/`로 이동

1. 이동(git mv 사용 권장 — 이동 이력이 남는다):
   - `app/core` → `acop_basement/core`
   - `app/domain` → `acop_basement/domain`
   - `app/application` → `acop_basement/application` (1단계로 이미 비어진 상태)
   - `app/infrastructure` → `acop_basement/infrastructure`
   - `app/presentation` → `acop_basement/presentation` (1단계로 이미 비어진 상태)
   - `app/tools` → `acop_basement/tools`
   - `app/introspection` → `acop_basement/introspection`
   - `acop_basement/__init__.py`(신규, 빈 패키지 마커) 추가
2. **전체 import 경로 일괄 치환**: `from acop_basement.core` → `from acop_basement.core`,
   `import acop_basement.core` → `import acop_basement.core`, 같은 방식으로
   `domain`·`application`·`infrastructure`·`presentation`·`tools`·
   `introspection` 전부. 대상: `app/**`(남은 `app.modules`·
   `app.composition`·`app.composer_staging`), `tests/**`, `eval/**`,
   `scripts/**`, `examples/**`. **`app.modules`는 옮기지 않는다** — 그
   경로 문자열(`app.modules.customer_ops....`)은 안 바뀐다(config/project.yaml
   의 `implementation_ref`도 그대로 둔다 — 도메인은 여전히 `app` 소속).
3. `pyproject.toml`: `[tool.setuptools.packages.find]`의 `include`에
   `"acop_basement*"`를 추가한다(`"app*"`는 유지 — `app.modules`·
   `app.composition`·`app.composer_staging`이 여전히 그 아래 있다).
   `[project] name`은 바꾸지 마라(패키지 배포 이름과 import 이름은
   다를 수 있다 — 지금은 import 이름만 바꾸는 단계다).
4. `Dockerfile`, `docker/compose.yml`, `.claude/launch.json`의 uvicorn
   실행 대상을 `acop_basement.presentation.api.app:app` → `acop_basement.presentation.api.app:app`
   로 바꾼다.
5. `scripts/basement_manifest.py`의 `BASEMENT_COMPONENTS`를 새 경로
   (`"acop_basement/core"` 등 7개)로 갱신한다.
6. `tests/architecture/test_basement_is_domain_free.py`를 새 구조에 맞게
   고친다 — `APP = Path("app")` + `BASEMENT_DIRS`(하위 디렉터리 이름)
   조합 방식이 아니라, **`acop_basement/` 전체를 basement 스캔 대상으로,
   `app/modules/` 를 도메인 스캔 대상으로** 스캔하도록 바꾼다. 검사
   로직(도메인 어휘 검색, import 위반 검사, allowlist 3개 제한)은
   그대로 유지하고 스캔 루트만 바꾼다. `ALLOWED`(예외 목록)의 경로
   문자열도 새 위치로 갱신한다(`app/core/redaction.py` →
   `acop_basement/core/redaction.py` 등).
7. **여기서 멈춰서 검증**: `python -m pytest -q --ignore=tests/integration/rag`
   와 `python -m pytest tests/architecture -q` 를 돌려서 1단계 이후와
   같은 수로 통과하는지 확인한다. 실패가 있으면 원인을 찾아 고치되,
   **1단계에서 옮긴 Composer 스테이징 파일의 로직 자체는 건드리지
   마라** — import 경로 문제만 고친다.

## 3단계 — 설치 PoC

```powershell
pip install -e . --no-deps
python -c "import acop_basement.core.contracts; import acop_basement.domain.case; print('OK')"
```

저장소 밖 임의 디렉터리(예: `%TEMP%`)로 이동해서 위 import 가 여전히
되는지 확인해라(저장소 cwd 에 우연히 얹혀가는 게 아니라 진짜 설치된
패키지로 import 되는지 증명). 안 되면 원인(namespace package 설정 누락
등)을 찾아 고쳐라.

## 4단계 — 전체 재검증

```powershell
python -m pytest -q --ignore=tests/integration/rag
python -m pytest tests/architecture -q
python -m scripts.verify_dod
python -m scripts.export_basement
```

`export_basement`가 새 경로(`acop_basement/**`) 기준으로 manifest 를
만드는지, 파일 수가 이전 실행(60개)과 비슷한지(Composer 3파일이 빠졌으니
57개 근처가 정상) 확인해라.

## 하지 않을 것

- `final_project_cs/`, `final_project_ui/`, `final_workspace/` 최상위
  파일은 손대지 않는다.
- `app.modules`(도메인)를 옮기지 않는다.
- `create_app()`을 선택적 마운트 구조로 바꾸지 않는다(별도 스트림).
- `[project] name`(배포 이름)을 바꾸지 않는다.
- 동시에 편집 중인 다른 세션의 파일(`CLAUDE.md`,
  `app/presentation/ui/{routes,theme,__init__}.py`, `config/project.yaml`,
  `docs/handoff/08`·`09`, `docs/release_checklist.md`,
  `tests/e2e/test_audience_boundary.py`)의 **내용을 편집하지 않는다** —
  이동이 그 파일에 영향을 준다면(예: import 경로 한 줄) 그 줄만 고치고
  나머지는 그대로 둔다.

## 만들 것 (리포트)

`docs/reports/2026-08-18_S-PIP-PACKAGE-ACOP-BASEMENT_리포트.md` — 각
단계(1~4)의 실제 pytest 결과 원문, 이동한 파일 전체 목록(git mv 이력),
import 일괄 치환에 사용한 명령/스크립트, 설치 PoC 결과 원문, 겪은 문제와
해결 방법. 확신 없는 부분은 "의심됨 — 확인 필요"로 표시해라.
