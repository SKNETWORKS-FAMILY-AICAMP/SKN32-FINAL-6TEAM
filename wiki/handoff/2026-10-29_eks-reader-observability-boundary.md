---
type: handoff
title: EKS reader 기존 읽기 관측 경로 미확보 HOLD
status: draft
domain: travel
---

# EKS reader 후속 인계

**PR110 draft·배포 HOLD. 운영 원인 미확정.** [보고](../records/reports/2026-10-29_eks-reader-observability-boundary.md)·[관측 집계](../records/evidence/2026-10-29_eks-reader-observability-boundary/observability-summary.json).

한 일 목록:

- 양쪽 지침/wiki·배포 계약·coord 관련 알림과 배포 SHA의 실제 reader/CD 경로를 읽었습니다.
- 원격 활성 workflow5/5=100%, 배포/워크플로 구성39/39=100% 읽기 검사. OIDC는 부수효과를 수행하는 CD deploy job뿐이며 기존 read-only 로그 분기가 없습니다. 로컬 AWS/kube/OIDC 실행 자격도 없습니다. IAM/RBAC live 거부가 아니라 기존 허용 읽기 실행 경로 미확보입니다. 실제 조직 로깅 부재로 일반화하지 않습니다.
- 새 격리 사본 배포 SHA 고정, 로그 분리7/7·기존24/24, 합31/31=100% 통과. 예산/정책/서킷 차단은 backend failed 로그 없이 최종 path=none reason에만 남는 점을 확인했습니다.
- main57f3d2f004d0·PR110 draft3fda4eee 유지. 제품 수정·workflow 실행/생성·권한 추가·모델 호출·운영 변경·배포·삭제0. 자료는 C:/_proj/eksobserve1029 보존, DB/listener 없음.

다음: 기존 권한으로 앱 로그 위치·보존·읽기 principal부터 확인하고 2026-10-28 22:09:29–22:12:00 UTC의 reader path=none backend/reason 집계만 받습니다. 시각만으로 합성 사건 귀속 금지. 연결 근거가 없으면 창 집계로 표시합니다. 원문/비밀/ID/전체 로그 수집 금지. 기존 경로가 없으면 HOLD 유지, 새 workflow·권한으로 우회하지 않습니다. 원인 확보 후 해당 조건을 격리 RED로 재현합니다. 운영 완료 전체 분모 모름. 원래3회 baseline은 보존합니다.
