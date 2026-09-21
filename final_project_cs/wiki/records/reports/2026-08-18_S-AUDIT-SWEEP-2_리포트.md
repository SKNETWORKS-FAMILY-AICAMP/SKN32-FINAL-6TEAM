# S-AUDIT-SWEEP-2 정밀 감사 리포트

- 감사일: 2026-08-18
- 읽기 범위: `app/domain/**`, `app/application/**`, `eval/**`
- 쓰기 범위: 이 리포트 파일만
- 제외 범위: `app/presentation/**`, `app/core/**`, `app/modules/**`, `app/tools/**`, `app/infrastructure/**`, `scripts/**`, `prompts/**`
- 판정 주의: 패턴 B의 “저장소 전체” 호출부 확인은 위 읽기 허용 범위 안의 비테스트 Python 코드와 `eval` 코드만 AST/검색으로 집계했다. 제외 범위 파일의 내용을 읽지 않았으므로, 외부 조립 루트나 라우트에서 호출될 가능성이 있는 항목은 죽은 코드로 확정하지 않고 보류 후보로 표시했다.

## 요약

- 패턴 A: 문제 0건 발견.
- 패턴 B: 유력 후보 4건. 외부 호출 가능성 때문에 확정하지 않은 보류 후보 3건 추가.
- 패턴 C: 실행 코드 잔재 0건. `eval/reports/*.jsonl`의 과거 평가 산출물에는 역사적 `billing`/`subscription` 문자열이 남아 있으나, 현재 실행 스크립트의 값이나 분기에는 사용되지 않는다.

## 패턴 A — DB row 쓰기 호출의 status/state 생략 충돌

### 결론: 0건 발견

재현 명령:

```powershell
rg -n -C 5 "repository\.|repo\.|\.create_[A-Za-z0-9_]*\s*\(|\.update_[A-Za-z0-9_]*\s*\(" app/application
```

확인된 쓰기 호출은 다음 1건이다.

- `app/application/controller.py:251-252`
  ```python
  self.repository.create_action_request(
      conn, tenant_id=case["tenant_id"], case_id=case["case_id"],
      action_type=proposal.action_type, arguments=proposal.arguments,
      idempotency_key=server_key, status="pending_approval"
  )
  ```

`status`를 생략하지 않고 `pending_approval`을 명시한다. 따라서 기본값 누락으로 조회부의 `status`/`state` 필터와 충돌하는 사례는 발견되지 않았다. `app/application/case_service.py`의 직접 SQL `INSERT/UPDATE`는 `repository.create_*`/`update_*` 호출이 아니므로 이 패턴의 대상 호출로 세지 않았다.

심각도: 해당 없음.

## 패턴 B — 정의됐지만 호출부가 없는 public 함수/클래스

집계 방법:

```powershell
rg -n "^\s*(async\s+)?def\s+[A-Za-z_][A-Za-z0-9_]*|^\s*class\s+[A-Za-z_][A-Za-z0-9_]*" app/domain app/application eval -g "*.py" -g "!tests/**"
```

추가로 비테스트 Python 파일을 AST로 순회하여 함수 호출(`Name`/`Attribute`)을 세고, 테스트 호출부도 별도 확인했다.

### 유력 후보 — 4건

1. `app/domain/case.py:92` — `fold_events`

   근거: 정의는 있으나 허용 범위 내 비테스트/테스트 호출부가 0건이다.

   판단: 이벤트 replay용 public 함수로 구현은 완결되어 있지만 현재 허용 범위에서 호출 경로가 확인되지 않는다. 실제로 외부 도메인 조립부에서 사용할 수 있으므로 “죽은 코드 확정”은 보류한다.

   심각도: 낮음(현재 런타임 영향 미확인).

2. `app/domain/events.py:129` — `allowed_next_statuses`

   근거: 정의는 있으나 허용 범위 내 비테스트/테스트 호출부가 0건이다.

   판단: 상태 전이 조회용 public 함수지만 현재 호출부가 확인되지 않는다. 문서화/진단 API로 남겨둔 의도일 가능성이 있어 보류한다.

   심각도: 낮음.

