---
type: handoff
title: EKS golden2 자전거 58 충돌 판정 인계
status: draft
domain: travel
---

# golden2 자전거 58 인계

누적 해소 **2/5 = 40%**, 잔여 **3/5**, PR110 **HOLD 유지**입니다. [보고서](../records/reports/2026-10-29_eks-golden-bike-policy-review.md).

한 일 목록:

- 코드·명세·Codex를 대조했습니다. 10-23 `more_options`·`departure_context`가 섞어 준 자전거를 고를 수 있는 경로 후보로 싣는 것은 58 「left_out에 이유만」과 **충돌**합니다. 현재 제품 경로에서는 일어나지 않고, 라이브러리·CLI에서만 일어납니다.
- 새 사본 `/root/eksbike_policy_1029/review`에 로컬 커밋 `52f933e82dbb`(기준 513ab4cc)를 만들었습니다. push는 없습니다. 수정은 plan.py +6줄 필터와, 대조군·출발 문맥 단언을 더한 시험(+13줄)입니다. 기존 단언·골든·픽스처·입력 변경은 0입니다.
- golden2는 2/2 통과했습니다. 변이를 넣으면 실패합니다. 5파일 회귀는 22/24(새 실패 0)이고 기본층은 78/78입니다.
- bike v2는 조건부로 정당합니다(도보 근거 없는 fixture의 동작을 잠급니다). all_v2 런타임으로 바꾼 것은 약화가 아닙니다.

다음:

- 담당 확인이 필요합니다. 혼합 수단에서 자전거가 계획 수단으로 뽑힐 수 있는 경로(`_choose_planned`)는 바꾸지 않았습니다.
  - ☆2026-10-29 후속: 사용자가 판단을 위임해 실행으로 재현하고 고쳤습니다(로컬 커밋 56fc3ce1). [인계](2026-10-29_eks-mixed-bike-planned.md).
- foot 키를 담은 bike 요약 재기록, 혼합 1건·새벽 1건, 전체 223개·concurrent·lint, 통합 예약, 운영 reader fatal이 남아 있습니다.
