# EKS 후보 잠금 상충 수정 · 속도 반영 뒤 읽기 전용 확인 — 인계

## 현재 결론

EKS 후보 I(`1b38aa7ef`)가 C 의 `lock_policy` 재시도를 끄던 상충을 최신 팀 main `e88e01925` 위 격리 clone 에서 고쳤다(수정 커밋 `aaebdacc3`, push 0). 속도 후보 A·B 는 x600 에 17:23 반영됐지만 그 뒤 접수가 0건이라 실측 전후 비교는 아직 못 한다. AWS 자격증명은 여전히 무효(`InvalidClientTokenId`). [보고서](../records/reports/2026-10-27_eks-lock-policy-conflict-fix-and-latency-readback.md)

## 한 일 목록

- 루트 `AGENTS.md`·`CLAUDE.md`·인계 목차, 팀 원격 최신 `2026-10-27_계획서빙_속도_병목측정.md` · 통합 K 보고서 §4 를 읽었다. 원본에서는 `tools/safe_git.py fetch team` 만 실행(main `e88e01925`, role-manager `ffb5fb1b5`).
- x600 읽기 전용: deploy.log 반영 기록, `aws sts get-caller-identity`(무효), 집계 SQL 1회(`BEGIN READ ONLY` · 시한 · `ROLLBACK`, id · 원문 출력 0).
- 격리 clone `cache/scratch/eks-lock-fix-20261027` 에서 I cherry-pick(충돌 0) → RED 6 → 수정 → GREEN. `test_aws_cd` 45/45, `test_migration_lock_policy` 13/13, ruff 전체 통과.
- 바뀐 폴더(clone 안만): `final_project_cs/deploy/aws_cd.py` · `tests/unit/deploy/test_aws_cd.py` · `wiki/operations/aws-main-cd.md` · I 보고서. 원본 작업 폴더에는 이 보고서와 인계만 더했다.
- 상태: 수정 **끝 · push 대기(부모 결정)**. 서비스 · DB · 설정 · 원격 쓰기 0.

## 남은 일

1. `patches/0001`+`0002`(scratch `eks-lock-fix-ev/patches`)를 main PR 흐름에 올릴지 부모가 결정 → CI(main) · CI(web) · actionlint 재실행.
2. 유효한 AWS 자격증명이 생기면 첫 CD 의 migration Job 종료 기록(`attempts` · `sqlstate`)을 확인.
3. 반영 뒤 채팅 접수가 쌓이면 `serving-latency-after-20261027/q_after.sql` 로 A·B 효과 실측.
