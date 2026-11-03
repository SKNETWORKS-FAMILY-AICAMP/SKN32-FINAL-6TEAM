---
type: report
title: C: 400GB 7차 — final_workspace scratch 승인 후보 3개(15.95GB) 증거 확인·보존본 선작성, 삭제 0
description: 규칙상 사용자 대상별 승인이 필요한 final_workspace scratch 90개 중 비활성·재현 가능성이 확인된 3개 폴더의 체크아웃만 승인 목록으로 정리했다. 보존본(bundle·diff·미추적 파일·.git 메타)을 이 프로필 backups에 먼저 만들고 sha256을 확인했다. 아무것도 지우지 않았다
status: draft
domain: travel
impl_scope: 읽기 전용 조사 + guguroute 프로필 backups/disk-round7-20261030 보존본 작성 + 이 보고서·증거·인계 색인 한 줄. final_workspace scratch·코드·Git·설정·다른 프로필·모델·서비스는 변경하지 않음
---

# C: 400GB 7차 — 승인 후보 3개 (2026-10-30 22:15–22:40)

앞선 기록: [6차](2026-10-30_c-drive-400gb-cleanup-round6.md). 단위 GB=10⁹ B. **이번 회차 삭제는 0건이다.** 아래 목록은 사용자 승인을 받기 위한 것이다.

- C: 여유 바이트: 22:15 기준 232,149,753,856, 22:40 기준 232,147,484,672 (232.15GB). 400GB까지 **167.85GB 부족**하다.
- 세 후보를 모두 승인해 지우면 논리 바이트 **15,950,881,145 B (15.95GB)** 를 회수한다. 그래도 약 151.9GB가 부족하다. 다른 작업이 동시에 쓰므로 회수량은 보장되지 않는다.

## 규칙

- 루트 AGENTS.md·CLAUDE.md 「로컬 원본·데이터셋 삭제 금지」가 적용된다. 세션이 만든 임시 사본도 대상이다. 지우기 전에 정확한 절대 경로·파일 목록·보존 상태를 보이고, **그 대상에 대한** 명시 승인을 받아야 한다.
- 같은 절은 재귀 삭제·`robocopy /MIR`를 용량 확보 수단으로 쓰지 말라고 적는다. 그래서 승인할 때 **삭제 방법도 함께 정해야 한다**. 제안하는 방법은 다음과 같다.
  1. 파일별 manifest(경로·크기)를 먼저 쓴다.
  2. junction은 대상 폴더를 따라가지 않고 링크만 지운다(`os.rmdir`).
  3. manifest에 있는 파일만 지운다.
  4. 지운 뒤 경로가 없는지 확인한다.

## 승인 요청 목록

| 순위 | 지울 경로 (이것만) | 바이트 | 남길 것 (그 자리) |
|---|---|---:|---|
| 1 | `C:/_proj/final_workspace/scratch/st4f719-fix-20261029/` 의 `repo`, `fresh-review`, `fresh-review-final`, `fresh-review-verified` | 6,648,295,754 | 루트 파일 99개 3,140,533 B(로그·사진·runner·patch 3개), `pgdata/` 72,385,641 B |
| 2 | `C:/_proj/final_workspace/scratch/st4f734-tight724-20261029/integration724` + `repo/` 안의 캐시만(.next*·.vitest·.pytest_cache·__pycache__·tsbuildinfo 344개 277,591,573 B) | 4,280,582,873 | `repo/` 소스 3,527개 168,470,204 B, 루트 파일 129개, `pgdata/`, `end-snapshot/` |
| 3 | `C:/_proj/final_workspace/scratch/st4f719-identity-20261029/` 의 `repo`, `delivery-repo`, `baseline-repo` | 5,022,002,518 | 루트 파일 93개 2,213,012 B, `pgdata/` 73,440,236 B, `mutation-web/` 3,624,652 B |

폴더 전체 크기는 6,723,821,928 / 4,528,340,784 / 5,101,280,418 B다. 파일별 목록은 [approval-candidates.json](../evidence/2026-10-30_disk-round7/approval-candidates.json)에 있다.

## 근거

### 활성 상태
- 마지막 쓰기는 10-29 10:56 / 07:46 / 11:28이다. 34~39시간 동안 쓰기가 없었다.
- 22:21 Win32_Process 373개 중 세 폴더 이름을 참조하는 프로세스는 0개다.
- 실행 중 postgres의 `-D`는 `C:/_proj/postgresql/data/guguroute-16`과 `C:/_proj/routinga11verify1029/pgdata`뿐이다. 세 후보 안에는 `postmaster.pid`가 없다.

### 주인
| 순위 | 주인 | 근거 |
|---|---|---|
| 1 | Codex ST4F-719 리뷰 수정 세션 | [인계](../../handoff/2026-10-29_st4f719-review-fixes.md) |
| 3 | Codex ST4F-719 identity 세션 | [인계](../../handoff/2026-10-29_st4f719-identity-bound.md) |
| 2 | Codex ST4F-734 세션 | `_coord/Codex-ST4F734-tight724-NOTICE.md`: COMPLETE, 통합 예약 없음 |

- 세 인계 모두 「사본·증거 보존」이라고 적었다. 이것은 작업자의 기록이지 사용자 보존 지시는 아니다. 그래도 남길 것 열과 보존본으로 그 내용을 지킨다.
- 719의 최신 후보는 `st4f719-blocker-independent-20261029/repo`다(10-30 [작업 감사](../../handoff/2026-10-30_workstreams-readonly-audit.md)). 이 폴더는 후보에서 제외했다.

### 고유 코드
- **719 사본 7개**
  - 모두 HEAD가 `656579fe37d6`이다. GitHub에 없는 로컬 커밋 1개이고, 부모 `fab3da50ab`는 GitHub role-manager에 있다.
  - 이 커밋을 bundle로 만들었다. GitHub 저장소에서 `bundle verify`를 통과했다.
