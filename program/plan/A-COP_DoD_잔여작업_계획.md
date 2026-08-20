# A-COP DoD 잔여작업 계획

## 1. 범위와 판단 기준

이 문서는 `program/research/_DoD_구현갭_분석.md`의 재계산 판정을 출발점으로 삼는다. 대상은 부분 구현 9개와 미구현 1개다. 구현됨으로 판정된 18개는 다루지 않는다.

대상은 DoD 4·10·12·15·16·17·18·22·23·28이다. 별도로 판정 불가인 DoD 1을 판정 가능하게 만드는 작업을 적는다. DoD 6은 ingest 코드와 수량·차원·격리 테스트를 재확인해 구현됨으로 제외했다.

현재 코드는 `final_project_cs/`에서 확인했다. `final_project_sample/`은 열지 않았다. 이 문서 작성 중 테스트는 실행하지 않았다.

## 2. 처리 순서 요약

권장 순서는 다음과 같다.

1. DoD 17 — Contract Freeze와 CI gate
2. DoD 4 — checkpoint와 graph projection 분리
3. DoD 12 — outbox worker failure injection과 replay
4. DoD 23 — 모든 consumer의 at-least-once 중복 처리
5. DoD 10 — 일일 VOC report 실행 경로
6. DoD 22 — Team의 직접 Tool 호출 금지
7. DoD 18 — Case UI의 trace·approval·VOC 단일 E2E
8. DoD 15 — A/B/Proposed holdout harness와 공통 metric·report schema 동결
9. DoD 16 — bootstrap CI·McNemar·통계 report
10. DoD 28 — defense metric과 두 모델 비교 경로

17을 먼저 고정하는 이유는 이후 작업의 계약과 migration 검증 기준이 바뀌지 않아야 하기 때문이다. 4는 중간발표에서 보여줄 Case trace의 기반이다. 12와 23은 상태 전이와 외부 전달의 재처리 위험을 먼저 줄인다. 15가 공통 schema를 소유한 뒤 16과 28이 이를 소비하게 해 평가 작업의 의존 방향을 하나로 고정한다.

일정 배분은 §25의 공식 일정에 맞춘다.

| 기간 | 배분 | 산출물 |
|---|---|---|
| 1W, 8/28~9/3 | 17의 CI·Contract Freeze 골격 | freeze 기록 형식, migration gate, 계약 테스트 명령 |
| 2W, 9/4~9/10 | 4의 구현과 fixture | projection/checkpoint 경계 검증 |
| 3W, 9/11~9/17 | 10·18의 중간발표 경로 | 일일 VOC report와 Case trace·approval·degraded 화면 E2E |
| 4W, 9/18~9/28 | 12·23·22 | worker 재처리, consumer 중복 방지, Tool 호출 경계 |
| 5W, 9/29~10/6 | 15의 평가 harness와 schema 동결 | 60/20 fixture 계약, holdout checksum, 공통 metric·report schema |
| 6W, 10/7~10/14 | 16 | paired bootstrap, McNemar, 통계 report와 CI gate 연결 |
| 7W, 10/15~10/21 | 28 | defense metric과 공개 1차·알파 2차 비교 결과 |
| 8W, 10/21~10/24 | 전체 DoD 재검증 | 입력·결과·증거 파일 고정, 최종 발표 시나리오 |
| 9W, 10/26 | 최종발표 | 결과 report와 데모 재현 |

중간발표에는 DoD 4·10·18과 구현 확인이 끝난 DoD 6을 우선 노출한다. 최종발표에는 12·15·16·23·28의 재처리와 평가 결과를 추가한다.

### DoD 15→16→28 처리 순서

DoD 15에서 `eval/contracts/evaluation_report.schema.json`을 만들고 case 식별자, arm, repeat, dataset hash, metric 이름, numerator, denominator, point estimate, seed, model, temperature, prompt version 필드를 동결한다. DoD 16은 이 schema를 입력으로 paired bootstrap CI, McNemar table, p-value와 한계 필드를 채운다. DoD 28은 같은 schema와 DoD 16 report 형식을 소비해 스키마 준수율·근거 정합률·근거 초과율·적절한 기권율·과잉 기권율을 추가한다.

