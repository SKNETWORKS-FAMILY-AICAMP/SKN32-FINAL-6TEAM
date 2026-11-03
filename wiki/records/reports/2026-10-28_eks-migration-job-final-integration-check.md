---
type: report
title: EKS 마이그레이션 Job 후보 ca879220b — 최신 main 기준 최종 통합 검증 · PR 후보
description: 팀 main e88e01925 위 4커밋(d83ec69b4 · aaebdacc3 · 0f584a2eb · ca879220b)을 최신 원격 기준으로 다시 확인. 격리 PG16 CI(main) 재현 전체 시험 · ruff · actionlint · 하드코딩 · 패치 왕복을 검증하고 PR 후보로 인계
status: draft
domain: travel
impl_scope: cs — .github/workflows/cd-aws.yml · ci-web.yml · final_project_cs/deploy/aws_cd.py · deploy/aws/migration-job.json · app/infrastructure/db/migrate.py (push 0 · PR 0 · 배포 0)
---

# EKS 마이그레이션 Job 후보 — 최종 통합 검증 · 2026-10-28

선행 문서: [2차 독립 검토](2026-10-28_eks-migration-deadline-independent-review-2.md) · [1차 독립 검토](2026-10-28_eks-lock-policy-independent-review-real-pg.md) · [수정 보고](2026-10-28_eks-migration-per-attempt-deadline-fix.md)

## 결론: PR 후보 준비 완료. push · PR · merge는 하지 않음

| 항목 | 결과 |
|---|---|
| 최신 원격 | 팀 `main` `e88e01925` · `develop` `36ba4c2fc` · `role-manager` `efc6fca47`. 10:31에 fetch하고 12:2x에 `ls-remote`로 다시 확인했으며 그사이 main은 움직이지 않음 |
| 기준 · rebase | 후보는 `e88e01925` 위 **4커밋**(`rev-list` 0/4, main이 조상)이라 **rebase할 필요가 없음**. 4커밋 모두 develop · role-manager에 없다. develop · role-manager에는 `aws_cd.py` · `cd-aws.yml`이 아예 없어서(main 전용 파일) 이후 develop→main 병합과 겹칠 일도 없음 |
| 바이트 | 2차 검토가 기록한 sha256 5개(`aws_cd.py` `f1e228d6…` · `migration-job.json` `63ec0f85…` · `migrate.py` `9be52358…` · 시험 2파일)와 **일치**. 따라서 그때 한 실제 PG 경합 시험 A~E가 이 바이트에도 그대로 적용됨 |
| 전체 시험(CI main 재현) | 격리 PG 16.15 + pgvector 0.8.6, 새 initdb `127.0.0.1:55511`. 가짜 값은 ci-main.yml과 같음. 순서도 같게 TZ 확인 → migrate → prompts → seed 모두 rc 0 → 아키텍처 **170/170** → 전체 `-n 8 --dist loadfile --ignore=tests/integration/rag`: **13,075 통과 · 실패 2 · 건너뜀 506 / 13,583 = 통과 96.3%**(분모에 건너뜀 포함), 1:20:13 |
| 실패 2건 | **변경과 무관한 시간 판정.** `test_intake_read_lock::…does_not_wait_for_a_write`(읽기 대기 < 2초)는 기준 main `e88e01925`에서 단독 3회 실행 시 **2/3 실패**, 후보는 1/3 실패. `test_trip_events::…signal_with_no_content`(`: ping`)는 8일꾼 부하에서만 실패했고, 단독에서는 후보·기준 모두 3/3 통과. 두 시험이 쓰는 경로는 후보 diff 9파일에 없음 |
| 변경 영역 시험 | `test_aws_cd` **52/52** · `test_migration_lock_policy` **24/24** · DB `test_migrations_rerun` **11/11** · `test_service_improvement` **12/12**(건너뜀 0) |
| 정적 검사 | ruff 0.16.8 통과. actionlint 1.7.12 windows_arm64 zip은 공식 checksums 파일로 확인했고, 그 파일의 linux_amd64 값이 ci-main.yml 고정값 `8aca8db9…`와 같다. `-shellcheck= -pyflakes=`로 cd-aws · ci-web · ci-main 검사 결과 0건. `git diff --check`는 CRLF 파일(`test_migration_lock_policy.py`, main에서도 CRLF) 줄 끝 82줄만 걸리고 `cr-at-eol` 기준 0 |
| 하드코딩 | 새로 추가된 값 가운데 600 · 2min · 120 · 120은 `deploy/aws/migration-job.json` 한 곳에 있고, 키·형식이 틀리면 클러스터 호출 전에 멈춘다. 그 밖의 숫자는 main에 원래 있던 값이다(gate 2400 · TTL 86400 · 자원 한도 · `role-duration-seconds` 3600은 기존 단계를 복제한 것). 나머지는 단위 변환(×1000)과 기록 정화 상한(attempts ≤ 100 · 정규식 길이)뿐이다. 계정 ID · ARN · 클러스터 이름 · 도메인은 0건이며, 비밀값은 모두 `secrets.*`로 읽는다. 보고서에 나오는 `ap-northeast-2`는 main 문서에 이미 있는 공개 리전 이름 |
| 패치 왕복 | `format-patch` 4개를 `e88e01925` 색인에 `apply --cached` → write-tree `faa8bd384…` = 후보 HEAD tree. bundle `verify` 통과 |

