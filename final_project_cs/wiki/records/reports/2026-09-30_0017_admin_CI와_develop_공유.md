---
type: report
title: 운영 앱 CI와 develop 공유
description: 운영 콘솔·단일 HTML 자동 검증 추가와 develop PR의 검증 범위
status: draft
domain: travel
---

# 운영 앱 CI와 develop 공유

2026-09-30 · Codex · `role-eval-ui` · TeamFlow `ST4F-176`.

사용자 승인에 따라 운영 앱을 develop에 공유하기 위한 CI와 [PR #17](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/pull/17)을 준비했다. 앱 구현 커밋은 `1317a74`, CI 추가 커밋은 `3aa0075`, 비교 기준 develop은 `38cd59d`다. 이 기록은 PR 병합 전 검증 결과이며, 실제 병합 여부·최종 커밋은 PR의 상태와 이력에서 확인한다.

## 변경

- [ci-admin.yml](../../../../.github/workflows/ci-admin.yml): admin/workflow 변경을 포함하는 develop·main 대상 PR과 push에서 실행한다. Ubuntu·Node 22·Chromium으로 기존 검증 명령을 자동화했다.
- [ci-develop.yml](../../../../.github/workflows/ci-develop.yml): `RULE.md` §5의 보안 시험을 기존 임시 DB에서 별도 단계로 실행하도록 추가했다. 아래 최초 실행 이후 추가한 검사이므로 최종 PR 체크에서 결과를 확인한다.
- [admin README](../../../frontend/apps/admin/README.md)·[개발 기준](../../../frontend/apps/admin/DEVELOPMENT.md): CI 실행 범위와 HTML 갱신 의무를 안내한다.
- 이 리포트와 [검증 증거](../evidence/2026-09-30_0017_admin_CI와_develop_공유.md), 허브 로그: 실행 조건·결과와 공유 경로를 연결한다.

CI는 demo 설정으로 lint·typecheck·단위시험·빌드를 수행하고, HTML 재생성 후 저장된 파일과 다르면 실패한다. 이어 앱·오프라인 HTML E2E와 별도 빌드의 미설정 모드를 검사한다. 읽기 권한만 사용하며 실패한 브라우저 증거는 7일 보관한다. 실제 백엔드·인증정보는 사용하지 않는다.

## 검증 결과

`3aa0075` PR에서 [CI (admin)](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/36588740572)과 [CI (develop)](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/36588740375)이 모두 성공했다.

| 검사 | 결과 |
|---|---|
| admin 단위시험 | 23/23(100%) 통과 |
| 앱·오프라인 HTML 브라우저 | 17/17(100%) 통과 |
| 연결 미설정 브라우저 | 1/1(100%) 통과 |
| admin 합계 | 41/41(100%) 통과 |
| lint·typecheck·demo/미설정 빌드·HTML 일치 | 모두 통과 |
| develop Ruff | 통과 |
| develop architecture·contract·unit | 1,712개 실행 시험 모두 통과(100%). 별도로 67개 skipped, 173개 deselected, warning 1개 |
| 독립 검토 | 데모 격리·의존성/경로·시간대·CI 순서·문서 링크에서 통합을 막는 문제를 발견하지 못함 |

기존 사용자 웹의 로컬 `.env.example` 수정은 PR에 포함하지 않았다. 기존 web·백엔드 실행 코드, 팀 규칙과 API 명세는 이 작업에서 변경하지 않았다. `CI (web)`은 해당 앱 변경이 없어 이 PR의 실행 대상이 아니다.

## 병합 기준의 미해결 사항

`RULE.md` §5는 모든 merge에 `scripts.verify_dod`를 요구하지만, 해당 스크립트는 자신을 v8 29항목의 과거 기록으로 명시하고 현행 기준으로 `verify_dod_v11`을 안내한다. 구판 증거 전제조건을 읽기 전용으로 확인한 결과 26/29(89.7%)만 충족하고 DoD-15·17·28은 부분통과다. 전체 DoD 명령을 실행한 결과가 아니며 제품의 현재 달성률도 아니다. 이 파일·증거는 admin 작업에서 변경하지 않았고, 에이전트가 게이트를 면제하거나 통과로 고치지 않는다. 병합 전에 적용 기준 또는 이번 PR의 예외 승인이 필요하다.

기준 develop의 [main 대상 PR #2 CI](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/36542545681)에는 기존 실패 1건이 있다. `tests/integration/api/test_openapi_surface.py`의 고정 `CONTRACT_V1_PATHS` 목록에 `/v1/web/warmup`이 빠져 실패하며 실제 Markdown API 명세에는 이미 존재한다. 원문 집계는 `1 failed, 2242 passed, 176 skipped, 180 deselected`다. admin→develop의 실행 대상은 아니지만 전체 제품 검증 성공과 혼동하지 않는다. 이 작업에서 해당 백엔드 시험을 수정하지 않았다.

## 남은 단계

백엔드와의 다음 작업은 [운영 앱 API 협의](../../external/admin-screen-api.md)를 기준으로 계약을 맞추는 것이다. API 계약 합의·live 어댑터·실제 서버 통합·배포는 이번 성공 범위에 포함하지 않는다. 이후 같은 CI에 계약·인증/권한·오류 응답·live 어댑터 회귀 시험을 추가하고, 실제 백엔드 통합은 별도의 실행 조건과 결과로 기록한다.
