---
type: report
title: final_workspace 승인 삭제 ①②③④ 65개 폴더 93.27GB 실행, final_workspace 54.68GB(100GB 미만), C: 여유 349.02GB(400GB까지 50.98GB 부족), _unified_mall_3·test_workspace 삭제 직전 보존 준비
description: 사용자 승인(11-03 15:47·15:51·15:53 Telegram)에 따라 final_workspace/scratch 63개와 .tmp/clones 2개를 manifest 대조 뒤 파일 단위로 지웠다. 건너뛴 것 0, 오류 0, 끊긴 링크 0. 보존본 해시 118/118·store 20,248/20,248 재확인. _unified_mall_3·test_workspace는 지우지 않고 최소 보존본(8.19GB)과 복원 시험까지 마쳤다
status: done
domain: ops
impl_scope: 삭제는 승인 목록의 정확한 65개 루트뿐(manifest에 있는 파일·폴더 안 링크만). 쓴 것은 guguroute backups 2곳(c400-unique-20261103/deletion-20261103, c400-projprep-20261103), 이 보고서·증거·인계·목차 줄, 기존 보고서 2개의 후속 줄. datasets·코드·Git 원본·모델·NPU·WSL·hiberfil·다른 프로필 변경 0, 커밋·푸시 0
---

# scratch 승인 삭제 실행과 남은 프로젝트 폴더 준비 (2026-11-03 15:52–17:2x KST)

앞선 기록: [분류·승인 목록](2026-11-03_scratch-unique-classification-approval.md), [400GB 달성 시점 대비](2026-11-03_c-drive-400gb-peak-vs-now.md), [10차](2026-11-03_c-drive-400gb-cleanup-round10.md). 인계: [2026-11-03_scratch-approved-deletion-handoff](../../handoff/2026-11-03_scratch-approved-deletion-handoff.md). 단위는 GB = 10⁹ B다. 근거 등급은 [근거 등급](../../governance/evidence-grades.md)을 따른다.

**결론 한 줄**: [실측] 승인된 65개 루트 1,217,470파일 93,266,602,317 B를 오류 0으로 지웠고 final_workspace는 54.68GB(100GB 미만)지만, C: 여유는 349.02GB로 400GB까지 50.98GB 부족하다 — 남은 후보는 `_unified_mall_3` 25.31·`test_workspace` 12.65(보존 준비 끝, 사용자 승인 대기)와 hiberfil 13.10(관리자)이다.

## 결과

| 항목 | 값 | 등급 |
|---|---|---|
| 삭제 루트 | 65/65 = 100% (scratch 63 + `.tmp/clones` 2), 건너뜀 0 | [실측] |
| 삭제 파일·바이트 | 1,217,470개 · 93,266,602,317 B, 디렉터리 128,449개, 오류 0 | [실측] |
| 폴더 안 junction 링크 | 41개를 링크만 `os.rmdir` (대상은 따라가지 않음) | [실측] |
| 삭제 뒤 경로 부재 | 65/65 부재, 달성 시점 폴더 19/19 그대로, `.disk_guard_ledger.json` 남김 | [실측] |
| 끊긴 링크 | 삭제 경로를 가리키는 junction·alternates·gitdir·remote **0** (디렉터리 234,727개 검사, 오류 0). 기존부터 끊긴 링크 12개는 무관 | [실측] |
| 보존본 재확인 | `c400-unique-20261103/SHA256SUMS.txt` 118/118, `store` 20,248/20,248(압축 풀어 sha256), hold3 보존 213/213·117/117 | [실측] |
| C: 여유 | 15:54 267,543,351,296 → 16:03:53 362,658,086,912 → 17:06:34 **349,017,649,152 B** | [실측] |
| 400GB까지 | **50,982,350,848 B 부족** (349.02/400 = 87.25%) | [실측] |
| final_workspace | 17:1x 논리 **54,677,926,238 B**, 할당 55,899,430,912 B (100GB 대비 54.68%) | [실측] |

