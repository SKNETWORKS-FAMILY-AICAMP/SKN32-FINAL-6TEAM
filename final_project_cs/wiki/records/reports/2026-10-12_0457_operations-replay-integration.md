---
type: report
title: 진단 기록 자동 재전송·영속 보관 접합 검증
status: draft
domain: travel
---

# 진단 기록의 자동 복구 접합

진단 기록의 재전송 CLI를 기존 공개 작업 일꾼에 연결했습니다. 오류 수집과 식당 조회 정책의 실제 호출 연결은 남습니다. 실제 업무 DB 변경·배포·원격 재시작·고객 알림·유료 호출·커밋·push는 하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 운영 재전송 관련 회귀 | 통과 | 27/27 = 100% |
| 작업 반복·볼륨 정의 검사 | 통과 | 8/8 = 100% |
| 담당이 인계한 운영 연결 묶음 | 재전송 묶음 검증 | 1/3 = 33% |

확인 시각: 2026-10-12T04:56:57+09:00. 27은 실제 선택 실행의 시험 수, 8은 셸 두 회차와 YAML 정의 검사 수입니다. 3은 인계 문서의 식당 조회·공통 오류 수집·자동 재전송 묶음 수이며 제품 전체 기능 수가 아닙니다. 최초 담당의 51개와 겹치는 시험이 있으므로 합산하지 않습니다.

## 동작과 경계

작업 일꾼은 진단 재전송과 만료 연결 정리를 먼저 실행합니다. 설정의 회차별 상한을 적용하며 실패가 있어도 감시·통지 배달 등 독립 작업과 다음 회차를 계속합니다. 재전송·보존 정리 실패를 별도 필드로 기록하고 실패 종료 코드를 유지합니다. 디스크 오류의 원문은 출력하지 않습니다. 누적 유실 수가 있으면 성공 종료로 숨기지 않습니다.

공개 API·작업 일꾼·운영 앱과 ARM API·작업 일꾼의 배포 정의에는 각 환경의 공유 영속 볼륨과 배포 판본 주입을 추가했습니다. 배포 판본 미설정은 `unrecorded`입니다. POSIX 대기 파일은 디렉터리 0700·파일 0600을 요구하도록 구현했으나 이번 Windows 실행으로 POSIX 권한 적용을 검증하지 않았습니다. 실제 볼륨 마운트·권한·재시작 시험은 남습니다. Windows의 ACL은 새로 설정하지 않았습니다.

## 실행과 원본

```powershell
python -B program/research/baseline_completion_2026-10-12/tasks/integration/run_operations_replay_checks.py
python -B program/research/baseline_completion_2026-10-12/tasks/integration/check_replay_worker.py
```

- [회귀 JUnit](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_045538_637275_operations_replay/junit.xml): 27 통과·실패/오류/건너뜀 각 0, 3.28초.
- [회귀 조건·소스 전후 해시](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_045538_637275_operations_replay/run.json): 8개 파일 전후 동일. 외부·기존 서비스·PostgreSQL 연결을 차단한 실행입니다. 실제 SQLite와 DB 트랜잭션 대역을 사용합니다.
- [작업 셸·YAML 결과](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_045657_378148_replay_worker/summary.json): 8/8. 원 작업 셸의 명령은 보존하고 반복을 두 번으로 한정했습니다. Python 명령은 대역 함수라 실제 outbox·감시·DB를 실행하지 않습니다. 첫 재전송 실패 1회 뒤 다음 회차의 재전송과 독립 작업 2회씩을 확인했습니다.
- DB 커밋 뒤 대기 행 삭제가 실패하는 회귀는 같은 발생 UUID로 두 번 전달되고 논리 발생 하나가 유지되는지 확인합니다. 실제 PostgreSQL 중복 방지·여러 프로세스 경쟁을 이 대역 시험으로 대체하지 않습니다.

첫 Git Bash 실행은 제한 환경의 Windows 내부 객체 생성 권한 오류로 시작하지 못했습니다. 원 [stderr](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_045633_456172_replay_worker/stderr.log)는 실행 폴더에서 보존하며 통과로 세지 않습니다. 자동 승인 검토를 거쳐 같은 한정 셸 검사를 권한 확장으로 실행했고 성공했습니다. 거절은 받지 않았습니다. 최초 오류 때 집계기의 stderr JSON 파싱도 실패해 안전하게 실패 결과를 남기도록 보완했습니다. 회귀 종료 후 pyreadline3 정리 오류는 시험 종료 코드 0·JUnit 통과와 별도로 원 출력에 남았습니다.

mock 서버 시험 (화면 반응): 안 했음 — 이번 접합은 화면을 수정하지 않았습니다.

실서버 확인 (서버 응답): 안 했음 — x600 서버의 cs 프로젝트 서버·ARM 앱·실제 PostgreSQL을 새로 호출하지 않았습니다.

## 남은 작업·백업

식당 조회 정책의 실제 호출, 공통 실행 오류 수집, PostgreSQL 다중 연결 설정·예산 경쟁, 최종 SQL 안전 실행, 전체 여행·공통·계약·보안 시험은 남습니다. 현재 [운영 계약](../../operations/unattended-operations.md)의 구현·검증 상태는 partial이며 전체 기능 완료로 올리지 않습니다.

수정 전 코드·설정·배포 정의·계약·시험은 [백업](../../../_backup/2026-10-12_045351_operations_replay_integration/)에 보존했습니다. 셸 검사기 보완 전 사본은 [검사기 백업](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/_backup/2026-10-12_0459_replay_shell_probe/)에 있습니다. 과거 기록과 담당별 원본 결과는 수정하지 않았습니다.
