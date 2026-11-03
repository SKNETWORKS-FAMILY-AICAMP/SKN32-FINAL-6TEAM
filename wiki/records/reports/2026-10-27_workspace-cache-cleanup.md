# 2026-10-27 작업 폴더 캐시·빌드 산출물 정리

사용자 지시(2026-10-27): 프로젝트 전체에서 불필요한 것 정리. 단, 다른 세션의 백업 분석 때문에 `scratch`·`.backup`은 보존하고, 외부 서비스와 프로세스는 끄지 않으며, git이 추적하는 파일과 비밀 파일도 보존한다. 재생성할 수 있어도 지금 쓰는 것은 건드리지 않는다.

## 결론

- **삭제: 파일 13,909개, 1,879,904,172바이트(1.88GB / 1.75GiB), 오류 0건.** 대상은 경로를 정확히 적은 허용 목록 32개 폴더와 `__pycache__` 764곳의 `*.pyc`다. 삭제 직후 확인에서 매니페스트 13,909개 중 남은 파일은 0개, 허용 목록 폴더 중 남은 것도 0개였다.
- C: 여유 공간은 403,961,397,248바이트에서 405,849,866,240바이트로 늘었다(+1,888,468,992). 다른 세션도 같은 디스크에 쓰고 있어서 이 차이가 전부 이번 삭제분은 아니다.
- 정리 뒤 작업 폴더 크기는 **약 51.80GB(파일 580,100개)**다. 폴더별 `du -sb` 결과(.git 포함)와 루트 파일 13개(110KB)를 더한 값이다. 정리 전 크기는 이 값에 삭제분을 더한 **약 53.68GB(약 594,009개)**로 추정했다. 스캔이 세션들의 쓰기와 동시에 돌았으므로 근사값이다.

## 확인한 것(삭제 전)

| 확인 | 결과 |
|---|---|
| git 추적 | 32개 폴더와 `*.pyc` 모두 추적 0건(`git ls-files`, `final_project_sample`은 자체 저장소에서 확인). `web/.vitest`는 추적 파일 1개가 있어 **제외**했다 |
| ignore 규칙 | 32개 폴더 모두 `check-ignore`로 해당하는 규칙을 확인했다(`.next*/`, `.next/`, `.pytest_cache/`, `.ruff_cache/`, `frontend/.gitignore:14` 등) |
| 사용 중 여부 | 실행 중인 node/python/postgres 프로세스는 모두 Hermes scratch 사본에서 돈다. 작업 폴더의 `.next*`를 쓰는 프로세스는 0개였다. `ops-jobs` 런처가 읽는 것은 `final_project_cs/.env*`와 `datasets/mobility/processed`뿐이고, 둘 다 건드리지 않았다 |
| 최근 쓰기 | 대상 안에서 최근 120분 사이에 수정된 파일 0개 |
| 링크·reparse | 심볼릭 링크 0개, NTFS reparse point 0개 |
| 재생성 방법 | `.next*`는 `next.config.ts`의 `distDir`(`NEXT_DIST_DIR`)가 빌드하거나 dev 서버를 띄울 때 다시 만든다(`tests/live/serve.mjs`는 `BUILD_ID`가 없으면 빌드한다. `lan_serve.ps1`과 `triPilot-실행.bat`는 `next dev`로 띄운다). 캐시와 `*.pyc`는 실행할 때 자동으로 생긴다 |

## 삭제 내역