- 묶음별 순서와 여유(삭제 직전→직후, [실측]):

  | 묶음 | 루트 | 파일 | 바이트 | 여유 직전 → 직후 |
  |---|---:|---:|---:|---|
  | ① 7차 후보 | 3 | 246,705 | 16,353,443,130 | 267,539,841,024 → 284,186,775,552 |
  | ④ `.tmp/clones` | 2 | 98,054 | 9,839,389,277 | → 294,256,824,320 |
  | ② HOLD 후보 | 4 | 134,225 | 12,463,029,463 | 294,256,816,128 → 306,993,565,696 |
  | ③ 나머지(`st4f740-review` 마지막) | 56 | 738,486 | 54,610,740,447 | 307,001,425,920 → 362,658,086,912 |

- 15:58:07→16:03:53 실측 여유 증가는 95,118,245,888 B로 논리 삭제량보다 1.85GB 크다(클러스터 반올림). [추정]
- 16:03 뒤 13.6GB가 다시 줄었다. 이 세션의 보존본 8.19GB(아래)와 다른 세션의 `.tmp/clones/backup-push-1103`(16:10 생성, ledger `leased`, 4.93GB) 때문이다. 나머지는 확인하지 않았다. [실측·일부 미확보]

## 실행 방법과 검사

1. **승인 기록 먼저**: 사용자 원문과 일시를 [인계](../../handoff/2026-11-03_scratch-approved-deletion-handoff.md)에 적은 뒤 시작했다.
2. **직전 대조**(루트마다, 삭제 바로 전): 재분석 지점을 따라가지 않고 다시 셌고, 63개는 c400 manifest와 경로·크기·mtime이 모두 같았다(새 파일 0·크기 변경 0·mtime 변경 0·누락 0). `.tmp/clones` 2개는 manifest가 없어 이번에 만들었고(`deletion-20261103/clones-*.manifest.jsonl.gz`), 바이트가 ledger `measured_bytes`와 정확히 같고(7,219,351,447·2,620,037,830) 05:40 뒤 수정 0, 상태 `idle`인 것을 확인했다.
3. **프로세스·소유자**: 묶음마다 `Win32_Process` 명령줄·실행 경로 223–235개 중 참조 0. 07:50 뒤 Hermes 두 프로필·Codex rollout에서 대상 이름을 쓴 세션은 이 세션·부모·cron 「작업 흐름 중단 감시」(문서 읽기만)뿐이었다. ② 실행 직전 새 cron 세션 1개가 나타나 한 번 멈췄고, 읽기 출력에만 이름이 있는 것을 확인한 뒤 진행했다.
4. **삭제**: 링크는 `os.rmdir`, 파일은 manifest와 크기·mtime이 같을 때만 `os.unlink`, 빈 디렉터리는 깊은 것부터 `os.rmdir`. `git clean`·`robocopy /MIR`·`rm -r` 등 재귀 삭제 도구는 쓰지 않았다.
5. ②(HOLD 4개)는 15:5x 사용자 추가 지시로 범위에 들어왔다. 4개 저장소가 `st4f740-review`를 alternates로 쓰므로 ②를 먼저, `st4f740-review`를 ③의 마지막에 지웠다. `teamflow-unowned`와 `st4f729-followup`은 연달아 지웠다.

## 건너뛴 것과 남은 주의

- 건너뛴 루트 **0**.
- `.tmp/clones/.disk_guard_ledger.json`에 지운 두 사본 항목이 `idle`로 남아 있다. 설정 파일이라 고치지 않았다. 담당(36cd5c)이 `release`/정리하거나 다음 `inventory` 때 정리된다. [실측]
- wiki 문서 여러 개가 지운 scratch 경로를 링크한다. 내용은 c400 manifest로 복원할 수 있다(대상 표 [list.md](../evidence/2026-11-03_scratch-unique-approval/list.md), 복원 절차 `backups/c400-unique-20261103/README.md`).
- cron 감시 문서 표의 「`scratch/st4f719-blocker-independent-20261029/repo` 기존 사본 우선 사용」 줄은 이제 맞지 않는다. 그 작업을 다시 열면 manifest로 복원해야 한다.

## final_workspace 크기 (목표 100GB 미만)

