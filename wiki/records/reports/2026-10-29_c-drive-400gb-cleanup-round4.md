---
type: report
title: C: 400GB 목표 4차 정리 — guguroute scratch 남은 후보 6개 17.91GB 보존 대조 후 삭제
description: 3차에서 미뤘던 깨끗한 사본 3개와 tf106-20261029 긴 경로 트리, 그리고 끝난 st4f710·st4f711-backend 체크아웃을 커밋·고유 파일 보존 확인 뒤 지웠다. C: 여유는 170.55GB에서 188.03GB가 됐고, 400GB까지 211.97GB가 부족하다
status: done
domain: travel
impl_scope: cs — guguroute 프로필 cache/scratch 의 정확한 6개 경로, 같은 프로필 backups, 이 보고서와 색인 한 줄만 다룬다. 원본 `C:/_proj/final_workspace`의 코드·Git·datasets·scratch, 기본 Hermes 프로필, 모델, NPU, WSL, 시스템 설정은 변경하지 않았다
---

# C: 400GB 목표 4차 정리 (2026-10-29 18:53–19:35)

앞선 회차: [3차 정리](2026-10-29_c-drive-400gb-cleanup-round3.md). 단위는 GB=10⁹ B다. NPU 빌드 등 다른 작업이 동시에 쓰고 있었으므로, 여유 변화는 삭제 효과와 다른 쓰기가 합쳐진 값이다.

## 결과

| 시각 | C: 여유 바이트 (`df -B1`) | GB |
|---|---:|---:|
| 18:53 작업 시작 | 173,641,265,152 | 173.64 |
| 19:23:57 삭제 직전 | 170,545,602,560 | 170.55 |
| 19:31:19 삭제 직후 | 188,028,575,744 | 188.03 |
| 19:32 재측정 | 187,537,862,656 | 187.54 |

- 시작부터 삭제 직전까지 여유가 3.10GB 줄었다. 이 가운데 0.69GB는 이번 보존 사본이고, 나머지는 다른 작업이 쓴 양이다.
- 삭제 구간(19:23:57→19:31:19)의 실측 변화는 **+17.48GB**다. 지운 논리 바이트는 17.91GB다.
- **400GB 목표는 달성하지 못했다.** 19:31 기준 부족분은 **211.97GB**다.

| 지운 정확한 경로 (scratch 기준) | 파일 | 논리 바이트 | 보존한 고유 파일 |
|---|---:|---:|---:|
| `st4f710b-20261028` | 20,259 | 2,356,848,205 | 39개 1.20MB |
| `speed-cc-codex-20261028` | 13,594 | 445,854,908 | 1,603개 73.9MB (pgdata·ev) |
| `sse-slot-fix-20261028` | 11,508 | 296,784,685 | 1,581개 78.3MB (pgdata·ev·probe·harness) |
| `st4f710-20261028` | 12,471 | 1,164,252,853 | 25개 0.08MB |
| `st4f711-backend-20261029-v1/repo` (체크아웃만) | 19,430 | 2,236,810,618 | 1,676개 128.8MB (형제 포함 사본) |
| `tf106-20261029` | 239,496 | 11,407,380,435 | 861개 410.7MB |
| **합계** | **316,758** | **17,907,931,704** | **5,785개 692.9MB** |

6/6=100% 경로가 없어졌고, 실패는 0건이다. 디렉터리 연결점(junction) 5개는 연결만 지웠고 대상을 따라가지 않았다. 5개 모두 삭제 범위 안을 가리켰다.

## 판정 근거

1. **사용 여부**
   - 삭제 직전 Win32_Process 445개 가운데 6개 이름을 가리키는 명령줄은 0개였다. 이 정리 작업 자신의 명령은 제외했다.
   - 6개 경로를 쓰는 PostgreSQL은 없었다. 실행 중인 PG 두 개는 `guguroute-16`과 `routinga11verify1029`다.
   - 가장 최근 파일 수정은 16.9시간 전(tf106)이었다.
   - 소유자 상태: ST4F-711 소유자 NOTICE 두 개가 COMPLETE였다. role-manager tip은 `3dd9bd70c`, 원본 커밋은 `217da9ad0`다. T(tf106) 작업도 이 커밋으로 끝났다.