이 순서는 계획서 원문의 DoD 16 통계 산식·한계 요구와 DoD 28 동일 golden/holdout·분모·CI 요구를 함께 만족한다. 공통 schema를 DoD 15가 소유하면 DoD 16이 DoD 28의 metric schema를 기다리거나 DoD 28이 DoD 16의 report schema를 기다리는 순환이 사라진다.

## 3. 항목별 실행 계획

### DoD 4. checkpoint와 projection 분리

**무엇이 빠졌는가.** `app/application/case_service.py`의 `CaseService.checkpoint()`는 business-state snapshot이 아니라 `case_id`, `run_id`, `graph_revision`, `node_name`, `runtime_state`를 반환하는 disposable graph checkpoint다. 그러나 `app/infrastructure/graph_projection/`에는 실질 구현이 없고, event를 graph projection으로 재생하는 경로와 checkpoint와 projection이 서로 독립임을 보이는 검증도 없다. 추가 요구는 만들지 않고, 계획서의 “graph revision 변경과 projection replay” 기준을 충족한다.

**어디를 손대는가.** `final_project_cs/app/infrastructure/graph_projection/__init__.py`에 둔 현재 골격을 기준으로 `projector.py`를 추가한다. 필요하면 projection 저장 구조를 `final_project_cs/app/infrastructure/db/migrations/003_graph_projection.sql`에 추가한다. 기존 event 읽기는 `final_project_cs/app/infrastructure/db/repository.py`와 `final_project_cs/app/core/transition.py`의 append-only 계약을 사용한다. 테스트는 `final_project_cs/tests/integration/graph/test_checkpoint_projection.py`를 새로 둔다.

**선행 조건.** DoD 17의 migration gate가 먼저다. event schema와 graph revision 명칭을 고정한 뒤 구현해야 한다.

**작업 규모.** 큼(3일 이상). projection 저장·재생·revision 경계가 새로 필요하고, checkpoint가 business projection을 오염시키지 않는다는 회귀 범위가 넓다.

**검증 방법.** `test_checkpoint_does_not_mutate_business_projection`, `test_projection_replay_from_case_events_is_deterministic`, `test_graph_revision_change_requires_replay`를 추가한다. 같은 event stream을 두 번 replay했을 때 같은 node·edge가 생기고, checkpoint runtime state만 바꿔도 business projection은 달라지지 않아야 한다.

### DoD 6. 재판정 확인

`final_project_cs/knowledge/ingest.py:63-70`, `86-101`에 corpus 로드·수량 계산·ingest 경로가 있다. `final_project_cs/tests/integration/rag/test_rag_integration.py:9-29`, `45-49`가 25문서·306 chunk·1536차원 embedding과 tenant·scope 격리를 검증한다. 잔여 구현 대상에서 제외한다.

### DoD 10. 일일 VOC report 실행 경로

**무엇이 빠졌는가.** `final_project_cs/app/application/feedback_job.py`의 `run_daily_feedback()`는 tenant별 7일 집계, ratio, surge 조건, report upsert, alert outbox insert를 구현한다. 그러나 이 함수를 실제 scheduled job으로 등록·호출하는 운영 경로가 없다. 현재 테스트도 함수와 DB 결과를 확인할 뿐 scheduler 등록이나 실행 실패 처리를 증명하지 않는다.

**어디를 손대는가.** `final_project_cs/app/application/feedback_job.py`의 순수 집계 계약은 유지한다. 실행 진입점은 `final_project_cs/app/application/scheduled_jobs.py`를 새로 두고 tenant 목록 조회와 report_date 전달을 맡긴다. 스케줄 등록 방식이 애플리케이션 수명주기에 있다면 `final_project_cs/app/presentation/api/app.py`에 연결한다. 테스트는 `final_project_cs/tests/unit/voc/test_feedback.py`와 `final_project_cs/tests/unit/voc/test_feedback_runtime.py`를 보강하고, scheduler 단위 테스트 파일 `final_project_cs/tests/unit/voc/test_feedback_scheduler.py`를 추가한다.

**선행 조건.** 구현 확인이 끝난 DoD 6 corpus 계약과 DoD 17의 migration gate를 기준으로 삼는다. DoD 12는 alert outbox의 실제 전달 전에도 report 생성 검증이 가능하므로 후행 조건이다.

