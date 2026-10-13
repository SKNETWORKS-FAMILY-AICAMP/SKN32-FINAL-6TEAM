---
type: guide
title: SQL 파일 목록
description: 실행기의 입력 파일과 보류 파일을 자동 집계한다
status: draft
domain: neutral
domain_note: 코드·카탈로그 파일의 자동 집계이며 제품 도메인 사례를 판정하지 않는다
automation:
  command: python program/scripts/build_wiki_catalogs.py
  owner: process:wiki-catalogs
  manual_edit: false
---

# SQL 파일 목록

[실측: 작업 트리] 실행 대상 SQL **89개**, 역사 보존 SQL **4개**, 보류 폴더 SQL **1개**. 파일 수이며 DB 적용 수가 아닙니다.

근거: [실행기](../../app/infrastructure/db/migrate.py), [SQL 적용 안내](migrations.md). 생성 명령은 워크스페이스 루트에서 실행합니다.

## 실행 대상

| SQL 파일 |
|---|
| [001_schema.sql](../../app/infrastructure/db/migrations/001_schema.sql) |
| [003_outbox_tenant_scoped_dedupe.sql](../../app/infrastructure/db/migrations/003_outbox_tenant_scoped_dedupe.sql) |
| [004_agent_runs_active_uniqueness.sql](../../app/infrastructure/db/migrations/004_agent_runs_active_uniqueness.sql) |
| [005_outbox_resolution.sql](../../app/infrastructure/db/migrations/005_outbox_resolution.sql) |
| [009_stuck_case_sweep_index.sql](../../app/infrastructure/db/migrations/009_stuck_case_sweep_index.sql) |
| [010_domain_travel.sql](../../app/infrastructure/db/migrations/010_domain_travel.sql) |
| [011_place_catalog.sql](../../app/infrastructure/db/migrations/011_place_catalog.sql) |
| [012_watch_observations.sql](../../app/infrastructure/db/migrations/012_watch_observations.sql) |
| [013_places_source_identity.sql](../../app/infrastructure/db/migrations/013_places_source_identity.sql) |
| [014_itinerary.sql](../../app/infrastructure/db/migrations/014_itinerary.sql) |
| [016_trip_request_key.sql](../../app/infrastructure/db/migrations/016_trip_request_key.sql) |
| [017_supplier_tier.sql](../../app/infrastructure/db/migrations/017_supplier_tier.sql) |
| [019_delegation_and_execution_record.sql](../../app/infrastructure/db/migrations/019_delegation_and_execution_record.sql) |
| [020_local_embedding_column.sql](../../app/infrastructure/db/migrations/020_local_embedding_column.sql) |
| [021_delegation_audit_trail.sql](../../app/infrastructure/db/migrations/021_delegation_audit_trail.sql) |
| [022_knowledge_chunk_openai_embedding_nullable.sql](../../app/infrastructure/db/migrations/022_knowledge_chunk_openai_embedding_nullable.sql) |
| [023_cancellation_terms.sql](../../app/infrastructure/db/migrations/023_cancellation_terms.sql) |
| [024_pending_changes.sql](../../app/infrastructure/db/migrations/024_pending_changes.sql) |
| [025_web_user_keys.sql](../../app/infrastructure/db/migrations/025_web_user_keys.sql) |
| [026_place_open_checks.sql](../../app/infrastructure/db/migrations/026_place_open_checks.sql) |
| [027_external_call_budget.sql](../../app/infrastructure/db/migrations/027_external_call_budget.sql) |
| [028_trip_intakes.sql](../../app/infrastructure/db/migrations/028_trip_intakes.sql) |
| [029_trip_scoped_places.sql](../../app/infrastructure/db/migrations/029_trip_scoped_places.sql) |
| [030_place_aliases.sql](../../app/infrastructure/db/migrations/030_place_aliases.sql) |
| [031_web_guard.sql](../../app/infrastructure/db/migrations/031_web_guard.sql) |
| [032_pending_consent.sql](../../app/infrastructure/db/migrations/032_pending_consent.sql) |
| [033_pending_relaxed.sql](../../app/infrastructure/db/migrations/033_pending_relaxed.sql) |
| [034_trip_chat_turns.sql](../../app/infrastructure/db/migrations/034_trip_chat_turns.sql) |
| [035_pending_other_options.sql](../../app/infrastructure/db/migrations/035_pending_other_options.sql) |
| [036_catalog_hours.sql](../../app/infrastructure/db/migrations/036_catalog_hours.sql) |
| [037_outbox_notice_prefix_idx.sql](../../app/infrastructure/db/migrations/037_outbox_notice_prefix_idx.sql) |
| [038_place_aliases_per_customer.sql](../../app/infrastructure/db/migrations/038_place_aliases_per_customer.sql) |
| [039_customer_profiles.sql](../../app/infrastructure/db/migrations/039_customer_profiles.sql) |
| [040_intake_reviews.sql](../../app/infrastructure/db/migrations/040_intake_reviews.sql) |
| [041_job_gates.sql](../../app/infrastructure/db/migrations/041_job_gates.sql) |
| [042_source_response_cache.sql](../../app/infrastructure/db/migrations/042_source_response_cache.sql) |
| [043_web_social_auth.sql](../../app/infrastructure/db/migrations/043_web_social_auth.sql) |
| [044_web_sessions.sql](../../app/infrastructure/db/migrations/044_web_sessions.sql) |
| [045_web_agent_keys.sql](../../app/infrastructure/db/migrations/045_web_agent_keys.sql) |
| [046_consents.sql](../../app/infrastructure/db/migrations/046_consents.sql) |
| [047_call_budget_outcomes.sql](../../app/infrastructure/db/migrations/047_call_budget_outcomes.sql) |
| [048_telegram_connect.sql](../../app/infrastructure/db/migrations/048_telegram_connect.sql) |
| [049_call_budget_provider_exhausted.sql](../../app/infrastructure/db/migrations/049_call_budget_provider_exhausted.sql) |
| [050_trip_guardian_changes.sql](../../app/infrastructure/db/migrations/050_trip_guardian_changes.sql) |
| [051_intake_survey_answers.sql](../../app/infrastructure/db/migrations/051_intake_survey_answers.sql) |
| [052_safety_pause_and_shelters.sql](../../app/infrastructure/db/migrations/052_safety_pause_and_shelters.sql) |
| [053_intake_survey_answer_history.sql](../../app/infrastructure/db/migrations/053_intake_survey_answer_history.sql) |
| [054_user_activity_events.sql](../../app/infrastructure/db/migrations/054_user_activity_events.sql) |
| [055_intake_transcription_differs.sql](../../app/infrastructure/db/migrations/055_intake_transcription_differs.sql) |
| [056_legal_retention.sql](../../app/infrastructure/db/migrations/056_legal_retention.sql) |
| [057_candidate_reasons.sql](../../app/infrastructure/db/migrations/057_candidate_reasons.sql) |
| [058_place_embeddings.sql](../../app/infrastructure/db/migrations/058_place_embeddings.sql) |
| [059_forecast_advisory_proposals.sql](../../app/infrastructure/db/migrations/059_forecast_advisory_proposals.sql) |
| [060_web_auth_guest_transfer.sql](../../app/infrastructure/db/migrations/060_web_auth_guest_transfer.sql) |
| [200_dining_schema.sql](../../app/infrastructure/db/migrations/200_dining_schema.sql) |
| [201_dining_core_link.sql](../../app/infrastructure/db/migrations/201_dining_core_link.sql) |
| [202_dining_matcher.sql](../../app/infrastructure/db/migrations/202_dining_matcher.sql) |
| [203_dining_holiday.sql](../../app/infrastructure/db/migrations/203_dining_holiday.sql) |
| [204_dining_links.sql](../../app/infrastructure/db/migrations/204_dining_links.sql) |
| [205_dining_attribute.sql](../../app/infrastructure/db/migrations/205_dining_attribute.sql) |
| [206_dining_live_check.sql](../../app/infrastructure/db/migrations/206_dining_live_check.sql) |
| [207_dining_alternatives.sql](../../app/infrastructure/db/migrations/207_dining_alternatives.sql) |
| [208_dining_quality.sql](../../app/infrastructure/db/migrations/208_dining_quality.sql) |
| [209_dining_notes.sql](../../app/infrastructure/db/migrations/209_dining_notes.sql) |
| [210_dining_closure_coverage.sql](../../app/infrastructure/db/migrations/210_dining_closure_coverage.sql) |
| [211_dining_trial_lane.sql](../../app/infrastructure/db/migrations/211_dining_trial_lane.sql) |
| [212_dining_notice.sql](../../app/infrastructure/db/migrations/212_dining_notice.sql) |
| [213_dining_area_district.sql](../../app/infrastructure/db/migrations/213_dining_area_district.sql) |
| [214_dining_category.sql](../../app/infrastructure/db/migrations/214_dining_category.sql) |
| [215_dining_external_ref.sql](../../app/infrastructure/db/migrations/215_dining_external_ref.sql) |
| [216_dining_google_place_id.sql](../../app/infrastructure/db/migrations/216_dining_google_place_id.sql) |
| [217_dining_halal_source.sql](../../app/infrastructure/db/migrations/217_dining_halal_source.sql) |
| [218_dining_michelin.sql](../../app/infrastructure/db/migrations/218_dining_michelin.sql) |
| [219_dining_alternatives_diet.sql](../../app/infrastructure/db/migrations/219_dining_alternatives_diet.sql) |
| [220_dining_notice_scope.sql](../../app/infrastructure/db/migrations/220_dining_notice_scope.sql) |
| [221_dining_core_promote.sql](../../app/infrastructure/db/migrations/221_dining_core_promote.sql) |
| [222_dining_core_sync.sql](../../app/infrastructure/db/migrations/222_dining_core_sync.sql) |
| [222_dining_vworld.sql](../../app/infrastructure/db/migrations/222_dining_vworld.sql) |
| [223_ops_loader_role.sql](../../app/infrastructure/db/migrations/223_ops_loader_role.sql) |
| [224_dining_runtime_link.sql](../../app/infrastructure/db/migrations/224_dining_runtime_link.sql) |
| [225_dining_license_search.sql](../../app/infrastructure/db/migrations/225_dining_license_search.sql) |
| [226_admin_operations.sql](../../app/infrastructure/db/migrations/226_admin_operations.sql) |
| [226_dining_nopo.sql](../../app/infrastructure/db/migrations/226_dining_nopo.sql) |
| [227_watch_simulation_proposal_scope.sql](../../app/infrastructure/db/migrations/227_watch_simulation_proposal_scope.sql) |
| [228_watch_run_history.sql](../../app/infrastructure/db/migrations/228_watch_run_history.sql) |
| [229_service_improvement.sql](../../app/infrastructure/db/migrations/229_service_improvement.sql) |
| [230_intake_test_scenarios.sql](../../app/infrastructure/db/migrations/230_intake_test_scenarios.sql) |
| [901_personal_ai_oauth.sql](../../app/infrastructure/db/migrations/901_personal_ai_oauth.sql) |
| [902_unattended_operations.sql](../../app/infrastructure/db/migrations/902_unattended_operations.sql) |

## 역사 보존 — 실행 제외

- [002_domain_commerce.sql](../../app/infrastructure/db/migrations/002_domain_commerce.sql)
- [006_products_catalog.sql](../../app/infrastructure/db/migrations/006_products_catalog.sql)
- [007_returns_order_item.sql](../../app/infrastructure/db/migrations/007_returns_order_item.sql)
- [008_products_return_restriction.sql](../../app/infrastructure/db/migrations/008_products_return_restriction.sql)

## 보류 폴더

- [015_drop_commerce_domain.sql](../../app/infrastructure/db/migrations/pending/015_drop_commerce_domain.sql)

## 관계

- [여행 데이터 안내](index.md) — 데이터 문서 입구
