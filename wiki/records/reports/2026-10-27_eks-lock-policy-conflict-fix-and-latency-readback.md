---
type: report
title: 계획 접수 속도 개선 뒤 읽기 전용 확인 · EKS 후보 마이그레이션 잠금 상충 수정
description: 속도 후보 A·B 배포 뒤 x600 실측 가능 여부(읽기 전용 집계), AWS 자격증명 상태, EKS 후보 I 의 lock_policy 상충을 최신 main 격리 clone 에서 TDD 로 고친 기록
status: draft
domain: travel
impl_scope: cs — final_project_cs/deploy/aws_cd.py 후보(push 안 함)
---

# 계획 접수 속도 개선 뒤 읽기 전용 확인 · EKS 후보 잠금 상충 수정 — 2026-10-27 23:35~23:50 KST

## 결론

| 항목 | 결과 |
|---|---|
| 속도 후보 A(위험 점검 동시) · B(대안 준비 양보) 운영 반영 | x600 `9a15223e0c` 반영 완료 **17:23:26**(deploy.log). 두 커밋(`3ea98bc48` · `b0c334285`) 모두 그 조상임을 git 으로 확인 |
| 반영 뒤 실측 | **불가 — 반영 뒤 접수 0건**(17:23:26 ~ 23:40 x600 `trip_intakes` 0행). 개선 수치는 아직 추정값이다 |
| 반영 전 기준선 재현(채팅 전용 접수, 10-20~10-26) | 읽기 p50 8.0 · p95 21.2초(152) / 검사 끝→채우기 끝 p50 10.2 · p95 39.2초(152) / 위험 점검 창 p50 4.2 · p95 19.4초(155) / **「읽는 중」 전체 p50 21.8 · p95 64.1초(152)** — 보고서(157건 p50 20.4 · p95 62.3)와 같은 크기. 차이는 표본 조건(채팅만 · 날짜 경계) 때문 |
| AWS 자격증명 | **여전히 무효.** x600 `aws sts get-caller-identity` → `InvalidClientTokenId`(rc 254, 23:39). 이 PC 에는 aws CLI · `~/.aws` · `AWS_*` 환경변수 · kubectl 없음. 키 값은 읽거나 기록하지 않았다 |
| EKS 후보 I(`1b38aa7ef`) ↔ C `lock_policy` 상충 | **고침(후보 커밋, push 0).** 최신 팀 main `e88e01925` 위 격리 clone 에 I cherry-pick(충돌 0) + 수정 커밋 `aaebdacc3`(tree `de564554`) |
| 시험 | 새/바뀐 6건 RED → GREEN · `test_aws_cd` **45/45 = 100%** · `test_migration_lock_policy` **13/13 = 100%** · 환경변수 없는 unittest 45/45 · ruff 0.16.8 `check .` 통과 · 변이(커밋 줄 제거) 6 실패 |

## 1. 속도 — 읽기 전용 측정 방법

- 접속: x600 SSH 키 로그인 → `docker exec -i tripilot-tripilot-db-1 psql`. SQL 은 `BEGIN READ ONLY` · `statement_timeout 30s` · `lock_timeout 2s` 안에서 집계만 하고 `ROLLBACK`. 접수 id · 원문 · 계정 열은 하나도 출력하지 않았다(백분위와 개수만).
- 구간 정의는 속도 병목 보고서 `final_project_cs/wiki/records/reports/2026-10-27_계획서빙_속도_병목측정.md`(로컬 작업 폴더에는 아직 없음 — 팀 원격에서 읽음)(팀 `role-manager` `1a6519688`)와 같다: 읽기 끝 = `reading.agent` rev1 `created_at`, 검사 끝 = `payload.built_at`, 채우기 끝 = `reading.prefill` `created_at`(clock_timestamp), 위험 점검 창 = `payload.risk_checked_at` → 일정별 `risk.checked_at` 최댓값.
- 고객 GET · 접수 재생 · 쓰기 0. SQL 원본: Hermes scratch `serving-latency-after-20261027/q_after.sql`, 결과 `result.txt`.
- **다음 측정**: 반영 뒤 채팅 접수가 쌓이면 같은 SQL 의 `after` 창으로 다시 잰다. 보고서의 추정(위험 점검 4일정 p50 4.8 → 약 2.7초, 겹친 읽기 p50 12.6 → 약 7.5초)은 그때까지 추정이다.

