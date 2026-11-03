---
type: handoff
title: C: 400GB 실제 달성 시점 대비 증가분 — 승인 대상 정확 목록과 남은 보존 작업 (2026-11-03)
description: 10-27 20:21 약 437GB(실측) 뒤 생긴 경로를 정량화했다. 400GB로 돌아가는 실행 대상과 각 대상의 승인·보존 상태를 넘긴다. 삭제 0, HEAD bundle 3개 보존
status: active
domain: ops
impl_scope: 운영 기록. 읽기 전용 조사와 guguroute backups bundle 3개 작성만 했다. 제품 코드·Git·서비스·설정·모델·다른 프로필 변경 0, 삭제 0
---

# C: 400GB 달성 시점 대비 증가분 — 인계 (2026-11-03 06:30 KST)

보고서: [2026-11-03_c-drive-400gb-peak-vs-now](../records/reports/2026-11-03_c-drive-400gb-peak-vs-now.md). 세션은 `20261103_060955_07d127`(부모 `20261103_032201_d047d36a`)이고, 단위는 GB = 10⁹ B다.

## 사실

- 400GB 실제 달성: 10-27 20:21 약 437GB(df 407GiB)이고, 10-28 00:58까지 유지됐다. 바이트로 남은 값은 21:59 403,961,397,248 B다.
- 현재: 06:15 273,446,379,520 B이고 부족분은 126.55GB다. 사용량은 달성 때보다 +163.15GB다.
- 증가 원인(현재 바이트):

| 원인 | 증가 |
|---|---:|
| `final_workspace/scratch` 10-29 작업 사본 67개 | 83.43 |
| `frog-npu-dev`(고유) | 65.28 |
| WSL vhdx 증가 | 38.41 |
| 기본 프로필 scratch 새 파일 | 16.63 |
| pagefile 증가 | 15.07 |
| `.tmp/clones` | 9.84 |
| guguroute backups | 6.65 |
| 기타 | ≈14.4 |
| 같은 기간 정리한 달성 시점 scratch | −77.8 |

## 다음 담당자가 할 일 (순서)

1. 사용자에게 **경로별 삭제 승인**을 요청한다. 목록은 증거 `final-scratch-clones-candidates.json`에 있다.
   - 즉시 실행할 수 있는 것: `C:/_proj/final_workspace/.tmp/clones/hold3-integ-1102`(7,219,351,447 B), `.../hold3-eks-precision-r18`(2,620,037,830 B), 7차 3개 체크아웃(15,950,881,145 B, 보존 완료). 합계 25.79GB다.
2. `final_workspace/scratch` 나머지 88개(68.04GB)는 미커밋 27개 폴더의 `diff HEAD --binary`, 미추적 파일, .git 메타를 7차 방식으로 보존한 뒤 승인 요청 → 삭제한다. HEAD 커밋은 모두 보존돼 있다(팀 원격 / 7차 bundle / 이번 `backups/c400-peak-diff-20261103/head-{6573e2067,cf8d97603,e96347fd7}.bundle`, 필요 커밋 `fab3da50a`).
3. 남는 약 33GB는 NPU 소유자(기본 프로필 Desktop `local-445eeffb…`) 실험 정리, EKS 소유자(36cd5c) WSL 안 정리 + 관리자 vhdx 압축, `hiberfil`/`_unified_mall_3` 사용자 결정 중 하나로 채운다.
4. 삭제 직전에 다시 확인한다. 크기와 mtime 변동, 프로세스 명령줄·실행 경로 참조, `state.db`에 같은 대상을 맡은 새 소유자 세션이 있는지 본다.

## 주의

- `tools/safe_git.py`는 Python에서 git을 실행하지 못한다(WinError 5). 원본 Git 판정이 필요하면 bash에서 실행할 방법을 먼저 정한다.
- 숨김 영역은 85.9GB이고 VSS는 상한에 닿아 있다(Volsnap 33 반복). 크기 확인에는 관리자 권한이 필요하다. `wsl.exe` 상태 조회는 하지 않는다.
- 이 세션의 조사 스크립트·원시 JSON은 guguroute `cache/scratch/c400-hist-1103/`에 있고, 24시간 동안 쓰지 않으면 정리된다. 필요한 사본은 증거 폴더에 있다.
