---
type: report
title: C: 400GB 실제 달성 시점(10-27 20:21, 약 437GB) 대비 현재 증가분 — 이후 생성분 196GB·제자리 증가 53GB, 승인 대상 정확 목록
description: 세션 DB·wiki·감시 cron에서 C: 여유 400GB 이상 실측을 찾아 단위를 맞추고, 그 시점 뒤 생성·증가한 경로를 현재 드라이브 재고(NTFS 생성 시각·하드링크 1회 계산)로 정량화했다. 삭제는 0건이다. 보존이 비어 있던 HEAD 커밋 3개는 bundle로 보존했다. 400GB로 되돌리는 실행 대상은 모두 경로별 사용자 승인 또는 다른 소유자·관리자 결정이 필요하다
status: done
domain: ops
impl_scope: 읽기 전용 재고·세션 DB 조회. 추가 파일은 이 보고서, 증거 폴더 2026-11-03_c-drive-400gb-peak-diff, 인계 1개, 인계 목차 한 줄, guguroute backups/c400-peak-diff-20261103(bundle 3개 27KB)뿐이다. final_workspace 자료·코드·Git, 다른 프로필, 모델, NPU, WSL, 시스템 설정은 바꾸지 않았다. 삭제 0
---

# C: 400GB 실제 달성 시점과 지금의 차이 (2026-11-03 06:10–06:30 KST)

단위는 GB = 10⁹ B, GiB = 2³⁰ B다. 대상은 이 PC의 C: 하나(전체 1,022,083,010,560 B = 1022.08GB = 951.9GiB)다. 앞선 기록은 [10차](2026-11-03_c-drive-400gb-cleanup-round10.md)·[10차 후속 인계](../../handoff/2026-11-03_c-drive-round10-owner-relay.md)·[단위 정정](2026-10-28_c-drive-free-space-units-and-scratch-cleanup.md)이다.

## 결론

- **400GB는 실제로 달성된 적이 있다.** 10-27 20:21 `df -h` 407G(GiB 단위) = **약 437GB**(df 반올림 때문에 436.5–437.6GB 범위)다. 파이널스페이스 삭제 세션이 보고한 「436.6GB」도 GB 단위가 맞다. 바이트로 남은 마지막 400GB 이상 값은 10-27 21:59 **403,961,397,248 B(404.0GB)**다. 10-28 00:58 409GB까지는 400GB를 넘었고, 04:01 392GB부터는 아래였다. 400GB 이상이었던 시간은 약 5–8시간이다. 목표값이 아니라 실측값이다.
- 10-31 이후 감시 cron `a19614eada92`의 최고값은 11-02 22:49 259.30GB다. 그 기간에 400GB를 넘은 기록은 없다.
- **현재**: 06:15 실측 **273,446,379,520 B = 273.45GB = 254.67GiB**. 사용량은 585.5GB에서 748.6GB로 **+163.2GB** 늘었다.
- **차이의 원인**(아래 표): 달성 뒤 새로 생긴 파일이 약 196GB, 제자리에서 커진 파일이 53.5GB(WSL vhdx +38.4, pagefile +15.1)다. 같은 기간 달성 시점에 있던 guguroute·기본 프로필 scratch 약 78GB를 지웠다. 그래서 순증가는 +172GB이고, 실제 +163.2GB와 약 9GB 차이가 난다. 이 차이는 숨김 영역과 추정 오차다.
- **400GB를 다시 만들려면 지울 대상**은 그때 없던 것들이다. ① `final_workspace/scratch`의 10-29 작업 폴더 67개 83.43GB, ② `.tmp/clones` 9.84GB, ③ `frog-npu-dev` 65.28GB, ④ WSL 증가분 38.4GB 순이다. ①+②만으로는 약 367GB가 되고, ③이나 ④ 가운데 약 33GB가 더 필요하다. 모든 항목이 경로별 사용자 승인(AGENTS.md)이나 다른 소유자·관리자 결정을 요구하므로, 이 회차에서 지운 것은 없다.

## 400GB 달성 경위 (10-27, 원기록)

