---
type: handoff
title: scratch 400GB 달성 뒤 사본 63개 보존 완료·경로별 삭제 승인 목록, NPU 추가 회수 0.24GB (2026-11-03)
description: 63개 폴더(83.43GB)의 모든 파일을 보존 Git 객체와 대조했고, 재현 불가분 2.97GB를 압축 보존(0.52GB)했으며, 복원 시험 62,914/62,914 일치. 삭제 0. 사용자 경로별 승인만 남았다. NPU 소유자는 추가 요청을 수락해 0.24GB를 회수했다
status: active
domain: ops
impl_scope: 운영 기록. guguroute backups/c400-unique-20261103 작성, wiki 보고서·증거·인계 추가. scratch·.tmp/clones·코드·Git·설정·다른 프로필·모델·WSL 변경 0, 프로젝트 파일 삭제 0
---

# scratch 고유 분류·승인 목록 — 인계 (2026-11-03 07:50 KST)

보고서: [2026-11-03_scratch-unique-classification-approval](../records/reports/2026-11-03_scratch-unique-classification-approval.md). 세션은 `20261103_062810_3836ad`(부모 `20261103_032201_d047d36a`)이고, 단위는 GB = 10⁹ B다.

## 사실

- 07:46 C: 여유는 270,532,591,616 B다. 동시 쓰기로 06:33 273.44GB보다 줄었다.
- 400GB 달성 뒤 생긴 scratch 폴더는 63개, 83,427,213,040 B다. 모두 보존이 끝났다.
  - 보존 Git으로 재현: 49.68
  - 캐시: 15.29
  - .git 객체: 12.61
  - tar 재생성: 2.60
  - 새 보존: 2.97(압축 0.52)
  - 기존 보존 동일: 0.28
- ref 116/116이 보존돼 있다. 새 bundle `git/tight724-origin-4refs.bundle`을 포함한다.
- 실행 전 확인 결과:
  - 프로세스 참조 0개
  - scratch 밖에서 들어오는 링크 0개
  - 최신 쓰기 ≤10-30 00:35
- 보존 위치: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/c400-unique-20261103/`
  - `README.md`에 복원 절차가 있다.
  - `manifest/` 82개
  - `store/` 20,248개
  - `SHA256SUMS.txt`

## 다음 담당자가 할 일

1. 사용자에게 **경로별 승인**을 받는다. 목록은 [list.md](../records/evidence/2026-11-03_scratch-unique-approval/list.md)·`approval_list.json`(63행)과 `.tmp/clones/{hold3-integ-1102, hold3-eks-precision-r18}`이다.
   - ① 7차 3개: 16.35GB
   - ② HOLD 후보 4개: 12.46GB. 코드는 manifest로 복원할 수 있다
   - ③ 나머지 56개: 54.61GB
   - ④ clones 2개: 9.84GB
   - 합계 93.27GB
2. 승인되면 다음을 순서대로 지킨다.
   - 직전에 manifest와 크기·mtime를 대조하고, 프로세스·새 소유자 세션을 확인한다.
   - junction은 링크만 지운다.
   - `st4f740-review`는 alternates 의존 18곳을 지운 뒤 마지막에 지운다.
   - `teamflow-unowned`와 `st4f729-followup`은 함께 지운다.
   - `.tmp/clones/.disk_guard_ledger.json`은 남긴다.
   - 지운 뒤 경로 부재와 `SHA256SUMS.txt`를 확인한다.
3. 400GB까지 남는 약 36GB는 사용자 결정 대상이다.
   - NPU `h16-here` 8.04, `h1-eps3` 은퇴(승인 필요), F16 GGUF 8.67
   - `hiberfil` 13.10(관리자)
   - `_unified_mall_3` 25.31
   - WSL 내부 정리

## NPU 소유자 (`local-445eeffb…`, 기본 프로필 Desktop)

- 06:39:19에 전달했다(admission `87ad9621…`). ACK 줄은 없었지만 수락하고 실행했으며, 06:48:57 `RESULT-NPUDISK2-1103`을 보냈다. 세션은 열려 있다.
- 실행 결과: zip 3개 238,561,407 B 삭제, 하드링크 5,959,680 B. 이 세션이 zip 부재와 inode·sha256을 재확인했다.
- 나머지는 소유자가 보존으로 판정했다. 사유는 `frog-npu-dev/_coord/disk1103b-exclusions.md`에 있다.

## 주의

- 이 세션의 작업 폴더 `guguroute cache/scratch/c400-unique-1103`은 24시간 동안 쓰지 않으면 정리된다. 객체원(`refrepo.git`)과 스캔 원본은 이미 지웠다. 필요한 사본은 backups와 wiki 증거에 있다.
- 복원에는 GitHub, 원본 `.git` 객체, guguroute backups bundle이 필요하다. 원본 local 브랜치에만 있는 객체도 쓰므로 원본 `.git`은 유지해야 한다.
- 원본 `.git`은 ref 파일을 읽기 전용으로 읽고 객체를 alternates로만 참조했다. 마지막에 새 wiki 파일 3개의 추적 상태를 보려고 원본에서 `GIT_OPTIONAL_LOCKS=0 git status --short --ignored -- <3경로>`를 한 번 실행했다(조회 전용, `tools/safe_git.py`는 이 셸에서 WinError 5). 결과는 3개 모두 미추적(`??`)이고 커밋·푸시는 0이다.

## 후속 (2026-11-03 16:03 추가)

- 이 목록의 ①②③④ 65개 루트는 사용자 지시(15:51:20 「정리 하라고」·15:53:41 「무조건 프로젝트폴더 용량 확보」)와 총괄 세션의 범위 해석(②·③은 확대 해석, [정정](../records/reports/2026-11-03_scratch-approved-deletion-independent-verification.md))에 따라 16:03까지 모두 삭제됐다(93,266,602,317 B, 건너뜀 0). 이 문서의 「삭제 0건」은 작성 시점 기준이다 → [실행 보고서](../records/reports/2026-11-03_scratch-approved-deletion-and-project-prep.md)
