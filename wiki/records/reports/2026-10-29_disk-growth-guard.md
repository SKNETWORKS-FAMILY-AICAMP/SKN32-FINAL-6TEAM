---
type: report
title: 디스크 증가 예방 가드 — 생성 경로 검사·사본 재사용 장부·원인 근거
description: 설정 기반 최소 여유 검사와 사본 재사용 장부를 구현·시험하고 NPU FP16 산출물·작업 사본 누적을 실측 근거로 기록했다
status: done
domain: travel
---

# 디스크 증가 예방 가드 (2026-10-29)

사용자 요청: 디스크가 계속 커지지 않게 예방하고(정리만이 아님), 진행 중 작업을 멈추지 않으며, 유일 자료를 보존한다. C: 여유 목표는 **400GB**다. 이번 세션은 **삭제·이동·프로세스 중단 0건**이다. 단위는 GB=10⁹ B다.

## 현재 측정 (이번 세션 실측)

| 시각 | C: 여유 바이트 | GB | 출처 |
|---|---:|---:|---|
| 15:52 (앞선 감사) | 103,664,947,200 | 103.665 | [앞선 감사](2026-10-29_c-drive-safe-cache-audit.md) |
| 16:20경 | 78,732,316,672 | 78.732 | `disk_guard.py check` 실측 |
| 16:23경 | 78,498,902,016 | 78.499 | `Get-PSDrive C` |

약 30분에 **-25.2GB**. 400GB 목표까지 **321.5GB 부족**하다. 이번 세션은 목표에 도달하지 못했다(삭제 승인 대상이 아니었다).

## 증가 원인 — 실측 근거

| 원인 | 크기 | 근거 |
|---|---:|---|
| NPU `engines/<tag>` 그래프 세트마다 ONNX+DLA 이중 저장 | `h1` 16.4GB, `h1-eps3` 16.4GB (ONNX 8.454GB + DLA 8.733GB씩) | `frog-npu-dev/experiments/npu-full/engines/*` 바이트 합. `h1`은 정확도 실패로 성능 사용 금지인데 보존 중(HANDOFF) |
| NPU 원시 FP16 추출 ① `.npy` | `weights/` 8.0GB, 426 텐서 | `export_weights.py`가 Q4_K_M(2,797,526,816 B)을 FP16으로 역양자화: 4비트대→16비트, 약 **×3.1** |
| NPU 원시 FP16 추출 ② GGUF | `FrogNano-dequant-F16.gguf` 8,665,620,256 B, **16:10:37 생성** | `resume-20261029/dequant-f16.log`: `llama_quantize ... as F16`, `model size 2657.47 MiB → quant size 8253.72 MiB (16.00 BPW)`. ①과 같은 가중치의 두 번째 FP16 사본 |
| NPU 로짓 덤프 반복 | `later-projection/` 23.9GB, 그중 같은 구성 결과 폴더 6개×3.19GB | 각 폴더 169파일, 실행당 전체 어휘 로짓 71,516,160 B |
| `frog-npu-dev/experiments` 전체 | 15:50 67.512GB → 16:10 83.75GB (+16.2GB) | 앞선 감사 frog-current.json 대비 이번 inventory |
| `C:/_proj/*1029` 작업 사본 | 28곳 48.34GB (각 2.3~7.0GB, 대부분 중첩 Git 사본 1개+증거) | 이번 inventory, 생성 시각 02:36~15:52 |
| guguroute Hermes scratch | 145.32GB, 810항목 | 이번 inventory(열거 오류 있는 항목은 하한) |
| WSL `ext4.vhdx` | 43,419,435,008 B (16:23) | 15:47 43,406,852,096 B와 거의 같음 — 이번 구간 증가원 아님. 가상 디스크는 자동 축소되지 않는다 |

공통 원인: **생성 경로에 여유 공간 검사·크기 신고·재사용 절차가 없었다.** 작업자마다 새 전체 사본(`git clone`)을 만들고 끝난 사본을 반환하지 않았다. NPU 쪽은 `build_stream.py`만 30GiB 하한을 검사하고, `export_weights.py`·`llama-quantize`·`make_onnx.py`는 검사하지 않는다. 이전 감사 이후 나머지 감소분은 폴더별로 완전히 귀속하지 못했다(분모 모름).