3. `app/application/feedback_job.py:30` — `run_daily_feedback`

   근거: 정의는 있으나 허용 범위 내 비테스트/테스트 호출부가 0건이다.

   판단: 일일 분석 리포트와 outbox를 실제 DB에 쓰는 함수다. 현재 보이는 런타임 경로에서 호출되지 않아 운영 잡 미연결 가능성이 있으나, 스케줄러/실행 진입점이 제외 범위에 있을 수 있어 확정하지 않는다.

   심각도: 중간(실제 미연결이면 분석/알림 누락).

4. `app/application/proposal_guard.py:70` — `recheck_before_execution`

   근거: 정의는 있으나 허용 범위 내 비테스트/테스트 호출부가 0건이다.

   판단: 승인 직전 재검증이라는 안전 경계 함수인데 현재 확인된 호출부가 없다. 실행 경로가 이 함수를 우회하면 stale proposal 실행 방어가 약화될 수 있지만, 실행기는 제외 범위이므로 보류한다.

   심각도: 중간~높음(실제 우회가 확인될 경우).

### 호출 문법 0건이지만 dead code로 세지 않은 항목 — 3건

- `app/domain/events.py:16` — `EventType`: 생성자 호출은 없지만 `EventType.CREATED` 등 enum 멤버 참조가 다수 있어 사용 중이다.
- `app/application/controller.py:26` — `Controller`: 허용 범위 안의 직접 생성 호출은 없지만 애플리케이션 진입점에서 주입될 수 있어 보류 대상이다.
- `app/application/controller.py:259` — `Controller.resume`: 허용 범위 안의 직접 호출은 없지만 라우트/외부 진입점에서 호출될 수 있어 보류 대상이다.

`eval/defense_metrics.py:39`의 `Ratio.value`는 `@property`이며 `self.value` 속성 참조로 사용된다. `eval/runners/common.py:167`의 `complete`와 `:177`의 중첩 `call`은 각각 비공개 어댑터 내부 구현/중첩 함수이며 public top-level API 후보에서 제외했다.

## 패턴 C — 옛 구독·청구 도메인 잔재

실행한 검색:

```powershell
grep -rniE "\bbilling\b|\bsubscription\b|technical_entitlement|entitlement" app/domain app/application eval
```

코드 중심 재확인:

```powershell
rg -n -i "\b(billing|subscription|technical_entitlement|entitlement)\b" app/domain app/application eval/runners eval/stats eval -g "*.py" -g "!tests/**"
```

### 실행 코드

두 번째 명령에서 `*.py` 일치가 0건이었다. 따라서 `app/domain`, `app/application`, `eval/runners`, `eval/stats`, `eval/*.py`에 해당 잔재가 실제 값·분기·주석으로 남아 있는 사례는 0건 발견했다.

판정: 0건. 심각도: 해당 없음.

### 평가 산출물

첫 번째 명령은 다음 `eval/reports/*.jsonl` 21개에서 과거 결과의 `billing`/`subscription` 문자열을 찾았다: `abl_no_approval.jsonl`, `abl_no_context_broker.jsonl`, `abl_no_feedback_inline.jsonl`, `abl_no_rag.jsonl`, `abl_no_team_split.jsonl`, `live_smoke.jsonl`, `pairs.jsonl`, `pairs_ba.jsonl`, `pairs_pa.jsonl`, `pairs_pb.jsonl`, `pairs_proposed_b.jsonl`, `raw.jsonl`, `raw_a_smoke.jsonl`, `raw_b_smoke.jsonl`, `raw_baseline_a.jsonl`, `raw_baseline_b.jsonl`, `raw_live_failed_codexsandbox.jsonl`, `raw_proposed.jsonl`, `rescored_baseline_a.jsonl`, `rescored_baseline_b.jsonl`, `rescored_proposed.jsonl`.

