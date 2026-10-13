---
type: guide
title: 여행 데이터 스키마 안내
description: 현재 여행 SQL의 역할을 분류한다. 운영 DB 적용 상태는 별도 확인한다
status: draft
tags: [data, contract]
domain: travel
---

# 여행 데이터 스키마 안내

## 실제 DB 조회 결과

[실측 2026-10-12] 이커머스 표 5개는 백업·복원 검증 후 두 환경에서 삭제했습니다. 로컬 개발 DB 91표·13뷰, x600 서버의 cs 프로젝트 DB 87표·13뷰이며 정확한 옛 표 이름 잔존은 각각 0개입니다. 삭제 대상 밖의 표·열·제약·인덱스·트리거 구조는 전후 동일합니다.

[현재 환경별 현황·관계도·전체 구조 검색](../../../../program/research/sql_retirement_2026-10-12/index.html)에서 조회 시각·범위·원본 JSON·검증 한계를 확인합니다. 여행 6표의 행 수·내용 해시는 두 환경에서 유지됐습니다. 로컬 고객·고객 사건 표는 관측 사이 증가하여 전체 데이터 불변으로 주장하지 않습니다. [2026-10-11 조회본](../../../../program/research/sql_review_2026-10-11/index.html)은 삭제 전 기록입니다.

이 문서는 현재 SQL 파일의 설계 안내입니다. 실행 중인 DB의 전체 테이블 목록이나 적용 완료 선언이 아닙니다.

| 데이터 역할 | 대표 테이블 | SQL 근거 |
|---|---|---|
| 공통 업무 상태·이력 | `customer_cases`, `case_events`, `agent_runs`, `team_tasks` | [001](../../../app/infrastructure/db/migrations/001_schema.sql) |
| 실행 요청·승인·알림 대기 | `action_requests`, `action_approvals`, `outbox` | [001](../../../app/infrastructure/db/migrations/001_schema.sql), [003](../../../app/infrastructure/db/migrations/003_outbox_tenant_scoped_dedupe.sql) |
| 장소·예약 | `places`, `bookings`, `supplier_bookings`, `cancellation_terms` | [010](../../../app/infrastructure/db/migrations/010_domain_travel.sql), [023](../../../app/infrastructure/db/migrations/023_cancellation_terms.sql) |
| 장소 목록·출처·별칭 | `place_catalog`, `source_sync_state`, `place_aliases` | [011](../../../app/infrastructure/db/migrations/011_place_catalog.sql), [030](../../../app/infrastructure/db/migrations/030_place_aliases.sql) |
| 여행·일정 판본·항목 | `trips`, `itinerary_versions`, `itinerary_items` | [014](../../../app/infrastructure/db/migrations/014_itinerary.sql) |
| 감시 관측·변경 | `watch_observations`, `watch_changes`, `trip_guardian_changes` | [012](../../../app/infrastructure/db/migrations/012_watch_observations.sql), [050](../../../app/infrastructure/db/migrations/050_trip_guardian_changes.sql) |
| 접수·확인·대화 | `trip_intakes`, `intake_sources`, `intake_claims`, `intake_reviews`, `trip_chat_turns` | [028](../../../app/infrastructure/db/migrations/028_trip_intakes.sql), [040](../../../app/infrastructure/db/migrations/040_intake_reviews.sql), [034](../../../app/infrastructure/db/migrations/034_trip_chat_turns.sql) |
| 웹 인증·개인 AI 키 | `web_social_links`, `web_sessions`, `web_agent_keys`, `consent_events` | [043](../../../app/infrastructure/db/migrations/043_web_social_auth.sql), [044](../../../app/infrastructure/db/migrations/044_web_sessions.sql), [045](../../../app/infrastructure/db/migrations/045_web_agent_keys.sql), [046](../../../app/infrastructure/db/migrations/046_consents.sql) |
| 조회 예산·공유 캐시·회차 제어 | `external_call_budget`, `job_gates`, `source_response_cache` | [027](../../../app/infrastructure/db/migrations/027_external_call_budget.sql), [041](../../../app/infrastructure/db/migrations/041_job_gates.sql), [042](../../../app/infrastructure/db/migrations/042_source_response_cache.sql) |
| 요식 장소·영업시간·휴무·근거 | `dining.dn_place`, `dining.dn_hours_rule`, `dining.dn_closure_rule`, `dining.dn_source_record` | [200](../../../app/infrastructure/db/migrations/200_dining_schema.sql), 이후 201~225 변경 |
| 보관기간·감시 실행·개선 작업 기록 | `legal_retention`, `travel_watch_runs`, `travel_watch_checks`, `service_improvement_batches` | [056](../../../app/infrastructure/db/migrations/056_legal_retention.sql), [228](../../../app/infrastructure/db/migrations/228_watch_run_history.sql), [229](../../../app/infrastructure/db/migrations/229_service_improvement.sql) |

위 표는 역할별 대표 목록입니다. 열·외래키·인덱스·이후 변경의 정확한 정의는 [전체 SQL 목록](../migrations.md)을 확인합니다. 파일의 CREATE TABLE 문 개수를 실행 중인 DB 테이블 수로 보고하지 않습니다.

## 공통 제약

- 사건 순서: `case_events UNIQUE(case_id, aggregate_version)`.
- 실행 중복 방지: `action_requests UNIQUE(tenant_id, idempotency_key)`.
- 알림 중복 방지: `outbox UNIQUE(tenant_id, topic, dedupe_key)`.
- 고객 데이터 접근은 [테넌트 격리](../tenancy.md) 계약을 함께 지킵니다.

## 쇼핑몰 표와 현재 제품을 구분하기

초기 SQL에는 쇼핑몰 표를 만드는 정의가 남아 있습니다. 파일 존재는 현재 여행 제품에서 사용한다는 뜻이 아닙니다. [D-023](../../../../wiki/decisions/D-023-no-commerce-assets-in-use.md)은 쇼핑몰 자산의 현재 제품 사용을 금지하며, 2026-10-06 로컬 개발 DB에서 5개 쇼핑몰 표를 제거한 기록을 갖고 있습니다. 이를 모든 환경의 현재 상태로 확대하지 않습니다. 현재 runner는 역사 SQL 4개를 명시적으로 제외하며 새 임시 DB 시험에서 옛 5개 표의 미생성을 확인했습니다. 기존 업무 DB의 잔존 표 여부·삭제 여부와는 별개입니다. 초기 SQL 실행 범위는 [SQL 적용 안내](../migrations.md)에서 확인합니다.

## 이전 문서

2026-10-11 정정 전 본문은 [보존본](_backup/2026-10-11_193844_current-facts/index.md)에 있습니다. 이전 측정·실험 결과를 현재 제품의 완료 증거로 사용하지 않습니다.

## 관계

- [문서 작성 표준](../../../../wiki/governance/document-standard.md) — 정본·근거·이력 분리 규칙
