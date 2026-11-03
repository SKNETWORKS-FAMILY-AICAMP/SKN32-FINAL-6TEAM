---
type: report
title: guguroute Hermes scratch 작업 사본·스냅숏 트리 정리 — 실측 회수와 보존 내역
description: 끝난 체크아웃 19개와 10-24~26 스냅숏 트리 18개를 커밋·고유 파일 보존 확인 뒤 지워 논리 57.08GB를 지우고, C: 여유는 최저 76.27GB에서 126.50GB가 됐다. 같은 시간 NPU 실험이 +33GB 늘었다
status: done
domain: travel
impl_scope: cs — 이 PC의 Hermes guguroute 프로필 scratch·backups와 wiki 기록만 다룬다. 원본 작업 폴더 `C:/_proj/final_workspace`의 코드·Git·데이터, `C:/_proj/*1029` 사본, 기본 프로필, NPU 실험은 변경하지 않았다
---

# guguroute scratch 사본 정리 (2026-10-29 15:55–18:05)

사용자 지시: C: 여유 400GB 목표. 재생성 가능하고 쓰지 않는 사본·캐시를 전수 분류해 최대한 회수한다. 원본·유일 변경·DB·모델·증거·현재 작업은 보호한다. 실행 중인 프로세스와 작업을 멈추지 않고, 기본 Hermes 프로필은 수정하지 않는다. 사용자는 검증된 불필요·재생성 가능 항목의 정리를 미리 승인했고, 파일별 재승인은 요구하지 않았다.

단위는 GB=10⁹ B다. 여러 작업자가 동시에 쓰고 있어서, 구간 여유 변화는 삭제 효과와 다른 작업의 쓰기가 합쳐진 값이다.

## 결과

| 시각 | C: 여유 바이트 | GB |
|---|---:|---:|
| 15:55 세션 시작 | 100,752,478,208 | 100.75 |
| 16:49 첫 삭제 직전(최저) | 76,269,846,528 | 76.27 |
| 18:03 마지막 삭제 직후 | 126,499,893,248 | 126.50 |

| 묶음 | 대상 | 파일 | 지운 논리 바이트 | 구간 여유 변화 |
|---|---:|---:|---:|---:|
| 체크아웃 A·B·C·D | 19 | 419,784 | 28,268,276,907 | +28.85GB |
| 스냅숏 트리 E·F·G | 18 | 357,158 | 28,805,408,685 (그중 2,871,031,221은 backups로 복사) | E +17.73 · F +2.87 · G −4.15GB |

- 지운 논리 바이트는 **57.07GB**다. 고유 파일을 backups로 복사한 2.87GB를 빼면 순수하게 줄어든 크기는 약 **54.2GB**다.
- G 구간(17:47–18:03)은 지운 크기보다 다른 작업의 쓰기가 많아서 여유가 오히려 줄었다.
- **400GB 목표는 달성하지 못했다.** 남은 부족분은 약 273.5GB다. 이 프로필 scratch 전체가 정리 전 145GB였으므로, scratch만 정리해서는 목표에 닿을 수 없다.

## 진행 중 증가 원인 (작업자 통제 필요)

- `C:/Users/kcxsz/frog-npu-dev/experiments` 크기가 15:50 67.5GB에서 18:05 100.4GB로 **+33GB** 늘었다. 엔진 세트 하나가 약 17GB이고(`h1`·`h1-eps3`), 16:44 이후 `review-hb`·`review-silufix64`·`stream16-tmp`·`h16-here`·`argen-tmp`가 새로 생겼다. NPU 실험이 실행 중이라 삭제하지 않았다. 담당자에게 `cache/scratch/_coord/disk-growth-alert-20261029-1610-NOTICE.md`로 알렸다.
- WSL `ext4.vhdx`는 16:23 43.42GB에서 18:05 47.12GB로 +3.70GB 늘었다. 가상 디스크는 자동으로 줄어들지 않는다.
- 생성 경로를 검사하는 장치는 [디스크 증가 예방 가드](2026-10-29_disk-growth-guard.md)가 맡는다. 이 정리 작업은 그 장치를 바꾸지 않았다.

## 판정 기준

모든 대상에 대해 다음을 확인했다.