| 경로(작업 폴더 기준) | 파일 | 바이트 |
|---|---:|---:|
| `final_project_cs/frontend/apps/admin/.next` | 178 | 201,241,545 |
| `final_project_cs/frontend/apps/admin/.next-api-limits-1009` | 107 | 128,280,227 |
| `final_project_cs/frontend/apps/admin/.next-demo-verification` | 104 | 119,598,754 |
| `final_project_cs/frontend/apps/admin/.next-unconfigured` | 140 | 43,494,411 |
| `final_project_cs/frontend/apps/admin/.next-watch-limits-1009` | 104 | 123,490,241 |
| `final_project_cs/frontend/apps/admin/.next-watch-monitoring-1009` | 106 | 122,382,311 |
| `final_project_cs/frontend/apps/admin/.next-watch-simulation-1009` | 104 | 121,054,611 |
| `final_project_cs/frontend/apps/web/.next` | 2,576 | 457,710,322 |
| `final_project_cs/frontend/apps/web/.next-chat-context-20261011` | 425 | 15,782,870 |
| `final_project_cs/frontend/apps/web/.next-consent-progress` | 424 | 15,795,618 |
| `final_project_cs/frontend/apps/web/.next-integration-support-0619` | 427 | 15,922,009 |
| `final_project_cs/frontend/apps/web/.next-lan` | 318 | 140,301,825 |
| `final_project_cs/frontend/apps/web/.next-live` | 513 | 120,269,889 |
| `final_project_cs/frontend/apps/web/.next-live-hours` | 454 | 82,797,063 |
| `final_project_cs/frontend/apps/web/.next-live-improvement-20261010` | 426 | 16,210,882 |
| `final_project_cs/frontend/apps/web/.next-operations-20261012` | 427 | 15,918,186 |
| `final_project_cs/frontend/apps/web/.next-taxi-20261012` | 427 | 15,917,850 |
| `final_project_cs/frontend/apps/web/.next-taxi-20261012-v4` | 427 | 15,919,517 |
| `final_project_cs/frontend/apps/web/.next-uiux-after` | 418 | 15,923,448 |
| `final_project_cs/frontend/apps/web/.next-uiux-before` | 415 | 15,737,964 |
| `.pytest_cache` | 5 | 52,862 |
| `.ruff_cache` | 889 | 1,344,282 |
| `acop_dojo/.pytest_cache` | 4 | 542 |
| `final_project_cs/.pytest_cache` | 5 | 1,060,892 |
| `final_project_cs/.ruff_cache` | 4 | 574 |
| `final_project_cs/legacy/deployment_candidates/2026-10-11_2203_plugin_v2/.pytest_cache` | 5 | 23,700 |
| `final_project_cs/legacy/deployment_candidates/2026-10-11_2204_plugin_v1/.pytest_cache` | 5 | 16,264 |
| `final_project_cs/legacy/deployment_candidates/2026-10-11_2206_plugin_v3/.pytest_cache` | 5 | 17,051 |
| `final_project_cs/legacy/deployment_candidates/2026-10-11_221806_plugin_v4/.pytest_cache` | 5 | 39,071 |
| `final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/.pytest_cache` | 4 | 40,947 |
| `final_project_sample/.pytest_cache` | 5 | 92,265 |
| `final_project_ui/.pytest_cache` | 5 | 15,222 |
| `__pycache__/*.pyc (764 dirs)` | 4,448 | 73,450,957 |
| **합계** | **13,909** | **1,879,904,172** |

`__pycache__`는 `.git`·`.backup`·`scratch`·`.tmp`·`datasets`·`.experiments`·`.acop_dojo`·`output`, 그리고 경로에 `_backup`·`.tmp`·`records`·`evidence`·`results`가 들어간 곳을 제외한 764곳에서 `*.pyc`만 지웠다. 빈 폴더가 된 곳은 `rmdir`로 없앴다. 이 때문에 `tests/`는 원래 `__pycache__`만 들어 있었고 추적 파일도 0개라서 빈 폴더로 남았다.

## 남은 것(일부러 남김)

| 대상 | 크기 | 남긴 이유 |
|---|---:|---|
| `final_project_cs/tests/unit/travel/mobility/__pycache__/*.pyc.27300` 2개 | 작음 | pytest가 원자적 쓰기를 하다 남긴 임시 파일이다. `*.pyc`가 아니어서 허용 목록 밖으로 두었다 |
| `final_project_cs/frontend/apps/web/node_modules` | 589MB | 의존성 설치본이고 `triPilot-실행.bat`·`lan_serve.ps1`이 실행할 때 쓴다(캐시나 빌드 산출물이 아니다) |
| `final_project_cs/frontend/apps/web/.tmp` | 354MB, 6,102개 | 캡처 결과·로그가 들어 있어 증거 성격이다 |
| `*/test-results`, `.pytest-tmp`, `final_project_sample/{build,dist}` | 1MB 미만 | 효과가 작고 실행·설치 증거일 수 있다 |
| `program/research/.../.cache`, `program/scripts/plan_qa_bench/results/.../.ruff_cache` | 작음 | 연구·벤치 결과 폴더 안에 있다 |
| `.tmp`(5.60GB, 189,274개), `.backup`(471MB), `scratch`(563MB), `datasets`(34.07GB) | — | 진행 중인 작업, 백업, 데이터라서 삭제 금지 대상이다 |
| `.git` | 1.49GB | git 저장소 |

