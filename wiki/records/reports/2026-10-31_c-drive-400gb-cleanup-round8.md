---
type: report
title: C: 400GB 8차 — 드라이브 전체 재조사, 진단 추적 1.70GB 삭제·불변 중복 116개 하드링크 5.62GB 회수, 동시 증가로 여유 207.94GB
description: 이전 회차가 보지 않은 영역(드라이브 전체 동일 바이트 중복, WSL 내부, 시스템 숨김 영역, Temp 진단 추적)을 새로 조사했다. 권한 안의 대상만 처리했다. RdClient ETL 210개를 지웠고, guguroute 프로필의 동일 sha256 불변 파일 116개를 하드링크로 합쳤다. 실측 +7.32GB를 회수했다. 같은 시간 다른 작업의 페이지 파일 확장(+9.84GB) 등으로 여유는 231.68GB에서 207.94GB로 줄었다
status: done
domain: travel
impl_scope: 사용자 Temp DiagOutputDir/RdClientAutoTrace의 24시간 지난 *.etl 210개 삭제. guguroute 프로필 cache/scratch 안의 불변 형식 중복 116개를 같은 내용의 하드링크로 교체(모든 경로·바이트 유지). 보존본·manifest는 guguroute backups/disk-round8-20261031. 이 보고서, 증거, 인계 색인 한 줄, NPU _coord NOTICE 한 개를 추가. final_workspace 자료·코드·Git, C:/_proj 다른 사본, 모델, NPU 산출물, 다른 프로필, WSL, 설정, 서비스는 변경하지 않음
---

# C: 400GB 8차 (2026-10-31 01:24–03:51)

앞선 기록: [7차](2026-10-30_c-drive-400gb-cleanup-round7.md), [6차](2026-10-30_c-drive-400gb-cleanup-round6.md), [5차](2026-10-30_c-drive-400gb-cleanup-round5.md). 단위는 GB=10⁹ B다. 7차의 final_workspace scratch 승인 요청은 응답 시간이 초과됐다. 그래서 **아직 승인되지 않았고**, 이번 회차도 그 대상을 건드리지 않았다.

## 결과

| 시각 | C: 여유 바이트 | GB | 비고 |
|---|---:|---:|---|
| 01:24 시작 | 231,682,412,544 | 231.68 | 7차 종료(232.15)와 비슷 |
| 02:04 ETL 삭제 직전 | 201,593,634,816 | 201.59 | 40분 사이 다른 작업으로 −30.09GB |
| 02:04 ETL 삭제 직후 | 203,289,174,016 | 203.29 | **+1,695,539,200** |
| 03:27 하드링크 직전 | 202,585,784,320 | 202.59 | |
| 03:30 하드링크 직후 | 208,205,606,912 | 208.21 | **+5,619,822,592** |
| 03:50 최종 | 207,941,357,568 | 207.94 | |

- 이번 회차가 실측으로 회수한 양은 **7,315,361,792 B (7.32GB)**다. 실패한 항목은 1개다(아래).
- 목표 대비 여유는 **207,941,357,568 / 400,000,000,000 = 51.99%**이고, **192,058,642,432 B (192.06GB)가 부족하다. 400GB는 달성하지 못했다.**
- 여유가 줄어든 원인은 이 작업 밖에 있다.
  - `C:/pagefile.sys`가 57,060,978,688 B에서 66,902,831,104 B로 **+9.84GB** 커졌다(02:39 기록). 시스템 관리 페이지 파일이다. 같은 시각 llama-server PID 39560(00:46 시작)의 private 메모리가 36.2GB였고, 사용 가능 메모리는 2.5GB였다. 10-31 골든 재시도 인계도 커밋 한도와 Qwen 36.5GiB 적재를 적었다. 페이지 파일은 재부팅해야 다시 줄어든다.
  - 기본 프로필 `hermes/cache/scratch/fw-nested-*` 펌웨어 추출이 2시간 동안 +1.41GB를 썼다. WSL vhdx는 +0.03GB였다.
  - **나머지 약 17GB는 원인을 찾지 못했다.** 일반 사용자가 읽을 수 있는 경로에서는 최근 2시간 안에 바뀐 큰 파일이 위 항목뿐이었다. 그러므로 관리자만 볼 수 있는 `System Volume Information`(VSS)이나 `WindowsApps`에 쓰였다고 추정한다. 다만 `Win32_ShadowStorage` 조회는 권한 부족으로 실패했다. 관리자 `vssadmin list shadowstorage`로 확인해야 한다.

## 이번에 새로 조사한 영역