1. 직전 Win32_Process 명령줄 스냅숏에 대상의 최상위 폴더 이름이 나오지 않는다. 이 정리 작업 자신의 명령은 제외했다.
2. 대상 안에 6시간 안에 수정된 파일이 없다. 삭제 직전에 다시 열거해서 확인했다.
3. 재분석 지점(junction·symlink)이 없다. 있으면 그 항목은 건너뛰고 따라가지 않았다.
4. 어떤 저장소의 `objects/info/alternates`도 대상을 가리키지 않는다. scratch·`C:/_proj`·backups 전체에서 확인했다.
5. 커밋과 파일 내용이 보존된다. 방법은 묶음마다 다르며 아래에 적었다.

### 체크아웃 19개 — 폴더째 삭제, 형제 증거 폴더는 보존

- **A (7개)**: 작업 트리가 깨끗하고 HEAD가 팀 GitHub(`team/*`)에 있다. 저장소째 지운 3곳은 모든 로컬 브랜치·태그도 팀 원격에 있다.
  - `teamflow-105-20261028b/wt_base`, `sse-final-20261028/rm`
  - `eks-final-20261028/repo`, `eks-fix-20261028/repo3`
  - `eks-release-20261028/wt_main`, `eks-release-20261028/wt_rm`
  - `eks-deadline-indep-review-20261028/fixclone`
