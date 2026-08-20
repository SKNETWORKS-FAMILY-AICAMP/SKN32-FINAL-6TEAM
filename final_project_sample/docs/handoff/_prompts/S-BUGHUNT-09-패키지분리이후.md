# S-BUGHUNT-09-패키지분리이후 — acop_basement/acop_composer 분리 이후 전체 점검 (리포트만, 수정 금지)

## 배경

라운드 1~8 이력(`docs/reports/debugs/2026-08-17_버그사냥_*.md`) 이후,
이번 세션에서 큰 리팩터가 있었다 — `app/` 단일 패키지를 `acop_basement`
(pip 설치 가능, 도메인 무관) / `acop_composer`(별도 선택 패키지) / `app/`
(로컬 도메인·조립·entrypoint) 세 조각으로 쪼갰다(v0.3.0, 커밋 `d6d948d`).
이 과정에서 이미 발견해 고친 결함들이 있다(`CHANGELOG.md` `[0.3.0]` 절 참고):
도메인 마이그레이션이 실수로 basement 패키지 안에 실렸던 것,
`acop_basement/presentation/api/app.py`가 basement 안에서 product 전용
`app.composition`을 최상단 import 하던 것, `KNOWN_IMPLEMENTATION_REFS`의
문자열 조각 우회 등. **같은 종류의 실수가 더 남아 있는지**가 이번 라운드의
목적이다.

그 직후 VISION-10 1층(예제 카탈로그·스캐폴딩 CLI)도 새로 추가됐다
(`examples/catalog.py`, `scripts/scaffold_project.py`, 커밋 `e322bab`) —
이것도 스캔 대상이다.

## 이번에도 다르게 한다 — ★고치지 않는다, 보고만 한다

이유는 앞선 라운드와 같다(`RULE.md` §3.6-3). **어떤 파일도 수정하지 않는다.**
새 파일도 만들지 않는다. 결과는 세션 최종 응답(stdout)으로만 낸다.

## 스캔 범위 — 저장소 전체, 단 우선순위를 둔다

**1순위 (이번 리팩터로 새로 생겼거나 경로가 바뀐 코드)**:

- `acop_basement/presentation/api/app.py` — `create_app()`이 optional
  `composer_write_router`/`composer_auth_router`를 받는 구조. Composer를
  안 넘겼을 때 정말로 `/composer/*`·`/auth/token` 라우트가 전혀 등록되지
  않는지, 모듈 레벨 `app = create_app()`(파일 끝)이 다른 어떤 코드 경로와도
  충돌하지 않는지.
- `app/entrypoint.py`, `Dockerfile`, `docker/compose.yml`,
  `.claude/launch.json` — uvicorn 대상이 실제로 일관되게
  `app.entrypoint:app`을 가리키는지, 하나라도 옛 `app.presentation.api.app:app`
  같은 죽은 경로를 참조하고 있지 않은지.
- `acop_basement/infrastructure/db/migrate.py` — core 마이그레이션(패키지
  내부)과 domain 마이그레이션(`config/migrations/`)을 파일명 순서로 함께
  적용한다는데, 정말로 실행 순서가 올바른지(예: domain 마이그레이션이 core
  스키마보다 먼저 실행되면 FK 실패), 두 디렉터리에 같은 파일명이 우연히
  겹칠 경우 무슨 일이 일어나는지.
- `acop_composer/api.py`, `acop_composer/auth.py`, `acop_composer/service.py`
  — 새 최상위 패키지로 옮기며 상대 import(`from .`)나 옛 `app.application.
  composer_service` 같은 죽은 경로 참조가 남아 있지 않은지.
