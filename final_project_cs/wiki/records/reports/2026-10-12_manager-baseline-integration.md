---
type: report
title: 매니저 기준 인증·SQL 안전 변경 통합
description: 독립 검증 가능한 범위와 선행 변경을 기다리는 범위를 분리한 검수 기록
status: partial
domain: travel
---

# 매니저 기준 인증·SQL 안전 변경 통합 — 2026-10-12

기존 매니저 이력과 웹 CI 보완을 보존하면서 개인 AI OAuth와 SQL·배포 안전 변경만 결합했습니다. 전체 wiki 개편·v12 확정·운영 배포 완료 보고가 아닙니다.

| 확인 항목 | 결과 | 분모 |
|---|---|---|
| 최종 백엔드 CI 범위·인증·SQL DB 회귀 | 실패 0, 통과 3378, 건너뜀 81 | 3459; 실호출 등 선택 제외 220 별도 |
| 필수 DoD 호환 관문 | 26/26 통과 | 기존 관문 26항목; 새 wiki 인수 전체를 대신하지 않음 |
| ruff | 통과 | 저장소 전체 |
| 팀 저장소 보안 검사 | 문제 0파일 | 추적·후보 텍스트 4359파일 |
| 개인 저장소 보안 검사 | 문제 0파일 | 추적·후보 텍스트 7237파일 |

## 반영한 동작

- 개인 AI는 사전 등록한 클라이언트의 로그인·동의·PKCE·자원·권한을 검사하고 본인 여행만 조회합니다. 코드·갱신 토큰 교환은 한 번만 성공하며 폐기·재사용을 검사합니다. 기존 키 접근과 MCP 쓰기 기본 꺼짐을 유지합니다.
- SQL은 전체 사전검사 후 단일 트랜잭션으로 적용합니다. 실패 시 앞선 DDL·행 변경을 함께 취소하며 중첩 호출은 savepoint를 사용합니다. 과거 커머스 SQL 원문은 남기고 현재 재실행에서 제외합니다. 기존 업무 표를 삭제하는 SQL은 추가하지 않았습니다.
- 배포 전 이미지 자체와 마운트 뒤 SQL 안전 계약을 확인합니다. 제한 시간·부분 실패 때 저장한 실제 이전 이미지 ID로 복구하고 건강 상태를 확인하는 절차를 제공합니다. 실제 Docker 배포·복구를 실행한 결과는 아닙니다.
- 데이터 전체 제외 규칙을 유지하며 양쪽 저장소의 기존 추적 데이터 57파일은 수정·추적 해제·삭제하지 않았습니다.

## 이번에 제외한 변경

최초 공유 후보에는 서로 다른 선행 구현이 섞여 있었습니다. 분류 실행 계획의 조립부는 아직 매니저에 없는 플러그인·가용성 계약에 의존했고 그대로 결합하면 앱 import가 실패했습니다. 운영 정책 화면도 실제 조회 호출부 접합과 함께 검증해야 합니다. 해당 기능의 공유 원본은 변경하지 않고 이번 커밋에서 제외했습니다.

전체 wiki 개편·시험 묶음 분리·자동 목록·v12 및 베이스라인 검토본은 현재 매니저와 코드·링크·검사 범위가 일치하지 않아 제외했습니다. 공유 개발 트리의 검증 결과를 이 매니저 후보의 결과로 바꾸어 주장하지 않습니다. 진행 중인 경보 방향·검색 벡터·택시 요금·요식업 및 이동 자료 변경도 포함하지 않았습니다.

인증 DB 시험은 새 전용 PostgreSQL에서 실행했고 해당 클러스터를 종료했습니다. 외부 통신 차단 발생과 시험 중 소스 변경은 모두 0건입니다. 실제 외부 개인 AI 등록·HTTPS 연결·운영 계정 흐름·유료 제공처 호출·운영 배포·재시작은 검증하지 않았습니다. mock 서버 화면 시험은 이번 추가 범위에 없으며 기존 웹 화면 변경도 추가하지 않았습니다.

## 포함 파일

아래는 두 매니저에 동일하게 적용할 검수 파일입니다. 커밋 후 변경 파일 목록과 대조합니다.