- **B (4개)**: 깨끗하지만 HEAD가 원격에 없다. `git bundle`을 만들고 verify를 통과한 뒤 지웠다.
  - 대상: `teamflow-105-20261028b/wt_main`·`wt_rm`, `teamflow-open-sweep-20261028/wt`, `eks-verify-20261028/repo`
  - bundle 위치: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-worktree-commits-20261029/` (sha256은 `SHA256SUMS`)
- **C·D (8개)**: 10-28 정리에서 「미커밋 변경」 때문에 남긴 트리다. 변경 내용을 확인해 보니 긴 경로 때문에 체크아웃되지 못한 pytest 임시 파일의 「deleted」였다. 그래도 다음을 모두 보존한 뒤 지웠다.
  - HEAD bundle(원격에 없는 경우), `dirty.patch`
  - 추적되지 않은 파일, 캐시가 아닌 무시 파일(sha256 대조 일치)
  - 대상: `port-develop-20261026-011444-95683888/wt`, `integ-merge-dev-20261026-0717/rm`, `fix5-20261026-1240/rm`, `reldate-rm-20261028-0337/rm-base`, `c1-notice-e2e-20261027/wt`, `past-edit-delete-only-20261026`, `mgr-merge-20261026-0045`, `integ-mgr-a465c6022-20261026`
  - 보존 위치: `backups/scratch-worktree-archive-20261029/<이름>/` (`SUMMARY.txt`, `copy-list.txt`)
- 삭제 뒤 19/19개 폴더가 모두 없는 것을 확인했다. 허브(`allpast-hotfix-20261025-2005/repo`)의 worktree 등록 정보는 prunable 상태로 남겨 두었다.

### 스냅숏 트리 18개 — 파일 단위 삭제, `.git`은 보존

10-24~26 검증에 쓴 저장소 모양 복사본(NOHEAD 저장소나 대량의 미추적 파일)이다. 10-27 정리에서는 판정 없이 「git 오류」 때문에 남겼다.

- **판정 방법**: 파일마다 git blob sha1을 계산했다. 원본 `C:/_proj/final_workspace`의 ref에서 도달 가능한 객체(`rev-list --objects --all`, 72,881개)에 들어 있는 파일만 「git 재현 가능」으로 보았다. 도달 불가 loose 객체나 작업 트리에만 같은 파일이 있는 경우는 재현 근거로 쓰지 않았다.
- **고유 파일 보존**: 나머지 80,345개 파일(2.87GB)은 `backups/scratch-snapshot-archive-20261029/<트리>/<상대경로>`에 덮어쓰지 않는 방식으로 복사했다. 복사 뒤 blob 해시를 다시 계산해 일치하는 것을 확인한 다음에만 원본 파일을 지웠다.
- **복원 근거**: 경로·크기·blob·보존 위치를 담은 전체 목록이 `snapman-*.tsv`에 있다.
- **삭제 범위**: `.git` 폴더(alternates 체인)와 재분석 지점은 건드리지 않았다. 각 상위 폴더의 로그·결과·tar·보고서도 남겼다. 지운 뒤 남은 대상 파일은 0개다.
- **대상**:
  - `remaining_dod_validation/{baseline,repo}`
  - `remaining_shared_implementation/{baseline_repo,repo}`
  - `remaining_local_review/{historical_exact_tree_v2,historical_roundtrip_exact_v2}`
  - `booking_admin_off_v2/{baseline_repo,repo}`
  - `customer_hours_integration_01`·`_02`
  - `customer_hours_independent_review_01/repo`·`_02/repo`
  - `final_integration_preparation/repo`
  - `date_risk_git_review_02`, `date_risk_baseline_03`, `date_risk_325ba25_02`
  - `fixture-clock-fix-20261026-0118-19126/{develop,rm}`
- **효율이 낮았던 트리**: `date_risk_325ba25_02`(43,311개 1.25GB 보존)와 `fixture-clock-fix`(각 0.46GB 보존)는 고유 파일이 많아서 실제로 줄어든 크기가 작았다.

## 보존한 것과 이유

- **실행 중이거나 롤백 참조가 있는 것**
  - `ops-jobs-20261026-054158`: `launch-ops-jobs.py --db live` 4개 프로세스가 실행 중이다.
  - `api-runtime-20261025-014236`, `date_risk_python_01`: 그 프로세스들의 런타임이다.
  - `latest-serving-6c345-20261025`: `runtime-v2`가 `source-v2`를 롤백 실행본으로 참조한다.
  - `local_admin_3300_v2`: admin 불변 빌드 기록이 있고, 고유 파일이 319MB다.
  - `public-web-binding-v5-*`·`web-v5-release-*`·`integ-v10c-ctx-*`·`candidate-review-fix-*`·`schedule-explain-impl-20261029`·`original_switch_20261028`: 실행 중이다.
- **최근 활동이 있거나 미커밋 작업이 있는 것**: `tf106-20261029`, `routing-open-2026102*`, `st4f710*`·`st4f711-backend-20261029-v1`, `modelq-G-20261027/rm`(변경 109개), `allpast-hotfix-20261025-2005` 허브(worktree 122개)
- **보존 지정된 것**: `place-quality-20261027`·`integ-Q-20261027`·`integ-K-allaudit-20261027`·`ctrl-audit-20261027`
- **보존물**: `_archive_20261027`(9.67GB), `finalspace_preservation`(1.82GB)이다. 이번에도 옮기지 않았다. scratch 자동 정리의 위험은 [이전 보고](2026-10-28_c-drive-free-space-units-and-scratch-cleanup.md) 그대로 남아 있다.
- **이번 범위에서 판정하지 않은 사본**
  - `C:/_proj/eks*1029`·`bus*`·`routing*1029` 22개 Git 루트(약 45GB): 각 Codex 작업자의 NOTICE가 HOLD·보존을 선언했다.
  - `C:/_proj/final_workspace/scratch` 83GB: 프로젝트 안의 자료라서 AGENTS.md 규칙상 대상별로 명시적 삭제 승인이 필요하다.
  - Git 분류 결과(`projroots.tsv`)를 보면, 깨끗하고 HEAD가 원격에 있는 후보는 `eksscalar1029/repo`·`eksreview1029/repo`·`eksprecision1029/repo`·`eksremaining1029/baseline`·`busreview1029`다. 각 소유자의 정리 판단이 필요하다.
- **캐시 디렉터리**: scratch의 node_modules는 5.37GB, `C:/_proj`는 6.57GB다. 대부분 최근 사본이나 원본 작업 폴더 안에 있어서 지우지 않았다.

## 원자료

`C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/disk-cleanup-20261029-scratch/` (56항목, `SHA256SUMS`)

- `manifest-{A,B,C,D}.tsv`: 지운 체크아웃 파일 419,784개의 크기와 경로
- `result-*.json`: 대상별 여유 실측과 삭제 후 존재 여부
- `snapman-*.tsv`·`snapresult-*.json`: 스냅숏 트리 파일 357,158개의 blob과 보존 위치
- `roots2.tsv`·`projroots.tsv`·`cand/`: Git 상태 분류
- `procs-*.json`: 프로세스 원자료. 명령줄이 들어 있으므로 커밋하지 않는다
- 스크립트 `delA.py`·`snapdel.py`·`arch1.sh`

작업 원본은 `cache/scratch/c-cleanup-20261029b/`에 있다. 작업자 알림은 `cache/scratch/_coord/disk-cleanup-scratch-20261029-NOTICE.md`다.

커밋·푸시는 하지 않았다. 제품 코드를 바꾸지 않았으므로 제품 시험은 실행하지 않았다.
