---
type: report
title: scratch 승인 삭제 65개 독립 재검증 — 삭제·보존·크기 통과, 문서 불일치 5건(승인 인용·worktree 역참조 3·MM 주장·용량 귀속·여유 수치)
description: 직전 삭제 작업자(세션 20261103_155209_afc3cb) 보고를 믿지 않고 디스크·해시·state.db를 직접 다시 확인했다. 읽기 전용이며 쓴 파일은 이 보고서 하나다(임시 복원본·스크립트는 profile scratch에 만들었다가 지웠다)
status: done
domain: ops
impl_scope: 검증만 했다. 파일 수정·삭제 0(이 보고서 신규 1개, 목차·인계 미갱신). 임시 복원·스크립트는 guguroute cache/scratch/xv1103 안의 내 파일만 만들고 지웠다(같은 폴더의 다른 세션 파일 guide.md·fw.diff·rm.diff·rt 등은 건드리지 않음)
---

# scratch 승인 삭제 독립 재검증 (2026-11-03 17:20–17:35 KST)

대상: [실행 보고서](2026-11-03_scratch-approved-deletion-and-project-prep.md), [인계](../../handoff/2026-11-03_scratch-approved-deletion-handoff.md)의 「독립 재검증 입력」. 단위는 GB = 10⁹ B다.

**결론**: [실측] 삭제·보존·크기는 모두 맞다(65/65 부재, 보존 해시 전부 일치, 복원 시험 930/930, final_workspace 49.75GB). 문서에는 불일치 5건이 있다. 승인 인용, `.git/worktrees` 역참조 3개, `MM` 주장, `backup-push` 용량 귀속, C: 여유 수치다. 데이터 손실은 0건이다.

## 1. 삭제 범위

| 검사 | 결과 | 판정 |
|---|---|---|
| 65개 루트 부재 (`approval_list.json` post_peak 63 + `.tmp/clones` 2, `deletion_roots.json`과 경로 집합 일치·중복 0) | 65/65 = 100% 부재 | 통과 |
| 달성 시점 폴더 19개 존재 | 19/19 = 100% | 통과 |
| 19개 내용 불변: 현재 파일 목록을 c400 manifest(07:30, 삭제 전)와 경로·크기·mtime 대조 | 19/19 = 100%. 누락·변경·새 파일 0 | 통과 |
| `.tmp/clones/.disk_guard_ledger.json` | 1/1 존재 | 통과 |
| 삭제 밖 최상위 항목: 17:10 인벤토리(`final_workspace_size.json` 1,160키)와 대조 | `datasets` 255,938개·34,071,144,278 B. 05시 10차 보고서의 삭제 전 값과도 같다. `.backup` 704개·472,791,918 B, `program`·`final_project_cs`·`final_project_ui`·`final_project_sample`·`team_branch`·`tools`·`scripts`·`tests`·`.git`·`acop_dojo`·`output`, `scratch` 16,804개·562,508,509 B, `.tmp`(clones 제외)는 개수·바이트가 모두 같다 | 통과 |
| 바뀐 것 ① `wiki` | 파일 +17개, +425,897 B로 추가만 있다. `git status`에서 wiki의 추적 파일 삭제는 0이다 | 통과(다른 세션의 문서 추가) |
| 바뀐 것 ② `.tmp/clones` | −50,875개, −4,929,872,157 B. `backup-push-1103`·`-rm`이 17:12 뒤 사라졌다. ledger에는 `released_at 17:18:08`(bk1103-backup-push)로 기록돼 있다. 65개 목록에는 없고, 삭제 보고서도 「건너뜀」으로 적었다. 누가 지웠는지는 **확인불가** | 이번 실행과 무관 |
| 추적 파일 4개가 작업 트리에 없음 (`docs/activity/…2026-10-12.md` 2개, `legacy/personal-role-manager/…/trip-home.*` 2개) | 삭제 루트 밖에 있고 17:10 인벤토리에도 없었다. `.git/index` mtime은 10-24다. 언제 사라졌는지는 **확인불가** | 이번 실행과 무관 |

한계: wiki·코드·`.backup`은 **삭제 뒤** 17:10 인벤토리와만 비교했다. 삭제 전 비대상 측정본(`deletion-20261103/measure_nontarget.json`)을 읽는 호출은 도구 승인 단계에서 막혀 실행되지 않았다. 따라서 이 셋은 삭제 전후 비교가 **확인불가**다. `datasets`의 삭제 전 값과 scratch 19개는 삭제 전 근거로 확인했다.

## 2. 보존본 해시와 복원 시험