| 시각 | 여유 | 원 표기 | 사건 | 출처 |
|---|---:|---|---|---|
| 10-27 16:36 | 2.2GB | shutil/2³⁰ 2.08 | 거의 가득 참. 에이전트 scratch 348GB가 원인(당시 사용 867.6GB) | guguroute state.db 감사 요약(세션 094be4 메시지 65373) |
| 10-27 오후 | — | — | 휴지통 +23.6GB, Nemotron 모델 삭제 +71.6GB, 1차 재생성물 +20.1GB, scratch 3차 230개 삭제(보존 `_archive_20261027`) | [Hi 감사 인계](../../handoff/2026-10-28_hi-telegram-session-audit.md) 44–47행 |
| 10-27 20:00–20:22 | 246.1→436.6GB | 246.1 단위 미확정 | `C:/_proj/파이널스페이스` 삭제 64.49GiB(69.2GB) | [이관·삭제 보고](2026-10-26_finalspace-migration-and-removal.md) |
| **10-27 20:21** | **≈437GB** | df 407G | 최고치 | 감사 요약 |
| 10-27 21:59 | 403,961,397,248 B | 바이트 | | 감사 요약 |
| 10-28 00:16 / 00:58 | 414.53 / ≈409GB | GB / df 381G | | 감사 요약 |
| 10-28 04:01 | ≈392GB | df 365G | 400GB 아래 | 감사 요약 |

- 10-27 20:55의 `SizeRemaining 442,512,584,704`는 10-24 16:35 출력을 다시 인용한 값이라 제외했다.
- Hi 세션 `ce47d8ba`의 원문 행은 11-02에 지워졌다. 그래서 위 오후 정리 수치는 인계 문서의 기록을 그대로 쓴다.

## 달성 시점 대비 지금 — 원인별 (현재 바이트)

방법: 06:13–06:16에 재분석 지점을 따라가지 않고 드라이브 전체를 셌다. 256KiB 이상 하드링크는 inode 하나로 한 번만 셌다. 파일별 NTFS 생성 시각이 10-27 20:21 이후이면 「달성 뒤 생성」으로 분류했다. 같은 볼륨 안의 이동은 생성 시각을 유지하므로, 옮긴 파일은 새 파일로 세지 않는다. 증거: [post-peak-by-path.json](../evidence/2026-11-03_c-drive-400gb-peak-diff/post-peak-by-path.json), [inventory-now-summary.json](../evidence/2026-11-03_c-drive-400gb-peak-diff/inventory-now-summary.json).

| # | 경로 | 달성 때 | 지금 | 증가 | 소유·성격 | 회수 조건 |
|---|---|---:|---:|---:|---|---|
| A | `C:/_proj/final_workspace/scratch` 10-29 생성 67개 | 0 | 83.43 | **+83.43** | 10-29 ST4F·TeamFlow 작업 사본(작업자 세션 다수) | AGENTS.md 경로별 승인. 아래 「정확한 대상」 |
| B | `C:/Users/kcxsz/frog-npu-dev` (10-27 23:53 생성) | 0 | 65.28 고유(논리 95.10) | **+65.28** | NPU 실험, 기본 프로필 Desktop 세션 | NPU 소유자 결정. 동결 `.logits` 21.1GB는 이미 하드링크 통합 |
| C | WSL `AppData/Local/wsl/.../ext4.vhdx` | 9.18 | 47.59 | **+38.41** | 안쪽 EKS 사본 약 35GB(8차 추정). 제자리에서 커짐 | EKS 소유자 내부 정리 + `wsl --shutdown` + 관리자 압축 |
| D | 기본 프로필 `hermes/cache/scratch` 새 파일 | — | 16.63 | +16.63 | 다른 프로필(GHelper·펌웨어·NPU UI) | 그 프로필 소유자 |
| E | `C:/pagefile.sys` | 51.5 | 66.57 | +15.07 | 시스템 관리 크기. 11-02 20:34 부팅 때 커짐 | 사용자+관리자. NPU commit 여유 때문에 줄이지 않는 편을 권한다 |
| F | `final_workspace/.tmp/clones` 2개 | 0 | 9.84 | +9.84 | HOLD 3(36cd5c). 재사용 불필요, bundle 확인 4/4 | 경로별 승인만 있으면 바로 삭제 가능 |
| G | guguroute `backups` | 0 | 6.65 | +6.65 | 정리 회차의 보존본(bundle·고유 파일) | 보존. 지우지 않음 |
| H | `Downloads` 새 파일 | — | 3.68 | +3.68 | 사용자 원본 | 대상 아님 |
| I | guguroute scratch 새 항목 | — | 2.93 | +2.93 | `schedule-explain-impl-20261029` 1.65(설명 작성기 후보, 삭제 방식 결정 대기), `finalspace_preservation` 1.07(보존) | 보존 결정 대기 |
| J | 기타(`final_project_cs` 1.13, Program Files 1.72, Local/Microsoft 1.02, Discord 0.89, CrashDumps 0.88, puccinialin 0.67, `_preserved` 0.75 등) | — | ≈7.8 | +7.8 | 각 앱·프로젝트 | 개별 |
| — | **증가 합계** | | | **≈249.7** | 생성 196.2 + 제자리 53.5 | |
| K | guguroute scratch 달성 시점분 | ≈101.1 | 32.2 | −68.9 | 10-28~11-03 정리 회차 | |
| L | 기본 프로필 scratch 달성 시점분 | ≈37.0 | 28.06 | −8.9 | 그 프로필이 정리 | |
| — | **순증가(보이는 영역)** | | | **≈+171.9** | 실제 사용 증가 +163.15 | 차이 −8.8GB는 아래 참조 |