## 정리 전 폴더별 크기(폴더별 `du -sb`, 바이트·파일 수)

datasets 34,071,056,618 / 255,935 · program 6,429,324,597 / 28,855 · .tmp 5,596,286,490 / 189,274 · final_project_cs 2,722,004,487 / 80,472(정리 뒤 측정값) · .git 1,489,808,561 / 3,002 · scratch 562,423,313 / 16,800 · .backup 471,486,683 / 642 · team_branch 244,034,671 / 288 · final_project_sample 115,995,158 / 1,963 · wiki 39,450,166 / 1,121 · .acop_dojo 23,131,750 / 744 · output 22,092,853 / 4 · .experiments 6,691,984 / 662 · 나머지는 각각 2MB 미만.

## 작업 기록 위치

허용 목록, 삭제 전 매니페스트(크기와 경로, 13,909행), 통계와 스캔 원본은 Hermes scratch의 `fw-cleanup-20261027/`(`allow_dirs.txt`, `manifest_before.tsv`, `cand_stats.tsv`, `pycache_ok.txt`, `top_scan.txt`)에 있다. scratch는 24시간이 지나면 정리될 수 있다.

커밋과 push는 하지 않았다. 바꾼 것은 이 보고서, 인계 문서, 인계 목차 1줄이다.

## 추가 정리: `.tmp` 전수 조사(2026-10-27 2차)

사용자 지시: `.tmp` 5.6GB를 전수 조사해 진행 중인 작업과 고유 내용은 보존하고, 검증된 재생성 가능 항목만 지운다.

### 결론

| | 파일 수 | 바이트 |
|---|---:|---:|
| 정리 전 `.tmp` | 189,274 | 5,596,286,490 (5.60GB) |
| 삭제 | 83,609 | 1,598,725,072 (1.60GB) |
| 정리 후 `.tmp` | 105,665 | 3,997,561,418 (4.00GB) |

- 오류 0건. 매니페스트 83,609개 중 남은 파일 0개. 정리 전후 최상위 항목 955개를 하나씩 대조했다. 각 항목의 차이가 매니페스트 합계와 정확히 같았고(불일치 0), 삭제 대상이 없는 항목은 최신 수정 시각도 바뀌지 않았다. 최상위 `.tmp/__pycache__`(14개, 338KB)만 비어서 없어졌다.
- C: 여유 공간은 430,207,401,984에서 431,801,368,576바이트로 늘었다(+1,593,966,592). 다른 세션도 쓰고 있어서 근사값이다.

### 지운 것

| 종류 | 위치 수 | 파일 | 바이트 | 재생성 근거 |
|---|---:|---:|---:|---|
| `node_modules` | 3 | 80,471 | 1,534,027,664 | 옆에 `package.json`·`package-lock.json`이 남아 있다. `postinstall`·`patch-package`·`file:` 의존성은 없다. 현재 작업 폴더에도 설치본이 있다 |
| `.next` | 1 | 127 | 6,701,435 | `full-release-20261008/release/.../apps/admin` 빌드 출력이다 |
| `__pycache__/*.pyc` | 434 | 2,923 | 57,804,243 | 같은 이름의 `.py` 원본이 있는 `.pyc`만 지웠다 |
| `.ruff_cache` | 3 | 88 | 191,730 | 린터 캐시 |

`node_modules` 3곳은 `full-release-20261008/release/final_project_cs/frontend/apps/{web,admin}`과 `manager_recovery_20261012/recovery-candidate/final_project_cs/frontend/apps/web`이다. `recovery-candidate` 저장소에서는 `node_modules/`가 `apps/web/.gitignore:1` 규칙으로 무시되고, 추적 파일도 0개다. 저장소 `.git`과 HEAD(`12f81c66a`)는 그대로다.

### 삭제 전 확인

