---
type: report
title: C:/_proj 지정 38개 중 남은 13개 — 독립 보존 검증 뒤 삭제 13/13, 지정 38개 전체 완료 (2026-11-02)
description: 새 담당 하위 세션이 남은 13개의 보존본(커밋 8개, DB 4개, 증거, 비밀 이름 파일)을 sha256으로 다시 대조하고, 오프라인 bundle 복원을 실측했다. Explorer 핸들이 풀린 것을 네이티브 조회로 확인한 뒤 Hermes terminal 승인 경로로 정확한 13개 경로만 삭제했다. 유실은 0건이다
status: done
domain: ops
impl_scope: 운영 기록. 제품 코드와 설정은 바꾸지 않았다. C:/_proj 대상 13개만 삭제했고, final_workspace는 이 보고서와 인계 목차 한 줄만 추가했다
---

# C:/_proj 남은 13개 최종 처리 (2026-11-02 22:23–22:50 KST)

- 수행: 구구루트 Telegram 총괄 `20261027_205452_5fbd35ab`의 하위 세션 `20261102_222226_bbe8c7`.
- 앞선 기록:
  - [38개 담당 직접 처리 감독](2026-11-01_proj-root-38-owner-relay-and-blockers.md)
  - guguroute `backups/proj-folder-audit-20261031/HANDOFF.md`
- 비공개 보존과 검증 자료: guguroute `backups/proj-root13-final-20261102/` (`README.md`에 복원 절차가 있다). 담당 Codex 스레드들이 만든 기존 보존본은 `backups/proj-folder-retire-20261031/<이름>/`에 있다.
- 단위: B.
- 10-31·11-01 기록에 있던 scratch `del38/`(status.py·codex_out)는 이미 정리돼 없었다. 그래서 그 기록이 아니라 디스크의 보존본을 기준으로 다시 검증했다.

## 결과

- **삭제 13/13 = 100%.** 지정 38개 전체로는 **38/38 = 100%**다. 22:50에 13개 경로가 모두 없는 것을 확인했다.
- 지금 `C:/_proj`에 남은 항목은 `_3rd_project_4`, `_unified_mall_3`, `final_workspace`, `guguroute`, `h7407ba`, `k.txt`, `mynews`, `postgresql`, `test_workspace`다. 모두 대상 밖이라 건드리지 않았다.
- 삭제 전 원본은 파일 35,745개, 3,330,411,092 B였다.
- C: 여유 공간은 22:44 255,185,264,640 B에서 삭제 후 258,584,367,104 B가 됐다(+3,399,102,464 B). 같은 시간에 다른 프로그램도 디스크를 쓰고 있었으므로 이 차이가 정확히 삭제분이라고 보장하지는 않는다.
- **유실 0건.** 원본 파일 35,745개는 모두 아래 넷 중 하나에 해당한다. 넷 중 어디에도 해당하지 않은 파일은 0개다.
  - sha256이 같은 보존본이 있다. 기존 보존본, tar·zip 내부, wiki, datasets 중 하나다.
  - Git 추적 파일이고 작업 트리가 깨끗하다.
  - Git 메타데이터이고 따로 보존했다.
  - Hermes Git 도구와 같은 사본이다.
- 기존 보존본에 없던 소량 파일 26개(1.98 MB)는 이번에 새로 복사했다. `__pycache__`, `.pytest_cache`, `tokenizer-cache` 같은 파일이다. 복사할 때 기존 파일을 덮어쓰지 않았고, 원본과 복사본 양쪽을 다시 해시해 일치를 확인했다.

## 폴더별 증거

