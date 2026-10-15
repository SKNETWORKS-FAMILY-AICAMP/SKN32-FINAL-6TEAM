# 백그라운드 회차의 Team 실행 격리

담당 Team이 꺼진 감시 종류는 점검·Case 생성 전에 제외하고, 독립 종류와 정리 작업은 계속하도록 로컬 코드를 수정했습니다. 운영 반영·실제 외부 데이터 검증은 이 기록의 범위가 아닙니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 백그라운드 인수·기존 동기 회귀 | 통과 | 18/18 = 100% |
| 기존 비동기 묶음 회귀 | 통과 | 15/15 = 100% |
| 수정 파일 정적 검사 | 통과 | 5/5 = 100% |

분모는 실행한 pytest 항목 및 ruff 검사 대상 파일입니다. 전체 제품 인수 시나리오 24개나 운영 완료율을 뜻하지 않습니다.

## 변경과 근거

계약은 [실행 가용성 계약](../../teams/team-contract/plugin-availability.md)과 [수명 관리 계획](../../teams/team-plugin-lifecycle.md)입니다. 계획의 감시 미실행 기록과 백그라운드 판 전파를 구현했습니다.

- [회차 실행기](../../../scripts/run_sweepers.py:94)는 한 회차의 Controller·계산 표를 고정하고 중첩 작업도 재사용합니다. 다음 회차는 새 조립을 읽습니다. 독립 정리 작업만 요청하면 Team 조립을 요구하지 않습니다. 선택 기능은 후보 조립 성공 후 연결합니다.
- [묶음 계산](../../../app/domains/travel_ops/components/watch/trip_watch_batch.py:89)은 같은 판에서 Team과 계산 연결을 함께 확인합니다. 미실행을 `nothing`→`clear`로 완료 처리하지 않습니다. 다른 종류 계산은 계속하며 미실행 이유를 경고·운영 로그에 남깁니다.
- [Case 감시](../../../app/domains/travel_ops/components/watch/trip_watch_cases.py:73)와 [여행 감시](../../../app/domains/travel_ops/components/watch/trip_watch.py:43)는 disabled 종류를 점검 전에 제외하고 `unavailable`에 셉니다. Activity 조정자가 꺼졌을 때 실행 가능한 Dining·Mobility 문제는 자기 담당 Case로 각각 보냅니다.
- Case 실행 중 `TeamUnavailable`은 감시가 일반 예외로 다시 닫지 않습니다. Controller가 보존한 상태를 유지합니다. 활성 Team의 `engine_unavailable`과 조립 누락 `composition_unbound`는 의도적 비활성과 구분해 치명 건수에 포함합니다.

수정 전 네 파일은 [원본 보존 폴더](../../../legacy/team_plugin_lifecycle/2026-10-11_1936/)에 경로 그대로 복사했습니다. 다른 작업자의 기존 변경을 포함해 보존했으며, 전체 diff를 이 작업 혼자 작성한 것으로 주장하지 않습니다.

## 실행 검증

신규 [백그라운드 시험](../../../tests/unit/travel/test_plugin_worker_availability.py)은 13항목입니다. 종류별 미실행·독립 점검, 모든 종류 비활성, 묶음의 거짓 완료 방지, Activity 비활성 시 독립 담당, 중첩 회차 고정·다음 판 전환, 정리 업무 유지, 활성 엔진 장애의 치명 판정, Case 상태 보존, 판 없는 운영 호출 거절을 검증했습니다.

재현 명령:

```powershell
python -m pytest tests/unit/travel/test_plugin_worker_availability.py tests/unit/travel/test_departure_watch_assembly_v1.py tests/unit/core/test_run_sweepers_signals_errors.py -q --tb=short
python -m pytest tests/unit/travel/activity/test_watch_batch_unit.py -q --tb=short
python -m ruff check scripts/run_sweepers.py app/domains/travel_ops/components/watch/trip_watch.py app/domains/travel_ops/components/watch/trip_watch_cases.py app/domains/travel_ops/components/watch/trip_watch_batch.py tests/unit/travel/test_plugin_worker_availability.py
```

실행 로그: [동기 회귀 18항목](../evidence/2026-10-11_1936_team_plugin_implementation/worker-regression-v2.log), [비동기 묶음 15항목](../evidence/2026-10-11_1936_team_plugin_implementation/worker-batch-regression.log). 초기 9항목 중 시험의 monkeypatch 대상 오류 1개를 수정한 뒤 재실행했으며, 최종 로그를 인용합니다. 동기 제한 환경 실행은 종료 시 `pyreadline3` 콘솔 해제 경고가 있었지만 pytest 결과와 프로세스 종료 코드는 성공입니다. 비동기 시험은 제한 환경에서 진행이 멈춰 제한 밖에서 같은 명령으로 다시 실행했고 15항목이 통과했습니다.

mock 서버 시험: 해당 없음(화면 반응을 검증하지 않았습니다).

실서버 확인(서버 응답): 안 했음. 이 하위 작업은 DB·외부 API를 호출하지 않는 회차 계약 및 계산 회귀 시험입니다. 기존 cs 프로젝트 서버의 배포·운영 점검과 Claude 독립 검토는 상위 통합 작업에서 따로 판정해야 합니다.

## 남은 통합 확인

공통 출발 관측 팩토리는 Mobility 비활성 상태에서 구현을 불러오지 않는 검사가 필요하다고 상위 작업에 전달했습니다. 전체 JSON·SSE·MCP, Controller 상태·토큰, 원격 실행, 운영 배포의 보장은 이 하위 시험으로 대신하지 않습니다.
