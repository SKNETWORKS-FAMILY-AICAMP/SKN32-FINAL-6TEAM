# DoD 구현 갭 분석

## 1. 요약

정적 코드와 테스트 파일을 기준으로 29개 DoD 중 **구현됨 18개**, **부분 구현 9개**, 미구현 1개, 판정 불가 1개로 판정했다. 핵심 런타임 골격은 존재한다. `final_project_cs/config/project.yaml`에서 활성 Team은 `voc_store_manager` 하나이며, 다수 Team을 전제로 한 계획과 실제 등록 상태 사이에는 차이가 있다(`final_project_cs/config/project.yaml:1-21`). 상태 전이·이벤트·outbox·계약·A2A·proposal guard는 코드와 테스트가 연결되어 있다. 평가 harness, 통계 report·CI gate, 파인튜닝 비교 경로, 정기 스케줄러처럼 운영·평가 단계에 해당하는 항목은 없거나 일부만 확인된다.

조사 대상 구조도 확인했다. `app/`에는 `application`, `core`, `domain`, `infrastructure`, `modules`, `presentation`, `tools`가 있고, `presentation` 아래에 REST API·MCP·A2A·UI 진입점이 있다. DB migration은 `001_schema.sql`, `002_domain_commerce.sql` 두 파일이다. 테스트는 `architecture`, `contract`, `e2e`, `integration`, `live`, `security`, `unit`으로 나뉜다. `app/core/contracts.py`에는 `ContextPack`, `TeamTask`, `ActionProposal`, `TeamResult`, `TeamManifest`, `TeamModule`, `MessageBrokerPort`가 정의되어 있고(`final_project_cs/app/core/contracts.py:122-157`, `165-193`, `201-295`, `303-345`), `app/application/controller.py`가 Registry·Context Broker·Executor·transition을 연결한다(`final_project_cs/app/application/controller.py:26-60`, `107-170`).

## 2. 항목별 판정표

아래 요구사항 요약은 계획서 §27의 기준 문구를 그대로 유지했다. 판정은 코드와 테스트가 모두 확인되는 경우에만 구현됨으로 두었다.

