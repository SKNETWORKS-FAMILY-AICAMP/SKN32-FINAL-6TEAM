# S-COMPOSER-CATALOG-CHANGES — 카탈로그 조회 + 인스턴스 CRUD (스트림 B)

## 배경

계획서는 `docs/plans/2026-08-28_선언형Team_카탈로그CRUD_계획.md`다. 이 계약은
그 계획서 §3의 스트림 B를 구현 지시로 옮긴 것이다. 계획서와 어긋나면
계획서가 정본이다.

지금 Composer는 v2뿐이다 — `/composer/current`·`/validate`·`/apply`가 전체
`ProjectConfig`를 통째로 주고받는다(`acop_composer/api.py`,
`acop_composer/service.py`). 이 방식은 UI가 전체 선언 구조를 알아야 해서
"UI가 대상 스키마를 복제하는" 문제로 이어진다.

이 스트림은 그 위에 **카탈로그 기반 인스턴스 CRUD**를 얹는다. UI가
"어떤 구현을 쓸 수 있는지"를 서버에서 받아, "이 인스턴스를 만들어줘"라는
좁은 명령만 보내면 되게 한다.

★v2(`/current`·`/validate`·`/apply`)는 **제거하지 않는다.** bulk migration
경로로 그대로 둔다.

## 만들 것

### 1. `GET /composer/catalog`

scope는 기존 `composer:read`를 재사용한다(`acop_composer/auth.py` 확인).

응답은 UI가 고를 수 있는 구현 종류를 낸다. 각 항목의 최소 필드:

- `implementation_id` — UI에 노출하는 안정된 ID
- `kind` — `team` 또는 `module`
- `display_name`, `description`
- `parameters_schema` — 이 구현을 인스턴스로 만들 때 입력해야 하는 값의
  JSON Schema (없으면 `null`)
- `requires_restart` — 이 종류를 바꾸면 재시작이 필요한가 (지금은 전부
  `true`, 계획서 §1이 자동 재시작을 Phase 2로 미뤘다)

★**Python 경로(`package.module:Class`)를 응답에 노출하지 마라.**
`implementation_id`만 낸다. 서버 안에서 ID↔경로를 매핑한다. 매핑의 출처는
`acop_basement/core/project_config.py`의 `KNOWN_IMPLEMENTATION_REFS`다
(실제로 읽어서 확인해라).

선언형 Team 타입(`acop_basement.teams.declarative:DeclarativeTeamRuntime`)도
카탈로그 항목으로 넣되, **스트림 A가 아직 그 파일을 안 만들었을 수 있다.**
import를 시도하지 말고 선언적 메타데이터로만 등록해라. `parameters_schema`는
계획서 §2.2 필드 목록을 그대로 쓴다.

### 2. `POST /composer/changes`

scope는 `composer:write`.

요청:
```json
{
  "operation": "create",
  "resource_type": "team",
  "instance_id": "vip_return_review",
  "implementation_id": "<catalog의 id>",
  "parameters": { },
  "active": true,
  "base_revision": "<현재 revision>",
  "reason": "왜 바꾸는지",
  "dry_run": false,
  "idempotency_key": "<uuid>"
}
```

- `operation`: `create`·`update`·`delete`·`enable`·`disable`
- `resource_type`: `team`·`module`
- `delete`/`enable`/`disable`은 `implementation_id`·`parameters`가 없어도 된다.

처리 순서:
1. `implementation_id`가 카탈로그에 있는지 확인 — 없으면 `422`.
2. `base_revision`이 현재 파일 revision과 다르면 `409 revision_conflict`
   (v2의 기존 처리와 **같은 에러 형태**를 써라 — `acop_composer/service.py`의
   `RevisionConflict` 재사용).
3. 현재 선언을 읽어 **해당 인스턴스 하나만** 바꾼 새 선언을 만든다.
   전체를 재구성하지 않는다.
4. 새 선언을 대상의 canonical loader(`load_project_config`)로 검증한다 —
   검증 실패는 `422`. ★검증기를 새로 만들지 마라. 실제 로더를 써야
   "검증은 통과했는데 기동하면 죽는" 문제가 안 생긴다.