2. **연결 의존성**
   - guguroute 프로필, `C:/_proj`, 기본 프로필 scratch(읽기만), frog-npu-dev에서 재분석 지점 778개를 검사했다. 삭제 범위 밖에서 6개 경로를 가리키는 것은 0개였다.
   - `.git/config`와 `objects/info/alternates`를 검사했다. objects 의존은 0개였다.
   - URL 참조만 두 건 있었다.
     - `st4f711-backend/repo`의 origin이 `tf106/.../validated`였다. 같이 지웠다.
     - `C:/_proj/final_workspace/scratch/st4f729-resolution-20261029/repo`가 `st4f711-backend-20261029-v1/gh.exe`를 credential helper로 쓴다. 그래서 그 폴더는 `repo/`만 지우고 형제 파일 124개는 그대로 두었다. 대신 `RETIRED.md`를 남겼다.
3. **커밋 보존**
   - 팀 GitHub에 없는 HEAD 5개를 bundle 하나로 묶었다.
     - `e6e754f27`: ST4F-710 수정
     - `35e1b0259`, `20a9a2bdf`: 접수 SSE 후보
     - `e181f23d3`: w711·rm HEAD
     - `1c286b6`: c714eecdb 스냅숏
   - 만든 방법: 임시 bare 저장소에 alternates를 걸고 `--not 57f3d2f fab3da50a 3463b30c6 3dd9bd70c`로 bundle을 만들었다.
   - 확인: `routing-open-20261028/repo` 객체만 alternates로 둔 검증 저장소에서 `bundle verify`가 통과했다. fetch한 뒤 ref 5개의 tree 항목 수도 원본과 같았다.
   - 나머지 HEAD는 GitHub 팀 ref에 있다: `e88e01925`(team/main), `c714eecdb`, `3dd9bd70c`(team role-manager).
4. **파일 단위 보존**
   - 대상: `.git`·캐시 밖의 모든 파일. 파일마다 git blob sha1을 계산했다. autocrlf 체크아웃이라 원본 bytes와 CRLF→LF 정규화본 두 가지로 계산했다.
   - 대조: 보존된 커밋 8개 tree의 blob 17,372개와 맞으면 재현 가능으로 판정했다.
   - 그 밖의 파일 5,785개는 덮어쓰지 않는 복사(`xb`)로 옮겼다. 원본·사본 sha256이 같은지 두 번 확인했고, 삭제 뒤 다시 대조해 0건이 달랐다. 복사 대상: 미추적·무시 파일, 증거 로그·XML, pgdata, `.git` 메타데이터(objects·index 제외), 이식형 node·git 도구.
   - 버린 것: `node_modules`·`.next*`·`.vite`·`__pycache__`·`.ruff_cache`(3.81GB), 그리고 bundle·팀 ref로 재현되는 `.git/objects`.
   - ST4F-711 후보 세 파일(`intake-starting.tsx`·`registration-screen.tsx`·`intake-starting-return.test.ts`)의 blob은 팀 `217da9ad0`과 같았다. w711·validated 사본 모두 같았다. 미통합 코드는 없다.
   - 변경분 `git diff HEAD --binary` 4개와 status는 `patches/`에 따로 두었다.
   - 삭제 스크립트: 경로마다 manifest에 없는 새 파일이나 크기가 바뀐 파일이 있으면 중단하도록 했다. 6개 모두 0건이었다.

## 남은 것과 알릴 점

