---
type: handoff
title: EKS 마이그레이션 시도별 제한 · Job 기한 검사 보강 인계
description: 누적 후보 0f584a2eb 의 상태와 다음 세션이 할 일
status: draft
domain: travel
impl_scope: cs — final_project_cs/deploy/aws_cd.py · app/infrastructure/db/migrate.py 후보(push 안 함)
---

# 인계 — 2026-10-28 EKS 마이그레이션 시도별 제한

## 한 일

- 팀 `main` 재확인 `e88e01925`. 격리 clone `cache/scratch/eks-lock-fix-20261027` 에 커밋 `0f584a2eb`(누적 3커밋, fast-forward 가능).
- 실제 PG16 에서 `statement_timeout` 이 문장마다 걸려 시도 하나를 못 묶는 것을 확인 → `apply_all(attempt_timeout_s=)` 시도별 취소 · `MigrationAttemptTimeout`, Job 기한 검사 = 횟수 × 시도 제한 + 사이 대기 + 시작 여유 ≤ 600초(지금 493초), COMMIT 중 오류 `commit_unknown`.
- 검증: 실 PG 10/10 · 단위 134/134 · DB 통합 23/23 · 변이 8/8 · ruff · actionlint 0. [보고서](../records/reports/2026-10-28_eks-migration-per-attempt-deadline-fix.md)
- 쓴 파일: 이 인계, 보고서, 인계 목차 한 줄. 후보 안에서 `final_project_cs/wiki/operations/aws-main-cd.md` 한 줄 갱신.

## 안 한 일 / 다음

1. push · PR · CI 안 함 — 부모 몫(`eks-lock-deadline-20261028/patches/0001~0003`).
2. 시작 여유 120초 · 시도 2분은 첫 CD Job timings 로 재검토.
3. 실제 EKS 확인은 AWS 자격증명 복구 뒤.