| 번호 | 요구사항 요약 | 판정 | 근거 |
|---:|---|---|---|
| 1 | 원본 v4 hash 불변 | 판정 불가 | `final_project_cs` 안에서 원본 v4 파일과 기준 hash를 확인할 수 없다. 계획서의 외부 hash 비교 절차만으로는 실제 불변 여부를 코드 읽기에서 확정할 수 없다(`program/plan/A-COP_구현계획서_v8.md:1315`). |
| 2 | 상태전이 규약 | 구현됨 | 상태와 허용 전이는 `final_project_cs/app/domain/events.py:41-70`, 전이 단일 진입점과 payload 검증은 `final_project_cs/app/core/transition.py:116-151`에 있다. `final_project_cs/tests/contract/test_case_state_table.py:49-95`가 허용 전이·terminal·실패 전이를 검증한다. |
| 3 | 동시성·append-only·replay | 구현됨 | version 조건 CAS, event append, outbox insert가 한 흐름에 있다(`final_project_cs/app/core/transition.py:60-87`, `153-203`). replay는 event만 읽어 `fold_events`를 호출한다(`final_project_cs/app/core/transition.py:215-227`). `final_project_cs/tests/integration/db/test_db_integration.py:59-91`, `final_project_cs/tests/unit/core/test_case_reducer.py:112-142`가 version conflict·dedupe·replay를 검증한다. |
| 4 | checkpoint/projection 분리 | 부분 구현 | `CaseService.checkpoint`는 business-state snapshot이 아닌 별도 checkpoint로 구현되어 있다(`final_project_cs/app/application/case_service.py:46-59`). 그러나 `app/infrastructure/graph_projection/`에 실제 projection 구현·replay 경로가 확인되지 않고, checkpoint와 graph projection 분리를 검증하는 전용 test도 없다. |
| 5 | ContextPack ≤12,000 | 구현됨 | `ContextPack.token_budget`가 literal `12000`이고 초과를 거부한다(`final_project_cs/app/core/contracts.py:122-156`). `final_project_cs/tests/contract/test_contracts.py:82-106`의 `test_context_pack_rejects_over_budget`, `test_context_pack_accepts_exact_budget`, `test_token_budget_is_literal_12000`이 검증한다. |
| 6 | 정책/FAQ 25건·300~400 chunk | 구현됨 | corpus 로드와 ingest 경로는 `final_project_cs/knowledge/ingest.py:63-70`, `86-101`에 있다. `final_project_cs/tests/integration/rag/test_rag_integration.py:9-29`가 25문서·306 chunk와 1536차원 embedding을 검증하고, 같은 파일 `45-49`가 tenant·scope 격리를 검증한다. |
| 7 | tenant scope·PII redaction | 구현됨 | tenant 조건은 `final_project_cs/app/core/transition.py:54-58`, redaction은 `final_project_cs/app/core/redaction.py:1-25`와 `final_project_cs/app/core/transition.py:148-151`에 있다. `final_project_cs/tests/security/test_pii_redaction_runtime.py:43-67`의 `test_case_message_is_redacted_in_db_api_and_audit`와 `final_project_cs/tests/security/test_scope_contract.py:8-18`이 검증한다. |
| 8 | TeamModule·manifest 호환 | 구현됨 | `TeamModule` Protocol과 `TeamManifest`가 `final_project_cs/app/core/contracts.py:299-330`에 있고, Registry가 contract version·중복 Team을 검사한다(`final_project_cs/app/core/registry.py:38-45`). `final_project_cs/tests/contract/test_team_contract.py:7-19`가 manifest 계약을 검증한다. |
| 9 | 인라인 분류 | 구현됨 | 분류 실패를 명시적으로 `classification_failed`로 기록하고 성공 시 routing으로 연결하는 흐름이 `final_project_cs/app/presentation/api/cases.py:65-107`과 `final_project_cs/app/modules/customer_ops/feedback.py:86-106`에 있다. `final_project_cs/tests/integration/api/test_api_runtime.py:162-200`, `final_project_cs/tests/unit/voc/test_feedback.py:16-35`가 성공·실패 경로를 검증한다. |
| 10 | 일일 배치 report | 부분 구현 | tenant별 7일 집계·ratio·surge alert·upsert report는 `final_project_cs/app/application/feedback_job.py:30-77`에 있다. `final_project_cs/tests/unit/voc/test_feedback.py:43-70`, `final_project_cs/tests/unit/voc/test_feedback_runtime.py:4-48`가 산식을 검증하지만, 실제 scheduled-job 등록·실행기는 확인되지 않았다. |
| 11 | action·approval·idempotency·unknown | 구현됨 | 서버 idempotency key 생성과 action request 저장은 `final_project_cs/app/application/controller.py:227-252`, `final_project_cs/app/core/idempotency.py:1-12`, `final_project_cs/app/infrastructure/db/repository.py:42-50`에 있다. approval·unknown·timeout 관련 테스트는 `final_project_cs/tests/contract/test_contracts.py:154-210`, `final_project_cs/tests/integration/controller/test_provider_timeout_unknown.py:41-123`, `final_project_cs/tests/integration/api/test_recheck_before_execution.py:1-100`에 있다. |
| 12 | outbox 원자성·worker replay | 부분 구현 | transition과 outbox insert의 원자적 경계와 dedupe는 `final_project_cs/app/core/transition.py:81-87`, `190-203`, worker의 pending/processing/unknown/dead_letter 처리는 `final_project_cs/app/infrastructure/messaging/worker.py:18-48`에 있다. DB dedupe test는 `final_project_cs/tests/integration/db/test_db_integration.py:81-91`에 있지만, `OutboxWorker` failure injection 후 replay를 직접 검증하는 test는 확인되지 않았다. |
| 13 | MVP REST 5 + MCP 3 contract | 구현됨 | REST API 앱과 case/composer 진입점은 `final_project_cs/app/presentation/api/app.py:1-80`, `final_project_cs/app/presentation/api/cases.py:1-110`, `final_project_cs/app/presentation/api/composer.py:1-80`에 있고 MCP 3개 tool은 `final_project_cs/app/presentation/api/mcp.py:5-20`에 있다. `final_project_cs/tests/integration/api/test_openapi_surface.py:1-120`, `final_project_cs/tests/security/test_scope_contract.py:15-18`가 surface와 MCP 3개를 검증한다. |
| 14 | API key scope | 구현됨 | scope 검사는 `final_project_cs/app/presentation/security.py:1-80`에 있고 MCP tool은 `mcp:read`를 요구한다(`final_project_cs/app/presentation/api/mcp.py:7-18`). `final_project_cs/tests/security/test_scope_contract.py:8-18`과 `final_project_cs/tests/e2e/test_composer_write_channel.py:121-130`이 scope·인증 실패를 검증한다. |
| 15 | A/B/Proposed·holdout | 미구현 | `final_project_cs/app`과 `final_project_cs/tests`에서 60건×3회 harness, holdout checksum, A/B/Proposed 실행 경로를 확인할 수 없다. 관련 계획서 기준은 `program/plan/A-COP_구현계획서_v8.md:1329`에 있다. |
| 16 | bootstrap CI·McNemar·한계 | 부분 구현 | paired bootstrap과 95% CI 산식은 `final_project_cs/eval/stats/bootstrap.py:11-36`, McNemar exact·근사 계산은 `final_project_cs/eval/stats/mcnemar.py:11-52`에 있다. `final_project_cs/eval/tests/test_stats_and_datasets.py:8-38`이 두 통계 경로를 검증한다. 다만 DoD 15 결과를 입력으로 받아 한계와 함께 단일 report를 만들고 CI gate로 연결하는 경로는 확인되지 않는다. |
| 17 | milestone gate·기능 동결 | 부분 구현 | Contract 모델 test와 SQL migration은 존재한다(`final_project_cs/tests/contract/test_contracts.py:72-246`, `final_project_cs/app/infrastructure/db/migrations/001_schema.sql:1-29`). 그러나 CI milestone gate, Contract Freeze 기록, Alembic upgrade/downgrade는 확인되지 않는다. |
| 18 | Case UI·trace·approval·VOC | 부분 구현 | UI가 Case 상태·degraded·approval·outbox 지표를 표시하는 코드는 `final_project_cs/app/presentation/ui/routes.py:90-170`, `250-270`에 있고 E2E는 `final_project_cs/tests/e2e/test_operations_ui.py:1-140`에 있다. 다만 요청한 전체 Case UI trace·approval·VOC report E2E 시나리오를 한 번에 검증하는 test는 확인되지 않는다. |
| 19 | LOCAL/A2A가 동일 `TeamResult`로 정규화 | 구현됨 | Local adapter와 A2A adapter 모두 `TeamResult`를 반환한다(`final_project_cs/app/core/remote_team/executor.py:8-19`, `final_project_cs/app/core/remote_team/a2a_executor.py:46-85`). `final_project_cs/tests/unit/ports/test_team_ports.py:26-67`가 Local 결과와 A2A 상태 매핑을 검증한다. |
| 20 | `TeamExecutorPort` 교체 시 Controller 불변 | 구현됨 | Controller는 `team_executor`를 주입받고 기본값만 Local adapter로 만든다(`final_project_cs/app/application/controller.py:26-60`). Local/A2A 선택과 Controller 주입은 `final_project_cs/app/composition.py:141-149`, `171-190`에 있다. `final_project_cs/tests/unit/ports/test_team_ports.py:39-66`은 두 adapter의 계약을 검증하지만, `TeamExecutorPort` 교체 시 Controller 불변을 직접 검증하는 테스트는 찾지 못했다. |
| 21 | `SqlGraphAdapter` 관계 질의 3종 정확성 | 구현됨 | Case→Issue, Issue→Policy, Issue→Team 축이 `final_project_cs/app/infrastructure/graphstore/sql_adapter.py:51-67`에 구현되어 있고 `neighbors`, `path`, `subgraph`가 `final_project_cs/app/infrastructure/graphstore/sql_adapter.py:25-119`에 있다. `final_project_cs/tests/integration/graph/test_sql_graph_adapter.py:1-180`과 `final_project_cs/tests/unit/infrastructure/test_graph_v7_axes.py:1-150`이 검증한다. |
| 22 | Team의 직접 Tool 호출 금지 | 부분 구현 | Tool registry 자체는 `final_project_cs/app/tools/read_tools.py:99-115`에 있다. 하지만 Team 구현이 직접 `tools.call`을 호출한다(`final_project_cs/app/modules/customer_ops/voc_store_manager.py:46-51`). 전 Team AST/import 금지 검사와 runtime spy test는 확인되지 않았다. |
| 23 | 모든 consumer at-least-once idempotency | 부분 구현 | action request와 outbox에 dedupe key·unique 제약이 있다(`final_project_cs/app/infrastructure/db/migrations/001_schema.sql:17-19`, `final_project_cs/app/infrastructure/db/repository.py:42-44`). 그러나 모든 consumer에 동일 message 2회 전달을 적용하는 공통 integration test는 확인되지 않았다. |
| 24 | ActionProposal 근거 대조·실행 차단 | 구현됨 | proposal 검증과 재검증은 `final_project_cs/app/application/proposal_guard.py:58-109`, Controller 차단·감사 payload는 `final_project_cs/app/application/controller.py:180-221`에 있다. `final_project_cs/tests/unit/core/test_proposal_verification.py:1-145`, `final_project_cs/tests/integration/controller/test_proposal_guard_blocks.py:148-164`, `final_project_cs/tests/integration/api/test_recheck_before_execution.py:1-100`이 검증한다. |
| 25 | degraded Context 자동 실행 금지 | 구현됨 | ContextBroker가 retrieval 실패·정책 누락을 degraded로 표시한다(`final_project_cs/app/core/context.py:252-274`). Controller가 proposal을 escalated로 바꾼다(`final_project_cs/app/application/controller.py:180-188`). `final_project_cs/tests/integration/controller/test_proposal_guard_blocks.py:148-164`, `final_project_cs/tests/unit/teams/test_voc_store_manager.py:42-48`이 검증한다. |
| 26 | A2A Catalog Verification 왕복 | 구현됨 | Remote Agent의 Card·submit·poll·input·artifact 경로는 `final_project_cs/app/presentation/a2a/remote_agent.py:65-123`, HTTP transport는 `final_project_cs/app/infrastructure/a2a/http_transport.py:23-75`에 있다. `final_project_cs/tests/integration/a2a/test_remote_round_trip.py:1-120`이 Card 발견부터 input-required와 완료까지 검증한다. |
| 27 | A2A 실패·타임아웃·취소·인증 | 구현됨 | A2A executor가 deadline·failed·cancelled를 분기한다(`final_project_cs/app/core/remote_team/a2a_executor.py:17-26`, `56-85`). Remote Agent가 인증·실패·지연·취소 fixture를 제공한다(`final_project_cs/app/presentation/a2a/remote_agent.py:45-52`, `76-87`, `125-137`). `final_project_cs/tests/integration/a2a/test_remote_round_trip.py:1-160`이 해당 결과를 검증한다. |
| 28 | 파인튜닝 경로와 방어 지표 | 부분 구현 | 방어 지표의 분모와 스키마 검사는 `final_project_cs/app/core/verification.py:1-120`, `final_project_cs/tests/unit/eval/test_defense_metrics.py:1-100`에 있다. 공개 1차·알파 2차 모델 비교, golden/holdout 실행, 파인튜닝 산출물과 CI 기록은 확인되지 않는다. |
| 29 | Response Generation & Review의 GEN→REV·재시도·개인정보 검증 | 구현됨 | Response Review Team의 생성·검토·재시도·PII 차단은 `final_project_cs/app/modules/customer_ops/response_review.py:1-160`, `final_project_cs/app/modules/customer_ops/response_review_policy.py:1-39`에 있다. `final_project_cs/tests/unit/teams/test_response_review_team.py:53-141`, `final_project_cs/tests/unit/teams/test_response_review.py:40-141`이 정상 흐름·재시도 상한·PII 차단을 검증한다. |

