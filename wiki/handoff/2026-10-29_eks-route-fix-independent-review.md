---
type: handoff
title: EKS 경로 후보 독립검토 재개 완료
status: draft
domain: travel
---

후보 `1ab3f0d88` 독립검토: 전체 223/223 = 100.00%, 빠른층 1629/1630 = 99.94%·skip1, 경계89/89 = 100%. 기준3실패 재현3/3 = 100%. **PR110 HOLD**, push/배포/운영/권한 변경0. [상세 보고](../records/reports/2026-10-29_eks-route-fix-independent-review.md).

한 일: 중단 로그·루트/cs 지침·wiki·실제 coord15개 확인, 기존 WSL 후보/기준 재사용, 공공입력113개+빈 marker 해시·5커밋파일 일치, 전체층/빠른층/저장·시각·고정 경계 재실행, 기준3실패 재현, 실제 route/context JSON 대조·ordinal4/4, 717노선/41103구간 점검·첫차 추정등급 확인, 동일10경로와 ABBA 성능 비교를 했습니다. 원본·기존 산출물·실패 로그 모두 보존했습니다.

남은 일: (1) **P2** 새 첫차 정책인데 양쪽 rules_version v0.9.2/input_basis 동일 — 정책판·이력/내용식별과 이전 context 처리 정리, 현재 wiki에 추정·미상·관측 우선 명시. (2) 성능 비용 수락: 이번10경로 합계 24.099→26.576초; EKS 개선 입증 아님. (3) 실제 정류장 첫차 관측 정확도 미검증과 운영 reader fatal HOLD를 유지하고 최신 통합판의 관문을 별도 실행. 이 남은 항목은 운영 전체 분모 모름으로 완료율을 만들지 않습니다.

작업 위치: `C:/_proj/eks-independent-1029`; 원래 후보 `/root/eksremain3r_1029/wt-bisect` 수정0, 새 clone0. runner raw 결과는 `C:/_proj/eksfix3_1029/independent-review-*`, 복사한 검토 증거는 [evidence](../records/evidence/2026-10-29_eks-route-fix-independent-review/). own pytest temp는 `/root/eksfix3_1029/pytest-independent-review-*`. 삭제·통합 예약 없음. 등록된 새 clone이 없어 release 대상 없음. 전체 디스크 가드 inventory와 작은 산출물 크기는 보고서에 있습니다.


2026-10-29 EKS 정책판 P2 후속: 집중71/71·portable2/2=100%, 10구간 ABBA 17.473→15.531초. PR110/운영 fatal HOLD. [후속](../records/reports/2026-10-29_eks-route-policy-version-followup.md).
