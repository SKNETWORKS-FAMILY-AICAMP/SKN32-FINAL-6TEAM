---
type: report
title: C: 여유 공간 단위(GB/GiB) 정정 · guguroute scratch 작업 사본 정리
description: 과거 기록의 「301GB」「251GB」가 GiB 값이었음을 원자료로 확인해 정정하고, 끝난 worktree·clone 작업 사본 20개(논리 32.88GB)를 커밋 보존 확인 뒤 지워 C: 여유를 실측 +33.69GB 늘렸다
status: done
domain: travel
impl_scope: cs — 이 PC의 Hermes guguroute scratch 와 wiki 기록만 다룬다. 원본 작업 폴더 코드·Git·데이터셋 변경은 0이다
---

# C: 여유 공간 단위 정정 · guguroute scratch 정리 (2026-10-28 21:50–22:40)

사용자 승인 범위: 쓰지 않는 요소 삭제와 용량 지속 관리. 다른 세션의 소스·DB·증거·유일한 패치·worktree·backups 는 보존한다. 기본(default) 프로필과 `C:/Users/kcxsz/frog-npu-dev` 는 건드리지 않는다. 원본 `C:/_proj/final_workspace` 의 Git 에는 쓰지 않는다.

단위: **GB = 10^9 바이트, GiB = 2^30 바이트.** C: 전체 1,022,083,010,560 B(1022.1GB = 951.9GiB).

## 1. 단위 정정

| 원래 기록 | 시각 | 실제 단위 | GB 로 환산 | 근거 |
|---|---|---|---|---|
| 「C: 여유 301GB」 | 10-28 18:13 | **GiB**(`df -h` 「301G」) | **≈323GB** | 감사 `cache/scratch/disk-audit-20261028-2114/SUMMARY.md` |
| 「여유 251GB」 | 10-27 20:08 | **GiB** | **≈269.5GB** | `cache/scratch/_cleanup3b.py` 의 `free()` 가 `disk_usage().free / 2**30` 을 「GB」로 찍는다 |
| 「302.1GB」「316.1GB」 등 10-27 정리 로그 | 10-27 | GiB | ×1.0737 | 같은 스크립트 |
| 「436.6GB」 | 10-27 20:2x | **GB 가 맞다** | 436.6GB(= `df -h` 407G) | 같은 SUMMARY |
| 「246.1GB」 | 10-27 20:0x | 원자료 미확인 | — | 단위를 확정할 원 출력이 남아 있지 않다 |
| 「C: 301G 여유」 | 10-28 | GiB(`df -h`) | ≈323GB | [ST4F-710 보고서](2026-10-28_st4f710-same-day-checkout-stay-fix.md) 68행 |

- [Hi 감사 인계](../../handoff/2026-10-28_hi-telegram-session-audit.md) 47·48행은 현재 상태를 설명하는 인계 문서라서 본문을 고치고 `[정정]` 표시를 붙였다. 고치기 전 사본은 `wiki/handoff/_backup/2026-10-28_disk-unit-correction/` 에 있다.
- `2026-10-26_finalspace-migration-and-removal.md` 와 위 ST4F-710 보고서는 기록 문서라서 고치지 않았다. 이 표로 정정한다.
- 「301GB → 346GB 로 늘었다」는 비교(10-28 21:06 보고)도 단위가 섞인 것이다. 같은 단위로 보면 18:08 323GB → 21:05 346.1GB 이고, 18:55 사이에 +26GB 가 있었지만 그 원인은 기록되지 않았다.

## 2. scratch 정리

### 측정
- 시작 21:50 C: 여유 **341,078,249,472 B (341.08GB)**. 삭제 직전 22:29:52 **336,970,563,584 B (336.97GB)** — 다른 활성 작업이 40분 동안 약 4.1GB 를 더 썼다.
- 삭제 직후 22:32:30 **370,657,013,760 B (370.66GB)**. 삭제로 실제 **+33,686,450,176 B (+33.69GB)** 늘었다. 지운 파일의 논리 크기 합은 32,882,384,528 B(32.88GB), 파일 수는 382,038개다.
- 조사 당시 scratch 전체는 152.13GB(786 항목)였다. 재생성 가능한 캐시(`node_modules` 0.84 · `__pycache__` 0.25 · `venv` 0.25 · `.cache` 0.08 · `.next` 0.09GB)는 합쳐서 약 1.5GB 에 그쳤다. 대부분은 작업 사본(worktree·clone)이었다.

