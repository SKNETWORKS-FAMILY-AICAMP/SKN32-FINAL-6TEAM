---
type: handoff
title: scratch 승인 삭제(①②③④) 실행·_unified_mall_3·test_workspace 삭제 준비 (2026-11-03)
description: 사용자 지시 원문·일시(state.db timestamp)와 총괄 세션의 범위 해석, 실행 결과. 실행 중에는 진행 상태가 아래 「진행」 절에 갱신된다
status: active
domain: ops
impl_scope: 운영 기록. 삭제 대상은 승인된 final_workspace/scratch 63개와 .tmp/clones 2개 폴더뿐. 코드·Git 원본·datasets·모델·NPU·WSL·hiberfil·다른 프로필 변경 0
---

# scratch 승인 삭제 실행 — 인계 (2026-11-03 15:54 KST 시작)

세션 `20261103_155209_afc3cb`(부모 `20261103_032201_d047d36a`, Telegram 총괄). 앞선 분류·승인 목록: [인계](2026-11-03_scratch-unique-approval-handoff.md) · [보고서](../records/reports/2026-11-03_scratch-unique-classification-approval.md).

## 사용자 지시 원문 (Telegram, 부모 세션 d047d36a state.db의 사용자 메시지·timestamp 그대로)

- 2026-11-03 06:09:46 KST: 「아니이전에 400기가 확보했던거 참고하면 뭐 지울지 알수있잖아」
- 2026-11-03 15:43:07 KST: 「세션왜 멈춰있어?」
- 2026-11-03 15:47:09 KST: 「아니 컴으로 내그 니한테한명령 ㅂㅇ솬아」
- 2026-11-03 15:51:20 KST: 「아 정리 하라고 시발여다 장발했어」
- 2026-11-03 15:53:41 KST: 「컴퓨터정리해야 한다고 무조건 프로젝타폴더 용량ㅎㄱ보」
- 2026-11-03 15:54:23 KST: 「프로젝트폴더 용량 백기가 안으로 만들어」
- 2026-11-03 15:56:17 KST: 「맞아」 (15:54:37 총괄 세션이 「`C:/_proj/final_workspace`를 100GB 이하로」라고 해석한 것에 대한 답)
- 2026-11-03 16:01:36 KST: 「백기가 미만으로」, 「용량 낭비 없게 프로젝트폴더 줄여」

**정정 (18:3x, [독립 재검증](../records/reports/2026-11-03_scratch-approved-deletion-independent-verification.md))**: 위 목록의 처음 제목은 「사용자 승인 원문」이었다. 06:09·15:43은 맥락이다. 15:47:09는 컴퓨터에서 보낸 명령이 도착하지 않았다는 항의였고(15:43:24 「내가 컴에서 명령흔 것들 왜 안해」에 이어짐) 승인이 아니다. 삭제 지시는 15:51:20 「정리 하라고」와 15:53:41 「무조건 프로젝트폴더 용량 확보」다. 100GB 목표는 15:54:23·15:56:17·16:01:36에서 나왔다. 15:51 직전 총괄 세션의 제안은 ①+④ 25.79GB였다(15:44:16·15:48:03). 사용자는 묶음 ②(HOLD 4개)와 ③(56개)을 이름으로 대지 않았다. 아래 「총괄 세션의 해석」대로 「무조건 확보」 취지를 근거로 확대 해석해 지웠다. 65개 모두 보존본 해시 확인과 복원 시험을 마쳤고 손실은 0이다.

총괄 세션의 해석(이 세션에 전달된 지시):
- 15:52 삭제 범위(총괄 세션 해석. ③은 사용자가 이름을 대지 않은 확대 해석) = 묶음 ① 7차 후보 3개 16,353,443,130 B + ③ 나머지 56개 54,610,740,447 B(`st4f740-review-20261029` 마지막, `teamflow-unowned`와 `st4f729-followup` 함께) + ④ `.tmp/clones/hold3-integ-1102`·`hold3-eks-precision-r18`(폴더만, `.disk_guard_ledger.json`은 남김) 9,839,389,277 B. ② HOLD 4개는 제외.
- 15:54 총괄 세션의 범위 확대(근거 15:53:41 「무조건 프로젝트폴더 용량 확보」. ②를 이름으로 지정한 사용자 발언은 없음): **② HOLD 후보 4개 12,463,029,463 B도 포함**(같은 방법, st4f740-review는 마지막). `C:/_proj/_unified_mall_3`·`C:/_proj/test_workspace`는 **삭제하지 않고 삭제 직전 상태로 준비만**(분류·최소 보존본·복원 시험·소유자 확인). 삭제 승인은 사용자에게서 받는다.
- 계속 금지: 달성 시점(10-27 20:21) 전부터 있던 scratch 폴더 19개, datasets, 모델, NPU(frog-npu-dev), WSL, hiberfil, 다른 프로젝트·프로필.
- 실행 방법(보고서 권장안): 직전 manifest와 크기·mtime 대조, 프로세스 참조 0 재확인, 새 소유자 세션 확인, junction은 링크만 `os.rmdir`, manifest에 있는 파일만 삭제 후 빈 디렉터리를 아래부터 삭제, 삭제 후 경로 부재·보존본 `SHA256SUMS.txt` 재확인·C: 여유 측정. `git clean/reset`·`robocopy /MIR` 등 재귀 삭제 도구 금지.

시작 시 C: 여유: 267,543,351,296 B (15:54:24).

## 진행 (15:54–17:2x, 결과)

