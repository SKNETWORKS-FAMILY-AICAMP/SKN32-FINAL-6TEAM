---
type: handoff
title: EKS 섞어 준 자전거 계획 수단 58 수정 인계
status: draft
domain: travel
---

# 섞어 준 자전거 계획 수단(58) 인계

선행 [인계](2026-10-29_eks-golden-bike-policy-review.md)가 남긴 `_choose_planned` 항목을 마쳤습니다. 누적 해소는 **2/5 = 40%**로 그대로이고, PR110은 **HOLD**를 유지합니다. 자세한 내용은 [보고서](../records/reports/2026-10-29_eks-mixed-bike-planned.md)에 있습니다.

## 한 일

- 58 원문과 실제 실행을 대조했습니다. 자전거를 다른 탈것과 섞어 준 요청에서 자전거가 계획 수단이 되는 경우를 3가지 재현했습니다(짧은 구간, 택시와 섞음, 자전거만 성립). 이는 「추천하지 않는다 · 이유만」에 어긋납니다.
- Claude와 Codex가 각각 따로 판정했고, 둘 다 위반이며 A안이 맞다고 봤습니다.
- 새 사본 `/root/eksbike_planned_1029/review`에 로컬 커밋 `56fc3ce151c8`을 만들었습니다(기준 52f933e8). push는 하지 않았습니다.
  - `_bike_mixed()` 술어 하나로 정리했습니다. 섞어 준 요청에서는 자전거를 판정만 하고, left_out에 `bike_not_recommended` 한 줄을 남깁니다.
  - earliest의 자전거 소스를 뺐습니다.
  - extras 필터는 이제 닿지 않는 코드라 지웠습니다.
- 시험을 3개 더했습니다(RED 2/3 → GREEN 3/3). 변이 4개를 모두 검출했습니다.
- mobility_full 전체 223개는 기준과 같은 3개만 실패해 새 실패가 0입니다. 기본층은 1619 통과, 1 skip입니다. golden2는 2/2, ruff는 통과입니다.
- 최종 diff를 R3에서 두 검토자 모두 승인했습니다.
- R2는 diff를 변이 실행 도중에 떠서 무효입니다. 증거의 `r2_invalid/`에 보존했습니다.

## 다음

- 통합할 때는 52f933e8 위에 56fc3ce1을 함께 가져갑니다(같은 브랜치 선형).
- 필수는 아닌 후속 보강이 셋 있습니다.
  - departure_context에 대한 직접 단언.
  - 성립하지 않는 자전거와 earliest_on_late를 함께 다루는 혼합 시험.
  - 이유 문구 구분.
  - ☆2026-10-29 후속: 앞의 두 개는 시험으로 잠갔습니다(로컬 커밋 47549aa4). 이유 문구는 남아 있습니다. [인계](2026-10-29_eks-mixed-bike-followup.md).
- 이전부터 남은 일:
  - foot 키를 담은 bike 요약 재기록.
  - 3실패(earliest after_last_holiday, mixed stations_blocked, station_fallback only_blocked).
  - 통합 예약.
  - 운영 reader fatal.
