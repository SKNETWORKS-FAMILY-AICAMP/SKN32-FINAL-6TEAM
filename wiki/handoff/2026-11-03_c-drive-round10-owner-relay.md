---
type: handoff
title: C: 400GB 10차 후속 — 소유자 회수 전달(36cd5c·NPU) 수락·결과, 여유 273.45GB, 400GB까지 승인 대상 조합 (2026-11-03)
description: HOLD 3 사본 소유자 36cd5c와 frog-npu-dev 소유자(기본 프로필 Desktop 세션)에게 안전 경로로 회수 요청을 전달하고 수락·결과를 state.db와 디스크에서 다시 확인했다. 승인 이력을 직접 조회해 이미 승인된 범위만 실행시켰다. 남은 대용량 후보는 모두 경로별 사용자 승인·관리자·다른 소유자 결정이 필요하다
status: active
domain: ops
impl_scope: 운영 기록. 이 세션은 메시지 2건 전달과 읽기 전용 확인만 했다. 삭제·하드링크는 각 소유자가 자기 작업물에 대해 실행했다. 제품 코드·Git·서비스·설정·모델·다른 프로필 설정 변경 0, 프로세스 중지 0
---

# C: 400GB 10차 후속 — 소유자 회수 전달 (2026-11-03 05:40–06:02 KST)

앞선 기록: [10차 보고서](../records/reports/2026-11-03_c-drive-400gb-cleanup-round10.md), [HOLD 3 인계](2026-11-02_proj-root38-post-deletion-handoff.md). 단위 GB=10⁹ B. 보낸 세션: `20261103_053949_85eca4`(부모 `20261103_032201_d047d36a`).

## 결과

- C: 여유 **245,652,701,184 B → 273,448,869,888 B (+27.80GB)**. 목표 대비 273.45/400 = **68.36%**, 부족 **126,551,130,112 B (126.55GB)**.
- 늘어난 27.80GB 중 근거 있는 것: 36cd5c 삭제 1,543,581,236 B + NPU 하드링크 통합 21,105,213,440 B = **22.65GB**. 나머지 약 5.1GB는 같은 시간 다른 작업의 변화로 **미확인**이다.

## 소유자별 전달·수락·결과

| 소유자 | 현재 작업 상태(전달 전) | 전달 | 수락 | 결과(직접 재확인) |
|---|---|---|---|---|
| `20261024_213155_36cd5c` (guguroute, 라우팅/EKS) | 하위 3개(deleg_cfa750b4) 01:18까지 모두 종료. 완료 알림이 턴을 시작하지 못해 `RESULT-HOLD3-1102`가 밀려 있었음. 실행 프로세스 0 | 05:45:10 resume→submit→plain detach, admission `b6112a8c…` | 05:45:25 `ACK-DISK-1103 36cd5c`, admission completed, 세션 열림 | scratch `hold3-integ-1102`의 env312·mingit·mobdata·정지 PG·py312 등 **1,543,581,236 B 삭제**(남은 15,234,972 B는 스크립트·출력). 증거는 backups로 옮김(SHA256SUMS 213/213 재확인). `.tmp/clones` 2개는 **재사용 불필요** 판정, 커밋은 bundle에 있음(`hold3-local-branches.bundle` 등, verify 4/4, 미커밋 0) → **삭제하지 않고 승인 요청**. `RESULT-HOLD3-1102`와 인계 절 「HOLD 3건 실행 결과(36cd5c)」 작성 확인 |
| `local-445eeffb…` (기본 프로필 Desktop, 「컴퓨터의 NPU 연산 활용 방법 찾기」, frog-npu-dev) | 마지막 턴 10-31 04:23, 활성 lease·NPU 프로세스 0 | 05:46:29 같은 경로(HERMES_HOME=기본 프로필), admission `d6f8e1f1…` | 첫 줄 ACK는 쓰지 않았지만 즉시 작업 시작, 06:00 `RESULT-NPUDISK-1103`, admission completed, 세션 열림 | 동결 결과의 같은 sha256 `.logits` **363개를 NTFS 하드링크로 교체, 21,105,213,440 B**(삭제 0, 경로 유지). 이 세션이 manifest 363행을 다시 대조: inode 일치 363/363, nlink≥2, 보존본 26개. 남긴 중복 32그룹 약 3.99GB(위조 시험 입력·엔진·덮어쓸 수 있는 결과, 해시 미재계산). 스크립트는 새 디렉터리만 쓰고 검증 뒤 하드링크하도록 바뀜(시험 5개 통과, 소유자 보고) |

