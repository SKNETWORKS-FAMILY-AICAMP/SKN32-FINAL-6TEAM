---
type: handoff
title: 새 PC 복원 안내 — 저장소에 올린 것·외장에만 있는 것 (2026-11-03 PC 이전)
description: 이 PC를 더 안 쓰기로 해 원본 C:/_proj/final_workspace 의 미커밋 문서·코드와 로컬 전용 커밋을 원격에 올렸다. 팀·개인 role-manager 에는 문서·도구만, 개인 A-COP 에는 backup/2026-11-03/* 브랜치로 원본 스냅숏과 로컬 전용 커밋 82개를 올렸다. 비밀·데이터셋·대용량은 외장 백업에서만 복원한다
status: active
domain: ops
impl_scope: 운영 기록. 원본 작업 폴더는 읽기만 했다(삭제·수정·checkout 0). 제품 코드 변경 0, role-manager 에 올린 것은 문서·도구뿐
---

# 새 PC 복원 안내 (2026-11-03)

사용자 지시(Telegram 11-03): 「백업은 알아서 해. 문서랑 복원가능하게 하고 커밋·푸시 최대한 하고 삭제하고 임시 자료 처리하고」. 이 PC 는 더 이상 쓰지 않는다.

## 1. 어디에 무엇이 있나

| 내용 | 위치 | 방법 | 비고 |
|---|---|---|---|
| 루트 `wiki/` 로컬 전용 문서(records/reports, handoff, decisions, governance, product, research, evaluation, architecture, business, delivery) 439개 + `wiki/index.md`·`log.md`·`handoff/index.md`·`AGENTS.md`·`CLAUDE.md`·`README.md`·`.gitignore` 로컬 추가분 | 팀 SKN `role-manager` · 개인 A-COP `role-manager` | 최신 role-manager 위 일반 커밋(3-way 합침, 충돌 구간은 원격본 유지 + 로컬에만 있던 줄 추가) | evidence·`_backup` 제외 |
| `final_project_cs/wiki/` 로컬 전용 문서 267개 + index/log 등 9개 문서 로컬 추가분 | 같은 두 role-manager | 같음 | evidence·`_backup` 제외 |
| `tools/disk_guard.py`·`disk_guard.json`·`guarded_clone.sh`·`tools/tests/test_disk_guard.py` | 같은 두 role-manager | 같음 | AGENTS.md「디스크 증가 예방」이 가리키는 도구 |
| 이 안내 문서 | 같은 두 role-manager | 같음 | |
| 원본 작업 폴더 스냅숏 전체(추적 파일 수정 117·삭제 4, 미추적 코드 321, 미추적 문서 3,950(evidence·_backup 포함), program/scripts·산출물양식 333, legacy·_backup 29,502) | 개인 A-COP `backup/2026-11-03/final-workspace-worktree` | 원본 HEAD `efeb873a8` 위 커밋 5개 | **role-manager 에 그대로 합치지 말 것**(1,102 커밋 뒤 기준) |
| 로컬 전용 커밋·후보(원본 로컬 브랜치 + 번들 보존본) 끝 커밋 81개 + 설명 작성기 r8 미커밋분 1개 | 개인 A-COP `backup/2026-11-03/{local,bundle}/…` 82개 | 각 끝 커밋 그대로 | 아래 표. 팀 SKN 에는 올리지 않았다 |
| 비밀(`.env`·`.env.apikeys`·`.env.local`·`.env.teamflow`·`*-private.json`·Hermes `.env`·auth) | 외장 백업에서만 | — | 저장소에 절대 올리지 않는다. 가능하면 새로 발급 |
| `datasets/` (약 34GB) | 외장 백업(원본 폴더 사본) | — | `.gitignore` 로 제외. 다시 받는 곳은 아래 4절 |
| Hermes 세션·state.db·세션 export | guguroute `backups/all-sessions-migration-20261103/` (외장으로 옮김) | — | [세션 이관 인계](2026-11-03_all-sessions-migration-backup-handoff.md). 비밀 원문 포함 → 암호화 보관 |
| guguroute `backups/` 나머지(번들·DB 보관본·pgdata 등) | 외장 백업 | — | 번들 head 는 위 backup 브랜치로도 올라가 있다 |
| 50MB 초과 3개: `program/scripts/plan_qa_bench/results/gpu_backlog_20261008/saluki_preservation_resume_hb0754_20261009/preservation_tail_hb0754.bin`(701MB), `…/gpu_management_20261009_1355/B_finch_seed13.tar.gz`(193MB), `…/B_finch_seed13/adapter_model.safetensors`(140MB) | 외장 백업 | — | GitHub 파일 한도 |
| `scratch/`(원본 루트), `.tmp/` | 올리지 않음 | — | 임시 사본. 정리는 scratch 삭제 작업 담당 |
| `final_project_cs/legacy/isolated_linux_checks/*_gates_inputs/` 중첩 Git 폴더 3개 | 외장 백업 | — | Git 안에 Git 을 담을 수 없음 |

### role-manager 에서 뺀 같은 이름 문서(원격본 유지, 로컬본은 backup 브랜치에만)

- 루트 7개: `wiki/handoff/2026-10-18_admin-trip-release.md`, `2026-10-18_qa-account-lifecycle.md`, `2026-10-29_st4f597-independent-review.md`, `2026-10-29_st4f728-guest-logout.md`, `wiki/records/reports/2026-10-18_guguroute-rename-exceptions.md`, `2026-10-18_intake-risk-trip-date.md`, `2026-10-29_bus-scalar-independent-continuation.md`
- `final_project_cs/wiki` 12개: records/reports 의 2026-10-13~10-29 문서 12개(목록은 backup 브랜치 커밋과 원본 비교로 재현 가능)
- 원본 `tools/local_data_guard.py` 도 원격본과 달라 role-manager 는 원격본을 유지했다.

### 보류(어디에도 올리지 않음)

| 항목 | 이유 |
|---|---|
| 원본 로컬 브랜치 `workspace`(끝 `52c7fcd56`, 원격 origin/workspace 보다 54 앞) | 고유 커밋에 `datasets/commerce/**` 106개 경로(실제 주문 페이지 `order_detail_real.html` 등 개인정보·데이터셋 규칙 위반)가 들어 있다. 브랜치로는 어디에도 올리지 않았다. **정정(18:3x)**: 처음 「외장 백업의 원본 `.git` 에만 있다」고 썼으나 틀렸다. 고유 커밋 54개(그중 `datasets/commerce` 를 건드리는 47개)는 개인 private A-COP 에 브랜치 없는 객체로 남아 있어 해시를 지정하면 받을 수 있다(`gh api repos/roroblack/A-COP/commits/<sha>` 54/54 조회, `git fetch origin 52c7fcd56…` 성공). A-COP `workspace` 브랜치에 08-18~08-29 push 한 뒤 09-14 force-push 로 되감긴 잔재이고, 11-03 푸시가 만든 것이 아니다. 팀 SKN 에는 0/54. GitHub 의 참조 없는 객체는 저장소 주인이 직접 지울 수 없고 GitHub Support 에 삭제를 요청해야 한다(결정은 사용자) |

## 2. 새 PC 에서 복원하는 순서

1. **저장소 받기**
   ```bash
   git clone https://github.com/roroblack/A-COP.git final_workspace
   cd final_workspace
   git remote add team https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM.git
   git fetch team
   git config core.longpaths true   # Windows: 긴 경로 파일이 있다
   git switch -c role-manager --track origin/role-manager   # 최신 작업 기준(문서·도구 포함)
   # 'git switch role-manager' 는 origin·team 두 원격에 같은 이름이 있어
   # "matched multiple (2) remote tracking branches" 로 실패한다(11-03 교차검증)
   ```
2. **원본 작업 폴더 상태가 필요할 때**(옛 미커밋 코드·evidence·legacy 등): 별도 폴더에서만 꺼낸다.
   ```bash
   git fetch origin 'refs/heads/backup/2026-11-03/*:refs/remotes/origin/backup/2026-11-03/*'
   git worktree add ../fw-snapshot origin/backup/2026-11-03/final-workspace-worktree
   ```
   이 스냅숏은 `efeb873a8` 기준이라 최신 role-manager 와 섞으면 안 된다. 필요한 파일만 골라 최신 위에서 다시 적용·시험한다.
3. **로컬 전용 후보 커밋**: 아래 표의 브랜치를 fetch 해 `git log`·`git diff <브랜치>~1 <브랜치>` 로 본다. 통합은 최신 role-manager 위 새 격리 사본에서 cherry-pick + 시험 후에만 한다(예: 513ab4cc·1ab3f0d88 은 [통합 적합성 보고](../records/reports/2026-11-02_hold3-513ab4cc-1ab3f0d88-integration-fit.md) 참고).
4. **외장 백업 복원**: 외장의 `C:/_proj/final_workspace` 사본에서 `datasets/`, 비밀 파일(`final_project_cs/.env`·`.env.apikeys`·`frontend/apps/web/.env.local`·루트 `.env.teamflow`), 50MB 초과 3개를 같은 상대 경로로 복사한다. guguroute `backups/` 는 새 PC 의 Hermes 프로필 아래로 옮긴다. 비밀은 가능하면 새로 발급해 넣는다(이 PC 폐기 전 교체 권장).
5. **Hermes 세션**: `backups/all-sessions-migration-20261103/MANIFEST.md` 절차대로 가져온다.
6. **확인**: `git log -1 role-manager`, `python tools/safe_git.py --self-test`, `python tools/disk_guard.py --help`.

## 3. 원격 브랜치 목록 (개인 A-COP 전용, backup/ 네임스페이스)

`backup/2026-11-03/final-workspace-worktree` 커밋 순서(원본 HEAD `efeb873a8` 위):

| 커밋 | 내용 |
|---|---|
| `2066eaeff` | 추적 파일 미커밋 변경(수정 117·삭제 4) |
| `970d5344e` | 미추적 코드·설정 321개 |
| `9f71d0758` | 미추적 문서 3,950개(wiki·evidence·docs·program 보고서) |
| `f30e2a17c` | program/scripts · 산출물양식 333개(50MB 초과 3개 제외) |
| `2a18a8c1c` | final_project_cs/legacy · 모든 `_backup` 29,502개 |

로컬 전용 끝 커밋 82개(+보류 1):

| 브랜치 | 끝 커밋 | 출처 | 상태 |
|---|---|---|---|
| `backup/2026-11-03/bundle/scratch-worktree-commits-20261029_teamflow-open-sw-010f9deeb` | `010f9deebc2a` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-worktree-commits-20261029/teamflow-open-sweep- | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/scratch-worktree-commits-20261028_speed-adjblank-2/speed-adjblank-20261028__tree-0955adb17` | `0955adb17699` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-worktree-commits-20261028/speed-adjblank-20261 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_clockfix-push-20261026-025217_rm-096a672a1` | `096a672a16dd` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/clockfix-push-20261026-025217/ | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_public-web-ddgs-20261026-053927_-0e04cf91c` | `0e04cf91c145` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/public-web-ddgs-20261026-05392 | 개인 origin 푸시 |
| `backup/2026-11-03/local/fix-web-sweep-20261027-10b537cdc` | `10b537cdc1e5` | 원본 로컬 브랜치 fix/web-sweep-20261027 | 개인 origin 푸시 |
| `backup/2026-11-03/local/scratch-c12-integ-20261028-129741ec3` | `129741ec3e95` | 원본 로컬 브랜치 scratch/c12-integ-20261028 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/proj-folder-retire-20261031_eks-independent-1029_f-1ab3f0d88` | `1ab3f0d882bc` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/proj-folder-retire-20261031/eks-independent-1029/follo | 개인 origin 푸시 |
| `backup/2026-11-03/local/scratch-eks-serving-20261027-1b38aa7ef` | `1b38aa7ef313` | 원본 로컬 브랜치 scratch/eks-serving-20261027 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/scratch-candidates-20261029d_scratch-candidates-un/tf106-web-checkout-master-1c286b697` | `1c286b697b85` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-candidates-20261029d/scratch-candidates-unpush | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/scratch-candidates-20261029d_scratch-candidates-un/sse-slot-head-20a9a2bdf` | `20a9a2bdf8f8` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-candidates-20261029d/scratch-candidates-unpush | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/scratch-worktree-commits-20261029_eks-verify-20261/release-eks-20261028-20e6c2d80` | `20e6c2d805a0` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-worktree-commits-20261029/eks-verify-20261028_ | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/scratch-worktree-commits-20261028_reldate-rm-20261/reldate-rm-20261028-0337__rm-254a0b1d4` | `254a0b1d4639` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-worktree-commits-20261028/reldate-rm-20261028- | 개인 origin 푸시 |
| `backup/2026-11-03/local/integ-K-allaudit-20261027-28ff40a0d` | `28ff40a0d5a8` | 원본 로컬 브랜치 integ/K-allaudit-20261027 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/C-__proj_final_workspace_.backup_2026-10-26_finals/29eecd500-29eecd500` | `29eecd5003e3` | 번들 C:/_proj/final_workspace/.backup/2026-10-26_finalspace_git.bundle (finalspace/29eecd500) | 개인 origin 푸시 |
| `backup/2026-11-03/local/fix-Q-review-revalidate-race-20261027-2c1ea3184` | `2c1ea3184c4e` | 원본 로컬 브랜치 fix/Q-review-revalidate-race-20261027 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_integ-rm10-20261026-1256_rm_unpu-322abf7b0` | `322abf7b03d6` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/integ-rm10-20261026-1256/rm/un | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_outdoor-diag-20261026-024352_dev/port-p0-l06-l01-on-fb291b33-34fd04252` | `34fd04252c64` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/outdoor-diag-20261026-024352/d | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/C-__proj_final_workspace_.tmp_git-history-backup_f/main-3622e403e` | `3622e403e78d` | 번들 C:/_proj/final_workspace/.tmp/git-history-backup/final_project_cs.bundle (heads/main) | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/C-__proj_final_workspace_.tmp_git-history-backup_f/main-36ef2dc7a` | `36ef2dc7aee8` | 번들 C:/_proj/final_workspace/.tmp/git-history-backup/final_project_sample.bundle (heads/main) | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_outdoor-diag-20261026-024352_dev/integ-merge-dev-0717-381c1b53d` | `381c1b53d0da` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/outdoor-diag-20261026-024352/d | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/C-__proj_final_workspace_.backup_2026-10-26_finals/382650d10-382650d10` | `382650d103a9` | 번들 C:/_proj/final_workspace/.backup/2026-10-26_finalspace_git.bundle (finalspace/382650d10) | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_outdoor-diag-20261026-024352_dev/stack-rm-allpast-u01-extras-20261026-on-da4ccd97-3b7ff2fc4` | `3b7ff2fc428d` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/outdoor-diag-20261026-024352/d | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_fix-chat-1221_rm_unpushed-466e8c563` | `466e8c563458` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/fix-chat-1221/rm/unpushed.bund | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_routing-p2-20261026-011814-21438/master-48613723a` | `48613723a62c` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/routing-p2-20261026-011814-214 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/explain-writer-wt-20261103_feat-schedule-explain-w/feat-schedule-explain-writer-20261029-4bc2d9080` | `4bc2d908005c` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/explain-writer-wt-20261103/feat-schedule-explain-write | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/scratch-worktree-commits-20261028_teamflow-J-20261/teamflow-J-20261027__rm__fix-teamflow-J-4cbfe2a01` | `4cbfe2a01bf4` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-worktree-commits-20261028/teamflow-J-20261027_ | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/scratch-worktree-commits-20261028_st4f-rm-20261028/st4f-rm-20261028-0336__rm-4f899ecd3` | `4f899ecd345d` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-worktree-commits-20261028/st4f-rm-20261028-033 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_outdoor-diag-20261026-024352_dev/port-writer-on-develop-52032f1dd` | `52032f1dda2d` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/outdoor-diag-20261026-024352/d | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/C-__proj_final_workspace_.backup_2026-10-26_finals/520d1b56e-520d1b56e` | `520d1b56e0a5` | 번들 C:/_proj/final_workspace/.backup/2026-10-26_finalspace_git.bundle (finalspace/520d1b56e) | 개인 origin 푸시 |
| `backup/2026-11-03/local/workspace-52c7fcd56` | `52c7fcd56137` | 원본 로컬 브랜치 workspace | 보류 — datasets/commerce 실제 주문 페이지 등 개인정보 포함(로컬 workspace 브랜치) |
| `backup/2026-11-03/bundle/_archive_20261027_integ-rm5-20261026-0700_rm_unpus-56414ab97` | `56414ab9703e` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/integ-rm5-20261026-0700/rm/unp | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_allpast-intake-gate-20261026-032-57ed39293` | `57ed39293746` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/allpast-intake-gate-20261026-0 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_fix-logkey-20261026-1221_rm_unpu-590c73920` | `590c73920726` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/fix-logkey-20261026-1221/rm/un | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_port-l05-20261026-080737_rm_unpu-601bb08ab` | `601bb08aba8c` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/port-l05-20261026-080737/rm/un | 개인 origin 푸시 |
| `backup/2026-11-03/local/integ-rebase-on-manager-a465c6022-20261026-60af7a7d2` | `60af7a7d296c` | 원본 로컬 브랜치 integ/rebase-on-manager-a465c6022-20261026 | 개인 origin 푸시 |
| `backup/2026-11-03/local/ci-M-hotel-e2e-20261026-64f6b52e3` | `64f6b52e3566` | 원본 로컬 브랜치 ci/M-hotel-e2e-20261026 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/disk-round7-20261030_st4f719-656579fe/fix-chat-card-complete-diff-20261029-656579fe3` | `656579fe37d6` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/disk-round7-20261030/st4f719-656579fe.bundle (heads/fi | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_port-l07-l02a-20261026-080756_rm-65b6bc99a` | `65b6bc99a144` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/port-l07-l02a-20261026-080756/ | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_fixture-clock-fix-20261026-0118-/master-66e5cf6c7` | `66e5cf6c7187` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/fixture-clock-fix-20261026-011 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_chat-stream-20261026-043045_v9_b/master-6fa08dc93` | `6fa08dc93bd4` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/chat-stream-20261026-043045/v9 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_web-v6-20261026-042515_tree_unpu/master-6fcffa86c` | `6fcffa86cde4` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/web-v6-20261026-042515/tree/un | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/scratch-worktree-commits-20261029_eks-verify-20261/v-main-72ba5ff48` | `72ba5ff4853f` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-worktree-commits-20261029/eks-verify-20261028_ | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/scratch-worktree-commits-20261028_plan-wait-copy-2/plan-wait-copy-20261028__tree-72c6a718f` | `72c6a718fa64` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-worktree-commits-20261028/plan-wait-copy-20261 | 개인 origin 푸시 |
| `backup/2026-11-03/local/fix-save-failure-paths-20261026-7f19fe4cd` | `7f19fe4cd054` | 원본 로컬 브랜치 fix/save-failure-paths-20261026 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_outdoor-diag-20261026-024352_dev/port-p0-l06-l01-on-af608588-90949d2e9` | `90949d2e9238` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/outdoor-diag-20261026-024352/d | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/C-__proj_final_workspace_.backup_2026-10-26_finals/988a7eda1-988a7eda1` | `988a7eda1547` | 번들 C:/_proj/final_workspace/.backup/2026-10-26_finalspace_git.bundle (finalspace/988a7eda1) | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_outdoor-diag-20261026-024352_dev-9a970b7df` | `9a970b7dfa3f` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/outdoor-diag-20261026-024352/d | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/scratch-worktree-commits-20261029_teamflow-105-202/tf105-candidates-a0ba3e50f` | `a0ba3e50ffa5` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-worktree-commits-20261029/teamflow-105-2026102 | 개인 origin 푸시 |
| `backup/2026-11-03/local/A-intake-audit-a0c677181` | `a0c6771813a2` | 원본 로컬 브랜치 A-intake-audit | 개인 origin 푸시 |
| `backup/2026-11-03/local/perf-serving-latency-20261027-a29e2d8eb` | `a29e2d8eb9ba` | 원본 로컬 브랜치 perf/serving-latency-20261027 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/scratch-worktree-commits-20261028_sse-rm-20261028-/sse-rm-20261028-0336__rm-a5197703c` | `a5197703c77d` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-worktree-commits-20261028/sse-rm-20261028-0336 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/C-__proj_final_workspace_.tmp_git-history-backup_f/public-ad3b137f3` | `ad3b137f384c` | 번들 C:/_proj/final_workspace/.tmp/git-history-backup/final_project_sample.bundle (heads/public) | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_bulk-shift-20261026-082127_rm_un-b45dd8d5b` | `b45dd8d5b8cc` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/bulk-shift-20261026-082127/rm/ | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_web-v6-20261026-042515_server_so/master-b470ad66b` | `b470ad66b21f` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/web-v6-20261026-042515/server_ | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_public-web-ddgs-20261026-053927_-b52ecb596` | `b52ecb596542` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/public-web-ddgs-20261026-05392 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_fix-intake-20261026-1221_rm_unpu-b8eaa672b` | `b8eaa672b212` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/fix-intake-20261026-1221/rm/un | 개인 origin 푸시 |
| `backup/2026-11-03/local/audit-chat-B-20261027-ba1a42860` | `ba1a42860cf1` | 원본 로컬 브랜치 audit/chat-B-20261027 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_fixture-clock-fix-20261026-0118-/master-bd4402357` | `bd4402357702` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/fixture-clock-fix-20261026-011 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_l03-default-on-20261026-0822_rm_-c59a4fff3` | `c59a4fff37d5` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/l03-default-on-20261026-0822/r | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_allpast-intake-gate-20261026-032-c75096106` | `c75096106d42` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/allpast-intake-gate-20261026-0 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_outdoor-diag-20261026-024352_dev/port-v7a-local-snapshot-c8287b9d9` | `c8287b9d984e` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/outdoor-diag-20261026-024352/d | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_routing-p2-20261026-011814-21438/master-cb3cecccb` | `cb3cecccbf23` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/routing-p2-20261026-011814-214 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/c400-peak-diff-20261103_head-cf8d97603-cf8d97603` | `cf8d976034b8` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/c400-peak-diff-20261103/head-cf8d97603.bundle (HEAD) | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_final_admin_non_db_integration_r/integration-final-admin-non-db-d0cc4f375` | `d0cc4f375bd5` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/final_admin_non_db_integration | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/proj-folder-retire-20261031_routingresume1029_git_/routing-resume-1029-d1b06357e` | `d1b06357e7c4` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/proj-folder-retire-20261031/routingresume1029/git/d1b0 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_public-web-ddgs-20261026-053927_-d9fd1ec54` | `d9fd1ec546f1` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/public-web-ddgs-20261026-05392 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/C-__proj_final_workspace_.backup_2026-10-26_finals/dcbbd5a91-dcbbd5a91` | `dcbbd5a9102e` | 번들 C:/_proj/final_workspace/.backup/2026-10-26_finalspace_git.bundle (finalspace/dcbbd5a91) | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/scratch-worktree-archive-20261029_fix5-20261026-12-debf1c37d` | `debf1c37d2d9` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-worktree-archive-20261029/fix5-20261026-1240_r | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/scratch-candidates-20261029d_scratch-candidates-un/tf106-w711-rm-head-e181f23d3` | `e181f23d3b6a` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-candidates-20261029d/scratch-candidates-unpush | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/C-__proj_final_workspace_.backup_2026-10-26_finals/e2d29b8b5-e2d29b8b5` | `e2d29b8b5051` | 번들 C:/_proj/final_workspace/.backup/2026-10-26_finalspace_git.bundle (finalspace/e2d29b8b5) | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/scratch-candidates-20261029d_scratch-candidates-un/st4f710b-fix-e6e754f27` | `e6e754f27f33` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-candidates-20261029d/scratch-candidates-unpush | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/hold3-integ-1102_hold3-local-branches/h3-rm-1ab3-p2-e8093b2a0` | `e8093b2a0a85` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/hold3-integ-1102/hold3-local-branches.bundle (heads/h3 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/c400-peak-diff-20261103_head-e96347fd7-e96347fd7` | `e96347fd7b22` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/c400-peak-diff-20261103/head-e96347fd7.bundle (HEAD) | 개인 origin 푸시 |
| `backup/2026-11-03/local/fix-ctrl-watch-audit-20261027-eaa649f40` | `eaa649f403f8` | 원본 로컬 브랜치 fix/ctrl-watch-audit-20261027 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/scratch-worktree-commits-20261028_speed-rm-2026102/speed-rm-20261028-0336__rm-ee766f4eb` | `ee766f4ebaa4` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-worktree-commits-20261028/speed-rm-20261028-03 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_fix-intake-20261026-1221_rm2_unp-efffc2684` | `efffc2684564` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/fix-intake-20261026-1221/rm2/u | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_fixture-clock-fix-20261026-0118-/master-f0c46b333` | `f0c46b3330f4` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/fixture-clock-fix-20261026-011 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_clockfix-push-20261026-025217_te-f506c4639` | `f506c4639a49` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/clockfix-push-20261026-025217/ | 개인 origin 푸시 |
| `backup/2026-11-03/local/fix-place-quality-20261027-f5edf4784` | `f5edf4784374` | 원본 로컬 브랜치 fix/place-quality-20261027 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_outdoor-diag2-20261026-033028_v8/master-fc08f54a6` | `fc08f54a6564` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/outdoor-diag2-20261026-033028/ | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_public-web-ddgs-20261026-053927_-fd1867e41` | `fd1867e41e57` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/public-web-ddgs-20261026-05392 | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/_archive_20261027_pubweb2-20261026-082147_rm_unpus-feb24fa90` | `feb24fa90332` | 번들 C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_archive_20261027/pubweb2-20261026-082147/rm/unp | 개인 origin 푸시 |
| `backup/2026-11-03/bundle/explain-writer-wt-20261103_r8-uncommitted-on-4bc2d9080-b2732cfe7` | `b2732cfe7440` | backups/explain-writer-wt-20261103 의 uncommitted-r8-tracked.patch + untracked 13개를 4bc2d9080 위에 커밋 | 개인 origin 푸시 |

번들 출처 경로는 이 PC 기준이다. 같은 번들 파일은 guguroute `backups/` 외장 사본에도 있다. 브랜치에 담긴 커밋 수: 고유 커밋 364개(원격 role-manager·develop·main 등 어떤 원격 브랜치에도 없던 것).

## 4. datasets 다시 받는 곳

`datasets/` 는 Git 에 없다. 외장 사본이 정본이며, 잃었을 때 다시 받는 곳(원본 `datasets/README.md` 「등록된 데이터셋」 요약):

| 경로 | 출처 |
|---|---|
| `safety/disaster_msg_*` | 행정안전부 긴급재난문자 API(DSSP-IF-00247) |
| `mobility/raw/subway_train_precision_*` | 서울교통공사·공공데이터포털 15098251 |
| `mobility/raw/live_web_golden_*` | 서울 열린데이터·TOPIS·AREX |
| `voc/naver_shopping_sentiment/` | github.com/bab2min/corpus `sentiment/naver_shopping.txt` |
| `mt/olist_reviews_mt_bench/` | Kaggle olistbr/brazilian-ecommerce |
| `voc/aihub_*` | AI Hub dataSetSn 71603 · 98 · 71844 · 102 (신청 필요) |
| `voc/data_go_kr_consumer_complaints/` | data.go.kr(공정거래위원회·한국소비자원) |
| `voc/ecmc_dispute_casebook_2024/` | usr.ecmc.or.kr |
| `voc/nikl_ne_2022/` | 국립국어원 모두의말뭉치(신청 승인 후 직접 다운로드) |
| `travel/activity_seoul_stores/` | 관광공사 TourAPI · 매장 공개 목록 |
| `travel/kto_contentlab_text/`, `travel/kto_content_lab_download/` | 한국관광콘텐츠랩(api.visitkorea.or.kr, 로그인 필요) |
| `travel/klue_wos/` | HF klue/klue (wos) |
| `travel/korea_places_multilingual/` | HF hjm1980/korea-places-multilingual |
| `travel/nemotron_personas_korea/` | HF nvidia/Nemotron-Personas-Korea |
| `travel/koculture_dialogues/` | HF huggingface-KREW/KoCulture-Dialogues |
| `travel/tourist_attractions_qa_seoul_gyeonggi/` | HF passionMan/ya_tourist_attractions_seoul_gyeonggi_by_scenario_1219 |
| 자체 생성(`travel/*bench*`, `*diagnostic*`, `plan_qa_bench` 등) | 다시 받을 곳 없음 → 외장 사본만 |
| `commerce/*` | 개인 주문 기록 — 다시 만들지 않는다(10-06 제거 결정) |

## 5. 시크릿 검사 방법 (푸시 전 실행, 값은 출력하지 않음)

- 대상: role-manager 에 올린 4개 커밋의 추가 줄 전부(4번째 = 이 안내 문서, 따로 검사), backup 스냅숏에 넣은 파일 34,224개 전체, 로컬 전용 커밋 364개의 추가 줄(333MB 패치)과 고유 blob 1,654개 전체.
- 규칙: 개인키 머리, AWS·GitHub·OpenAI·Anthropic·Google·Slack·Telegram 토큰 꼴, JWT, 접속 문자열 속 비밀번호, `serviceKey=`류 질의, `*key|secret|token|password* = "<20자 이상 고엔트로피>"`, 그리고 이 PC 의 `.env`·`.env.apikeys`·`.env.local`·`.env.teamflow`·Hermes `.env`·`*-private.json` 실제 값 29개와의 정확 일치.
- 결과: 실제 자격증명 0건. 검출은 모두 오탐(공개 Turnstile site key, 시험 이름 속 `PRIVATE KEY` 문자열, PyJWT 문서 예시, 127.0.0.1 시험 DB 접속 문자열, 시험 실행이 만든 resume_token, 원격에 이미 있는 Google Travel 페이지 토큰).
- 개인정보: 로컬 `workspace` 브랜치만 보류(위 표). 개인 A-COP 은 비공개 저장소, 팀 SKN 은 공개 저장소다.
- **팀 SKN 은 public 저장소다**(누구나 읽을 수 있다). 11-03 role-manager 4커밋의 727 파일(문서·도구)에는 비밀·개인정보가 0건이었다([교차검증](../records/reports/2026-11-03_backup-push-independent-crosscheck.md) 재검사). 다만 인프라 정보가 들어 있다: Windows 사용자 경로(`C:/Users/<사용자>/…`) 189 파일(409회), 사설 LAN IP 15 파일(23회), `사용자@IP` 6 파일(7회). 이전부터 팀 저장소에 같은 꼴이 있었다(`fab3da50a` 트리 사용자 경로 21 파일·사설 IP 9 파일). 현재 파일에서 빼도 이력에는 남고, 이력에서 지우려면 force-push 가 필요해 하지 않았다 — 결정은 사용자.

## 6. 원격 확인 (2026-11-03 17:18 KST, ls-remote · gh api)

- 팀 SKN `role-manager` = 개인 A-COP `role-manager` = `4c2f82a3b9236327e5515781d3a572ef94086e12` (fab3da50a 에서 빨리감기, 커밋 4개: 4fc6ded17 · 897532bde · ce789a6a1 · 4c2f82a3b). develop·main 은 손대지 않음(팀 3463b30c6·57f3d2f00, 개인 da35486cb·b0485d05f).
- 개인 A-COP `backup/2026-11-03/*` 83개 모두 기대 해시와 일치(스냅숏 끝 `2a18a8c1ce6fbe03ce6b466828d49e4a67e66de4`, r8 `b2732cfe74409c08ce4abfd3d00d881340919d68`). 팀 SKN 의 backup/2026-11-03 브랜치 0개. 보류 브랜치(workspace) 미푸시 확인.
- **후속(18:3x)**: 같은 날 정정 커밋이 `4c2f82a3b` 위에 일반 push 로 올라갔다(이 안내 문서의 switch 명령·보류 커밋 위치·커밋 수·팀 SKN 공개 정보 정정 포함). 최신 끝은 `git ls-remote origin refs/heads/role-manager` 로 확인한다.
- 이 절은 17:17 role-manager 커밋 뒤 원본 사본에 덧붙였고, 18:3x 정정 커밋으로 role-manager 에도 올라갔다.
