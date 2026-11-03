---
type: report
title: final_workspace/scratch 400GB 달성 뒤 사본 63개(83.43GB) 고유·미커밋·참조·소유자 분류와 경로별 삭제 승인 목록, NPU 소유자 추가 회수 0.24GB
description: 10-27 20:21(약 437GB) 뒤 생긴 scratch 폴더 63개의 파일 1,119,416개를 전부 해시해 보존된 Git 객체(GitHub·원본·bundle 43개)와 대조했다. 재현 불가 파일 2.97GB는 압축 내용 주소 저장소(0.52GB)에 보존하고 3개 폴더를 실제로 복원해 sha256 62,914/62,914 일치를 확인했다. 미보존 원격 ref 4개는 bundle로 보존해 ref 116/116 보존이다. 삭제는 0건이고 경로별 승인 목록만 만들었다. NPU 소유자는 요청을 수락해 0.24GB를 회수했다
status: done
domain: ops
impl_scope: 읽기 전용 조사. 쓴 것은 guguroute backups/c400-unique-20261103(653MB), 이 보고서, 증거 폴더 2026-11-03_scratch-unique-approval, 인계 1개, 인계 목차 한 줄뿐이다. final_workspace scratch·.tmp/clones·코드·Git, 다른 프로필, 모델, WSL, 시스템 설정은 바꾸지 않았다. NPU 쪽 삭제·하드링크는 소유자 세션이 자기 산출물에 대해 실행했다
---

# scratch 고유 분류와 경로별 삭제 승인 목록 (2026-11-03 06:30–07:50 KST)

앞선 기록: [400GB 달성 시점 대비](2026-11-03_c-drive-400gb-peak-vs-now.md), [10차](2026-11-03_c-drive-400gb-cleanup-round10.md), [7차 후보 3개](2026-10-30_c-drive-400gb-cleanup-round7.md). 단위는 GB = 10⁹ B다. **실측**은 이번에 직접 센 값이다.

## 결론

- **대상**: `C:/_proj/final_workspace/scratch`에서 10-27 20:21 뒤 생긴 폴더 **63개, 83,427,213,040 B, 파일 1,119,416개**. 이것이 달성 시점 대비 증가분 A(83.43GB)다. 달성 전부터 있던 19개(495,949,324 B)는 목록에서 뺐다.
- **63개 모두 보존이 끝났다.** 파일마다 아래 중 하나로 복원할 수 있다(실측 바이트).

  | 방식 | 바이트 | 근거 |
  |---|---:|---|
  | 보존 Git 객체로 재현 | 49,681,224,301 | blob(원본 또는 CRLF→LF)이 GitHub·원본·bundle에서 도달 가능 |
  | 재생성 캐시 | 15,285,799,863 | node_modules·.next·__pycache__·브라우저 캐시 |
  | `.git/objects` | 12,606,434,349 | 참조 커밋 116/116이 보존 객체원에 있음 |
  | `git archive` tar 재생성 | 2,602,332,160 | tar 10개의 구성원 blob 전부가 보존 객체에 있음 |
  | **새로 보존(고유)** | **2,971,209,884** | pgdata·로그·`*-private.json`·미커밋 파일 등. 압축 저장 523,178,741 B(내용 주소, 중복 1벌) |
  | 기존 보존본과 같은 sha256 | 280,212,483 | guguroute backups·wiki 등의 같은 파일 |

- **실제 복원 시험**: 3개 폴더를 manifest만으로 다시 만들어 sha256을 전수 대조했다. `st4f731-correction` 12,709/12,709, `st4f729-independent`(허브가 사라진 worktree) 22,284/22,284, `st4f719-blocker-independent`(HOLD 후보) 27,921/27,921. 불일치 0이다. 시험본은 지웠다.
- **삭제는 0건이다.** AGENTS.md 「대상별 명시 삭제 승인」 때문에 경로별 승인 목록만 만들었다([approval_list.json](../evidence/2026-11-03_scratch-unique-approval/approval_list.json), [표](../evidence/2026-11-03_scratch-unique-approval/list.md)).
- 63개와 `.tmp/clones` 2개(9,839,389,277 B, 이번에 ref 11/11 보존·`status` 0줄 재확인)를 모두 승인하면 **93.27GB**를 회수한다. 현재 270.53GB(07:46)에서 단순 합으로 약 363.8GB가 된다. 400GB까지 약 36GB가 더 필요하다(아래 「남은 것」). 동시 쓰기가 있어 보장하지 않는다.

## 분류 방법