- 증거: 36cd5c 보고 `backups/hold3-integ-1102/`, `backups/hold3-eks-precision-r18-1102/`; NPU `frog-npu-dev/_coord/disk1103-frozen-logits/manifest.jsonl`, `disk1103-frozen-h1-paired/manifest.jsonl`, `disk1103-verification.json`, `disk1103-remaining.json`. 전달문·조회 스크립트: guguroute `cache/scratch/owner-relay-1103/`(24시간 미사용 시 정리됨).
- 위험: 하드링크된 NPU 결과 폴더는 한 경로를 제자리 수정하면 연결된 사본이 함께 바뀐다. 동결 유지가 조건이다.

## 승인 이력 직접 조회 결과

guguroute·기본 프로필 `state.db`의 사람 입력(telegram/desktop)에서 확인했다.
- 10-31 04:08–04:09: 「각 세션이 자기가 만든 용량을 알아서 지우면서 작업」 → 소유자 자기 산출물(중복 복사본·재생성 캐시) 정리는 승인됨. 이번 두 소유자 실행은 이 범위다.
- 10-31 19:49: 「저 리스트의 폴더들 하나도 남지 않게」 → `C:/_proj` 루트 지정 38개(이미 38/38 처리).
- `.tmp/clones` 두 사본, `final_workspace/scratch` 7차 3개·나머지, Flash-Next, hiberfil, NPU 잔여에 대한 **경로별 승인 기록은 없다**. 그래서 아래 표는 승인 요청이다.

## 400GB까지 — 대용량 후보 (06:00 기준, 부족 126.55GB)

| # | 정확한 경로 | 바이트 | 실사용·보존 상태 | 필요 승인 |
|---|---|---:|---|---|
| 1 | `C:/_proj/final_workspace/.tmp/clones/hold3-integ-1102` | 7,219,351,447 | idle, 소유자 재사용 불필요, 커밋 bundle 보존·verify | AGENTS.md 대상별 삭제 승인 |
| 2 | `C:/_proj/final_workspace/.tmp/clones/hold3-eks-precision-r18` | 2,620,037,830 | 같음(무시 파일은 `datasets/mobility` 복사본) | 같음 |
| 3 | `C:/_proj/final_workspace/scratch/{st4f719-fix-20261029, st4f734-tight724-20261029/integration724, st4f719-identity-20261029}` 체크아웃 | 15,950,881,145 | 7차에 bundle·diff·미추적·.git 메타 보존 완료. 3번은 다른 `node_modules` 링크가 끊김 | 대상별 승인 + 삭제 방법 결정(7차 보고서) |
| 4 | `C:/_proj/final_workspace/scratch` 나머지 87개 | 67,620,817,840 (폴더 합계) | 90/90 존재, 최상위 최신 쓰기 ≤10-31, 6차 시점 프로세스 참조 0. 보존본은 아직 없음 | 보존본 작성 뒤 대상별 승인. 목록: `wiki/records/evidence/2026-10-30_disk-round6/final-scratch-approval-candidates.json` |
| 5 | `C:/hiberfil.sys` | 13,096,894,464 | 최대 절전 파일 | 사용자 결정 + 관리자 `powercfg /h off`(시스템 설정) |
| 6 | `C:/_proj/_unified_mall_3` | 25,314,085,642 | 다른 프로젝트 | 사용자 결정 |
| 7 | `C:/_proj/test_workspace` | 12,652,794,811 | 다른 프로젝트 | 사용자 결정 |
| 8 | WSL `ext4.vhdx` | 47,585,427,456 | 안에 EKS 사본 약 35GB(8차 추정). 지금 WSL VM 미실행 | EKS 소유자 내부 정리 + `wsl --shutdown` + 관리자 압축 |
| — | Hermes 모델 Flash-Next 93,682,584,224 / 27B 16,464,440,224 | — | 모델 보존 규칙 | 계산에서 제외 |
| — | 기본 프로필 `hermes/cache` 44.71GB | — | 다른 프로필 | 제외 |

- **모델 없이 도달하는 조합**: 1+2+3+4 = 93.41GB, + 5 hiberfil 13.10GB + 6 `_unified_mall_3` 25.31GB = **131.82GB ≥ 126.55GB**(여유 5.27GB). 4·6 대신 7+8 안쪽 정리를 써도 된다. 모든 항목에 승인·관리자 실행이 필요하고, 동시 쓰기 때문에 결과는 보장되지 않는다.
- 즉시 실행할 수 있는 순서: 사용자가 1·2·3을 승인하면 보존본이 이미 있어 바로 지울 수 있다(25.79GB). 4는 보존본 작성이 먼저다.

## 미확인·남은 것

- +27.80GB 중 약 5.1GB의 출처.
- NPU 잔여 32그룹 3.99GB의 현재 해시, 기존 목록의 없어진 경로 26개.
- 36cd5c가 지운 `mingit`의 대체 git이 다른 작업에 필요한지(소유자 미확인 보고).
- WSL Ubuntu는 36cd5c 하위 작업이 11-02에 시작했고, 06:00에는 VM 프로세스가 없다. 종료하지 않았다.
