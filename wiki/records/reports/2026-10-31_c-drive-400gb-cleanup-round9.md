---
type: report
title: C: 400GB 9차 — Temp 브라우저·설치 임시 735.5MB 삭제(실측 +0.75GB), 숨김 공간 98.43GB 재측정과 시스템 복원 15% 상한 확인, 여유 209.46GB
description: 8차가 처리하지 않은 사용자 Temp의 유휴 브라우저 자동화 프로필·설치 임시 45개를 지웠다. 하드링크와 클러스터 반올림을 반영해 드라이브를 다시 셌다. 일반 권한으로 볼 수 없는 사용량은 98.43GB였다. 그 원인 후보로 현재 사용자 Appx 17.19GB와 시스템 복원(VSS) 설정을 실측했다. VSS 설정은 DiskPercent 15%이고, 상한 도달 이벤트가 있다. 400GB까지 190.54GB가 부족하다
status: done
domain: travel
impl_scope: 사용자 Temp의 playwright_chromiumdev_profile-* 23개, agent-browser-chrome-* 20개, WinGet, playwright-transform-cache만 삭제했다. 보존본과 manifest는 guguroute backups/disk-round9-20261031에 있다. 추가한 것은 이 보고서, 증거 폴더 2026-10-31_disk-round9, 인계 색인 한 줄뿐이다. final_workspace 자료·코드·Git, 8차 하드링크·보존 경로, C:/_proj 사본, 모델, NPU, 다른 프로필, WSL, 설정, 서비스는 변경하지 않았다
---

# C: 400GB 9차 (2026-10-31 04:09–04:53)

앞선 기록: [8차](2026-10-31_c-drive-400gb-cleanup-round8.md), [8차 독립 검토](2026-10-31_disk-round8-independent-review.md), [7차](2026-10-30_c-drive-400gb-cleanup-round7.md). 단위는 GB=10⁹ B다. **실측**은 이 회차에서 직접 센 값이고, **추정**은 확인하지 못한 판단이다.

## 결과

| 시각 | C: 여유 바이트 | GB | 비고 |
|---|---:|---:|---|
| 04:09 시작 | 207,939,317,760 | 207.94 | 8차 종료와 같다 |
| 04:25 Temp 삭제 직전 | 208,651,943,936 | 208.65 | |
| 04:25 Temp 삭제 직후 | 209,401,602,048 | 209.40 | **+749,658,112** |
| 04:52 최종 | 209,461,575,680 | 209.46 | |

- 이번에 지운 논리 바이트는 **735,547,156 B**(파일 9,837개, 루트 45개)다. 실측 여유 증가는 **749,658,112 B**다. 실패는 0개다.
- 목표 대비 여유는 **209.46 / 400 = 52.37%**다. **190,538,424,320 B (190.54GB)가 부족하다. 400GB는 달성하지 못했다.**
- 8차 독립 검토의 지적에 따라, 독립 보존본을 공유 저장으로 바꾸는 하드링크 통합은 이번에 하지 않았다. 8차 링크·보존 경로도 건드리지 않았다.

## 삭제한 것 — 사용자 Temp 735,547,156 B

| 묶음 | 루트 | 바이트 | 소유·재생성 근거 |
|---|---:|---:|---|
| `playwright_chromiumdev_profile-*` | 23 | 330,048,423 | Playwright가 실행할 때마다 새로 만드는 임시 브라우저 프로필이다. 정상 종료되면 스스로 지운다. 남은 것은 중단된 실행의 잔여물이다 |
| `agent-browser-chrome-*` | 20 | 227,994,217 | 브라우저 자동화 도구가 실행할 때마다 uuid로 새로 만드는 임시 프로필이다. 각 폴더의 `Crashpad/reports/*.dmp` 6개(약 1.37MB씩)는 종료 시 생긴 크래시 보고서다. wiki에서 이 경로를 근거로 쓰는 조사는 없었다(디스크 재고 기록만 있다) |
| `WinGet` | 1 | 115,815,011 | WinGet 설치 내려받기 캐시다. 70시간 동안 쓰기가 없었다 |
| `playwright-transform-cache` | 1 | 61,689,505 | Playwright 테스트 실행기의 변환 캐시다. 다음 실행 때 다시 만든다 |