1. 63개 폴더의 모든 파일을 재분석 지점을 따라가지 않고 셌다. 파일마다 sha256, Git blob(원본 바이트), CRLF→LF blob을 계산했다.
2. 보존 객체원을 만들었다. GitHub 전체 브랜치를 새로 fetch했다(tip `main 57f3d2f00`·`develop 3463b30c6`·`role-manager fab3da50a`, 10-29와 같다). 원본 `.git` 객체는 읽기 전용 alternates로만 썼다. guguroute backups의 bundle 42개는 모두 fetch에 성공했다. 여기서 도달 가능한 객체 73,830개와 대조했다.
3. 재현 안 된 파일은 기존 보존 위치(backups·final_workspace, scratch와 `.tmp/clones` 제외)의 같은 sha256 파일을 찾았다. 없으면 `store/<sha256>.gz`에 한 벌만 압축 보존하고 압축을 풀어 다시 대조했다.
4. Git 루트 44개의 HEAD·브랜치·태그·stash·원격 추적 ref 116개를 검사했다. `st4f734-tight724/integration724`의 `origin/*` 4개(커밋 11개)는 어디에도 없어서 `git/tight724-origin-4refs.bundle`(174,049 B)로 보존했고 fetch 검증을 통과했다. 이제 미보존 ref는 0개다. 7차가 「보존 완료」라고 한 후보에도 이 구멍이 있었다.

## 참조·의존 (모두 scratch 안)

검사 범위는 `C:/_proj`, Hermes 전체, frog-npu-dev, `.codex`, Desktop이다. 디렉터리 339,590개를 읽었고 오류는 0이었다. scratch 밖에서 63개를 가리키는 junction·alternates·worktree는 0개다.

- **alternates**: 18개 저장소가 `st4f740-review-20261029/repo/.git/objects`를 객체원으로 쓴다. st4f740은 의존 폴더를 먼저 지우고 마지막에 지워야 한다.
- **worktree**: `st4f729-followup/repo`는 `teamflow-unowned/repo`의 worktree다. 두 폴더는 함께 지운다.
- **node_modules junction 39개**: 사본끼리 체인으로 연결돼 있다(예: storage → independent → after740 → st4f734-independent). 링크만 지우고(`os.rmdir`) 대상은 따라가지 않는다.
- worktree 3개(`st4f597-review/repo`, `st4f729-independent/repo`, `teamflow-next/repo2`)는 허브(guguroute scratch `st4f711-backend-20261029-v1`)가 이미 지워져 Git으로 판정할 수 없다. 내용 대조로 보존했다(위 복원 시험의 하나).
- 프로세스 참조는 07:3x 기준 229개 중 0개다(이 세션 제외). `postmaster.pid`는 없다. 63개의 최신 쓰기는 10-30 00:35 이전이다. 11-01 이후 Hermes 세션 중 이 경로를 쓴 것은 디스크 조사·감시 세션뿐이다.
- wiki 문서 다수가 scratch 안 경로를 링크한다. 지우면 링크가 끊긴다. 그러나 내용은 manifest로 복원할 수 있으므로 매핑은 이 보고서와 보존 README에 남긴다.

## 소유자

63개 중 56개는 생성 Codex 스레드를 특정했다. 방법은 rollout의 첫 도구 호출 언급 시각이 폴더 생성 시각과 11초 안에 맞는지 보는 것이다(대부분 0–0.6초). 결과는 [owners3.json](../evidence/2026-11-03_scratch-unique-approval/owners3.json)과 표의 「생성 Codex 스레드」 열에 있다. 나머지 7개는 미특정이다: `st4f719-blocker-independent`(wiki상 중단된 delegation `deleg_20889115`의 사본), `st4f719-blocker-fix`, `st4f719-privacy-independent`, `sft-synth-prep-20261031`, `teamflow-manager-20261029-{1745,1914,2000}`. 실행 중인 codex·claude 프로세스는 없다.

## 경로별 삭제 승인 목록 (요약 — 전체 63행은 [표](../evidence/2026-11-03_scratch-unique-approval/list.md))

| 묶음 | 폴더 | 바이트 | 조건 |
|---|---|---:|---|
| ① 7차 후보 | `st4f719-fix-20261029`, `st4f719-identity-20261029`, `st4f734-tight724-20261029` (폴더 전체) | 16,353,443,130 | 보존 완료. identity를 지우면 `st4f719-independent`의 junction이 끊기므로 ③과 함께 |
| ② HOLD 후보 | `st4f719-blocker-independent`, `teamflow-product-next`, `teamflow-next-after740`, `st4f719-privacy-independent` | 12,463,029,463 | 코드는 파일 단위로 복원할 수 있다(실증 포함). 통합 담당이 다시 열 때 manifest로 복원한다. 사용자 결정 |
| ③ 나머지 일반 | 위를 뺀 56개(마지막 `st4f740-review-20261029`, `teamflow-unowned`는 `st4f729-followup`과 함께) | 54,610,740,447 | 보존 완료 |
| ④ `.tmp/clones` | `hold3-integ-1102`, `hold3-eks-precision-r18`(폴더만. `.disk_guard_ledger.json`은 설정이므로 남김) | 9,839,389,277 | 36cd5c 재사용 불필요. ref 11/11 보존, 작업 트리 5개 `status` 0줄 |

