---
type: handoff
title: EKS 남은 3실패 모양 C 원인 귀속 인계
status: draft
domain: travel
---

# 남은 3실패 원인 귀속 인계

**원인 귀속은 3/3이고 해소는 0/3입니다.** 누적 해소는 2/5 = 40%, PR110은 draft/HOLD입니다. [보고서](../records/reports/2026-10-29_eks-remaining3-shape-c-causality.md).

## 한 일

- 앞선 작업자가 인계 없이 멈춘 bisect(`C:/_proj/eksremain3_1029`)는 건드리지 않았습니다. 대신 `--shared` 사본 `/root/eksremain3r_1029`에서 이어서 진행했습니다. 입력은 113/113을 확인했습니다.
- mixed와 only_blocked는 `9c2edb189`가 원인입니다. 이 커밋에서 버스→버스(C)가 혼합 판정 슬롯에 들어갔습니다.
- 새벽(after_last_holiday)은 bisect 11단계로 찾았고, 병합 `2b5ad1633`에서 `_mixed_sources`에 C가 추가된 것이 원인입니다.
- tip 47549aa4에서 메모리상으로만 C를 끄면 원래 시험 5/5가 통과합니다.
- 기제: `MIX_VERIFY_MAX = 3` 자리를 구체화 뒤 89분으로 늘어난 B 하나와 C 둘이 차지합니다. 제품 자체 `_rank`로 더 나은 B(10:09·54분)는 판정되지 못합니다. 따라서 두 시험은 낡은 시험이 아니라 탐색 결함을 잡고 있습니다.

## 다음(결정 필요)

- 판정 순서를 구체화 뒤 추정으로 다시 정렬할지, 모양별 판정 몫이나 상한을 둘지 정해야 합니다. 상한을 바꾸면 서빙 지연을 측정해야 합니다.
- 새벽은 첫차의 중간 정류장 도달 근거를 어떻게 다룰지 계약이 필요합니다.
- 결정이 나면 원래 3시험이 RED입니다. 이를 GREEN으로 만들고 mobility_full 223 새 실패 0, 성능 전후 비교를 거칩니다.
- 운영 reader fatal은 읽기 경로가 없어 그대로입니다. 팀플로 반영은 manager 브랜치 담당만 합니다.

## 산출물

- 작업 폴더 `C:/_proj/eksremain3_resume_1029`
- WSL `/root/eksremain3r_1029`(약 3.8GB). 삭제 승인이 없어 보존합니다.
- 공유 증거 [폴더](../records/evidence/2026-10-29_eks-remaining3-shape-c-causality/)
