# S-COMPOSER-V3-TOGGLE-ENDPOINT — 최소 4단계 토글 endpoint + introspection registered_ids 확장

## 0. 배경 — 설계는 이미 승인됐다, 이 계약은 그 구현이다

정본 설계 문서: `../program/plan/A-COP_Composer_v3_설계_토글전용_UI이관.md`
(읽기만 해라, 이 계약이 실제 구현 지시다). 핵심 결론(§1): Composer
쓰기채널을 "전체 ProjectConfig 제출·검증·적용"(v2, 지금 있는
`/composer/validate`·`/composer/apply`)에서 "등록된 항목의 활성 상태만
변경"(v3, 이번에 새로 만드는 `/composer/toggle`)으로 **좁힌다.** v2
endpoint는 그대로 둔다 — 없애지 않는다, v3는 **추가**다.

`final_project_ui`(별도 프로그램, 이 저장소 밖)가 이 endpoint를
호출할 화면·판단 로직을 맡는다. cs는 **등록 ID 확인 → revision 충돌
검사 → flag 원자적 변경 → 감사 로그**, 딱 이 네 단계만 한다(설계
문서 §2.3). 그 이상(예: 새 `implementation_ref` 등록, 여러 항목 동시
변경, Core 계약 구조 변경)은 명시적으로 범위 밖이다(§2.4).

## 1. introspection 응답에 `registered_ids` 확장

`app/introspection/contract.py::snapshot()`(오늘 S-BASEMENT-10로 막
만들어짐)에 최상위 키 `registered_ids`를 추가해라:

```json
"registered_ids": {
  "modules": ["vector_rag", "graph_store", "a2a_executor", "mcp", "voc", "ops_ui"],
  "teams": ["voc_store_manager", "response_generation_review", "return_refund", "procurement_order_payment", "fulfillment_logistics"],
  "ports": []
}
```

- `modules`는 `config.modules`의 키 전체(등록된 모든 모듈 ID — 현재
  enabled 여부와 무관하게 **등록된 것 전체**).
- `teams`는 `config.teams`의 `team_id` 전체(활성/비활성 무관하게
  선언된 것 전체 — `active: false`인 Team도 토글로 다시 켤 수
  있어야 하므로 등록 목록엔 있어야 한다).
- `ports`는 **빈 리스트로 고정해라.** cs의 `PortConfig`는
  `team_executor: Literal["local","a2a"]` 처럼 **값 선택형**이지
  on/off 불리언이 아니다(`app/core/project_config.py`의 `PortConfig`
  확인해라). 설계 문서 §2.1이 이미 이 경우를 언급한다 — "단순히 연결
  방식 값을 선택하는 Port를 임의로 활성/비활성으로 해석하지 않는다."
  cs는 토글 가능한 Port가 하나도 없다는 뜻이다. 억지로 무언가를
  채우지 마라.

기존 `modules`(`{name: bool(enabled)}`)와 `teams`(리스트, 각 항목에
`active` 포함)는 이미 있는 그대로 현재 상태를 담고 있으니 **그 구조를
바꾸지 마라** — `registered_ids`만 새로 추가한다.

**`config_revision`을 실제 값으로 고쳐라.** 지금
`getattr(config, "revision", None)`이라 항상 `None`이 나온다(cs의
`ProjectConfig`엔 그 속성이 없어서다) — 이러면 토글 UI가 `base_revision`으로
쓸 값을 못 받는다. `app/application/composer_service.py::revision(config)`
(이미 있는 sha256 hex digest 계산 함수)를 import해서 실제 값을 채워라.
순환 import 걱정할 필요 없다 — `composer_service.py`는 `introspection`을
import하지 않는다(방향은 introspection → composer_service 한쪽뿐이다).

## 2. `POST /composer/toggle` — 새 endpoint

`app/presentation/api/composer.py`에 추가해라(새 파일을 만들지 마라 —
기존 `/composer/*` 라우터에 자연스럽게 속한다).

### 요청

```json
{
  "target_type": "module",
  "target_id": "vector_rag",
  "active": false,
  "base_revision": "<config_revision>",
  "reason": "운영 점검 중 임시 비활성화"
}
```

- `target_type`: `"module"` | `"team"`만 허용(`"port"`는 위 §1 이유로
  cs에서 대상이 없다 — 요청에 `"port"`가 오면 미등록 ID와 동일하게
  거부해라, 별도 특수 케이스 코드를 만들지 마라. 그냥
  `registered_ids`에 `ports`가 비어 있으니 자연히 "미등록"으로
  걸린다).
- `reason`: 필수, 빈 문자열 금지(기존 `ApplyPayload.reason`과 같은
  `Field(min_length=1)` 패턴을 따라라).

### 인증

