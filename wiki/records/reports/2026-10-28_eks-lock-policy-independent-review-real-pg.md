---
type: report
title: EKS 배포 후보 I + lock_policy 수정 — 독립 검토 · 격리 실제 PostgreSQL 충돌 재시도 검증
description: 후보 aaebdacc3(팀 main e88e01925 위 2커밋)를 코드 검토하고, scratch 전용 PostgreSQL 16.15 클러스터에서 Job 스크립트 원문을 잠금 대기 · 교착 충돌 아래 실제로 돌려 재시도 동작과 수정 전 결함을 확인한 기록
status: draft
domain: travel
impl_scope: cs — final_project_cs/deploy/aws_cd.py · .github/workflows/cd-aws.yml · ci-web.yml 후보(push 안 함)
---

# EKS 후보 lock_policy 수정 독립 검토 · 실제 PostgreSQL 충돌 재시도 — 2026-10-28

선행: [2026-10-27 수정 보고](2026-10-27_eks-lock-policy-conflict-fix-and-latency-readback.md). 이 보고는 그 후보를 다시 고치지 않고 **검토와 실 DB 검증만** 했다.

## 결론 — main 통합 준비: **가능(조건부)**

| 항목 | 결과 |
|---|---|
| 기준 | 팀 `main` = `e88e01925`(10-28 `ls-remote` 로 재확인, 10-27 이후 안 움직임). 후보 `aaebdacc3` 는 그 위 2커밋(`d83ec69b4` I · `aaebdacc3` 수정), `rev-list` 0/2 → **fast-forward 가능, 충돌 없음** |
| 실제 PostgreSQL 충돌 시나리오(후보 Job 스크립트 원문) | **5/5 = 100% 기대대로** — 잠금 대기 뒤 재시도 성공 · 3회 소진 실패 기록 · 교착 뒤 재시도 성공 · 빈 DB 첫 적용 · 재실행 |
| 수정 전(I `d83ec69b4`) 같은 충돌 | **2/2 = 100% 결함 재현** — 재시도 0회, 첫 55P03 · 40P01 에서 바로 실패 |
| 단위 시험(재실행) | 6파일 **119/119 = 100%**(`test_aws_cd` 45 · lock_policy 13 · safe_deploy 39 · restore_check 12 · deploy_notice 6 · current_plan 4) |
| 실 DB 통합 시험 | `tests/integration/db/test_migrations_rerun.py` **11/11 = 100%**(격리 클러스터) |
| 정적 | ruff 0.16.8 `check .` 통과 · `git diff --check` 0 |
| 미확인 | actionlint(이 PC 에 없음) · GitHub CI(main/web) · 실제 EKS — **PR 때 CI 로 확인 필요** |

## 1. 코드 검토(독립)

정상으로 판단한 것:

- Job 스크립트는 `statement_timeout` 만 세션에 걸고 확인 → `conn.commit()` → IDLE 확인 → `apply_all(conn)`. `apply_all` 은 IDLE 일 때만 맨 바깥 경로(시도마다 `SET LOCAL lock_timeout` + 40P01/55P03 재시도)로 간다 — 두 조건이 맞물린다. psycopg 3 기본 tuple 행이라 `fetchone()[0]` 도 맞다.
- 잠금 값은 `migration-plan.json` `lock_policy`(5000ms · 3회 · [3, 10]) 한 곳. CD 러너는 `migration_plan.py`(표준 라이브러리만)를 파일 경로로 읽어 같은 검증기로 확인하고, 정책이 없거나 틀리면 Job 을 만들지 않는다.
- 실패 기록: `MigrationLockFailed.attempts`(int) · `sqlstate` 를 termination 메시지에 싣고, CD 쪽 `job_outcome` 은 정해진 키 · 정규식 · 0~100 정수만 읽는다(로그 · 메시지 원문 없음).
- 워크플로: `gate --main-only` → 이미지 게시 → 전체 gate → 자격 재발급 → deploy. deploy 는 두 gate 의 sha 가 같을 때만. role-manager 트리거 추가 없음(10-13 규칙 지킴).

남는 위험(통합을 막지 않음, 후속 권고):

1. **Job 기한 검사가 최악값이 아니다.** 검사식은 `잠금 예산 28초 + 문장 제한 300초 < 600초` 인데, `statement_timeout` 은 **시도마다** 다시 걸리고 `lock_timeout` 은 **잠금 하나마다**다. 시도 1·2 가 오래 돈 끝에 잠금 실패하면 이론상 3×300+13 초 > 600 초 → `activeDeadlineSeconds` 로 파드가 죽고 기록은 `unknown`(서버는 연결 끊김으로 되돌린다 — 반쯤 적용은 없다). 지금 마이그레이션은 빈 DB 첫 적용 2.5초 · 재실행 1.4~1.6초라 실제 가능성은 낮다. 고치려면 `statement_timeout ≤ (600−13)/3`(예: `3min`) 로 줄이거나 검사식을 `attempts×statement` 로 바꾼다.
2. 주석 「lock_policy retries plus the statement bound must end before the Job deadline」은 위 1 의 범위(잠금 대기분)만 보장한다는 점이 드러나지 않는다.