**작업 규모.** 작음(반나절 이내). 집계 함수와 upsert가 이미 있어 등록·호출·중복 실행 검증이 핵심이다.

**검증 방법.** `test_scheduler_runs_once_per_tenant_and_report_date`, `test_daily_report_is_idempotent`, `test_surge_alert_is_written_to_outbox_once`를 추가한다. 동일 날짜를 두 번 실행해 report 한 건과 alert dedupe 한 건만 남고, 다른 tenant가 섞이지 않아야 한다.

### DoD 12. outbox worker replay

**무엇이 빠졌는가.** `final_project_cs/app/infrastructure/messaging/worker.py`의 `OutboxWorker`는 pending row를 processing으로 claim하고, 일시 오류는 unknown, 일반 오류는 pending 또는 dead_letter, 성공은 delivered로 바꾼다. 그러나 publisher failure injection으로 pending 재처리와 unknown·dead_letter 경계를 직접 검증하는 테스트가 없다. 현재 DB dedupe는 insert 경로에 집중되어 있다.

**어디를 손대는가.** 주 구현은 `final_project_cs/app/infrastructure/messaging/worker.py`다. 필요하면 retry 대상의 `available_at`, `attempts`, `last_error` 갱신을 migration의 현재 schema와 맞춘다. `final_project_cs/tests/integration/messaging/test_outbox_worker_replay.py`를 새로 두고 connection factory와 publisher를 주입한다.

**선행 조건.** DoD 17의 migration gate가 먼저다. DoD 23의 consumer idempotency는 worker가 전달한 동일 message를 안전하게 소비하는 검증이므로 12 뒤에 둔다.

**작업 규모.** 중간(1~2일). 상태 전이 자체는 있으나 transaction 경계, 재시도 횟수, unknown의 수동 확인 경계를 함께 고정해야 한다.

**검증 방법.** `test_transient_failure_returns_row_to_pending`, `test_timeout_marks_unknown_without_automatic_retry`, `test_max_attempts_moves_to_dead_letter`, `test_success_after_replay_is_delivered`를 추가한다. failure injection 후 attempts·status·last_error·available_at을 DB에서 확인한다.

### DoD 15. A/B/Proposed holdout harness

**무엇이 빠졌는가.** `final_project_cs/eval/runners/baseline_a.py`, `baseline_b.py`, `proposed.py`와 golden·holdout 파일은 이미 있다. 그러나 60건 입력, 20건 holdout, 각 runner의 동일 입력 실행, holdout checksum, 결과 로그를 하나의 재현 가능한 harness로 묶은 경로가 없다. 따라서 현재 report 파일만으로는 정해진 평가가 실행됐는지 판정할 수 없다.

**어디를 손대는가.** 공통 입력·출력 계약은 `final_project_cs/eval/runners/common.py`에 둔다. `final_project_cs/eval/harness.py`를 새로 만들어 60/20 분리, checksum, A/B/Proposed 실행, raw 결과 저장을 담당하게 한다. 공통 metric·report 계약은 `final_project_cs/eval/contracts/evaluation_report.schema.json`에 둔다. 결과 파일은 `final_project_cs/eval/reports/`에 남긴다. 데이터 검증은 `final_project_cs/scripts/verify_eval_datasets.py`를 확장하고, 테스트는 `final_project_cs/eval/tests/test_harness.py`를 새로 둔다.

**선행 조건.** DoD 17의 CI gate가 먼저다. DoD 6의 입력 fixture를 고정한다. DoD 28 실행에 필요한 방어 fixture의 식별자와 metric 분모는 이 항목의 공통 schema 동결에 포함한다.

**작업 규모.** 큼(3일 이상). 세 runner의 입력·출력 schema, holdout 분리·checksum, 실패 로그와 재현 명령을 함께 설계해야 한다.

**검증 방법.** `test_harness_uses_exactly_60_eval_and_20_holdout_cases`, `test_holdout_checksum_is_recorded`, `test_all_three_runners_emit_same_case_ids`, `test_runner_failure_is_not_silent`를 둔다. holdout label은 runner 출력이 아니라 별도 정답 파일에서 읽고, 결과에 runner·dataset checksum·실행 revision을 기록한다.

