# 회차 조립 실패로 독립 정리 작업과 상주 실행까지 중단

## 해결됨 (2026-10-11)

Team 조립에 실패해도 독립 정리·분류·안전 점검을 수행하고, 상주 실행은 다음 회차를 이어가도록 수정했습니다. [회귀 원문](../../evidence/2026-10-11_1936_team_plugin_implementation/worker-audit-regression-v2.log)의 32/32 시험이 통과했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 실패 격리·같은 판 유지 시험 | 통과 | 20/20 = 100% |
| 기존 종료 신호·감시 주기 시험 | 통과 | 12/12 = 100% |

## 원인·영향

[작업자 실행 코드](../../../../scripts/run_sweepers.py)의 `_in_round`가 Team 조립을 먼저 수행해, 필수 Team 적재나 이동 자료 오류가 나면 분류 되잡기·회원 정리·끝난 여행의 외부 값 정리까지 호출되지 않았습니다. 상주 반복문도 예외를 잡지 않아 다음 회차가 멈출 수 있었습니다. 실패한 Team 업무를 실행하는 문제와 구분되는 가용성 결함입니다.

이전 파일은 [원본 보존 폴더](../../../../legacy/team_plugin_worker_audit/2026-10-11_2130/)에 상대 경로대로 보존했습니다. 같은 작업자의 앞선 변경이 포함된 원본이며 Git 전체 diff를 이번 후속 변경으로 주장하지 않습니다.

## 수정·검증

[실행 가용성 계약](../../../teams/team-contract/plugin-availability.md)의 회차 실패 격리 문단을 먼저 추가했습니다. 조립 실패는 내부 `_CompositionFailed`로 구분하고, Team 의존 작업을 실행하지 않으며 fatal 건수를 남깁니다. 독립 작업을 재실행하지 않고 같은 회차 안에서 이어갑니다. 재난 안전 점검은 기존 주기 문을 지키며 수행합니다.

개별 작업 예외는 작업 이름·예외 종류·조립 판으로 기록하고 다음 작업을 수행합니다. 상주 실행은 회차 예외 뒤에도 다음 회차를 돌고, 단발 실행은 exit 1을 반환합니다. KeyboardInterrupt·SystemExit는 가로채지 않습니다. 예외 메시지의 고객 정보는 새 로그에 싣지 않습니다.

```powershell
python -m pytest tests/unit/travel/test_plugin_worker_availability.py tests/unit/core/test_run_sweepers_signals_errors.py tests/integration/test_watch_cadence.py -q
```

신규 시험은 조립 실패 원인 두 종류, 같은 판의 후속 작업 실행, 안전 점검 주기 문 열림·닫힘, 상주 예외 뒤 세 회차, 단발 실패 종료를 확인합니다. 이전 13개 worker 시험을 포함한 파일은 20개이며 종료 신호 4개와 DB 감시 주기 8개를 합쳐 32개입니다. [정적 검사](../../evidence/2026-10-11_1936_team_plugin_implementation/worker-e2e-audit-lint-v2.log)도 통과했습니다.

실서버 확인(서버 응답): 로컬 개발 서버의 앱 코드·PostgreSQL 감시 주기 시험을 실행했습니다. 운영 중인 cs 프로젝트 서버의 배포·네트워크 확인은 하지 않았습니다. mock 서버 화면 시험은 해당 없습니다. 커밋·푸시·배포는 하지 않았습니다.
