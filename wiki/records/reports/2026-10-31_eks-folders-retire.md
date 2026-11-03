# 2026-10-31 EKS 작업 폴더 정리 (세션 B)

사용자 지시(2026-10-31, 텔레그램): 「담당 세션들이 직접 작업을 마무리하고 전부 삭제하라」. 대상은 `C:/_proj/` 바로 아래 폴더 7개다. 이름이 정확히 같은 폴더만 다뤘다.

## 결론

- 삭제 6/7 = 86%: `eksbike_policy_1029` · `eksbike_planned_1029` · `eksbike_followup_1029` · `eksfix3_1029` · `eksremain3_1029` · `eksremain3_resume_1029`. 6개 모두 git 체크아웃이 아니고 링크·reparse point도 없는 증거 폴더였다(로그 · xml · json · patch · 스크립트). 이 폴더들을 쓰는 프로세스나 예약작업 · cron 참조는 0이었다.
- 보류 1/7: `_clones`. `tools/disk_guard.json` 이 이 폴더를 `ledger_path`(`C:/_proj/_clones/.disk_guard_ledger.json`)와 `managed_roots` 로 정해 두었다. `disk_guard.py` 의 `check` · `inventory` · `reserve` 는 실행할 때마다 장부를 다시 쓰고, 폴더가 없으면 새로 만든다. 이번 작업 중에도 장부가 다시 쓰였다(20:05:40). AGENTS.md 「디스크 증가 예방」은 모든 세션에 이 도구를 쓰라고 한다. 따라서 이 폴더를 계속 쓰는 쪽이 있다. 위치를 옮기려면 원본 `tools/` 를 고쳐야 해서 하지 않았다. 지금 들어 있는 것은 빈 장부(20바이트)뿐이고 lease · 사본 디렉터리는 0개다.

## 결론 문서 (이미 wiki에 있음)

| 폴더 | 결론 · 인계 |
|---|---|
| eksbike_policy_1029 | [보고](2026-10-29_eks-golden-bike-policy-review.md) · `handoff/2026-10-29_eks-golden-bike-policy-review.md` |
| eksbike_planned_1029 | [보고](2026-10-29_eks-mixed-bike-planned.md) · `handoff/2026-10-29_eks-mixed-bike-planned.md` |
| eksbike_followup_1029 | [보고](2026-10-29_eks-mixed-bike-followup.md) · `evidence/2026-10-29_eks-mixed-bike-followup/` |
| eksfix3_1029 | [보고](2026-10-29_eks-remaining3-fix.md) · `handoff/2026-10-29_eks-remaining3-fix.md` |
| eksremain3_1029 | 인계 없이 멈춘 bisect였다. 이어받은 결론은 [보고](2026-10-29_eks-remaining3-shape-c-causality.md)에 있다 |
| eksremain3_resume_1029 | [보고](2026-10-29_eks-remaining3-shape-c-causality.md) |

빠진 결론은 없다. 각 인계에 적힌 로컬 커밋(`52f933e8`, `56fc3ce1` 등)은 WSL `/root/eks*` 사본에 있다. 이 폴더들 안에는 없어서 이번 정리 범위 밖이다.

## 보관

- 위치: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/proj-folder-retire-20261031/<폴더>/`
- 폴더마다 `<폴더>_unique.tar.gz` 와 `MANIFEST.sha256.tsv` 를 두었다.
  - tar.gz: wiki `records/evidence` 에 같은 sha256 파일이 없는 것만 담았다.
  - MANIFEST: 모든 파일의 상대경로 · 크기 · sha256 · 위치(`archive` 또는 `wiki:<경로>`)를 적었다.
- 재대조 결과(삭제 직전 원본과 비교): 57/57 · 141/141 · 46/46 · 147/147 · 24/24 · 58/58이다. 비밀 · 인증 파일은 0개였다.
- 해제(압축 풀기): `tar -xzf <폴더>_unique.tar.gz`. 나머지 파일은 MANIFEST의 wiki 경로에 있다.

## 바이트

- freed_bytes 합계: 6,991,612. 폴더별 `du -sb` 값은 379,553 · 1,649,593 · 410,844 · 2,041,603 · 25,705 · 2,484,314다.
- 보관본 총 바이트: 872,831.
- C: 여유 바이트(삭제 직후): 242,261,721,088. 다른 세션이 동시에 쓰고 있어 정리 전후 차이는 freed_bytes와 같지 않다.

## 책임과 재확인 (2026-10-31 후속)

- 폴더를 만든 곳: 구구루트 총괄 Telegram 세션 `20261027_205452_5fbd35ab` — Codex exec 스레드(01a18661-7a1e, 01a1866b, 01a18784 등)와 Hermes 하위 세션(5b0e9f, 9b8d19, 5002f5, 7ae533, 20c7f7, f7610f, 44dcaf, A11 deleg_*).
- 정리·삭제 담당: 라우팅 세션 `20261024_213155_36cd5c`(하위 `deleg_bd131b61`).
- 보존본 재확인 결과: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/proj-folder-retire-20261031/_routing_session_result.json` 의 `readback_20261031`.