## 3. 미구현·부분 구현 항목의 상세

### 1) 기준 hash와 외부 평가 경로

1번은 원본 문서와 저장소 hash를 함께 비교해야 한다. `final_project_cs` 코드만으로는 비교 대상 원본과 기준값을 확정할 수 없다.

15번은 A/B/Proposed와 holdout 실행 harness가 없다. 60건×3회 로그와 checksum도 확인되지 않는다.

16번은 McNemar와 paired bootstrap CI 산식 및 단위 test가 있다. DoD 15 실행 결과를 받아 통계·한계를 단일 report로 만들고 CI gate에 연결하는 경로는 없다.

### 2) 데이터·배치·운영 경로

10번은 `run_daily_feedback` 함수가 있지만 스케줄러가 없다. 함수 호출을 일일 배치로 등록하는 운영 경로가 확인되지 않는다.

12번은 outbox 원자성·재시도 상태 전이는 구현되어 있다. 다만 worker가 실패한 pending row를 다시 처리하는 전용 failure injection test가 없다.

17번은 migration과 contract test는 있다. CI gate, Contract Freeze 기록, Alembic lifecycle은 없다.

### 3) 아키텍처 경계와 범위

4번은 checkpoint 저장과 event projection이 개념적으로 분리되어 있다. graph projection 디렉터리의 실제 구현과 분리 검증은 부족하다.