각 항목은 실행 코드가 아니라 과거 평가 입력/예측/검색 근거를 보존한 JSONL 산출물이다. 현재 도메인 값을 결정하는 코드 잔재로 판정하지 않았으며, 수정하지 않았다. `eval/datasets/golden.jsonl` 및 `holdout.jsonl`은 요청대로 커머스 도메인으로 재작성됐다는 전제를 재확인하는 수준으로만 다뤘다.

심각도: 해당 없음(산출물의 역사적 문자열).

## 범위·변경 검증

읽기 대상 외 파일은 읽거나 수정하지 않았다. 수정은 이 리포트 파일 생성 1건뿐이다.

요청한 명령:

```powershell
git -c safe.directory='C:/Users/playdata2/Documents/final_workspace' status --short
```

출력:

```text
+ M ../.gitignore
 D "../A-COP_Mandate_Outcome_\352\270\260\354\210\240\352\265\254\355\230\204\352\263\204\355\232\215\354\204\234.md"
 D "../A-COP_Mandate_Outcome_\353\270\214\353\246\254\355\225\221.html"
 D "../A-COP_\352\265\254\355\230\204\352\263\204\355\232\215\354\204\234(4).md"
 D "../A-COP_\352\265\254\355\230\204\352\263\204\355\232\215\354\204\234_A2A_Graph\353\260\230\354\230\201.md"
 D "../A-COP_\352\265\254\355\230\204\352\263\204\355\232\215\354\204\234_v5.md"
 D "../A-COP_\352\265\254\355\230\204\352\263\204\355\232\215\354\204\234_v6.md"
 D "../A-COP_\352\265\254\355\230\204\352\263\204\355\232\215\354\204\234_v7.md"
 D "../A-COP_\353\270\214\353\246\254\355\225\221(9).html"
 D "../A-COP_\353\270\214\353\246\254\355\225\221_A2A_Graph\353\260\230\354\230\201_\354\265\234\354\242\205.html"
 D "../A-COP_\353\270\214\353\246\254\355\225\221_v10.html"
 D "../A-COP_\353\270\214\353\246\254\355\225\221_v7.html"
 D "../A-COP_\355\231\225\354\236\245\354\225\210_\352\265\254\355\230\204\353\252\205\354\204\270_B2B\354\244\221\354\213\254_2026-08-15.md"
 D "../A-COP_\355\231\225\354\236\245\354\225\210_\353\270\214\353\246\254\355\225\221_\354\232\260\354\270\241\354\266\225\354\206\214\353\240\210\354\235\274_\353\236\230\355\215\274\353\237\260\354\212\244\353\260\230\354\230\201_2026-08-15.html"
 D "../A-COPilot_\354\240\234\354\266\234\355\221\234.xlsx"
 D "../A-COPilot_\354\240\234\354\266\234\355\221\234_v2.md"
 D "../A-COPilot_\355\224\204\353\241\234\354\240\235\355\212\270_\354\240\234\354\266\234\355\221\234.md"
 M "../briefing/A-COP_\353\270\214\353\246\254\355\225\221_v8.html"
 M CLAUDE.md
 M RULE.md
 M app/composition.py
 M app/infrastructure/llm/openai.py
 M app/modules/customer_ops/order_shipping.py
 M app/modules/customer_ops/return_exchange.py
 M app/presentation/ui/__init__.py
 D app/presentation/ui/composer.py
 M app/presentation/ui/routes.py
 M app/presentation/ui/theme.py
 M app/tools/read_tools.py
 M config/project.yaml
 M "wiki/records/handoff/08_\353\252\250\353\223\210_\354\273\264\355\217\254\353\204\214\355\212\270_\353\252\251\353\241\235.md"
 M "wiki/records/handoff/09_Composer_GUI_\352\263\204\354\225\275.md"
 M "wiki/records/handoff/10_\353\217\204\353\251\224\354\235\270_\352\265\220\354\262\264_\352\260\200\354\235\264\353\223\234.md"
 M wiki/records/release_checklist.md
 M "wiki/records/reports/debugs/2026-08-17_2340_\355\224\204\353\241\254\355\224\204\355\212\270_\352\260\220\354\202\254\354\266\224\354\240\201_\353\257\270\354\227\260\352\262\260.md"
R  prompts/billing/classify_billing.v1.md -> legacy/final_project_sample/prompts/billing/classify_billing.v1.md
R  prompts/billing/classify_billing.v2.md -> legacy/final_project_sample/prompts/billing/classify_billing.v2.md
R  prompts/billing/explain_billing.v1.md -> legacy/final_project_sample/prompts/billing/explain_billing.v1.md
R  prompts/billing/explain_billing.v2.md -> legacy/final_project_sample/prompts/billing/explain_billing.v2.md
R  prompts/billing/propose_refund.v1.md -> legacy/final_project_sample/prompts/billing/propose_refund.v1.md
R  prompts/billing/propose_refund.v2.md -> legacy/final_project_sample/prompts/billing/propose_refund.v2.md
R  prompts/technical/classify_entitlement.v1.md -> legacy/final_project_sample/prompts/technical/classify_entitlement.v1.md
R  prompts/technical/classify_entitlement.v2.md -> legacy/final_project_sample/prompts/technical/classify_entitlement.v2.md
R  prompts/technical/diagnose_entitlement.v1.md -> legacy/final_project_sample/prompts/technical/diagnose_entitlement.v1.md
R  prompts/technical/diagnose_entitlement.v2.md -> legacy/final_project_sample/prompts/technical/diagnose_entitlement.v2.md
R  prompts/technical/propose_support_action.v1.md -> legacy/final_project_sample/prompts/technical/propose_support_action.v1.md
R  prompts/technical/propose_support_action.v2.md -> legacy/final_project_sample/prompts/technical/propose_support_action.v2.md
 D tests/e2e/test_composer_structure.py
 D tests/e2e/test_composer_ui.py
 M tests/e2e/test_root_landing.py
 M tests/unit/test_project_composition.py
 M ../final_project_sample/.env.example
 M ../final_project_sample/.gitignore
 M ../final_project_sample/CLAUDE.md
 M ../final_project_sample/RULE.md
 M ../final_project_sample/app/application/case_service.py
 M ../final_project_sample/app/application/composer_service.py
 M ../final_project_sample/app/application/controller.py
 M ../final_project_sample/app/application/feedback_job.py
 M ../final_project_sample/app/composition.py
 M ../final_project_sample/app/core/project_config.py
 M ../final_project_sample/app/core/settings.py
 M ../final_project_sample/app/core/transition.py
 M ../final_project_sample/app/infrastructure/messaging/outbox.py
 M ../final_project_sample/app/modules/customer_ops/__init__.py
 D ../final_project_sample/app/modules/customer_ops/billing.py
 D ../final_project_sample/app/modules/customer_ops/technical.py
 M ../final_project_sample/app/presentation/api/app.py
 M ../final_project_sample/app/presentation/api/cases.py
 M ../final_project_sample/app/presentation/api/composer.py
 M ../final_project_sample/app/presentation/ui/__init__.py
 D ../final_project_sample/app/presentation/ui/composer.py
 M ../final_project_sample/app/presentation/ui/routes.py
 M ../final_project_sample/app/presentation/ui/theme.py
 M ../final_project_sample/config/guardrails.yaml
 M ../final_project_sample/config/project.yaml
 M "../final_project_sample/docs/evidence/DoD-12_outbox_\354\233\220\354\236\220\354\204\261_replay.md"
 M "../final_project_sample/docs/handoff/03_REST_MCP_\354\235\270\355\204\260\355\216\230\354\235\264\354\212\244.md"
 M "../final_project_sample/docs/handoff/04_Team_\353\252\250\353\223\210_\352\263\204\354\225\275.md"
 M "../final_project_sample/docs/handoff/08_\353\252\250\353\223\210_\354\273\264\355\217\254\353\204\214\355\212\270_\353\252\251\353\241\235.md"
 M "../final_project_sample/docs/handoff/09_Composer_GUI_\352\263\204\354\225\275.md"
 M "../final_project_sample/docs/handoff/13_Composer_\354\223\260\352\270\260\354\261\204\353\204\220_\352\263\204\354\225\275.md"
 M ../final_project_sample/docs/release_checklist.md
 M ../final_project_sample/eval/runners/common.py
 M ../final_project_sample/requirements.txt
 M ../final_project_sample/scripts/verify_dod.py
 M ../final_project_sample/tests/contract/test_contracts.py
 M ../final_project_sample/tests/contract/test_team_contract.py
 M ../final_project_sample/tests/e2e/test_audience_boundary.py
 D ../final_project_sample/tests/e2e/test_composer_structure.py
 D ../final_project_sample/tests/e2e/test_composer_ui.py
 M ../final_project_sample/tests/e2e/test_composer_write_channel.py
 M ../final_project_sample/tests/e2e/test_introspection_endpoint.py
 M ../final_project_sample/tests/e2e/test_root_landing.py
 M ../final_project_sample/tests/integration/api/test_api_runtime.py
 M ../final_project_sample/tests/integration/controller/test_controller_integration.py
 M ../final_project_sample/tests/integration/controller/test_outbox_tenant_isolation.py
 M ../final_project_sample/tests/security/test_scope_contract.py
 M ../final_project_sample/tests/unit/core/test_case_reducer.py
 M ../final_project_sample/tests/unit/core/test_config_revision.py
 M ../final_project_sample/tests/unit/infrastructure/test_graph_v7_axes.py
 D ../final_project_sample/tests/unit/teams/test_team_scenarios.py
 M ../final_project_sample/tests/unit/test_composition_root.py
 M ../final_project_sample/tests/unit/test_project_composition.py
 M ../final_project_ui/CLAUDE.md
 M ../final_project_ui/console/profiles.py
 M ../final_project_ui/console/web.py
 M "../final_project_ui/docs/plans/2026-08-17_\353\266\204\353\246\254_\353\214\200\354\213\234\353\263\264\353\223\234_\354\213\244\355\226\211\352\263\204\355\232\215.md"
 M ../final_project_ui/requirements.txt
 M "../plan/A-COP_\352\265\254\355\230\204\352\263\204\355\232\215\354\204\234_v8.md"
 M ../research/index.md
 M "../research/\354\227\220\354\235\264\354\240\204\355\212\270\355\214\200_\352\265\254\354\204\261.md"
?? wiki/records/handoff/_prompts/S-AUDIT-SWEEP-2.md
?? wiki/records/handoff/_prompts/S-AUDIT-SWEEP.md
?? wiki/records/handoff/_prompts/S-PROMPT-AUDIT-WIRING.md
?? wiki/records/handoff/_prompts/S-PROMPT-WIRING-DISCUSS.md
?? "wiki/records/history/2026-08-18_0010_S-AUDIT-SWEEP_\352\265\220\354\260\250\352\262\200\354\246\235.md"
?? wiki/records/history/2026-08-18_S-PROMPT-AUDIT-WIRING.md
?? "wiki/records/reports/2026-08-18_S-AUDIT-SWEEP-2_\353\246\254\355\217\254\355\212\270.md"
?? "wiki/records/reports/2026-08-18_S-AUDIT-SWEEP_\353\246\254\355\217\254\355\212\270.md"
?? "wiki/records/reports/2026-08-18_S-PROMPT-AUDIT-WIRING_\353\246\254\355\217\254\355\212\270.md"
?? "wiki/records/reports/2026-08-18_S-PROMPT-WIRING-DISCUSS_\352\262\200\355\206\240.md"
?? eval/label_holdout_template.py
?? eval/stats/agreement.py
?? eval/tests/test_holdout_labeling.py
?? prompts/order_shipping/
?? prompts/return_exchange/
?? scripts/register_prompts.py
?? tests/integration/llm/
?? tests/unit/tools/
?? ../final_project_sample/.dockerignore
?? ../final_project_sample/.pytest-tmp/
?? ../final_project_sample/app/infrastructure/db/migrations/004_agent_runs_active_uniqueness.sql
?? ../final_project_sample/app/infrastructure/db/migrations/005_outbox_dedupe_key_tenant_scoped.sql
?? ../final_project_sample/app/modules/customer_ops/response_review.py
?? ../final_project_sample/app/modules/customer_ops/response_review_policy.py
?? ../final_project_sample/app/presentation/composer_auth.py
?? ../final_project_sample/docs/evidence/DoD-29_ResponseGenerationReview.md
?? ../final_project_sample/docs/handoff/_prompts/S-BUGHUNT-07-COMPOSER-EVAL.md
?? "../final_project_sample/docs/handoff/_prompts/S-BUGHUNT-08-\354\240\204\354\262\264\354\240\220\352\262\200.md"
?? ../final_project_sample/docs/handoff/_prompts/S-COMPOSER-V2-JWT.md
?? ../final_project_sample/docs/handoff/_prompts/S-EXAMPLES-SEPARATION-AUDIT.md
?? ../final_project_sample/docs/handoff/_prompts/S-RESPONSE-REVIEW-TEAM.md
?? "../final_project_sample/docs/history/2026-08-18_Billing_Technical_examples_\353\266\204\353\246\254.md"
?? "../final_project_sample/docs/reports/2026-08-17_\353\262\204\352\267\270\354\202\254\353\203\245_07_Composer_eval.md"
?? "../final_project_sample/docs/reports/2026-08-18_Billing_Technical_examples_\353\266\204\353\246\254_\353\246\254\355\217\254\355\212\270.md"
?? ../final_project_sample/docs/reports/2026-08-18_S-COMPOSER-V2-JWT.md
?? "../final_project_sample/docs/reports/2026-08-18_S-RESPONSE-REVIEW-TEAM_DoD-29_\353\246\254\355\217\254\355\212\270.md"
?? "../final_project_sample/docs/reports/debugs/2026-08-17_\353\262\204\352\267\270\354\202\254\353\203\245_06_\353\217\231\354\213\234\354\213\244\355\226\211\352\260\200\353\223\234_\352\262\275\355\225\251_\354\210\230\354\240\225.md"
?? "../final_project_sample/docs/reports/debugs/2026-08-17_\353\262\204\352\267\270\354\202\254\353\203\245_07_\354\236\204\354\213\234\355\214\214\354\235\274\353\210\204\354\210\230_\354\210\230\354\240\225_\353\260\217_\353\262\224\354\234\204\354\234\204\353\260\230.md"
?? "../final_project_sample/docs/reports/debugs/2026-08-17_\353\262\204\352\267\270\354\202\254\353\203\245_08_\353\257\270\355\225\264\352\262\2603\352\261\264_\354\262\230\353\246\254.md"
?? "../final_project_sample/docs/reports/debugs/2026-08-18_Composer_v2_ResponseReview_\352\262\200\354\210\230.md"
?? ../final_project_sample/examples/
?? ../final_project_sample/tests/integration/controller/test_active_run_uniqueness.py
?? ../final_project_sample/tests/unit/application/
?? ../final_project_sample/tests/unit/teams/test_response_review_team.py
?? ../final_project_ui/UsersPLAYDA~1AppDataLocalTempfinal_project_ui-pytest-exact/
?? ../final_project_ui/console/composer.py
?? ../final_project_ui/docs/backup/
?? "../final_project_ui/docs/reports/2026-08-18_P10_\353\213\244\354\244\221\355\224\204\353\241\234\354\240\235\355\212\270_\354\213\244\354\246\235.md"
?? "../final_project_ui/docs/reports/2026-08-18_P11_Composer_\354\223\260\352\270\260\354\261\204\353\204\220.md"
?? "../final_project_ui/docs/reports/2026-08-18_P12_Composer_UI_\354\235\264\354\240\204_\353\260\217_\353\214\200\354\203\201_\354\240\234\352\261\260.md"
?? ../final_project_ui/tests/test_composer.py
?? ../final_project_ui/tests/test_composer_web.py
?? ../research/_prompts/
?? "../research/_\354\240\225\353\263\270\353\214\200\354\241\260_2026-08-18.md"
```
