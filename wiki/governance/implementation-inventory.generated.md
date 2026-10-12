---
type: guide
title: 현재 결정·계약 상태 적용 목록
description: 현재 결정·계약과 개정 대상의 미적용 필드를 자동 열거한다
status: draft
domain: neutral
impl_scope: cs — 현재 제품과 허브 결정·계약의 적용 목록이며 sample 참고 구현의 실행 상태를 추정하지 않는다
domain_note: 코드·카탈로그 파일의 자동 집계이며 제품 도메인 사례를 판정하지 않는다
automation:
  command: python program/scripts/build_wiki_catalogs.py
  owner: process:wiki-catalogs
  manual_edit: false
---

# 현재 결정·계약 상태 적용 목록

[실측: 작업 트리] 현재 적용 대상 **94개**, 상태 필드 미적용 **89개**. 실행·배포 완료 수가 아닙니다.

범위: 허브·cs의 현재 `decision`·`contract` 전체와 W01~W25의 현재 wiki 대상. `deprecated`·생성물·기록·백업·이관 폴더·sample 참고 구현은 제외합니다. 사용자 선택을 결정 필드로 자동 복사하거나 상태를 승격하지 않습니다.

아래 값은 각 페이지 머리말을 그대로 읽은 것입니다. 필드가 없으면 `unverified`입니다. 환경별 본문 표·실행 근거는 페이지를 열어 확인해야 하며 이 생성기는 배포를 조사하지 않아 모두 `unverified`로 표시합니다.

