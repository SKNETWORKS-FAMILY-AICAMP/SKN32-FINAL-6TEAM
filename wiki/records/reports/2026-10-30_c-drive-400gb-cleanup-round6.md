---
type: report
title: C: 400GB 6차 정리 — 규칙 경계 재대조, guguroute scratch 재현 가능 파일 5.40GB 삭제, 승인 후보·가드 연결 소유 정리
description: AGENTS/CLAUDE 「대상별 승인」은 C:/_proj/final_workspace 안 자료에 적용됨을 확인하고, 그 밖의 이 프로필 scratch·Temp 캐시 중 GitHub 객체나 git archive로 바이트 재현되는 것만 지웠다. C: 여유 226.92GB→232.21GB, 400GB까지 167.79GB 부족
status: done
domain: travel
impl_scope: guguroute 프로필 cache/scratch의 정확한 경로 16곳 + 사용자 Temp node-compile-cache v26 2개 폴더만 삭제. 보존본은 같은 프로필 backups/disk-round6-20261030. 원본 C:/_proj/final_workspace의 scratch·datasets·코드·Git, C:/_proj 다른 사본, 모델, NPU, 다른 프로필, 설정, 서비스는 변경하지 않음. 이 보고서·증거·색인 한 줄만 추가
---

# C: 400GB 6차 정리 (2026-10-30 21:17–22:12)

앞선 기록: [5차](2026-10-30_c-drive-400gb-cleanup-round5.md), [4차](2026-10-29_c-drive-400gb-cleanup-round4.md), [가드](2026-10-29_disk-growth-guard.md). 단위 GB=10⁹ B. 다른 작업이 계속 쓰므로 여유 변화는 삭제 효과와 동시 쓰기의 합이다.

## 결과

| 시각 | C: 여유 바이트 | GB |
|---|---:|---:|
| 21:17:16 시작 | 226,917,208,064 | 226.92 |
| 21:52:03 첫 삭제 직전 | 226,650,923,008 | 226.65 |
| 22:10:41 마지막 삭제 직후 | 232,213,229,568 | 232.21 |
| 22:11:55 최종 | 232,212,664,320 | 232.21 |

- 지운 논리 바이트 **5,398,585,886 B**. 삭제 구간 실측 합 **+5,585,383,424 B**(작은 파일 4만여 개의 클러스터 여유분 포함). 실패 0, 건너뜀 0.
- 목표 대비 **232,212,664,320 / 400,000,000,000 = 58.05%**, 부족 **167,787,335,680 B**. **400GB는 달성하지 못했다.**

| 지운 것 (scratch = `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch`) | 파일 | 바이트 | 재현 근거 |
|---|---:|---:|---|
| `date_risk_325ba25_full_01.tar` | 1 | 1,633,730,560 | 10-24 `git archive 325ba25d8`로 생성(state.db 기록). 오늘 다시 만든 tar의 sha256 `d9a73efe…8025`가 같다. 커밋은 GitHub origin/main에 있다 |
| `c12-review-20261028/src.tar` | 1 | 234,567,680 | 소유자 인계 「통합 뒤 삭제 가능, 증거 폴더 보존」. 멤버 9,946/9,946 blob이 `7f670774f`와 같고, 이 커밋은 `c12-integ-ev/c12-integ.bundle`(verify 통과)에 있다 |
| `writing-replay-20261025-032529-579319/` | 572 | 619,147,357 | shallow 재생 사본. pack 객체는 모두 GitHub `325ba25d8`에서 도달 가능 |
| `writing-helper-replay-20261025-032841-917959/` | 442 | 618,347,147 | 같음 |
| `sse-final-20261028/base` 외 snapshot 트리 13곳 | 37,376 | 2,122,103,306 | 각 파일 raw git blob이 GitHub 원격 ref에서 도달 가능한 것만 지움 |
| `C:/Users/kcxsz/AppData/Local/Temp/node-compile-cache/{v26.7.0-arm64-8d7ad2ee,v26.12.1-arm64-310b2ce3}` | 31,537 | 170,689,836 | Node 컴파일 캐시. 그 버전 node 프로세스 없음, 24시간 넘게 쓰기 없음 |
| **합계** | | **5,398,585,886** | |