- 달성 때 K·L 크기는 10-28 21:43 감사(논리 크기)에서 「10-27 20:20 이후 생성분」을 뺀 추정이다. 다른 행의 「달성 때」 값은 같은 감사의 실측이다(pagefile 48GiB, vhdx 9.18GB, 모델 116.1GB 불변).
- **바뀌지 않은 것**: Hermes 모델 116.12GB, `datasets` 34.07GB(10-27 이관 4.72GB 포함, 모두 달성 전 생성), `_unified_mall_3` 25.31, `test_workspace` 12.65, `C:/_proj/guguroute` 10.31(모두 10-24 생성, 달성 때 있었음), `hiberfil.sys` 13.10.
- **숨김 영역**: 사용량 748.64GB에서 보이는 고유 바이트 583.06GB, pagefile, hiberfil, swapfile을 빼면 **85.9GB**다. 여기에는 읽을 수 없는 `WindowsApps`(9차 17.19GB), `System Volume Information`(VSS), 메타데이터가 들어 있다. System 로그 Volsnap 33(상한 유지를 위한 가장 오래된 스냅숏 삭제)이 10-28부터 11-03 05:54까지 반복되므로, VSS 차분 영역은 상한에 닿아 있다. 10-27 14:35 Volsnap 24·35는 디스크가 가득 차 C: 스냅숏 전체가 중단된 사건이다. 달성 시점의 숨김 크기는 기록이 없다. 위 순증가 합계가 실제와 9GB 안에서 맞으므로 **VSS 증가가 주원인은 아니라고 판단한다(추정)**. 크기 확인에는 관리자 `vssadmin list shadowstorage`가 필요하다. 이 세션은 `IsInRole(Administrator)=False`다.
- 10-28 감사가 「숨김 0」으로 맞아떨어진 것은 논리 크기가 로컬 clone 하드링크와 WinSxS를 두 번 센 결과로 보인다(추정). 그 수치로 숨김 증가를 계산하지 않았다.

## 정확한 대상 — A·F (92행, 경로·바이트·HEAD 보존·미커밋 줄 수)

전체 목록: [final-scratch-clones-candidates.json](../evidence/2026-11-03_c-drive-400gb-peak-diff/final-scratch-clones-candidates.json). `final_workspace/scratch` 91개(83,989,721,549 B)와 `.tmp/clones` 1개(2개 사본 합 9,839,390,371 B)로, 합계 **93,829,111,920 B**다.