이전 회차는 재생성 캐시(npm·pip·node_modules·.next·__pycache__)를 주로 찾았고, 그 결과는 사실상 0이었다. 이번에는 그 영역을 되풀이하지 않고 다음을 새로 조사했다.

1. **C: 전체 재고**: 01:25에 시작해 175초 걸렸다. 파일 3,632,957개, 논리 바이트 736.62GB를 셌다. 재분석 지점은 따라가지 않았다. 권한 때문에 읽지 못한 디렉터리는 140개다(`WindowsApps`, `$Recycle.Bin`의 다른 SID, `ProgramData/Microsoft` 일부 등).
   - 같은 시각 사용량은 790.40GB였다. **약 53.8GB는 일반 권한으로 볼 수 없는 영역**이다. 여기에는 VSS, WindowsApps, MFT, 작은 파일의 클러스터 여유분이 들어간다.
2. **동일 바이트 중복**: 크기로 묶은 뒤 앞뒤 1MiB를 해시하고, 일치한 후보는 전체 sha256으로 확인했다.
   - guguroute 프로필, `_preserved`, Downloads, `models`(1MiB 이상)에서 **27.93GB가 중복**이었다.
   - frog-npu-dev(16MiB 이상)에서는 **25.57GB가 중복**이었다.
   - 드라이브 전체 스캔은 메모리 압박 때문에 너무 느려서 1시간 뒤 중단했다. 그래서 final_workspace·`_proj` 사본·기본 프로필의 중복 바이트는 **측정하지 못했다**. 크기 그룹만 보면 같은 pack·GHelper exe·데이터셋 모델 사본이 보인다.
3. **WSL 내부**(`wsl -d Ubuntu -- df/du`, 읽기 전용, 실행 전 상태는 Stopped): vhdx 47.43GB 가운데 46.07GB를 실제로 쓰고 있다.
   - `/root`가 39GB다. 대부분 EKS 작업자 사본(`eksremain3_1029` 5.8, `eksremaining1029-native` 5.1, `eksgolden_causality_1029` 5.0 등)이다. `/root/.cache/pip`는 3.4GB다.
   - vhdx 안의 빈 공간이 거의 없으므로 압축만으로는 회수량이 0에 가깝다. 안의 파일을 지워도 호스트 공간이 늘려면 `wsl --shutdown` 뒤 관리자 Optimize-VHD나 diskpart가 필요하다.
   - WSL 2.7.8의 sparse VHD는 데이터 손상 위험이 있어 기본으로 꺼져 있다. 그래서 그 방법은 쓰지 않았다.
4. **Temp 진단 추적**: `DiagOutputDir/RdClientAutoTrace`가 1.83GB였다. 그중 24시간 넘은 210개 1.70GB는 5차 때(15MB)와 달리 모두 회전이 끝난 파일이었다.
5. **시스템·앱 영역**:
   - `WinSxS` 25.15GB(Temp 1.21)는 관리자 DISM이 필요하다.
   - Office 4.88GB와 ASUS AICreator FLUX 모델 2.84GB는 설치 앱과 모델이다. Edge 캐시 2.38GB는 브라우저가 실행 중이다. `node-compile-cache`에는 실행 중인 두 버전만 남았다.
   - 이 영역에서 회수할 수 있는 것은 없었다.

## 처리한 것

### 1. RdClient 진단 추적 삭제 — 1,695,547,392 B
- 대상: `C:/Users/kcxsz/AppData/Local/Temp/DiagOutputDir/RdClientAutoTrace/*.etl` 가운데 mtime이 24시간을 넘고 nlink가 1인 210개.
- 이 파일들은 MSRDC(WSLg 원격 데스크톱 클라이언트) 자동 진단 추적이다. 회전 중인 최신 파일 20개는 남겼다.
- 지우기 직전에 파일마다 크기와 mtime을 다시 대조했다. 210/210을 지웠고 실패는 0이다.
- manifest: [manifest-rdclient-etl.json](../evidence/2026-10-31_disk-round8/manifest-rdclient-etl.json), 결과: [result-rdclient-etl.json](../evidence/2026-10-31_disk-round8/result-rdclient-etl.json).

### 2. 불변 형식 중복의 하드링크 통합 — 116개, 5,616,292,684 B
삭제가 아니다. 모든 경로가 그대로 남고, 각 경로는 같은 바이트를 가리킨다. 중복으로 잡혀 있던 할당만 풀었다.