- **선정 조건**: 루트 안 가장 최근 쓰기가 24시간을 넘었다. 재분석 지점이 0개이고, 모든 파일의 nlink가 1이다.
- **실행 중 제외**: Win32_Process 390개의 명령줄을 확인했다. 실행 중 chrome이 쓰는 `agent-browser-chrome-eb3a4bf3…`·`…468e7634…` 2개는 제외했다. 최근 11.2시간 안에 쓴 2개도 제외했다. 삭제 직전에 명령줄을 다시 확인했고, 계획 파일 목록·크기·mtime을 루트마다 다시 대조했다. 하나라도 다르면 그 루트를 건너뛰도록 했다(건너뛴 것 0개).
- **방식**: manifest에 있는 파일만 하나씩 지운 뒤 빈 디렉터리를 아래부터 지웠다. 45개 루트 모두 사라진 것을 확인했다.
- **복원**: 이 데이터는 다음 실행 때 도구가 새로 만든다. 원본 바이트 보존본은 만들지 않았다. 파일별 경로·크기·mtime은 backups `temp_plan.json`에 있다.

## 지우지 않은 Temp·앱 항목

| 항목 | 크기 | 이유 |
|---|---:|---|
| `Temp/hermes_agy_*` 19개 | 약 283MB | Antigravity CLI 임시 홈이다. 대화 기록(`brain/*/transcript*.jsonl`)과 `conversation_summaries.db`가 들어 있다. 캐시가 아니라 세션 기록이고, 어느 프로필 것인지 확인하지 못했다. 보존한다 |
| `Temp/node-compile-cache` | 479MB | 6시간 전에 썼다. 실행 중인 node가 쓰는 버전이 들어 있다 |
| `Temp/DiagOutputDir` | 226MB | 24시간 안에 생긴 회전 중 추적이다 |
| `Discord/app-1.0.9188`·`download`·`packages` | 약 0.53GB | Discord가 실행 중이다(9265). 설치된 앱의 갱신·롤백 자료다 |
| `~/.nuget/packages`, `AppData/Local/NuGet` | 0.77 + 0.20 | 여러 프로필의 .NET 빌드가 함께 쓰는 패키지 캐시다. 지우면 다음 빌드가 인터넷에서 다시 받아야 한다 |
| Edge `User Data` | 2.37 | 브라우저가 실행 중이다 |

조사한 다른 캐시 위치(`.cache`, pip, npm, D3DSCache, NVIDIA, WER(사용자), Explorer, INetCache, Packages, WinGet(Local), `C:/tmp` 33MB, `C:/Users/TEMP` 3MB, `C:/Users/sshuser` 0.27GB 등)는 모두 합쳐도 1GB 미만이었다. 증거는 [survey.json](../evidence/2026-10-31_disk-round9/survey.json)이다. **재생성 가능한 캐시로는 192GB 부족분을 채울 수 없다.**

## 숨김 공간 재측정 (04:33–04:46, 실측)

8차는 하드링크를 두 번 세었고, 클러스터 반올림도 하지 않았다. 이번에는 둘 다 반영해 드라이브 전체를 다시 셌다. 재분석 지점은 따라가지 않았다.

| 항목 | 바이트 | GB |
|---|---:|---:|
| 볼륨 크기 | 1,022,083,010,560 | 1,022.08 |
| 사용량 (스캔 종료 시점) | 812,615,856,128 | 812.62 |
| 보이는 파일 할당 추정 (inode당 1회, 4096 B 클러스터 반올림, 600 B 이하는 MFT 상주로 0) | 714,185,711,634 | 714.19 |
| 같은 inode를 두 번째 이후 경로로 센 바이트 (8차 합계에 섞여 있던 값) | 34,530,283,688 | 34.53 |
| **일반 권한으로 보이지 않는 사용량** | **98,430,144,494** | **98.43** |

- 파일 3,627,219개, 디렉터리 517,831개를 셌다. 읽지 못한 디렉터리는 142개다. 압축·sparse 파일은 127개(논리 0.12GB, 할당 0.06GB)뿐이었다.
- 하드링크 판정은 256KiB 이상인 파일과 `C:/Windows` 아래 전체 파일에만 했다. 그보다 작은 하드링크는 중복으로 세었을 수 있다. 그러면 숨김 사용량은 이 값보다 조금 더 크다.
- 8차의 「약 53.8GB」는 하드링크 34.53GB를 두 번 센 값이었다. 그래서 이번 98.43GB와 직접 비교할 수 없다. **둘의 차이를 증가로 해석하면 안 된다.**

