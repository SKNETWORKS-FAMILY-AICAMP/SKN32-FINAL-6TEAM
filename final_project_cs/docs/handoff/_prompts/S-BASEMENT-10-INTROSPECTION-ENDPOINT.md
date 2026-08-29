# S-BASEMENT-10-INTROSPECTION-ENDPOINT — 외부 콘솔용 read-only 조립 스냅샷 API

## 0. 배경

`final_project_sample/acop_basement/introspection/` (참고용, **절대 수정
금지**, 파일 2개: `__init__.py`, `contract.py`)이 cs에 통째로 없다.

sample의 `contract.py` docstring이 이유를 설명한다: 예전엔 `/ui/admin`이
`composition.build_registry()`를 **같은 프로세스 안에서** 직접 호출했는데,
이러면 별도 프로세스로 도는 대시보드 프로그램(`final_project_ui`)이 이
데이터를 못 가져온다. 그래서 sample은 이 결합을 끊고, "무엇으로
조립됐나"만 담은 작고 버전 있는 JSON을 `GET /introspection`
(`docs/handoff/12_introspection_계약.md` 참고, scope `ops:introspect`)
로 노출했다.

cs는 이미 같은 이유로 Composer를 분리했다 — `/ui/composer`가
2026-08-18 삭제되고 `final_project_ui`의 인증된 `/composer/*` API로
옮겨졌다(`docs/handoff/09_Composer_GUI_계약.md` 참고). **admin/introspection
쪽은 아직 같은 분리를 안 했다** — `app/presentation/ui/routes.py`의
`_admin_snapshot()`(line 101-142)이 조립 데이터를 만들지만 `/ui/admin`
HTML 라우트 안에서만 쓰이는 비공개 함수라, 외부 프로세스가 못 부른다.

## ★중요 — cs의 `_admin_snapshot()`은 sample의 introspection보다 범위가 넓다, 그대로 복사하지 마라

sample의 `snapshot()`은 **순수 조립 정보만** 낸다(선언된 모듈·Port·Team
manifest·guardrails·LLM 설정) — docstring이 명시: "고객 데이터는 한 줄도
나가지 않는다." 그런데 cs의 `_admin_snapshot()`은 그 위에 **tenant
스코프 운영 데이터**(`document_count`, `chunk_count`, `case_statuses`,
`outbox_statuses` — 전부 tenant별로 달라지는 실시간 카운트)까지 섞어서
낸다.

이번에 새로 만드는 `app/introspection/contract.py::snapshot()`은
**sample과 같은 범위**(순수 조립 정보만)로 만들어라 — tenant 운영
데이터는 넣지 마라. `/ui/admin` 페이지는 자기 데이터(조립 정보 + tenant
운영 데이터)를 계속 그대로 보여주면 된다; 새 `/introspection`
엔드포인트는 tenant 컨텍스트가 없는 범용 "자기소개" 계약이라 tenant별
숫자를 낼 수 없다(애초에 tenant_id 파라미터가 없다).

## 1. 할 일

1. `app/introspection/contract.py` 신규 — sample의 `snapshot()`을
   참고해서 cs의 `app/composition.py` 실제 함수 시그니처에 맞게
   다시 써라(복사-붙여넣기 하지 마라):
   - `composition.load_project_config()`, `composition.build_registry(config=config)`,
     `composition.build_team_executor(registry=registry, config=config)`,
     `composition.build_broker(config=config)`,
     `composition.build_graph_store(connection=None, tenant_id="introspection", config=config)`
     — 정확한 키워드 인자 이름은 `app/composition.py`를 직접 열어서
     확인해라(위는 참고용, 이 문서 작성 시점 기준).
   - `TeamManifest`의 실제 필드는 `app/core/contracts.py`를 확인해라 —
     sample의 `_manifest()`가 읽는 필드명(`team_id`, `display_name`,
     `capabilities`, `allowed_tools`, `knowledge_scope`, `max_steps`,
     `active`, `implementation_revision`)이 cs 계약과 다를 수 있다.
   - `config.revision`은 cs의 `ProjectConfig`에 그 필드가 없다(sample과
     다르게 revision 계산이 `app/application/composer_service.py::_revision()`
     로 분리돼 있다) — `getattr(config, "revision", None)`으로 안전하게
     처리해서 `None`이 나오는 걸 그대로 둬라(값을 억지로 채우려고
     `composer_service`를 introspection에서 import하지 마라 — 순환
     의존을 피한다).
   - `settings.openai_api_key`가 있으면 `"sk-****"`, 없으면 `"missing"`
     (또는 cs 관례에 맞는 문자열 — 다른 곳에서 `"없음"`을 쓰는 걸
     참고해서 일관되게 골라라) 마스킹은 sample과 동일하게 유지해라 —
     API key 원문은 절대 내지 않는다.
   - `CONTRACT_VERSION = "1.0"`.