snapshot 13곳은 `sse-final-20261028/base`(전부), `acceptance-matrix-20261025/{frozen-baseline,frozen-api,fixcandidate-comment7-complete,fixcandidate-comment7}`(고유 259개는 그 자리에 남김), `public-web-ddgs-20261026-053927/{base,base53,rm,rm-on-1e4e3b2,rm-on-3c1af5b,rm-on-418cc19}`(전부, 빈 상위 폴더 제거), `clockfix-push-20261026-025217`(전부), `c12-review-20261028/src`(고유 5개+LF 정규화 일치 1개 남김)이다. 파일이 남은 곳에는 `_ROUND6_REPRODUCIBLE_FILES_REMOVED.md`를 두었다. 모든 대상이 이 프로필 scratch나 사용자 Temp의 재생성 캐시다.

## 규칙 대조 — 「사용자 개별 승인 필요」가 막는 범위

[루트 AGENTS.md·CLAUDE.md](../../../AGENTS.md) 「로컬 원본·데이터셋 삭제 금지」(2026-10-17)와 「디스크 증가 예방」(2026-10-29) 원문 기준이다. 두 파일의 이 두 절은 같다. `final_project_cs`·`final_project_sample` RULE/AGENTS·`final_project_ui/CLAUDE.md`에는 디스크·삭제 절이 따로 없다.

- **대상**: 「이 로컬 작업 폴더」 = `C:/_proj/final_workspace` 안의 자료다. `datasets/`, `program/`, `w3/`, `.tmp/`, `_backup/`처럼 이름만으로 폐기 가능하다고 보지 않는다. **세션이 만든 임시 사본도 포함**되므로 `final_workspace/scratch` 90개 항목은 모두 대상이다.
- **요구**: 지우기 전에 정확한 절대 경로, 파일 목록, 보존 상태를 보이고, 사용자가 **그 대상에 대해** 명시적으로 삭제를 승인해야 한다. 일반 정리 승인이나 커밋·푸시·동기화 승인은 이것을 대신하지 않는다.
- **금지 수단**: 원본에서 `git clean/reset/restore/checkout/pull`, 재귀 삭제, `robocopy /MIR /PURGE /MOV`, `rsync --delete`를 용량 확보에 쓰지 않는다. 디스크 절도 「공간 확보 삭제는 위 절 규칙을 그대로 따른다」고 적는다.
- **범위 밖**: 이 프로필의 Hermes scratch·backups, 사용자 Temp 캐시는 프로젝트 폴더 밖이다. 앞선 회차(2~5차)도 같은 해석으로 지웠다. 다만 그 안의 명시 보존 지정(`_archive_20261027`, `finalspace_preservation`, Hi 감사 보존물 `integ-K/Q`·`place-quality`, 「이동 보존」한 `original_runtime_prep/web_node_modules_x64_backup_20261028`, 증거 tar `latest_team_audit_valid.tar`)과 실행 중·롤백 참조는 그대로 지켰다.
- `C:/_proj/<이름>1029` 사본은 프로젝트 폴더 밖이지만 다른 작업자(EKS·routing·bus)의 HOLD 연쇄와 증거다. 그래서 소유자 결정 대상으로 남겼다.

## 검증 방법

