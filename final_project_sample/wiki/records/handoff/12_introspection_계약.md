# Introspection contract v1

`app.introspection.snapshot()`(별칭 `describe`)이 basement 의 read-only
조립 상태 projection 이다. `GET /introspection`(scope `ops:introspect`)이 이걸
그대로 JSON 으로 낸다 — **외부 개발 콘솔**(`final_project_ui`)이 이 프로세스 안에서
파이썬을 실행하지 않고 붙는 유일한 통로다.

★2026-08-17: 예전에는 이 값을 `/ui/admin`(이 저장소 안의 HTML 화면)이 렌더링했다.
그 화면은 지웠다 — 개발 콘솔은 별도 프로그램으로 옮겨갔고, 그 프로그램은 read-only 라
이 프로세스를 직접 부를 수 없다(`final_project_ui/CLAUDE.md` §0.3). 그래서 데이터를
**HTTP 로** 낸다. `snapshot()` 자체는 그대로다 — 소비자만 HTML 렌더러에서 HTTP
핸들러로 바뀌었다.

## 반환 형태

- `contract_version`: `"1.1"`
- ★**실행 중인 조립과 저장된 선언을 구분한다**(1.1, 2026-08-31):
  - `active_revision` — 지금 요청을 처리하는 Controller 를 **실제로 만든** 선언.
    모르면 `null`(주입된 Controller 등). 관찰로 계산하지 않는다 — 조립할 때
    받아 적은 값이다
  - `desired_revision` — 저장소(파일 또는 중앙 DB)에 지금 들어 있는 선언
  - `reload_state` — `active`(둘이 같다) · `stale`(저장은 됐는데 아직 안 돌고
    있다) · `reload_failed`(반영을 시도했고 실패했다, 옛 조립이 계속 돈다) ·
    `unknown`(한쪽 revision 을 모른다)
  - `reload_error` — 마지막 반영 실패 사유. 없으면 `null`
- `config_revision` — 옛 소비자용. 이제 **active** 를 가리키고, 모르면 desired 로
  떨어진다. 정확히 보려면 위 두 필드를 읽는다
- `modules`(활성 모듈), `ports`(선언된 Port)

> ★1.0 → 1.1 이 왜 필요했나: 1.0 의 `config_revision` 은 요청마다 저장소를
> **다시 읽어** 계산한 값이었다. 그래서 Composer 로 선언을 바꾸면 대상은 아직
> 옛 조립으로 처리하는데 화면에는 새 revision 이 이미 반영된 것처럼 보였다.
> 반영 안 된 상태를 정상으로 감추는 것이라, 설계검토
> (`wiki/records/reports/2026-08-19_Composer_reload_계약_설계검토.md` §3)가 금지한
> 상태다. 아래 `modules`·`teams`·`ports` 는 지금도 **저장된 선언**을 읽어
> 계산하므로 desired 쪽을 설명한다는 점에 주의한다.
- `team_manifests`: `team_id`, `display_name`, `capabilities`, `allowed_tools`,
  `knowledge_scope`, `max_steps`, `active`, `revision`
- `teams`: 선언(`team_id`·`active`·`implementation_ref`) + 조립된 `manifest`
  (조립 실패 시 `manifest: null` — "없다" 와 "모른다" 를 구분한다)
- `port_implementations`: 실제 조립된 구현 클래스 이름. **하드코딩 맵으로
  추측하지 않는다** — 얻지 못하면 `null`
- `guardrails`: `config/guardrails.yaml` 값 그대로
- `llm`: `provider`, `model`, `api_key`(마스킹된 `"sk-****"` 또는 `"missing"` — 원문 없음)

## 경계

- JSON-safe 데이터만 담는다. Team 을 실행하지 않고, 쓰기를 하지 않고,
  API key 원문을 내지 않는다
- `GET /introspection` 은 `ops:introspect` scope 로 인증한다.
  `mcp:read` 와는 다른 scope 다 — 개인 AI 용 표면과 우리 도구용 표면을 가른다
- `/v1` 아래에 두지 않는다 — case 리소스가 아니라 `/health` 급의 운영 메타데이터다

## 짝이 되는 표면 — `POST /admin/reload`

`stale` 을 **해소하는** 유일한 통로다(재기동 말고). scope 는 `ops:reload` —
`composer:write`(저장)와도, `ops:introspect`(조회)와도 분리한다. 저장은 되돌릴
수 있지만 반영은 그 순간 트래픽이 받는 것을 바꾸기 때문이다.

- 성공: `200 {reload_state, active_revision, desired_revision}`
- 실패: `409 {error.code="reload_failed", active_revision, desired_revision}` —
  ★**옛 조립이 그대로 살아 있다.** 새 조립이 전부 성공한 뒤에만 갈아 끼우므로
  반쯤 바뀐 상태가 생기지 않는다. 실패 사실은 이후 `/introspection` 의
  `reload_state`·`reload_error` 에도 남는다
- 반영하는 것은 **Controller(Registry·Team·Port)** 다. 분류기(`build_classifier`)는
  기동 시 한 번 만들고 여기서 바꾸지 않는다