- 생성 시각: scratch 91개 가운데 67개(83,427,298,236 B)가 10-29 생성이다. 나머지 24개(562,423,313 B)는 10-24 생성으로 달성 때도 있었다. 최신 쓰기는 scratch 10-31 03:32, clones 11-03 05:26(36cd5c 정리)이다. 06:24 프로세스 명령줄·실행 경로 참조는 0개다(이 세션 제외).
- HEAD 보존(깊이 4 안의 Git 루트 58개): 팀 원격(10-29 fetch 기준 `team/role-manager` 등)에 있는 것은 `fab3da50a`·`efeb873a8`·`006268853`·`3dd9bd70c`이고, bundle로 있는 것은 `656579fe3`(7차)와 HOLD 3 4개다. 남은 3개 `6573e2067`·`cf8d97603`·`e96347fd7`(5개 폴더 11.76GB)는 이번에 guguroute `backups/c400-peak-diff-20261103/head-*.bundle`로 보존했다(필요 커밋 `fab3da50a`, hold3 clone에서 `bundle verify` 3/3 통과, `SHA256SUMS`). 이제 HEAD 커밋이 보존되지 않은 루트는 0개다.
- **남은 보존 작업**: 미커밋 변경이 있는 폴더 27개(70.34GB, 줄 수 1–20,662). 줄 수가 수천인 것(`bus-independent` 20,662, `teamflow-next-after740/repo` 19,227, `st4f719-blocker-independent` 10,756 등)은 CRLF 표류나 긴 경로 체크아웃 실패일 가능성이 크지만 확인하지 않았다. Git이 아닌 폴더 37개(7.25GB)에는 로그·pgdata·증거가 있다. 삭제 전에 7차와 같은 방식(`diff HEAD --binary`·미추적 파일 복사·.git 메타)으로 폴더별 보존본을 만들어야 한다. 7차의 3개(16.35GB)는 이미 끝났다.
- `.tmp/clones` 2개는 36cd5c가 「재사용 불필요·미커밋 0·bundle verify 4/4」라고 보고했다. 보존 작업 없이 승인만 받으면 지울 수 있다.

## 400GB까지 (06:15 기준 부족 126.55GB) — 권하는 순서

1. 사용자 경로별 승인: F `.tmp/clones` 2개(9.84) + 7차 3개(15.95, 보존 완료) → 즉시 실행 가능. 25.79GB를 회수해 약 299GB가 된다.
2. A의 나머지 88개(68.04GB): 폴더별 보존본을 만든 뒤 승인을 받아 삭제한다. 1과 합치면 93.83GB, 여유는 약 367GB가 된다.
3. 남는 약 33GB는 다음 셋 중 하나로 채운다. (a) NPU 소유자가 `frog-npu-dev`의 끝난 실험을 정리(고유 65.28GB 중 33GB 이상), (b) EKS 소유자가 WSL 안 사본을 정리하고 관리자가 vhdx를 압축(증가분 38.4), (c) `hiberfil` 13.10(관리자 `powercfg /h off`) + `_unified_mall_3` 25.31(사용자 결정, 달성 때도 있던 자료).
- 동시 작업이 계속 쓰므로(10차 9분에 −0.75GB) 달성을 보장하지 않는다. 모델 116GB와 기본 프로필은 계산에서 뺐다.

## 이 회차에 한 일과 하지 않은 일

- 지운 것은 0 B다. 승인 이력(10-31 「각 세션이 자기가 만든 용량 정리」, 10-31 `C:/_proj` 루트 38개)에 들어가는 자기 작업 잔여물 중 남은 대용량은 없었다. guguroute scratch의 달성 뒤 생성분 2.93GB는 보존·결정 대기 항목이다.
- 만든 것: bundle 3개 27,336 B(위 경로), 이 보고서, 증거 폴더(스크립트·JSON), [인계](../../handoff/2026-11-03_c-drive-400gb-peak-diff-handoff.md)와 인계 목차 한 줄.
- 한계:
  - `tools/safe_git.py`는 이 셸의 Python에서 git을 실행하지 못했다(WinError 5). 그래서 HEAD 판정은 원본 Git이 아니라 hold3 clone의 `team/*` 원격 참조(10-29 fetch)로 했다.
  - WSL 내부 사용량은 재지 않았다(`wsl.exe` 호출 금지).
  - 숨김 영역과 VSS 차분 크기는 관리자 권한이 필요하다.

## 후속 (2026-11-03 17:2x 추가)

- 이 문서가 승인 대상으로 든 scratch·`.tmp/clones` 사본 65개(93.27GB)는 16:03까지 삭제됐다. 17:06 C: 여유 349.02GB, 400GB까지 50.98GB 부족 → [실행 보고서](2026-11-03_scratch-approved-deletion-and-project-prep.md)