## 리뷰 소견 (막는 것은 아님)

1. **merge가 곧 운영 배포다.** `cd-aws.yml`은 main의 CI (main) 성공 `workflow_run`을 받아 실제 EKS · RDS에 반영한다. merge 시점과 첫 배포 관찰은 사람이 맡는다. 첫 실행의 `timings` · Job 종료 기록으로 판단값인 시도 2min · 시작 여유 120을 다시 본다.
2. `cd-aws.yml` job 하나의 최악 시간은 gate 40분(이론상 두 번) + 게시 + 배포인데 `timeout-minutes: 75`다. 보통은 CI (main) 성공 뒤에 시작하므로 `--main-only` gate가 바로 열려 여유가 있다. 다만 job 시간 초과가 DB 단계 도중에 닿으면 Job은 클러스터에서 계속 돌고, 다음 배포는 `require_clean_jobs`가 막는다(안전한 쪽).
3. 2차 검토 권고 두 건은 그대로 남아 있다. COMMIT에서 서버 오류(SQLSTATE 있음)가 나면 `failed_before_commit`으로 좁힐 수 있다(지금은 보수적으로 `commit_unknown`). `get_connection()`에 `connect_timeout`이 없다.
4. Docker 빌드 · CI (web) Playwright 8묶음은 로컬에서 돌리지 않았다(Docker 없음). 이 diff는 Dockerfile · requirements를 건드리지 않으므로 PR CI가 확인한다.

## 격리 · 안전

- AWS · EKS · RDS · x600 접속 0, push 0, 원본 작업 폴더에서는 `safe_git.py`로 fetch · ls-remote만 실행. 개인 origin `ls-remote`는 gh 자격 도우미 Permission denied로 확인하지 못했다(팀 원격만 확인).
- 전체 시험의 dining 통합 246건은 CI와 마찬가지로 기본 포트 5433에 접속을 시도하다 인증 단계(`no password supplied`)에서 끊겨 건너뛰었다. 세션은 열리지 않았고 쓰기도 0. 추가 확인으로 `DINING_PG_PORT=55511`(격리)을 넣어 다시 돌렸더니 248/249 통과했다. 남은 1건 `test_dining_agent_judge`(`trip_intakes` 표 없음)는 기준 main에서도 똑같이 실패하므로 원래 있던 시험 환경 결함이다.
- 시험 클러스터는 정지했다(`pg_ctl status` no server running, 55511 LISTEN 0). 다시 만들 수 있는 `pgdata` · pytest `tmp` · 기준 worktree는 지웠다.

## PR 후보 · 증거 (Hermes profile scratch `eks-final-20261028/`)

- 브랜치 `hotfix/eks-migration-deadline-20261028` = `ca879220b`(격리 clone `repo/`, base `main`). main 직접 PR의 선례는 #102 `hotfix/…`.
- `ev/PR_BODY.md` · `ev/patches/0001~0004-*.patch` · `ev/eks-migration-deadline.bundle`(sha256 `c4cde3e2…`) · `ev/hashes.txt`
- `ev/cand/`(0~5 단계 log · rc · `4_arch.xml` · `5_full.xml`) · `ev/cand_rerun` · `ev/base_rerun` · `ev/cand_dining` · `ev/base_dining` · `ev/ruff.log` · `ev/actionlint.log` · `ev/pg.log` · `ev/initdb.log` · `run_ci.sh` · `rerun.sh`

## 다음 일 (부모 · 사용자)

1. 팀 원격에 브랜치 push, main 대상 PR을 열고 CI (main) · CI (web) · CI (admin) 결과를 확인한다. push 직전 main이 `e88e01925`인지 다시 확인하고, 움직였다면 rebase한 뒤 같은 시험을 다시 돌린다.
2. merge는 사람이 승인한다(운영 배포가 시작됨). 첫 CD 결과(`aws-deploy-result.json` timings · Job 종료 기록)로 판단값 두 개를 다시 판단한다.

## 후속 주석 (2026-10-28 21:4x) — 이 문서의 「실패 2 · 건너뜀 506 · 원래 있던 시험 환경 결함」 판단은 낡았다

원인을 실측으로 다시 봤다. 두 실패와 dining `test_dining_agent_judge` 는 환경이 아니라 시험의 벽시계 창 · 갱신 안 된 대역이었고, 재검증 중 SSE 시험 3건 · 자료 기기 전용 이동 시험 1건이 더 드러났다. 시험만 고친 3커밋(`ee606a5ef` · `1826f5f42` · `1dbef9e6d`, 앱 0) 뒤 같은 CI 재현 전체 시험 **13,376 통과 · 실패 0 · 건너뜀 207 / 13,583**, 건너뜀 506 중 485 실제 실행 · 통과. → [원인 수정 · 건너뜀 해소 보고서](2026-10-28_eks-candidate-test-failures-root-cause-and-skips.md)