- [.gitignore](../../../../.gitignore)
- [final_project_cs/app/domains/travel_ops/modules/mcp/mcp_server.py](../../../../final_project_cs/app/domains/travel_ops/modules/mcp/mcp_server.py)
- [final_project_cs/app/domains/travel_ops/modules/web_account/personal_ai_api.py](../../../../final_project_cs/app/domains/travel_ops/modules/web_account/personal_ai_api.py)
- [final_project_cs/app/domains/travel_ops/modules/web_account/personal_ai_context.py](../../../../final_project_cs/app/domains/travel_ops/modules/web_account/personal_ai_context.py)
- [final_project_cs/app/domains/travel_ops/modules/web_account/personal_ai_oauth.py](../../../../final_project_cs/app/domains/travel_ops/modules/web_account/personal_ai_oauth.py)
- [final_project_cs/app/domains/travel_ops/modules/web_account/personal_ai_store.py](../../../../final_project_cs/app/domains/travel_ops/modules/web_account/personal_ai_store.py)
- [final_project_cs/app/domains/travel_ops/modules/web_account/personal_ai_views.py](../../../../final_project_cs/app/domains/travel_ops/modules/web_account/personal_ai_views.py)
- [final_project_cs/app/domains/travel_ops/modules/web_account/web_auth_api.py](../../../../final_project_cs/app/domains/travel_ops/modules/web_account/web_auth_api.py)
- [final_project_cs/app/domains/travel_ops/modules/web_account/web_cookie.py](../../../../final_project_cs/app/domains/travel_ops/modules/web_account/web_cookie.py)
- [final_project_cs/app/infrastructure/db/migrate.py](../../../../final_project_cs/app/infrastructure/db/migrate.py)
- [final_project_cs/app/infrastructure/db/migration_plan.py](../../../../final_project_cs/app/infrastructure/db/migration_plan.py)
- [final_project_cs/app/infrastructure/db/migration_sql.py](../../../../final_project_cs/app/infrastructure/db/migration_sql.py)
- [final_project_cs/app/infrastructure/db/migrations/901_personal_ai_oauth.sql](../../../../final_project_cs/app/infrastructure/db/migrations/901_personal_ai_oauth.sql)
- [final_project_cs/app/infrastructure/db/migrations/migration-plan.json](../../../../final_project_cs/app/infrastructure/db/migrations/migration-plan.json)
- [final_project_cs/config/personal-ai-oauth.json](../../../../final_project_cs/config/personal-ai-oauth.json)
- [final_project_cs/deploy/.gitignore](../../../../final_project_cs/deploy/.gitignore)
- [final_project_cs/deploy/Dockerfile.api](../../../../final_project_cs/deploy/Dockerfile.api)
- [final_project_cs/deploy/Dockerfile.migration-safety](../../../../final_project_cs/deploy/Dockerfile.migration-safety)
- [final_project_cs/deploy/auto_deploy.sh](../../../../final_project_cs/deploy/auto_deploy.sh)
- [final_project_cs/deploy/migration_safe_deploy.py](../../../../final_project_cs/deploy/migration_safe_deploy.py)
- [final_project_cs/deploy/server_up.sh](../../../../final_project_cs/deploy/server_up.sh)
- [final_project_cs/requirements.txt](../../../../final_project_cs/requirements.txt)
- [final_project_cs/tests/e2e/test_personal_ai_oauth_db.py](../../../../final_project_cs/tests/e2e/test_personal_ai_oauth_db.py)
- [final_project_cs/tests/integration/db/test_migrations_rerun.py](../../../../final_project_cs/tests/integration/db/test_migrations_rerun.py)
- [final_project_cs/tests/security/test_personal_ai_oauth.py](../../../../final_project_cs/tests/security/test_personal_ai_oauth.py)
- [final_project_cs/tests/unit/core/test_current_migration_plan.py](../../../../final_project_cs/tests/unit/core/test_current_migration_plan.py)
- [final_project_cs/tests/unit/core/test_migration_atomic_sql.py](../../../../final_project_cs/tests/unit/core/test_migration_atomic_sql.py)
- [final_project_cs/tests/unit/core/test_migration_safe_deploy.py](../../../../final_project_cs/tests/unit/core/test_migration_safe_deploy.py)
- [final_project_cs/wiki/external/personal-ai-oauth.md](../../../../final_project_cs/wiki/external/personal-ai-oauth.md)
- [final_project_cs/wiki/records/reports/2026-10-12_migration-transaction-and-deploy-safety.md](../../../../final_project_cs/wiki/records/reports/2026-10-12_migration-transaction-and-deploy-safety.md)
- [program/research/baseline_completion_2026-10-12/tasks/auth/integration-request.md](../../../../program/research/baseline_completion_2026-10-12/tasks/auth/integration-request.md)
- [program/research/baseline_completion_2026-10-12/tasks/auth/report.md](../../../../program/research/baseline_completion_2026-10-12/tasks/auth/report.md)

이번 보고서와 cs wiki 변경 기록의 한 줄 링크도 함께 추가합니다. 원문 로그·JUnit·전체 grep 출력·검수 사본·백업은 비공개 작업 폴더에 보관하며 커밋하지 않습니다.