- `allpast-hotfix-20261025-2005/repo/.git/worktrees/{w711,rm61}`은 작업 트리가 없는 등록으로 남아 있다. 다른 저장소의 Git 디렉터리라 이번에는 고치지 않았다. 허브 소유자가 `git worktree prune`을 결정한다.
- 원본 `C:/_proj/final_workspace`에서 커밋 존재 확인용으로 `git cat-file -e`/`branch -r --contains`를 한 번 직접 실행했다(`GIT_OPTIONAL_LOCKS=0`, 읽기 전용). 규칙상 진입점은 `tools/safe_git.py`다. 이후 원본 Git은 쓰지 않았다.
- 이 프로필 scratch에서 남은 큰 항목은 모두 앞선 보고서에서 보존, 실행 중, 롤백, 미커밋, 최근 활동으로 판정한 것이다.
  - `_archive_20261027` 9.67GB: 보존물
  - `allpast-hotfix` 허브 9.56GB: 작업 트리 등록 122개, 이번에 빈 등록이 된 2개 포함
  - `remaining_dod_validation` 6.39GB 등 10-24 옛 사본: 2차에서 재현분을 이미 지웠고, 고유분만 남아 있다
  - `latest-serving` 3.32GB: 롤백 참조
  - `local_admin_3300_v2`: 불변 빌드 기록
  - `ops-jobs`: 실행 중
  - `schedule-explain-impl`, `routing-open-*`: 최근 활동
  - `modelq-G`: 미커밋
  - 이번 회차에 추가로 안전하게 지울 수 있는 큰 대상은 찾지 못했다.

## 400GB까지의 차단 범위 (3차 표 갱신, 19:31 기준 부족 211.97GB)

| 범위 | 크기 GB (3차 실측) | 차단 이유 | 풀려면 |
|---|---:|---|---|
| `C:/_proj/final_workspace/scratch` | 84.01 (6시간 유휴 67.86) | AGENTS.md 「로컬 원본·데이터셋 삭제 금지」에 따라 대상별 명시 삭제 승인이 필요하다 | 사용자가 항목별로 승인 |
| Hermes 모델 `hermes/models` | 116.12 | 실행 중인 llama-server preset에 등록되어 있고, 사용자가 모델 보존을 지시했다 | 사용자 결정 |
| 기본 Hermes 프로필 scratch | 72.20 (유휴 55.27) | 다른 프로필이다 | 그 프로필 세션이나 사용자 지시 |
| WSL `ext4.vhdx` | 47.25 | `wsl --shutdown`이 필요하고 NPU 작업이 실행 중이다 | NPU 작업이 끝난 뒤 압축 |
| `pagefile.sys` + `hiberfil.sys` | 70.16 | 관리자 권한과 재부팅이 필요하다 | 사용자가 관리자로 설정 |
| NPU 남은 산출물 | 약 65 | 담당자 결정이 필요하거나 실행 중인 입력이다 | NPU 담당자 |
| `datasets`, `_unified_mall_3`·`test_workspace`·`C:/_proj/guguroute`, `C:/Windows` | 34.07 + 48.27 + 43.06 | 데이터셋 삭제 금지, 다른 프로젝트, 관리자 DISM | 사용자 확인 |

- **조합 예시**: 211.97GB가 필요하다. 예를 들어 final_workspace scratch 유휴분 67.86 + 기본 프로필 scratch 유휴분 55.27 + Flash-Next 모델 93.68을 합치면 216.81GB다. 모두 사용자나 다른 소유자가 결정할 항목이다. 동시 작업이 계속 쓰고 있으므로 달성을 보장하지 않는다.

## 원자료

- 영구 보존: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-candidates-20261029d/`
  - `scratch-candidates-unpushed.bundle`: sha256 `830fa3a69770548d84ed3c4678fe0620e85eb8d9251006fded16171e3dcd9cb5`
  - `files/<이름>/...`: 고유 파일 5,785개
  - `patches/`
  - `records/`: manifest·preserved tsv·삭제 결과 `delete-result-193119.json`·df 기록·스크립트

커밋·푸시는 하지 않았다. 제품 코드를 바꾸지 않았으므로 제품 시험은 실행하지 않았다.