**권하는 실행 방법**(AGENTS.md가 재귀 삭제를 용량 확보 수단으로 금지하므로 승인 때 함께 정한다):
1. 직전에 manifest와 크기·mtime 대조, 프로세스 재확인, 새 소유자 세션 확인.
2. junction은 링크만 `os.rmdir`.
3. manifest에 있는 파일만 지우고 빈 디렉터리를 아래부터 지운다.
4. 경로 부재와 보존본 `SHA256SUMS.txt`를 재확인한다.

## NPU 소유자 추가 회수 (frog-npu-dev, 달성 뒤 생성분 고유 65.28GB)

- 06:39:19 기존 소유자 세션 `local-445eeffb…`(기본 프로필 Desktop)에 안전 경로(resume → submit → plain detach)로 전달했다. admission은 `87ad9621…`(started → completed)이고 세션은 열려 있다. 첫 줄 `ACK-NPUDISK2-1103`는 쓰지 않았지만 즉시 작업했다. 06:48:57 `RESULT-NPUDISK2-1103`.
- 후보 6개를 구체 경로·바이트로 요청했다. 그중 실행된 것은 **244,521,087 B**다.
  - `toolchain/downloads`의 CMake·LLVM·Ninja zip 3개 238,561,407 B 삭제. 풀어 둔 사본의 구성원 대조 후 실행했다.
  - `owned-mapped-*`의 같은 logits 2개 5,959,680 B를 하드링크로 교체했다.
  - 이 세션이 다시 확인했다: zip 폴더가 비었고, 세 경로가 inode 1개(nlink 3)이며 sha256이 같다.
- 보존 사유(소유자 판정, `_coord/disk1103b-exclusions.md`):
  - F16 GGUF 8,665,620,256 B: README가 「matched-reference용으로 유지」라고 적었다.
  - `weights/` 8,411,974,960 B: 엔진 재생성에 필요하다.
  - 엔진 전부: `h1-eps3` attention·FFN 5.28GB는 **사용자 승인 필요**, `h16-here` 8.04GB는 소유·사용 여부 미확정.
  - ONNX: 그래프 증거로 지정돼 있다.
  - 중간 덤프: 게이트가 참조한다.
  - `export-venv` 4.10GB: WSL 금지로 재생성을 검증할 수 없다.
- 소유자 측정 여유는 273,382,891,520 → 272,298,156,032 B였다. 줄어든 것은 같은 시간 이 세션의 객체원 fetch(0.72GB)·스캔 파일 등 동시 쓰기 때문이다. 이후 정리했다.

## 남은 것 (400GB까지)

- ①–④ 승인·실행 후 약 363.8GB. 남는 약 36GB 후보는 다음과 같다. 모두 사용자 결정이 필요하다.
  - NPU `h16-here` 8.04GB와 `h1-eps3` 은퇴 5.28GB(공유 하드링크라 실제 회수는 더 작다).
  - F16 GGUF 8.67GB: 재생성할 수 있으나 정렬 스크립트를 다시 돌려야 한다.
  - `hiberfil` 13.10GB: 관리자 `powercfg /h off`.
  - `_unified_mall_3` 25.31GB.
  - WSL vhdx 내부 정리와 압축: `wsl --shutdown`과 관리자 권한이 필요하다.
- 동시 작업 때문에 06:33 273.44GB에서 07:46 270.53GB로 줄었다. 그중 약 1.2GB는 이 세션이 만들었다가 지운 작업 파일이고, 보존본 0.65GB는 남는다. 나머지는 원인을 확인하지 않았다.

## 증거

[evidence/2026-11-03_scratch-unique-approval/](../evidence/2026-11-03_scratch-unique-approval/)에 다음을 넣었다.
- approval_list·표
- refcheck(ref 116개)·tarcheck·owners3
- preserve_result·restore_test
- NPU 요청문
- 스크립트

전체 manifest·store·bundle·Git 정보·참조 원자료는 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/c400-unique-20261103/`에 있다(`README.md`, `SHA256SUMS.txt` 118행). 프로세스 명령줄 원문과 `*-private.json` 내용은 증거에 넣지 않았다.
