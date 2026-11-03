---
type: handoff
title: EKS 섞어 준 자전거 58 후속 시험 인계
status: draft
domain: travel
---

# 섞어 준 자전거 58 후속 인계

선행 [인계](2026-10-29_eks-mixed-bike-planned.md)의 필수 아닌 후속 3개 중 2개를 시험으로 잠갔습니다. 누적 해소는 **2/5 = 40%**, PR110은 **draft/HOLD** 그대로입니다. [보고서](../records/reports/2026-10-29_eks-mixed-bike-followup.md).

## 한 일

- 선행 사본이 깨끗하고 실행 중인 담당이 없음을 확인한 뒤, 새 사본 `/root/eksbike_followup_1029/review`(기준 56fc3ce1)에서만 작업했습니다. 입력 113/113을 해시로 확인했습니다.
- 시험 2개를 더했습니다. 하나는 departure_context 직접 단언이고, 다른 하나는 성립·불성립 자전거와 earliest_on_late를 섞은 시험입니다. 제품 코드 변경은 0입니다.
- RED는 52f933e8과 513ab4cc에서 각각 2/2 실패했습니다. GREEN은 2/2이고 변이 4/4를 검출했습니다.
- 기본층은 1621 통과·1 skip, golden2는 2/2, mobility_full 223은 같은 3실패로 새 실패가 0입니다. ruff는 통과입니다.
- 로컬 커밋은 `47549aa4e867`입니다. push·병합·배포는 0이고, 독립 검토는 받지 않았습니다.

## 다음

- 통합할 때는 52f933e8 → 56fc3ce1 → 47549aa4 순서로 같은 브랜치 선형으로 가져갑니다.
- 이유 문구 구분(앞 일정보다 먼저 떠나야 하는 자전거)은 문구 계약 결정이 필요합니다.
- foot 키를 담은 bike 요약 재기록, 3실패, 통합 예약은 그대로 남아 있습니다.
- 운영 reader fatal은 로그 접근 경로가 없어 막혀 있습니다. PR110 HOLD를 유지합니다.
- 팀플로에 넣는 작업은 manager(`role-manager`) 브랜치 담당만 합니다.
