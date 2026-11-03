---
type: handoff
title: EKS 남은 3실패 해소 후보 인계
status: draft
domain: travel
---

# 남은 3실패 해소 인계

**3/3을 해소한 후보 커밋 `1ab3f0d88`이 있고, push는 0입니다.** 누적 해소는 5/5이고 PR110은 HOLD입니다. 자세한 내용은 [보고서](../records/reports/2026-10-29_eks-remaining3-fix.md)에 있습니다.

## 한 일

- 혼합 판정 순서를 고쳤습니다(`candidates.settle_head`, `_mixed`·`_mixed_sources`).
  - 구체화(사고 반영) 뒤 늘어난 후보는 같은 모양의 남은 자리 안에서 뒤로 보냅니다.
  - 모양 자리와 판정 상한 3은 그대로입니다.
- 버스 첫차 승차 하한을 넣었습니다(`Verifier._first_pass_floor`).
  - 중간 정류장에서는 첫차가 그 정류장을 지나는 추정 시각보다 일찍 타지 않습니다. 추정기는 승차 소요와 같고, 새 불가는 만들지 않습니다.
  - 규칙과 경고 3개를 신설했습니다.
- 실측 결과:
  - mobility_full: 220/223 → 223/223
  - 빠른 층: 1611 → 1629, 새 실패 0
  - 변이 검사: D1을 빼면 3개, D2를 빼면 6개가 실패합니다.
  - 지연: 같은 10구간 합계 25.5초 → 23.5초
- Codex·Claude 검토를 3회 했습니다. 설계에서 둘이 같은 안에 합의했고, diff 2차 지적 5건을 반영한 뒤 3차에서 둘 다 ship-candidate였습니다.

## 다음

- 반영할 때: manager 담당이 `team/role-manager` tip 위에 `candidate.patch`를 `git -c core.autocrlf=false apply -3`로 올립니다. 그다음 mobility_full과 빠른 층을 다시 돌리고 push 순서를 따릅니다.
- 첫차 하한은 추정입니다. 정류장별 첫차 관측이 생기면 교체해야 합니다.
- 운영 reader fatal은 그대로이므로 PR110 HOLD를 유지합니다.

## 산출물

- 작업 폴더: `C:/_proj/eksfix3_1029`
- 후보 트리: WSL `/root/eksremain3r_1029/wt-bisect`. 기존 작업트리를 재사용해 새 사본은 0입니다.
- 증거: [폴더](../records/evidence/2026-10-29_eks-remaining3-fix/)
