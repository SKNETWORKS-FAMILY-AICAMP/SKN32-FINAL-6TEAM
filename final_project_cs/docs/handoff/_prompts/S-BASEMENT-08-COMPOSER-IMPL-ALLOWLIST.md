# S-BASEMENT-08-COMPOSER-IMPL-ALLOWLIST — Composer 쓰기채널 임의 모듈 import 차단

## 0. 배경 — 인증된 사용자가 임의 모듈을 import 시킬 수 있다

`app/core/project_config.py::_validate_active_team_implementations()`는
`config/project.yaml`의 각 활성 Team의 `implementation_ref`
(`"package.module:ClassName"` 형식 문자열)에 대해 무조건
`importlib.import_module(module_name)` + `getattr(module, class_name)`를
실행한다. 이건 **신뢰된 로컬 파일 편집 경로**에서는 맞는 동작이다 —
`config/project.yaml`을 직접 고치는 사람은 이미 저장소 쓰기 권한이 있다.

문제는 `app/application/composer_service.py::validate_candidate()`/
`apply_candidate()`가 이 **같은** `load_project_config()` 경로를 그대로
타고, 그 위에 `app/presentation/api/composer.py`의 인증된 HTTP
엔드포인트(`POST /composer/validate`, `POST /composer/apply` — scope
`composer:validate`/`composer:write`)가 얹혀 있다는 것이다. 즉
**`composer:write` scope만 있으면 원격에서 임의의 `implementation_ref`
문자열을 제출해서 cs 프로세스가 임의 모듈을 import하게 만들 수 있다.**

`final_project_sample`(참고용, **절대 수정 금지**)은 이 경계를 이미
막아뒀다 — HTTP로 들어오는 후보만 알려진 구현체 목록으로 제한하고,
신뢰된 로컬 파일 편집 경로는 그대로 무제한으로 둔다:

- `final_project_sample/acop_basement/core/project_config.py`:
  `KNOWN_IMPLEMENTATION_REFS` frozenset 상수 (파일 상단 근처)
- `final_project_sample/acop_composer/service.py`:
  `_validate_http_registry(raw)` 함수 + `validate_candidate()`/
  `apply_candidate()`의 `enforce_registry: bool = False` 파라미터
- `final_project_sample/acop_composer/api.py` line 86, 99:
  실제 HTTP 핸들러는 항상 `enforce_registry=True`로 호출한다

## 1. 할 일

1. `app/core/project_config.py`에 `KNOWN_IMPLEMENTATION_REFS` frozenset을
   추가해라 — cs의 `config/project.yaml`에 지금 실제로 선언된 5개 활성
   Team의 `implementation_ref`를 그대로 채워라(sample의 예시를 복사하지
   마라, cs 것을 써라):
   ```python
   KNOWN_IMPLEMENTATION_REFS = frozenset({
       "app.modules.customer_ops:VocStoreManagerTeam",
       "app.modules.customer_ops.response_review:ResponseGenerationReviewTeam",
       "app.modules.customer_ops.return_refund:ReturnRefundTeam",
       "app.modules.customer_ops.procurement_order_payment:ProcurementOrderPaymentTeam",
       "app.modules.customer_ops.fulfillment_logistics:FulfillmentLogisticsTeam",
   })
   ```
   (`config/project.yaml`을 직접 열어서 정확한 문자열을 재확인해라 — 위
   목록은 참고용이고 실제 파일이 정본이다.)
2. `app/application/composer_service.py`에 sample의
   `_validate_http_registry(raw)`와 동등한 함수를 추가해라 — `raw`
   dict(아직 파싱 전, HTTP body 그대로)를 받아 `raw["teams"]`를 순회하며
   `active is True`인 항목의 `implementation_ref`가
   `KNOWN_IMPLEMENTATION_REFS`에 없으면 에러 문자열을 모아 리스트로
   돌려주는 함수다. `validate_candidate()`와 `apply_candidate()` 둘 다에
   `enforce_registry: bool = False` 파라미터를 추가하고, `True`일 때
   후보를 파일에 쓰기 **전에** 이 함수를 호출해 에러가 있으면
   (validate는) `ValidationResult(False, None, errors)`를 돌려주고
   (apply는) `ProjectConfigError`를 던져라 — sample의 정확한 순서를
   따라라(`apply_candidate`는 `_WRITE_LOCK` 진입 **후**, revision 비교
   **전**에 검사한다).
3. `app/presentation/api/composer.py`의 `/composer/validate`,
   `/composer/apply` 핸들러가 `validate_candidate(...)`/
   `apply_candidate(...)` 호출 시 `enforce_registry=True`를 넘기도록
   고쳐라 — HTTP 경로는 항상 강제하고, 트러스티드 로컬 경로
   (`load_project_config()`를 직접 부르는 다른 코드, 있다면)는 건드리지
   마라.

## 2. 검증

- `tests/e2e/test_composer_write_channel.py`에 재현 테스트를 추가해라:
  - `KNOWN_IMPLEMENTATION_REFS`에 없는 임의의 `implementation_ref`
    (예: `"os:system"` 같이 명백히 위험한 것, 또는 그냥
    `"not.a.real.module:NotAClass"`)를 가진 `active: true` Team을 넣은
    후보를 `/composer/validate`와 `/composer/apply`에 각각 제출했을 때
    **거부**되는지 확인해라(validate는 `valid: false` + errors, apply는
    422 `invalid_declaration` 또는 동등한 에러).
  - `KNOWN_IMPLEMENTATION_REFS`에 있는 정상 `implementation_ref`로는
    기존처럼 통과하는지도 확인해라(과잉 차단 없음 — 기존 통과 테스트가
    깨지면 안 된다).
  - `active: false`인 Team의 `implementation_ref`는 목록에 없어도
    걸리지 않는지 확인해라(sample도 이렇게 동작한다 — 비활성 선언은
    검사 대상이 아니다).
- `python -m pytest -q tests/e2e/test_composer_write_channel.py -v`와
  전체 `python -m pytest -q -m "not live"` 결과를 리포트에 붙여라
  (378 passed 기준 변화 명시).

## 3. 쓰기 대상

- `app/core/project_config.py`
- `app/application/composer_service.py`
- `app/presentation/api/composer.py`
- `tests/e2e/test_composer_write_channel.py`
- `docs/reports/2026-08-24_S-BASEMENT-08-COMPOSER-IMPL-ALLOWLIST_리포트.md` (신규)

## 4. 하지 말 것

- `final_project_sample/` 수정 금지 — 읽기만
- `app/core/settings.py` 수정 금지 — 병렬로 도는 S-BASEMENT-07 계약이
  그 파일을 쓴다
- `tests/unit/core/test_settings_composer_secrets.py` 만들지 마라 —
  S-BASEMENT-07 계약 소관이다
- 신뢰된 로컬 파일 편집 경로(HTTP를 거치지 않는
  `load_project_config()` 직접 호출)까지 제한하지 마라 — sample도 그건
  그대로 둔다
