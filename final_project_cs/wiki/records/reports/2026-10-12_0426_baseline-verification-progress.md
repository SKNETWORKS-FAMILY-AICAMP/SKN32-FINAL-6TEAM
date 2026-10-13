---
type: report
title: 기준선 공통·여행 검증 중간 기록
description: 격리 전체 시험의 실패와 기존 모니터링·모델·환경 근거 대조 위치
status: draft
domain: travel
tags: [quality, verification, baseline]
---

# 기준선 공통·여행 검증 중간 기록

공통 시험은 806통과·19실패이며 여행 전체 시험은 실행 중입니다. 최종 제품 통과와 배포 완료를 선언하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 공통 시험 실행 | 완료 | 825/825 = 100% |
| 공통 시험 통과 | 실패 포함 | 806/825 = 97.7% |
| 추가 운영 시험 | 건너뜀 포함 | 26/36 = 72.2% |
| 여행 전체 시험 | 실행 중 | 6,798건 중 완료 수 집계 중 |

관측 시각: 2026-10-12 04:26 KST. 정확한 후속 상태는 [담당 상태](../../../../program/research/baseline_completion_2026-10-12/tasks/verification/status.json), 조건·시각·모델 학습 여부·실행 해시는 [담당 보고서](../../../../program/research/baseline_completion_2026-10-12/tasks/verification/report.md)를 확인합니다. 19실패의 재현과 접합안은 [인계 기록](../../../../program/research/baseline_completion_2026-10-12/tasks/verification/failure-handoff.md)에 있습니다.

실제 업무 DB 대신 새 PostgreSQL 16.14·pgvector 임시 DB를 사용합니다. 외부 통신·기존 모델 연결을 차단했고 유료 호출·고객 알림·원격 배포·커밋·푸시는 실행하지 않았습니다. 운영 추가 시험의 건너뜀 10건과 실행 중 코드·SQL 변경을 최종 통합 검증에 남겼습니다.

mock 서버 시험(화면 반응): 이번 범위에서는 하지 않았습니다.

실서버 확인(서버 응답): 새로 하지 않았습니다. 기존 오라클 ARM 관측 기록을 시점을 표시해 대조했습니다. 새 DB 시험은 격리된 로컬 시험입니다.