- [실측] 17:1x 논리 54,677,926,238 B · 할당 55,899,430,912 B · 파일 558,297개 · 재분석 지점 0. 하드링크는 한 번만 셌다.
- [실측] 삭제 직후 16:05에는 49,748,047,749 B(할당 50,842,705,920)였다. 차이는 다른 세션의 `backup-push-1103` 사본(`.tmp/clones` 4.93GB, 일부 `.git` 팩 하드링크)이다.
- [추정] 삭제 전은 약 143.01GB(16:05 값 + 삭제 93.27GB).
- 큰 구성(논리, [실측]): `datasets/travel` 11.63 · `datasets/ml` 8.14 · `.tmp/clones` 4.93 · `program/scripts` 4.27 · `datasets/mobility` 3.66 · `datasets/core` 3.04 · `datasets/_archive` 1.88 · `final_project_cs/frontend` 1.66 · `datasets/voc` 1.59 · `datasets/_recovery` 1.55 · `.git` 1.45 · `program/research` 1.06. 전체 표는 [final_workspace_size.json](../evidence/2026-11-03_scratch-approved-deletion/final_workspace_size.json).
- **낭비 후보**(바꾸지 않음, 옵션만, [실측] [waste_candidates.json](../evidence/2026-11-03_scratch-approved-deletion/waste_candidates.json)):
  - sha256이 같은 1MiB 이상 파일 322묶음, 중복분 11,450,688,995 B. 대부분 `datasets` 안(`ml` 3.76, `core`·`travel`·`program/scripts` 1.75, `core`·`travel` 1.24, `mobility` 1.17)이라 삭제 금지 대상이다. 옵션: 이관 때 내용 주소 압축 보관(tar.zst + manifest)으로 한 벌만 옮기기. 하드링크는 쓰지 않는다.
  - 재생성 캐시 1,478,264,013 B(`frontend/apps/{admin,web}/node_modules` 0.99, `.next*` 0.46 등). 활성 실행기가 쓰는지 확인한 뒤에만 지울 수 있다.
  - `.tmp` 옛 작업 사본(`manager_recovery_20261012` 0.58, `location-controls-20261011` 0.32 등)은 대상별 승인이 필요하다(AGENTS.md).

## `_unified_mall_3`·`test_workspace` — 삭제 직전 준비 (지우지 않음)