부수 발견: AGENTS.md 「Claude 실행 전 훅」의 `tools/local_data_guard.py`를 연결하는 설정을 프로젝트 `.claude/`(settings.local.json만 있음)와 `~/.claude/settings.json`(없음)에서 찾지 못했다. `tools/`는 HEAD에 추적되지 않는다. 훅이 실제로 동작한다고 확인하지 못했다. 이번에 바꾸지 않았다.

## 구현한 것 — `tools/disk_guard.py`

표준 라이브러리만 쓰고, **삭제·이동·reset·checkout을 하지 않는다**.

- **설정 필수**: `--config` → `TRIPILOT_DISK_GUARD_CONFIG` → `tools/disk_guard.json`. 없거나 키가 빠지거나 값이 잘못되면 종료 코드 2로 거부한다. 코드에 기본 임계값이 없다.
- `check --path P --need-bytes N`: 쓰기 후 여유가 `min_free_bytes` 아래면 3으로 거부. 크기를 모르면 거부. 다른 스크립트는 `require_free()`를 import한다.
- `reserve` → `git clone` → `complete`: 새 사본은 `managed_roots` 아래만 허용. 대기 중 예약 합을 여유에서 빼서 동시 작업자가 함께 통과하지 못하게 한다(잠금 파일 + 원자 교체). 크기는 같은 원본의 실측 사본 크기, 없으면 `--expected-bytes`를 요구한다.
- 여유가 `target_free_bytes` 미만이면 `below_target_policy`대로: `reuse_first`는 같은 원본의 유휴 사본이 있을 때 새 사본을 거부하고 `acquire`를 요구, `deny_new`는 새 사본을 모두 거부.
- `acquire`/`release`: 작업 끝난 사본을 장부에 반환해 다음 작업자가 재사용. 재사용자는 `git status --porcelain`이 비었는지 먼저 확인한다(도구가 대신 정리하지 않는다).
- `abandon`: 사본이 생기지 않은 예약만 지운다. 부분 생성 폴더가 있으면 거부하고 남긴다.
- `inventory`: 장부의 사본별 상태·실측 크기와 managed root 아래 **미등록 폴더**를 보여 준다.
- `tools/guarded_clone.sh`: acquire 시도 → 실패(3)면 reserve → `git clone` → complete. 설정 오류(2)면 복제하지 않고 멈춘다. Hermes의 Python은 WindowsApps git을 실행하지 못하므로(WinError 5) 복제는 셸에서 한다.

설정 `tools/disk_guard.json`:

| 키 | 값 | 근거 |
|---|---|---|
| `min_free_bytes` | 32,212,254,720 (30GiB) | 기존 문서 값: NPU `build_stream.py`·README의 30GiB 하한. 새로 추정하지 않았다 |
| `target_free_bytes` | 400,000,000,000 | 2026-10-29 사용자 지시 |
| `below_target_policy` | `reuse_first` | 이번 세션 **권고값 — 사용자 확인 필요**. 현재 여유가 목표보다 낮아 이 정책이 즉시 적용된다 |
| `managed_roots` / `ledger_path` | `C:/_proj/_clones` / 그 안 `.disk_guard_ledger.json` | 새 빈 폴더. 기존 사본은 옮기지 않았다 |

## 시험

- `tools/tests/test_disk_guard.py` 18건: 설정 없음·키 누락·잘못된 값 거부, 하한 경계(정확히 하한 허용, 1바이트 초과 거부), 크기 미상 거부, 관리 루트 밖 거부, 예약 합산, 실측 크기 재사용, 목표 미달 시 재사용 강제·acquire·임차인 아닌 release 거부, `deny_new`, abandon 규칙, 미등록 폴더, 6스레드 동시 예약(통과 2·거부 4), 삭제 코드 부재. **3회 연속 18/18 = 100%** (`DISK_GUARD_TEST_DIR=<scratch> python tools/tests/test_disk_guard.py`).
- 실제 git 종단 시험(scratch 원본·별도 설정): 크기 미상 거부(3) → 크기 지정 복제 성공 → release → 재사용으로 **같은 사본 반환, 새 폴더 0** → 임차 중이면 새 사본 → 유휴 사본이 있으면 reserve 거부 → 없는 원본 복제 실패 시 예약 자동 abandon. 장부 실측 27,752 B.
- 실제 설정으로 C: 확인: 50GB 쓰기 요청 → 여유 78.73GB, 쓰기 후 28.73GB < 30GiB라 **거부(3)**. 설정 경로 없음 → **거부(2)**.

