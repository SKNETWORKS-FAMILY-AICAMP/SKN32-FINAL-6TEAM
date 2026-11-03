---
type: handoff
title: EKS golden2 도보·시간·출발 문맥 후속 인계
status: draft
domain: travel
---

# golden2 인계

추가 해소 1/5 = **20%**(test_golden_bike), 잔여 4/5, PR110 **HOLD 유지**입니다. [보고서](../records/reports/2026-10-29_eks-golden-walk-context-causality.md).

한 일 목록:

- 중단된 Codex `eksgolden_causality_1029` 자료·coord 알림·관련 wiki/커밋 이력을 확인하고 Claude 알림을 남겼습니다. 기존 파일 수정 0, `claude_*` 파일만 추가했습니다.
- 원인 3갈래를 확인했습니다. 출발 문맥 추가, bike v1의 직선 138.5m×1.4=194m 도보(현행 계약상 제외), 기본 golden이 v1(10-14 v2 이전)을 가리키며 GH에 따라 달라지는 런타임을 쓴 것입니다. 두 시험은 `mobility_full`이라 계약 변경 때 갱신되지 않았습니다.
- 새 사본 `/root/eksgolden_causality_1029/claude_fix`에서 로컬 커밋 513ab4cc0e3a를 만들었습니다(push 없음). bike v2를 v1+계약 변환으로 독립 도출해 실제와 일치를 확인했고, concurrency golden은 all_v2 생산 런타임에서 비교합니다. 고정 시계를 적용했습니다. 제품·픽스처·입력·v1 golden 변경은 0입니다.
- 5파일 회귀는 21/24 통과·새 실패 0, 기본층은 12/12입니다. 입력은 113/113 보존됐습니다.

다음:

- 시계로 가려졌던 실제 차이가 남아 있습니다. bike를 섞으면 출발 문맥 options에 자전거 more_option이 생깁니다(10-23 more_options). 58 결정과 충돌하는지 Mobility 담당이 판정해야 하며, 그 전까지 실패로 둡니다.
- 담당 검토 대상: bike v2·all_v2 런타임 고정 수락, 혼합·새벽은 기존 인계대로입니다.
- 전체 223개, concurrent/interleave, lint는 미실행입니다. 독립 검토 승인과 통합 예약은 없습니다. 운영 reader fatal은 미확정입니다.