- **범위**: guguroute 프로필 `cache/scratch` 안의 파일만 바꿨다. `_preserved`와 backups의 파일은 유지본(keeper)으로만 썼다.
- **형식**: 제자리에서 고쳐 쓰지 않는 형식만 다뤘다. `.pack`·`.idx`·`.bundle`·`.gguf`·`.zip`·`.gz`·`.exe`·`.dll`·`.pyd`다. Git은 pack을 고치지 않고 새로 쓴 뒤 지운다.
- **제외**: `.json`·`.jsonl`·`.sql`·문서·이미지처럼 제자리 쓰기가 가능한 형식의 중복 약 18GB는 하지 않았다. 하드링크로 묶은 경로 하나에 제자리 쓰기를 하면 같은 링크의 롤백 원본(`latest-serving-6c345/source-v2`)과 보존 사본까지 함께 바뀌기 때문이다.
- **실행 중 제외**: 실행 직전 Win32_Process 명령줄을 검사했다. 참조된 scratch 트리 15개(`api-runtime-*`, `date_risk_python_01`, `date_risk_node24_official`, `cs-web-response-status`, `ops-jobs-*`, `gugu-memdiag-20261031` 등)는 계획에서 뺐다. 계획 항목 중 이 트리를 건드린 것은 0개였다.
- **파일별 조건**:
  - 계획과 크기·mtime이 같고 nlink가 1이다.
  - 재분석 지점이 아니다.
  - 실행 직전에 대상과 유지본의 전체 sha256을 **다시 계산**했고, 모두 계획 해시와 같았다.
  - 24시간 넘게 쓰기가 없었다.
- **방식**:
  1. 같은 폴더에 유지본으로 `os.link` 임시 링크를 만든다.
  2. inode를 확인한다.
  3. 대상이 읽기 전용이면 그 대상의 속성만 푼다.
  4. `os.replace`로 원자 교체한다.
  5. 교체가 거부되면 원래 상태로 되돌린다.
- **사후 검증**: 116/116이 유지본과 inode·크기가 같고 nlink가 2 이상이다. 남은 임시 링크는 0개다. inode 24개를 다시 전체 해시해 **불일치 0**을 확인했다.
- **주요 대상**:
  - 같은 pack `pack-601a49c9…`(696,486,623 B)의 사본 5개: `booking_admin_off_v2/{baseline_repo,repo}`, `final_integration_preparation/repo`, `local_admin_3300_v2/repo`, `remaining_shared_implementation/baseline_repo`
  - `finalspace_preservation/finalspace_full_20261028.bundle`(730MB) → `C:/Users/kcxsz/_preserved/finalspace_20261028/`의 같은 bundle에 연결했다. 두 보존 경로가 모두 남는다. scratch가 만료되어 정리되어도 `_preserved` 쪽 바이트는 유지된다.
  - 체크아웃 13곳에서 추적되는 같은 `.gguf`·`.zip`·`.gz`
- **실패 1개**: `ui-pinned-20261025-030017-646167/web/node_modules/@next/swc-win32-x64-msvc/next-swc.win32-x64-msvc.node`(110MB)는 교체가 거부됐다(WinError 5). 임시 링크는 지웠고, 원본은 sha256이 같고 nlink가 1인 채로 그대로 있다.
- **파일별 manifest**: [dedupe-result.json](../evidence/2026-10-31_disk-round8/dedupe-result.json). 항목마다 target·keeper·size·sha256·old/keeper/new inode가 있다.
- **링크를 다시 독립 파일로 만드는 법**: 일반 복사로 `<경로>.tmp`를 만든 뒤 원래 경로 위로 rename한다. 이 절차는 backups `README.md`에도 적었다.

## 할 수 없었던 것 — 영역별 GB와 막는 것

