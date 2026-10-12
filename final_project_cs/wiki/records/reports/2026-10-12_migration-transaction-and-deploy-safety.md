---
type: report
title: SQL 전체 롤백·이미지 포함·실제 이전 이미지 복구 후속 수정
description: 기존 25개 wiki 검토와 분리한 로컬 코드 수정과 독립 DB 실행 시험
status: complete
domain: travel
---

# SQL 적용·배포 안전 후속 수정 — 2026-10-12

SQL 파일 원문을 바꾸지 않고 실행 시 파일 바깥의 단순 BEGIN/COMMIT을 문법으로 처리했습니다. 전체 입력 사전검사·단일 트랜잭션·중첩 savepoint를 지원합니다. 독립 PostgreSQL의 11개 실행 시험에서 기존 오류·부분 커밋 재현과 수정 후 전체 롤백·반복 적용을 확인했습니다. 운영 배포 완료를 뜻하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 독립 DB 실행 시험 | 통과 | 11/11 = 100% |
| 실제 x600 서버 배포 | 이번 범위 밖 | 0/1 = 0% |
| 실제 고객 흐름 시험 | 미실행 | 0/1 = 0% |

기본 이미지 빌드는 내장 실행기·제외 목록을 DB 접속 없이 검사합니다. 배포 검사기는 Compose 마운트 뒤 결과와 대조해 누락·오래된 마운트를 차단합니다. 배포 전 실제 실행 중 이미지 ID·최종 구성을 저장하고, 부분 실패·시간 초과 때 그 ID로 복구한 뒤 건강·재시작을 검사합니다. 상태를 가진 Docker 제어 모의 시험은 실제 Docker 배포와 구분합니다.

**새 후속 작업**으로서 기존 25개 현황 보고서·wiki-review-v2·이전 삭제 보고서는 수정하지 않았습니다. 이미 삭제한 과거 5표를 다시 삭제하지 않았고 실제 업무 DB 변경·커밋·푸시·x600 서버 배포도 하지 않았습니다. 독립 PostgreSQL은 이 작업 폴더에서만 만들고 종료했습니다. 운영과 다른 PostgreSQL 빌드이므로 실제 후보 Docker 이미지의 PostgreSQL 17 격리 확인은 배포 전 남은 관문입니다.

담당은 이번 변경을 수행한 Codex이며, 공통 DB 실행·배포 경로에 영향이 있습니다. 코드 검수·시험을 자체 수행했으며 별도 매니저·영향 기능 담당자의 독립 승인으로 표시하지 않습니다.

[변경 파일·실행 명령·배포 전후 확인·복구 절차](../../../../program/research/migration_safety_2026-10-12/README.md), [시험·한계 집계](../../../../program/research/migration_safety_2026-10-12/summary.json), [원문·공유 변경 보존 검사](../../../../program/research/migration_safety_2026-10-12/source-validation.json), [수정 전 백업](../../../../program/research/migration_safety_2026-10-12/backups.json), [배포 흐름도](../../../../program/research/migration_safety_2026-10-12/deployment-flow.html)를 확인합니다.