- [실측] 묶음 ①→④→②→③ 순서로 65/65 루트를 지웠다. 1,217,470파일 93,266,602,317 B, 폴더 안 junction 링크 41개(링크만), 오류 0, 건너뜀 0. 묶음마다 직전 manifest 대조(새 파일·크기·mtime 변경 0), 프로세스 참조 0, 새 소유자 0을 확인했다.
- [실측] 삭제 뒤 65/65 경로 부재, 달성 시점 폴더 19/19 그대로, `.disk_guard_ledger.json` 남김. 지운 경로를 가리키는 junction·alternates·`.git` 링크 파일·remote 0. **정정**: 보존본 `backups/scratch-candidates-20261029d/files/st4f711-backend-20261029-v1/repo/.git/worktrees/{repo,repo1,repo2}/gitdir` 3개는 지운 폴더를 가리킨다(아카이브 사본, 실사용 저장소 아님).
- [실측] 보존본 `c400-unique-20261103/SHA256SUMS.txt` 118/118, `store` 20,248/20,248, hold3 보존 213/213·117/117.
- [실측] C: 여유 267.54GB(15:54) → 362.66GB(16:03) → **349.02GB(17:06, 이 세션 실측)**. 400GB까지 50.98GB 부족(17:06 기준). 줄어든 몫은 이 세션 보존본 8.19GB와 다른 세션의 `.tmp/clones/backup-push-1103`(3.31GB)·`backup-push-1103-rm`(1.62GB)(16:10, `leased`) 등이다. 그 뒤 여유는 343.80GB(17:30:41, 독립 재검증)~350.91GB(18:28, 정정 작업)로 오르내린다.
- [실측] final_workspace 54.68GB 논리 / 55.90GB 할당(17:1x, `backup-push-1103`·`backup-push-1103-rm` 2개 4.93GB 포함. 둘이 사라진 뒤 17:23 독립 재검증 49.75GB). 100GB 미만.
- `_unified_mall_3`·`test_workspace`는 **지우지 않았다.** 보존본 `guguroute backups/c400-projprep-20261103/`(8.19GB, `SHA256SUMS.txt` 174/174, `README.md`에 복원 절차), 복원 시험 test_workspace 48,767/48,767·mall3 표본 2,067/2,067.
- 상세: [보고서](../records/reports/2026-11-03_scratch-approved-deletion-and-project-prep.md).

## 다음 담당자가 할 일

1. 사용자에게 `_unified_mall_3`(25.31GB)·`test_workspace`(12.65GB) 삭제 승인을 받는다. `test_workspace/npu_sm8735`는 NPU 소유자(`local-445eeffb…`, 기본 프로필) 확인 뒤에만. 지울 때도 이번과 같이 `backups/c400-projprep-20261103/<폴더>/manifest.jsonl.gz`와 크기·mtime 대조 → 파일 단위 삭제 → 부재·`SHA256SUMS.txt` 재확인.
2. 400GB까지 남는 몫은 hiberfil(관리자)·NPU·WSL 결정이다(보고서 「400GB까지 남은 것」).
3. `.tmp/clones/.disk_guard_ledger.json`의 지운 두 항목은 담당 36cd5c가 정리한다(설정 파일이라 이 세션은 고치지 않음).
4. 이 세션이 만든 wiki 파일은 **커밋·푸시하지 않은 단일 사본(untracked)**이다. 사본은 `guguroute backups/c400-docs-20261103/`에 있다. 같은 시각 다른 세션(`bk1103-backup-push`)이 백업 커밋을 준비 중이므로, 이 파일들이 그쪽 커밋에 들어갈지는 그 세션이 정한다. **후속**: 보고서·인계의 앞부분은 17:17 role-manager 커밋(`4c2f82a3b`)에 들어갔고, 18:3x 정정본이 그 위 커밋으로 팀·개인 role-manager에 올라갔다. evidence 폴더는 push 범위 밖이라 원본·외장에만 있다.
5. `.tmp/clones/backup-push-1103`(3.31GB)·`backup-push-1103-rm`(1.62GB)은 하위 세션 `20261103_160743_67c3f3`이 쓰는 중이라 지우지 않았다. 그 세션이 `release` 뒤 정리한다(독립 재검증: ledger `released_at 17:18:08`, 두 폴더는 17:12 뒤 사라짐).

## 독립 재검증 입력

- 대상 목록: [approval_list.json](../records/evidence/2026-11-03_scratch-unique-approval/approval_list.json) `post_peak` 63행 + `C:/_proj/final_workspace/.tmp/clones/{hold3-integ-1102,hold3-eks-precision-r18}`. 루트별 결과: [deletion_roots.json](../records/evidence/2026-11-03_scratch-approved-deletion/deletion_roots.json).
- 보존본: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/c400-unique-20261103/`(삭제 로그 `deletion-20261103/`), `.../backups/c400-projprep-20261103/`.
- 확인 명령(Git Bash):
  - 부재: `python -c "import json,os;d=json.load(open(r'C:/_proj/final_workspace/wiki/records/evidence/2026-11-03_scratch-unique-approval/approval_list.json',encoding='utf-8'));print(sum(os.path.exists(r['path']) for r in d['post_peak']), sum(os.path.exists(r['path'] if isinstance(r,dict) else r) for r in d['pre_peak_excluded']))"` → `0 19`
  - 해시: `cd <backups>/c400-unique-20261103 && sha256sum -c SHA256SUMS.txt | grep -c ': OK$'` → 118, `cd <backups>/c400-projprep-20261103 && sha256sum -c SHA256SUMS.txt | grep -c ': OK$'` → 174
  - 여유: `powershell -NoProfile -Command "(Get-PSDrive C).Free"`