| 폴더 | 파일 / B | 마지막 수정 | 의존·활동 (22:30, 22:44 실측) | 완성도 (wiki 인계) | 보존 / 이번에 추가 |
|---|---|---|---|---|---|
| busreview1029 | 1 / 769 | 10-29 18:41 | 없음 | COMPLETE ([bus scalar](../../handoff/2026-10-29_bus-scalar-independent-continuation.md)) | RETIRED.md 일치 / 0 |
| ekscheckingcontinue1029 | 2,058 / 77,129,498 | 10-29 18:45 | 없음. pgdata는 정지 상태 | PR110 draft HOLD ([인계](../../handoff/2026-10-29_eks-checking-amd64-validation-and-baseline-fatal.md)) | pgdata.tar.gz와 files 일치 / pyc 5개 |
| eksdawn_causality_1029 | 18 / 732,841 | 10-29 11:04 | 없음 | HOLD ([인계](../../handoff/2026-10-29_eks-dawn-first-vehicle-causality.md)) | 일치. 커밋 5개 bundle 보관 위치 / 0 |
| eksdeep1029 | 75 / 753,237 | 10-29 18:43 | 없음 | COMPLETE/HOLD ([인계](../../handoff/2026-10-29_eks-full-data-latitude-pruning.md)) | 일치 / pyc 2개 |
| eksfatal1029 | 50 / 200,687 | 10-29 18:44 | 없음. 감사 #6/#7 참조는 10-31에 보존 경로로 바뀌어 있음 | HOLD ([오프라인 분리](../../handoff/2026-10-29_eks-reading-fatal-offline-discrimination.md), [감사](../../handoff/2026-10-30_workstreams-readonly-audit.md)) | 일치 / 0 |
| eksgolden_causality_1029 | 52 / 1,230,212 | 10-29 11:39 | 없음 | COMPLETE/HOLD. 513ab4cc 미푸시 ([인계](../../handoff/2026-10-31_eksgolden-causality-retirement.md)) | 일치. 전체 이력 bundle / pyc 1개 |
| eks-independent-1029 | 145 / 1,461,681 | 10-29 21:37 | 없음 | HOLD ([검토](../../handoff/2026-10-29_eks-route-fix-independent-review.md)) | 일치. 1ab3f0d88 bundle / pyc 1개 |
| eksmix_selection_1029 | 30 / 5,997,822 | 10-29 11:12 | 없음 | HOLD ([인계](../../handoff/2026-10-29_eks-mixed-selection-causality.md)) | 일치 / .pytest_cache 2개 |
| eksobserve1029 | 27 / 128,524 | 10-29 18:44 | 없음 | HOLD ([인계](../../handoff/2026-10-29_eks-reader-observability-boundary.md)) | 일치 / 0 |
| eksperf1029 | 2,023 / 74,233,156 | 10-29 18:44 | 없음. pgdata는 정지 상태 | COMPLETE ([인계](../../handoff/2026-10-29_eks-operational-performance-continuation.md)) | pgdata.tar.gz 일치 / pyc 1개 |
| eksprecision1029 | 29,109 / 3,091,046,694 | 10-29 18:41 | 없음. 핸들 0, 프로세스 0 | HOLD. 잔여 18건, 로컬 커밋 3개 ([인계](../../handoff/2026-10-29_eks-linux-precision-expectations.md)) | 아래 「eksprecision1029」 / 7개 1.91 MB |
| eksscalar1029 | 2,095 / 76,426,397 | 10-29 18:42 | 없음. Explorer 핸들 해소 | RELEASED. PR109 병합 ([인계](../../handoff/2026-10-29_eks-scalar-release-and-measurement.md)) | pgdata.zip 일치 / pyc 6개 |
| eksserve1029 | 62 / 1,069,574 | 10-29 18:43 | 없음 | COMPLETE/HOLD ([인계](../../handoff/2026-10-29_eks-serving-bottleneck-partition.md)) | 일치 / pyc 1개 |

- 위 표의 「일치」는 그 폴더의 모든 파일이 sha256이 같은 보존본을 가진다는 뜻이다.
- 모든 폴더에서 reparse 점 0, NTFS ADS 0, `postmaster.pid` 0이었다.
- 삭제 직전에 크기와 mtime을 다시 비교했다. 신규 0, 사라짐 0, 변경 0이었다.
- 대상 밖에서 대상 안으로 향하는 Git 원격·alternates·설정 참조는 0개다. 검사 범위는 `C:/_proj`, guguroute scratch, `final_workspace/scratch`, `final_workspace/.tmp`이고 깊이 5까지 봤다.
- cron `a19614eada92`(작업 흐름 감시)는 출력 기록에 폴더 이름이 나올 뿐이다. 실행 경로로 이 폴더들을 쓰지 않는다.

### eksprecision1029 세부

- `candidate` 체크아웃:
  - HEAD `346a57d4d`, `git diff HEAD`는 비어 있다. 미추적 XML 2개는 wiki의 같은 파일과 일치한다.
  - 추적 파일 17,306개(1,267,093,999 B)는 Git 객체로 복원된다.
  - 로컬 커밋 3개(`3e5a60af6`, `acf0fadcd`, `346a57d4d`)는 `unique.bundle`에 있다. 선행 커밋은 57f3d2f다.