- **작업 트리 변경**: `git apply --check -R` 결과 다음과 같다.

  | 사본 | 일치하는 patch |
  |---|---|
  | fix `repo`·`fresh-review-verified`, identity `baseline-repo` | 리뷰 수정 `candidate.patch`. 원본 증거 sha256 `fe9656c1…`와 같다 |
  | `fresh-review` | `candidate-v1.patch` |
  | `fresh-review-final` | `candidate-final-fixture-error.patch` |
  | identity `repo` | identity `candidate.patch` |
  | identity `delivery-repo` | identity `candidate.patch`. diff-HEAD sha256 `d68ab05e…`가 원본 증거와 바이트 단위로 같다 |

- **패치 밖의 미추적 시험·설정 파일**: 22+11개를 복사했다(합계는 보존 절).
- **fix `repo`의 wiki 미추적 파일**: 원본 `C:/_proj/final_workspace`에 게시된 사본과 sha256이 같다.
- **integration724**
  - HEAD `fab3da50ab`는 GitHub에 있다.
  - `tf105/candidates` `a0ba3e50f`(로컬 커밋 4개)는 검증된 기존 bundle(`teamflow-105-20261028b_wt_rm.bundle`, sha256 `0ecab72f…`)에 있다. `st4f734-independent` 사본에도 있다.
  - staged된 package 변경의 diff는 `fab3da50a..ef4a3c54b` diff와 sha256이 같다.
  - 작업 트리 diff 3,139,232 B를 저장했다.
- **tight724 `repo/` 스냅숏**: GitHub 기준 고유 24개(679,065 B), LF만 일치 2,871개다. 그래서 소스는 그대로 두고 캐시만 후보에 넣었다.

### 연결
- reparse 점 768개를 검사했다. 범위는 `C:/_proj`와 `hermes` 전체이고, 디렉터리 369,191개를 오류 0으로 읽었다.
- alternates 파일 48개를 검사했다. 후보 안을 가리키는 alternates는 0개다.
- 다른 폴더가 후보를 가리키는 곳은 다음과 같다.
  - `st4f719-second-review/repo`의 origin → fix `repo`. 설정만 가리킨다.
  - `st4f734-independent/integration724`의 origin → tight724. 설정만 가리킨다.
  - `st4f719-independent/repo`의 origin → identity `delivery-repo`.
  - **`st4f719-independent-20261029/repo/.../web/node_modules` junction → identity `repo/.../web/node_modules`**. 이 링크 자체도 `st4f718-storage-20261029/r`로 가는 junction이다. 3번을 지우면 이 링크가 끊긴다. 실제 자료는 st4f718에 있어 잃지 않는다. 3번 순위가 낮은 이유다.
- 후보에서 밖으로 나가는 링크는 다음과 같다.
  - 719 사본의 alternates는 `st4f740-review-20261029/repo` 객체를 가리킨다.
  - `node_modules` junction은 `st4f718-storage`·`teamflow-unowned`를 가리킨다. 이 링크는 대상을 따라가지 않고 링크만 지워야 한다.

### 제외한 큰 폴더
| 폴더 | 크기 | 제외 이유 |
|---|---:|---|
| `st4f719-blocker-independent` | 6.11GB | 최신 HOLD 후보 |
| `st4f734-independent` | 4.50GB | `node_modules`가 `st4f719-blocker-fix`·`teamflow-next-after740`의 junction 대상 |
| `st4f719-blocker-fix` | 4.05GB | 분류하지 않음 |

## 보존 (먼저 만들었고, 삭제는 아님)

- 위치: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/disk-round7-20261030/` (파일 537개, 약 30.0MB). `README.md`에 복원 절차가 있다.
- 사본별로 보존한 것:
  - HEAD·refs·status·`diff-HEAD`·`diff-cached`
  - 미추적·무시 목록과 origin·alternates
  - `.git` 메타(objects 제외) 206개 24,206,270 B, 느슨한 객체 218개 410,351 B
  - 미추적·무시(캐시 제외) 파일 36개 173,803 B
- 모두 배타 생성으로 복사했고 sha256을 다시 대조했다.
- bundle `st4f719-656579fe.bundle`의 sha256은 `380fa4d7f94c7bf8b9625415971763b228db7861074f49169422a054372815bc`다.

## 승인 후 실행할 때의 확인

1. 지우기 직전에 다음을 다시 확인한다. 하나라도 다르면 그 후보를 중단한다.
   - 프로세스와 postgres
   - reparse 점과 origin 참조
   - 파일 목록·크기·mtime이 이번 inventory와 같은지
2. 3번을 지운다면 `st4f719-independent`의 끊긴 junction을 어떻게 할지 함께 정한다. 그대로 둘 수도 있고, `st4f718-storage`로 다시 연결할 수도 있다. 다시 연결하는 것은 다른 폴더를 바꾸는 일이다.
3. 지운 뒤 경로가 없는지, 보존본 sha256이 그대로인지, C: 여유 바이트를 확인한다.

## 기타

- `C:/_proj/k.txt`는 열지 않았다. 크기와 mtime만 확인했고 148 B, 10-25 05:09로 6차와 같다.
- 커밋·푸시·서비스·설정·skill·다른 프로필 변경은 없다.
- 증거: [approval-candidates.json](../evidence/2026-10-30_disk-round7/approval-candidates.json), [tight724-repo-unique-vs-github.txt](../evidence/2026-10-30_disk-round7/tight724-repo-unique-vs-github.txt), 실행 스크립트 `scripts-r7_*`. 프로세스 명령줄 원문과 `*-private.json` 내용은 증거에 넣지 않았다.