### 98.43GB의 구성

| 원인 | 크기 | 근거 수준 |
|---|---:|---|
| 현재 사용자 Appx 패키지 (`Program Files/WindowsApps`, 목록 조회 거부 영역) | 17.19 (논리) | **실측**. `Get-AppxPackage`의 설치 위치를 하나씩 셌다. HermesAgent 4.04, StoryCube 2.95, PowerAutomate 1.26, Photos 1.12 등이다 |
| NTFS 메타데이터 (MFT 등) | 최소 약 4.2 | **추정**. 현재 레코드 약 4.15M × 1KiB로 잡았다. MFT는 줄어들지 않으므로, 앞선 회차에 지운 수백만 파일의 레코드만큼 더 클 수 있다. `fsutil fsinfo ntfsinfo`는 권한이 없어 거부됐다 |
| 나머지 (`System Volume Information`, 다른 SID 휴지통, `sshuser.H7407BA-SU344W`, WER ReportQueue 커널 보고 4개, Defender 등 142개) | 약 77 | **미측정**. 크기를 셀 권한이 없다 |

**시스템 복원(VSS)에 대해 권한 안에서 확인한 사실** ([vss_events.txt](../evidence/2026-10-31_disk-round9/vss_events.txt)):

- 레지스트리 `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore\cfg`의 `DiskPercent`는 **15**다. 볼륨의 15%는 **153.31GB**다. 이 값은 시스템 복원 저장소 **설정**이다. 현재 사용량은 아니다. 실제 상한(MaxSpace)은 관리자 `vssadmin list shadowstorage`로만 확인할 수 있다.
- 10-18부터 10-30까지 C: 스냅숏이 계속 만들어졌다. 만든 주체는 Windows Update(`wuauserv`), 예약 작업 `srtasks.exe ExecuteScheduledSPPCreation`, 서비싱 스택이다. 마지막 스냅숏은 **10-30 13:50**(`HarddiskVolumeShadowCopy29`)이다.
- Volsnap 33(「사용자 지정 한도를 넘지 않도록 가장 오래된 섀도 복사본 삭제」)이 10-25~10-29에 9번 기록됐다. Volsnap 36(「한도 때문에 저장소를 늘릴 수 없어 섀도 복사본 중단」)은 10-26·10-28·10-29에 기록됐다. 10-27 14:35에는 Volsnap 24·35(디스크 공간 부족으로 저장소 확장 불가)도 있었다. 즉 **VSS 저장소는 이번 주에 여러 번 설정 한도까지 찼다.**
- **추정**: 나머지 약 77GB의 가장 큰 부분은 10-30 13:50 스냅숏 이후 쌓인 VSS 차분 영역일 가능성이 높다. 스냅숏이 있는 동안에는 지우거나 덮어쓴 블록의 옛 내용이 차분 영역으로 복사된다. 그래서 정리로 비운 공간을 다른 작업이 다시 쓰면, 여유가 회수량만큼 늘지 않을 수 있다. 8차의 「원인 미상 약 17GB」도 이 동작과 맞는다. **다만 크기를 직접 재지 못했으므로 사실로 단정하지 않는다.**

## 공간 부족의 원인 — 실측 구성 (04:46 기준, 할당 추정)

| 구역 | GB | 상태 |
|---|---:|---|
| `C:/Users` (Hermes 234.8, WSL 47.5, frog-npu-dev 약 96, Downloads 8.6 등) | 388.21 | Hermes 모델 116.1, 기본 프로필 scratch 45.0, guguroute 프로필 70.4. 모두 사용자 모델·다른 소유자·보존 지정 범위다 |
| `C:/_proj` (final_workspace 133.2, `_unified_mall_3` 25.3, `test_workspace` 12.7, `guguroute` 10.3 등) | 199.70 | 프로젝트 대상별 승인 규칙, 다른 프로젝트, HOLD 범위다 |
| 숨김 (위 표) | 98.43 | 관리자 권한이 필요하다 |
| `pagefile.sys` | 66.90 | 시스템 관리 크기다. 8차 때 +9.84GB 늘었다 |
| `C:/Windows` (하드링크 1회) | 29.58 | 관리자 DISM이 필요하다 |
| `hiberfil.sys` | 13.10 | 관리자 `powercfg /h off`가 필요하다 |
| Program Files ×2, ProgramData | 16.65 | 설치 앱이다 |