- `.tmp`는 루트 `.gitignore:12`(`.tmp/`)로 무시되고, 루트 저장소가 추적하는 파일은 0개다. 안쪽 저장소와 worktree 9곳에서도 지울 패턴의 추적 파일은 0개였다.
- reparse point와 심볼릭 링크 0개, 읽기 오류 0건. 마지막 수정은 10-13(`node_modules`·캐시)이고 `.tmp` 전체의 최신 수정은 10-24다. 최근 48시간 사이에 수정된 최상위 항목은 0개다.
- 명령줄이나 실행 파일 경로에 `final_workspace`가 들어간 프로세스는 다른 세션의 셸뿐이었다. `.tmp`를 쓰는 프로세스는 0개였다. 프로세스와 서비스는 하나도 멈추지 않았다.
- Hermes scratch 런처, `final_project_cs`·`scripts`·`tools`·wiki에서 삭제한 `node_modules` 경로를 가리키는 곳은 0곳이었다.
- 삭제 직전에 폴더마다 파일 수와 바이트를 인벤토리와 다시 비교했고, 2시간 이내에 쓴 파일이 있으면 제외하도록 했다. 해당한 경우는 0건이었다.

### 일부러 남긴 것(근거)

| 대상 | 이유 |
|---|---|
| 안쪽 저장소·worktree: `full-release-20261008/{release,baseline}`, `baseline-manager-20261012/team`, `wt_dev`, `mobility-develop-20261008`(옛 PC `C:/Users/playdata2/...` worktree를 가리키는 고아 worktree), `manager_recovery_20261012/{recovery-candidate,manager-snapshot}`, `claude_followup_20261012/workspace`, `uiux-handoff-*/base` | 커밋하지 않은 변경이나 병합하지 않은 코드가 있을 수 있다(`recovery-candidate`의 `status`에서 삭제 표시가 대량으로 나온다). 통합 검토가 끝나기 전에는 고유 내용으로 본다 |
| `.pytest_cache` 5곳(689KB), `uiux-visual-20261012-v1/.next`(11개, 거의 0바이트) | 재실행 결과(`lastfailed`)와 검증 증거 폴더 안에 있다. 얻는 공간도 작다 |
| 원본 `.py`가 없는 `.pyc` 25개 | 원본이 없으면 그 `.pyc`가 유일한 사본일 수 있다 |
| `verification_pg_20261012_v3`(154MB, PostgreSQL 데이터 폴더) | `postmaster.pid`가 없어 실행 중은 아니다. 검증 DB 스냅샷이므로 증거로 남겼다 |
| 캡처·로그·zip·webm·jsonl(`ci54`, `uiux-*`, `map-*`, `e2_rebuild_*` 등)과 `.py`·`.json` 스크립트 수백 개 | 검증 증거와 세션 작업물이다. `e2_rebuild_*` 3곳의 `reference_audit.json`은 해시가 같지만, 폴더 구성을 보존하려고 남겼다 |
| `pytest-of-*`/`test_repo_root_ignores_*` 임시 폴더 | 테스트 실행 산출물로 증거 폴더 안에 있고, 크기도 작다 |

남은 `.tmp` 4.00GB 가운데 가장 큰 것은 `manager_recovery_20261012`(853MB), `full-release-20261008`(701MB), `location-controls-20261011`(315MB)이다. 더 줄이려면 안쪽 worktree를 `readonly-candidate-reclassification`으로 대조해 병합 여부를 확정해야 한다.

### 기록 위치

Hermes scratch의 `tmp-audit-20261027/`에 있다. 인벤토리(`before.json`, `after.json`), 후보 목록(`cands.json`, `cands_after.json`), 삭제 매니페스트(`manifest_apply.tsv`, 83,609행), 보류 목록(`held_apply.tsv`, 31행), 여유 공간(`free_*.txt`), 스크립트(`inventory.py`, `candidates.py`, `purge.py`)가 들어 있다. scratch는 24시간 뒤에 정리될 수 있다. opencode 보조 검토는 `opencode models`가 `EPERM uv_spawn 'git'`으로 실패해서 쓰지 않았다.

## 추가 정리: `.tmp` 안쪽 worktree·저장소 대조(2026-10-27 3차)

사용자 지시: `.tmp`에 남은 오래된 worktree와 안쪽 저장소를 현재 팀 코드·작업 폴더와 대조해 보존·통합·중복으로 나누고, 재생성 사본이라는 것이 증명된 것만 정리한다. 불명확한 작업물은 남긴다. (`readonly-candidate-reclassification` 절차를 따랐다.)

### 결론

| | 파일 수 | 바이트 |
|---|---:|---:|
| 정리 전 `.tmp` | 105,665 | 3,997,561,418 (4.00GB) |
| 삭제 | 16,094 | 989,108,948 (0.99GB) |
| 안내 파일 추가 | 3 | 1,952 |
| 정리 후 `.tmp` | 89,574 | 3,008,454,422 (3.01GB) |