18번은 UI가 상태·approval·degraded 정보를 표시한다. trace와 VOC report까지 포함하는 단일 E2E 시나리오는 확인되지 않는다.

22번은 Tool registry를 통한 호출 기능은 있지만, 실제 `VocStoreManagerTeam`이 Tool을 직접 호출한다. 계획서의 직접 호출 금지와 현재 코드가 충돌한다.

23번은 action과 outbox의 dedupe가 있다. 모든 consumer에 대한 at-least-once duplicate/replay 검증은 없다.

28번은 defense metrics 단위 검증만 있다. 모델 비교와 파인튜닝 결과를 생산하는 경로는 없다.

## 4. 테스트로 검증되는 항목 목록

자동 테스트 파일과 함수명을 기준으로 다음 항목이 직접 검증된다.

- 2번: `tests/contract/test_case_state_table.py` — `test_allowed_next_statuses_match_v5`, `test_all_twelve_statuses_exist`, `test_cancelled_is_terminal`, `test_classification_failure_escalates_not_silently_continues`, `test_wait_expiry_escalates_not_auto_resolves`.
- 3번: `tests/integration/db/test_db_integration.py` — `test_transition_round_trip_and_versions`, `test_version_conflict`, `test_outbox_dedupe`; `tests/unit/core/test_case_reducer.py` — `test_fold_reproduces_step_by_step_result`, `test_replay_is_deterministic`, `test_version_always_equals_event_count`.
- 5번: `tests/contract/test_contracts.py` — `test_context_pack_rejects_over_budget`, `test_context_pack_accepts_exact_budget`, `test_token_budget_is_literal_12000`.
- 6번: `tests/integration/rag/test_rag_integration.py` — `populated_demo`, `test_corpus_counts_and_embedding_dimension`, `test_tenant_isolation_and_scope_filter`.
- 7번: `tests/security/test_pii_redaction_runtime.py` — `test_case_message_is_redacted_in_db_api_and_audit`; `tests/security/test_scope_contract.py` — `test_nine_scopes_are_guardrail_owned`, `test_mcp_has_exactly_three_read_scoped_tools`.
- 8번: `tests/contract/test_team_contract.py` — `test_team_manifests_implement_protocol`, `test_manifest_scopes_are_exact`.
- 9번: `tests/integration/api/test_api_runtime.py` — classification success/failure assertions in `test_*`; `tests/unit/voc/test_feedback.py` — `test_classify_rejects_incomplete_output` 계열.
- 10번: `tests/unit/voc/test_feedback.py` — `test_daily_report_is_idempotent`, surge 경계 검증; `tests/unit/voc/test_feedback_runtime.py` — `test_*` report runtime 검증.
- 11번: `tests/contract/test_contracts.py` — `test_approval_required_proposal_forces_wait_for_approval`, `test_proposal_cannot_cite_unknown_evidence`; `tests/integration/controller/test_provider_timeout_unknown.py` — `test_provider_timeout_stays_unknown_and_is_not_retried`; `tests/integration/api/test_recheck_before_execution.py` — recheck 차단 검증.
- 13~14번: `tests/integration/api/test_openapi_surface.py`, `tests/security/test_scope_contract.py`, `tests/e2e/test_composer_write_channel.py` — OpenAPI surface, MCP 3개 scope, 만료·위조 인증 검증.
- 16번: `eval/tests/test_stats_and_datasets.py` — bootstrap 고정 seed·0 포함·양의 차이와 McNemar exact·근사 분기를 검증한다.
- 19번: `tests/unit/ports/test_team_ports.py` — Local 결과와 A2A 상태 정규화를 검증한다.
- 20번: `TeamExecutorPort` 교체 시 Controller 불변을 직접 검증하는 테스트는 찾지 못했다.
- 21번: `tests/integration/graph/test_sql_graph_adapter.py`, `tests/unit/infrastructure/test_graph_v7_axes.py` — 관계 질의와 세 축을 검증한다.
- 24번: `tests/unit/core/test_proposal_verification.py` — proposal mismatch 전수 보고; `tests/integration/controller/test_proposal_guard_blocks.py` — `test_core_blocks_proposals_when_context_is_degraded`와 guard 차단; `tests/integration/api/test_recheck_before_execution.py`.
- 25번: `tests/unit/teams/test_voc_store_manager.py` — `test_degraded_context_escalates_without_policy_lookup`; `tests/integration/controller/test_proposal_guard_blocks.py` — `test_core_blocks_proposals_when_context_is_degraded`.
- 26~27번: `tests/integration/a2a/test_remote_round_trip.py` — remote round-trip, failure, timeout, cancel, auth 시나리오 함수들.
- 29번: `tests/unit/teams/test_response_review_team.py` — `test_normal_generation_review_returns_contract_result`, `test_forbidden_word_retries_then_escalates`, `test_fact_mismatch_retries_and_later_pass_is_recorded`, `test_pii_escalates_without_retry`; `tests/unit/teams/test_response_review.py` — 생성·재시도·PII 검증 함수들.

