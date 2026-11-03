---
type: handoff
title: EKS 새벽 첫 차량 실행 인과 후속
status: draft
domain: travel
---

# 새벽 첫 차량 후속 인계

추가 해소0/5 = **0%**, 잔여5/5 = **100%**, PR110 **HOLD 유지**입니다. [보고서](../records/reports/2026-10-29_eks-dawn-first-vehicle-causality.md).

한 일 목록:

- 루트/cs 규칙·wiki·실제 Hermes coord14개·데이터 REPORT를 확인했습니다.
- `/root/eksdawn_causality_1029/candidate` 새 no-hardlinks 사본에서 원본113/113=100% 해시와 제품/시험3/3=100% 바이트를 보존했습니다.
- 원래 새벽 실패1/1=100% 재현, 첫차 시험군2/3=66.67% 통과·1실패·skip0입니다. 나머지4개/전체223개 재실행은 하지 않았습니다.
- 실제710 승차 입력04:00 → best04:05/worst04:09를 추적했습니다. 기점 첫차03:50 비교 후 배차만 더하며, `_bus_board`는 막차만 상한 처리하고 첫차 도달은 검증하지 않습니다. 관측 차량은 없습니다.
- 원래 ID 직접 진단12회에서 seq1과seq20의 첫차 경계가 동일함을 확인했습니다. 수락시험12통과라고 표시하지 않습니다.
- 노선 기점명 상암차고지와 목록seq1 월드컵파크7단지를 구별했습니다. 이전12,048m는 목록seq1부터의 합이며 기점부터의 정확한 거리라는 단정은 보류합니다.
- 제품·시험·golden 변경0, 폴백/기대교체/삭제/운영/모델/push/merge/배포0입니다. 정류장 첫 차량 근거 또는 추정·결측 처리 계약이 없어 임의 수정하지 않았습니다.

다음: 방향·정류장별 첫 차량 자료/기점 대응을 확보하고 결측 처리 범위를 검토합니다. p90을 실제 첫차/최소 통과시각으로 쓰지 않습니다. 혼합2·golden2는 기존 인계를 유지합니다. 운영 fatal은 별도 미확정이며 PR110 HOLD 해제 조건은 기존 이유 로그·운영 수락입니다. 독립 검토자 승인·통합 예약은 없습니다.

모든 raw·도구 `C:/_proj/eksdawn_causality_1029`; 실제 Linux `/root/eksdawn_causality_1029`. [해시·실행 근거](../records/evidence/2026-10-29_eks-dawn-first-vehicle-causality/manifest.json). 원본 safe_git 조회는 WinError5로 실패했으며 우회하지 않았습니다.