- 삭제 계획 12,573개 중 지운 것 12,573개, 보류 0건, 오류 0건. 지우기 직전에 파일마다 크기·수정 시각·blob 해시를 다시 확인했다. 그 밖에 `manager-snapshot/.git`(3,521개, 76,920,365B)를 지웠다.
- 정리 전 측정값은 2차 정리 후 값(105,665개, 3,997,561,418B)과 정확히 같았다. 그 사이에 바뀐 것이 없었다.
- 최상위 954개 항목을 전후로 대조했다. 바뀐 항목은 4개(`full-release-20261008`, `mobility-develop-20261008`, `manager_recovery_20261012`, `baseline-manager-20261012`)뿐이고, 각 차이는 삭제 목록 합계와 같다.
- C: 여유 공간은 430,483,193,856B에서 431,500,128,256B로 늘었다(+1,016,934,400). 다른 세션도 쓰고 있어서 근사값이다.
- 루트 저장소의 `git status --porcelain` 1,163행은 정리 전후 바이트 단위로 같았다. `.tmp`를 추적하는 파일은 0개다(`.gitignore:12`). 인덱스·HEAD·ref·원격은 바꾸지 않았고, fetch·커밋·push도 하지 않았다. 프로세스와 서비스는 멈추지 않았다.

### 대조 방법