2. `app/introspection/__init__.py` 신규 — sample처럼 `contract.py`에서
   전부 재수출만 해라(`snapshot`을 여기서 다시 정의하지 마라 — sample의
   __init__.py docstring이 설명하는 그 실수를 반복하지 마라).
3. `config/guardrails.yaml`의 `security.scopes` 목록에 `ops:introspect`
   를 추가해라(가드레일 수치는 이 파일 한 곳에만 둔다는 원칙,
   `CLAUDE.md` §3).
4. 새 라우트 `GET /introspection`을 만들어라(적당한 파일 — 기존
   `app/presentation/api/*.py` 라우터 파일 구조를 보고, 새 파일
   `app/presentation/api/introspection.py`를 만들거나 기존 라우터에
   추가해도 된다). `app/presentation/security.py`의
   `require_scope("ops:introspect")` 패턴을 다른 REST 라우트와 똑같이
   써라(`app/presentation/api/cases.py`의 `require_scope(...)` 사용
   패턴 참고). 핸들러는 `app.introspection.contract.snapshot()`을 호출해
   그대로 반환한다.
5. `app/presentation/api/app.py`에 새 라우터를 등록해라(기존
   `app.include_router(...)` 패턴을 따라라).

## 2. 선택 사항 — `_admin_snapshot()` 중복 제거

`app/presentation/ui/routes.py`의 `_admin_snapshot()`이 조립 정보
부분(manifests, ports, llm_provider/model/key, guardrails)을 새
`app.introspection.contract.snapshot()`과 거의 동일하게 다시 만들고
있다. **안전하게 할 수 있으면** `_admin_snapshot()`이 새 `snapshot()`을
호출해서 조립 정보를 얻고, 그 위에 자기 tenant 운영 데이터만 얹도록
리팩터링해라. **단, `/ui/admin` 페이지가 지금 보여주는 필드·구조를
하나도 깨면 안 된다** — 기존 `tests/e2e/`의 admin 페이지 테스트가 전부
그대로 통과해야 한다. 리팩터링이 조금이라도 위험해 보이면(필드명이
안 맞는다, 반환 dict 구조가 다르다 등) **하지 마라** — 새 코드만
추가하고 `_admin_snapshot()`은 그대로 둬도 된다. 이건 요구사항이 아니라
기회다.

## 3. 검증

- 새 계약 테스트(`tests/contract/test_introspection_contract.py` 또는
  적당한 위치, sample의 `tests/contracts/test_introspection_contract.py`
  구조를 참고해서 이름은 cs 관례에 맞춰라): `snapshot()`이 반환하는
  dict가 `contract_version`, `modules`, `ports`, `team_manifests`,
  `teams`, `port_implementations`, `guardrails`, `llm` 키를 갖고,
  `llm.api_key`에 원문이 없는지, `team_manifests`의 각 항목이 cs의
  실제 활성 Team 5개를 담고 있는지 확인해라.
- 새 e2e 테스트(`tests/e2e/test_introspection_endpoint.py` 또는 적당한
  위치): `GET /introspection`이 scope 없으면 401/403, `ops:introspect`
  scope 있으면 200 + 위 구조를 확인해라.
- `/ui/admin`을 건드렸다면(§2 리팩터링을 했다면) 기존 admin 관련
  `tests/e2e/` 테스트가 여전히 전부 통과하는지 확인해라.
- `python -m pytest -q -m "not live"` 전체 실행 결과를 리포트에 붙여라
  (378 passed 기준 변화 명시).
- 여유가 있으면 `docs/handoff/13_introspection_계약.md` 신규로 API
  계약을 짧게 문서화해라(선택 사항 — 기존 handoff 문서 스타일을
  따라라, 없어도 감점 없다).

## 4. 쓰기 대상

- `app/introspection/__init__.py` (신규)
- `app/introspection/contract.py` (신규)
- `app/presentation/api/introspection.py` (신규, 또는 기존 라우터 파일)
- `app/presentation/api/app.py`
- `config/guardrails.yaml` (scopes 목록에 한 줄 추가만)
- `app/presentation/ui/routes.py` (§2가 안전할 때만, 선택)
- 관련 테스트 파일들 (신규)
- `docs/handoff/13_introspection_계약.md` (신규, 선택)
- `docs/reports/2026-08-24_S-BASEMENT-10-INTROSPECTION-ENDPOINT_리포트.md` (신규)

## 5. 하지 말 것

- `final_project_sample/` 수정 금지 — 읽기만
- 새 `/introspection` 응답에 tenant 스코프 운영 데이터(문서/청크
  개수, Case 상태 분포, outbox 상태 분포 등) 넣지 마라 — `/ui/admin`
  전용으로 남긴다
- API key·기타 시크릿 원문을 어떤 형태로도 내지 마라
- `config/guardrails.yaml`의 다른 가드레일 수치는 건드리지 마라 — scopes
  목록에 한 줄만 추가한다