- 오프라인 복원 실측:
  - 빈 bare repo에 golden 전체 bundle을 fetch하면 57f3d2f가 생긴다.
  - 그 상태에서 precision, dawn, independent bundle 3개가 모두 verify rc=0이었다.
  - precision bundle의 tree `2a2dbbb85cbd…`는 candidate HEAD의 tree와 같고, fsck rc=0이었다.
  - 삭제 후에도 bundle verify rc=0이었다.
  - GitHub 팀 main도 57f3d2f다.
- Git 메타데이터(99개, 715,197,579 B):
  - 이력은 bundle로 대체된다.
  - 추가로 보존한 것: 도달 불가 blob 17개를 담은 pack(`verify-pack ok`), objects를 뺀 `.git` tar, `ls-files`, refs, status. reflog의 커밋 4개는 모두 bundle 안에 있다.
- `.retire-tools` 7,623개(389,167,978 B): Hermes 설치본 `agent-payload/tools/git-2.53.0+3-win32-arm64`와 7,623개 모두 sha256이 같다. 11-01에 STOP 조건이 됐던 항목인데, 재생성할 수 있는 도구 사본으로 판정을 정리했다.
- `pgdata-preserved`: `db/pgdata-preserved.tar.gz` 내부 파일과 일치한다.
- 이번 세션은 candidate의 `.git`에 쓰지 않았다. 예외는 `pack-objects` 하나인데, 출력은 절대 경로로 보존 폴더에 썼다.

## 커밋 8개와 HOLD 연쇄

- `eksprecision1029` 3개는 `proj-folder-retire-20261031/eksprecision1029/git/candidate/unique.bundle`에 있다.
- 이미 삭제된 `eksremaining1029`의 5개(`ee8ca8807`까지)는 `eksdawn_causality_1029/wsl-dawn-local-commits.bundle`과 golden 전체 bundle에 있다.
- WSL 쪽 커밋 `513ab4cc`(golden)와 `1ab3f0d88`(independent)도 bundle로 보존돼 있다.
- HOLD 연쇄의 원천이던 체크아웃은 이제 bundle로만 남는다. 통합할 때는 위 bundle로 격리 사본을 만든다. 복원 명령은 보존 폴더 `README.md`에 있다.

## 비밀 이름 파일

- 이름 패턴에 걸린 프로젝트 증거 11개는 모두 비공개 `backups/`나 기존 wiki에 같은 sha로 있다: `envcheck.sh`, `push-authenticated.log`, `replay-paid_auth.json`×2, `pg-env.json`, tokenizer 관련 6개.
- candidate의 `.env*.example` 8개는 Git 추적 파일이라 bundle에 들어 있다.
- 내용은 열거나 출력하지 않았다. 유실은 0개다.

## 승인과 Explorer

- 삭제는 Hermes terminal의 `rm -rf --one-file-system` 한 번으로 했다. 대상은 정확한 13개 절대 경로뿐이었다.
- 이 명령은 smart approval이 위험 명령으로 표시했고 자동 승인했다. 거부된 적이 없어서 반복이나 우회는 없었다. Codex 스레드는 다시 실행하지 않았다.
- 11-01에 핸들을 쥐고 있던 explorer PID 11372는 이미 없다. 지금 셸은 PID 10512이고, 이 세션이 시작하거나 종료한 것이 아니다.
- 22:30과 22:44에 네이티브 핸들 조회(`NtQuerySystemInformation`)를 했다. 대상 경로를 가진 핸들은 두 번 모두 0개였다.
- 프로세스 종료, 화면 조작, 재부팅은 0건이다.

## 확인하지 못한 것과 남은 일

- **WSL `Ubuntu`는 Stopped 상태라 시작하지 않았다.**
  - `/root/eks*`가 `/mnt/c/_proj/<대상>`을 참조하는지는 eksserve에서 확인되지 않았다.
  - 그 참조가 있었다면 이제 끊긴다. 다만 해당 커밋은 bundle에 있다.
- **남은 실질 작업은 위 표의 각 wiki 인계에 있다.** 폴더가 없어져도 인계의 결론과 증거는 wiki와 보존본에 남는다.
  - EKS 정밀 잔여 18건과 PR110 HOLD
  - reader fatal #6/#7: 관측 로그 확보
  - golden 513ab4cc와 1ab3f0d88 후보의 통합 여부
- 이 작업들의 담당 결정은 총괄 세션 `5fbd35ab`의 몫이다. 이 하위 세션의 결과 보고가 그 세션에 직접 돌아간다. 실행 중인 부모에게 gateway로 별도 메시지를 넣지는 않았다.
- 검증용 scratch(`cache/scratch/root13-bundleverify`)는 삭제했다.