- **사용**: 삭제 직전마다 Win32_Process를 스냅숏했다(367~375개, 이 작업 자신의 명령 제외). 대상 이름을 참조하는 프로세스는 0개였다. 실행 중 node는 v24.10.0 x64(PID 16248·26720·27028)와 v24.22.1 arm64(PID 6576·32620)라서 그 두 컴파일 캐시는 남겼다.
- **연결**: 허브 `.git/worktrees/*/gitdir`, 스크립트·json 참조를 검사했다. `public-web-ddgs`·`clockfix-push` 하위 트리는 `allpast-hotfix-20261025-2005/repo`의 옛 worktree 등록 대상이지만 `.git` 파일이 이미 없는 잔여 파일이었다. 허브 등록은 고치지 않았다(허브 소유자의 `worktree prune` 결정). 재분석 지점과 hardlink(nlink≠1)는 0개였다.
- **재현성**: GitHub 원격 ref(`routing-open-20261028/repo` 45개 + 허브 13개)에서 도달 가능한 객체 70,240+69,606개와 raw blob이 같은 파일만 지웠다. CRLF→LF 정규화로만 일치하는 파일은 바이트 복원이 보장되지 않아 남겼다. 그래서 `port-develop-20261026-011444-95683888/percommit`(LF 일치 211MB)은 대상에서 뺐다.
- **보존**: writing 두 사본은 `.git/objects/pack/*`을 뺀 `.git` 전체(HEAD·config·index·`selected-candidate.index`·`selected-replay.index`·shallow·logs, pin에서 도달할 수 없는 느슨한 객체 128개)와 pin blob과 다른 작업 트리 파일 82개씩(수정 34 + 미추적 48)을 배타 생성(`xb`)으로 복사했다. sha256을 다시 대조했고 342개 10.47MB다. 삭제할 때는 파일 집합·크기·mtime·nlink 일치, 보존본 sha256, 50MB 넘는 원본 sha256을 다시 확인했다. 첫 실행은 `DirEntry.stat()`의 nlink가 Windows에서 0인 탓에 두 폴더를 지우지 않고 중단했다. `os.stat`으로 고쳐 다시 실행했다.
- **보존 위치**: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/disk-round6-20261030/` (366개, 21,128,331 B). `RETIRED.md`(복원 절차), snapshot별 삭제 manifest `removed-*.tsv`(경로·크기·sha256·blob)가 있다.

## 승인·소유자 결정이 필요한 후보 (우회하지 않음)

| 후보 | GB | 막는 것 | 정확한 목록 |
|---|---:|---|---|
| `C:/_proj/final_workspace/scratch` 90개 | 83.97 (24시간+ 유휴·프로세스 참조 0: 80개 73.92, 그 안 재생성 캐시 5.74) | AGENTS.md 대상별 명시 승인 | [final-scratch-approval-candidates.json](../evidence/2026-10-30_disk-round6/final-scratch-approval-candidates.json): 항목별 경로·바이트·파일 수·유휴·Git 수·캐시 바이트·지금 프로세스 참조·소유 인계 |
| `C:/_proj/eksremaining1029/{candidate,baseline}` + `pgdata-preserved.tar`, `eksprecision1029/candidate`, `ekslat-review1029/repo` | 5.24+1.75+2.62+0.56 | EKS PR110 HOLD 연쇄 원천, HEAD `ee8ca8807`·`346a57d4d`가 GitHub ref에 없음(10-29 13:29 fetch 기준) | EKS 소유자가 HOLD를 풀면 bundle·증거 보존 뒤 체크아웃만 회수 |
| `C:/_proj/routingresume1029`, `routinga11base1029`, scratch `routing-open-20261028`·`routing-open-20261029b` | 약 3.4 | routing 허브 `routing-open-20261028/repo`의 worktree 연쇄. `routinga11verify1029/pgdata`는 postgres PID 38472가 실행 중 | routing 소유자 |
| scratch `integ-K-allaudit-20261027/final_project_cs`·`integ-Q-20261027/final_project_cs` | 0.36+0.36 (raw 재현 99.9%) | Hi 감사 보존 지정 | 사용자 |
| scratch `original_runtime_prep/web_node_modules_x64_backup_20261028` | 0.59 | 원본에서 「이동 보존」한 x64 node_modules | 원본 실행 담당 |
| Temp `hermes_agy_*` 19개 | 0.28 | Hermes 앱(Gemini/Antigravity) 임시 홈, 다른 소유·자격 정보 가능 | 앱 소유자 |
| Hermes 모델, hiberfil, WSL vhdx, NPU 산출물, 기본 프로필 scratch, 다른 프로젝트 | 5차 표와 같음 | 모델 보존 지시·관리자 권한·다른 소유자 | [5차 표](2026-10-30_c-drive-400gb-cleanup-round5.md#400gb-가능-여부) |

- **조합 예시**: 부족 167.79GB = final_workspace scratch 73.92(유휴분) + Flash-Next 모델 98.74 → 172.66GB. 모두 사용자 결정이며 동시 쓰기 때문에 보장되지 않는다.

## C:/_proj 다른 사본과 disk-guard 연결 누락의 소유

- `C:/_proj`에는 10-29 02:36~20:55에 만든 `*1029` 폴더 37개가 있다(생성 시각 기준). 인계 기준 소유는 이렇다.
  - `eks*` 26개: EKS 작업자
  - `routing*` 10개: routing A11 작업자
  - `busreview1029`: bus 작업자
- 대부분은 3차에서 체크아웃을 회수했다(`RETIRED.md`). 지금 Git 체크아웃이 남은 곳은 5개다. `eksremaining1029`·`eksprecision1029`·`ekslat-review1029`는 HOLD이고, `routingresume1029`·`routinga11base1029`는 routing worktree다. 나머지는 증거 폴더다.
- `disk_guard.py inventory`의 결과는 `entries=[]`, `unregistered_dirs=[]`다. 장부는 managed root `C:/_proj/_clones`만 보므로 이 37개와 scratch 사본을 보지 못한다.
- 가드 도입(10-29 16:20경) 뒤에도 9개를 `C:/_proj/` 바로 아래에 만들었다: routing 증거 6개, `eksremain3_resume_1029`, `eksfix3_1029`, `eks-independent-1029`. 장부 등록은 0이다. 이 9개가 당시 clone을 담았었는지는 지금 상태로 확인하지 못했다. 인계 여러 건은 `check`만 실행했다.
- 연결 누락의 소유:
  - ① Hermes 위임 시작 절차(guguroute 프로필 skill `guguroute-claude-coding-workers`): clone·작업 경로 규칙에 `guarded_clone`이 없다. 이 프로필 소유다.
  - ② Claude 실행 전 훅: 프로젝트 `.claude/settings.local.json`(73 B)에 연결이 없다. 프로젝트 지시 파일 소유자 승인이 필요하다.
  - ③ NPU: `npu_disk.py`(30GiB 하한, 95/110GB 예산)와 `argen3/run_ffnvar.py`의 `disk_guard check`만 연결됐다. `stage.py`·`run_stream.py`는 자체 85GiB 하한을 쓴다. `make_onnx.py`·`export_weights.py`·`llama-quantize`는 미연결이다. NPU 소유다.
  - ④ Codex 작업자는 문서 규칙만 따른다.
- 이번 회차는 위 연결을 바꾸지 않았다. 다른 작업자의 진행 중 경로와 설정이기 때문이다.
- 부수 확인 1: `disk_guard.py inventory`는 실행할 때마다 장부 파일을 원자 교체로 다시 쓴다(내용 동일, mtime 22:11:45).
- 부수 확인 2: `C:/c/`(799 B, 파일 1개)는 MSYS 경로 오류로 생긴 잔여 폴더다(10-29 15:07, 10-30 13:54). 다른 세션 산출물이라 남겼다.
- 부수 확인 3: `C:/_proj/k.txt`(148 B)에 평문 API 키 2개가 있다. 건드리지 않았다.

## 남은 일

- 400GB 목표는 열려 있다. 다음 회수는 사용자의 final_workspace scratch 항목별 승인, 또는 모델·HOLD·routing 소유자 결정이 있어야 가능하다.
- 커밋·푸시·서비스 중지·설정·skill·다른 프로필 변경은 없다. 제품 코드를 바꾸지 않았으므로 제품 시험은 해당 없다.
- 증거 19개: [artifacts.json](../evidence/2026-10-30_disk-round6/artifacts.json), [plan.json](../evidence/2026-10-30_disk-round6/plan.json)(sha256 `405e3b62143f281ce640c9812a89d6823c9e935013306b4502d43dc3fc048657`), [delete-result-3-snap.json](../evidence/2026-10-30_disk-round6/delete-result-3-snap.json)(sha256 `9e6ee23a84aff51417e45100cede1a1b062ef2507711b722f491b1a7a9d720a2`), [snapshot-classification-summary.json](../evidence/2026-10-30_disk-round6/snapshot-classification-summary.json), [backup-inventory.json](../evidence/2026-10-30_disk-round6/backup-inventory.json). 실행 스크립트는 `scripts-*.py`다. 프로세스 명령줄 원문은 비밀 노출을 피하려고 증거에 넣지 않았다.