### DoD 16. bootstrap CI와 McNemar 통계 report

**무엇이 빠졌는가.** `final_project_cs/eval/stats/bootstrap.py`와 `mcnemar.py`는 존재하고 관련 unit test도 있다. 하지만 DoD 15 harness의 paired 결과를 받아 paired bootstrap CI와 McNemar 검정을 계산하고 report로 저장하는 실행 경로와 CI gate가 없다. 현재 통계 함수의 존재만으로는 실제 60/20 평가가 통계 report까지 끝났다고 볼 수 없다.

**어디를 손대는가.** 기존 `final_project_cs/eval/stats/bootstrap.py`, `mcnemar.py`, `make_pairs.py`의 API를 `evaluation_report.schema.json`에 맞춘다. `final_project_cs/eval/report.py`를 새로 두고 paired 결과 입력, bootstrap seed·반복 횟수, McNemar table, CI·p-value, 분모를 포함한 report를 만든다. `final_project_cs/eval/tests/test_report.py`와 기존 `final_project_cs/eval/tests/test_stats_and_datasets.py`를 보강한다. CI 명령은 `final_project_cs/scripts/verify_eval_datasets.py`와 분리해 평가 report gate로 둔다.

**선행 조건.** DoD 15의 harness 결과와 `evaluation_report.schema.json` 동결이 먼저다. DoD 28은 이 report를 소비하는 후행 작업이다.

**작업 규모.** 큼(3일 이상). paired 표본 정렬, seed 고정, 0 분모 처리, report serialization, CI 실패 조건까지 연결해야 한다.

**검증 방법.** `test_paired_bootstrap_is_reproducible_with_seed`, `test_mcnemar_uses_discordant_pairs`, `test_report_contains_denominators_and_ci`, `test_zero_denominator_is_reported_as_unknown`, `test_report_fails_on_case_id_mismatch`를 추가한다. 동일 입력과 seed의 report가 같고, case 순서가 달라도 case_id 기준으로 pair가 맞아야 한다.

### DoD 17. milestone gate와 기능 통합

**무엇이 빠졌는가.** `final_project_cs/app/infrastructure/db/migrations/001_schema.sql`, `002_domain_commerce.sql`과 contract test는 있다. 그러나 CI에서 migration upgrade/downgrade, Contract Freeze 기록, 핵심 contract·기능 테스트를 한 번에 막는 gate가 없고 Alembic lifecycle도 확인되지 않았다.

**어디를 손대는가.** migration 관례는 `final_project_cs/app/infrastructure/db/migrations/`를 따른다. 현재 도구가 Alembic이 아니면 억지로 전환하지 않고, `final_project_cs/scripts/verify_migrations.py`를 새로 둬 빈 DB upgrade·downgrade와 schema 재적용을 검증한다. CI 설정은 `final_project_cs/.github/workflows/dod-gates.yml`에 둔다. Contract Freeze 원본은 `final_project_cs/docs/evidence/DoD-17_contract_freeze.json`에 둔다. JSON에는 대상 계약 파일과 SHA-256, schema revision, 검증 명령, git revision을 기록하고 CI artifact로도 업로드한다. Core 1 담당자가 1W 수요일까지 경로와 형식을 만들고 프로젝트 리드가 Contract Freeze Day인 1W 금요일에 확인한다.

**선행 조건.** 없음. 10개 중 가장 먼저 처리한다.

**작업 규모.** 중간(1~2일). migration 명령과 현재 계약 테스트를 연결하는 일은 중간이지만, CI 환경에서 DB 의존성을 안정화해야 한다.

**검증 방법.** `test_migrations_upgrade_from_empty_database`, `test_migrations_downgrade_and_reapply`, `test_contract_freeze_manifest_matches_tests`를 추가한다. CI gate는 migration, contract, 핵심 unit test가 실패하면 통과하지 않아야 하며 실행 revision과 schema revision을 artifact에 남긴다.

### DoD 18. Case UI·trace·approval·VOC E2E

**무엇이 빠졌는가.** `final_project_cs/app/presentation/ui/routes.py`는 Case 상세, append-only trace, approval, degraded banner, VOC 화면을 제공한다. `final_project_cs/tests/e2e/test_operations_ui.py`도 각 화면 일부를 검사한다. 그러나 한 Case가 생성되어 trace가 쌓이고, approval이 표시되며, VOC report가 같은 운영 UI 흐름에서 보이는 단일 E2E 시나리오가 없다.

