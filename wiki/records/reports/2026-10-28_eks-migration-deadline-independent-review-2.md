---
type: report
title: EKS 마이그레이션 시도별 제한 후보 0f584a2eb — 2차 독립 검토 · 격리 실제 PostgreSQL 경합 시험 · 하드코딩 격리 수정
description: 후보 0f584a2eb 의 commit 불확실 · 취소 경합 · 여러 문장 재시도 · DB 시험 격리 · Job 시간 값 하드코딩을 독립으로 확인하고, 하드코딩(RULE.md 3)만 격리 clone 의 추가 커밋 ca879220b 로 고친 기록
status: draft
domain: travel
impl_scope: cs — final_project_cs/deploy/aws_cd.py · deploy/aws/migration-job.json · app/infrastructure/db/migrate.py 후보(push 안 함)
---

# EKS 마이그레이션 시도별 제한 — 2차 독립 검토 · 2026-10-28

선행: [수정 보고](2026-10-28_eks-migration-per-attempt-deadline-fix.md) · [1차 독립 검토](2026-10-28_eks-lock-policy-independent-review-real-pg.md). 개발 쪽 clone `eks-lock-fix-20261027`(HEAD `0f584a2eb`, 작업 트리 변경 0)은 건드리지 않았다. push · 배포 0.

## 결론 — 통합 준비: **가능(조건부)**, blocker 1건 격리 수정

| 항목 | 판단 | 근거 |
|---|---|---|
| 여러 문장 한 execute 를 시도 제한이 끊는가 | **끊는다** | A: 1.5초×4 문장 · 제한 3초 → 4.12초에 `MigrationAttemptTimeout` 57014, 탐침 표 없음(Job 스크립트 원문) |
| commit 불확실 표시 | **맞음(보수적)** | B: 제한이 COMMIT 중(지연 제약 트리거 sleep)에 닿음 → `commit_unknown` · QueryCanceled. 실제 DB 는 되돌려짐(표 없음). C: COMMIT 중 연결 강제 종료 → `commit_unknown` · AdminShutdown 57P01, 표 없음. **서버가 COMMIT 에 오류를 돌려준 경우는 되돌림이 확정이라 `commit_unknown` 은 과한 쪽**이다(안전 방향, 다음 배포가 사람 확인을 요구할 수 있음 — 막는 결함 아님) |
| 취소 경합(늦은 취소가 다음 문장에 닿는가) | **이번 시험 범위에서 0건** | D: 실행이 제한(1.0초) 근처에서 끝나게 0.80~1.20초 무작위 60회 → 커밋 29 · 시도 초과 31, **결과와 DB 상태 불일치 0/60**, 직후 같은 연결 10문장씩 늦은 취소 0/600. E/E2: lock_timeout(950 · 900ms)과 제한 1.0초 경합 · 사이 대기 0 · 50회 → 커밋 0 · 표 남음 0 · 늦은 취소 0/500. 경합은 확률 시험이라 「없음 증명」이 아니다 |
| 재시도 · 시간 상한 | **식은 맞고, 시도마다 소량 초과** | 시도 하나 = 제한 + 취소 왕복 + 되돌림. 로컬 실측 초과 최대 0.23초/시도(D 1.234초 · E2 3.781초/3시도). 식 `횟수×제한+대기+여유` 에 이 몫은 없다 — 지금 493 ≤ 600 의 남는 107초가 덮는다. 취소 자체가 서버에 못 닿으면(망 단절) 시도 제한은 지켜지지 않고 `statement_timeout`(문장마다 2분)과 Job `activeDeadlineSeconds` 가 마지막 상한이다(그때 기록은 `unknown`) |
| 시도 제한 초과 후 재시도 여부 | 다시 하지 않음 | E2 에서 `attempt_timeout@1` · `@2` 각 1회 — 그 시도에서 멈춤 |
| DB 시험이 진짜 · 격리인가 | **진짜 · 격리** | 새 initdb 클러스터 `127.0.0.1:55481`(PG 16.15) 에 `ACOP_DATABASE_URL` 로만 접속. `test_migrations_rerun` + `test_service_improvement` **23/23 · skip 0**, 서버 로그에 임시 DB `CREATE DATABASE` 12회(migtest 11 · improve 1) 확인. ★단 이 23건은 `attempt_timeout_s` 를 쓰지 않는 경로(x600 · 시험)만 탄다 — 새 시도 제한은 위 A~E 하네스와 단위 시험만 덮는다 |
| **하드코딩(blocker)** | **RULE.md 3 위반 → 격리 수정** | 후보는 Job 기한 600 · 시도 2min · 시작 여유 120 · 결과 대기 `+ 120` 을 `aws_cd.py` 에 박았다. 같은 저장소가 잠금 값은 이미 `migration-plan.json` 한 곳으로 뺐으니 피할 수 없는 값이 아니고, 「불가피」 문서도 없었다 |
| 중첩 경로의 조용한 제한 누락 | 고침(같은 커밋) | `apply_all(attempt_timeout_s=)` 를 바깥 트랜잭션 안에서 부르면 제한 없이 돌았다(하네스 첫 판이 실수로 그 상태가 되어 5분 넘게 잠금 대기). Job 은 IDLE 을 먼저 확인해 닿지 않지만 「조용한 폴백」이라 거절로 바꿨다 |