읽기(GET `/introspection`)는 이미 있는 `ops:introspect` scope를 그대로
쓴다(따로 손댈 필요 없다). 쓰기(`POST /composer/toggle`)는 기존
`require_composer_scope("composer:write")`를 재사용해라(새 scope
만들지 마라 — 설계 문서 §2.2가 명시적으로 "쓰기는 composer:write
scope를 사용한다"고 한다).

### 네 단계 처리 (설계 문서 §2.3 그대로)

`app/application/composer_service.py`에 새 함수(예: `toggle_target()`)를
추가해서 아래 네 단계를 순서대로 해라 — `apply_candidate()`와 같은
`_WRITE_LOCK` 안에서 실행해라(동시 쓰기 방지, 기존 패턴 재사용):

1. **등록 확인**: `target_type`이 `"module"`이면 `target_id`가
   `config.modules`에 있는지, `"team"`이면 `config.teams`의
   `team_id` 중에 있는지 확인해라. 없으면(또는 `target_type`이
   `"port"`거나 그 외 값이면) `ProjectConfigError`류 예외로 거부해라
   — **이건 깊은 검증이 아니라 존재 확인일 뿐이다**, `importlib`
   같은 걸 다시 태우지 마라.
2. **revision 충돌 검사**: 현재 `revision(current_config)`이
   `base_revision`과 다르면 기존 `RevisionConflict` 예외를 그대로
   재사용해서 던져라(새 예외 타입 만들지 마라 — `/composer/apply`가
   이미 이 패턴으로 409를 반환한다).
3. **flag만 원자적으로 바꾼다.** `apply_candidate()`처럼 raw YAML을
   통째로 다시 쓰지 마라 — **현재 YAML을 읽어서, 해당 항목의
   `enabled`(module) 또는 `active`(team) 필드 **하나만** 바꾼 뒤,
   기존 `apply_candidate()`가 쓰는 것과 같은 안전장치(백업
   `.bak` 파일, 임시 staged 파일에 먼저 쓰고 `os.replace()`로 원자적
   교체, `finally`에서 임시 파일 정리)로 저장해라. 저장 후
   `load_project_config(target)`으로 다시 읽어 새 revision을 계산해서
   반환값에 담아라(이 재로드가 곧 사후 검증이다 — 결과가 여전히 유효한
   선언인지 자동 확인된다).
4. **감사 로그**: `app/presentation/api/composer.py`의 기존
   `_append_audit()` 패턴을 재사용해서 `var/audit/composer_events.jsonl`에
   한 줄 남겨라. 이벤트 이름은 `"composer.toggle"`,
   필드는 요청자(`principal["sub"]`), `target_type`, `target_id`,
   이전 상태, 새 상태, `base_revision`, 새 `config_revision`, `reason`,
   `correlation_id`(uuid4) — `/composer/apply`의 `event` dict 구성을
   그대로 참고해라.

### 응답

성공(200):
```json
{"target_type": "module", "target_id": "vector_rag", "active": false,
 "config_revision": "<new-content-hash>", "audit_id": "<correlation_id>"}
```

실패:
- 미등록 ID → 422, 기존 `/composer/apply`의 `ProjectConfigError` →
  `_error(422, "invalid_declaration", ...)` 처리 패턴을 그대로 따라라.
- revision 충돌 → 409, 기존 `/composer/apply`의 `RevisionConflict` 처리
  패턴(`_error(409, "revision_conflict", ..., current_revision=...)`)을
  그대로 따라라.
- 감사 기록 실패 → 500 `audit_failure`(기존 `/composer/apply`와 동일
  패턴). **단, 이 시점에 flag 변경 자체는 이미 성공해서 파일에
  반영됐다** — `/composer/apply`가 이미 이 순서(먼저 쓰고, 그 다음
  감사, 감사 실패해도 쓰기는 롤백하지 않음)로 동작하니 그대로 따라라.

## 3. 검증

- `tests/e2e/test_composer_write_channel.py`에 재현 테스트를 추가해라:
  - 정상 토글(모듈 `enabled: true → false`, revision 바뀜, 파일에
    실제로 반영됨, 감사 로그 1줄 남음) — module 대상 1건, team 대상
    1건 각각.
  - 미등록 `target_id` → 422, 파일 안 바뀜.
  - `target_type: "port"` → 422(등록된 port가 없으므로), 파일 안
    바뀜.
  - `base_revision`이 현재와 다름 → 409, 파일 안 바뀜.
  - `composer:write` scope 없이 호출 → 401/403(기존 인증 테스트
    패턴).
  - 토글이 **다른 모듈·Team·Port를 건드리지 않는지** 확인해라 — 토글
    전후로 대상 외 필드가 전부 동일한지 대조해라(이게 "전체
    ProjectConfig를 재구성하지 않는다"는 핵심 요구사항이다).
- `tests/contract/test_introspection_contract.py`에 `registered_ids`
  검증을 추가해라: `modules`/`teams` 목록이 `config/project.yaml`의
  실제 등록 항목과 일치하는지, `ports`가 빈 리스트인지,
  `config_revision`이 이제 `None`이 아니라 실제 문자열인지.
- `python -m pytest -q -m "not live"` 전체 실행 결과를 리포트에 붙여라
  (389 passed 기준 변화 명시).

## 4. 쓰기 대상

- `app/introspection/contract.py`
- `app/application/composer_service.py`
- `app/presentation/api/composer.py`
- `tests/e2e/test_composer_write_channel.py`
- `tests/contract/test_introspection_contract.py`
- `docs/reports/2026-08-24_S-COMPOSER-V3-TOGGLE-ENDPOINT_리포트.md` (신규)
- 여유가 있으면 `docs/handoff/13_introspection_계약.md`가 이미 있으면
  거기에, 없으면 새 문서에 `POST /composer/toggle` 계약을 간단히
  추가해라(선택 사항)

## 5. 하지 말 것

- `final_project_sample/` 수정 금지 — 읽기만
- `final_project_ui/`(이 저장소 밖의 별도 프로그램) 수정 금지 — 그건
  다른 프로젝트 담당이다
- `/composer/validate`, `/composer/apply`(v2 endpoint) 삭제·변경
  금지 — v3는 추가고, v2는 유지한다(설계 문서 §5)
- 새 scope 만들지 마라 — `composer:write`/`ops:introspect` 그대로
  재사용
- `target_type: "port"`를 위한 특수 로직·새 필드를 만들지 마라 —
  cs엔 토글 가능한 Port가 없다는 사실 그대로 "미등록"으로 자연스럽게
  거부되게 둬라
- `implementation_ref` 등록·변경 기능을 만들지 마라(설계 문서 §2.4
  "명시적으로 안 되는 것" 그대로)
