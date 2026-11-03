---
type: report
title: C: 400GB 목표 3차 정리 — 실행 범위 59.29GB와 정책상 차단 범위 실측
description: NPU 무효 엔진 17.72GB, C:/_proj 끝난 체크아웃 15개 36.23GB, Temp 잔여물 5.33GB를 보존 확인 뒤 지워 C: 여유가 119.73GB에서 175.24GB가 됐다. 400GB까지 남은 224.76GB는 모두 정책·소유·실행 중 제약에 걸린 범위다
status: done
domain: travel
impl_scope: cs — C:/_proj/*1029 체크아웃, frog-npu-dev NPU 엔진 일부, 사용자 Temp, guguroute 프로필 backups와 이 보고서·색인 한 줄만 다룬다. 원본 `C:/_proj/final_workspace`의 코드·Git·datasets·scratch, 기본 Hermes 프로필, Hermes 모델, WSL, 시스템 설정은 변경하지 않았다
---

# C: 400GB 목표 3차 정리 (2026-10-29 18:10–18:50)

앞선 정리: [guguroute scratch 사본 정리](2026-10-29_guguroute-scratch-copy-cleanup.md), [디스크 증가 예방 가드](2026-10-29_disk-growth-guard.md). 단위는 GB=10⁹ B다. 다른 작업자(NPU 빌드, ST4F719 시험)가 동시에 쓰고 있었으므로 여유 변화는 삭제 효과와 다른 쓰기가 합쳐진 값이다.

## 결과

| 시각 | C: 여유 바이트 | GB |
|---|---:|---:|
| 18:10 시작 (`df -B1`) | 119,732,924,416 | 119.73 |
| 18:49 끝 | 175,244,697,600 | 175.24 |

| 묶음 | 파일 | 지운 논리 바이트 | 실측 여유 변화 |
|---|---:|---:|---:|
| NPU `engines/h1`·`h1-eps`의 `.dla`·`.onnx` | 151 | 17,724,502,248 | +17.72GB (단독 실행) |
| `C:/_proj/*1029` 끝난 체크아웃 15개 | 288,509 | 36,233,842,230 | 구간 합 +42.78GB (Temp 정리와 겹침) |
| 사용자 Temp 잔여물 | 432 | 5,334,665,560 | +5.43GB |
| **합계** | **289,092** | **59,293,009,038** | 시작→끝 **+55.51GB** |

**400GB 목표는 달성하지 못했다.** 18:49 기준 부족분은 **224.76GB**다. 아래 「차단 범위」를 보면, 이번에 허용된 범위 안에서는 더 회수할 수 있는 큰 대상이 남아 있지 않다.

## 실행한 것과 판정 근거

### 1. NPU 무효·대체 엔진 (17.72GB)

- 대상: `C:/Users/kcxsz/frog-npu-dev/experiments/npu-full/engines/h1/`의 `.dla` 73개·`.onnx` 73개, `engines/h1-eps/`의 5개.
- 근거: 담당자 `_coord/NOTICE-npu-stream16-20261029.md`가 `h1`을 「epsilon 버그로 무효, h1-eps3로 대체, 실패 증거는 `resume-20261029/` JSON에 보존」, `h1-eps`를 「대체된 부분 세트」로 분류해 정리 후보로 올렸다. HANDOFF는 `h1`을 성능 주장에 쓰지 말라고 적었다. 사용자가 검증된 불필요 항목의 정리를 미리 승인했다.
- 확인한 것:
  - 실행 중인 명령줄 481개 중 두 폴더를 가리키는 것은 0개였다. 실행 중인 argen·stream 작업은 `h1-eps3`·`review-silufix64`·`argen-tmp`만 쓴다.
  - 모든 파일이 1시간 넘게 수정되지 않았다.
  - 지우기 전에 151개 전부 sha256을 계산했다. `h1` DLA 65개는 `resume-20261029/engine-manifest.json`과 일치했고 불일치는 0개였다.
- 남긴 것: 두 폴더의 `.log` 73개, `meta.json`, `build.jsonl`. 나머지 NPU 산출물은 하나도 건드리지 않았다.
- 담당자 알림: `frog-npu-dev/_coord/NOTICE-disk-cleanup-20261029c.md`

### 2. `C:/_proj/*1029` 끝난 체크아웃 15개 (36.23GB)

대상 Git 작업 트리:

- `busreview1029`(루트 자체)
- `eksprecision1029/repo`, `eksreview1029/repo`, `eksscalar1029/repo`, `ekscheck1029/repo`, `ekscheckreview1029/repo`, `eksdeep1029/repo`, `eksserve1029/repo`, `eksstruct1029/repo`, `ekslat-review1029/localrepo`, `eksobserve1029/repo`, `eksperf1029/repo`, `eksfatal1029/repo`, `ekslinuxreliability1029/repo`, `ekscheckingcontinue1029/repo`

같은 상위 폴더의 로그·XML·JSON·`pgdata`·`pgdata-preserved`·`release-artifact`·스크립트는 그대로 두었다. 각 체크아웃 폴더에는 `RETIRED.md`를 남겨 보존 위치와 복원 방법을 적었다.

판정 근거:

1. **소유자 상태**: 각 Codex/Claude 작업자 NOTICE가 COMPLETE(HOLD 포함)이고, 예약을 해제했으며, 실행 중인 PG가 없다고 적었다. 소유자가 `C:/_proj/routingresume1029`(17:58 사용)와 `routinga11base1029`를 사용 중이라 제외했다. HOLD 연쇄의 원천인 `eksremaining1029`·`eksprecision1029/candidate`·`eksremain3*`도 제외했다.
2. **사용 여부**:
   - 삭제 직전 Win32_Process 스냅숏에서 상위 폴더 이름이 나오는 명령은 0개였다. 이 정리 작업 자신의 명령은 제외했다.
   - `.git` 밖 파일 중 가장 최근 수정은 08:33(`eksprecision1029/repo`)이었다. 판정 기준은 6시간이다.
   - 재분석 지점이 0개였다.
   - `C:/_proj`·`final_workspace/scratch`·guguroute scratch에서 이 저장소들을 가리키는 `objects/info/alternates`는 0개였다.
3. **커밋 보존**: HEAD는 모두 GitHub 팀 저장소의 `main`(57f3d2f004d0, PR109 머지)·`team/main`·`team/role-manager`에 있다. 보존 저장소 `eksprecision1029/candidate`·`routingresume1029`에 없는 커밋은 `3fda4eee2`(PR110 draft 가지, `perf/checking-validation-20261029`) 하나였다. 이것은 두 저장소(`ekscheckingcontinue1029`·`eksfatal1029`)에서 `--not 57f3d2f` bundle로 만들었고, `eksprecision1029/candidate`에서 `bundle verify`가 통과했다.
4. **변경 보존**: 저장소마다 다음을 남겼다.
   - `git diff HEAD --binary` (`dirty.patch`): 0~214,552 B, 스테이징된 wiki 문서 포함
   - 미추적 파일과 캐시가 아닌 무시 파일(`.pytest_cache` 등): 덮어쓰지 않는 복사 후 sha256 재대조. 합계 81개, 1.74MB
   - HEAD·refs·remote·status, 전체 파일 목록 `manifest.tsv`
5. **데이터셋 사본**: 무시된 `datasets/mobility/processed/mobility/` 파일 419개는 원본 `C:/_proj/final_workspace/datasets/...`와 크기·sha256이 모두 같았다. 그래서 따로 복사하지 않았다.

결과: 15/15를 지웠고 남은 파일은 0개다. 보존 위치는 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/proj-checkout-archive-20261029c/<이름>/`(`phase2-results-184526.json`)다.

### 3. 사용자 Temp (5.33GB)

- `AppData/Local/Temp/DiagOutputDir/RdClientAutoTrace/RdClientAutoTrace-*.etl` 중 24시간이 지난 원격 데스크톱(WSLg msrdc) 자동 추적 로그. 지금 쓰고 있는 `MSRDCEventProcessor_*.etl`은 남겼다.
- `Temp/tmp*/`(`e.dla`·`e0.dla`·`e1.dla`만 든 Python 임시 폴더) 23개: 10-28~29 NPU 시험이 남긴 임시 엔진이다. 6시간 넘게 수정되지 않았고 명령줄 참조가 없다. `migration-plan.json`이 든 폴더는 남겼다.
- 잠겨서 실패한 파일은 0개다. 결과 기록: `backups/disk-cleanup-20261029c/temp-cleanup-result.json`

## 정책상 차단 범위 (18:10–18:49 실측, 삭제 0)

| 범위 | 크기 GB | 차단 이유 | 풀려면 |
|---|---:|---|---|
| `C:/_proj/final_workspace/scratch` 80항목 | 84.01 (6시간 유휴 67.86) | AGENTS.md 「로컬 원본·데이터셋 삭제 금지」: 세션이 만든 임시 사본도 **대상별 명시 삭제 승인**이 필요하다. ST4F719 시험이 지금 실행 중이다 | 대상 목록을 보고 사용자가 항목별로 승인 |
| `C:/_proj/final_workspace/datasets` | 34.07 | 같은 규칙: 데이터셋 삭제 금지 | 해당 없음 |
| Hermes 모델 `AppData/Local/hermes/models` | 116.12 (Flash-Next 3분할 93.68, 27B 16.46, assets) | 실행 중인 `llama-server` preset 두 개에 등록되어 있다. 사용자 지시: 모델 보존 | 사용자가 모델을 쓰지 않겠다고 결정 |
| 기본 Hermes 프로필 `AppData/Local/hermes/cache/scratch` 688항목 | 72.20 (6시간 유휴 55.27) | 다른 프로필이라 수정 권한이 없다. 기본 프로필 gateway가 실행 중이다 | 그 프로필 세션이나 사용자 지시 |
| WSL `ext4.vhdx` | 47.25 | 줄이려면 `wsl --shutdown`이 필요하다. NPU `make_onnx`(WSL)가 실행 중이라 작업을 멈추게 된다 | NPU 작업 종료 뒤 fstrim+compact |
| `pagefile.sys` 57.06 + `hiberfil.sys` 13.10 | 70.16 | 시스템 설정이다. 이 세션은 관리자가 아니다(`IsInRole Administrator=false`). 재부팅도 필요하다 | 사용자가 관리자 권한으로 최대 크기 지정·`powercfg /h off` |
| NPU 남은 산출물 | later-projection 23.91, F16 GGUF 8.67, h1-eps3 `.onnx` ≈8.45, h16-here 15.22, h1-here-silufix 8.72 | 담당자 NOTICE: 소유자 결정 필요 또는 실행 중 입력. h16-here·h1-here-silufix는 17:55 이후 빌드 중 | NPU 담당자 결정 |
| `C:/_proj/_unified_mall_3` 25.31, `test_workspace` 12.65, `C:/_proj/guguroute` 10.31 | 48.27 | 이번 범위 밖의 다른 프로젝트·사용자 자료이고 분류하지 않았다 | 사용자 확인 |
| `C:/Windows` (WinSxS 25.15) | 43.06 | 관리자 DISM이 필요하다 | 관리자 정리 |
| guguroute scratch 남은 것 | 88.49 (18:14) | 실행 중·롤백·보존 지정·미커밋 항목(앞선 보고서). 정리 후보인 `tf106-20261029` 11.31GB는 긴 경로 실패로 status가 22,410·30,698줄인 트리가 섞여 있어 스냅숏 절차가 필요하다. 깨끗한 소형 3개(`st4f710b`·`speed-cc-codex`·`sse-slot-fix`, 약 3GB)는 이번에 처리하지 않았다 | 다음 회차 |

- **400GB에 닿는 조합 예시**: 224.76GB가 필요하다. 예를 들어 `final_workspace/scratch` 유휴분 67.86 + 기본 프로필 scratch 유휴분 55.27 + Flash-Next 모델 93.68 + `hiberfil` 13.10을 합치면 229.91GB다. 모두 사용자나 다른 소유자가 결정할 항목이다. 동시 작업이 계속 쓰고 있으므로 달성을 보장하지 않는다.
- **용량 귀속**: 사용 중 846.84GB 가운데 약 90GB는 이 세션이 열거하지 못했다. 관리자가 아니어서 `System Volume Information`과 메타데이터에 접근할 수 없었다. 보이는 섀도 복사본은 0개다.

## 원자료

- `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/disk-cleanup-20261029c/`
  - `npu-retire-manifest.json`·`npu-retire-result.json`
  - `temp-cleanup-result.json`
- `.../backups/proj-checkout-archive-20261029c/`: 저장소별 보존물, `phase2-results-*.json`
- 만료 대상 scratch `cache/scratch/c-cleanup-20261029c/`:
  - 크기 inventory `inv-*.json`, 프로세스 스냅숏 `procs-*.json`(명령줄이 들어 있으므로 커밋 금지)
  - Git 분류 `projroots.tsv`, 스크립트 `phase1.sh`·`phase2.py`·`npu_retire.py`·`temp_clean.py`

커밋·푸시는 하지 않았다. 제품 코드를 바꾸지 않았으므로 제품 시험은 실행하지 않았다.