**어디를 손대는가.** 기존 route와 `final_project_cs/app/presentation/ui/theme.py`의 표시 구조를 유지한다. fixture는 `final_project_cs/tests/e2e/test_operations_ui.py`의 `ui_fixture`를 확장하고, 부족하면 `final_project_cs/tests/e2e/fixtures/operations_case.py`를 새로 둔다. 테스트는 기존 파일에 `test_case_trace_approval_and_voc_are_visible_in_one_flow`를 추가한다.

**선행 조건.** DoD 10의 report 생성과 DoD 17의 schema gate가 먼저다. DoD 4의 projection은 화면에서 직접 사용하지 않는다면 선행 조건이 아니다.

**작업 규모.** 중간(1~2일). 화면 구성은 있으나 DB seed, degraded state, approval evidence, report를 한 시나리오로 맞춰야 한다.

**검증 방법.** Case 생성 후 `/ui/cases/{case_id}`, `/trace`, `/approvals`, `/voc`를 같은 tenant로 조회한다. `test_case_trace_approval_and_voc_are_visible_in_one_flow`에서 case id, event type, evidence, approval disabled/enabled 상태, report period와 alert를 모두 확인한다.

### DoD 22. Team의 직접 Tool 호출 금지

**무엇이 빠졌는가.** `final_project_cs/app/tools/read_tools.py`에 named tool registry와 `ReadToolbox.call()`이 있고, `VocStoreManagerTeam`은 현재 `self.tools.call()`을 사용한다. 갭은 현재 코드가 직접 call하는지를 정적으로나 runtime spy로 금지하지 않는다는 점이다. 계획서의 규칙은 Team이 직접 tool을 호출하지 않고 Context Broker를 통해 read 결과를 받아야 한다.

**어디를 손대는가.** 호출 경계는 `final_project_cs/app/modules/customer_ops/voc_store_manager.py`, `final_project_cs/app/tools/read_tools.py`, Context Broker 구현인 `final_project_cs/app/core/context.py`와 controller 조립부 `final_project_cs/app/composition.py`다. Tool adapter는 `final_project_cs/app/application/` 또는 `app/core/`의 port 경계를 따르는 새 adapter로 옮긴다. 테스트는 `final_project_cs/tests/architecture/test_team_tool_boundary.py`와 `final_project_cs/tests/unit/teams/test_voc_store_manager.py`에 둔다.

**선행 조건.** DoD 17의 contract freeze와 ContextPack 계약이 먼저다. 구현 확인이 끝난 DoD 6의 policy retrieval 결과 schema를 adapter 이동 기준으로 사용한다.

**작업 규모.** 작음(반나절 이내). 현재 직접 호출 지점이 좁고, 금지 규칙과 spy 검증이 명확하다.

**검증 방법.** `test_team_module_does_not_import_read_toolbox`, `test_team_receives_tool_result_from_context_broker`, `test_direct_tool_call_is_rejected_at_runtime`를 추가한다. AST/import 검사와 fake broker를 함께 사용해 Team 실행 중 `ReadToolbox.call()`이 호출되지 않음을 확인한다.

### DoD 23. 모든 consumer의 at-least-once idempotency

**무엇이 빠졌는가.** `final_project_cs/app/infrastructure/db/repository.py`의 action request idempotency와 `001_schema.sql`의 dedupe unique constraint, transition의 outbox dedupe는 있다. 그러나 모든 consumer가 같은 message를 두 번 받아도 한 번만 side effect를 적용한다는 공통 통합 테스트가 없다. producer dedupe만으로 consumer의 중복 적용을 보장할 수 없다.

**어디를 손대는가.** 공통 처리 계약은 `final_project_cs/app/infrastructure/messaging/`에 두고, consumer별 적용 경로와 `final_project_cs/app/infrastructure/db/repository.py`의 idempotent write를 정리한다. 필요하면 `final_project_cs/app/infrastructure/messaging/consumer.py`를 새로 둔다. 테스트는 `final_project_cs/tests/integration/messaging/test_consumer_idempotency.py`를 새로 둔다.