### 지운 것 — 작업 사본 20개(체크아웃 폴더만)
조건 6가지를 모두 만족한 것만 지웠다.
1. 작업 트리가 깨끗하다: `git status --porcelain --untracked-files=all` 이 0줄이다. 무시된 파일은 `.ruff_cache`·`__pycache__`·빈 `datasets/dining/processed/_build/` 뿐이었다.
2. 6시간 넘게 파일 변경이 없다(삭제 직전에 다시 확인했다).
3. 이 폴더를 쓰는 프로세스가 없다(Win32_Process 전체 명령줄 검사).
4. 진행 중인 R·S 알림(`_coord`)에서 쓰는 트리가 아니다.
5. 다른 저장소의 `objects/info/alternates` 가 이 폴더를 가리키지 않는다(32개 파일 검사).
6. HEAD 커밋이 아래 둘 중 하나로 보존된다.

- **팀 원격(SKN32-FINAL-6TEAM)에 이미 있는 HEAD — 10개**: `fix-queue-circuit-20261028-0717/{base,rm}` · `fix-refusal-wording-20261028-0756/rm` · `fix-timemove-20261028-0554/rm` · `fix-warning-wording-20261028-0843/rm` · `integ-rm13-20261027-2006/rm` · `sse-rm-20261028-0336/base` · `st4f631-review-20261028/wt` · `integ-c12-wait-20261028` · `combined-codex-c1-20261027/repo`. 원격 포함 여부는 21:27 에 갱신된 `eks-release-20261028/repo` 의 `team/*` 기준으로 판정했다.
- **원격에 없는 HEAD — 10개, bundle 로 보존한 뒤 삭제**: `reldate-rm-20261028-0337/rm` `254a0b1d4` · `speed-adjblank-20261028/tree` `0955adb17` · `speed-real-20261028/tree` `06b75e491` · `speed-rm-20261028-0336/rm` `ee766f4eb` · `sse-rm-20261028-0336/rm` `a5197703c` · `st4f-rm-20261028-0336/rm` `4f899ecd3` · `plan-wait-copy-20261028/tree` `72c6a718f` · `c12-integ-20261028` `129741ec3`(원본 브랜치 `scratch/c12-integ-20261028` 에도 있다) · `routing-p1-choose-20261027` `7f670774f` · `teamflow-J-20261027/rm` 브랜치 `fix/teamflow-J-20261027` `4cbfe2a01`.
  - bundle 은 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-worktree-commits-20261028/` 에 10개 있다. scratch 처럼 자동으로 지워지는 곳이 아니다. 각 bundle 은 팀 develop·role-manager·main·release 를 뺀 커밋만 담고 있다(1~4커밋, 4.6~41KB). `bundle verify` 10/10 통과, 담긴 HEAD 가 원래 HEAD 와 10/10 일치한다. sha256 은 `cache/scratch/disk-cleanup-20261028-2150/bundles.sha256` 에 있다.
  - bundle 은 원본 Git 에 쓰지 않고 만들었다. 새 bare 저장소(alternates 는 eks-release clone)로 해당 커밋만 fetch 해서 만들었다.
- 각 작업 폴더의 증거(`ev/` · `out/` · `db/` · `pgdata/` · 스크립트 · `rm-base` 등)는 지우지 않았다. 지운 것은 체크아웃 하위 폴더 하나뿐이다. 최상위 자체가 worktree 였던 3개(`c12-integ` · `integ-c12-wait` · `routing-p1-choose`)는 추적되지 않은 파일이 0개였다.
- 지운 파일 하나하나의 크기와 경로는 `cache/scratch/disk-cleanup-20261028-2150/manifest_deleted.tsv`(382,058줄)에 있다. 삭제 뒤 대상 20/20 이 없는 것을 확인했다.
- 지운 worktree 의 등록 정보(`.git/worktrees/<이름>`)는 각 허브 저장소(`allpast-hotfix-20261025-2005/repo`, 원본 `C:/_proj/final_workspace`)에 「prunable」로 남겨 두었다. 원본 Git 에 쓰지 않기 위해서다. 등록이 남아 있는 동안은 원본 객체 저장소에도 그 HEAD 가 살아 있다.

### 남긴 것과 이유(큰 것 위주, 논리 GB)
- 수정이 커밋되지 않은 트리: `modelq-G-20261027/rm`(변경 109) · `fix5-20261026-1240/rm` · `integ-merge-dev-20261026-0717/rm` · `integ-mgr-a465c6022-20261026` · `mgr-merge-20261026-0045` · `past-edit-delete-only-20261026` · `port-develop-20261026-011444-95683888/wt` · `c1-notice-e2e-20261027/wt` · `reldate-rm-20261028-0337/rm-base`. 고유한 미커밋 작업일 수 있다.
- 원격에 없는 기록 커밋 4개를 담은 트리: `ctrl-audit-20261027`(C `eaa649f40`) · `integ-K-allaudit-20261027`(K `28ff40a0d`) · `integ-Q-20261027`(Q `2c1ea3184`) · `place-quality-20261027`(E `f5edf4784`). Hi 감사에서 보존 대상으로 지목한 것들이다. `serving-latency-20261027` 에는 `.env` 가 있다.
- 실행 중이거나 진행 중인 것: `allpast-hotfix-20261025-2005`(9.54, 허브 저장소, 0.3시간 전 사용) · `routing-open-20261028` · `teamflow-open-sweep-20261028` · `sse-final-20261028` · `st4f710*` · `eks-*` · `ops-jobs-20261026-054158` · 서비스가 쓰는 `api-runtime-20261025-014236` · `date_risk_python_01` · `cs-web-response-status` · `public-web-binding-v5-*` · `web-v5-release-*` · `candidate-review-fix-*` · `integ-v10c-ctx-*`.
- 10-27 정리에서 보존하기로 판정한 옛 사본(git 오류, bundle 실패 또는 500MB 초과): `remaining_dod_validation` 9.61 · `remaining_shared_implementation` 6.26 · `booking_admin_off_v2` 4.68 · `fixture-clock-fix-*` 3.75 · `final_integration_preparation` 3.75 · `latest-serving-6c345-20261025` 3.32 · `remaining_local_review` 3.23 · `customer_hours_*` 4개 7.2 · `local_admin_3300_v2` 2.65 · `date_risk_*`. 이번에 다시 판정하지 않았다.
- `_archive_20261027`(9.67, 10-27 bundle·patch)와 `finalspace_preservation`(1.82)은 보존물이다.

## 3. 남은 위험 · 할 일
- **`_archive_20261027` 은 scratch 안에 있다.** Hermes 는 scratch 에서 24시간 동안 쓰이지 않은 항목을 지운다. 10-27 에 보존한 bundle·patch 9.67GB 가 자동으로 지워질 수 있으니, 담당자가 `backups/` 같은 영구 위치로 옮길지 정해야 한다. 이번에는 옮기지 않았다.
- 정리 뒤에도 활성 작업 때문에 C: 여유가 계속 줄어든다(이번 측정에서 40분에 약 4GB). 작업 사본 하나가 1.6~3.3GB 다. 정리 요청을 `cache/scratch/_coord/disk-hygiene-NOTICE.md` 에 남겼다. 각 작업자는 인계할 때 자기 사본 정리 결과를 보고해야 한다. 아직 실제로 정리했다고 보고한 작업자는 0명이다.
- 기본 프로필 scratch(64.7GB, 그중 10-27 이후 생성 27.7GB)와 `frog-npu-dev`(11.8GB)는 다른 세션 소유라서 손대지 않았다.