## 적용 범위와 한계

- **강제되는 곳은 이 도구를 거치는 생성뿐이다.** 맨 `git clone`·`cp`·`robocopy`, NPU `export_weights.py`·`llama-quantize`·`make_onnx.py`, Hermes 위임 작업자의 scratch 사본, Codex 작업자는 규칙을 따를 때만 걸린다. 운영체제 할당량이나 파일시스템 훅이 아니다. 모든 생성을 막는다고 보고하지 않는다.
- Claude 실행 전 훅 연결, NPU 스크립트에 `require_free` 호출 추가, Hermes 위임 시작 절차 변경은 **진행 중 작업자 파일·설정을 바꾸므로 하지 않았다**. 각 소유자 승인 후 연결할 일이다.
- 로컬 경로 `git clone`은 같은 볼륨에서 객체를 하드링크하므로 실측 논리 크기가 실제 점유보다 클 수 있다(보수적 추정).
- 장부는 등록된 사본만 안다. 기존 28+810개 폴더는 미등록이며 옮기거나 등록하지 않았다.

## 400GB까지 — 승인·검증이 필요한 후보 (삭제 0건)

AGENTS.md 「로컬 원본·데이터셋 삭제 금지」에 따라 아래는 **대상별 사용자 승인과 고유 자료 검증 전에는 삭제하지 않는다.**

| 후보 | 크기 | 먼저 확인할 것 |
|---|---:|---|
| NPU `engines/h1` (정확도 실패 세트) | 16.4GB | NPU 담당자의 보존 지시·재현 필요성. `resume-20261029`에 해시 매니페스트 있음 |
| `h1-eps3`·`h1`의 `.onnx` (DLA 빌드 후 중간물) | 각 8.45GB | `make_onnx.py`로 재생성 가능 여부·해시 보존 |
| `FrogNano-dequant-F16.gguf` 또는 `weights/*.npy` 중 하나 | 8.3 / 8.0GB | 같은 FP16 가중치 이중 저장. 활성 작업(16:10 생성) 종료 후 소유자 결정 |
| `later-projection` 결과 6×3.19GB 로짓 | 19.2GB | 결과 요약·해시 보존 후 원시 로짓 처분 |
| `C:/_proj/*1029` 28곳 | 48.34GB | 사본별 미푸시 커밋·미커밋 변경·증거 보존(번들 검증) |
| guguroute scratch 오래된 사본 | 145.32GB 중 일부 | 같은 절차. scratch는 24시간 유휴 정리 대상이라 유일 자료는 먼저 영구 위치로 |

위 합계를 모두 회수해도 **321.5GB 부족분을 확실히 채운다는 근거는 없다**(scratch 중 회수 가능분 분모 모름). Hermes 모델(과거 116GB)·기본 프로필 cache(과거 64.8GB)는 다른 소유 범위라 이번에 측정·변경하지 않았다.

## 작업자 규칙 (요약)

1. 새 사본은 `bash tools/guarded_clone.sh <원본> C:/_proj/_clones/<이름> <작업자> <목적> [예상바이트]`로 만든다. 끝나면 `python tools/disk_guard.py release --dest ... --owner ...`.
2. 수 GB 산출물을 쓰기 전에 `python tools/disk_guard.py check --path <쓸 위치> --need-bytes <예상>`; 거부(3)면 쓰지 않고 보고한다.
3. 같은 데이터의 두 번째 전체 사본(FP16 npy와 F16 GGUF, ONNX와 DLA)을 만들기 전에 기존 산출물 재사용 가능성을 먼저 적는다.
4. 인계 때 `inventory` 결과와 자신이 만든 사본 목록·크기를 남긴다.

## 원자료

`C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/disk-guard-20261029/` (영구 사본) — `proj.json`·`scratch.json`·`frog.json`(최상위 항목별 바이트·파일 수·최신 mtime·중첩 .git·열거 오류, 재분석 지점은 따라가지 않음), `inventory.py`, 종단 시험 원자료 `e2e/`는 만료 대상 `cache/scratch/diskguard_1029/`에만 있다.

변경 파일: `tools/disk_guard.py`, `tools/disk_guard.json`, `tools/guarded_clone.sh`, `tools/tests/test_disk_guard.py`, 이 보고서, wiki 색인 줄. 빈 폴더 `C:/_proj/_clones` 생성. 커밋·푸시하지 않았다.
