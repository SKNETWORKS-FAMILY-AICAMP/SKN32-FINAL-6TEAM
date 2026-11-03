---
type: report
title: EKS 마이그레이션 시도별 제한 시간 · Job 기한 검사 보강 — 격리 실제 PostgreSQL 검증
description: 독립 검토 §1 위험 1(기한 검사가 재시도마다 다시 걸리는 제한을 한 번만 셈)을 고친 누적 후보 0f584a2eb(팀 main e88e01925 위 3커밋)와 실 DB · 단위 · 변이 · 워크플로 검사 기록
status: draft
domain: travel
impl_scope: cs — final_project_cs/deploy/aws_cd.py · app/infrastructure/db/migrate.py 후보(push 안 함)
---

# EKS 마이그레이션 시도별 제한 · Job 기한 보강 — 2026-10-28

선행: [독립 검토](2026-10-28_eks-lock-policy-independent-review-real-pg.md) §1 위험 1 · §4-2.

## 결론

| 항목 | 결과 |
|---|---|
| 누적 후보 | 격리 clone `cache/scratch/eks-lock-fix-20261027` branch `fix/eks-lock-policy-20261027`: `d83ec69b4`(I) → `aaebdacc3`(lock_policy) → **`0f584a2eb`**(이번, tree `a1af7e5b`). 팀 `main` = `e88e01925`(10-28 `ls-remote` 재확인) → fast-forward 가능. patch 3개를 `e88e01925` 에 다시 얹은 tree 가 HEAD tree 와 같다 |
| 검토가 본 것보다 큰 결함 | `statement_timeout` 은 한 번에 보낸 여러 SQL 의 **문장마다** 걸린다(PostgreSQL 13+). 실제 16.15 에서 3초 제한 · 2초×3 문장 한 execute 가 6.03초 끝까지 돌았다. 마이그레이션은 111개 SQL 을 한 execute 로 보내므로 「횟수 × statement_timeout」 도 상한이 아니다 |
| 고침 | `apply_all(attempt_timeout_s=)` 가 **시도마다 새** 벽시계 제한(BEGIN~COMMIT). 넘으면 다른 스레드가 `cancel_safe()` → 그 시도 되돌림 → `MigrationAttemptTimeout`(57014 · 시도 번호), 다시 하지 않음. Job 은 `2min`(=120초)을 넘기고 같은 값을 세션 `statement_timeout`(받침)으로 건다 |
| 기한 검사 | `lock_policy` 횟수 × 시도 제한 + 사이 대기 합 + 시작 여유 `MIGRATION_START_RESERVE_SECONDS` 120 ≤ `activeDeadlineSeconds` 600. 값은 지금 `migration-plan.json` · `aws_cd` 설정에서 읽는다 → 지금 3×120+13+120 = **493초**. `lock_timeout` ≥ 시도 제한(재시도 불가능)도 거절. 옛 식(잠금 예산 28 + 문장 300 = 328)은 최악 913초 이상을 통과시켰다 |
| 기록 정정 | `apply_all` 의 COMMIT 도중 오류에 `migration_commit_uncertain` → Job 기록 `commit_unknown`(전에는 `failed_before_commit` 으로 잘못 적힐 수 있었다) |
| x600 경로 | `migrate.main()` 은 `attempt_timeout_s` 를 안 넘긴다 → 동작 그대로 |
| 실제 PostgreSQL(Job 스크립트 원문, 새 DB) | **10/10 = 100% 기대대로**(아래 표) · 서버 로그: 사용자 취소 2(D1 · D3) · lock timeout 7(N2 1 + N3 3 + D2 3) · deadlock 1(N4) — 표와 같다 |
| 시험 | RED 16(새 기능 없음 때문만) → `test_aws_cd` + lock_policy **73/73** · 6파일 **134/134**(skip 0) · DB 통합 `test_migrations_rerun` + `test_service_improvement` **23/23**(skip 0, 격리 클러스터) · 변이 **8/8 = 100% 검출** |
| 정적 · 워크플로 | ruff 0.16.8 `check .` 통과 · actionlint 1.7.12(공식 릴리스, sha256 대조) `cd-aws` · `ci-main` · `ci-web` 0건(shellcheck · pyflakes 미설치로 끔) · `git diff --check` 는 CRLF 파일(`test_migration_lock_policy.py`, 저장소 blob 이 CRLF)의 줄 끝만 보고 — `cr-at-eol` 로 0 |
| 미확인 | GitHub CI(main · web) · 실제 EKS · RDS(PostgreSQL 18.3) — push 0 |

## 실제 PostgreSQL 시나리오