보존본: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/c400-projprep-20261103/` (`README.md` 복원 절차, `SHA256SUMS.txt` 174/174).

| | `C:/_proj/_unified_mall_3` | `C:/_proj/test_workspace` |
|---|---|---|
| 크기 [실측] | 25,314,085,642 B · 100,506 파일 | 12,652,794,811 B · 191,360 파일 |
| 정체 | 보험 약관 RAG 프로젝트(옛 PC `playdata2/Documents/llm_workspace`에서 10-24 복사). `.git`에 `info/exclude`만 있어 **Git 이력 없음** | 개인 프로젝트 모음(GitHub `roroblack/*` 등). 실제 저장소 12개 + 끊긴 worktree 18개 |
| 프로세스·링크 [실측] | 참조 0, 들어오는 junction 0. `final_workspace/.claude/launch.json`은 옛 PC 경로라 이 폴더를 가리키지 않음 | 참조 0, junction 0 |
| 미커밋·고유 [실측] | 해당 없음(Git 없음) → 캐시 1.06GB를 뺀 전부가 고유 | 미푸시 커밋 yok3x 22·gPUteer 40·npu_sm8735 7(원격 없음)·keyword_dictionary 2(원격 없음), stash 1, 미추적·수정 파일 다수 → 모두 bundle·store에 보존 |
| DB·데이터 | `data/pgdata`(PG16, 7.41GB, `postmaster.pid` 없음 = [추정] 정상 정지). 10-25 세션 36cd5c가 「source, 중지·보존」으로 기록. `.env` 1개(내용 미열람, store에만) | `.venv`·Rust `target/`·pytest 임시 9.51GB는 재생성 캐시 |
| 보존 방식 | 캐시 제외 전부를 내용 주소 tar.zst로: 고유 52,566개 22,641,501,563 B → **6,954,323,517 B** | 저장소 12개 `bundle --all` 541,563,269 B(얕은 2개는 `.shallow` 동봉) + Git으로 재현 안 되는 파일 고유 11,305개 → **664,309,663 B** + 혼합 EOL 90개 4,355,163 B |
| 검증 [실측] | store 구성원 52,566/52,566 sha256 일치. 표본 복원 2,067/2,067 | bundle 단독 fetch 12/12. **전체 복원 48,767/48,767**(캐시·.git/objects 제외 전 파일) |
| 보존하지 않는 것 | 캐시 1.06GB | 캐시 9.51GB, ref에서 도달 불가한 Git 객체 |
| 소유자 | 사용자(옛 프로젝트). 36cd5c의 「보존」 기록이 있어 **사용자 승인 필요** | 사용자. 단 `npu_sm8735`(0.57GB)는 NPU 세션 `local-445eeffb…`(기본 프로필)이 10-27–10-29에 썼다 → NPU 소유자 확인 전 제외 권장. `jira_for_me/mcp-server`는 10-28 TeamFlow 조회에 수동 실행(설정 등록 없음) |
| **삭제 가능 여부** | **가능(사용자 승인 후)**. 보존·검증 완료 | **가능(사용자 승인 후)**, `npu_sm8735`는 NPU 소유자 확인 후 |
| 삭제 시 회수 | 25.31GB | 12.65GB (`npu_sm8735` 빼면 12.08GB) |

## 400GB까지 남은 것 (한 줄씩)

- 부족분 [실측]: **50.98GB** (17:06:34 기준, 동시 쓰기로 변함).
- ② HOLD: 이번에 삭제 완료(12.46GB) — 남은 후보 아님.
- `_unified_mall_3` 25.31GB: 보존·검증 완료, 사용자 승인만 남음.
- `test_workspace` 12.65GB: 보존·검증 완료, 사용자 승인(+`npu_sm8735` NPU 소유자 확인).
- `hiberfil.sys` 13.10GB: 관리자 `powercfg /h off`.
- NPU `frog-npu-dev` 65.04GB: 소유자 결정(`h16-here` 8.04·`h1-eps3` 5.28·F16 GGUF 8.67 등).
- WSL `ext4.vhdx` 47.59GB: 내부 정리 뒤 `wsl --shutdown`·관리자 압축.
- 예시 조합: `_unified_mall_3` + `test_workspace` + `hiberfil` = 51.06GB ≥ 50.98GB. [추정] 여유가 거의 없어 동시 쓰기가 있으면 모자랄 수 있다.

## 이관 때 옮길 총량 ([실측] 17:1x 논리 바이트, 하드링크 1회)

| 위치 | 바이트 |
|---|---:|
| `C:/_proj` (final_workspace 54.68 · `_unified_mall_3` 25.31 · test_workspace 12.65 · guguroute 10.31 · postgresql 1.57 · `_3rd_project_4` 0.95) | 105.47GB |
| Hermes 전체 `AppData/Local/hermes` (프로필·모델·backups, 이 세션 보존본 8.19GB 포함) | 218.03GB |
| `frog-npu-dev` | 65.04GB |
| WSL `ext4.vhdx` | 47.59GB |
| `models`·`_preserved`·`.codex`·`llama.cpp`·`.claude` 등 | 4.45GB |
| **합계** | **약 440.6GB** |

두 폴더를 승인 삭제하면 약 402.6GB다. Desktop·Documents 등 다른 사용자 폴더는 재지 않았다. [미확보] 원자료: [migration_sizes.json](../evidence/2026-11-03_scratch-approved-deletion/migration_sizes.json).

## 증거

[evidence/2026-11-03_scratch-approved-deletion/](../evidence/2026-11-03_scratch-approved-deletion/):
- 루트별 결과: `deletion_roots.json`
- 링크 검사: `junction_check.json`
- 크기: `final_workspace_size.json`
- 낭비 후보: `waste_candidates.json`
- 준비 요약: `prep_*_summary.json`, `test_workspace_git_status.txt`
- 이관 크기: `migration_sizes.json`

삭제 로그·스크립트 원본(65행 결과, 직전 dry-run, 사전 점검, 측정)은 `backups/c400-unique-20261103/deletion-20261103/`에 있다. 프로세스 명령줄 원문은 넣지 않았다.

## 관계

- [분류·승인 목록](2026-11-03_scratch-unique-classification-approval.md) — 이번 삭제의 대상 목록과 보존 근거
- [400GB 달성 시점 대비](2026-11-03_c-drive-400gb-peak-vs-now.md) — 증가분 원인
- [10차](2026-11-03_c-drive-400gb-cleanup-round10.md) — 직전 여유 시계열
- [디스크 증가 예방 가드](2026-10-29_disk-growth-guard.md) — `.tmp/clones` ledger
