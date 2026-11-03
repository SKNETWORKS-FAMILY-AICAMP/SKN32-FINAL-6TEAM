---
type: handoff
title: scratch 승인 삭제(①②③④) 실행·_unified_mall_3·test_workspace 삭제 준비 (2026-11-03)
description: 사용자 삭제 승인 원문·일시 기록과 실행 결과. 실행 중에는 진행 상태가 아래 「진행」 절에 갱신된다
status: active
domain: ops
impl_scope: 운영 기록. 삭제 대상은 승인된 final_workspace/scratch 63개와 .tmp/clones 2개 폴더뿐. 코드·Git 원본·datasets·모델·NPU·WSL·hiberfil·다른 프로필 변경 0
---

# scratch 승인 삭제 실행 — 인계 (2026-11-03 15:54 KST 시작)

세션 `20261103_155209_afc3cb`(부모 `20261103_032201_d047d36a`, Telegram 총괄). 앞선 분류·승인 목록: [인계](2026-11-03_scratch-unique-approval-handoff.md) · [보고서](../records/reports/2026-11-03_scratch-unique-classification-approval.md).

## 사용자 승인 원문 (Telegram, 부모 세션 d047d36a의 사용자 메시지 그대로)

- 2026-11-03 06:09:46 KST: 「아니이전에 400기가 확보했던거 참고하면 뭐 지울지 알수있잖아」
- 2026-11-03 15:43:07 KST: 「세션왜 멈춰있어?」
- 2026-11-03 15:47:09 KST: 「아니 컴으로 내그 니한테한명령 ㅂㅇ솬아」
- 2026-11-03 15:51:20 KST: 「아 정리 하라고 시발여다 장발했어」
- 2026-11-03 15:53:41 KST: 「컴퓨터정리해야 한다고 무조건 프로젝타폴더 용량ㅎㄱ보」

총괄 세션의 해석(이 세션에 전달된 지시):
- 15:52 승인 범위 = 묶음 ① 7차 후보 3개 16,353,443,130 B + ③ 나머지 56개 54,610,740,447 B(`st4f740-review-20261029` 마지막, `teamflow-unowned`와 `st4f729-followup` 함께) + ④ `.tmp/clones/hold3-integ-1102`·`hold3-eks-precision-r18`(폴더만, `.disk_guard_ledger.json`은 남김) 9,839,389,277 B. ② HOLD 4개는 제외.
- 15:5x 추가 지시(「무조건 프로젝트 폴더 용량 확보」): **② HOLD 후보 4개 12,463,029,463 B도 포함**(같은 방법, st4f740-review는 마지막). `C:/_proj/_unified_mall_3`·`C:/_proj/test_workspace`는 **삭제하지 않고 삭제 직전 상태로 준비만**(분류·최소 보존본·복원 시험·소유자 확인). 삭제 승인은 사용자에게서 받는다.
- 계속 금지: 달성 시점(10-27 20:21) 전부터 있던 scratch 폴더 19개, datasets, 모델, NPU(frog-npu-dev), WSL, hiberfil, 다른 프로젝트·프로필.
- 실행 방법(보고서 권장안): 직전 manifest와 크기·mtime 대조, 프로세스 참조 0 재확인, 새 소유자 세션 확인, junction은 링크만 `os.rmdir`, manifest에 있는 파일만 삭제 후 빈 디렉터리를 아래부터 삭제, 삭제 후 경로 부재·보존본 `SHA256SUMS.txt` 재확인·C: 여유 측정. `git clean/reset`·`robocopy /MIR` 등 재귀 삭제 도구 금지.

시작 시 C: 여유: 267,543,351,296 B (15:54:24).

## 진행

(실행 중 — 결과는 끝난 뒤 이 절과 보고서에 적는다)
