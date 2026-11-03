---
type: handoff
title: EKS 후보 lock_policy 수정 독립 검토 · 실 PostgreSQL 충돌 재시도 인계
description: aaebdacc3 의 main 통합 준비 상태와 다음 세션이 할 일
status: draft
domain: travel
impl_scope: cs — final_project_cs/deploy/aws_cd.py 후보(push 안 함)
---

# 인계 — 2026-10-28 EKS 후보 독립 검토

## 한 일

- 팀 `main` 재확인: `e88e01925`(ls-remote). 후보 clone `cache/scratch/eks-lock-fix-20261027` 의 `aaebdacc3` 는 그 위 2커밋 → fast-forward 가능.
- 코드 검토: 재시도 경로 맞물림 · 잠금 값 단일화 · 기록 정제 · 워크플로 gate 순서 정상. 후속 권고 1건(Job 기한 검사가 시도별 `statement_timeout` 을 한 번만 셈).
- 격리 PostgreSQL 16.15(`127.0.0.1:55472`, scratch 새 클러스터, 끝나고 정지)에서 Job 스크립트 원문 실행: 후보 5/5 기대대로(55P03 재시도 성공 · 3회 소진 기록 · 40P01 재시도 성공), 수정 전 I 2/2 재시도 0회로 결함 재현. 실패 시 전체 되돌림은 탐침 인덱스로 확인.
- 재실행: 단위 119/119 · `test_migrations_rerun` 11/11 · ruff 통과 · `diff --check` 0.
- 쓴 파일: 이 인계, [보고서](../records/reports/2026-10-28_eks-lock-policy-independent-review-real-pg.md), 인계 목차 한 줄. 증거는 Hermes scratch `eks-lock-pg-review-20261028/`.

## 안 한 일 / 다음

1. push · PR · CI 실행 안 함 — 부모가 `series.patch` 로 팀 main PR 을 올리고 CI (main) · CI (web) · actionlint 확인.
2. Job 기한 최악값(3×300+13 > 600초) 보강 여부 결정.
3. 실제 EKS 확인은 AWS 자격증명 복구 뒤.
