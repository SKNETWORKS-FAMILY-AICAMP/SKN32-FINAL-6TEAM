---
type: report
title: C: 400GB 5차 정리 — NPU 재생성 ONNX 138개 15.64GB 삭제, 전 드라이브 재실측과 남은 차단 범위
description: DLA가 이미 빌드되어 있고 build.jsonl ok인 h1-eps3·h16-here ONNX 중간물만 지웠다. C: 여유 211.77GB→226.92GB, 400GB까지 173.08GB 부족. 나머지 큰 범위는 모두 사용자·다른 소유자 결정이 필요하다
status: done
domain: travel
impl_scope: frog-npu-dev/experiments/npu-full/engines/{h1-eps3,h16-here}/*.onnx 138개 삭제, 이 보고서·증거·인계·색인·NPU _coord NOTICE만 추가. 코드·Git·datasets·모델·설정·다른 프로필 skills/plugins/cron/memories/config 변경 없음
---

# C: 400GB 5차 정리 (2026-10-30 20:46–21:15)

앞선 기록: [중복 정리](2026-10-30_disk-duplicate-cleanup.md), [계속 감사](2026-10-30_disk-duplicate-cleanup-continuation.md), [4차](2026-10-29_c-drive-400gb-cleanup-round4.md). 단위 GB=10⁹ B. 다른 작업이 동시에 쓰므로 여유 변화는 삭제 효과와 다른 쓰기의 합이다.

## 결과

| 시각 | C: 여유 바이트 | GB |
|---|---:|---:|
| 20:46:47 시작 | 211,773,046,784 | 211.77 |
| 21:05:36 삭제 직전 | 211,280,777,216 | 211.28 |
| 21:07:45 삭제 직후 | 226,917,797,888 | 226.92 |
| 21:13 최종 | 226,920,222,720 | 226.92 |

- 삭제 구간 실측 **+15,637,020,672 B**, 지운 논리 바이트 **15,638,812,560 B** (138/138 = 100%, 보류 0, 실패 0).
- 목표 대비 **226,920,222,720 / 400,000,000,000 = 56.73%**, 부족 **173,079,777,280 B**. **400GB는 달성하지 못했다.**

| 지운 범위 (`C:/Users/kcxsz/frog-npu-dev/experiments/npu-full/engines/`) | 파일 | 바이트 |
|---|---:|---:|
| `h1-eps3/*.onnx` | 73 | 8,454,019,922 |
| `h16-here/*.onnx` | 65 | 7,184,792,638 |
| 합계 | 138 | 15,638,812,560 |

파일별 절대 경로·크기·mtime·nlink·sha256·짝 DLA 경로/크기는 [npu-onnx-plan.json](../evidence/2026-10-30_disk-round5/npu-onnx-plan.json)(sha256 `b2a200c0c5907352503e2c65fefdf8287818c6c9a6a9c0701eddfd99523fd734`), 실행 결과는 [npu-onnx-result.jsonl](../evidence/2026-10-30_disk-round5/npu-onnx-result.jsonl)에 있다. 두 폴더에는 DLA 73+65개, `.log`, `build.jsonl`, `meta.json`이 그대로 남았다.

## 판정 근거

- **재생성 중간물**: stream16 소유자 NOTICE가 `h1-eps3/*.onnx`를 "`make_onnx.py h1-eps3 all:1:1024`로 재생성 가능, DLA는 보존"으로 분류했다. `npu_disk.py growth`도 "DLA가 있는 ONNX = 재생성 중간물, DLA sha256과 build.jsonl ok 기록 뒤 제거 가능"으로 정의한다. 모든 NPU 빌드 경로(`stage.py`, `run_stream.py`, `run_ffnvar.py`)는 DLA 빌드 직후 ONNX를 스스로 지운다. 재생성 입력 `weights/`와 `export-venv`는 그대로다.
- **소비자 없음**: `argen2/run_full.py`, `argen3/run_ab3.py`, `argen4/run_repro.py`, `measure_ffn_h16_npu_clock.py`, `audit_inputs.py`는 디렉터리의 `.dla`·`meta.json`만 쓴다. NPU 소스(.cpp/.h)에 onnx 읽기가 없다.
- **파일별 조건**(전부 충족): 짝 `.dla` 존재, `build.jsonl` `ok:true, exit:0`, DLA 크기 = build.jsonl `dla_bytes`, 1시간 이상 경과(최신 10-29 18:10), nlink 1, 외부 `.onnx.data` 없음.
- **실행 중 아님**: 삭제 직전 프로세스 368개 중 NPU 관련은 `wslservice.exe`(상시 서비스)뿐. WSL Ubuntu Stopped. argen4 작업자는 20:40 종료 기록, 그 뒤 frog-npu-dev에 새 파일 없음. 재분석 지점 중 이 경로를 가리키는 것 0개.
- **삭제 방식**: 파일마다 공유 없는 배타 핸들(GENERIC_READ|DELETE, share 0)로 열고, 크기·nlink·DLA 재확인, 그 핸들로 sha256 재계산 일치 후 `FileDispositionInfo`로 삭제. 재귀 삭제 없음. 삭제 후 138/138 경로 부재 확인.
- `h1-eps3/ffn0_h1.onnx`와 같은 바이트의 `engines/eps3-probe/ffn0_h1.onnx`(증거 probe)는 남겼다.

## 전 드라이브 재실측 (읽기 전용, 재분석 지점 미추적)

| 범위 | 논리 GB | 상태 |
|---|---:|---|
| `C:/_proj` | 196.47 | final_workspace 133.20(scratch 83.97, datasets 34.07), `_unified_mall_3` 25.31, `test_workspace` 12.65, `guguroute` 10.31, `eks*1029` 9.72, `postgresql` 1.57(실행 중) |
| `hermes` | 240.03 | models 116.12, guguroute 프로필 75.33(scratch 70.51, backups 3.86), 기본 프로필 cache/scratch 44.95, tools 2.90 |
| `frog-npu-dev` | 111.43→약 95.8 (논리) | engines·later-projection 23.91·weights 8.41·F16 GGUF 8.67·tests 6.49·late-ffn 5.83·export-venv 4.10 |
| 나머지 C: | 209.60 | pagefile 57.06, hiberfil 13.10, WSL vhdx 47.43, Windows 43.08, Program Files 18.65, Downloads 8.61, Temp 4.94 |

요약 JSON: [inventory-summary.json](../evidence/2026-10-30_disk-round5/inventory-summary.json), 최상위 폴더표 `toplevel-*.json`, final_workspace scratch 후보표 [final-scratch-candidates.json](../evidence/2026-10-30_disk-round5/final-scratch-candidates.json).

검토했지만 지우지 않은 것:
- 각 scratch의 재생성 캐시(`node_modules`·`.next`·`__pycache__` 등)는 생각보다 작다: final_workspace scratch 5.74GB(대상별 승인 필요), guguroute 0.64GB, 기본 프로필 0.02GB.
- Temp `RdClientAutoTrace` ETL 1.82GB: 24시간 넘은 것은 2개 15MB뿐(원격 데스크톱 클라이언트가 계속 기록 중). 보류.
- `CrashDumps` 0.88GB: NPU `ffn31bench`·`trtexec` 덤프 = 진단 증거. NPU 소유자 결정.
- 같은 크기 tar 쌍(`remaining_shared_implementation/baseline.tar` ↔ `remaining_dod_validation/candidate.tar`) sha256이 달라 중복이 아니다([tars.jsonl](../evidence/2026-10-30_disk-round5/tars.jsonl)).
- `C:/_proj/guguroute/tripilot_model_copy_20261014/base_e4b.gguf` 9.61GB: 같은 크기 파일이 드라이브에 없어 고유 모델로 보존.
- 관리자 권한 없음(`IsInRole(Administrator)=False`): pagefile/hiberfil, WinSxS PendingDeletes 1.20GB, VSS 저장소는 확인·변경 불가.

## 400GB 가능 여부

**지금 승인된 범위(검증된 비활성 재생성물·중복)만으로는 불가능하다.** 남은 173.08GB는 아래 결정 항목에서만 나온다.

| 후보 | GB | 막는 것 | 풀려면 |
|---|---:|---|---|
| `C:/_proj/final_workspace/scratch` 90개 항목 | 83.97 (24시간+ 유휴·프로세스 참조 0: 73.92) | AGENTS.md: 대상별 절대 경로·파일 목록·보존 상태 제시 후 명시 승인 | 사용자가 `final-scratch-candidates.json` 항목별 승인 → 미푸시 커밋 bundle·미추적 증거 보존 후 삭제 |
| Hermes Flash-Next 모델 세트(2/3+3/3+1/3, mtp, mmproj) | 98.74 | 사용자 모델 보존 지시, presets.ini 등록(PID 28436 autoload 가능) | 사용자 결정 |
| `hiberfil.sys` | 13.10 | 관리자 `powercfg /h off` | 사용자 관리자 실행 |
| `pagefile.sys` 축소 | 최대 ~41 | 관리자+재부팅. **주의**: argen4가 커밋 여유 1.96GB까지 떨어짐을 기록. 축소하면 NPU·LLM이 커밋 부족으로 실패할 수 있다 | 권장하지 않음 |
| WSL `ext4.vhdx` 압축 | 0~47.43 (내부 사용량 미측정) | `wsl --shutdown` 후 관리자 Optimize-VHD/diskpart. NPU make_onnx가 WSL 사용 | NPU 유휴 시 사용자 관리자 실행 |
| NPU `later-projection` 원시 로짓 | 23.91 | 소유자: 증거 | NPU 소유자 |
| NPU F16 GGUF | 8.67 | 재생성 시 임베딩 정렬 재수행, GPU-FP16 기준 실행에 필요 | NPU 소유자 |
| 기본 Hermes 프로필 scratch | 44.95 | 다른 프로필의 GHelper·펌웨어 작업물(펌웨어 추출 5.71, BIOS ISO/설치본 5.24, NVIDIA 설치본 1.22 등) | 그 프로필 소유자·사용자 |
| `_unified_mall_3`, `test_workspace`, `eks*1029` | 47.68 | 다른 프로젝트 / HOLD | 사용자 |
| guguroute scratch 남은 것 | 70.51 | 앞선 회차에서 보존·실행 중·롤백·미커밋으로 분류 | 개별 재분류 |

- **조합 예시**: final_workspace scratch 83.97 + Flash-Next 98.74 = 182.71GB > 173.08GB(여유 약 9.6GB). 동시 작업이 계속 쓰므로 달성을 보장하지 않는다.
- 모델을 남기는 경우: scratch 83.97 + hiberfil 13.10 + later-projection 23.91 + F16 8.67 + 기본 프로필 scratch 일부 + `_unified_mall_3` 25.31 등 여러 소유자 결정이 모두 필요하다.

## 남은 일

- 다음 정리 후보는 사용자 승인 대기다. final_workspace scratch를 승인하면 [4차 방법](2026-10-29_c-drive-400gb-cleanup-round4.md)대로 Git 상태·bundle·고유 파일 보존 뒤 지운다.
- NPU 소유자에게 `_coord/NOTICE-disk-cleanup-20261030-round5.md`로 알렸다. h1-eps3·h16-here를 다시 빌드할 일이 있으면 ONNX를 재생성해야 한다.
- 커밋·푸시·서비스 중지·설정 변경 없음. 제품 코드를 바꾸지 않아 제품 시험은 해당 없음. 증거 18개 529,995 B는 [artifacts.json](../evidence/2026-10-30_disk-round5/artifacts.json).