## 2. EKS 후보 잠금 상충 — 원인과 고침

- 원인(통합 K 보고서 §4): psycopg 기본은 autocommit 꺼짐이다. I 의 Job 스크립트가 `SELECT set_config(...)` · `current_setting` 으로 트랜잭션을 연 채 `apply_all(conn)` 을 불러, `apply_all` 이 **중첩(savepoint) 경로**로 갔다 → `migration-plan.json` `lock_policy` 의 교착(40P01) · 잠금 대기 초과(55P03) 재시도가 꺼진다. 잠금 값도 두 곳(I 상수 `"5s"` · C json 5000ms)이었다.
- RED 증거: 진짜 `migrate.apply_all` + psycopg 처럼 트랜잭션 상태를 바꾸는 가짜 연결로 Job 스크립트를 돌리면, 고치기 전에는 첫 `LockNotAvailable` 에서 **1회 만에 실패**(`1 != 2`, 재시도 없음).
- 고침(`final_project_cs/deploy/aws_cd.py`):
  - Job 은 `statement_timeout 5min` 만 세션에 걸고 서버 값 확인 → `conn.commit()` → 연결이 IDLE 이 아니면 시작하지 않음 → `apply_all` 맨 바깥 호출(시도마다 `SET LOCAL lock_timeout` + 재시도).
  - `MIGRATION_LOCK_TIMEOUT` 상수 삭제. 잠금 값은 `lock_policy` 한 곳 — Job 생성 때 `migration_plan.lock_policy` 검증기(같은 파일)로 읽어 잠금 예산(횟수×대기+사이 대기 = 지금 28초) + 문장 제한 300초가 Job 제한 600초 안인지 확인하고, 넘거나 정책이 없으면 Job 을 만들지 않는다(무음 기본값 없음).
  - 종료 기록에 `attempts`(정수 0~100 만 읽음) 추가 — `MigrationLockFailed.sqlstate` 는 그대로 싣는다.
- 문서: `final_project_cs/wiki/operations/aws-main-cd.md` 의 `[2026-10-27 후보]` 줄과 I 보고서 §4 에 반영(같은 커밋).

## 3. 증거 위치(공개 저장소 밖, Hermes profile scratch)

- 격리 clone: `cache/scratch/eks-lock-fix-20261027`(branch `fix/eks-lock-policy-20261027`, `--shared` clone · sparse; 원본 작업 폴더의 index · HEAD · 작업 트리 변경 0. 원본에서는 `tools/safe_git.py fetch team` 만 실행).
- 증거: `cache/scratch/eks-lock-fix-ev/` — `red.log`/`red.xml`(5 실패, 이어 6번째 새 시험은 수정 전 `aws_cd.py` 로 따로 1 실패 확인), `green.xml`, `final.xml`(58/58), `noenv_unittest.log`, `ruff_full.log`, `patches/0001`(I cherry-pick) · `patches/0002`(수정), `hashes.txt`(aws_cd.py `9242e422…`, test `26e3e3a5…`).
- 시험용 설정은 CI 모양의 가짜 값이며 DB 주소는 닫힌 로컬 포트다(`env.sh`). 실제 Postgres · EKS · GitHub 실행은 하지 않았다.

## 4. 남은 일

1. **push 하지 않았다.** I 는 main 기반 별도 PR 대상이다(통합 K 결정). 부모가 `0001`+`0002` 를 최신 main/develop 흐름에 올릴지 정하고, 올릴 때 CI(main) · CI(web) · actionlint 를 다시 돌린다.
2. 실제 EKS 에서의 확인(첫 CD 의 migration Job 종료 기록 · timings)은 유효한 AWS 자격증명 또는 CD 실행 뒤에만 가능하다. 지금 자격증명은 무효 — 사용자가 x600 에 새 키/SSO 를 직접 설정해야 한다(채팅으로 받지 않는다).
3. 속도 후보 A·B 의 실측은 반영 뒤 채팅 접수가 생긴 다음 같은 SQL 로 다시 잰다.
4. 팀 `role-manager` 는 `ffb5fb1b5`(22:00 커밋)이고 x600 deploy.log 의 마지막 반영은 `93c7ba8ecf`(18:59) — `ffb5fb1b5` 반영 기록은 23:40 현재 없었다(이 작업 범위 밖, 부모 확인 필요).