## 5. 판정 불가 항목과 그 이유

1번만 판정 불가로 두었다. 이 항목은 코드의 존재 여부가 아니라 원본 v4 문서와 현재 저장소의 hash 값이 같다는 외부 비교 결과를 요구한다. 현재 조사 범위에서 그 비교를 실행하지 않았고, `final_project_cs` 내부에도 기준 hash가 없다.

## 6. 이 분석의 한계

이번 분석은 `program/plan/A-COP_구현계획서_v8.md` §27과 `final_project_cs/`의 파일을 정적으로 읽은 결과다. `final_project_sample/`은 열지 않았다. 프로그램 실행, pytest 실행, DB 연결, 외부 Agent 호출, 성능 측정, hash 비교는 수행하지 않았다. 따라서 테스트 파일에 검증 코드가 있어도 실제 실행 통과까지를 의미하지 않는다.

## 출력 요약

- 보고서 파일: `program/research/_DoD_구현갭_분석.md`
- 판정 분포: 구현됨 18개 / 부분 9개 / 미구현 1개 / 판정불가 1개
- 가장 큰 갭 5개: A/B/Proposed·holdout harness 부재, 통계 report·CI gate 연결 부재, 활성 Team이 `voc_store_manager` 하나인 구성, 파인튜닝 비교 경로 부재, Team 직접 Tool 호출 금지와 실제 호출의 충돌