- 기준: 루트 저장소에서 `git rev-list --objects --all`로 도달할 수 있는 객체 72,357개. 원격 추적 ref는 `team/develop` `36ba4c2fc`(`ls-remote` 값과 같음)와 `origin/develop` `da35486cb`다. `team/role-manager`는 원격 `ffb5fb1b5`, 로컬 `93c7ba8ec`로 로컬이 뒤처져 있다. 로컬에 없는 객체는 '없음'으로 셌으므로 이 차이는 보존하는 쪽으로만 작용한다.
- 후보 14곳의 파일 35,596개는 확장 경로(`\\?\`)로 읽었다. 파일마다 원본 바이트와 CRLF→LF 변환본의 git blob 해시를 구했다. 그다음 10-05~10-13 커밋 542개의 트리 전체와 경로·blob을 대조해, 후보마다 가장 가까운 커밋을 찾았다.
- 삭제 기준은 세 가지를 모두 만족하는 것이다. (1) 추적 파일 전부가 한 커밋과 같은 경로·같은 내용이다. (2) 그 커밋이 공개 원격(`origin/develop`, `team/develop` 등)에 들어 있다. (3) wiki·스크립트가 현재 의존하지 않는다. 남는 파일 중 원본이 없을 수 있는 것은 제자리에 둔다.

### 지운 것(재생성이 증명된 사본)

| 대상 | 지운 파일 | 바이트 | 근거 | 되살리는 법 |
|---|---:|---:|---|---|
| `full-release-20261008/baseline`(옛 PC 고아 worktree) | 5,732 | 537,625,260 | 커밋 `38f9e08cb0`의 추적 파일 5,732개와 같다(5,732/5,732, 다름 0, 빠짐 0). 그 밖의 파일은 `.pytest_cache` 5개뿐이다 | `git worktree add --detach <경로> 38f9e08cb08cafba6ce2f66ff7b08c19788cf1d1` |
| `mobility-develop-20261008`(옛 PC 고아 worktree) | 3,118 | 180,741,885 | 커밋 `d85cc7cf0c`와 같다(3,118/3,118). 그 밖의 파일은 `.pytest_cache`와 `.pyc`뿐이다 | `git worktree add --detach <경로> d85cc7cf0c2dbacb2301ef492e0cf866a4c271b4` |
| `manager_recovery_20261012/manager-snapshot`(폴더 전체) | 3,682 + `.git` 3,521 | 128,341,452 + 76,920,365 | `complete_manager_snapshot.py`가 만든 `git archive 45ab1efa8e -- final_project_cs` 사본이다. 커밋 없는 `.git`이고, index 3,682개와 loose object 3,502개도 같은 내용이다. `manager-complete-manifest.json` SHA-256이 3,682/3,682 일치했다 | 같은 스크립트 절차(archive를 풀고 `git init`, `add --force`). 그 결과를 manifest와 대조한다 |
| `.next-live/cache/turbopack` 3곳(`recovery-candidate` web, `baseline-manager/team` web·admin) | 41 | 65,479,986 | Next 컴파일러 캐시다. 추적 0건이고 `apps/web/.gitignore:4`(`.next-live/`)로 무시된다 | 다음 빌드 때 다시 생긴다 |

- 남긴 것: 두 고아 worktree의 `.git` 포인터 파일(`C:/Users/playdata2/...`), `.pytest_cache`(실행 결과 `lastfailed`), 원본 `.py`가 커밋에 없는 `.pyc` 14개(`mobility-develop`)
- 지운 자리마다 `_PRUNED_20261027.txt`를 남겼다(`manager_recovery_20261012/manager-snapshot_PRUNED_20261027.txt` 포함). 커밋과 되살리는 법을 적었다.
- `manager-snapshot`은 10-12 기록(`c-drive-root-cause-20261012.md`)에서 '보존 지시가 있어 그대로 두었다'고 한 폴더다. 그때는 회복 작업이 진행 중이었다. 이번에는 사용자 지시와 바이트 재생성 증명(manifest 일치, 공개 커밋)을 근거로 지웠다. 생성 스크립트와 manifest 두 개는 그대로 있다.

### 남긴 것과 분류

| 대상 | 분류 | 근거 |
|---|---|---|
| `manager_recovery_20261012/recovery-candidate` | **통합 검토 필요** | `refs/local-backups/unpublished-recovery-20261012` = `349ad1d`(`fix(deploy): restore native migration safety contract and atomic SQL execution`)가 루트 저장소에 없다(같은 제목의 커밋도 0개). 작업 트리의 고유 파일은 캐시를 빼고 56개(`_backup/*`, `merge-inputs/*`, `mockups/*`)다. status는 4,871행이다. alternates가 옛 PC 경로를 가리켜 부모 커밋은 읽을 수 없다 |
| `wt_dev`(고아 worktree, 기준 `e87a45e07` 10-07) | **통합 검토 필요** | 이력 어디에도 없는 내용의 파일이 37개 있다. 35개는 현재 `team/develop`에 같은 경로가 있다(`app/core/settings.py`, `watch.py`, `wiki/log.md` 등). 2개는 develop에 경로가 없다(`instances/activity/watch.py`, `src/features/trip/trip-home.tsx`). 대부분 이미 바뀌었을 수 있으나 의미 대조는 하지 않았다 |
| `baseline-manager-20261012/team`(기준 `42df598c8e`) | 보존(로컬 검증 설정) | 4,857/4,858이 같다. 다른 것은 `apps/web/tsconfig.json` 1개이고, develop에 없는 `playwright.*-private.config.ts` 7개가 더 있다. `.next-*` 빌드 출력과 이미지 캐시는 검증 산출물로 남겼다 |
| `full-release-20261008/release` | 보존(증거 인용) | `final_project_cs/wiki/records/evidence/2026-10-08_채팅모델_연결진단/README.md:76`이 인용한다. 기준 `5ded30ca3e`와 4,639/4,639 같지만, 고유 파일이 84개(`_backup/*.bak`, `test-results` 캡처, 지도 타일) 있다 |
| `claude_followup_20261012/workspace` | 보존 | HEAD `12f81c6`은 루트에 있다. 고유 파일은 `final_project_cs/CLAUDE.md` 1개(1,244B, 로컬 수정)다. alternates가 끊겨 있다 |
| `uiux-handoff-*/base` 6곳(합계 약 2.1MB) | 보존(편집 전 사본) | 고유 파일은 23개다. 그중 다수가 `full-release/release`의 `_backup/2026-10-10_*_before/*.bak`과 같지만, `plan-check.module.css` 등 6개는 다른 곳에 없다. 얻는 공간도 작다 |
| `pytest`의 `test_repo_root_ignores_*` 안쪽 `.git`(약 100곳) | 보존 | 테스트 고정물(fixture)이고 증거 폴더 안에 있다 |

### 기록 위치

Hermes scratch의 `tmp-wt-audit-20261027/`에 있다. 파일별 해시(`hashes.tsv`, 35,596행), 기준 커밋 대조(`basematch.json`), 삭제 계획과 결과(`purge_plan.tsv`, `purge_deleted.tsv` 12,573행, `purge_held.tsv` 0행), 최상위 전후 측정(`before_top.json`, `after_top.json`), 루트 status 전후, 스크립트(`listfiles.py`, `hashcov.py`, `basematch.py`, `mscheck.py`, `purge.py`)가 들어 있다. scratch는 24시간 뒤에 정리될 수 있다.