- `examples/catalog.py`, `scripts/scaffold_project.py` — 카탈로그의
  `required_modules`/`required_ports`/`implementation_ref` 값이 실제
  `examples/customer_ops/billing.py`·`technical.py`·
  `acop_basement/core/project_config.py`·`app/composition.py`의 실제 동작과
  여전히 일치하는지(이미 한 번 `a2a_executor`·`voc` 오류가 검수에서
  발견돼 고쳐졌다 — 비슷한 종류의 다른 불일치가 더 있는지). `scaffold_project.py new`가
  만드는 `app/__init__.py` 빈 파일들이 대상 프로젝트의 다른 필요한 파일
  (예: `app/modules/__init__.py`)을 빠뜨리지 않는지.
- `docs/handoff/10_도메인_교체_가이드.md`, `docs/handoff/15_basement_버전_배포_계약.md`
  — 이번 세션에 재작성됐다. 문서가 가리키는 파일 경로·명령이 실제로
  존재하고 동작하는지(예: 문서의 `python -m acop_basement.infrastructure.db.migrate`
  같은 명령이 실제 모듈 경로와 일치하는지).

**2순위 (패키지 분리로 간접 영향받았을 수 있는 기존 코드)**:

- `tests/architecture/test_basement_is_domain_free.py` — `BASEMENT_DIRS`에
  `acop_basement/tools`·`acop_basement/introspection`이 반영됐는지, 이
  테스트가 실제로 `acop_basement/` 전체를 스캔 대상으로 삼고 있는지(옛
  `app/core` 등 경로를 여전히 스캔하려다 존재하지 않는 디렉터리라 조용히
  통과("스캔 대상 0건 → 자동 OK")하는 함정이 없는지 — 있다면 위험도 높음).
- `scripts/basement_manifest.py`, `scripts/export_basement.py` — 저장소
  밖 디렉터리로 export 했을 때 실제로 `acop_basement`만 export 되고
  `acop_composer`가 섞여 들어가지 않는지(반대로 `acop_composer`를 export
  하고 싶을 때 이 도구가 아예 다루지 않는다는 게 문서화돼 있는지).
- `pyproject.toml`의 `[tool.setuptools.packages.find] include`가
  `["app*", "acop_basement*", "acop_composer*"]`인데, `app*` 패턴이
  `acop_basement`/`acop_composer`와 무관한 `app/modules`·`app/composition.py`
  등도 의도대로 패키징하는지, 혹은 `tests/`·`examples/`·`scripts/` 같은
  다른 최상위 디렉터리를 실수로 함께 패키징하고 있지 않은지.

**3순위 (전체 스윕 — 얕게, 명백한 것만)**:

- 저장소 전체에서 `except: continue`/`except Exception: pass` 류의 조용한
  스킵.
- `tenant_id`/`customer_id` 조건 없는 SQL 조회.
- `acop_basement/**`에 도메인 어휘(billing, subscription, refund, payment,
  entitlement, incident 등)가 남아 있는지 — `test_basement_is_domain_free.py`의
  사전 자체가 놓치는 단어가 있는지도 같이 본다.

## 찾을 것

라운드 1~8과 같은 기준(진짜 재현 가능한 결함, 잘못된 근거로 쓴 주석/문서,
문서 간 수치 불일치). **확신 없으면 "의심됨 — 확인 필요"로 표시.** 억지로
개수를 채우지 않는다 — 못 찾으면 못 찾았다고 적는다.

## 만들 것

리포트 하나만, stdout 으로. 형식:

```
### <파일:줄번호> — <한 줄 요약>
- 시나리오: <구체적 입력/상태 → 무엇이 잘못되는지>
- 왜 기존 테스트가 못 잡는가: <이유>
- 재현 시도: <실제로 재현을 시도했다면 그 결과. 못 했으면 "재현 안 해봄, 코드 읽기로만 판단">
- 위험도: 높음 | 보통 | 낮음
```

## 완료 기준

이 스트림은 코드를 안 건드린다. `python -m pytest -q --ignore=tests/integration/rag`
는 시작 전과 끝난 후 결과가 같아야 한다(같지 않다면 그건 이 스트림이 아니라
동시 편집 세션 때문일 수 있으니 그 사실만 보고한다).