**선행 조건.** DoD 12의 worker가 동일 message를 다시 전달할 수 있어야 하며, DoD 17의 unique constraint가 먼저 고정되어야 한다.

**작업 규모.** 중간(1~2일). consumer 목록을 식별하고 각 side effect의 dedupe key와 transaction 경계를 맞춰야 한다.

**검증 방법.** `test_same_message_twice_applies_side_effect_once`, `test_duplicate_after_commit_returns_existing_result`, `test_different_tenants_do_not_share_dedupe_key`를 추가한다. 동일 message_id와 dedupe key를 두 번 전달하고 action·audit·outbox·report의 row 수와 결과가 한 번 처리와 같아야 한다.

### DoD 28. 포인트-쉐어링 경로와 방어 지표

**무엇이 빠졌는가.** `final_project_cs/app/core/verification.py`와 `final_project_cs/tests/unit/eval/test_defense_metrics.py`는 proposal 검증과 단위 방어 지표를 갖는다. 그러나 공개 1차 모델과 2차 모델의 동일 golden/holdout 비교, 실제 defense 실행 결과, metric report와 CI 기록이 없다. 기존 test는 attack fixture가 실제 방어를 거치는지까지는 검사하지만 모델 비교 경로는 아니다.

**어디를 손대는가.** 기존 `final_project_cs/eval/runners/baseline_a.py`, `baseline_b.py`, `proposed.py`와 `final_project_cs/eval/defense_metrics.py`를 DoD 15 harness 결과에 연결한다. 비교·report 함수는 `final_project_cs/eval/defense_report.py`를 새로 두고, fixture 검증은 `final_project_cs/tests/unit/eval/test_defense_metrics.py`를 보강한다.

**선행 조건.** DoD 15의 동일 dataset·checksum과 공통 metric·report schema가 먼저다. DoD 16이 같은 schema로 통계 report를 생성한 뒤 착수한다.

**작업 규모.** 중간(1~2일). 방어 로직은 있으나 두 모델의 같은 입력·같은 분모·같은 지표를 연결하고 과잉 차단도 함께 보고해야 한다.

**검증 방법.** `test_baseline_and_proposed_use_same_holdout`, `test_defense_report_contains_proper_and_over_abstention`, `test_attack_and_legitimate_denominators_are_nonzero`, `test_metric_is_independent_of_fixture_prediction_field`를 둔다. report에는 모델명, dataset checksum, blocked·passed·parse failure 분모와 지표를 포함한다.

## 4. 판정 불가 항목

### DoD 1. 원본 v4 hash 불일치 여부

현재 저장소와 코드만으로는 원본 v4 문서의 실제 파일과 기준 hash를 확인할 수 없다. 계획서 §27의 검증 방법은 파일 hash 비교를 요구하지만, 갭 분석 시점에는 비교 대상 원본과 기준값이 없었다.

판정 가능하게 하려면 다음이 필요하다.

1. 공식 원본 v4 파일의 정확한 경로와 수정되지 않은 사본을 제공한다.
2. 기준 hash의 알고리즘과 값, 계산 시점 또는 freeze commit을 확정한다.
3. `Get-FileHash` 또는 동일 알고리즘으로 원본과 저장소 사본을 비교한다.
4. 파일 경로, 알고리즘, 두 hash, 비교 결과를 evidence에 기록한다.

검증 산출물은 `program/plan/`의 실행 계획을 수정하는 대신 프로젝트가 정한 evidence 위치에 남긴다. 원본과 기준 hash가 모두 확보되기 전에는 구현됨·미구현으로 재분류하지 않는다.

## 5. 규모 분포

작음 2개(DoD 10·22), 중간 5개(DoD 12·17·18·23·28), 큼 3개(DoD 4·15·16)다.

## 6. 완료 판정 기준

각 항목은 코드가 존재하는 것만으로 완료로 보지 않는다. 지정한 테스트가 실제 입력 fixture를 사용하고, 실패·중복·경계 조건을 확인하며, 필요한 경우 재현 가능한 report 또는 migration artifact를 남겨야 한다. 이 계획에서 제안한 테스트는 실행하지 않은 상태이며, 구현 단계에서 추가한 뒤 CI gate에 편입한다.
