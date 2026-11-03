---
type: handoff
title: EKS Linux 전체 원본113파일 기준선·시각/정밀표 원인 경계
status: draft
domain: travel
---

# EKS Linux 신뢰성 후속 인계

**PR110 draft/HOLD, 운영 fatal 원인 미확정.** [보고](../records/reports/2026-10-29_eks-linux-full-original-reliability.md)·[실행 집계](../records/evidence/2026-10-29_eks-linux-full-original-reliability/summary.json).

한 일 목록:

- 지침/wiki/지정 reader 인계/실제 PR110·coord 확인, main57f3d2f004d0의 새 격리 사본 준비.
- 기존61파일과 로컬 전체 원본의 차이를 확인. 원본113/113=100%(289,950,471바이트)를 별도 사본에 전부 복사·해시 검증, 백업/과거 그래프 포함 보존.
- Linux 전체층 두 입력 cohort 각각180/216=83.33% 통과·36실패·skip0.216/216=100% 결과 일치, 새 실패0. 기존 단언/golden/기능/관문 변경0.
- 시각 실패2건의 정상 비교 차이는 captured_at뿐, 전체113파일의 원래 음성대조·80건을 포함한 고정시계 진단2/2=100%. 기존 정밀표 경계 23/23=100%. canonical 실패에 합산하지 않음.
- 공식 원본423107행/대상104614행 재대조: 원값104613/104614=99.9990%,0초→null 한 칸을 명시하면104614/104614=100%.18건 실제 MISS와 선택 열차 근거 보존.
- 초기 harness46skip·CSV 요일코드 오류·원시1칸 차이 실패까지 보존. 원본 제품/Git 변경·DB/listener·운영접수/모델/권한/workflow/push/배포/삭제0.

다음: Mobility 담당에게 정밀표18개 기대·0초 정규화·요금/경로/golden 수락 근거 검토를, 매니저에게 릴리스 관문·독립 검토 연결을 요청할 필요가 있습니다. coord에 범위를 게시했으며 확인/승인을 받은 것은 아닙니다. 제품 시각 제거·precision 끄기·golden 덮어쓰기·시험 제외로 녹색화하지 않습니다. reader 운영 로그 기존 읽기 경로 미확보이므로 HOLD 유지, 새 자격·권한·workflow로 우회하지 않습니다. 원래 운영3회 baseline 보존, 전체 운영 검증 분모 모름.

소유: C:/_proj/ekslinuxreliability1029(모든 사본·113파일·XML·실패 기록 보존). 독립 검토자 미배정·통합 예약 없음. 새 작업은 coord·main/PR 최신 상태부터 확인합니다.