| 보존본 | 재계산 | 보고치 | 판정 |
|---|---|---|---|
| `c400-unique-20261103/SHA256SUMS.txt` | 118/118 | 118/118 | 통과 |
| `c400-unique-20261103/store` (gzip을 풀어 sha256 = 파일 이름) | 20,248/20,248. manifest 82개의 store 참조 20,248개가 모두 있고, 참조 없는 store 파일도 0개 | 20,248/20,248 | 통과 |
| `c400-projprep-20261103/SHA256SUMS.txt` | 174/174 | 174/174 | 통과 |
| `c400-docs-20261103/SHA256SUMS.txt` | 27/27 | 27/27 | 통과 |
| `hold3-integ-1102/SHA256SUMS` | 213/213 | 213/213 | 통과 |
| `hold3-eks-precision-r18-1102/SHA256SUMS` | 117/117 | 117/117 | 통과 |
| 두 hold3의 `scratch-extra-1103/SHA256SUMS` (보고서에는 없음) | 그대로 `sha256sum -c`를 돌리면 0/15·0/58이다. 줄 끝이 CRLF라서다. CR을 빼면 15/15·58/58 | — | 내용 통과, 형식 주의 |

복원 시험은 README 절차를 그대로 따랐다. 임시 bare 저장소를 만들고, 원본 `.git/objects`는 읽기 전용 alternates로 붙였다. 여기에 GitHub를 fetch하고 `restore_top.py prep`, `checkout-index`, `fix`를 차례로 돌린 뒤, 따로 짠 sha256 전수 대조를 한 번 더 했다.
- `st4f711-preflight-20261029-012520`: 17/17 = 100%. 내역은 git_blob 5, git_blob_lf 4, store 8이고, 캐시 1개는 설계상 제외했다.
- `st4f718-storage-review-20261029`: 913/913 = 100%. 내역은 store 115, empty 83, elsewhere 5, git_blob_lf 653, git_blob 57이고, browser_cache 16개는 제외했다.
- 주의: 첫 시험의 blob 9개 중 4개는 원본 `.git`에 없어서 GitHub fetch를 해야 복원됐다. bundle만으로 복원하는 경로(오프라인)는 이번에 시험하지 않았다(**확인불가**).
- 임시 복원본과 objrepo는 시험 뒤 지웠다.

## 3. 크기와 여유

- [실측] final_workspace(17:23): 논리 **49,748,479,978 B**, 507,439개 파일. 하드링크는 한 번만 셌고 재분석 지점은 따라가지 않았다(재분석 지점 0, 오류 0). 할당 바이트는 4KiB 반올림 추정으로 50,843,172,864 B이며 실제 할당과는 다를 수 있다. **100GB 미만 1/1 통과(49.75%)**.
- 보고서의 17:10 값 54,677,926,238 B와는 이렇게 맞아떨어진다: 54,677,926,238 − 4,929,872,157(clones 사본 2개 제거) + 425,897(wiki 추가) = 49,748,479,978로 정확히 같다.
- [실측] C: 여유는 **344,702,279,680 B(17:25:15)**, 343,799,287,808 B(17:30:41)다. 보고서의 349,017,649,152 B(17:06)보다 약 5.2GB 적고 계속 줄고 있다. 원인은 동시에 쓰는 작업으로 보이지만 귀속은 **확인불가**다. 위임 문맥의 「약 349.47GB」는 보고서·인계 어디에도 없는 값이다(보고서는 349.02, 17:13 349.016).

## 4. 끊긴 참조

검사 범위는 C:/_proj, hermes 전체, frog-npu-dev, .codex, Desktop, frog-npu-projection-experiment, llama.cpp, models, _preserved, Documents, .claude다. 디렉터리 263,022개, 재분석 지점 15개를 봤고 오류는 0이다.

| 항목 | 결과 |
|---|---|
| 삭제 경로를 가리키는 junction·symlink | 0 |
| `objects/info/alternates` | 0 |
| git config의 remote·경로 | 0 |
| `.git` 링크 파일(gitdir:) | 0 |
| 실행 중 프로세스(Win32_Process 235개의 명령줄·실행 경로에서 65개 이름 검색) | 0 |
| `git worktree list` (final_workspace) | 3개, 삭제 경로에 있는 것은 0 |
| **`.git/worktrees/*/gitdir` 역참조** | **3개**. `backups/scratch-candidates-20261029d/files/st4f711-backend-20261029-v1/repo/.git/worktrees/{repo,repo1,repo2}/gitdir`이 지운 `scratch/st4f597-review-20261029/repo`·`st4f729-independent-20261029/repo`·`teamflow-next-20261029/repo2`를 가리킨다 |

worktree 역참조 3개는 10-29 보존본 안의 `.git` 사본이고 활성 허브가 아니다. 데이터 손실은 없고, 그 사본에서 `git worktree list`를 돌리면 prunable로 보일 뿐이다. 그래도 보고서의 「gitdir 0」(`junction_check.json` `gitdir_into_deleted: []`)은 이 종류를 검사하지 않은 결과로 보인다. 「끊긴 링크 0」은 이 범위에서는 엄밀히 맞지 않는다.

기존부터 끊겨 있던 링크: 내 검사는 1개를 찾았다(`date_risk_baseline_03/.../node_modules`). 보고서 목록의 첫 항목과 같다. 나머지 11개(venv symlink)는 내 스크립트가 분류하지 못했다(**확인불가**). 삭제와는 무관하다.

## 5. 문서 불일치·과장