| 현재 문서 | 문서 검토 | 결정 | 구현 | 검증 | 환경 배포 | 확인 시각 | 미적용 필드 |
|---|---|---|---|---|---|---|---|
| [final_project_cs/wiki/actions/action-proposal.md](../../final_project_cs/wiki/actions/action-proposal.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/actions/idempotency.md](../../final_project_cs/wiki/actions/idempotency.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/context/context-budget.md](../../final_project_cs/wiki/context/context-budget.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/data/index.md](../../final_project_cs/wiki/data/index.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/data/schema/fields.md](../../final_project_cs/wiki/data/schema/fields.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/data/schema/index.md](../../final_project_cs/wiki/data/schema/index.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/decisions/D-CS-001-composer-ui-removal.md](../../final_project_cs/wiki/decisions/D-CS-001-composer-ui-removal.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [final_project_cs/wiki/decisions/D-CS-002-finetuned-model-not-adopted.md](../../final_project_cs/wiki/decisions/D-CS-002-finetuned-model-not-adopted.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [final_project_cs/wiki/decisions/D-CS-003-composer-scope.md](../../final_project_cs/wiki/decisions/D-CS-003-composer-scope.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [final_project_cs/wiki/decisions/D-CS-004-composer-boundary.md](../../final_project_cs/wiki/decisions/D-CS-004-composer-boundary.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/decisions/D-CS-005-odsay-not-used.md](../../final_project_cs/wiki/decisions/D-CS-005-odsay-not-used.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [final_project_cs/wiki/decisions/D-CS-006-cancellation-terms-are-structured.md](../../final_project_cs/wiki/decisions/D-CS-006-cancellation-terms-are-structured.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [final_project_cs/wiki/decisions/D-CS-007-ui-operator-login.md](../../final_project_cs/wiki/decisions/D-CS-007-ui-operator-login.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [final_project_cs/wiki/decisions/D-CS-008-ops-console-separate-app.md](../../final_project_cs/wiki/decisions/D-CS-008-ops-console-separate-app.md) | draft | accepted | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/decisions/D-CS-009-daytime-closure-detection.md](../../final_project_cs/wiki/decisions/D-CS-009-daytime-closure-detection.md) | draft | accepted | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/decisions/D-CS-010-google-calls-in-dawn-batch-only.md](../../final_project_cs/wiki/decisions/D-CS-010-google-calls-in-dawn-batch-only.md) | draft | accepted | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/decisions/D-CS-011-browser-session-cookie.md](../../final_project_cs/wiki/decisions/D-CS-011-browser-session-cookie.md) | draft | accepted | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/decisions/D-CS-012-agent-auth-claude-style.md](../../final_project_cs/wiki/decisions/D-CS-012-agent-auth-claude-style.md) | draft | accepted | implemented | partial | unverified | unverified | — |
| [final_project_cs/wiki/decisions/D-CS-013-domain-folder-layout.md](../../final_project_cs/wiki/decisions/D-CS-013-domain-folder-layout.md) | draft | accepted | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/decisions/D-CS-014-routing-reroute.md](../../final_project_cs/wiki/decisions/D-CS-014-routing-reroute.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [final_project_cs/wiki/external/a2a-protocol.md](../../final_project_cs/wiki/external/a2a-protocol.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/admin-screen-api.md](../../final_project_cs/wiki/external/admin-screen-api.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/api-environment-limits.md](../../final_project_cs/wiki/external/api-environment-limits.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/api-key-issue-guide.md](../../final_project_cs/wiki/external/api-key-issue-guide.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/introspection.md](../../final_project_cs/wiki/external/introspection.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/llm-failover.md](../../final_project_cs/wiki/external/llm-failover.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/mcp-tools.md](../../final_project_cs/wiki/external/mcp-tools.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/personal-ai-oauth.md](../../final_project_cs/wiki/external/personal-ai-oauth.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/rest-api.md](../../final_project_cs/wiki/external/rest-api.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/rest-endpoints.md](../../final_project_cs/wiki/external/rest-endpoints.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/rest-endpoints/cases.md](../../final_project_cs/wiki/external/rest-endpoints/cases.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/rest-endpoints/delegations.md](../../final_project_cs/wiki/external/rest-endpoints/delegations.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/rest-endpoints/trips.md](../../final_project_cs/wiki/external/rest-endpoints/trips.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/rest-endpoints/web-access.md](../../final_project_cs/wiki/external/rest-endpoints/web-access.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/rest-endpoints/web-auth.md](../../final_project_cs/wiki/external/rest-endpoints/web-auth.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/rest-endpoints/web-intakes.md](../../final_project_cs/wiki/external/rest-endpoints/web-intakes.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/rest-endpoints/web-trips.md](../../final_project_cs/wiki/external/rest-endpoints/web-trips.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/service-chat-help.md](../../final_project_cs/wiki/external/service-chat-help.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/taxi-pricing-web-v1.md](../../final_project_cs/wiki/external/taxi-pricing-web-v1.md) | draft | accepted | partial | partial | unverified | unverified | — |
| [final_project_cs/wiki/external/test-scenarios.md](../../final_project_cs/wiki/external/test-scenarios.md) | draft | unverified | partial | unverified | unverified | unverified | validation_status |
| [final_project_cs/wiki/external/travel-density.md](../../final_project_cs/wiki/external/travel-density.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/trip-chat-context.md](../../final_project_cs/wiki/external/trip-chat-context.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/watch-monitoring.md](../../final_project_cs/wiki/external/watch-monitoring.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/watch-simulation.md](../../final_project_cs/wiki/external/watch-simulation.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/web-auth-transfer.md](../../final_project_cs/wiki/external/web-auth-transfer.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/web-flow-2026-10-09.md](../../final_project_cs/wiki/external/web-flow-2026-10-09.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/external/web-intake-restore.md](../../final_project_cs/wiki/external/web-intake-restore.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/log.md](../../final_project_cs/wiki/log.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/operations/always-on.md](../../final_project_cs/wiki/operations/always-on.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/operations/unattended-operations.md](../../final_project_cs/wiki/operations/unattended-operations.md) | draft | accepted | partial | partial | unverified | 2026-10-12T04:56:57+09:00 | — |
| [final_project_cs/wiki/quality/guardrails.md](../../final_project_cs/wiki/quality/guardrails.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/quality/invariants.md](../../final_project_cs/wiki/quality/invariants.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/quality/slm-model-evaluation.md](../../final_project_cs/wiki/quality/slm-model-evaluation.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/runtime/case-lifecycle.md](../../final_project_cs/wiki/runtime/case-lifecycle.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/teams/classification-execution-plan.md](../../final_project_cs/wiki/teams/classification-execution-plan.md) | draft | accepted | implemented | verified | unverified | 2026-10-12T04:43:59.881485+09:00 | — |
| [final_project_cs/wiki/teams/code-layout.md](../../final_project_cs/wiki/teams/code-layout.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/teams/composition.md](../../final_project_cs/wiki/teams/composition.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/teams/dining-agent-design.md](../../final_project_cs/wiki/teams/dining-agent-design.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/teams/team-boundary.md](../../final_project_cs/wiki/teams/team-boundary.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/teams/team-contract/fields.md](../../final_project_cs/wiki/teams/team-contract/fields.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [final_project_cs/wiki/teams/team-contract/plugin-availability.md](../../final_project_cs/wiki/teams/team-contract/plugin-availability.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [wiki/architecture/notifications.md](../architecture/notifications.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [wiki/architecture/system-context.md](../architecture/system-context.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [wiki/business/pricing-travel.md](../business/pricing-travel.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [wiki/decisions/D-002-graph-store-gate.md](../decisions/D-002-graph-store-gate.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [wiki/decisions/D-003-message-broker.md](../decisions/D-003-message-broker.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [wiki/decisions/D-004-self-hosting-rationale.md](../decisions/D-004-self-hosting-rationale.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [wiki/decisions/D-005-write-gate.md](../decisions/D-005-write-gate.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [wiki/decisions/D-006-composer-ownership.md](../decisions/D-006-composer-ownership.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [wiki/decisions/D-007-central-config-store.md](../decisions/D-007-central-config-store.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [wiki/decisions/D-009-recommendation-scope.md](../decisions/D-009-recommendation-scope.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [wiki/decisions/D-010-deferral-scoring.md](../decisions/D-010-deferral-scoring.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [wiki/decisions/D-011-composer-v3-gap.md](../decisions/D-011-composer-v3-gap.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [wiki/decisions/D-012-cutover-timing.md](../decisions/D-012-cutover-timing.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [wiki/decisions/D-013-declarative-team.md](../decisions/D-013-declarative-team.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [wiki/decisions/D-015-implementation-catalog.md](../decisions/D-015-implementation-catalog.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [wiki/decisions/D-016-scope-narrowing-reasons.md](../decisions/D-016-scope-narrowing-reasons.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [wiki/decisions/D-017-watch-cadence-golden-time.md](../decisions/D-017-watch-cadence-golden-time.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [wiki/decisions/D-018-decision15-stop-paths.md](../decisions/D-018-decision15-stop-paths.md) | draft | accepted | unverified | unverified | unverified | unverified | — |
| [wiki/decisions/D-019-travel-density.md](../decisions/D-019-travel-density.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [wiki/decisions/D-020-trip-survey-and-ask-first.md](../decisions/D-020-trip-survey-and-ask-first.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [wiki/decisions/D-021-email-verified-key-recovery.md](../decisions/D-021-email-verified-key-recovery.md) | draft | unverified | unverified | unverified | unverified | unverified | decision_status, implementation_status, validation_status |
| [wiki/decisions/D-022-study-only-kto-images.md](../decisions/D-022-study-only-kto-images.md) | draft | accepted | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [wiki/decisions/D-023-no-commerce-assets-in-use.md](../decisions/D-023-no-commerce-assets-in-use.md) | draft | accepted | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [wiki/delivery/dod.md](../delivery/dod.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [wiki/delivery/release-gate.md](../delivery/release-gate.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [wiki/delivery/roles.md](../delivery/roles.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [wiki/delivery/timeline.md](../delivery/timeline.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [wiki/evaluation/finetuning.md](../evaluation/finetuning.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [wiki/evaluation/index.md](../evaluation/index.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [wiki/governance/document-standard.md](document-standard.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [wiki/index.md](../index.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [wiki/product/positioning.md](../product/positioning.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |
| [wiki/product/scope.md](../product/scope.md) | draft | unverified | unverified | unverified | unverified | unverified | implementation_status, validation_status |

## 읽는 법·후속 적용

미적용 필드는 검사 위반과 다릅니다. 기존 초안의 선택 필드를 일괄 필수로 바꾸지 않습니다. 문서 담당자는 기능 구현 결과를 받으면 해당 변경의 범위·실행 시각·증거를 본문 환경별 표에 연결하고 필드를 채웁니다. 병렬 작업 중인 기능 문서는 담당자가 적용합니다.

`implemented-local`·`implemented-partial`은 기존 표기이며 새 표준 값으로 채택하지 않습니다. 개별 담당자의 범위 확인이 필요합니다. `draft`는 채택 취소, `accepted`는 구현 완료를 뜻하지 않습니다.

## 관계

- [상태 표시 안내](implementation-state.md) — 필드 의미와 환경별 근거
- [리뷰 정책](review-policy.md) — 문서 검토와 승격 조건