## 격리 수정 — `ca879220b`(clone `eks-deadline-indep-review-20261028/fixclone`, branch `review/eks-migration-job-settings-20261028`, `0f584a2eb` 위 1커밋)

- `final_project_cs/deploy/aws/migration-job.json`: `active_deadline_seconds` 600 · `attempt_timeout` `"2min"` · `start_reserve_seconds` 120 · `result_wait_margin_seconds` 120. `aws_cd.migration_job_settings()` 가 정확한 키 · 양의 정수(bool 거절) · 단위 있는 기간만 받고, 없거나 틀리면 `DeploymentError`(코드 기본값 없음).
- 값의 근거는 `final_project_cs/wiki/operations/aws-main-cd.md` 에 적었다: 600 · 720(=600+120) 대기는 팀 main `e88e01925` 에 이미 있던 값 그대로, **시도 2min · 시작 여유 120 은 판단값**(EKS 에서 안 잼) — 첫 CD Job timings 로 다시 본다.
- 동작 불변: 만든 Job JSON · `MIGRATION_SCRIPT` 가 `0f584a2eb` 와 **바이트 동일**, 최악값 373 + 여유 120 = 493 그대로.
- 시험: 새 3건 RED(기능 없음 4 실패 — 이 중 1건은 기존 시험의 리터럴 600 을 설정값 비교로 바꾼 것) → GREEN. 6파일 **137/137**(skip 0) · DB 통합 **23/23**(55481, skip 0) · 변이 **7/7 = 100%**(통제 실행 통과 확인 뒤 — 첫 판은 `config/` 를 안 복사해 76 errors 로 전부 「검출」처럼 보였고 버렸다) · ruff 0.16.8 통과 · `git diff --check` 는 CRLF 파일(`test_migration_lock_policy.py`) 줄 끝만, `cr-at-eol` 로 0.
- 개발 쪽 변이 8/8(`mutate.log`)은 다시 열어 실패(failed)로 잡힌 것을 확인했다 — errors 아님.

## 남은 일 · 한계

1. **push 0.** 부모가 `0f584a2eb` + `ca879220b`(patch `eks-deadline-indep-review-20261028/patches/0001-*.patch`)를 팀 main PR 로 → CI (main) · CI (web). main 이 움직였으면 rebase 후 같은 시험 재실행.
2. 수정 권고(막지 않음): COMMIT 에 **서버 오류(SQLSTATE 있음)** 가 오면 되돌림 확정이므로 `failed_before_commit` 으로 좁힐 수 있다. 지금은 연결 끊김과 같이 `commit_unknown` — 안전하지만 다음 배포를 불필요하게 막을 수 있다.
3. `get_connection()` 은 `connect_timeout` 이 없어 RDS 접속이 매달리면 시작 여유 120초 밖이다(Job 기한이 마지막 상한, 기록 `unknown`, DB 변경 없음). `aws_cd.py` 의 다른 명령 시간 제한(60 · 300 · 600 · 1200 · 2400초)은 main 에 원래 있던 값이라 이번 범위 밖.
4. 실제 EKS · RDS(PostgreSQL 18.3) · psycopg 3.3.4 + 이미지 libpq 조합의 취소 왕복 시간은 안 잼(로컬 libpq 18.3 · 서버 16.15).
5. actionlint 는 이번 수정이 워크플로를 안 바꿔 다시 돌리지 않았다(개발 쪽 기록 0건).

## 증거(공개 저장소 밖, Hermes profile scratch `eks-deadline-indep-review-20261028/`)

`race_harness.py` · `race_e2.py` · `race.log`(A~C 기록 · 첫 D/E 는 하네스 결함으로 무효 — 아래 `race_de.log` 가 유효) · `race_de.log` · `race_results_de.json` · `race_results_e2.json` · `rec_A/B/C.json` · `unit2.xml` · `dbint.xml` · `fix_red.xml` · `fix_unit6.xml` · `fix_dbint.xml` · `mutate_fix.py/log` · `fix_ruff.log` · `pg.log` · `patches/0001-*.patch`(sha256 `ae4687b5…`) · `hashes.txt`. 최종 파일 sha256: `aws_cd.py` `f1e228d6…` · `migration-job.json` `63ec0f85…` · `migrate.py` `9be52358…` · `test_aws_cd.py` `622a8de1…` · `test_migration_lock_policy.py` `ae272376…`. 클러스터는 끝나고 정지(55481 LISTEN 0). 공유 5433 · x600 · EKS · RDS 접속 0.
