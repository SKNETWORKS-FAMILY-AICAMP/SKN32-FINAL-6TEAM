# S-SCAFFOLD-CLI-01 실행 리포트

실행일: 2026-08-19

## 실행 명령과 실제 출력

### `list`

```powershell
python -m scripts.scaffold_project list
```

```text
example_id             case_type  summary
---------------------  ---------  -----------------------------------------------
billing_subscription   구독/결제      결제·구독을 읽고 설명하며 환불을 제안하는 Team (읽기·설명·제안 전용)
technical_entitlement  기술 지원      계정·권한·인시던트를 진단하고 지원 조치를 제안하는 Team (접근 권한 변경 없음)
```

### `show`

```powershell
python -m scripts.scaffold_project show billing_subscription
```

```json
{
  "example_id": "billing_subscription",
  "case_type": "구독/결제",
  "summary": "결제·구독을 읽고 설명하며 환불을 제안하는 Team (읽기·설명·제안 전용)",
  "module_path": "examples/customer_ops/billing.py",
  "implementation_ref": "app.modules.customer_ops.billing:BillingSubscriptionTeam",
  "required_modules": ["vector_rag", "graph_store", "a2a_executor", "mcp", "voc", "ops_ui"],
  "required_ports": {"team_executor": "local", "message_broker": "outbox", "graph_store": "sql"},
  "knowledge_scope": "billing, subscription, refund"
}
```

### `new`

```powershell
python -m scripts.scaffold_project new technical_entitlement --target <target> --team-id support_team
```

```text
Created project scaffold in <target>
Copied example module: <target>\app\modules\customer_ops\technical.py
Created project declaration: <target>\config\project.yaml
Next steps (run manually):
  pip install -e <acop_basement path>
  Apply the project's database migrations.
  python -m pytest tests/architecture -q
```

생성된 `project.yaml` 전문:

```yaml
modules:
  vector_rag:
    enabled: true
  graph_store:
    enabled: true
  a2a_executor:
    enabled: true
  mcp:
    enabled: true
  voc:
    enabled: true
  ops_ui:
    enabled: true
ports:
  team_executor: local
  message_broker: outbox
  graph_store: sql
teams:
- team_id: support_team
  active: true
  implementation_ref: app.modules.customer_ops.technical:TechnicalEntitlementTeam
```

## 검증 결과

- `python -m pytest tests/unit/scripts/test_scaffold_project.py -q`: 4 passed
- `python -m pytest tests/architecture -q`: 72 passed
- `python -m pytest -q --ignore=tests/integration/rag`: 355 passed, 1 deselected
- 생성된 YAML은 `acop_basement.core.project_config.load_project_config`로 로드되고 활성 Team 구현 참조 import 검증을 통과했다.

## 만든 파일

- `examples/catalog.py`
- `scripts/scaffold_project.py`
- `tests/unit/scripts/test_scaffold_project.py`
- `docs/reports/2026-08-19_S-SCAFFOLD-CLI-01_리포트.md`

## 고친 파일

- `docs/handoff/10_도메인_교체_가이드.md`
- `docs/vision/TODO_VISION.md`
- `docs/vision/VISION-10_예제_카탈로그_스캐폴딩_CLI.md`

`acop_basement/**`, `acop_composer/**`, 루트 `config/project.yaml`, 원본
`examples/customer_ops/billing.py`·`technical.py`는 수정하지 않았다.

## 검수 중 발견해 고친 것 (Claude, 2026-08-19)

Codex 산출물의 `required_modules`가 두 예시 모두 `config/project.yaml`의
전체 6개 모듈 키를 그대로 복사한 것이었다 — 그중 2개가 실제로는 근거가
없었다:

- `a2a_executor`: `app/composition.py:76`에서 `team_executor` 포트가
  `"a2a"`일 때만 요구된다. 두 예시의 `required_ports.team_executor`는
  `"local"`이라 자기모순이었다.
- `voc`: 코드베이스 어디에도 `module_enabled("voc")` 호출이 없다
  (`FeedbackAnalyticsTeam` 전용이고 그 팀은 이 카탈로그에 없다) — billing/
  technical 예시와 무관한데 "필수"로 선언돼 있었다.

`vector_rag`(`app/composition.py:118`)·`graph_store`(`app/composition.py:159`,
`acop_basement/introspection/contract.py:116`)·`ops_ui`
(`acop_basement/presentation/ui/__init__.py:34`)는 실제 코드 조회가
근거를 확인해줘서 유지했다. `mcp`는 `module_enabled()`로 게이팅되는
곳이 없지만 기본 `project.yaml`이 켜 두는 상태와 맞추려고 유지했다.

`examples/catalog.py`의 `_REQUIRED_MODULES`를 4개(`vector_rag`·
`graph_store`·`mcp`·`ops_ui`)로 정정하고 각 항목 옆에 근거
파일:줄번호 주석을 남겼다. 스캐폴딩 산출물 예시(§ `new`)와 위 `show`
출력은 정정 전 값이다 — 정정 후 `show billing_subscription`은
`required_modules: ["vector_rag", "graph_store", "mcp", "ops_ui"]`를
반환한다(재실행으로 실측 확인, 4개 테스트·72개 아키텍처 테스트·355개
전체 테스트 모두 정정 후에도 통과).