## 400GB까지 190.54GB를 막는 것

8차 표([8차](2026-10-31_c-drive-400gb-cleanup-round8.md) 「할 수 없었던 것」)는 그대로 유효하다. 바뀐 점과 추가된 점은 다음과 같다.

- **VSS (신규 실측 근거)**: 숨김 약 77GB 중 상당 부분으로 추정한다. 설정 상한은 15%=153.31GB다. 풀려면 관리자가 `vssadmin list shadowstorage`·`vssadmin list shadows`로 먼저 실제 사용량을 확인해야 한다. 그다음 사용자가 복원 지점을 줄일지 결정한다. 예를 들어 `vssadmin resize shadowstorage /for=C: /on=C: /maxsize=<N>GB`로 상한을 낮추거나 오래된 복원 지점을 지울 수 있다. 이렇게 하면 시스템 복원 능력이 줄어든다. **이번 회차는 실행하지 않았다(권한이 없고 사용자 결정 사항이다).**
- **하드링크**: 8차 링크 중 보존 경로 18 inode(938,329,044 B)를 분리하면 공간이 **줄어든다**. 독립 검토의 A~E 선택지는 사용자 결정이다.
- **조합 예시**: VSS 상한 축소(실측 뒤 회수량 확정) + final_workspace scratch 유휴분 73.92 + Flash-Next 모델 98.74 + `hiberfil` 13.10을 더하면 VSS를 빼고도 185.76GB다. VSS 회수량이 5GB를 넘으면 목표에 닿는다. 하지만 각 항목은 사용자 승인이나 관리자 실행이 필요하다. 동시 증가(페이지 파일, VSS 차분, 다른 작업) 때문에 결과를 보장할 수 없다.

## 이 세션의 디스크 사용

- backups `disk-round9-20261031`은 약 2.4MB다(manifest·재고 JSON·스크립트). wiki 증거 폴더는 약 60KB다.
- 장시간 스캔은 메모리 여유가 1.8~2.0GB인 상태에서 돌렸다. 다른 작업의 프로세스는 멈추거나 끄지 않았다.

## 다음 인수

1. **관리자 확인 (사용자)**: `vssadmin list shadowstorage`, `vssadmin list shadows`, `fsutil fsinfo ntfsinfo C:`. 이 세 결과로 숨김 98.43GB 중 VSS와 MFT 몫을 확정한다.
2. **사용자 결정**: VSS 상한·복원 지점, 7차 final_workspace scratch 승인 목록, Flash-Next 모델 보존 여부, `hiberfil`, 8차 하드링크 분리 A~E.
3. **소유자 결정**: NPU 중복 25.57GB(`_coord` NOTICE), WSL 안의 EKS 사본, 기본 프로필 scratch 45GB, `Temp/hermes_agy_*` 대화 기록의 소유 프로필.
4. 다음 회차에서 재생성 캐시를 다시 찾는 일은 효과가 거의 없다(이번 1GB 미만). 대신 위 결정이 내려진 대상만 처리한다.

## 증거

- [fullinv.json](../evidence/2026-10-31_disk-round9/fullinv.json): 드라이브 전체 재고, 하드링크·클러스터 반영, 읽지 못한 디렉터리 142개
- [vss_events.txt](../evidence/2026-10-31_disk-round9/vss_events.txt): Volsnap·VSS 이벤트, SR 예약 작업, 레지스트리
- [survey.json](../evidence/2026-10-31_disk-round9/survey.json): 캐시 위치 크기
- [temp_manifest_summary.json](../evidence/2026-10-31_disk-round9/temp_manifest_summary.json), [temp_del_result.json](../evidence/2026-10-31_disk-round9/temp_del_result.json): 삭제 루트·결과
- 실행 스크립트 `scripts-r9_*`. 파일별 전체 manifest(`temp_plan.json`)는 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/disk-round9-20261031/`에 있다. 프로세스 명령줄 원문은 증거에 넣지 않았다.
- 커밋·푸시·서비스·설정·skill·다른 프로필 변경은 없다. 제품 코드를 바꾸지 않았으므로 제품 시험은 해당하지 않는다.