5. `dry_run: true`면 **여기서 멈추고 파일을 건드리지 않는다.** 검증
   결과만 반환한다.
6. 아니면 v2와 같은 원자적 쓰기 경로(`_WRITE_LOCK` → 임시파일 →
   `os.replace()`)로 저장한다. 기존 `apply_candidate()`의 안전장치를
   재사용해라 — 복붙하지 말고 공통 함수로 뽑아 쓰는 쪽을 우선 검토하되,
   v2 동작이 바뀌면 안 된다.
7. audit 이벤트를 append 한다(v2와 같은 `var/audit/composer_events.jsonl`,
   같은 형식). `operation`·`resource_type`·`instance_id`·이전/새 상태·
   revision·reason·actor를 남긴다.

응답:
```json
{
  "change_id": "...",
  "desired_revision": "<새 revision>",
  "activation_state": "pending_restart",
  "dry_run": false,
  "errors": []
}
```

★`activation_state`는 **정직해야 한다.** 저장에 성공해도 이미 떠 있는
프로세스는 그 설정으로 안 돌아간다(`app/composition.py`가 기동 시 한 번만
조립한다 — 실제로 확인해라). 그러니 `pending_restart`를 반환하고, 절대
"적용 완료"처럼 응답하지 마라. 이 프로젝트는 조용한 성공 위장을 금지한다
(`CLAUDE.md` §0.1).

### 3. idempotency

같은 `idempotency_key`로 같은 요청이 두 번 오면 **두 번 쓰지 않는다.**
두 번째는 첫 번째 결과를 그대로 반환한다. 저장 방식은 이 저장소의 기존
idempotency 처리(`acop_basement/core/idempotency.py` 등, 실제로 찾아봐라)를
참고하되, Composer는 DB가 아니라 파일 기반이므로 그에 맞는 최소 방식을
골라라. 고른 이유를 리포트에 적어라.

## 검증

- `GET /composer/catalog`가 등록 구현체와 선언형 타입을 반환한다.
- `dry_run: true`가 파일을 **안 건드린다**(파일 mtime·내용 둘 다 확인).
- `base_revision` 불일치 → `409`.
- 카탈로그에 없는 `implementation_id` → `422`.
- 같은 `idempotency_key` 2회 → 파일은 1번만 바뀐다.
- 응답의 `activation_state`가 `pending_restart`다.
- ★기존 v2 테스트(`tests/e2e/test_composer_write_channel.py`)가 **그대로
  통과**해야 한다 — v2 동작을 바꾸지 않았다는 증거다.

```powershell
python -m pytest tests/e2e/test_composer_write_channel.py -q
python -m pytest -q --ignore=tests/integration/rag
```

## 하지 말 것

- ★`acop_basement/**`, `app/composition.py`를 건드리지 마라 — 스트림 A가
  동시에 작업 중이다. 읽기만 해라.
- ★**선언형 Team을 실제로 만드는 테스트를 쓰지 마라.** 스트림 A가
  `TeamConfig.parameters`를 아직 안 넣었을 수 있어서 로더 검증에 실패한다.
  CRUD 테스트는 기존 등록 구현체(`app.modules.placeholder:PlaceholderTeam`
  등)로만 해라. 통합 테스트는 두 스트림이 끝난 뒤 Claude가 직접 넣는다.
- v2 엔드포인트를 제거하거나 동작을 바꾸지 마라.
- 자동 재시작·reload를 구현하지 마라(Phase 2).
- `config/project.yaml`(저장소 루트)을 바꾸지 마라. 테스트는 임시 파일로.

## 만들 것 (리포트)

`docs/reports/2026-08-28_S-COMPOSER-CATALOG-CHANGES_리포트.md` — 만든/고친
파일, ID↔경로 매핑을 어디에 뒀는지, idempotency 방식과 선택 이유, v2
원자적 쓰기를 어떻게 재사용했는지(복제했다면 왜), 테스트 결과.