클러스터: 독립 검토가 만든 scratch `eks-lock-pg-review-20261028/pgdata`(16.15 · `127.0.0.1:55472` · trust), 새 DB `eks_deadline_review`. 끝나고 정지(55472 LISTEN 0). 공유 5433 · x600 · EKS · RDS 접속 0. D 시나리오는 Job 스크립트 원문을 그대로 돌리고 `compiled_sql` 만 느린 합성 SQL 로 바꿨다(`harness2.py` WRAP).

| 시나리오 | 스크립트 · 제한 | rc | 기록 | 재시도 줄 | 걸린 시간 | 남은 것 |
|---|---|---|---|---|---|---|
| N0 빈 DB 첫 적용 | 새 · 2min | 0 | committed | 0 | 3.14s | 탐침 인덱스 있음 |
| N1 재실행 | 새 | 0 | committed | 0 | 1.44s | 있음 |
| N2 잠금 7초 쥐고 놓음 | 새 | 0 | committed | 1(55P03) | 9.50s | 있음 |
| N3 잠금 계속 쥠 | 새 | 1 | failed_before_commit · MigrationLockFailed · 55P03 · 3 | 2 | 29.61s | **없음**(전체 되돌림) |
| N4 교착 1회 | 새 | 0 | committed | 1(40P01) | 7.58s | 있음 |
| D1 5초 문장 2개 | 새 · 6s | 1 | failed_before_commit · MigrationAttemptTimeout · 57014 · 1 | 0 | 7.27s(시작 약 1.2s 포함) | 탐침 표 **없음** |
| D1p 같은 조건 | 이전 `aaebdacc3` · 6s | 0 | committed | 0 | **11.31s** — 제한을 넘겨 커밋 | 탐침 표 있음 |
| D2 6초 작업 + 잠금 대기, 잠금 계속 쥠 | 새 · 12s | 1 | MigrationLockFailed · 55P03 · 3 | 2 | **47.16s** — 옛 식 28+12 = 40 초과, 새 식 3×12+13 = 49 안 | 없음 |
| D3 9초 작업 + 잠금 대기 | 새 · 12s | 1 | MigrationAttemptTimeout · 57014 · 1 | 0 | 13.97s — 잠금 대기도 시도 제한 안에서 끊김 | 없음 |
| N5 마무리 재실행 | 새 | 0 | committed | 0 | 1.56s | 있음 |

## 변이(scratch 사본)

옛 식 복원 · 시작 여유 무시 · Job 이 제한 안 넘김 · Job 이 commit 불확실 무시 · 취소 안 보냄 · 첫 시도만 제한 · COMMIT 단계 표시 안 함 · `lock_timeout ≥ 시도` 허용 — 8/8 이 시험 실패(2~3건씩).

## 증거(공개 저장소 밖, Hermes profile scratch `eks-lock-deadline-20261028/`)

`probe_statement_scope.py/.json` · `harness2.py` · `results2.json` · `harness2.log` · `red.xml/log` · `green.xml/log` · `unit6.xml/log` · `db_integration.xml/log` · `mutate.py/log` · `ruff.log` · `actionlint.log` · `patches/0001~0003` · `aws_cd_prev_aaebdacc3.py`(sha256 `9242e422…` = 검토 대상) · `hashes.txt`. 서버 로그 `eks-lock-pg-review-20261028/pg2.log`. 최종 파일 sha256: `aws_cd.py` `16305da7…` · `migrate.py` `8b7591d6…` · `test_aws_cd.py` `d7ece163…` · `test_migration_lock_policy.py` `b640a98c…`.

## 남은 일

1. **push 0.** 부모가 `patches/0001~0003`(또는 clone `0f584a2eb`)로 팀 main PR → CI (main) · CI (web) 확인. main 이 움직였으면 rebase 뒤 같은 시험 재실행.
2. 시작 여유 120초 · 시도 제한 2분은 판단값이다(지금 마이그레이션 2~3초, 새 API 이미지 pull 시간은 EKS 에서 안 잼). 첫 CD 의 Job timings 로 다시 본다.
3. RDS 는 PostgreSQL 18.3 이라 서버 쪽 `transaction_timeout`(17+)도 쓸 수 있지만 CI · 격리 검증이 16 이라 이번엔 버전 무관한 클라이언트 취소로 했다.
4. 워크플로 `timeout-minutes: 75` 는 바꾸지 않았다. 마이그레이션 최악이 600+120초 대기 → Job 이 약 493초 안에 끝나 여유는 늘었다.
5. 실제 EKS 확인은 AWS 자격증명 복구 뒤.