| 영역 | GB | 이번 판단 | 풀려면 |
|---|---:|---|---|
| `C:/_proj/final_workspace/scratch` 90개 | 83.97 (7차 승인 후보 3개 15.95) | AGENTS.md 대상별 명시 승인이 필요하다. 7차 요청은 응답 시간이 초과되어 미승인 상태다 | 사용자가 7차 목록이나 항목별로 승인 |
| Hermes 모델(Flash-Next 2/3·3/3, 27B, mtp) | 116.12 | 사용자 모델 보존 지시가 있다. llama-server 2개가 실행 중이다 | 사용자 결정 |
| `pagefile.sys` | 66.90 (+9.84 이번 확장) | 시스템 관리 크기다. 커밋 여유 5.5GB여서 줄이면 실행 중 LLM과 NPU가 실패할 수 있다 | 대형 모델 해제 뒤 재부팅(줄이기는 권장하지 않음) |
| 관리자 전용 숨김 영역 (VSS 추정) | 01:25 기준 약 53.8 + 이후 원인 미상 증가 약 17 | `IsInRole(Administrator)=False`이고 ShadowStorage 조회도 거부됐다 | 관리자 `vssadmin list shadowstorage` 확인 뒤 복원 지점 정리 |
| WSL `ext4.vhdx` | 47.43 (안에서 46.07 사용) | 안의 EKS 사본 약 35GB와 pip 3.4GB는 EKS 소유다. 지워도 압축 전에는 호스트 공간이 늘지 않는다 | EKS 소유자 정리 → `wsl --shutdown` → 관리자 Optimize-VHD |
| frog-npu-dev 검증된 중복 | **25.57** (`later-projection/accuracy-*` 로짓 사본 6~7벌 약 20, `build-fresh-wave-verify/results`, `late-ffn/*/tampered-engines` 1.0 등) | NPU 증거이고 소유자가 다르다. 하드링크 통합도 그 트리를 바꾸는 일이라 하지 않았다 | NPU 소유자가 하드링크 통합이나 사본 정리를 결정. 근거: [npu-dup-summary.json](../evidence/2026-10-31_disk-round8/npu-dup-summary.json), `_coord/NOTICE-disk-round8-20261031.md` |
| guguroute scratch 제자리 쓰기 형식 중복 | 약 18 | 롤백 원본이나 보존 사본이 공유 inode로 함께 바뀔 위험이 있다 | 체크아웃 반환이나 대상별 결정 |
| Downloads·기본 프로필 GHelper 산출물 중복 | Downloads 내부 1.82 + 연계 0.41, 기본 프로필 미측정 | 사용자 폴더이자 다른 프로필의 작업물이다. 빌드가 제자리 덮어쓰기를 한다 | 사용자·기본 프로필 소유자 |
| 기본 프로필 `hermes/cache/scratch` | 44.98 | 다른 프로필이고, 지금 펌웨어 추출로 계속 쓰는 중이다 | 그 프로필 소유자 |
| `hiberfil.sys` | 13.10 | 관리자 `powercfg /h off`가 필요하다 | 사용자 관리자 실행 |
| `_unified_mall_3`·`test_workspace`·`eks*1029`·routing 사본 | 47.7 | 다른 프로젝트이거나 HOLD·실행 중(postgres PID 38472)이다 | 사용자·소유자 |
| `WinSxS` Temp·PendingDeletes | 약 1.2 | 관리자 DISM이 필요하다 | 관리자 |
| CrashDumps 0.88, Edge 캐시 2.38 | 3.26 | NPU 진단 증거이거나 실행 중 브라우저 | 소유자·브라우저 종료 |

- **조합 예시**(부족 192.06GB): final_workspace scratch 유휴분 73.92 + Flash-Next 98.74 + NPU 중복 통합 25.57 = 198.23GB다. 그러나 페이지 파일·VSS·기본 프로필의 동시 증가가 이번처럼 30GB 단위로 생기면 이 조합으로도 목표를 보장할 수 없다.
- 증가를 막으려면 대형 모델 적재로 생기는 페이지 파일 확장과 VSS 사용량 상한(관리자)을 함께 다뤄야 한다. 이번 회차는 설정을 바꾸지 않았다.

## 기타

- 이번 조사 자체도 메모리 압박을 키웠다(이 작업 python의 작업 세트가 6~11MB까지 줄어든 상태로 페이지 입출력이 일어났다). 그래서 드라이브 전체 중복 스캔을 중단했다. 다른 작업의 프로세스는 멈추거나 끄지 않았다.
- WSL 측정 때문에 Ubuntu가 잠시 시작됐다(01:33). 다시 Stopped가 된 것을 확인했다. 그 시점에 RdClient 추적 2개가 새로 생겼다.
- 커밋·푸시·서비스·설정·skill·다른 프로필 변경은 없다. 제품 코드를 바꾸지 않았으므로 제품 시험은 해당 없다.
- 보존본과 manifest: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/disk-round8-20261031/`. 여기에 `README.md`, dedupe 계획·결과, 중복 그룹 전체 `dups-own.json`, 스크립트가 있다.
- 증거: [inventory-summary.json](../evidence/2026-10-31_disk-round8/inventory-summary.json), [dedupe-result.json](../evidence/2026-10-31_disk-round8/dedupe-result.json), [npu-dup-summary.json](../evidence/2026-10-31_disk-round8/npu-dup-summary.json), ETL manifest·결과, 실행 스크립트 `scripts-r8_*`. 프로세스 명령줄 원문은 증거에 넣지 않았다.
