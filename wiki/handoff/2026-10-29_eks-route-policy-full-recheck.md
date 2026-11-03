---
type: handoff
title: EKS v0.9.3 전체 이동 재검증 인계
status: draft
domain: travel
---

전체 이동 **223/223 = 100.00%**, 집중 호환성 **73/73 = 100.00%**, 추가 과거/캐시 문맥 **11/11 = 100%**를 이번에 실행했습니다. **PR110 draft/HOLD·reader fatal 미해결·운영쓰기/push/merge/배포0**. [보고·실제 결과](../records/reports/2026-10-29_eks-route-policy-full-recheck.md).

한 일: 루트/cs 지침·wiki·coord15 재확인, 기존 `/root/eksremain3r_1029/wt-bisect` HEAD1ab3f0d88+미커밋 v0.9.3 설정/history/wiki 후보 재사용, 기존 데이터로 전체223층 재실행, 집중 저장/고정/운행일 경계 재검증, 실제 과거 snapshot 및 옛/누락 판×3수단 보존·사전 거절 확인, 판별 캐시 키/복사본 보존 확인, 실제 공개 입력 첫차4표본·출처 재생, 전후 해시·inventory·XML 보존. 새 제품 코드 수정·clone·전체 데이터 복사·삭제0.

정본은 후보 rules_v0.3.json(v0.9.3/source_id/effective_date)과 대응 history/wiki이며 원본/운영 적용은 아닙니다. 옛 문맥은 needs_replan/basis_changed → 알림 held; 자동 재계획/고객 고정 항목 변경 완료가 아닙니다. 첫차4표본은 모두 추정이며 실제 정류장 최초 도착 관측0, 정확도 분모 모름. v0.9.2 안의 기존 충돌 소급 식별 불가.

다음 담당: 최신 통합판에 기존 candidate.patch와 portable test_rules_policy_version_v1.py 검토·적용 및 필수 관문, 담당자 수락, 실제 첫차 정확도와 reader fatal 근거 확보. review-only test_policy_identity_review_v1.py는 외부 snapshot 경로를 쓰므로 통합 시험으로 그대로 넣지 않습니다. 이번 자체 검증을 제3자 승인/배포 허가로 사용하지 않습니다. 후보/기존 자료/모든 산출물 보존. 등록 clone0이라 release 없음. [기존 인계](2026-10-29_eks-route-policy-version-followup.md).


산출물 크기(최종 검증 직전): scratch 331,923바이트, 새 실행 스크립트 26,287바이트, bytecode 18,614바이트, evidence 260,693바이트. 전체층 temp 미생성, 집중층 temp du 10,035바이트. 기존 사본·자료는 보존했고 새 clone 0바이트입니다. [크기·inventory](../records/evidence/2026-10-29_eks-route-policy-full-recheck/artifact-sizes.json).