## 2. 격리 실제 PostgreSQL 검증

- 클러스터: portable `C:/_proj/postgresql/runtime/pgsql-16.15` 로 Hermes scratch `eks-lock-pg-review-20261028/pgdata` 에 **새로 initdb**(trust · `127.0.0.1:55472` · Asia/Seoul · `log_lock_waits`), DB `eks_lock_review`. 공유 5433 · x600 · EKS · RDS 접속 0. 끝나고 `pg_ctl stop`(55472 LISTEN 0 확인).
- 대상: 후보 트리 `final_project_cs`(현 main 의 `migrate.py` 그대로) + `aws_cd.py` 의 `MIGRATION_SCRIPT` **원문**을 `python -c` 로 Job 과 같은 인자(`result_path`, `5min`)로 실행. 수정 전 비교는 `d83ec69b4` 의 스크립트 원문(`5s`, `5min`).
- 충돌 방법: 다른 세션이 마지막 `ALTER TABLE` 대상 `trip_intakes` 에 ACCESS EXCLUSIVE 를 쥔다. 교착은 Job 이 그 표에서 기다리는 것을 `pg_locks` 로 본 뒤, Job 이 이미 쥔 `action_requests` 를 요청해 순환을 만든다(차단 세션 `deadlock_timeout 60s` → Job 이 희생자).
- 되돌림 확인: 실행 전마다 앞쪽 `CREATE INDEX IF NOT EXISTS` 의 `cases_tenant_customer_idx` 를 지우고, 실패 뒤에는 **없음**(전체 되돌림) · 성공 뒤에는 **있음**을 확인했다.

| 시나리오 | 스크립트 | rc | 기록(termination) | 재시도 줄 | 걸린 시간 | 탐침 인덱스 |
|---|---|---|---|---|---|---|
| S0 빈 DB 첫 적용 | 후보 | 0 | committed | 0 | 2.48s | 있음 |
| S1 재실행 | 후보 | 0 | committed | 0 | 1.56s | 있음 |
| S2 잠금 7초 쥐고 놓음 | 후보 | 0 | committed | 1(55P03, wait 3) | 9.42s | 있음 |
| S3 잠금 계속 쥠 | 후보 | 1 | failed_before_commit · MigrationLockFailed · 55P03 · attempts 3 | 2(wait 3·10) | 29.47s(예산 28s) | **없음** |
| S4 교착 1회 | 후보 | 0 | committed | 1(40P01) | 5.64s | 있음 |
| R1 = S2 조건 | 수정 전 I | 1 | failed_before_commit · LockNotAvailable · 55P03 | **0** | 7.00s | 없음 |
| R2 = S4 조건 | 수정 전 I | 1 | failed_before_commit · DeadlockDetected · 40P01 | **0** | 2.34s | 없음 |
| S5 마무리 재실행 | 후보 | 0 | committed | 0 | 1.39s | 있음 |

서버 로그 교차 확인: `lock timeout` 5건(S2 1 + S3 3 + R1 1) · `deadlock detected` 2건(S4 · R2) — 표와 같다.

## 3. 증거(공개 저장소 밖, Hermes profile scratch `eks-lock-pg-review-20261028/`)

`harness.py`(sha256 `5ba8e092…`) · `results.json`(`a8116f83…`) · `unit.xml`(`6e8af1a7…`) · `db_rerun.xml`(`e204f219…`) · `series.patch`(`format-patch e88e01925..aaebdacc3`, `c47d2e7f…`) · `pg.log` · `hashes.txt`. 후보 `aws_cd.py` sha256 `9242e422…` = 10-27 기록과 같다. 후보 clone 작업 트리 변경 0 · 원본 작업 폴더는 `safe_git fetch team` · `ls-remote` 만(HEAD `efeb873a8` 그대로).

## 4. 남은 일

1. **push 0.** 통합은 부모 몫: `series.patch`(또는 clone 의 `aaebdacc3`)를 팀 main 기반 PR 로 올리고 CI (main) · CI (web) · actionlint 결과를 확인한다(main 이 움직였으면 rebase 후 같은 시험 재실행).
2. 위 §1 위험 1(Job 기한 최악값) — 통합 전 고칠지 결정. 고치면 `test_aws_cd` 에 「attempts×statement ≥ 기한이면 Job 거절」 시험을 추가.
3. 실제 EKS 확인(첫 CD migration Job termination 기록 · timings)은 유효한 AWS 자격증명 또는 CD 실행 뒤에만 가능 — 10-27 기준 자격증명 무효 그대로.