1. **승인 인용.** 인계에 적힌 원문 5개는 부모 세션 `d047d36a`의 state.db와 글자·시각이 모두 같다(5/5). 다만 다음이 다르다.
   - 보고서 description, `handoff/index.md`, `log.md`, 분류 보고서 후속 줄은 「사용자 승인(15:47·15:51·15:53)」이라고 쓴다. 그런데 15:47:09 메시지 「아니 컴으로 내그 니한테한명령 ㅂㅇ솬아」는 전달되지 않은 명령을 묻는 말이지 승인이 아니다.
   - 100GB 목표의 출처는 15:54:23 「프로젝트폴더 용량 백기가 안으로 만들어」, 15:56:17 「맞아」, 16:01:36 「백기가 미만으로」다. 인계의 「사용자 승인 원문」 절에는 이 셋이 빠져 있다.
   - 위임 문맥의 시각 대응(「15:47 정리 하라고」, 「15:51 무조건 프로젝트폴더 용량 확보」, 「15:53 100GB 미만」)은 메시지 하나씩 밀려 있다. 실제는 15:51:20, 15:53:41, 15:54:23이다.
   - 범위 해석: 15:51 직전에 부모가 제안한 것은 「삭제해」라고 하면 **25.79GB(`.tmp/clones` 2 + 7차 후보 3)**를 지운다는 것이었다(15:44:16, 15:48:03). 실제 ①+④는 26,192,832,407 B라 이 숫자부터 맞지 않는다. 사용자는 ③ 56개나 ② HOLD 4개를 이름으로 승인하지 않았다. 인계는 이를 「총괄 세션의 해석」으로 구분해 적었지만, 보고서 4행 「사용자 승인에 따라」와 48행 「15:5x 사용자 추가 지시로 범위에 들어왔다」는 원문보다 강한 표현이다.
2. **worktree 역참조 3개 누락**(4절). 「끊긴 링크·gitdir 0」은 `.git/worktrees/*/gitdir` 3개를 뺀 값이다.
3. **보고서 115행 「스테이징된 변경이 있었다(`git status` = `MM`)」는 재현되지 않는다.** 지금 `git diff --cached`는 비어 있고 상태는 ` M`이며, `.git/index` mtime은 2026-10-24 20:48:36이다. 그 뒤 index가 쓰이지 않았으므로 17:1x에도 스테이징은 없었을 가능성이 높다.
4. **`backup-push-1103` 용량 귀속.** 40행과 60행은 4.93GB를 `backup-push-1103` 하나에 돌린다. 113행에 따르면 실제는 `backup-push-1103` 3,309,433,631 B와 `backup-push-1103-rm` 1,620,496,011 B의 합이다. ledger의 `backup-push-1103` `measured_bytes`는 2,872,651,527 B다.
5. **C: 여유 수치.** 보고서의 349.02GB는 17:06 시점 값으로는 맞다. 하지만 17:30 실측은 343.80GB이고, 위임 문맥의 349.47GB는 근거가 없다.

**합계 숫자는 전부 맞다**(검산 14/14 = 100%).
- 65행 합계: 1,217,470개, 93,266,602,317 B, 디렉터리 128,449개, junction 41개, 오류 0
- 묶음별 3·4·56·2개 합계
- 여유 증가 95,118,245,888 B, 부족분 50,982,350,848 B, 87.25%
- 삭제 전 추정 143.01GB, 예시 조합 51.06GB
- 이관 합계 105.47GB, 440.6GB, 402.6GB
- 큰 구성 12개(`datasets/travel` 11.63 등)
- ledger `measured_bytes` 2개, 승인 목록과 삭제 결과의 행별 파일·바이트(63/63)

**위키 링크**: 보고서의 상대 링크 15/15, 인계 5/5가 열린다(끊김 0). 단 `c400-docs-20261103/wiki` 사본은 16/17만 현재 파일과 같다. `handoff/index.md`가 복사 뒤 바뀌어 「단일 사본」 백업이 그 파일만 낡았다.

## 판정 요약

| 항목 | 통과/전체 |
|---|---|
| (1) 부재 65 + 존재 19 + 내용 불변 19 + ledger 1 + 비대상 그룹 14(scratch 포함, `.tmp` 나머지는 별도 동일) | 118/118 = 100% (wiki 추가 +17은 범위 밖 변화로 별도 기재) |
| (2) 해시 6세트 + store + 복원 2 | 9/9 = 100% (scratch-extra 2세트는 CRLF 처리 뒤 통과) |
| (3) final_workspace < 100GB | 1/1 = 100% |
| (4) junction·alternates·remote·.git 파일·프로세스 0 | 5/6 = 83%. worktree 역참조 3개 때문에 실패 1 |
| (5) 문서 | 불일치 5건(위 1–5), 합계 숫자 14/14, 링크 20/20 |

사용 모델: claude-opus-5-5 (Hermes guguroute 하위 세션, 읽기 전용 교차검증).

후속(2026-11-03 18:3x): 5절의 불일치 1–5를 [실행 보고서](2026-11-03_scratch-approved-deletion-and-project-prep.md)·[인계](../../handoff/2026-11-03_scratch-approved-deletion-handoff.md)·목차·log에 정정했다(정정 세션. 이 보고서 본문은 그대로).
